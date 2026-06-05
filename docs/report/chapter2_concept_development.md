# CHAPTER 2: CONCEPT DEVELOPMENT

> Provide a list of project requirements and metrics that will be used to demonstrate that these have been satisfied, summarize the scope of ideas considered, and describe the processes and rationale used for selecting the "best" concepts for the overall product.

---

## 2.1 Identifying Customer Needs

To gain a comprehensive understanding of customer needs, interviews and surveys were conducted with various stakeholders across public healthcare, clinical academia, and health-technology industry, as listed in Table 2.1. Proof of these interviews, including pictures taken during the sessions, can be found in Appendix A. These engagements were anchored by our primary industry partner, **MHNexus**, whose operational exposure to Malaysia's rural *Klinik Kesihatan* network directed our attention to the **Remote Medicine** problem space — where junior Medical Officers (MOs) and Medical Assistants (MAs) deliver care under severe structural constraints.

*Table 2.1 List of stakeholders interviewed*

| Companies | Individuals | Position |
|---|---|---|
| MHNexus | Mr Billy Soo Kong Mooi | Chief Operating Officer |
| | Dr Teh Ee Von | Medical Officer |
| Kementrian Kesihatan Malaysia | Dr Wilson | Doctor in Klinik Kesihatan Belaga |
| | Dr Marcos Popey Jarith | Leader of one of the mobile clinics team |
| | Dr Farhan | Doctor in Klinik Kesihatan Kemabong |
| | Dr Ch'ng | Consultant / Senior Specialist in private hospital of Alor Setar |
| | Dr Gavin | Medical Officer in Hospital Kapit |
| | Dr Rajiv | Clinical Specialist in Hospital Kapit |
| | Dr Adibah M | Medical Officer in PKD Nabawan |
| | Dr Vignes A/L Subramaniam | Medical Officer in Hospital Kapit, Sarawak |
| Faculty of Medicine, University Malaya | Associate Prof. Dr Terence Ong Ing Wei | Associate Professor in University Malaya |
| Mudah HealthTech | Chin Jun Jie | Operation Executive |
| Remedi | Dr Khairul | Managing Director |
| | Mr Rashidi | Head of Business and Services |
| Clique Tech | Mr Ganesha Karuppiaya | Managing Director |
| | Mr Daniel | Chief Technical Officer |
| | Mr Robinsen | Account Manager |
| AlphaSwift | Mr Prathiv | Aeronautical Engineer |

Three structural realities surfaced consistently across the rural-facing interviews (Dr Wilson, Dr Marcos, Dr Farhan, Dr Adibah, Dr Vignes) and were corroborated by published statistics. First, up to **45.6% of rural clinics in East Malaysia operate without a resident doctor**, and only **53.5% of rural public clinics are staffed with a medical doctor** (versus 93.8% urban) — so the typical user is a junior MO/MA working in professional isolation. Second, authoritative Clinical Practice Guidelines (CPGs) run to **100+ pages**, yet a primary-care consultation lasts only **10.5–14.3 minutes**, making manual guideline lookup infeasible at the point of care. Third, **76% of Malaysian doctors** cite poor facilities to access evidence as a barrier to evidence-based practice — a gap that widens under the unstable connectivity and absent specialist/pharmacist backup of rural settings.

Using the information gathered, the customer needs are translated into formal statements to facilitate clear analysis. Rather than the broad functional buckets used in the initial study, the statements are re-categorised against the **three core clinical bottlenecks** that the final system is required to resolve, as shown in Table 2.2.

*Table 2.2: Categorized customer need statements*

| Category | Customer Need Statement |
|---|---|
| **1. Guideline Accessibility & Search Friction** | Clinicians need the right CPG recommendation surfaced within the consultation window, without manually opening and searching long PDF guidelines. |
| | The system must ground every recommendation in official, current Malaysian MOH CPGs rather than generic or unverifiable internet sources. |
| | The system must deliver evidence-graded answers (with their original MOH grading) so clinicians can judge the strength of each recommendation. |
| | Rural clinics need guidance that remains usable under unstable connectivity and limited clinic IT support. |
| | The system should route a patient's presentation to the correct guideline deterministically, so the same case yields the same scoped guidance regardless of who is using it. |
| **2. Diagnostic Isolation & Cognitive Fatigue** | Junior clinicians working without on-site specialists need decision support that helps reason through complex, overlapping comorbidities. |
| | The system needs to generate a ranked differential diagnosis tailored to the patient's age, sex, comorbidities, and current medications. |
| | The system must respect the clinician's own clinical judgement — surfacing diagnoses they have already named and never overriding them silently. |
| | Clinicians need full override control, with the care plan re-synthesised instantly when they change a diagnosis. |
| | The system must reduce cognitive load with a transparent, step-by-step trace the clinician can follow and trust, not an opaque single answer. |
| **3. Medication Safety in Pharmacist-Vacant Clinics** | In clinics without an on-site pharmacist, the system must independently audit prescriptions for drug–drug interactions, allergy cross-reactivity, and organ-impairment dosing. |
| | The system must catch structural drug–condition contraindications even when no single guideline paragraph explicitly states them. |
| | The system must block sign-off when a critical or major safety concern is detected, rather than letting an unsafe plan pass silently. |
| | Safety review must remain reliable even when supporting infrastructure is flaky — concerns must never be hidden by a technical failure. |
| **Cross-cutting: Continuity & Workflow Fit** | The system must produce a structured, executable care plan that a clinician can act on directly within the visit. |
| | The system should preserve continuity across visits — carrying forward what changed, what to watch, and what to verify — for patients seen by rotating staff. |
| | The system must keep the clinician in the loop: it advises and documents, but the clinician retains final sign-off and accountability. |

