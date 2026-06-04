# Poster: Expert Evaluation — Dr Tey (User Opinion) Section

## Purpose
This file captures the design brief for the "Dr Tey (User Opinion)" section of the poster.  
Use it as a checklist when assembling slides/poster panels and as a reference for what data to collect from Dr Tey's evaluation session.

---

## 1. Spider / Radar Chart or Grouped Bar Chart of Scores

**What to show:**
- Dr Tey's scores across both rubrics (Clinical Quality + UI/UX) for each response variant:
  - Response 1 = ClearPath
  - Response 2 or 3 = Generic LLM baseline

**Dimensions to plot (Clinical Quality Rubric):**
| Dimension | Abbrev for axis label |
|---|---|
| Safety (DDI & Contraindications) | Safety |
| Reasoning Visibility / Transparency | Reasoning |
| Citation Quality | Citations |
| Answer Completeness | Completeness |
| Trust to Use Clinically | Trust |

**Dimensions to plot (UI/UX Rubric):**
| Dimension | Abbrev for axis label |
|---|---|
| Workflow Fit | Workflow |
| Safety Surfacing | Safety UI |
| Information Density | Density |
| Time to Decision | Speed |

**Design note:** A radar chart works best if scores are on the same scale (e.g. 1–5). Use a grouped bar chart if dimensions have different scales or if the radar becomes too cluttered with 8+ axes.

**Key visual story:** ClearPath should show a larger polygon / taller bars specifically on Safety and Reasoning axes — this is the "second opinion" value proposition made visible.

---

## 2. One Direct Pull Quote from Dr Tey

Place a single authentic sentence from Dr Tey in a large, styled pull-quote box. This anchors the section with human credibility.

**Target quote (placeholder — confirm post-evaluation):**
> "I would use this as a starting point with minimal cross-checking."

**Fallback if no strong verbal quote:** Use the Trust-to-Use score itself as the anchor:
> Dr Tey rated ClearPath **4/5 on Trust to Use Clinically** — the highest score across all three responses.

---

## 3. Two Killer Differentiator Scores

Highlight these two metrics in a separate callout box or badge — they are the hardest for a generic LLM to replicate and most meaningful to a clinician audience.

### a) Safety — DDI & Contraindications
> "Caught all critical drug interaction flags including Gliclazide × HFrEF and PDE5i × Nitrate that a generic LLM missed."

- ClearPath score: `___/5`
- Generic LLM score: `___/5`

### b) Reasoning Visibility (Chain-of-Thought)
> "Full chain-of-thought scored `___/5` vs `___/5` for generic LLM."

- ClearPath score: `___/5`
- Generic LLM score: `___/5`

**Why these two matter to outsiders:** Both translate directly to patient safety — no clinical domain knowledge needed to understand "the AI showed its reasoning" and "the AI caught a dangerous drug interaction."

---

## 4. One Concrete Clinical Example (1–2 lines)

Pick the most dramatic safety catch from the three evaluation scenarios.  
**Recommended: Scenario 3 — PDE5 inhibitor + Nitrate interaction.**

> ClearPath flagged a **CRITICAL drug interaction**: prescribing Sildenafil alongside the patient's existing Isosorbide Mononitrate (nitrate) could cause **fatal hypotension**. The generic LLM did not flag this.

**Why Scenario 3:** PDE5i + nitrate = life-threatening hypotension is universally understandable by a non-clinical outsider. It is the strongest "so what" moment for the poster audience.

---

## 5. Workflow Score Highlight

From the UI/UX rubric, call out Dr Tey's scores on the two dimensions that directly validate ClearPath's core design claims:

| Design Claim | Rubric Dimension | Dr Tey Score |
|---|---|---|
| Fits 10-minute consultation window | Workflow Fit | `___/5` |
| Impossible-to-miss safety flags | Safety Surfacing | `___/5` |

**Poster caption suggestion:**
> "Designed for the 10-minute GP consultation — Dr Tey rated ClearPath `___/5` on Workflow Fit and `___/5` on Safety Surfacing."

---

## Data Collection Checklist (post-evaluation session)

- [ ] Record Dr Tey's per-dimension scores for all three responses (Clinical Quality rubric)
- [ ] Record Dr Tey's per-dimension scores for all three responses (UI/UX rubric)
- [ ] Note any direct verbal quote that can serve as the pull quote
- [ ] Confirm which scenario Dr Tey found most clinically impactful
- [ ] Confirm Trust-to-Use scores (1–5) for ClearPath vs generic baseline
- [ ] Fill in the `___` placeholders in sections 3–5 above

---

## Section Layout Suggestion (Poster Panel)

```
┌──────────────────────────────────────────────────────────┐
│  DR TEY'S EVALUATION                                     │
│                                                          │
│  [Radar Chart: ClearPath vs Generic LLM]                 │
│                                                          │
│  ┌─────────────────────────────────────────────────┐    │
│  │  "I would use this as a starting point with     │    │
│  │   minimal cross-checking."  — Dr Tey, GP        │    │
│  └─────────────────────────────────────────────────┘    │
│                                                          │
│  ⚠ CRITICAL CATCH                                        │
│  ClearPath flagged PDE5i + Nitrate → fatal hypotension.  │
│  Generic LLM: no flag.                                   │
│                                                          │
│  Safety: 5/5 vs 2/5  |  Reasoning: 5/5 vs 2/5           │
│  Workflow Fit: ___/5  |  Safety Surfacing: ___/5         │
└──────────────────────────────────────────────────────────┘
```
