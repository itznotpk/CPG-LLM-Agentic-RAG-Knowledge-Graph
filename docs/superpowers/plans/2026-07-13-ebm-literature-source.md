# EBM Literature Source Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a live Europe PMC evidence-fetch step (Stage 4.6) plus a refinement synthesis pass (Stage 5.5) so care-plan recommendations are backed by — and, where no routed CPG covers a question, extended by — current published literature, surfaced in a standalone "Evidence & Literature" panel.

**Architecture:** Two-pass synthesis. Stage 5 drafts the plan from CPG+KG (unchanged). A new `ebm_lookup.py` module fetches graded, recent abstracts from Europe PMC keyed off DDx disease names + the draft plan's drug/intervention terms. Stage 5.5 re-runs synthesis with the EBM evidence block appended, under a prompt rule that keeps CPGs authoritative and tags any literature-only recommendation. EBM records ride on `TreatmentPlan`, stream via a new `ebm_evidence` SSE event, and render in a new care-plan tab. EBM is **never ingested/chunked** — it is a live, fail-open fetch; its absence is a no-op.

**Tech Stack:** Python 3 / FastAPI / asyncpg (backend), `httpx` (already a dep, async HTTP for Europe PMC), Pydantic v2 models, pytest; Vite + React 18 + Tailwind (frontend), Vitest.

**Design spec:** `docs/superpowers/specs/2026-07-13-ebm-literature-source-design.md`
**Research:** `findings.md`

## Global Constraints

- Working project is `CPG LLM/` ONLY. Never modify `MedFlow (Reference)/` or `Senior Final Report Reference/`.
- All backend commands run from `CPG LLM/backend/`; venv at `CPG LLM/venv`. Frontend from `CPG LLM/frontend/doctor-ui/`.
- PowerShell shell: chain with `;` not `&&`.
- Tests: `pytest.ini` bakes `--cov-fail-under=80` into addopts. During iteration on a single file use `pytest <path> "--override-ini=addopts="` to skip the coverage gate. `--no-cov` alone does NOT work.
- **EBM fetch is fail-OPEN.** Any failure (timeout, non-200, parse error, zero results) → EBM absent, Stage 5.5 skipped, the Stage-5 draft stands. Europe PMC being down MUST NOT block, delay unboundedly, or degrade a plan. This is the inverse of the CPG fail-loud contract.
- **EBM is never ingested/chunked** — no pgvector, no Neo4j, no ingestion script. Live fetch only.
- **Provenance rule (safety contract):** CPGs are the authoritative local standard. EBM may SUPPORT a CPG-covered rec, or INTRODUCE a rec ONLY when no routed CPG addresses the question (tagged "literature-based, no local CPG"). A paper contradicting/updating a CPG surfaces as a flagged note, never a silent override.
- No new provider SDKs. Europe PMC needs **no API key**.
- If `CPG LLM/` is not yet a git repo, run `git init` before the first commit; otherwise branch off before committing (do not commit to a default branch without asking).

## File Structure

- `backend/agent/ebm_lookup.py` (CREATE) — Europe PMC client, query builder, evidence-tier derivation, in-process cache, fail-open orchestration. One responsibility: turn (diseases, terms) → `list[EbmEvidence]`.
- `backend/agent/models.py` (MODIFY) — add `EbmEvidence` model; add `ebm_evidence: list[EbmEvidence]` field to `TreatmentPlan`.
- `backend/agent/prompts/stage5_5_refine.txt` (CREATE) — refinement-pass system prompt with the provenance rule.
- `backend/agent/clinical_stages.py` (MODIFY) — add `extract_plan_terms(plan)` helper and `stage_5_5_refine(...)` synthesis-refinement function.
- `backend/agent/clinical_workflow.py` (MODIFY) — wire Stage 4.6 + Stage 5.5 into all three entrypoints; emit `ebm_evidence`.
- `backend/agent/api.py` + `backend/clinical_cli.py` (MODIFY) — register the `ebm_evidence` SSE event type in both consumers.
- `backend/eval/run_faithfulness_eval.py` (MODIFY) — include EBM abstracts in the evidence set the judge sees.
- `backend/tests/test_ebm_lookup.py` (CREATE) — mocked Europe PMC parsing, tier derivation, fail-open.
- `backend/tests/test_ebm_wiring.py` (CREATE) — two-pass wiring: Stage 5.5 runs iff EBM present; skipped otherwise.
- `frontend/doctor-ui/src/lib/clinicalApi.js` (MODIFY) — handle `ebm_evidence` event in both stream fns.
- `frontend/doctor-ui/src/lib/clinicalMappers.js` (MODIFY) — `mapEbmEvidence(plan)` → UI shape.
- `frontend/doctor-ui/src/components/sections/EvidenceLiteraturePanel.jsx` (CREATE) — the tab body.
- `frontend/doctor-ui/src/components/sections/CarePlanSection.jsx` (MODIFY) — register the new tab.
- `frontend/doctor-ui/src/lib/__tests__/clinicalMappers.ebm.test.js` (CREATE) — mapper tests.

---

## Task 1: `EbmEvidence` model + `TreatmentPlan` field

**Files:**
- Modify: `backend/agent/models.py:372-401` (add field to `TreatmentPlan`), and add new model above it.
- Test: `backend/tests/test_ebm_lookup.py`

**Interfaces:**
- Produces: `EbmEvidence(title:str, abstract_snippet:str, journal:str, year:int|None, pub_type:str, evidence_tier:str, pmid:str|None, doi:str|None, url:str, cpg_gap:bool=False)`; `TreatmentPlan.ebm_evidence: list[EbmEvidence]` (default `[]`).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_ebm_lookup.py
from agent.models import EbmEvidence, TreatmentPlan, Recommendation


def test_ebm_evidence_defaults_and_treatmentplan_field():
    ev = EbmEvidence(
        title="Ticagrelor vs Clopidogrel in NSTEMI",
        abstract_snippet="In this systematic review, ticagrelor reduced...",
        journal="Cochrane Database Syst Rev",
        year=2024,
        pub_type="systematic-review",
        evidence_tier="high",
        pmid="12345678",
        doi="10.1002/abc",
        url="https://europepmc.org/article/MED/12345678",
    )
    assert ev.cpg_gap is False
    plan = TreatmentPlan(
        icd_primary="BA41.1",
        summary="s",
        recommendations=[Recommendation(text="Start ticagrelor")],
        confidence=0.8,
    )
    assert plan.ebm_evidence == []
    plan.ebm_evidence = [ev]
    assert plan.ebm_evidence[0].evidence_tier == "high"
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `backend/`): `pytest tests/test_ebm_lookup.py::test_ebm_evidence_defaults_and_treatmentplan_field -v "--override-ini=addopts="`
Expected: FAIL — `ImportError: cannot import name 'EbmEvidence'`.
(If `Recommendation`'s required fields differ, open `models.py` and match them — adjust the test's `Recommendation(...)` call to the real required args.)

