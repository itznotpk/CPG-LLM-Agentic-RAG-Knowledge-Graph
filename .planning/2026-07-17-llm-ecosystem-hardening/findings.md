# Findings: LLM Ecosystem Hardening

## Requirements
- Implement all seven recommendations from the latest-commit review.
- Use Superpowers to plan, design dynamically from repository evidence, execute with TDD, and verify before completion.
- Preserve the clinical pipeline's fail-safe behavior and avoid PHI in telemetry.

## Research Findings
- Commit `8666940` raised selected Gemini output budgets but left prep brief at 200 and consultation summarization at 1200.
- `_probe_llm` treats every HTTP status below 500 as healthy, including 400/401/404.
- Independent environment fallback chains can combine URL, key, and model from different provider tiers.
- Existing `machine_signals` capture gate decisions, coverage gaps, and stage errors but not silent LLM fallbacks.
- No `.github/workflows` directory exists.
- `.env.example` omits several runtime LLM configuration groups.
- `CLAUDE.md` contains stale MiMo and token-budget documentation.

## Technical Decisions
| Decision | Rationale |
|----------|-----------|
| Pending user-approved design | Brainstorming skill requires alternatives and approval first. |

## Issues Encountered
| Issue | Resolution |
|-------|------------|
| Root `findings.md` belongs to an older EBM task | Keep this task's state in an isolated `.planning` directory. |

## Resources
- `backend/agent/clinical_stages.py`
- `backend/agent/api.py`
- `backend/agent/providers.py`
- `backend/agent/db_utils.py`
- `backend/tests/`
- `frontend/doctor-ui/package.json`
- `.env.example`
- `CLAUDE.md`

## Visual/Browser Findings
- None; this is an architecture/configuration task and does not currently need a visual companion.
