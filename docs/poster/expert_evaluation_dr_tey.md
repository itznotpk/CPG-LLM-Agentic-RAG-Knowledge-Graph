# Poster: Expert Evaluation — Clinician (User Opinion) Section

## Purpose
This file is the design brief for the "Clinician Evaluation (User Opinion)" panel of the poster.
**The scores below are the real captured results** from the structured rubric review
(`docs/evaluation/doctor_evaluation_summary.md`, Universiti Malaya doctor, 2026-06-06), not
placeholders. The three scenarios are the evaluation-framework cases:

- **Scenario 1 = Case 8** — HFrEF + T2DM + Obesity (62M, LVEF 25%, NYHA II)
- **Scenario 2 = Case 10** — Pregnancy HTN + GDM (35F, 30 weeks, Losartan on board)
- **Scenario 3 = Case 11** — Stable CAD + T2DM + Obesity + ED (56M, on Isosorbide Mononitrate)

Response variants scored:
- **R1 = ClearPath** (structured UI: AI reasoning trace, safety flags, tabular care plan)
- **R2, R3 = prose LLM baselines** (narrative format)

> **Honesty note — read before designing the panel.** An earlier draft of this brief assumed a
> "ClearPath 5/5 vs generic LLM 2/5" safety/reasoning contrast and a "generic LLM missed the
> interaction" story. **The captured scores do not support that.** The prose baselines tied
> ClearPath at the ceiling on safety and reasoning transparency, both caught the critical
> interactions, and the strongest prose baseline (R2) actually edged ClearPath on the clinical-
> quality grand total (111 vs 107/120). The defensible poster story is **structural** — ClearPath
> matches a strong LLM on clinical content while adding clinician-confirmed transparency, safety
> surfacing, and override control — not a head-to-head safety win. Build the panel on that.

---

## 1. Scores to Plot (real data)

### Clinical Quality rubric — aggregate across all 3 cases (/15 per aspect)

| Dimension | R1 ClearPath | R2 prose | R3 prose |
|---|---:|---:|---:|
| Clinical Correctness | 13 | **15** | 13 |
| Guideline Fidelity | 15 | 15 | 15 |
| Safety (DDIs & Contraindications) | **15** | **15** | 14 |
| Reasoning Transparency | 15 | 15 | 15 |
| Evidence Citation Quality | 12 | **14** | 13 |
| Uncertainty Handling | **13** | 12 | 12 |
| Appropriate Deferral | 12 | 13 | 12 |
| Trust to Use | 12 | 12 | 12 |
| **Grand total (/120)** | **107** | **111** | **106** |

### Per-scenario totals (/40)

| Scenario | R1 | R2 | R3 |
|---|---:|---:|---:|
| 1 — Case 8 (HFrEF + T2DM + Obesity) | 36 | 36 | 33 |
| 2 — Case 10 (Preg HTN + GDM) | 35 | 37 | 36 |
| 3 — Case 11 (Stable CAD + ED) | 36 | 38 | 37 |

### Workflow / UI-UX rubric — ClearPath (/5 per aspect, total 21/30)

| Dimension | Score | Note |
|---|---:|---|
| Workflow fit | 2 | Works for long reviews, not fast triage |
| Time-to-answer | 2 | Noticeable wait; tolerable for complex cases |
| Information density | 3 | Some sections too dense or too sparse |
| Reasoning visibility | **5** | Citations visible; full trace on demand |
| Safety surfacing | 4 | No risk of missing CRITICAL/MAJOR flags |
| Override & feedback | **5** | Can edit final plan; safety-acknowledgement flow present |

**Chart recommendation:** a **grouped bar chart** of R1 vs R2 across the eight Clinical Quality
dimensions is the honest visual — a radar implying a "larger ClearPath polygon" would overstate the
result, because R1 and R2 are close and R2 leads on total. The true visual story is **parity on
clinical content, ceiling ties on safety/reasoning, and a narrow ClearPath lead on uncertainty
handling** — plus the separate UI/UX bars, where reasoning visibility and override score 5/5.

---

## 2. Pull Quote (real)

