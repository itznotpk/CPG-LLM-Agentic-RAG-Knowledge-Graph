# Doctor Evaluation Summary — CPG LLM System

**Evaluator:** Doctor, Universiti Malaya  
**Evaluation Date:** 2026-06-06  
**Scenarios Covered:** 3 clinical cases + Workflow/UI-UX assessment

---

## Overview

Three response types were compared across 8 clinical aspects (1–5 scale):
- **Response 1** — System's structured UI output (with AI Reasoning Trace, Safety flags, tabular care plan)
- **Response 2** — Prose LLM output (narrative format with numbered sections)
- **Response 3** — Prose LLM output (alternative narrative format)

---

## Scenario 1 — HFrEF + T2DM + Obesity (62M, LVEF 25%, NYHA II)

| Aspect | R1 | R2 | R3 |
|---|---|---|---|
| 1. Clinical Correctness | 4 | **5** | 4 |
| 2. Guideline Fidelity | 5 | 5 | 5 |
| 3. Safety (DDIs & Contraindications) | 5 | 5 | 4 |
| 4. Reasoning Transparency | 5 | 5 | 5 |
| 5. Evidence Citation Quality | 4 | **5** | 4 |
| 6. Uncertainty Handling | 5 | 4 | 4 |
| 7. Appropriate Deferral | 4 | 3 | 3 |
| 8. Trust to Use | 4 | 4 | 4 |
| **Total** | **36** | **36** | **33** |

**Notes:** R1 and R2 tied overall. R2 scored higher on clinical correctness and citation quality. R1 scored higher on uncertainty handling and appropriate deferral (8 referrals identified vs 3).

---

## Scenario 2 — Pregnancy HTN + GDM (35F, 30 weeks, Losartan on board)

| Aspect | R1 | R2 | R3 |
|---|---|---|---|
| 1. Clinical Correctness | 4 | **5** | 4 |
| 2. Guideline Fidelity | 5 | 5 | 5 |
| 3. Safety (DDIs & Contraindications) | 5 | 5 | 5 |
| 4. Reasoning Transparency | 5 | 5 | 5 |
| 5. Evidence Citation Quality | 4 | 4 | **5** |
| 6. Uncertainty Handling | 4 | 4 | 4 |
| 7. Appropriate Deferral | 4 | **5** | 4 |
| 8. Trust to Use | 4 | 4 | 4 |
| **Total** | **35** | **37** | **36** |

**Notes:** All three correctly flagged Losartan as contraindicated in pregnancy. R2 led on clinical correctness (correctly classified as overt diabetes, not just GDM) and specialist deferral. R3 led on citation quality (specific CPG section references).

---

## Scenario 3 — Stable CAD + T2DM + Obesity + ED (56M, on Isosorbide Mononitrate)

| Aspect | R1 | R2 | R3 |
|---|---|---|---|
| 1. Clinical Correctness | 5 | 5 | 5 |
| 2. Guideline Fidelity | 5 | 5 | 5 |
| 3. Safety (DDIs & Contraindications) | 5 | 5 | 5 |
| 4. Reasoning Transparency | 5 | 5 | 5 |
| 5. Evidence Citation Quality | 4 | **5** | 4 |
| 6. Uncertainty Handling | 4 | 4 | 4 |
| 7. Appropriate Deferral | 4 | **5** | **5** |
| 8. Trust to Use | 4 | 4 | 4 |
| **Total** | **36** | **38** | **37** |

**Notes:** Highest-scoring scenario across all responses. All three correctly caught the critical PDE5i + nitrate contraindication. R2 scored highest, with perfect scores on citation quality and deferral.

---

## Aggregate Scores Across All Scenarios

| Aspect | R1 | R2 | R3 |
|---|---|---|---|
| Clinical Correctness | 13 | **15** | 13 |
| Guideline Fidelity | 15 | 15 | 15 |
| Safety | 15 | 15 | 14 |
| Reasoning Transparency | 15 | 15 | 15 |
| Evidence Citation Quality | 12 | **14** | 13 |
| Uncertainty Handling | 13 | 12 | 12 |
| Appropriate Deferral | 12 | 13 | 12 |
| Trust to Use | 12 | 12 | 12 |
| **Grand Total (/120)** | **107** | **111** | **106** |

---

## Workflow / UI-UX Assessment

| Aspect | Score (/5) | Comment |
|---|---|---|
| 1. Workflow fit | 2 | Borderline; works for long reviews, not fast triage |
| 2. Time-to-answer | 2 | Noticeable wait; tolerable for complex cases |
| 3. Information density | 3 | Mixed; some sections too dense or too sparse |
| 4. Reasoning visibility | 5 | Citations visible; full trace on demand |
| 5. Safety surfacing | 4 | Clearly displayed; no risk of missing CRITICAL/MAJOR |
| 6. Override & feedback | 5 | Can edit final plan; safety acknowledgement flow present |
| **Total** | **21/30** | |

---

## Open Questions — Doctor's Responses

| Question | Answer |
|---|---|
| Where would this tool fit? | Post-consult or teaching; text too long for in-consult reading |
| What to remove from UI? | Collapse all explanation and reasoning unless actively sought |
| What to add? | — (nothing specified) |
| Recommend to a colleague? | Not for day-to-day clinical use; maybe for post-consult learning or colleague discussion |

**Extended comment:**
> "Accuracy is good enough but needs more simplification of the output for fast readability for in-consult use. Clinics don't usually allow time for extensive reading and patients will lose confidence or feel ignored if clinician is busy reading the screen instead of talking to them."

---

## Key Findings

### Strengths
- **Clinical accuracy** is consistently high across all scenarios (4–5/5)
- **Guideline fidelity** is perfect across all three responses — all recommendations traceable to Malaysian MoH CPGs
- **Safety detection** is reliable — critical DDIs caught in all cases (Losartan in pregnancy, PDE5i + nitrate)
- **Reasoning transparency** rated 5/5 in all scenarios across all responses
- **Override & feedback loop** rated 5/5 — safety acknowledgement workflow is effective

### Weaknesses / Areas for Improvement
- **Workflow fit (2/5)** — Too verbose for real-time consultations; better suited as a post-consult or teaching tool
- **Latency (2/5)** — Noticeable wait time is a barrier for time-pressured clinical use
- **Information density (3/5)** — Too much text shown by default; doctor wants reasoning collapsed unless actively requested
- **Uncertainty handling** — R1 outperformed prose responses here, but still not achieving the maximum score consistently
- **Appropriate deferral** — R1 slightly underperforms compared to R2 on complex multi-specialist cases

### Overall Verdict
The system demonstrates **clinically acceptable accuracy and strong safety surfacing**, but requires a **UI/UX overhaul for in-consult deployment**. The primary recommended use cases are **post-consult review and medical education/teaching**, not live patient encounters in current form.
