# LLM Ecosystem Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden all clinical LLM configuration, structured calls, health checks, degradation telemetry, run manifests, CI, and operational documentation without changing clinical decision semantics.

**Architecture:** Add a focused `llm_runtime` module for atomic target resolution, per-operation policies, request-local call records, and structured non-streaming calls. Existing domain modules keep prompts, parsing, fallbacks, and streaming; API harvesting persists PHI-free signals and manifests through the existing `machine_signals` table.

**Tech Stack:** Python 3.12, FastAPI, OpenAI-compatible SDK, Pydantic, pytest/pytest-asyncio, React 18, Vitest, Supabase, GitHub Actions.

## Global Constraints

- Do not change clinical prompts, routing rules, retrieval, recommendation semantics, or safety decisions.
- Preserve existing fail-open/fail-safe behavior at every domain boundary.
- Never record API keys, endpoint URLs, prompts, completions, NRICs, names, free-text notes, or other patient fields in new telemetry.
- Reuse `machine_signals`; do not add a Supabase migration or modify `update_consultation`.
- Keep `/health` response fields compatible; `/live` and `/ready` are additive.
- Ordinary CI must not use live secrets or make live provider calls.
- Use TDD: run every new behavioral test red before production implementation.

---

### Task 1: Atomic LLM Target Resolution and Policy Registry

**Files:**
- Create: `backend/agent/llm_runtime.py`
- Create: `backend/tests/test_llm_runtime.py`

**Interfaces:**
- Produces: `LLMTarget`, `TargetTier`, `StructuredCallPolicy`, `POLICIES`, `resolve_target(operation, environ=None)`, `configuration_defects(environ=None)`, `completion_kwargs(operation)`.
- `LLMTarget` fields: `alias`, `base_url`, `api_key`, `model`, `provider`.
- `configuration_defects` returns PHI/secret-free strings naming incomplete tiers and missing variable names.

- [ ] **Step 1: Write failing resolver tests**

Cover complete specialized-tier precedence, fallback from an incomplete specialized tier to a complete lower tier, correct `*_MODEL`/`*_CHOICE` mapping, and no secret values in defect messages.

```python
def test_referral_target_keeps_prior_summary_tuple_atomic():
    env = {
        "PRIOR_VISIT_SUMMARISER_BASE_URL": "https://prior.test/v1",
        "PRIOR_VISIT_SUMMARISER_API_KEY": "prior-secret",
        "PRIOR_VISIT_SUMMARISER_MODEL": "prior-model",
        "STAGE5_LLM_BASE_URL": "https://stage5.test/v1",
        "STAGE5_LLM_API_KEY": "stage5-secret",
        "STAGE5_LLM_CHOICE": "stage5-model",
    }
    target = resolve_target("referral_gate", env)
    assert (target.base_url, target.api_key, target.model) == (
        "https://prior.test/v1", "prior-secret", "prior-model"
    )

def test_incomplete_override_falls_back_and_is_a_configuration_defect():
    env = {
        "PREP_BRIEF_LLM_BASE_URL": "https://partial.test/v1",
        "GEMINI_BASE_URL": "https://gemini.test/v1",
        "GEMINI_API_KEY": "gemini-secret",
        "GEMINI_MODEL": "gemini-2.5-flash",
    }
    assert resolve_target("prep_brief", env).alias == "gemini"
    defects = configuration_defects(env)
    assert any("PREP_BRIEF_LLM" in item for item in defects)
    assert all("gemini-secret" not in item for item in defects)
```

- [ ] **Step 2: Verify red**

Run: `cd backend; ..\venv\Scripts\python.exe -m pytest tests/test_llm_runtime.py "--override-ini=addopts=" -q`

Expected: collection fails because `agent.llm_runtime` does not exist.

- [ ] **Step 3: Implement the minimal resolver and policies**

Implement immutable dataclasses, explicit per-operation tier definitions, complete-tier selection, defect reporting, and these ceilings:

```python
POLICIES = {
    "ddx_rerank": StructuredCallPolicy("ddx_rerank", 8000, True, "v1"),
    "ddx_structured": StructuredCallPolicy("ddx_structured", 8000, True, "v1"),
    "stage4_queries": StructuredCallPolicy("stage4_queries", 8000, True, "v1"),
    "stage5_synthesis": StructuredCallPolicy("stage5_synthesis", 32000, True, "v1"),
    "stage5_refine": StructuredCallPolicy("stage5_refine", 32000, True, "v1"),
    "referral_gate": StructuredCallPolicy("referral_gate", 8000, True, "v1"),
    "prior_summary": StructuredCallPolicy("prior_summary", 8000, True, "v1"),
    "prep_brief": StructuredCallPolicy("prep_brief", 8000, True, "v1"),
    "safety_critic": StructuredCallPolicy("safety_critic", 8000, True, "v1"),
    "followup_protocol": StructuredCallPolicy("followup_protocol", 8000, True, "v1"),
    "followup_triage": StructuredCallPolicy("followup_triage", 8000, True, "v1"),
    "consultation_summary": StructuredCallPolicy("consultation_summary", 8000, False, "v1"),
    "readiness_probe": StructuredCallPolicy("readiness_probe", 1024, False, "v1"),
}
```

Provider capabilities must centralize Gemini seed omission and MiMo `enable_thinking=False` extra-body behavior.

- [ ] **Step 4: Verify green**

Run the Task 1 command; expected all tests pass.

- [ ] **Step 5: Commit**

`git commit -m "feat: add atomic LLM target policies"`

### Task 2: Structured Call Runtime and Request-Local Records

**Files:**
- Modify: `backend/agent/llm_runtime.py`
- Modify: `backend/tests/test_llm_runtime.py`

**Interfaces:**
- Produces: `LLMCallRecord`, `LLMRunContext`, `begin_llm_run(request_id, consultation_id=None)`, `end_llm_run(token)`, `current_llm_records()`, `call_structured(...)`, `record_stream_completion(...)`, `record_degradation(...)`.
- `call_structured` returns parsed `dict` plus the raw SDK response metadata; domain modules continue Pydantic validation.

- [ ] **Step 1: Write failing runtime tests**

Test successful JSON recording, transient retry count, empty-content classification, `finish_reason="length"`, malformed JSON, schema-error recording hook, context isolation with `asyncio.gather`, and serialized records containing none of the forbidden fields.

```python
@pytest.mark.asyncio
async def test_concurrent_run_contexts_do_not_mix_records():
    async def one(request_id):
        token = begin_llm_run(request_id)
        try:
            record_degradation("prep_brief", "empty_content")
            return [r.request_id for r in current_llm_records()]
        finally:
            end_llm_run(token)
    assert await asyncio.gather(one("a"), one("b")) == [["a"], ["b"]]
```

- [ ] **Step 2: Verify red**

Run Task 1's test command; expected missing runtime symbols or failed behavior assertions.

- [ ] **Step 3: Implement minimal call execution and recording**

Use `ContextVar[LLMRunContext | None]`, `time.perf_counter`, existing transient status rules, SDK `usage`, and choice `finish_reason`. Never serialize target URLs or keys. Accept a prompt-template string only to hash it immediately; do not store it.

- [ ] **Step 4: Verify green and regression**

Run `test_llm_runtime.py`, then `tests/test_stage_retry.py`; expected all pass.

- [ ] **Step 5: Commit**

`git commit -m "feat: record structured LLM outcomes"`

### Task 3: Migrate Clinical Structured Calls and Correct Gemini Budgets

**Files:**
- Modify: `backend/agent/clinical_stages.py`
- Modify: `backend/agent/safety_critic.py`
- Modify: `backend/agent/followup/protocol.py`
- Modify: `backend/agent/followup/triage.py`
- Modify tests: `backend/tests/test_clinical_stages.py`, `test_prep_brief.py`, `test_safety_critic.py`, and follow-up tests.

**Interfaces:**
- Consumes Task 1 target/policy resolution and Task 2 recording.
- Existing public function signatures and return/fallback shapes remain unchanged.

- [ ] **Step 1: Add failing call-contract tests**

Assert each migrated call uses its resolved target, exact policy ceiling, JSON mode, and provider capabilities. Add explicit regression assertions that prep brief and SOAP summary use `8000`, Stage 5/refine use `32000`, and referral/prior use `8000`.

- [ ] **Step 2: Verify red**

Run the affected test files with `--override-ini=addopts=`; expect assertions to show old budgets/fallback chains.

- [ ] **Step 3: Migrate non-streaming structured calls**

Use `call_structured` for Stage-4 queries, Stage-5/refine, referral gate, prior summary, prep brief, safety critic, and follow-up protocol/triage. Keep domain parsing, Pydantic validation, logging, and fallbacks in their current functions.

- [ ] **Step 4: Adapt Stage-2 streaming rerank**

Resolve its atomic target and shared policy kwargs, preserve thinking-delta SSE, and call `record_stream_completion` once. Do not alter rank parsing or fallback-to-vector behavior.

- [ ] **Step 5: Correct SOAP summarization**