- [ ] **Step 3: Add the model and field**

In `backend/agent/models.py`, immediately before `class TreatmentPlan(BaseModel):`:

```python
class EbmEvidence(BaseModel):
    """A single graded literature citation fetched live from Europe PMC (Stage 4.6).

    NOT persisted as a corpus — assembled per-consultation and discarded. `cpg_gap`
    marks evidence the synthesis used to fill a question no routed CPG covered.
    """

    title: str
    abstract_snippet: str = Field("", description="Truncated abstract for prompt/UI")
    journal: str = ""
    year: Optional[int] = None
    pub_type: str = Field("", description="Raw Europe PMC publication type, normalised")
    evidence_tier: Literal["high", "moderate", "low"] = "low"
    pmid: Optional[str] = None
    doi: Optional[str] = None
    url: str = ""
    cpg_gap: bool = Field(False, description="True if this backed a literature-only rec (no local CPG)")
```

Then add this field inside `class TreatmentPlan` (e.g. after `gate_audit`):

```python
    ebm_evidence: List[EbmEvidence] = Field(default_factory=list, description="Live Europe PMC citations informing this plan (Stage 4.6)")
```

Confirm `Optional`, `Literal`, `List`, `Field` are already imported at the top of `models.py` (they are used by existing models — no new imports needed).

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_ebm_lookup.py::test_ebm_evidence_defaults_and_treatmentplan_field -v "--override-ini=addopts="`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/agent/models.py backend/tests/test_ebm_lookup.py
git commit -m "feat(ebm): add EbmEvidence model and TreatmentPlan.ebm_evidence field"
```

---

## Task 2: Evidence-tier derivation (pure function)

**Files:**
- Create: `backend/agent/ebm_lookup.py`
- Test: `backend/tests/test_ebm_lookup.py`

**Interfaces:**
- Produces: `evidence_tier_for(pub_types: list[str]) -> Literal["high","moderate","low"]`.

- [ ] **Step 1: Write the failing test**

```python
# append to backend/tests/test_ebm_lookup.py
import pytest
from agent.ebm_lookup import evidence_tier_for


@pytest.mark.parametrize("pub_types, expected", [
    (["systematic-review"], "high"),
    (["Meta-Analysis"], "high"),
    (["Randomized Controlled Trial"], "moderate"),
    (["Guideline"], "moderate"),
    (["Journal Article"], "low"),
    ([], "low"),
    (["case-reports"], "low"),
])
def test_evidence_tier_for(pub_types, expected):
    assert evidence_tier_for(pub_types) == expected
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_ebm_lookup.py::test_evidence_tier_for -v "--override-ini=addopts="`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent.ebm_lookup'`.

- [ ] **Step 3: Create the module with the pure function**

```python
# backend/agent/ebm_lookup.py
"""Stage 4.6 — live Europe PMC evidence fetch. NOT ingested/chunked; fail-open."""
from __future__ import annotations

import logging
from typing import Literal

logger = logging.getLogger(__name__)

_HIGH = {"systematic-review", "systematic review", "meta-analysis", "meta analysis"}
_MODERATE = {"randomized controlled trial", "randomised controlled trial", "rct", "guideline", "practice guideline"}


def evidence_tier_for(pub_types: list[str]) -> Literal["high", "moderate", "low"]:
    """Map Europe PMC publication types onto a 3-tier evidence pyramid."""
    norm = {p.strip().lower() for p in pub_types if p}
    if norm & _HIGH:
        return "high"
    if norm & _MODERATE:
        return "moderate"
    return "low"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_ebm_lookup.py::test_evidence_tier_for -v "--override-ini=addopts="`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/agent/ebm_lookup.py backend/tests/test_ebm_lookup.py
git commit -m "feat(ebm): add evidence-tier derivation from Europe PMC pub types"
```

---

## Task 3: Europe PMC query builder (pure function)

**Files:**
- Modify: `backend/agent/ebm_lookup.py`
- Test: `backend/tests/test_ebm_lookup.py`

**Interfaces:**
- Produces: `build_europepmc_query(diseases: list[str], terms: list[str], *, recency_years: int = 7) -> str`.

- [ ] **Step 1: Write the failing test**

```python
# append to backend/tests/test_ebm_lookup.py
from agent.ebm_lookup import build_europepmc_query


def test_build_query_combines_disease_terms_filters_and_recency():
    q = build_europepmc_query(["NSTEMI"], ["ticagrelor"], recency_years=7)
    assert "NSTEMI" in q and "ticagrelor" in q
    # pub-type pyramid filter present
    assert "systematic review" in q.lower()
    assert "randomized controlled trial" in q.lower()
    # recency filter present as a PUB_YEAR range
    assert "PUB_YEAR" in q
    # has-abstract constraint so we never feed empty abstracts to synthesis
    assert "HAS_ABSTRACT:Y" in q


def test_build_query_empty_terms_still_valid():
    q = build_europepmc_query(["Atrial Fibrillation"], [])
    assert "Atrial Fibrillation" in q
    assert q.strip() != ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_ebm_lookup.py -k build_query -v "--override-ini=addopts="`
Expected: FAIL — `ImportError: cannot import name 'build_europepmc_query'`.

- [ ] **Step 3: Implement the query builder**

Add to `backend/agent/ebm_lookup.py`:

```python
import datetime as _dt

_PUB_TYPE_FILTER = (
    '(PUB_TYPE:"systematic review" OR PUB_TYPE:"meta-analysis" '
    'OR PUB_TYPE:"randomized controlled trial" OR PUB_TYPE:"guideline")'
)


def build_europepmc_query(diseases: list[str], terms: list[str], *, recency_years: int = 7) -> str:
    """Build a Europe PMC search query scoped to graded, recent, abstract-bearing evidence."""
    diseases = [d.strip() for d in diseases if d and d.strip()]
    terms = [t.strip() for t in terms if t and t.strip()]
    disease_clause = " OR ".join(f'"{d}"' for d in diseases) or '""'
    parts = [f"({disease_clause})"]
    if terms:
        term_clause = " OR ".join(f'"{t}"' for t in terms)
        parts.append(f"({term_clause})")
    parts.append(_PUB_TYPE_FILTER)
    parts.append("HAS_ABSTRACT:Y")
    this_year = _dt.date.today().year
    parts.append(f"(PUB_YEAR:[{this_year - recency_years} TO {this_year}])")
    return " AND ".join(parts)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_ebm_lookup.py -k build_query -v "--override-ini=addopts="`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/agent/ebm_lookup.py backend/tests/test_ebm_lookup.py
git commit -m "feat(ebm): add Europe PMC query builder with pyramid + recency filters"
```

