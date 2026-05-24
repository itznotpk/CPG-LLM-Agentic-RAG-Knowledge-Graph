"""
Smoke tests for the shared SSE helper in agent.api._sse_stream.

Validates the four guarantees the helper was introduced to provide:
  1. Events carry monotonic `id:` sequence numbers, terminated by `done`.
  2. Ordering is preserved end-to-end.
  3. Producer exceptions surface as `event: error` then `done` (no mid-stream 500).
  4. Client disconnect cancels the producer task — Stage 5/6 work stops.
"""
import asyncio
import re
import pytest

from agent.api import _sse_stream, _SSE_HEARTBEAT_SEC


class FakeRequest:
    """Minimal Starlette-Request stand-in: only is_disconnected() is consulted."""
    def __init__(self):
        self._disconnected = False

    def disconnect(self):
        self._disconnected = True

    async def is_disconnected(self):
        return self._disconnected


async def _drain(response, max_frames=50, timeout=2.0):
    """Pull frames from a StreamingResponse body_iterator until `done` or limit."""
    frames = []
    async def runner():
        async for chunk in response.body_iterator:
            if isinstance(chunk, bytes):
                chunk = chunk.decode()
            frames.append(chunk)
            if "event: done" in chunk or len(frames) >= max_frames:
                break
    await asyncio.wait_for(runner(), timeout=timeout)
    return frames


def _parse(frames):
    """Return list of (id, event, data) tuples, ignoring `: ping` comment lines."""
    parsed = []
    for f in frames:
        if f.startswith(": "):
            continue
        m = re.match(r"id: (\d+)\nevent: (\S+)\ndata: (.*)\n\n", f, re.DOTALL)
        if m:
            parsed.append((int(m.group(1)), m.group(2), m.group(3)))
    return parsed


# ── 1. Happy path: id ordering + terminal done ────────────────────────────────

@pytest.mark.asyncio
async def test_sse_emits_monotonic_ids_and_terminates():
    req = FakeRequest()

    async def producer(emit):
        await emit("stage_update", {"stage": 2, "status": "running"})
        await emit("stage_update", {"stage": 2, "status": "complete"})
        await emit("safety_review", {"safe_to_proceed": True})
        await emit("final_result", {"ok": True})

    resp = await _sse_stream(req, producer, "happy")
    frames = await _drain(resp)
    parsed = _parse(frames)

    ids = [p[0] for p in parsed]
    events = [p[1] for p in parsed]

    assert ids == list(range(1, len(ids) + 1)), f"non-monotonic ids: {ids}"
    assert events[-1] == "done"
    # Stage-6 contract: safety_review precedes final_result.
    assert events.index("safety_review") < events.index("final_result")


# ── 2. Ordering preserved under producer back-pressure ────────────────────────

@pytest.mark.asyncio
async def test_sse_preserves_order_with_many_events():
    req = FakeRequest()
    N = 100

    async def producer(emit):
        for i in range(N):
            await emit("tick", {"i": i})

    resp = await _sse_stream(req, producer, "order")
    frames = await _drain(resp, max_frames=N + 5)
    parsed = _parse(frames)

    ticks = [p for p in parsed if p[1] == "tick"]
    assert len(ticks) == N
    # JSON payloads should arrive in producer order.
    seen = [int(re.search(r'"i":(\d+)', p[2]).group(1)) for p in ticks]
    assert seen == list(range(N))


# ── 3. Producer exception → graceful error frame, no crash ────────────────────

@pytest.mark.asyncio
async def test_sse_producer_exception_becomes_error_event():
    req = FakeRequest()

    async def producer(emit):
        await emit("stage_update", {"stage": 5, "status": "running"})
        raise RuntimeError("synthesize blew up")

    resp = await _sse_stream(req, producer, "boom")
    frames = await _drain(resp)
    parsed = _parse(frames)
    events = [p[1] for p in parsed]

    assert "error" in events
    assert events[-1] == "done"
    err_payload = next(p[2] for p in parsed if p[1] == "error")
    assert "synthesize blew up" in err_payload


# ── 4. THE BIG ONE: disconnect cancels the producer mid-flight ────────────────

@pytest.mark.asyncio
async def test_sse_disconnect_cancels_producer():
    """
    Simulates a client dropping during Stage 5. The producer is awaiting a long
    sleep (stand-in for a Gemini call); after the heartbeat tick, the helper
    sees is_disconnected()==True and must cancel the producer task.
    """
    req = FakeRequest()
    producer_cancelled = asyncio.Event()
    producer_finished = asyncio.Event()

    async def producer(emit):
        try:
            await emit("stage_update", {"stage": 5, "status": "running"})
            # Stand-in for the Stage 5 Gemini call. Must be cancellable.
            await asyncio.sleep(60)
            producer_finished.set()
        except asyncio.CancelledError:
            producer_cancelled.set()
            raise

    # Speed up the heartbeat probe so the test doesn't wait 15s.
    import agent.api as api_mod
    orig = api_mod._SSE_HEARTBEAT_SEC
    api_mod._SSE_HEARTBEAT_SEC = 0.05
    try:
        resp = await _sse_stream(req, producer, "drop")

        # Consume one frame, then "drop" the client and close the body iterator.
        it = resp.body_iterator.__aiter__()
        first = await asyncio.wait_for(it.__anext__(), timeout=1.0)
        assert b"stage_update" in (first if isinstance(first, bytes) else first.encode())

        req.disconnect()

        # Closing the iterator triggers the generator's `finally` → cancels producer.
        await it.aclose()
    finally:
        api_mod._SSE_HEARTBEAT_SEC = orig

    # The producer must have been cancelled, not completed.
    await asyncio.wait_for(producer_cancelled.wait(), timeout=1.0)
    assert not producer_finished.is_set(), "producer ran to completion after disconnect"