Use the clinician's actual extended comment — it is more credible than a manufactured endorsement
and it sets up the honest "great content, needs faster UX" narrative:

> "Accuracy is good enough but needs more simplification of the output for fast readability for
> in-consult use. Clinics don't usually allow time for extensive reading."
> — Doctor, Universiti Malaya

---

## 3. The Real Differentiators (where ClearPath genuinely led or tied at ceiling)

These are the defensible callouts — each is backed by a captured score, not an assumption.

### a) Reasoning visibility & override control (the transparency thesis)
> ClearPath scored **5/5 on reasoning visibility** and **5/5 on override & feedback** — citations
> visible inline with the full reasoning trace on demand, and an editable plan with a safety-
> acknowledgement flow. This is the auditable-second-opinion value, clinician-confirmed.

### b) Uncertainty handling
> ClearPath led the prose baselines on uncertainty handling (**13 vs 12**), surfacing **8 referrals
> on Case 8 against the prose responses' 3** — it flags what it cannot resolve rather than papering
> over it.

### c) Guideline-traceable safety (a tie, stated honestly)
> All responses scored **5/5 on safety** and caught the critical interactions (Losartan in
> pregnancy; PDE5i × nitrate). ClearPath's edge is not detection but **traceability** — every
> recommendation maps to a Malaysian MoH CPG section, and safety surfacing scored 4/5.

---

## 4. One Concrete Clinical Example (1–2 lines)

Keep the PDE5i × nitrate example — it is universally understandable — but frame it as a
**reproducibility-by-structure** catch, not a "generic LLM missed it" contrast (it didn't):

> On Case 11, ClearPath flagged the **CRITICAL** PDE5-inhibitor × isosorbide-mononitrate
> interaction (fatal-hypotension risk) from a typed knowledge-graph drug–drug edge — a structural
> catch that is reproducible by design, with the flag surfaced in an impossible-to-miss safety
> banner.

---

## 5. The Honest Weakness (own it on the poster)

A single, clearly-stated limitation reads as credibility, not failure:

> The clinician rated **workflow fit 2/5 and time-to-answer 2/5**: the default output is too verbose
> and the wait too long for live in-consult use. Recommended deployment today is
> **post-consultation review or medical teaching** — the primary improvement target is UI/UX
> simplification and Stage-5 latency.

---

## Section Layout Suggestion (Poster Panel)

```
┌──────────────────────────────────────────────────────────┐
│  CLINICIAN EVALUATION  (n=1 expert review, cases 8/10/11) │
│                                                          │
│  [Grouped bar: R1 ClearPath vs R2 prose — 8 dimensions]  │
│                                                          │
│  ┌─────────────────────────────────────────────────┐    │
│  │ "Accuracy is good enough but needs more         │    │
│  │  simplification ... clinics don't usually allow │    │
│  │  time for extensive reading."  — Doctor, UM     │    │
│  └─────────────────────────────────────────────────┘    │
│                                                          │
│  ✔ Reasoning visibility 5/5  |  Override 5/5            │
│  ✔ Safety 15/15 (all variants) — ClearPath traceable    │
│  ✔ Uncertainty handling: led 13 vs 12 (8 referrals)     │
│  ⚠ Workflow fit 2/5 · Latency 2/5 → post-consult/teach   │
│                                                          │
│  Clinical-quality total: R1 107 · R2 111 · R3 106 /120  │
└──────────────────────────────────────────────────────────┘
```

---

## Data Collection Checklist (for any future multi-clinician round)

This single-expert review is formative (n = 1). To upgrade it to a validation claim:

- [ ] Recruit ≥ 3 clinicians (IRB track, per VALIDATION_PLAN §5)
- [ ] Re-score all variants on both rubrics for cases 8 / 10 / 11 (+ ideally 9, 12)
- [ ] Capture SUS / TAM / trust scales alongside the clinical-quality rubric
- [ ] Report mean ± spread across clinicians, not a single score
- [ ] Add the five-system competitor panel (Qmed AskCPG, NotebookLM, GPT-4/Gemini floor)
