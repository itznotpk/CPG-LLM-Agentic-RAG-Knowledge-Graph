# Repository Layout

The repo is split into two top-level code folders, with project docs and data at the root.

```
backend/    Python pipeline & tooling — agent/ ingestion/ ddx/ eval/ tools/
            tests/ sql/ scripts/, the entry scripts (cli.py, clinical_cli.py,
            convert_pdf.py, audit_markdown.py, split_cpg_markdown.py),
            and test config (pytest.ini, .coveragerc)
frontend/   doctor-ui/ — the React clinician dashboard (talks to the backend over HTTP)
rppg-poc/   standalone rPPG vitals POC, mounted by the backend at /rppg
docs/       validation, poster, eval and reading material
tasks/      planning notes and ingestion reports
documents/ markdown/ staging/ backups/   CPG corpus and pipeline artifacts
assets/     images used in the README
```

## Code-location references

All code paths cited in the README and other docs (e.g. `agent/routing.py`,
`ddx/search_ddx.py`, `scripts/…`) live under `backend/`. Python **import** paths are
unchanged (`from agent…`, `from ddx…`) because the backend runs from the `backend/`
directory.

## Run commands

| Task | Command |
|------|---------|
| Tests | `cd backend && pytest` |
| CLI | `python backend/cli.py` |
| Corpus scripts | run from the repo root, e.g. `python backend/convert_pdf.py`, so the root-level `markdown/` and `documents/` paths resolve |
