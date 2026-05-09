# Step 07B — DDx LLM Re-ranking with Gemini 2.5 Flash Thinking

## Context

Step 07 is complete. This is a **targeted patch** to `agent/clinical_stages.py` only.

The current `stage_2_ddx` returns ICD-11 codes ranked purely by vector similarity + morbidity tabulation rules. This misses clinical context: a 68-year-old male with palpitations, HTN, and HR=110 should score AF higher than anxiety — but the embedding doesn't know that age, sex, vitals, and medications are clinically weighted fields.

**MedFlow (Reference)** solves this with Gemini 2.5 Flash + `ThinkingConfig` on the DifferentialDiagnosis node. We adopt the same pattern via OpenRouter (no new SDK — same `openai.AsyncOpenAI` client already in use).

---

## What to read first

- [agent/clinical_stages.py](../agent/clinical_stages.py) — the file to patch (lines 56–68, `stage_2_ddx`)
- [MedFlow (Reference)/backend/thinking_stream.py] — reference implementation of ThinkingConfig
- [MedFlow (Reference)/backend/doctor_graph.py] — how DDx node uses thinking

---

## Objective

Add a **Pass 2 LLM re-rank** step inside `stage_2_ddx`. The function signature is unchanged — callers see no difference.

```
stage_2_ddx(case)
    │
    ├─ Pass 1 (existing): search_ddx() → top 10 vector + tabulation candidates
    │
    └─ Pass 2 (new):  Gemini 2.5 Flash + thinking → re-ranked top 5
                      falls back to Pass 1 order if LLM call fails
```

---

## Changes to `agent/clinical_stages.py`

### 1. New constant at module level

```python
DDX_RERANK_MODEL = "google/gemini-2.5-flash-preview"
DDX_THINKING_BUDGET = 5000   # tokens; MedFlow uses 8000, 5000 is enough for re-rank
```

### 2. New function `_llm_rerank_ddx`

Add after `_build_symptom_text`, before `stage_2_ddx`:

```python
async def _llm_rerank_ddx(
    case: PatientCase,
    candidates: list[DDxResult],
) -> list[DDxResult]:
    """
    Re-rank DDx candidates using Gemini 2.5 Flash extended thinking.

    Applies clinical reasoning over age, sex, vitals, comorbidities, medications
    that pure vector similarity cannot weight correctly.
    Falls back to original order on any failure.
    """
    if not candidates:
        return candidates

    client = openai.AsyncOpenAI(
        base_url=os.getenv("LLM_BASE_URL"),
        api_key=os.getenv("LLM_API_KEY"),
    )

    vitals_str = json.dumps(case.vitals) if case.vitals else "none"
    candidate_lines = "\n".join(
        f"  {i+1}. {c.code}  {c.title}  (vector score: {c.similarity:.3f})"
        for i, c in enumerate(candidates)
    )

    prompt = f"""You are a clinical coding expert performing differential diagnosis.

Patient:
- Chief complaint: {case.chief_complaint}
- Age / sex: {case.age or "unknown"} / {case.sex or "unknown"}
- History: {case.history or "none"}
- Comorbidities: {", ".join(case.comorbidities) or "none"}
- Current medications: {", ".join(case.current_medications) or "none"}
- Allergies: {", ".join(case.allergies) or "none"}
- Vitals: {vitals_str}

Candidate ICD-11 codes (pre-ranked by vector similarity):
{candidate_lines}

Re-rank these candidates based on clinical probability for THIS specific patient.
Apply reasoning about:
- How age, sex, vitals, and comorbidities shift the prior probability of each code
- Whether current medications suggest an existing diagnosis
- Which codes are actionable vs incidental findings

Return a JSON array of objects, ordered from most to least likely. Include ALL candidates.
No markdown fences. Example format:
[
  {{"code": "BC81.3", "confidence": 0.91, "reasoning": "68M irregular pulse HR 110 — persistent AF fits best"}},
  {{"code": "BC81.1", "confidence": 0.72, "reasoning": "Paroxysmal AF cannot be excluded without Holter"}},
  ...
]"""

    try:
        resp = await client.chat.completions.create(
            model=DDX_RERANK_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=1,          # required when thinking is enabled
            extra_body={
                "thinking": {
                    "type": "enabled",
                    "budget_tokens": DDX_THINKING_BUDGET,
                }
            },
        )
        raw = resp.choices[0].message.content.strip().strip("` \n")
        if raw.startswith("json"):
            raw = raw[4:]
        ranked = json.loads(raw)

        # Map re-ranked codes back to DDxResult objects, preserving all fields
        code_to_result = {c.code: c for c in candidates}
        reranked: list[DDxResult] = []
        for item in ranked:
            code = item.get("code")
            if code and code in code_to_result:
                result = code_to_result[code].model_copy()
                # Append LLM reasoning to existing reasoning list
                llm_reason = item.get("reasoning", "")
                if llm_reason:
                    result.reasoning = result.reasoning + [f"LLM: {llm_reason}"]
                reranked.append(result)

        # Safety: any candidates the LLM dropped → append at end
        seen = {r.code for r in reranked}
        for c in candidates:
            if c.code not in seen:
                reranked.append(c)

        logger.info("DDx re-ranked %d candidates via %s", len(reranked), DDX_RERANK_MODEL)
        return reranked

    except Exception as exc:
        logger.warning("DDx LLM re-rank failed (%s) — using original order", exc)
        return candidates   # graceful fallback
