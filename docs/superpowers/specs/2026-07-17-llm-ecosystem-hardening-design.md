# LLM Ecosystem Hardening Design

**Date:** 2026-07-17  
**Status:** Approved in conversation; awaiting written-spec review  
**Source:** Review of commit `8666940`

## Objective

Implement all seven reliability improvements identified in the latest-commit review without changing clinical decision semantics:

1. atomic provider configuration;
2. a shared policy for clinical structured-output LLM calls;
3. correct liveness/readiness behavior;
4. durable PHI-free LLM degradation telemetry;
5. request-linked run manifests;
6. deterministic push/PR CI plus manual/nightly live-provider smoke tests;
7. synchronized configuration and operational documentation.

The implementation must preserve each existing domain fallback. Telemetry, readiness, and configuration validation must never invent or alter clinical content.

## Chosen Architecture

### Focused runtime module

Add a focused backend runtime module rather than a minimal patch set or a gateway for every LLM feature. It owns:

- `LLMTarget`: a complete provider tuple containing provider alias, base URL, API key, model, and optional provider kind;
- ordered target-tier resolution for each operation;
- `StructuredCallPolicy`: operation name, maximum output tokens, JSON-mode requirement, transient retry profile, and policy version;
- non-streaming structured-call execution and response inspection;
- request-local call records and degradation events.

Existing domain functions continue to own prompts, Pydantic validation, clinical fallbacks, and SSE behavior. The Stage-2 streaming reranker consumes the shared target and policy but keeps its custom streaming loop.

### Atomic provider resolution

A target tier is usable only when all required fields for that tier are present. URL, key, and model are never independently coalesced across tiers. An incomplete configured tier is skipped at runtime in favor of the next complete tier, recorded as a configuration defect, and causes strict readiness to return HTTP 503 until fixed.

Operation precedence is explicit:

| Operations | Ordered complete tiers |
|---|---|
| Stage-2 rerank and Stage-2 structured helpers | `STAGE2_RERANK_LLM_*` where applicable, then `STAGE2_LLM_*`, then `LLM_*` |
| Stage-4 query generation | `STAGE4_LLM_*`, then `LLM_*` |
| Stage-5 synthesis and EBM refinement | `STAGE5_LLM_*`, then `LLM_*` |
| Referral gate | `REFERRAL_GATE_*`, `PRIOR_VISIT_SUMMARISER_*`, `STAGE5_LLM_*`, then `LLM_*` |
| Prior-visit summary | `PRIOR_VISIT_SUMMARISER_*`, `STAGE5_LLM_*`, then `LLM_*` |
| Prep brief | `PREP_BRIEF_LLM_*`, `GEMINI_*`, then `LLM_*` |
| Safety critic | `SAFETY_CRITIC_LLM_*`, `STAGE5_LLM_*`, then `LLM_*` |
| Follow-up protocol and triage | `FOLLOWUP_LLM_*`, `GEMINI_*`, then `LLM_*` |
| Consultation SOAP summary | `GEMINI_BASE_URL` + `GEMINI_API_KEY` + `CONSULTATION_SUMMARY_MODEL`, then `LLM_*` |

The resolver maps the repository's existing `*_MODEL` versus `*_CHOICE` names explicitly; environment variables are not renamed in this change.

### Structured-call policies

Clinical JSON paths adopt the shared policy. Chatbox, ingestion, free-text symptom extraction, and other non-JSON paths remain outside it. The SOAP summarizer stays a free-text call but receives the Gemini-safe budget correction and target resolution.

Initial policy ceilings are:

| Operation class | `max_tokens` |
|---|---:|
| Stage-5 synthesis and Stage-5.5 refinement | 32000 |
| Stage-2 structured helpers/rerank, Stage-4 query generation, referral gate, prior summary, prep brief, safety critic, follow-up protocol/triage | 8000 |
| Consultation SOAP summary | 8000 |
| Readiness probe | 1024 |

These are ceilings, not reserved allocations. JSON policies require `response_format={"type":"json_object"}` where the provider supports it. Existing MiMo thinking-disable behavior and Gemini seed omission remain provider capabilities, not scattered call-site conditionals.

Transient retries cover the existing retryable HTTP statuses and connection/timeout failures. Empty content, `finish_reason == "length"`, malformed JSON, and schema validation failure are classified distinctly. Domain fallbacks remain unchanged after retries are exhausted.

## Health Interfaces

Add two endpoints while preserving `/health`:

- `GET /live`: no dependency calls; HTTP 200 with process status, version, and timestamp.
- `GET /ready`: strict database, graph, Stage-5 target, and safety target checks; HTTP 200 only when all required dependencies are usable, otherwise HTTP 503 with the health body.
- `GET /health`: retains its current response schema and always-return-body compatibility, but uses the corrected probe so 400/401/403/404 are not reported as successful.

