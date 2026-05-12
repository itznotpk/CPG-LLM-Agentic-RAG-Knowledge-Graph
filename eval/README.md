# Evaluation Harness — CPG LLM

End-to-end validation suite for the agentic clinical pipeline. Each script targets ONE pipeline stage so failures can be localised.

## Mapping: validation layers → your pipeline stages

| Validation Layer (VALIDATION_PLAN.md) | Pipeline Stage (README.md) | Script |
|---|---|---|
| **Layer A1** — Symptom → ICD-11 (DDx planner) | Stage 2 — DDx | `run_ddx_eval.py` |
| **Layer A2** — ICD → CPG routing | Stage 3 — Routing | `run_routing_eval.py` |
| **Layer B** — Retrieval recall / precision | Stage 4 — Scoped CPG retrieval | `run_retrieval_eval.py` |
| **Layer C** — Re-ranker / dedup quality | Stage 4 — top-20 dedup | `run_retrieval_eval.py` (`--rerank` flag) |
| **Layer D** — Generation faithfulness | Stage 5 — Synthesis | `run_faithfulness_eval.py` |
| **Layer E** — End-to-end clinical correctness | Full workflow | `run_e2e_eval.py` |
| **Non-accuracy** — Latency, cost, robustness | Whole API | `run_latency_eval.py` |
| **Baselines** — vanilla LLM vs naive RAG vs full | n/a (comparison) | `compare_baselines.py` |

## Gold sets (you build these manually — see templates)

| File | Purpose | Target size |
|---|---|---|
| `gold_sets/ddx_gold.jsonl` | symptom vignette → expected ICD-11 codes | 30–50 |
| `gold_sets/routing_gold.jsonl` | ICD-11 code → expected CPG document_id | 30–50 |
| `gold_sets/retrieval_gold.jsonl` | clinical question → relevant chunk_ids | 100–200 |
| `gold_sets/clinical_qa_gold.jsonl` | full patient case → expected answer + CPG citations | 30–50 |

**You can build all four sets yourself by reading the CPGs.** No clinician needed for retrieval/routing/DDx-mapping. A clinician only adds value when grading clinical_qa "safety" — and you can defer that to the stakeholder phase.

## Running

```bash
# From CPG LLM/ root, with venv activated and .env loaded
python -m eval.run_ddx_eval          # Stage 2
python -m eval.run_routing_eval      # Stage 3
python -m eval.run_retrieval_eval    # Stage 4 (recall@k / MRR / nDCG)
python -m eval.run_retrieval_eval --rerank   # Layer C lift
python -m eval.run_faithfulness_eval # Stage 5 groundedness
python -m eval.run_e2e_eval          # Full workflow
python -m eval.run_latency_eval      # p50 / p95 / cost
python -m eval.compare_baselines     # 3-way bar-chart data
```

Each script writes a timestamped JSON + CSV to `eval/results/`.

## Reporting outputs you'll have

After all scripts run on the full gold sets, you'll have:

- `results/retrieval_<ts>.csv` — Recall@5, Recall@10, MRR, nDCG@10 per query
- `results/retrieval_summary.json` — aggregate scores
- `results/faithfulness_<ts>.csv` — per-answer groundedness + citation accuracy
- `results/e2e_<ts>.csv` — clinical-correctness scorecard
- `results/baselines_<ts>.csv` — 3-way comparison table for your report chart
