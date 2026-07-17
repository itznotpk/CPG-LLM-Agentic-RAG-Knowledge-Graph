# AGENTS.md

Read `CLAUDE.md` before changing this project. It is the canonical project guide.

Key rules:

- Work only inside this `CPG LLM/` project; the workspace's two reference siblings are read-only.
- Preserve clinical prompts, routing semantics, safety behavior, and fail-open/fail-safe boundaries unless the user explicitly requests a clinical change.
- Use `backend/agent/llm_runtime.py` for clinical LLM target resolution and policies. Never rebuild environment fallback chains at call sites.
- Add tests before behavior changes and run focused tests first, then the relevant backend/frontend suites.
- Never put secrets, endpoints, prompts, completions, or patient data in logs, manifests, signals, or test fixtures.
- Run `python backend/scripts/check_env_example.py` whenever runtime environment variables change.

Common checks:

```powershell
cd backend; pytest -m "not slow and not integration and not live_provider" --ignore=tests/tools/test_convert_pdf.py
cd frontend/doctor-ui; npm run test
cd frontend/doctor-ui; npm run build
python backend/scripts/check_env_example.py
```