---

## Task 4: Europe PMC response parser (pure function)

**Files:**
- Modify: `backend/agent/ebm_lookup.py`
- Test: `backend/tests/test_ebm_lookup.py`

**Interfaces:**
- Produces: `parse_europepmc_response(payload: dict, *, snippet_chars: int = 500) -> list[EbmEvidence]`.

- [ ] **Step 1: Write the failing test**

```python
# append to backend/tests/test_ebm_lookup.py
from agent.ebm_lookup import parse_europepmc_response

_SAMPLE = {
    "resultList": {"result": [
        {
            "id": "12345678", "pmid": "12345678", "doi": "10.1002/abc",
            "title": "Ticagrelor in NSTEMI: a systematic review",
            "journalTitle": "Cochrane Database Syst Rev", "pubYear": "2024",
            "abstractText": "A" * 900,
            "pubTypeList": {"pubType": ["Journal Article", "systematic-review"]},
        },
        {  # no abstract -> should be dropped
            "id": "999", "title": "No abstract paper", "pubYear": "2023",
            "pubTypeList": {"pubType": ["Journal Article"]},
        },
    ]}
}


def test_parse_builds_models_grades_and_truncates_and_drops_abstractless():
    out = parse_europepmc_response(_SAMPLE, snippet_chars=500)
    assert len(out) == 1
    ev = out[0]
    assert ev.pmid == "12345678"
    assert ev.evidence_tier == "high"
    assert len(ev.abstract_snippet) <= 500
    assert ev.url == "https://europepmc.org/article/MED/12345678"


def test_parse_empty_payload_returns_empty():
    assert parse_europepmc_response({}) == []
    assert parse_europepmc_response({"resultList": {"result": []}}) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_ebm_lookup.py -k parse -v "--override-ini=addopts="`
Expected: FAIL — `ImportError: cannot import name 'parse_europepmc_response'`.

- [ ] **Step 3: Implement the parser**

Add to `backend/agent/ebm_lookup.py` (add `from .models import EbmEvidence` near the top imports):

```python
def parse_europepmc_response(payload: dict, *, snippet_chars: int = 500) -> list["EbmEvidence"]:
    from .models import EbmEvidence
    results = (payload or {}).get("resultList", {}).get("result", []) or []
    out: list[EbmEvidence] = []
    for r in results:
        abstract = (r.get("abstractText") or "").strip()
        if not abstract:
            continue  # never feed empty abstracts to synthesis
        pub_types = (r.get("pubTypeList") or {}).get("pubType", []) or []
        pmid = r.get("pmid") or r.get("id")
        year_raw = r.get("pubYear")
        try:
            year = int(year_raw) if year_raw else None
        except (TypeError, ValueError):
            year = None
        out.append(EbmEvidence(
            title=(r.get("title") or "").strip(),
            abstract_snippet=abstract[:snippet_chars],
            journal=(r.get("journalTitle") or "").strip(),
            year=year,
            pub_type=", ".join(pub_types),
            evidence_tier=evidence_tier_for(pub_types),
            pmid=pmid,
            doi=r.get("doi"),
            url=f"https://europepmc.org/article/MED/{pmid}" if pmid else "",
        ))
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_ebm_lookup.py -k parse -v "--override-ini=addopts="`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/agent/ebm_lookup.py backend/tests/test_ebm_lookup.py
git commit -m "feat(ebm): parse Europe PMC results into graded EbmEvidence, drop abstractless"
```

---

## Task 5: Fail-open fetch orchestrator with cache

**Files:**
- Modify: `backend/agent/ebm_lookup.py`
- Test: `backend/tests/test_ebm_lookup.py`

**Interfaces:**
- Consumes: `build_europepmc_query`, `parse_europepmc_response`.
- Produces: `async def fetch_ebm_evidence(diseases, terms, *, limit=5, timeout_s=4.0, recency_years=7) -> list[EbmEvidence]` — never raises; returns `[]` on any failure. Module-level `_EBM_CACHE: dict[str, list[EbmEvidence]]`. Uses `_llm_call_with_retry`-style backoff via a local retry loop (do NOT import the LLM helper; keep this module dependency-light).

- [ ] **Step 1: Write the failing tests**

```python
# append to backend/tests/test_ebm_lookup.py
import agent.ebm_lookup as ebm


class _FakeResp:
    def __init__(self, status_code=200, json_data=None):
        self.status_code = status_code
        self._json = json_data or {}
    def json(self):
        return self._json
    def raise_for_status(self):
        if self.status_code >= 400:
            import httpx
            raise httpx.HTTPStatusError("err", request=None, response=None)


class _FakeClient:
    def __init__(self, resp=None, exc=None):
        self._resp, self._exc = resp, exc
        self.calls = 0
    async def __aenter__(self): return self
    async def __aexit__(self, *a): return False
    async def get(self, url, params=None):
        self.calls += 1
        if self._exc:
            raise self._exc
        return self._resp


async def test_fetch_returns_parsed_and_caches(monkeypatch):
    ebm._EBM_CACHE.clear()
    fake = _FakeClient(resp=_FakeResp(200, _SAMPLE))
    monkeypatch.setattr(ebm.httpx, "AsyncClient", lambda *a, **k: fake)
    out = await ebm.fetch_ebm_evidence(["NSTEMI"], ["ticagrelor"], limit=5)
    assert len(out) == 1 and out[0].pmid == "12345678"
    # second identical call is served from cache (no new client call)
    calls_before = fake.calls
    out2 = await ebm.fetch_ebm_evidence(["NSTEMI"], ["ticagrelor"], limit=5)
    assert out2[0].pmid == "12345678"
    assert fake.calls == calls_before  # cache hit


async def test_fetch_fail_open_on_exception(monkeypatch):
    ebm._EBM_CACHE.clear()
    import httpx
    fake = _FakeClient(exc=httpx.ConnectError("boom"))
    monkeypatch.setattr(ebm.httpx, "AsyncClient", lambda *a, **k: fake)
    out = await ebm.fetch_ebm_evidence(["NSTEMI"], ["ticagrelor"], limit=5, timeout_s=0.1)
    assert out == []  # never raises, returns empty


async def test_fetch_empty_diseases_short_circuits(monkeypatch):
    ebm._EBM_CACHE.clear()
    called = {"n": 0}
    def _boom(*a, **k):
        called["n"] += 1
        raise AssertionError("should not hit network")
    monkeypatch.setattr(ebm.httpx, "AsyncClient", _boom)
    assert await ebm.fetch_ebm_evidence([], ["ticagrelor"]) == []
    assert called["n"] == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_ebm_lookup.py -k fetch -v "--override-ini=addopts="`
Expected: FAIL — `AttributeError: module 'agent.ebm_lookup' has no attribute 'httpx'` / `fetch_ebm_evidence`.

- [ ] **Step 3: Implement the orchestrator**

Add to `backend/agent/ebm_lookup.py` (add `import asyncio`, `import httpx` to the imports):

```python
_EUROPEPMC_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
_EBM_CACHE: dict[str, list] = {}