Resolve its explicit Gemini-summary tier and use `max_tokens=8000`; keep empty-string fallback.

- [ ] **Step 6: Verify green**

Run all affected backend tests plus `test_streaming.py`; expected all pass.

- [ ] **Step 7: Commit**

`git commit -m "fix: apply provider-safe clinical LLM policies"`

### Task 4: Liveness, Strict Readiness, and Probe Cache

**Files:**
- Modify: `backend/agent/api.py`
- Modify: `backend/agent/models.py`
- Create: `backend/tests/test_health_endpoints.py`

**Interfaces:**
- Add `GET /live` returning `{status:"alive", version, timestamp}`.
- Add `GET /ready` returning the existing health body with HTTP 200 or 503.
- Preserve `GET /health` body/fields and HTTP compatibility.

- [ ] **Step 1: Write failing endpoint and probe tests**

Cover 2xx non-empty success; 2xx empty, 400, 401, 404, 429, and 5xx failures; 30-second target-fingerprint cache; incomplete-tier readiness failure; `/live` making no dependency calls; `/ready` returning 503 on any required failure.

- [ ] **Step 2: Verify red**

Run `tests/test_health_endpoints.py`; expected missing endpoints and current 4xx-as-healthy failure.

- [ ] **Step 3: Implement strict probe and endpoints**

Use Task 1 targets and the 1024-token probe policy. Parse `choices[0].message.content`; require 2xx and non-empty content. Cache by a SHA-256 of alias/model/base URL without retaining the URL in response/log payloads.

- [ ] **Step 4: Verify green**

Run health tests and existing API tests; expected all pass.

- [ ] **Step 5: Commit**

`git commit -m "feat: add strict readiness and liveness checks"`

### Task 5: Degradation Signals and Run Manifests

**Files:**
- Modify: `backend/agent/api.py`
- Modify: `backend/agent/db_utils.py`
- Modify: `backend/agent/clinical_workflow.py` only if routed CPG identifiers are not already available to harvesting.
- Create/modify: `backend/tests/test_llm_observability.py`, `backend/tests/test_machine_signals.py`.

**Interfaces:**
- Add machine signal types `llm_degradation` and `run_manifest` using existing columns.
- Manifest payload schema version is `1`.
- Use `APP_COMMIT_SHA` and `CPG_CORPUS_VERSION`, defaulting to `unknown` without failing a request.

- [ ] **Step 1: Write failing harvesting tests**

Assert one degradation row per degraded call, exactly one manifest per pipeline request, correct request/consultation IDs, routed CPG identifiers, prompt/policy hashes, and forbidden-field absence.

- [ ] **Step 2: Verify red**

Run the two observability test files; expect missing signal emissions.

- [ ] **Step 3: Scope and flush run contexts**

Open a context around plan, DDx-only, resynthesis, prep/prior, and follow-up job entrypoints. Flush in `finally`; emit manifests only for completed clinical pipeline requests. Preserve no-pool no-op behavior.

- [ ] **Step 4: Build PHI-free manifest**

```python
{
    "schema_version": 1,
    "app_commit": os.getenv("APP_COMMIT_SHA", "unknown"),
    "corpus_version": os.getenv("CPG_CORPUS_VERSION", "unknown"),
    "config_fingerprint": fingerprint,
    "cpg_documents": sorted(unique_document_ids),
    "operations": [record.to_payload() for record in records],
}
```

- [ ] **Step 5: Verify green and no regression**

Run observability, machine-signal, clinical-workflow, and streaming tests.

- [ ] **Step 6: Commit**

`git commit -m "feat: persist LLM degradation manifests"`

### Task 6: Clinical Performance Degradation Summary

**Files:**
- Modify: `frontend/doctor-ui/src/lib/supabase.js`
- Modify: `frontend/doctor-ui/src/components/sections/FeedbackInsightsSection.jsx`
- Create/modify corresponding Vitest files under `frontend/doctor-ui/src`.

**Interfaces:**
- `getFeedbackInsights()` adds `pipeline.llmDegradations` with `{operation, reason, count, severity}` rows.
- `run_manifest` rows are counted in raw machine totals only if needed for audit, but excluded from `otherTop` and clinician-facing recurring signals.

- [ ] **Step 1: Write failing aggregation tests**

Fixture machine rows with repeated degradations and manifests. Assert grouped degradation output and manifest filtering.

- [ ] **Step 2: Verify red**

Run the focused Vitest file; expected missing `llmDegradations`.

- [ ] **Step 3: Implement aggregation and compact UI**

