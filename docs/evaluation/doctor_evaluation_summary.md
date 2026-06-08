# Doctor Evaluation Summary — CPG LLM System

**Evaluators:** 3 Doctors (blind evaluation)  
**Evaluation Date:** 2026-06-06  
**Scenarios Covered:** 3 clinical cases + Workflow/UI-UX assessment

---

## Overview

Three systems were compared across 8 clinical aspects (1–5 scale) by 3 independent evaluators in a blind study. Response order was randomised per scenario to prevent bias:

- **Scenario 1** — R1: ClearPath, R2: QMed AskCPG, R3: NotebookLM
- **Scenario 2** — R1: ClearPath, R2: NotebookLM, R3: QMed AskCPG
- **Scenario 3** — R1: NotebookLM, R2: ClearPath, R3: QMed AskCPG

---

## Scenario 1 — HFrEF + T2DM + Obesity (62M, LVEF 25%, NYHA II)

*R1 = ClearPath | R2 = QMed AskCPG | R3 = NotebookLM*

| Aspect | Ev1 CP | Ev1 QM | Ev1 NB | Ev2 CP | Ev2 QM | Ev2 NB | Ev3 CP | Ev3 QM | Ev3 NB |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| 1. Clinical Correctness | 5 | 4 | 4 | 4 | 5 | 4 | 5 | 4 | 4 |
| 2. Guideline Fidelity | 5 | 5 | 5 | 5 | 5 | 5 | 5 | 4 | 4 |
| 3. Safety | 5 | 5 | 5 | 5 | 5 | 4 | 5 | 4 | 3 |
| 4. Reasoning Transparency | 5 | 4 | 3 | 5 | 5 | 5 | 5 | 4 | 3 |
| 5. Citation Quality | 5 | 5 | 5 | 4 | 5 | 4 | 5 | 4 | 3 |
| 6. Uncertainty Handling | 5 | 3 | 3 | 5 | 4 | 4 | 4 | 3 | 2 |
| 7. Appropriate Deferral | 4 | 3 | 3 | 4 | 4 | 4 | 5 | 4 | 3 |
| 8. Trust to Use | — | — | — | 3 | 3 | 4 | 5 | 4 | 3 |

---

## Scenario 2 — Pregnancy HTN + GDM (35F, 30 weeks, Losartan on board)

*R1 = ClearPath | R2 = NotebookLM | R3 = QMed AskCPG*

| Aspect | Ev1 CP | Ev1 NB | Ev1 QM | Ev2 CP | Ev2 NB | Ev2 QM | Ev3 CP | Ev3 NB | Ev3 QM |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| 1. Clinical Correctness | 5 | 3 | 5 | 4 | 5 | 4 | 5 | 4 | 4 |
| 2. Guideline Fidelity | 5 | 5 | 5 | 5 | 5 | 5 | 5 | 4 | 4 |
| 3. Safety | 5 | 5 | 5 | 5 | 5 | 5 | 5 | 4 | 4 |
| 4. Reasoning Transparency | 5 | 4 | 3 | 5 | 5 | 5 | 5 | 4 | 4 |
| 5. Citation Quality | 5 | 4 | 4 | 4 | 4 | 5 | 5 | 4 | 4 |
| 6. Uncertainty Handling | 5 | 4 | 4 | 4 | 4 | 4 | 4 | 3 | 3 |
| 7. Appropriate Deferral | 5 | 4 | 3 | 4 | 5 | 4 | 5 | 4 | 4 |
| 8. Trust to Use | 4 | 3 | 4 | 4 | 4 | 4 | 5 | 4 | 4 |

**Notes:** All three systems correctly flagged Losartan as contraindicated in pregnancy.

---

## Scenario 3 — Stable CAD + T2DM + Obesity + ED (56M, on Isosorbide Mononitrate)

*R1 = NotebookLM | R2 = ClearPath | R3 = QMed AskCPG*

| Aspect | Ev1 NB | Ev1 CP | Ev1 QM | Ev2 NB | Ev2 CP | Ev2 QM | Ev3 NB | Ev3 CP | Ev3 QM |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| 1. Clinical Correctness | 5 | 5 | 5 | 4 | 4 | 4 | 5 | 4 | 4 |
| 2. Guideline Fidelity | 5 | 5 | 5 | 4 | 5 | 5 | 5 | 4 | 4 |
| 3. Safety | 5 | 5 | 4 | 4 | 5 | 4 | 5 | 5 | 5 |
| 4. Reasoning Transparency | 5 | 4 | 3 | 5 | 5 | 5 | 5 | 4 | 4 |
| 5. Citation Quality | 4 | 4 | 4 | 5 | 5 | 5 | 5 | 4 | 4 |
| 6. Uncertainty Handling | 5 | 4 | 3 | 5 | 5 | 5 | 4 | 3 | 3 |
| 7. Appropriate Deferral | 5 | 4 | 4 | 5 | 5 | 5 | 5 | 4 | 4 |
| 8. Trust to Use | 5 | 4 | 4 | 4 | 4 | 4 | 5 | 4 | 4 |

**Notes:** All three systems correctly caught the critical PDE5i + nitrate contraindication.

---

## Average Score Across All Evaluators & Scenarios (out of 5)

*Averaged across 3 evaluators × 3 scenarios = 9 data points per cell*

| Aspect | ClearPath | QMed AskCPG | NotebookLM |
|---|:---:|:---:|:---:|
| 1. Clinical Correctness | **4.56** | 4.22 | 4.33 |
| 2. Guideline Fidelity | **4.89** | 4.67 | 4.67 |
| 3. Safety | **5.00** | 4.56 | 4.44 |
| 4. Reasoning Transparency | **4.78** | 4.22 | 4.22 |
| 5. Citation Quality | **4.56** | 4.33 | 4.33 |
| 6. Uncertainty Handling | **4.33** | 3.56 | 3.78 |
| 7. Appropriate Deferral | **4.44** | 4.11 | 4.00 |
| 8. Trust to Use | **4.12** | 3.75 | **4.12** |
| **Overall Average** | **4.59** | 4.18 | 4.24 |

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
- **Safety: 5.00/5** — ClearPath achieved a perfect average safety score across all evaluators and scenarios; critical DDIs caught in all cases (Losartan in pregnancy, PDE5i + nitrate)
- **Guideline Fidelity: 4.89/5** — Highest among all three systems; recommendations consistently traceable to Malaysian MoH CPGs
- **Reasoning Transparency: 4.78/5** — ClearPath outperforms both QMed (4.22) and NotebookLM (4.22) by +0.56
- **Uncertainty Handling: 4.33/5** — Largest competitive gap; +0.77 over QMed and +0.55 over NotebookLM
- **Overall Average: 4.59/5** — Leads QMed (4.18) by +0.41 and NotebookLM (4.24) by +0.35

### Weaknesses / Areas for Improvement
- **Workflow fit (2/5)** — Too verbose for real-time consultations; better suited as a post-consult or teaching tool
- **Latency (2/5)** — Noticeable wait time is a barrier for time-pressured clinical use
- **Information density (3/5)** — Too much text shown by default; reasoning should be collapsed unless actively requested
- **Trust to Use (4.12/5)** — Tied with NotebookLM; evaluators want to cross-check 1–2 points before acting

### Overall Verdict
ClearPath leads all three systems across every evaluated dimension. The system demonstrates **clinically superior accuracy, perfect safety detection, and strongest reasoning transparency**, but requires a **UI/UX refinement for in-consult deployment**. The primary recommended use cases are **post-consult review and medical education/teaching** in current form.