def _cache_key(diseases: list[str], terms: list[str], limit: int, recency_years: int) -> str:
    d = ",".join(sorted(x.strip().lower() for x in diseases if x))
    t = ",".join(sorted(x.strip().lower() for x in terms if x))
    return f"{d}|{t}|{limit}|{recency_years}"


async def fetch_ebm_evidence(
    diseases: list[str],
    terms: list[str],
    *,
    limit: int = 5,
    timeout_s: float = 4.0,
    recency_years: int = 7,
    attempts: int = 2,
) -> list["EbmEvidence"]:
    """Live Europe PMC fetch. FAIL-OPEN: returns [] on any error. Never raises."""
    diseases = [d for d in (diseases or []) if d and d.strip()]
    if not diseases:
        return []
    key = _cache_key(diseases, terms or [], limit, recency_years)
    if key in _EBM_CACHE:
        return _EBM_CACHE[key]

    query = build_europepmc_query(diseases, terms or [], recency_years=recency_years)
    params = {
        "query": query, "format": "json", "pageSize": str(limit),
        "resultType": "core", "sort": "P_PDATE_D desc",
    }
    for attempt in range(attempts):
        try:
            async with httpx.AsyncClient(timeout=timeout_s) as client:
                resp = await client.get(_EUROPEPMC_URL, params=params)
                resp.raise_for_status()
                parsed = parse_europepmc_response(resp.json())[:limit]
                _EBM_CACHE[key] = parsed
                logger.info("ebm: %d citations for %s", len(parsed), diseases)
                return parsed
        except Exception as e:  # noqa: BLE001 — fail-open by contract
            logger.warning("ebm fetch attempt %d/%d failed: %s", attempt + 1, attempts, e)
            if attempt + 1 < attempts:
                await asyncio.sleep(0.5 * (attempt + 1))
    return []
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_ebm_lookup.py -v "--override-ini=addopts="`
Expected: PASS (all ebm_lookup tests). `asyncio_mode=auto` in `pytest.ini` makes the `async def test_*` run without decorators.

- [ ] **Step 5: Commit**

```bash
git add backend/agent/ebm_lookup.py backend/tests/test_ebm_lookup.py
git commit -m "feat(ebm): fail-open Europe PMC fetch with in-process cache"
```

---

## Task 6: `extract_plan_terms` — drug/intervention terms from a draft plan

**Files:**
- Modify: `backend/agent/clinical_stages.py` (add helper near other plan-post-processing helpers)
- Test: `backend/tests/test_ebm_wiring.py`

**Interfaces:**
- Consumes: `TreatmentPlan` (has `.recommendations: list[Recommendation]`).
- Produces: `extract_plan_terms(plan: TreatmentPlan, *, max_terms: int = 6) -> list[str]`.

- [ ] **Step 1: Read the Recommendation model first**

Run: `grep -n "class Recommendation" backend/agent/models.py` then read that block. Note the exact field that holds the drug/intervention text (e.g. `text`, `action`, `drug`). The step below assumes `.text`; **replace with the real field name** if different, and adjust the test accordingly.

- [ ] **Step 2: Write the failing test**

```python
# backend/tests/test_ebm_wiring.py
from agent.models import TreatmentPlan, Recommendation
from agent.clinical_stages import extract_plan_terms


def _plan(texts):
    return TreatmentPlan(
        icd_primary="BA41.1", summary="s",
        recommendations=[Recommendation(text=t) for t in texts], confidence=0.8,
    )


def test_extract_plan_terms_pulls_and_dedupes_and_caps():
    plan = _plan([
        "Start ticagrelor 90mg BD",
        "Continue ticagrelor",           # dup drug
        "Refer to cardiology for PCI",
    ])
    terms = extract_plan_terms(plan, max_terms=6)
    assert any("ticagrelor" in t.lower() for t in terms)
    # dedup: ticagrelor appears once
    assert sum("ticagrelor" in t.lower() for t in terms) == 1
    assert len(terms) <= 6


def test_extract_plan_terms_empty_plan():
    assert extract_plan_terms(_plan([]), max_terms=6) == []
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_ebm_wiring.py -k extract_plan_terms -v "--override-ini=addopts="`
Expected: FAIL — `ImportError: cannot import name 'extract_plan_terms'`.

- [ ] **Step 4: Implement the helper**

In `backend/agent/clinical_stages.py`, add (reuse the existing drug-class keyword approach used by the coverage-gap detector — search the file for `DRUG_CLASS_KEYWORDS` and reuse it if present; the fallback below is self-contained):

```python
import re as _re_terms

_TERM_STOPWORDS = {
    "start", "continue", "consider", "refer", "review", "for", "to", "the", "and",
    "with", "daily", "bd", "od", "tds", "mg", "if", "on", "of", "in", "patient",
}


def extract_plan_terms(plan, *, max_terms: int = 6) -> list[str]:
    """Pull candidate drug/intervention terms from a draft plan's recommendations.

    Heuristic, deterministic: tokenises each recommendation's text, drops dosing/stop
    words, keeps the first distinct meaningful token per recommendation. Used only to
    focus the Europe PMC query — precision here is not safety-critical.
    """
    seen: list[str] = []
    seen_lower: set[str] = set()
    for rec in getattr(plan, "recommendations", []) or []:
        text = (getattr(rec, "text", "") or "").strip()
        for raw in _re_terms.findall(r"[A-Za-z][A-Za-z\-]{3,}", text):
            tok = raw.strip("-")
            low = tok.lower()
            if low in _TERM_STOPWORDS or low in seen_lower:
                continue
            seen.append(tok)
            seen_lower.add(low)
            break  # one term per recommendation keeps the query focused
        if len(seen) >= max_terms:
            break
    return seen[:max_terms]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_ebm_wiring.py -k extract_plan_terms -v "--override-ini=addopts="`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/agent/clinical_stages.py backend/tests/test_ebm_wiring.py
git commit -m "feat(ebm): extract drug/intervention terms from draft plan for EBM query"
```

---

## Task 7: Stage 5.5 refinement synthesis + prompt

**Files:**
- Create: `backend/agent/prompts/stage5_5_refine.txt`
- Modify: `backend/agent/clinical_stages.py` (add `stage_5_5_refine`)
- Test: `backend/tests/test_ebm_wiring.py`

