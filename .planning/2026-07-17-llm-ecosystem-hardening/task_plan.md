# Task Plan: LLM Ecosystem Hardening

## Goal
Design, specify, implement, and verify all seven ecosystem improvements identified in the review of commit `8666940`.

## Current Phase
Phase 1

## Phases

### Phase 1: Superpowers discovery and design approval
- [x] Capture the seven requested outcomes
- [ ] Map existing configuration, LLM calls, telemetry, health checks, tests, docs, and CI
- [ ] Ask the user one clarifying question at a time
- [ ] Present 2-3 approaches and a recommended design
- [ ] Obtain user approval
- **Status:** in_progress

### Phase 2: Committed design specification
- [ ] Write `docs/superpowers/specs/2026-07-17-llm-ecosystem-hardening-design.md`
- [ ] Self-review for placeholders, contradictions, ambiguity, and scope
- [ ] Commit the approved design document
- [ ] Obtain user review of the written spec
- **Status:** pending

### Phase 3: Detailed implementation plan
- [ ] Use the writing-plans skill
- [ ] Write `docs/superpowers/plans/2026-07-17-llm-ecosystem-hardening.md`
- [ ] Self-review coverage and interfaces
- **Status:** pending

### Phase 4: TDD implementation
- [ ] Execute provider resolver and structured-call policy
- [ ] Execute liveness/readiness correction
- [ ] Execute degradation telemetry and run manifests
- [ ] Execute CI and configuration-inventory checks
- [ ] Execute documentation and environment-example synchronization
- **Status:** pending

### Phase 5: Verification and delivery
- [ ] Run targeted red-green tests during each task
- [ ] Run full backend verification
- [ ] Run frontend tests and production build
- [ ] Review diff against all seven requirements
- [ ] Report results and any manual deployment steps
- **Status:** pending

## Key Questions
1. Should this remain provider-agnostic with current Gemini behavior encoded as capabilities, or optimize only for Gemini?
2. Should live-provider smoke tests run nightly/manual only to avoid secrets and quota in ordinary CI?
3. Should run manifests be persisted in `machine_signals` metadata or a dedicated table?

## Decisions Made
| Decision | Rationale |
|----------|-----------|
| Use an isolated `.planning` directory | Preserve the unrelated legacy root `findings.md`. |
| No production edits before design approval | Required by the Superpowers brainstorming hard gate. |

## Errors Encountered
| Error | Attempt | Resolution |
|-------|---------|------------|
| Project-level `CPG LLM/AGENTS.md` referenced by root guidance is missing | 1 | Use the supplied root guidance and existing `CPG LLM/CLAUDE.md`; include governance repair in design. |

## Notes
- Treat planning files as workflow state, not production deliverables.
- Re-read this plan before architecture and implementation decisions.
