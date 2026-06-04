"""
Live disconnect smoke test. Run while `python -m agent.api` is up on :8058.

  python tests/manual_sse_disconnect.py

Posts a real case to /clinical/plan/stream, reads N frames, then aborts.
The server log should show the workflow stopping early (no Stage 5/6 completion).
"""
import asyncio
import json
import sys
import time
import httpx

URL = "http://127.0.0.1:8058/clinical/plan/stream"
BODY = {
    "case": {
        "chief_complaint": "palpitations and shortness of breath",
        "age": 68,
        "sex": "M",
        "comorbidities": ["hypertension"],
        "current_medications": ["amlodipine 5mg"],
        "allergies": [],
    }
}
DROP_AFTER_FRAMES = 3   # disconnect after 3 SSE frames


async def main():
    print(f"POST {URL} — will drop after {DROP_AFTER_FRAMES} frames")
    start = time.monotonic()
    frames_seen = 0
    async with httpx.AsyncClient(timeout=None) as client:
        async with client.stream("POST", URL, json=BODY) as resp:
            print(f"  HTTP {resp.status_code}  content-type={resp.headers.get('content-type')}")
            async for line in resp.aiter_lines():
                if not line:
                    continue
                if line.startswith("id:") or line.startswith("event:") or line.startswith("data:"):
                    print(f"  [{time.monotonic()-start:5.2f}s] {line[:120]}")
                if line.startswith("event:"):
                    frames_seen += 1
                    if frames_seen >= DROP_AFTER_FRAMES:
                        print(f"  >>> dropping connection after {frames_seen} events")
                        break
    print(f"  client closed at t={time.monotonic()-start:.2f}s")
    print("  Now watching server log for ~10s — Stage 5/6 should NOT complete.")


if __name__ == "__main__":
    asyncio.run(main())