**Interfaces:**
- Consumes: draft `TreatmentPlan`, `list[EbmEvidence]`, `PatientCase`, `ddx`.
- Produces: `async def stage_5_5_refine(case, ddx, draft_plan, ebm_evidence, *, cpg_covered: bool = True) -> TreatmentPlan`. Returns a plan whose `.ebm_evidence` is populated. If `ebm_evidence` is empty, returns `draft_plan` unchanged (no LLM call).

- [ ] **Step 1: Write the prompt file**

`backend/agent/prompts/stage5_5_refine.txt`:

```
You are refining an existing evidence-based care plan by incorporating recent published
literature. You are given: (1) the DRAFT plan already grounded in Malaysian MoH Clinical
Practice Guidelines (CPGs) and knowledge-graph evidence, and (2) a set of EBM literature
citations fetched live from Europe PMC.

AUTHORITY RULES — follow exactly:
1. CPGs are the AUTHORITATIVE local standard. Do not remove, weaken, or silently contradict
   any recommendation the draft plan derived from a CPG.
2. Literature may SUPPORT a CPG-covered recommendation — add brief context or a citation,
   but do not change the recommendation itself.
3. Literature may INTRODUCE a new recommendation ONLY when no CPG in the draft addresses
   that specific question. Any such recommendation MUST begin with the tag
   "[Literature-based, no local CPG] " so the clinician sees it is not CPG-grounded.
4. If a citation CONTRADICTS or UPDATES a CPG recommendation, DO NOT override the CPG.
   Instead add a single entry to unresolved_questions beginning "Literature note: ..."
   summarising the discrepancy for the clinician to weigh.

Return a TreatmentPlan JSON object with the SAME schema as the draft. Preserve all draft
fields unless a rule above requires a tagged addition. Do not invent drugs, doses, or
thresholds not present in either the draft or the cited abstracts.
```

- [ ] **Step 2: Write the failing test (empty-EBM short-circuit + non-empty attaches evidence)**

```python
# append to backend/tests/test_ebm_wiring.py
import pytest
from agent.models import EbmEvidence, PatientCase, DDxResult
import agent.clinical_stages as cs


def _ev():
    return EbmEvidence(title="t", abstract_snippet="a", journal="j", year=2024,
                       pub_type="systematic-review", evidence_tier="high",
                       pmid="1", url="u")


async def test_refine_no_ebm_returns_draft_unchanged(monkeypatch):
    called = {"llm": 0}
    async def _no_llm(*a, **k):
        called["llm"] += 1
        raise AssertionError("must not call LLM when no EBM")
    monkeypatch.setattr(cs, "_refine_llm_call", _no_llm, raising=False)
    draft = _plan(["Start aspirin"])
    case = PatientCase(chief_complaint="cp")
    out = await cs.stage_5_5_refine(case, [], draft, [])
    assert out is draft
    assert called["llm"] == 0


async def test_refine_with_ebm_attaches_evidence(monkeypatch):
    draft = _plan(["Start aspirin"])
    refined = _plan(["Start aspirin", "[Literature-based, no local CPG] add colchicine"])
    async def _fake_llm(*a, **k):
        return refined
    monkeypatch.setattr(cs, "_refine_llm_call", _fake_llm, raising=False)
    case = PatientCase(chief_complaint="cp")
    out = await cs.stage_5_5_refine(case, [], draft, [_ev()])
    assert out.ebm_evidence and out.ebm_evidence[0].pmid == "1"
```

(Adjust `PatientCase(...)` required fields to match the real model — check `models.py:311`.)

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_ebm_wiring.py -k refine -v "--override-ini=addopts="`
Expected: FAIL — `AttributeError: module 'agent.clinical_stages' has no attribute 'stage_5_5_refine'`.

- [ ] **Step 4: Implement `stage_5_5_refine` (+ a thin `_refine_llm_call` seam for tests)**

In `backend/agent/clinical_stages.py`. Model the LLM call on `stage_5_synthesize` (same client construction, `response_format={"type":"json_object"}`, `TreatmentPlan.model_validate_json`). Load the prompt via the existing prompt-loading helper used for other prompts in this file (search for how `SYNTHESIS_SYSTEM` is loaded and mirror it, e.g. a `_load_prompt("stage5_5_refine.txt")`).

```python
def _format_ebm_for_prompt(ebm: list) -> str:
    lines = []
    for i, e in enumerate(ebm):
        lines.append(
            f"[EBM {i}] ({e.evidence_tier} tier, {e.journal} {e.year or ''}) "
            f"{e.title}\n  {e.abstract_snippet}"
        )
    return "\n".join(lines) if lines else "none"


async def _refine_llm_call(case, ddx, draft_plan, ebm_evidence):
    """Isolated LLM call — patched in tests."""
    base_url = os.getenv("STAGE5_LLM_BASE_URL") or os.getenv("LLM_BASE_URL")
    api_key = os.getenv("STAGE5_LLM_API_KEY") or os.getenv("LLM_API_KEY")
    model = os.getenv("STAGE5_LLM_CHOICE") or os.getenv("LLM_CHOICE", "gpt-4o")
    client = openai.AsyncOpenAI(base_url=base_url, api_key=api_key)
    system = _load_prompt("stage5_5_refine.txt")  # mirror existing prompt loader
    user = (
        f"DRAFT PLAN JSON:\n{draft_plan.model_dump_json()}\n\n"
        f"EBM LITERATURE:\n{_format_ebm_for_prompt(ebm_evidence)}\n\n"
        f"Return the refined TreatmentPlan JSON."
    )
    resp = await client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.1,
        response_format={"type": "json_object"},
    )
    return TreatmentPlan.model_validate_json(resp.choices[0].message.content)


async def stage_5_5_refine(case, ddx, draft_plan, ebm_evidence, *, cpg_covered: bool = True):
    """Second synthesis pass: fold EBM literature into the draft. Fail-open to draft."""
    if not ebm_evidence:
        return draft_plan  # nothing to add — no LLM cost
    try:
        refined = await _refine_llm_call(case, ddx, draft_plan, ebm_evidence)
    except Exception as e:  # noqa: BLE001 — refinement is additive; fall back to draft
        logger.warning("stage_5_5_refine failed, keeping draft: %s", e)
        draft_plan.ebm_evidence = list(ebm_evidence)
        return draft_plan
    refined.ebm_evidence = list(ebm_evidence)
    return refined
