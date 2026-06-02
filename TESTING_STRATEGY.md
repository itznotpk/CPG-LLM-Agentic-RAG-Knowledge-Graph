# Testing Strategy

This document outlines four testing approaches that go beyond the existing offline batch evaluation (gold sets + eval scripts). Each addresses a different gap in the current validation coverage.

---

## 1. A/B Testing

**Goal:** Compare two versions of the pipeline on the same cases to isolate the impact of a specific change.

**Example comparisons to run:**
- Vector-only retrieval vs. hybrid (vector + BM25 keyword) — does hybrid improve Recall@10?
- With vs. without KG injection (Stage 4.5) — does the graph actually improve plan quality?
- Current DDx reranker prompt vs. a revised prompt — does Hit@5 improve?
- `SEMANTIC_SCOPE_THRESHOLD = 0.32` vs. 0.28 or 0.36 — routing sensitivity

**How to implement:**
- Run both variants against the same gold set
- Report delta on key metrics (Recall@K, Hit@5, Top-1 routing accuracy)
- Use `compare_baselines.py` as the starting point

**Test cases to use:** Existing gold sets (`retrieval_gold.jsonl`, `ddx_gold.jsonl`, `routing_gold.jsonl`)

---

## 2. Adversarial / Red-Team Cases

**Goal:** Probe failure modes with deliberately difficult or edge-case inputs, not just measure average performance.

**Categories to cover:**

| Category | Example case |
|----------|-------------|
| Rare / ambiguous presentation | "Fatigue, weight loss, night sweats" — could be TB, lymphoma, or endocrine |
| Symptom-diagnosis mismatch | Chief complaint names a wrong diagnosis (e.g. "I have dengue" but vitals suggest sepsis) |
| Multi-morbidity routing | Patient has T2DM + CKD Stage 3 + hypertension — does it route to all 3 CPGs? |
| Out-of-scope ICD code | Obscure code with no CPG mapping — does it gracefully reach D9? |
| Ambiguous drug name | "Salbutamol" vs "Ventolin" vs "albuterol" — same drug, multiple aliases |
| Conflicting CPG guidance | Two routed CPGs give contradictory first-line recommendations |
| Paediatric patient edge | Age 17 vs age 18 — does the paediatric filter boundary work correctly? |
| Sex filter boundary | Male patient + obstetric CPG routed — does it get filtered? |

**Success criteria:** System either handles gracefully OR surfaces a clear assumption flag (not silent wrong answer).

---

## 3. Regression Tracking Over Time

**Goal:** Detect when a code change causes metric degradation before it reaches production.

**Current gap:** Results files exist (`eval/results/*.csv`) but there is no automated comparison against a baseline — you have to manually diff CSVs.

**What to build:**
- A `baseline.json` file that stores the last "accepted" metric snapshot (e.g. Recall@10 = 0.68, Hit@5 = 0.42)
- A `compare_to_baseline.py` script that:
  1. Runs the relevant eval scripts
  2. Compares results to `baseline.json`
  3. Flags any metric that regresses by more than a threshold (e.g. >5% drop)
  4. Prints a pass/fail summary

**Trigger:** Run automatically before any merge, or manually after changing a prompt / threshold / retrieval config.

**Key metrics to track per stage:**

| Stage | Metric | Regression threshold |
|-------|--------|---------------------|
| DDx (Stage 2) | Hit@5 | -5% |
| Routing (Stage 3) | Top-1 Accuracy | -5% |
| Retrieval (Stage 4) | Recall@10 | -3% |
| E2E | Action Recall, Safety Pass Rate | -3% |

---

## 4. Safety Critic Stress Tests

**Goal:** Verify that Stage 6 (the hybrid adversarial safety critic) catches dangerous plans. This is the highest-stakes layer and currently has the least dedicated test coverage.

**Approach:** Create a set of deliberately unsafe treatment plans and assert that the critic flags them correctly.

**Test case categories:**

| Hazard type | Injected scenario | Expected flag |
|-------------|------------------|---------------|
| Drug allergy | Patient allergic to penicillin; plan recommends amoxicillin | CRITICAL — allergy violation |
| Drug-drug interaction | Warfarin + ibuprofen co-prescribed | MAJOR — bleeding risk DDI |
| Organ impairment dosing | Metformin prescribed; patient has CKD Stage 4 (eGFR < 30) | CRITICAL — contraindicated in severe renal impairment |
| Absolute contraindication | Non-selective beta-blocker (propranolol) in patient with asthma | CRITICAL — absolute contraindication |
| Sulfonamide cross-reactivity | Patient allergic to sulfamethoxazole; plan adds furosemide | MAJOR — sulfonamide class cross-reactivity |
| False positive (safe plan) | Correct first-line plan for uncomplicated hypertension | No flags — safe_to_proceed = True |

**Metrics to report:**
- **Sensitivity** — % of dangerous plans correctly flagged (target: 100% for CRITICAL)
- **Specificity** — % of safe plans not flagged (target: >90%)
- **LLM vs. KG critic agreement** — for each case, did both critics agree? Disagreements highlight ambiguity zones.

**Implementation:** Build as a standalone `eval/run_safety_stress_test.py` that injects pre-built `TreatmentPlan` objects directly into `SafetyCritic` (bypassing Stages 1–5), so tests are fast and deterministic.

---

## Priority Order

| Priority | Test type | Reason |
|----------|-----------|--------|
| 1 | Safety Critic Stress Tests | Highest clinical stakes; lowest existing coverage |
| 2 | Adversarial / Red-Team Cases | Uncovers silent failures not visible in average metrics |
| 3 | Regression Tracking | Prevents metric decay as codebase evolves |
| 4 | A/B Testing | Useful once baselines are stable and bugs are fixed |