An LLM probe succeeds only on a 2xx response containing a non-empty assistant completion. Results are cached for 30 seconds per non-secret target fingerprint to prevent quota churn. Incomplete configured tiers make readiness fail even when runtime fallback is available.

## Telemetry and Run Manifest

### Request-local collection

Each clinical request or follow-up job opens an `LLMRunContext` stored in a `ContextVar`. Concurrent requests receive separate mutable records. A call record contains only:

- operation and policy version;
- provider alias and model;
- prompt-template SHA-256, never prompt content;
- configured token ceiling;
- attempts, latency, finish reason, and provider-reported token counts;
- outcome classification.

It must not contain API keys, endpoint URLs, prompts, completions, NRICs, names, free-text notes, or other patient fields.

### Machine signals

Reuse the existing append-only `machine_signals` table; no Supabase migration is required.

- `llm_degradation`: emitted when a call falls back because retries were exhausted, content was empty/truncated, or JSON/schema validation failed. Payload includes the PHI-free call metadata and reason.
- `run_manifest`: exactly one per completed clinical pipeline request. Payload schema version `1` contains `APP_COMMIT_SHA`, `CPG_CORPUS_VERSION`, routed CPG document identifiers, configuration fingerprint, and collected operation records.

Telemetry flushes in `finally` paths and remains fail-open. A telemetry write can never change an API response or clinical plan.

### Clinical Performance UI

Aggregate `llm_degradation` by operation and reason in Feedback Insights. Add the signal label and a compact degradation summary. Keep `run_manifest` rows out of the generic recurring-signal list; they remain queryable by `request_id` for engineering drill-down.

## CI and Live Provider Validation

### Push and pull-request workflow

Use GitHub Actions with Python 3.12 and Node 22:

- run the environment-inventory check;
- run backend tests excluding `slow`, `integration`, and `live_provider`, retaining the repository's coverage gate;
- run frontend Vitest;
- run the Vite production build.

No live secrets or external LLM calls are permitted in ordinary CI.

### Manual/nightly provider workflow

Add a `workflow_dispatch` and nightly scheduled workflow using the Gemini secret. It resolves configured targets, deduplicates identical non-secret provider/model fingerprints, and requests a minimal structured completion from each unique target. Provider outages fail this workflow but do not block ordinary commits. Register a `live_provider` pytest marker and exclude it by default.

## Configuration and Documentation Contract

Add an AST-based script that scans `os.getenv`/`os.environ.get` usage under `backend/agent` and compares the discovered runtime names with `.env.example`. A small explicit allowlist is permitted only for platform-provided variables. The check prints sorted missing names and exits non-zero on drift.

Update `.env.example` and `CLAUDE.md` for:

- all target groups and their atomic precedence;
- Gemini-safe structured-call budgets;
- liveness/readiness semantics;
- `llm_degradation` and `run_manifest` signals;
- `APP_COMMIT_SHA` and `CPG_CORPUS_VERSION`;
- ordinary and live-provider CI commands.

Create project-level `AGENTS.md` so the workspace-level instruction no longer points to a missing file. It will direct agents to the canonical `CLAUDE.md`, repeat essential commands and non-negotiable clinical invariants, and state that reference sibling projects are out of scope.

## Testing and Acceptance

Implementation follows red-green-refactor. Tests must demonstrate:

- exact tier precedence, complete-tuple selection, incomplete-tier fallback, and readiness failure;
- every policy's token ceiling and JSON-mode behavior;
- retry exhaustion, empty content, length truncation, JSON failure, and schema failure classifications;
- request-context isolation under concurrent calls;
- absence of forbidden PHI/secret fields from telemetry payloads;
- exactly one manifest per pipeline request and correct `request_id` correlation;
- strict health status handling for 2xx, 400, 401, 404, 429, and 5xx responses;
- prep brief and SOAP summary use Gemini-safe budgets;
- frontend degradation aggregation and manifest filtering;
- environment inventory fails on a missing fixture variable and passes for the synchronized example;
- backend test suite, frontend test suite, and production build succeed.

## Rollout and Compatibility

- No database migration is required.
- Existing environment variable names and `/health` response fields remain compatible.
- `/live` and `/ready` are additive.
- Deployment should set `APP_COMMIT_SHA` to the release commit and `CPG_CORPUS_VERSION` to the active corpus snapshot.
- Configure the platform readiness probe to `/ready` only after the new release is deployed and verified; keep `/live` for liveness.
- Monitor the first 24 hours for `llm_degradation` counts by operation and nightly provider-smoke failures.

## Out of Scope

- Replacing OpenAI-compatible provider SDKs.
- Refactoring chatbox, ingestion, or all free-text LLM paths into the structured-call helper.
- Changing clinical prompts, routing rules, retrieval, synthesis semantics, or safety decisions.
- Creating an online-learning loop from feedback signals.