These needs map directly onto the three bottlenecks the final ClearPath system was built to resolve — **guideline access friction** (deterministic scoped routing and evidence-graded retrieval), **diagnostic isolation** (contextual differential re-ranking with clinician override), and **medication safety** (the hybrid adversarial safety critic) — with continuity and human-in-the-loop sign-off carried across all three. This categorisation forms the foundation for the prioritised needs statements (Section 2.2) and the target specifications (Section 2.3) that follow.

---

## 2.2 Needs Statements

The categorized statements in Table 2.2 capture *what* stakeholders expressed, but they vary in granularity and are not yet weighted for design trade-offs. In this section the raw statements are consolidated into a concise set of **prioritized customer needs** — each phrased in solution-neutral language ("the system does X" rather than "the system uses technology Y") so that no single design is presumed at this stage. The prioritisation reflects the emphasis our stakeholders placed on each need during the interviews.

The clearest signal came from our engagement with **MHNexus** and the rural Klinik Kesihatan clinicians. Across these conversations a consistent hierarchy emerged: **patient safety is non-negotiable**, **trust through transparency and clinician control is the precondition for adoption**, and **speed is what makes the tool usable inside a real consultation**. Dr Teh Ee Von (MHNexus) and the field MOs were explicit that a tool which is fast but occasionally unsafe, or accurate but opaque, would not be used — a junior officer in an isolated clinic will only rely on a second opinion they can both verify and overrule. These three themes — safety, trust, and speed — drive the importance weighting below.

Each need is rated on a 1–5 importance scale, where **5 = Critical** (the product fails without it), **4 = High**, **3 = Moderate**. The ratings carry forward into the Needs–Metrics matrix in Section 2.3.

*Table 2.3: Prioritized customer needs*

| # | Need Statement | Bottleneck Addressed | Importance |
|---|---|---|---|
| N1 | The system surfaces the relevant clinical-practice-guideline content for a patient's presentation fast enough to be used within a single consultation. | Guideline access | 5 |
| N2 | The system grounds every recommendation it makes in official, current Malaysian MOH CPGs, with the source traceable. | Guideline access | 5 |
| N3 | The system labels each recommendation with its evidence grade so the clinician can weigh its strength. | Guideline access | 4 |
| N4 | The system maps a patient's presentation to the correct guideline consistently, returning the same scoped guidance for the same case. | Guideline access | 4 |
| N5 | The system produces a ranked differential diagnosis tailored to the patient's age, sex, comorbidities, and current medications. | Diagnostic isolation | 5 |
| N6 | The system respects the clinician's own clinical reasoning — surfacing diagnoses they have already named and never silently overriding them. | Diagnostic isolation | 5 |
| N7 | The system lets the clinician override any diagnosis and re-generates the care plan immediately on that change. | Diagnostic isolation | 4 |
| N8 | The system exposes its reasoning as a transparent, followable trace rather than an opaque single answer. | Diagnostic isolation | 4 |
| N9 | The system independently audits every prescribed plan for drug–drug interactions, allergy cross-reactivity, and organ-impairment dosing. | Medication safety | 5 |
| N10 | The system catches structural drug–condition contraindications even when no single guideline paragraph states them explicitly. | Medication safety | 5 |
| N11 | The system withholds sign-off when a critical or major safety concern is present, rather than letting an unsafe plan pass. | Medication safety | 5 |
| N12 | The system keeps safety review reliable under degraded infrastructure — a technical failure never hides a clinical concern. | Medication safety | 4 |
| N13 | The system outputs a structured, executable care plan the clinician can act on directly within the visit. | Cross-cutting | 4 |
| N14 | The system preserves continuity across visits, carrying forward what changed, what to watch, and what to verify. | Cross-cutting | 3 |
| N15 | The system keeps the clinician in final control — it advises and documents, but the clinician signs off and remains accountable. | Cross-cutting | 5 |

**Reading the priorities.** Six needs are rated Critical (N1, N2, N5, N6, N9, N10, N11, N15). They cluster on exactly the two themes our stakeholders refused to compromise on: *safety* (N9–N11 — independent auditing, structural contraindication detection, and the sign-off block) and *trustworthy grounding under clinician control* (N2 source-traceability, N6 respecting the clinician's diagnoses, N15 human-in-the-loop accountability). Speed (N1) is the third Critical need — not because it outranks safety, but because a second opinion that arrives after the consultation has ended provides no value at all. The remaining High and Moderate needs refine the experience (evidence grading, override re-synthesis, transparency, continuity) but the product would not be considered viable for a rural clinic without the Critical set. This prioritisation directly shapes the target specifications in Section 2.3, where each need is converted into one or more measurable engineering metrics.
