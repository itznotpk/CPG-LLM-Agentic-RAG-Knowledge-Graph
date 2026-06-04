# Validation Framework — MHNexus CPG LLM

> Quick-start guide. Full strategy → [VALIDATION_PLAN.md](VALIDATION_PLAN.md). Eval harness → [eval/README.md](eval/README.md).

---

## CPG Coverage (24 CPGs across 3 categories + ED)

| # | Category | CPG | Document Title (used in gold sets) |
|---|---|---|---|
| 1 | Cardiovascular | STEMI (4th Edition) | STEMI |
| 2 | Cardiovascular | NSTE-ACS (3rd Edition) | NSTE-ACS |
| 3 | Cardiovascular | NSTEMI (2011) | NSTEMI |
| 4 | Cardiovascular | Heart Failure (5th Edition) | Heart Failure |
| 5 | Cardiovascular | Hypertension (5th Edition) | Hypertension |
| 6 | Cardiovascular | Dyslipidaemia (6th Edition) | Dyslipidaemia |
| 7 | Cardiovascular | Atrial Fibrillation (2012) | Atrial Fibrillation |
| 8 | Cardiovascular | Stable Coronary Artery Disease (2nd Edition) | Stable Coronary Artery Disease |
| 9 | Cardiovascular | Percutaneous Coronary Intervention | Percutaneous Coronary Intervention |
| 10 | Cardiovascular | Pulmonary Arterial Hypertension (2011) | Pulmonary Arterial Hypertension |
| 11 | Cardiovascular | Heart Disease in Pregnancy (2nd Edition) | Heart Disease in Pregnancy |
| 12 | Cardiovascular | Primary & Secondary Prevention of CVD (2017) | Primary Secondary Prevention of CVD |
| 13 | Cardiovascular | CVD Prevention in Women (2016) | CVD Prevention in Women |
| 14 | Cardiovascular | Prevention, Diagnosis & Management of IE | Infective Endocarditis |
| 15 | Cardiovascular | Ischaemic Stroke (3rd Edition) | Ischaemic Stroke |
| 16 | Cancer | Breast Cancer (3rd Edition) | Breast Cancer |
| 17 | Cancer | Colorectal Carcinoma (2017) | Colorectal Carcinoma |
| 18 | Cancer | Cancer Pain (2nd Edition) | Cancer Pain |
| 19 | Cancer | Nasopharyngeal Carcinoma | Nasopharyngeal Carcinoma |
| 20 | Anaesthesia | Anaesthesia Medication Safety | Anaesthesia Medication Safety |
| 21 | Anaesthesia | Guidelines on Safe Use of Medication in Anaesthesia (Oct 2024) | Anaesthesia Safe Medication Use |
| 22 | Anaesthesia | Patient Safety & Minimal Monitoring | Patient Safety Minimal Monitoring |
| 23 | Anaesthesia | Pre-Anaesthetic Assessment | Pre-Anaesthetic Assessment |
| 24 | Others | Erectile Dysfunction | Erectile Dysfunction |

---

## Gold-Set Status

| File | Entries | Status | Action needed |
|---|---|---|---|
| `eval/gold_sets/ddx_gold.jsonl` | 35 | Draft complete | None — vignettes + ICD-11 codes are final |
| `eval/gold_sets/routing_gold.jsonl` | 42 | Draft complete | None — ICD-11 → document mapping is final |
| `eval/gold_sets/retrieval_gold.jsonl` | 120 | **Chunk IDs are placeholders** | Replace every `REPLACE_WITH_chunk_id_XXX` after ingestion |
| `eval/gold_sets/clinical_qa_gold.jsonl` | 30 | Draft complete | Optionally get clinician sign-off on safety criteria |

---

## Filling In Chunk IDs (retrieval gold set)

After running the CPG ingestion pipeline, replace every placeholder in `retrieval_gold.jsonl`.

Quick SQL pattern:
```sql
-- Find chunk IDs matching keyword + document
SELECT id, LEFT(content, 120)
FROM chunks
WHERE document_id = (SELECT id FROM documents WHERE title ILIKE '%STEMI%')
  AND content ILIKE '%reperfusion%'
ORDER BY id;
```

Replace `"REPLACE_WITH_chunk_id_STEMI_s7_001"` → real UUID from the chunks table.
Aim for **2–3 chunk IDs per retrieval entry** where the same fact spans multiple chunks.

---

## Running the Full Suite

```bash
# From project root, with venv activated and .env loaded
python -m eval.run_ddx_eval          # Layer A1 — DDx vignette → ICD-11
python -m eval.run_routing_eval      # Layer A2 — ICD-11 → CPG document
python -m eval.run_retrieval_eval    # Layer B  — retrieval Recall/MRR/nDCG
python -m eval.run_retrieval_eval --rerank   # Layer C  — re-ranker lift
python -m eval.run_faithfulness_eval # Layer D  — generation groundedness
python -m eval.run_e2e_eval          # Layer E  — end-to-end clinical correctness
python -m eval.run_latency_eval      # Non-accuracy — p50/p95/cost
python -m eval.compare_baselines     # Baselines — naive RAG vs full system
```

Results land in `eval/results/` as timestamped CSV + JSON.

---

## Target Scores

| Metric | Target | Layer |
|---|---|---|
| Recall@10 | ≥ 0.85 | B |
| MRR | ≥ 0.70 | B |
| nDCG@10 | ≥ 0.75 | B |
| Hit Rate@5 | ≥ 0.90 | B |
| Faithfulness / Groundedness | ≥ 0.90 | D |
| Hallucination rate | ≤ 5% | D |
| E2E clinical correctness | ≥ 80% | E |
| p95 latency | < 8 s | Non-acc |

---

## Minimum Viable Validation (if time-constrained)

Per [VALIDATION_PLAN.md § 6](VALIDATION_PLAN.md):
- 50 retrieval entries → Recall@10 + MRR
- 30 clinical QA entries → faithfulness + correctness (manual)
- One baseline comparison (naive RAG vs full system)
- 3 clinicians × SUS + 5 interview questions