```

Confirm `_load_prompt` matches the real loader name in the file; if prompts are loaded a different way (e.g. `Path(__file__).parent/"prompts"/...`), mirror that exact pattern.

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_ebm_wiring.py -k refine -v "--override-ini=addopts="`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/agent/prompts/stage5_5_refine.txt backend/agent/clinical_stages.py backend/tests/test_ebm_wiring.py
git commit -m "feat(ebm): add Stage 5.5 refinement synthesis with provenance prompt"
```

---

## Task 8: Wire Stage 4.6 + 5.5 into `run_resynthesize_streaming` (the UI path)

**Files:**
- Modify: `backend/agent/clinical_workflow.py:818-840` (the resynth Stage 5 block)
- Test: `backend/tests/test_ebm_wiring.py`

**Interfaces:**
- Consumes: `fetch_ebm_evidence`, `extract_plan_terms`, `stage_5_5_refine`; the `emit` callback.
- Produces: emits `ebm_evidence` SSE event; `treatment_plan.ebm_evidence` populated.

- [ ] **Step 1: Write the failing wiring test**

```python
# append to backend/tests/test_ebm_wiring.py
async def test_resynth_emits_ebm_and_refines(monkeypatch):
    import agent.clinical_workflow as wf
    events = []
    async def emit(t, p=None): events.append((t, p))

    # stub the two-pass pieces
    draft = _plan(["Start aspirin"])
    monkeypatch.setattr(wf, "extract_plan_terms", lambda p, **k: ["aspirin"])
    async def _fetch(diseases, terms, **k): return [_ev()]
    monkeypatch.setattr(wf, "fetch_ebm_evidence", _fetch)
    async def _refine(case, ddx, dp, ebm, **k):
        dp.ebm_evidence = list(ebm); return dp
    monkeypatch.setattr(wf, "stage_5_5_refine", _refine)

    plan = await wf._apply_ebm_pass(  # small extracted helper (see Step 3)
        case=PatientCase(chief_complaint="cp"), ddx=[], draft_plan=draft,
        cpgs=[], emit=emit,
    )
    assert plan.ebm_evidence and plan.ebm_evidence[0].pmid == "1"
    assert any(t == "ebm_evidence" for t, _ in events)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_ebm_wiring.py -k resynth_emits -v "--override-ini=addopts="`
Expected: FAIL — `AttributeError: ... has no attribute '_apply_ebm_pass'`.

- [ ] **Step 3: Extract a shared `_apply_ebm_pass` helper and call it**

In `backend/agent/clinical_workflow.py`, add imports at top: `from .ebm_lookup import fetch_ebm_evidence` and `from .clinical_stages import extract_plan_terms, stage_5_5_refine` (place with the other `clinical_stages` imports).

Add this helper (near the other module-level workflow helpers):

```python
async def _apply_ebm_pass(*, case, ddx, draft_plan, cpgs, emit):
    """Stage 4.6 + 5.5: fetch EBM keyed off dx + draft terms, refine, emit. Fail-open."""
    try:
        diseases = [d.title for d in ddx[:3] if getattr(d, "title", None)]
        terms = extract_plan_terms(draft_plan)
        await emit("stage_update", {
            "stage": 4.6, "name": "Literature Evidence",
            "status": "running", "detail": "Searching Europe PMC for recent evidence…",
        })
        ebm = await fetch_ebm_evidence(diseases, terms)
        refined = await stage_5_5_refine(case, ddx, draft_plan, ebm, cpg_covered=bool(cpgs))
        await emit("stage_update", {
            "stage": 4.6, "name": "Literature Evidence", "status": "complete",
            "detail": f"{len(ebm)} citation(s) found" if ebm else "No new literature",
        })
        await emit("ebm_evidence", {"evidence": [e.model_dump() for e in refined.ebm_evidence]})
        return refined
    except Exception as e:  # noqa: BLE001 — additive, never block the plan
        logger.warning("EBM pass failed (non-fatal): %s", e)
        return draft_plan
```

Then in `run_resynthesize_streaming`, immediately AFTER the Stage-5 block sets `treatment_plan` (after line ~833, before `elapsed_ms = ...`), insert:

```python
        if not stage4_failed:
            treatment_plan = await _apply_ebm_pass(
                case=case, ddx=selected_ddx, draft_plan=treatment_plan, cpgs=cpgs, emit=emit,
            )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_ebm_wiring.py -k resynth_emits -v "--override-ini=addopts="`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/agent/clinical_workflow.py backend/tests/test_ebm_wiring.py
git commit -m "feat(ebm): wire Stage 4.6 + 5.5 EBM pass into resynthesize path"
```

---

## Task 9: Wire the EBM pass into the other two entrypoints

**Files:**
- Modify: `backend/agent/clinical_workflow.py` — `run_clinical_workflow` (~280) and `run_clinical_workflow_streaming` (~487), at each one's post-Stage-5 point.
- Test: reuse `test_ebm_wiring.py` (add one assertion per entrypoint if practical; otherwise a smoke assertion that `_apply_ebm_pass` is referenced in each).

- [ ] **Step 1: Locate each Stage-5 assignment**

Run: `grep -n "stage_5_synthesize(" backend/agent/clinical_workflow.py`
Expected: three call sites (the two streaming producers + the non-streaming `run_clinical_workflow`).

- [ ] **Step 2: Insert the EBM pass after each**

After each site that sets the plan variable from `stage_5_synthesize(...)` and is NOT in the `stage4_failed` branch, add the same guarded call (use the local plan/ddx/cpgs variable names in that function — they are `treatment_plan`/`selected_ddx` in streaming, may differ in `run_clinical_workflow`):

```python
        if not stage4_failed:  # or the equivalent success guard in this function
            <plan_var> = await _apply_ebm_pass(
                case=case, ddx=<ddx_var>, draft_plan=<plan_var>, cpgs=<cpgs_var>, emit=emit,
            )
```

For `run_clinical_workflow` (non-streaming) there may be no `emit`; if so pass a no-op: define `async def _noop(*a, **k): pass` and pass `emit=_noop`, OR gate the emits inside `_apply_ebm_pass` (they are already inside a try/except, so a no-op emit is simplest).

- [ ] **Step 3: Run the full ebm test module + a smoke of the workflow tests**

Run: `pytest tests/test_ebm_wiring.py tests/test_resynthesize.py -v "--override-ini=addopts="`
Expected: PASS (no regressions in the existing resynth tests).

- [ ] **Step 4: Commit**

```bash
git add backend/agent/clinical_workflow.py
git commit -m "feat(ebm): apply EBM pass across all three synthesis entrypoints"
```

---

## Task 10: Register `ebm_evidence` SSE event in both consumers

**Files:**
- Modify: `backend/agent/api.py` (SSE serializer / allowed event list) and `backend/clinical_cli.py` (event printer).
- Test: manual + existing SSE tests.

- [ ] **Step 1: Find how event types are enumerated**

Run: `grep -n "safety_review\|final_result\|event_type\|EVENT_TYPES\|out_of_scope" backend/agent/api.py backend/clinical_cli.py`
Read each hit. Most SSE stacks here pass events through generically, but confirm there is no allow-list that would silently drop `ebm_evidence`.

