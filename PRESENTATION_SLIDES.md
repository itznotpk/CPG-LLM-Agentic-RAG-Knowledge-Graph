# ClearPath — Presentation Content

Slide-ready strings. Each block: **strong headline phrase** + short elaboration. Copy straight into slides; appendix notes go on backup slides.

---

## SLIDE 1 — Problem Statements

*Three point-of-care bottlenecks. Each is a clinical friction, not a tech gap.*

**1. The Adherence Gap — guidelines are too slow to use.**
Manual CPG search doesn't fit a 10-minute consult, and pausing to search looks unsure in front of the patient. Doctors default to memory → guideline drift goes uncaught, silently.

**2. Multimorbidity Reconciliation — one guideline, one disease.**
Each CPG is written standalone; a comorbid patient needs 2–3 merged by hand. Dosing and threshold conflicts are left for the doctor to resolve alone, under time pressure.

**3. The AI Trust Gap — generic AI can't be verified.**
Off-the-shelf AI summarises CPG text with no source and no safety check. The doctor can't verify it against the real guideline → output stops at text, and the plan is still built alone.

> **Appendix:** All three are structural, not knowledge gaps — the doctor *knows* the medicine; the workflow fails them. ClearPath turns each friction into a pipeline capability (Stages 3–4, Stages 2 & 5, Stage 6).

---

## SLIDE 2 — Needs Statements

*What the point of care actually demands.*

- **Guideline evidence, instantly and invisibly** — surfaced automatically, no visible search step.
- **Automatic multimorbidity merge** — one reconciled plan tailored to age, sex, comorbidities, and current meds.
- **Verifiable, not just plausible** — every recommendation citation-traced to a specific CPG paragraph.
- **A safety net that blocks harm** — an independent check that stops a dangerous plan before sign-off.
- **Doctor stays in control** — override, edit, and feedback at every step; the AI proposes, the clinician decides.

> **Appendix:** Need framing = *"A busy Malaysian clinician needs guideline-grounded, safety-checked plans in the flow of a 10-minute consult, without trading away verifiability or control."*

---

## SLIDE 3 — Target Audience

*Who feels the pain first.*

**Primary — Frontline clinicians in Malaysia.**
GPs, medical officers, and outpatient/primary-care doctors working under 10-minute consults with multimorbid patients and MoH CPGs as the standard of care.

**Secondary — Clinics & hospital departments.**
Groups seeking consistent, auditable, guideline-adherent care and a defensible safety trail.

**Tertiary — Health systems & MoH-aligned programmes.**
Standardising CPG adherence and capturing structured decision data at scale.

> **Appendix — near-term deployment context (from clinician pilot):** synthesis is currently too slow for live in-consult use → best first fit is **post-consult review, second-opinion, and teaching**, moving to in-consult as latency drops.

---

## SLIDE 4 — Solution (transition into demo)

*One line, then show it live.*

**ClearPath — Malaysian CPG-grounded clinical decision support.**
Converts static, multi-hundred-page guidelines into an automated, moment-driven pipeline: **triage → grounded evidence → reconciled plan → safety-checked sign-off** — so doctors spend hours **with patients, not paperwork**.

- **Hybrid deterministic + agentic** — anything that can be deterministic *is*; LLMs reason only on grounded evidence.
- **Dual-database foundation** — vector store for *recall*, knowledge graph for *structural safety*.
- **Live literature + international guidance** — graded Europe PMC evidence, clinician-gated comparison.

*→ Rest is the demo.*

---

## SLIDE 5 — Impact of ClearPath

*Safe. Coherent. Actionable. Traceable. Clinician-led.*

**1. From Guidelines to Safer Care** — an independent Stage-6 safety critic catches harm before sign-off (**92% sensitivity / 100% specificity**).

**2. One Patient. Multiple Guidelines. One Coherent Plan.** — 2–3 conflicting CPGs reconciled automatically into a single plan tailored to the patient.

**3. A Clinician's Second Opinion** — grounded, on-demand support that reinforces the doctor's judgement instead of replacing it.

**4. AI Proposes. Clinicians Decide.** — override, edit, and feedback at every step; the clinician stays in control (Reasoning Visibility **5/5**).

**5. From Evidence to an Actionable Plan** — output isn't a text summary but an executable 8-section care plan.

**6. Trust Through Traceability** — every recommendation citation-traced to a specific CPG paragraph (Reasoning Transparency **4.82/5**).

> **Appendix — measured pilot results** (in-house RAGAS-style harness, reproducible): end-to-end **~2.1 min**; routing **100% top-1 (44/44)**; scope refusal **11/11**; adversarial + injection + multilingual **14/14**; Safety scored **4.93/5** by clinicians. In blinded scoring by 5 doctors, ClearPath **led every clinical-quality dimension** over Qmed AskCPG and NotebookLM (widest margin: Uncertainty Handling **+0.80**). Reported honestly: Faithfulness **0.864** and retrieval nDCG **0.669** fall a *stated* distance below target. Pilot scale = 3 cases, 5 evaluators.

---

## SLIDE 6 — Built with Codex + GPT-5.6

*A tiny team shipped a semester of work — because Codex did the building.*

**1. Right model for each job.** GPT-5.6 matched to task: **Sol** on the safety-critical core (hybrid safety critic, D1–D6 routing ladder, two-pass EBM refine, validator chain); **Terra** on the supporting systems (CPG ingestion, Telegram follow-up, eval, docs).

**2. Skills enforced discipline.** Superpowers skills — brainstorming, test-driven development, systematic debugging, verification-before-completion — turned Codex from a code generator into a disciplined engineer that plans, tests, and verifies.

**3. Sub-agents distributed the work.** Specialised agents ran in parallel — code-explorer to map, code-architect to design, root-cause-debugger to fix, code-reviewer to catch — so one prompt fanned out into a coordinated team.

> **Appendix:** The free GPT-5.6 quota was our single biggest accelerant — genuine thanks for the compute.

---

## SLIDE 7 — Business Model

*B2B SaaS to the healthcare system — value = time saved + risk reduced + adherence proven.*

**How we charge — tiered subscription:**
- **Clinician seat** — per-doctor monthly subscription (solo GPs, small practices).
- **Clinic / department licence** — per-site tier with shared analytics and audit trail.
- **Health-system / MoH programme** — volume licensing + deployment, standardising CPG adherence at scale.

**Why they pay:**
- **Time** — reclaimed minutes per consult, at scale.
- **Risk** — a documented, auditable safety trail on every plan.
- **Adherence** — provable guideline fidelity for accreditation and quality reporting.

**Land-and-expand:** start as **post-consult review / teaching** → prove safety and adherence → expand into in-consult decision support as latency drops.

> **Appendix — moats to defence:** the curated dual database (30 CPGs + knowledge graph) and clinician-validated gold sets are the hard-to-copy asset; corpus growth and the feedback-reinforced retrieval loop compound the advantage with every consult.