Add static Tailwind classes and `SIGNAL_META.llm_degradation`. Render a compact grouped list with empty state; do not expose models, prompt hashes, or manifest contents to the clinician-facing panel.

- [ ] **Step 4: Verify green**

Run focused Vitest, full `npm run test`, and `npm run build`.

- [ ] **Step 5: Commit**

`git commit -m "feat: surface LLM degradation patterns"`

### Task 7: Configuration Inventory and GitHub Actions

**Files:**
- Create: `backend/scripts/check_env_example.py`
- Create: `backend/tests/test_env_inventory.py`
- Modify: `backend/pytest.ini`
- Create: `.github/workflows/ci.yml`
- Create: `.github/workflows/provider-smoke.yml`
- Create: `backend/tests/live/test_provider_smoke.py`

**Interfaces:**
- Inventory command exits 0 when synchronized and 1 with sorted missing names otherwise.
- Register `live_provider` marker.
- Push/PR CI uses Python 3.12 and Node 22; live smoke uses schedule plus `workflow_dispatch`.

- [ ] **Step 1: Write failing inventory tests**

Use temporary source/example fixtures to prove `os.getenv` and `os.environ.get` discovery, deterministic missing output, and allowlist behavior.

- [ ] **Step 2: Verify red**

Run `tests/test_env_inventory.py`; expected missing module/script.

- [ ] **Step 3: Implement the AST inventory**

Expose pure `discover_env_names(paths)` and `documented_env_names(example_text)` functions plus CLI `main()`. Allowlist only platform-provided variables documented in the design/plan.

- [ ] **Step 4: Add deterministic CI**

CI commands:

```powershell
python backend/scripts/check_env_example.py
cd backend; pytest -m "not slow and not integration and not live_provider"
cd frontend/doctor-ui; npm ci; npm run test; npm run build
```

- [ ] **Step 5: Add live smoke workflow/test**

Skip locally unless `GEMINI_API_KEY` exists. Resolve and deduplicate target fingerprints, request `{"ok": true}` in JSON mode, and assert parsed output. Schedule nightly at `18:00 UTC` and permit manual dispatch.

- [ ] **Step 6: Verify workflow syntax and tests**

Run inventory tests, inventory CLI, pytest collection for the live marker, and a YAML parse check using Python/PyYAML already present in requirements.

- [ ] **Step 7: Commit**

`git commit -m "ci: enforce configuration and provider health"`

### Task 8: Environment, Agent Guidance, Documentation, and Final Verification

**Files:**
- Modify: `.env.example`
- Modify: `CLAUDE.md`
- Create: `AGENTS.md`
- Modify: `docs/superpowers/specs/2026-07-17-llm-ecosystem-hardening-design.md` status to implemented after verification.

**Interfaces:**
- `.env.example` documents every runtime environment variable found by Task 7.
- `AGENTS.md` points to canonical `CLAUDE.md`, commands, and critical invariants.

- [ ] **Step 1: Run inventory to establish documentation red**

Run `python backend/scripts/check_env_example.py`; expected failure listing currently undocumented variables.

- [ ] **Step 2: Synchronize `.env.example`**

Add safe placeholders for all runtime target groups, `APP_COMMIT_SHA`, `CPG_CORPUS_VERSION`, health-cache configuration if exposed, follow-up, tracing, and worker variables. Never copy values from `.env`.

- [ ] **Step 3: Correct canonical docs and create project guidance**

Remove stale MiMo/current-model and old token-budget claims; document atomic fallback, policy ceilings, health endpoints, signals, CI, rollout variables, and manual Supabase non-requirement. Create concise project `AGENTS.md` without duplicating all 100k of `CLAUDE.md`.

- [ ] **Step 4: Verify documentation contract**

Run inventory CLI and placeholder/stale-claim searches. Expected zero missing environment variables and no obsolete current-MiMo claims.

- [ ] **Step 5: Run fresh full verification**

```powershell
cd backend; pytest -m "not slow and not integration and not live_provider"
cd frontend/doctor-ui; npm run test
cd frontend/doctor-ui; npm run build
git diff --check
```

Also run targeted health, runtime, observability, and frontend degradation tests separately so failures are attributable.

- [ ] **Step 6: Review every requirement against the diff**

Confirm all seven objective items, public endpoint compatibility, no migration, no secret/PHI telemetry fields, and no clinical prompt/semantic changes.

- [ ] **Step 7: Commit**

`git commit -m "docs: synchronize LLM operations guidance"`

- [ ] **Step 8: Finish the development branch**

Invoke `superpowers:finishing-a-development-branch`, present integration choices, and do not merge/push without the user's choice.