```

### 3. Update `stage_2_ddx` to call re-rank

Replace the existing `stage_2_ddx` function (lines 56–68) with:

```python
async def stage_2_ddx(
    case: PatientCase,
    top_k: int = 5,
    rerank: bool = True,
) -> list[DDxResult]:
    """
    Return top-k ICD-11 differential diagnoses for the patient case.

    Pass 1: vector similarity + morbidity tabulation (search_ddx).
    Pass 2: Gemini 2.5 Flash thinking re-ranks by clinical probability.
    Set rerank=False to skip Pass 2 (e.g. in unit tests or latency-sensitive paths).
    """
    from ddx.search_ddx import search_ddx

    symptom_text = _build_symptom_text(case)

    # Pass 1 — fetch more candidates than needed so re-ranker has material to work with
    fetch_k = top_k * 2 if rerank else top_k
    raw = await search_ddx(symptom_text, top_k=fetch_k)

    results: list[DDxResult] = []
    for r in raw:
        try:
            results.append(
                DDxResult(**{k: v for k, v in r.items() if k in DDxResult.model_fields})
            )
        except Exception as exc:
            logger.warning("Skipping malformed DDx result %r: %s", r, exc)

    # Pass 2 — LLM re-rank (skipped if rerank=False or no results)
    if rerank and results:
        results = await _llm_rerank_ddx(case, results)

    return results[:top_k]
```

---

## Changes to `tests/test_clinical_stages.py`

Add these tests. Do NOT remove any existing tests.

```python
# ── Stage 2 re-rank tests ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_stage2_rerank_called_by_default(minimal_case):
    """rerank=True by default → _llm_rerank_ddx is called."""
    with patch("ddx.search_ddx.search_ddx", return_value=MOCK_DDX_RAW[:4]), \
         patch("agent.clinical_stages._llm_rerank_ddx", new_callable=AsyncMock) as mock_rerank:
        mock_rerank.return_value = [DDxResult(code="BC81.3", title="AF", similarity=0.91)]
        result = await stage_2_ddx(minimal_case, top_k=1)
        mock_rerank.assert_called_once()
        assert result[0].code == "BC81.3"


@pytest.mark.asyncio
async def test_stage2_rerank_skipped_when_false(minimal_case):
    """rerank=False → _llm_rerank_ddx is never called."""
    with patch("ddx.search_ddx.search_ddx", return_value=MOCK_DDX_RAW[:2]), \
         patch("agent.clinical_stages._llm_rerank_ddx", new_callable=AsyncMock) as mock_rerank:
        await stage_2_ddx(minimal_case, top_k=2, rerank=False)
        mock_rerank.assert_not_called()


@pytest.mark.asyncio
async def test_rerank_uses_gemini_25_flash(minimal_case):
    """_llm_rerank_ddx calls the DDX_RERANK_MODEL with thinking extra_body."""
    candidates = [
        DDxResult(code="BC81.3", title="AF", similarity=0.91),
        DDxResult(code="BA00", title="HTN", similarity=0.72),
    ]
    mock_resp = MagicMock()
    mock_resp.choices[0].message.content = json.dumps([
        {"code": "BC81.3", "confidence": 0.92, "reasoning": "fits best"},
        {"code": "BA00",   "confidence": 0.45, "reasoning": "comorbid"},
    ])
    with patch("agent.clinical_stages.openai.AsyncOpenAI") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value = mock_client
        mock_client.chat.completions.create = AsyncMock(return_value=mock_resp)

        result = await _llm_rerank_ddx(minimal_case, candidates)

        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["model"] == DDX_RERANK_MODEL
        assert call_kwargs["extra_body"]["thinking"]["type"] == "enabled"
        assert call_kwargs["extra_body"]["thinking"]["budget_tokens"] == DDX_THINKING_BUDGET
        assert call_kwargs["temperature"] == 1


