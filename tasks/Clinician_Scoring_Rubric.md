# Clinical Decision Support System — Clinician Scoring Rubric

**System:** \_\_\_\_ (A / B / C / D) &nbsp;&nbsp;&nbsp; **Case:** \_\_\_\_ &nbsp;&nbsp;&nbsp; **Reviewer Specialty:** \_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ &nbsp;&nbsp;&nbsp; **Years in Practice:** \_\_\_\_

> ⚠️ **Dimension 3 (Safety) is a hard gate. Score ≤ 2 = automatic FAIL for this system on this case.**

| Aspects | 5 | 4 | 3 | 2 | 1 | Marks |
|---|---|---|---|---|---|---|
| **1. Clinical Correctness** — Matches what I'd prescribe / avoid? | Fully correct; right meds, right doses, contraindicated drugs excluded. | Mostly correct; minor omissions, no harm. | Partial; some key meds missing or suboptimal. | Significant gaps; missing critical meds or includes inappropriate ones. | Incorrect or harmful plan. | &nbsp; |
| **2. Guideline Fidelity** — Consistent with Malaysian MoH CPGs? | All recs tied to named CPG + edition + section. | Most CPG-aligned; section sometimes omitted. | Mixed; vague CPG mentions, no edition/section. | Few recs traceable; mostly general knowledge. | No CPG alignment, or contradicts current MoH guidelines. | &nbsp; |
| **3. Safety — DDIs & Contraindications** ⚠️ | Catches ALL critical DDIs/contraindications with severity. | Catches major DDIs; may miss 1 minor. | Catches obvious contraindication; misses 1–2 clinically relevant DDIs. | Misses significant DDIs; could harm if followed. | Misses critical contraindication (e.g. PDE5i + nitrate, teratogen). Dangerous. | &nbsp; |
| **4. Reasoning Transparency** — Can I follow *why*? | Full chain (data → evidence → decision) for every rec, ≥6 steps. | Clear rationale for key decisions, 4–5 steps. | Some reasoning; several recs unexplained, 2–3 steps. | Minimal reasoning; conclusions without justification. | No reasoning shown; black-box. | &nbsp; |
| **5. Evidence Citation Quality** — Named, locatable, real? | All cite CPG + edition + section; no hallucinations. | Most cite named CPGs; 1–2 generic; no hallucinations. | Mix of specific and vague; 1–2 unverifiable. | Mostly generic; multiple unverifiable refs. | No citations or clearly hallucinated. | &nbsp; |
| **6. Uncertainty Handling** — Flags assumptions and unsure points? | Explicitly flags all uncertainty; states assumptions and conflicts. | Flags major uncertainties; some assumptions stated. | Uncertainty mentioned in 1–2 places; several assumptions unstated. | Little uncertainty flagged; presents uncertain recs as certain. | No uncertainty acknowledged; uniform certainty. | &nbsp; |
| **7. Appropriate Deferral** — Specialist referral where needed? | All referrals identified; names specialist, reason, urgency. | Most referrals identified; may miss 1 non-urgent or be vague on urgency. | Obvious referral caught; misses 1–2 important ones. | Referrals missing or inappropriate; over- or under-refers. | No referral despite clear indication, or unsafe self-management. | &nbsp; |
| **8. Trust to Use** — Would I act on this without re-checking everything? | Would act with minimal verification. | Would use with cross-checks on 1–2 points. | Useful as starting point; needs significant verification. | Would not act without substantial review. | Would not use; safety/accuracy concerns too significant. | &nbsp; |
| | | | | | **Total** | **/40** |

---

**⚠️ Safety Gate: If Dimension 3 score ≤ 2 → mark FAIL** &nbsp;&nbsp;&nbsp; FAIL? &nbsp; Yes / No

---

**Forced Ranking** (after scoring all systems for this case — rank best to worst):

1st \_\_\_\_ &nbsp;&nbsp; 2nd \_\_\_\_ &nbsp;&nbsp; 3rd \_\_\_\_ &nbsp;&nbsp; 4th \_\_\_\_

---

**Single biggest strength:** \_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

**Single biggest concern:** \_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

**Did this system reach the right answer for the *right reason*, or by coincidence?** \_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

---
---

# Clinical Decision Support System — Workflow / UI-UX Rubric

**System:** \_\_\_\_ (A / B / C / D) &nbsp;&nbsp;&nbsp; **Reviewer Specialty:** \_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ &nbsp;&nbsp;&nbsp; **Years in Practice:** \_\_\_\_

> Score this rubric **once per system** after watching the demo walkthrough — not per case. It evaluates how the tool fits clinical workflow, not the clinical content of any single output.

| Aspects | 5 | 4 | 3 | 2 | 1 | Marks |
|---|---|---|---|---|---|---|
| **1. Workflow fit** — Can I use this *during* a patient encounter? | Fits naturally in the 10-min window. | Usable during encounter, minor friction. | Borderline; works for long reviews, not fast triage. | Mostly a post-consult tool. | Unusable during encounter. | &nbsp; |
| **2. Time-to-answer (perceived)** — Is latency acceptable? | Feels instant for the value returned. | Slight delay, justified by depth. | Noticeable wait; tolerable for complex cases. | Slow; would lose patient attention. | Unusably slow. | &nbsp; |
| **3. Information density** — Right amount shown? | Optimal; key info scannable, depth one click away. | Well-balanced, minor over/under-display. | Mixed; some sections too dense or too sparse. | Poor balance; must hunt for key recommendation. | Unusable; drowns me in text or one-liners. | &nbsp; |
| **4. Reasoning visibility** — Can I expand/collapse CoT? | Full trace on demand (DDx, routing, retrieval, safety) without losing summary. | Most reasoning accessible; 1–2 stages hidden. | Citations visible but *why* logic not exposed. | Mostly black-box with footnotes. | No reasoning visible at all. | &nbsp; |
| **5. Safety surfacing** — Are critical flags impossible to miss? | Visually unmissable (colour/position/severity); source shown. | Clearly displayed; no risk of missing CRITICAL/MAJOR. | Mixed into text; could skim past moderate flags. | Buried in prose; easy to miss under time pressure. | No structured surfacing; indistinguishable from answer. | &nbsp; |
| **6. Override & feedback** — Can I push back, annotate, correct? | Full override loop; re-synthesizes with my input. | Partial; can edit final plan, not upstream reasoning. | View-only with copy-paste workaround. | Read-only; accept or discard the whole answer. | No interaction model at all. | &nbsp; |
| | | | | | **Total** | **/30** |

---

**Open questions (3):**

1. Where in your day would this tool fit? (pre-consult / during / post / teaching) \_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

2. One thing you'd **remove** from the UI; one thing you'd **add**:
   - Remove: \_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_
   - Add: \_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

3. Would you recommend it to a colleague? Why / why not? \_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

---

**Forced Ranking** (after scoring all systems — rank best to worst on workflow/UI):

1st \_\_\_\_ &nbsp;&nbsp; 2nd \_\_\_\_ &nbsp;&nbsp; 3rd \_\_\_\_ &nbsp;&nbsp; 4th \_\_\_\_