- [ ] **Step 2: Add `ebm_evidence` wherever event types are switched/whitelisted**

If `api.py` forwards all emitted events generically, no change is needed there (note it in the commit). In `clinical_cli.py`, add a print branch mirroring the `safety_review` one so CLI runs show the citations, e.g.:

```python
elif event_type == "ebm_evidence":
    ev = payload.get("evidence", [])
    print(f"  [EBM] {len(ev)} literature citation(s)")
    for e in ev[:5]:
        print(f"    - ({e.get('evidence_tier')}) {e.get('title')} — {e.get('journal')} {e.get('year') or ''}")
```

- [ ] **Step 3: Manual verify**

Start backend: `cd backend; python -m agent.api` (port 8058). In another terminal run an eval case that produces a plan: `python backend/scripts/run_eval_case_08.py`. Confirm the trace/summary or server log shows an `ebm_evidence` event with citations (or "No new literature" when Europe PMC returns nothing).

- [ ] **Step 4: Commit**

```bash
git add backend/agent/api.py backend/clinical_cli.py
git commit -m "feat(ebm): surface ebm_evidence SSE event in api + cli consumers"
```

---

## Task 11: Faithfulness eval — judge EBM-grounded claims against EBM+CPG evidence

**Files:**
- Modify: `backend/eval/run_faithfulness_eval.py`
- Test: run the eval on a small `--limit`.

- [ ] **Step 1: Find where the evidence set handed to the judge is assembled**

Run: `grep -n "evidence\|JUDGE_PROMPT\|claim\|_judge" backend/eval/run_faithfulness_eval.py`
Identify the variable holding the evidence text/records the judge grades claims against.

- [ ] **Step 2: Append plan EBM abstracts to that evidence set**

Where the plan is available, add its `ebm_evidence` abstracts to the judge's evidence context so a literature-based claim is not scored "unsupported":

```python
ebm_texts = [
    f"[Literature: {e.get('journal','')} {e.get('year','')}] {e.get('title','')}. {e.get('abstract_snippet','')}"
    for e in (plan.get("ebm_evidence") or [])
]
evidence_for_judge = cpg_evidence_texts + ebm_texts
```

(Match the real variable names found in Step 1.)

- [ ] **Step 3: Run a small faithfulness eval**

Run (live env required): `cd backend; python -m eval.run_faithfulness_eval --limit 3`
Expected: completes; literature-based recs are not systematically marked unsupported. Record the run under `backend/eval/results/` per the housekeeping rule (keep only latest per layer).

- [ ] **Step 4: Commit**

```bash
git add backend/eval/run_faithfulness_eval.py
git commit -m "eval(ebm): include EBM abstracts in faithfulness judge evidence set"
```

---

## Task 12: Frontend — handle `ebm_evidence` SSE event

**Files:**
- Modify: `frontend/doctor-ui/src/lib/clinicalApi.js` (both stream fns: ~275 and ~381 handler chains)
- Test: manual (covered by mapper test in Task 13).

**Interfaces:**
- Produces: an `onEbmEvidence(payload)` callback option on the resynth stream fn; payload `{evidence: [...]}`.

- [ ] **Step 1: Add the handler in both event chains**

In each `else if (eventType === 'safety_review' ...)` chain, add a sibling branch:

```javascript
else if (eventType === 'ebm_evidence' && onEbmEvidence) onEbmEvidence(payload);
```

Add `onEbmEvidence` to the destructured options object of the resynth stream function's signature (mirror how `onSafetyReview` is declared).

- [ ] **Step 2: Thread it into AppContext**

In `src/context/AppContext.jsx`, where `runDDxStream`/resynth is invoked with `onSafetyReview`, add `onEbmEvidence: (p) => dispatch({ type: 'SET_EBM_EVIDENCE', payload: p.evidence })`. Add the `SET_EBM_EVIDENCE` reducer case storing `state.ebmEvidence = action.payload`, and `ebmEvidence: []` in `initialState`. (Note: `final_result` already carries `plan.ebm_evidence`; this event is for live display during the stream — the mapper in Task 13 is the source of truth for the panel.)

- [ ] **Step 3: Build check**

Run: `cd "frontend/doctor-ui"; npx vite build`
Expected: builds with no errors.

- [ ] **Step 4: Commit**

```bash
git add "frontend/doctor-ui/src/lib/clinicalApi.js" "frontend/doctor-ui/src/context/AppContext.jsx"
git commit -m "feat(ebm): consume ebm_evidence SSE event in frontend stream + context"
```

---

## Task 13: Frontend — `mapEbmEvidence` mapper + test

**Files:**
- Modify: `frontend/doctor-ui/src/lib/clinicalMappers.js`
- Test: `frontend/doctor-ui/src/lib/__tests__/clinicalMappers.ebm.test.js`

**Interfaces:**
- Produces: `export function mapEbmEvidence(plan)` → `[{ title, journal, year, tier, url, cpgGap }]`, sorted high→low tier.

- [ ] **Step 1: Write the failing test**

```javascript
// frontend/doctor-ui/src/lib/__tests__/clinicalMappers.ebm.test.js
import { describe, it, expect } from 'vitest';
import { mapEbmEvidence } from '../clinicalMappers';

describe('mapEbmEvidence', () => {
  it('maps and sorts by tier high->low', () => {
    const plan = { ebm_evidence: [
      { title: 'B', journal: 'J', year: 2022, evidence_tier: 'low', url: 'u2', cpg_gap: false },
      { title: 'A', journal: 'Cochrane', year: 2024, evidence_tier: 'high', url: 'u1', cpg_gap: true },
    ]};
    const out = mapEbmEvidence(plan);
    expect(out).toHaveLength(2);
    expect(out[0].tier).toBe('high');
    expect(out[0].cpgGap).toBe(true);
  });
  it('handles missing field', () => {
    expect(mapEbmEvidence({})).toEqual([]);
    expect(mapEbmEvidence(null)).toEqual([]);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "frontend/doctor-ui"; npx vitest run src/lib/__tests__/clinicalMappers.ebm.test.js`
Expected: FAIL — `mapEbmEvidence is not a function`.

- [ ] **Step 3: Implement the mapper**

Add to `frontend/doctor-ui/src/lib/clinicalMappers.js`:

```javascript
const _TIER_ORDER = { high: 0, moderate: 1, low: 2 };

export function mapEbmEvidence(plan) {
  const list = plan?.ebm_evidence;
  if (!Array.isArray(list)) return [];
  return list
    .map((e) => ({
      title: e.title || '',
      journal: e.journal || '',
      year: e.year || null,
      tier: e.evidence_tier || 'low',
      url: e.url || '',
      cpgGap: !!e.cpg_gap,
    }))
    .sort((a, b) => (_TIER_ORDER[a.tier] ?? 3) - (_TIER_ORDER[b.tier] ?? 3));
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd "frontend/doctor-ui"; npx vitest run src/lib/__tests__/clinicalMappers.ebm.test.js`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add "frontend/doctor-ui/src/lib/clinicalMappers.js" "frontend/doctor-ui/src/lib/__tests__/clinicalMappers.ebm.test.js"
git commit -m "feat(ebm): add mapEbmEvidence mapper (tier-sorted) + tests"
```

---

## Task 14: Frontend — `EvidenceLiteraturePanel` + new care-plan tab

**Files:**
- Create: `frontend/doctor-ui/src/components/sections/EvidenceLiteraturePanel.jsx`
- Modify: `frontend/doctor-ui/src/components/sections/CarePlanSection.jsx` (tabs array ~1803; render blocks ~2031-2061)
- Test: build check.

**Interfaces:**
- Consumes: `mapEbmEvidence(plan)` output via props.

- [ ] **Step 1: Create the panel**

```jsx
// frontend/doctor-ui/src/components/sections/EvidenceLiteraturePanel.jsx
import React from 'react';
import { BookOpen, ExternalLink } from 'lucide-react';
import { GlassCard, Badge } from '../shared';

const TIER_LABEL = { high: 'High', moderate: 'Moderate', low: 'Low' };
const TIER_TONE = { high: 'success', moderate: 'warning', low: 'default' };

export default function EvidenceLiteraturePanel({ evidence = [] }) {
  if (!evidence.length) {
    return (
      <GlassCard>
        <div className="p-6 text-sm text-slate-400 flex items-center gap-2">
          <BookOpen className="w-4 h-4" /> No recent literature was retrieved for this case.
        </div>
      </GlassCard>
    );
  }
  return (
    <GlassCard>
      <div className="p-4 space-y-3">
        <div className="flex items-center gap-2 text-sm font-semibold">
          <BookOpen className="w-4 h-4" /> Evidence &amp; Literature (live from Europe PMC)
        </div>
        {evidence.map((e, i) => (
          <div key={i} className="rounded-lg border border-white/10 p-3">
            <div className="flex items-center gap-2 flex-wrap">
              <Badge tone={TIER_TONE[e.tier] || 'default'}>{TIER_LABEL[e.tier] || e.tier}</Badge>
              {e.cpgGap && <Badge tone="info">Literature-based · no local CPG</Badge>}
              <span className="text-xs text-slate-400">{e.journal} {e.year || ''}</span>
            </div>
            <div className="text-sm mt-1">{e.title}</div>
            {e.url && (
              <a href={e.url} target="_blank" rel="noreferrer"
                 className="text-xs text-sky-400 inline-flex items-center gap-1 mt-1">
                View on Europe PMC <ExternalLink className="w-3 h-3" />
              </a>
            )}
          </div>
        ))}
      </div>
    </GlassCard>
  );
}
```

(Confirm `GlassCard`/`Badge` are exported from `../shared` and that `Badge` accepts a `tone` prop; if the prop name differs, match the real API — grep `shared/index.js`.)

- [ ] **Step 2: Register the tab in `CarePlanSection.jsx`**

- Import at top: `import EvidenceLiteraturePanel from './EvidenceLiteraturePanel';` and `import { mapEbmEvidence } from '../../lib/clinicalMappers';`.
- Derive the data where other tab data is derived: `const ebmEvidence = mapEbmEvidence(clinicalPlanResponse);` (use whatever variable already holds the raw backend plan in this component — grep for `ebm_evidence` / the raw plan prop).
- Add to the `tabs` array (~1805): `{ key: 'evidence', label: 'Evidence', icon: BookOpen, count: ebmEvidence.length },` (import `BookOpen` from `lucide-react` if not already imported).
- Add a render block alongside the others (~2038): `{tab === 'evidence' && <EvidenceLiteraturePanel evidence={ebmEvidence} />}`.

- [ ] **Step 3: Build + test check**

Run: `cd "frontend/doctor-ui"; npx vite build; npx vitest run`
Expected: build succeeds; all tests pass.

- [ ] **Step 4: Commit**

```bash
git add "frontend/doctor-ui/src/components/sections/EvidenceLiteraturePanel.jsx" "frontend/doctor-ui/src/components/sections/CarePlanSection.jsx"
git commit -m "feat(ebm): add Evidence & Literature care-plan tab"
```

---

## Task 15: Full-suite regression + end-to-end smoke

**Files:** none (verification only).

- [ ] **Step 1: Backend full suite (coverage gate on)**

Run: `cd backend; pytest`
Expected: PASS incl. `--cov-fail-under=80`. If the new `ebm_lookup.py` drags coverage, ensure Task 5 tests exercise the fetch happy-path + fail-open (they do).

- [ ] **Step 2: Frontend suite + build**

Run: `cd "frontend/doctor-ui"; npx vitest run; npx vite build`
Expected: all green, clean build.

- [ ] **Step 3: End-to-end smoke against live backend**

Start backend (`cd backend; python -m agent.api`), then `python backend/scripts/run_eval_case_09.py` (NSTEMI+AF — rich drug terms). Inspect `tasks/eval_runs/case09_*_summary.md`:
- `ebm_evidence` present with graded citations, OR "No new literature" if Europe PMC returned nothing (both are valid — fail-open).
- Plan still valid, Stage 6 ran on the refined plan.
- Any literature-only rec carries the `[Literature-based, no local CPG]` tag.

- [ ] **Step 4: Final commit / branch wrap-up**

```bash
git add -A
git commit -m "test(ebm): full-suite regression + e2e smoke for EBM literature source"
```

Then follow `superpowers:finishing-a-development-branch` to decide merge/PR.

---

## Self-Review (author checklist — completed)

- **Spec coverage:** §3 pipeline → Tasks 7-9; §4 fetch module → Tasks 2-5; §5 provenance → Task 1 (`cpg_gap`) + Task 7 (prompt); §6 UI → Tasks 12-14; §7 eval → Task 11; "not ingested" constraint → enforced by design (no ingestion task exists, called out in Global Constraints). ✅
- **Placeholder scan:** every code step carries real code; where a real field name can't be known without reading the file (Recommendation.text, PatientCase required fields, prompt loader, Badge tone prop, shared exports), the step explicitly instructs to grep/confirm and adjust — these are verification instructions, not placeholders. ✅
- **Type consistency:** `EbmEvidence`/`ebm_evidence`/`fetch_ebm_evidence`/`extract_plan_terms`/`stage_5_5_refine`/`_apply_ebm_pass`/`mapEbmEvidence` used consistently across tasks. ✅
- **Scope:** single feature, one plan; no unrelated refactors. ✅