@pytest.mark.asyncio
async def test_rerank_fallback_on_llm_failure(minimal_case):
    """If LLM call raises, original candidate order is preserved."""
    candidates = [
        DDxResult(code="BC81.3", title="AF", similarity=0.91),
        DDxResult(code="BA00",   title="HTN", similarity=0.72),
    ]
    with patch("agent.clinical_stages.openai.AsyncOpenAI") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value = mock_client
        mock_client.chat.completions.create = AsyncMock(side_effect=Exception("timeout"))

        result = await _llm_rerank_ddx(minimal_case, candidates)
        assert [r.code for r in result] == ["BC81.3", "BA00"]  # original order


@pytest.mark.asyncio
async def test_rerank_appends_llm_reasoning(minimal_case):
    """LLM reasoning string is appended to DDxResult.reasoning list."""
    candidates = [DDxResult(code="BC81.3", title="AF", similarity=0.91, reasoning=["Vector similarity 0.910"])]
    mock_resp = MagicMock()
    mock_resp.choices[0].message.content = json.dumps([
        {"code": "BC81.3", "confidence": 0.92, "reasoning": "68M fits AF profile"},
    ])
    with patch("agent.clinical_stages.openai.AsyncOpenAI") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value = mock_client
        mock_client.chat.completions.create = AsyncMock(return_value=mock_resp)

        result = await _llm_rerank_ddx(minimal_case, candidates)
        assert any("LLM:" in r for r in result[0].reasoning)
        assert any("Vector" in r for r in result[0].reasoning)


@pytest.mark.asyncio
async def test_rerank_drops_no_candidates(minimal_case):
    """If LLM response omits a candidate, it is appended at end — no data loss."""
    candidates = [
        DDxResult(code="BC81.3", title="AF",  similarity=0.91),
        DDxResult(code="BA00",   title="HTN", similarity=0.72),
    ]
    mock_resp = MagicMock()
    # LLM only returns one of the two
    mock_resp.choices[0].message.content = json.dumps([
        {"code": "BC81.3", "confidence": 0.92, "reasoning": "top pick"},
    ])
    with patch("agent.clinical_stages.openai.AsyncOpenAI") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value = mock_client
        mock_client.chat.completions.create = AsyncMock(return_value=mock_resp)

        result = await _llm_rerank_ddx(minimal_case, candidates)
        codes = [r.code for r in result]
        assert "BC81.3" in codes
        assert "BA00" in codes   # appended, not lost
        assert len(result) == 2
```

---

## No other files to change

- `agent/routing.py` — unchanged
- `agent/tools.py` — unchanged
- `agent/db_utils.py` — unchanged
- `ddx/search_ddx.py` — unchanged
- `tests/test_routing.py` — unchanged

---

## Implementation notes

- `temperature=1` is **required** by OpenRouter when `thinking` is enabled — do not use 0.1 or 0.2 for this call.
- The `extra_body` dict is passed through by `openai.AsyncOpenAI` as additional JSON fields — no library change needed.
- `DDX_RERANK_MODEL = "google/gemini-2.5-flash-preview"` is intentionally **hardcoded**, not read from `LLM_CHOICE` env var. DDx re-ranking needs a thinking-capable model; the standard env var may point to a model that doesn't support it.
- Fetch `top_k * 2` candidates in Pass 1 when re-ranking (e.g. top_k=5 → fetch 10). This gives the LLM enough material to discriminate. Cap at `top_k` after re-rank.
- The fallback (original vector order) means **no pipeline breakage** if OpenRouter is down, Gemini 2.5 Flash is unavailable, or the response is unparseable.
- MedFlow uses `thinking_budget=8000` for a full replanning node. `5000` is sufficient for re-ranking 10 candidates — the task is simpler.

---

## Done criteria

1. `pytest tests/test_clinical_stages.py -v` — all previous 17 tests + 6 new re-rank tests = **23 green**.
2. `stage_2_ddx(case, rerank=False)` — `_llm_rerank_ddx` is never called (verified by test).
3. `stage_2_ddx(case, rerank=True)` — `openai.AsyncOpenAI.chat.completions.create` is called with `model="google/gemini-2.5-flash-preview"` and `extra_body={"thinking": {...}}`.
4. LLM failure → `stage_2_ddx` still returns results (fallback verified by test).

---

## Report back

1. **Diff summary** — lines added/changed in `agent/clinical_stages.py`.
2. **Test output** — full `pytest tests/test_clinical_stages.py -v` (23 tests).
3. **Any deviations** and why.
