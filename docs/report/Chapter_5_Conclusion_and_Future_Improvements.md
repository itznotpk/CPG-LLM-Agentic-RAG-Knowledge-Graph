# CHAPTER 5: CONCLUSION AND FUTURE IMPROVEMENTS

## 5.1 Project Outcome

ClearPath was built to close one specific gap: clinical decision isolation in Malaysia's rural and district primary care clinics, where a single clinician must manage a wide case spectrum without access to a colleague, a usable guideline, or a pharmacist. The system built and evaluated is a seven-stage hybrid deterministic–agentic pipeline, grounded in 30 validated Malaysian MOH CPGs and a curated drug knowledge graph, that accepts a structured patient case and returns a schema-validated, action-tagged care plan with dual-source safety checking.

The reasoning backend — the part that could be evaluated without recruiting clinicians — passed the majority of its quantitative targets. The application-tier test suites and the multi-clinician blinded evaluation remain incomplete. Both facts are stated here, not softened.

---

## 5.2 Achievement Against Objectives

**Objective 1 — Unified, machine-interpretable knowledge base.** Met. The ICD-11 routing layer resolves every tested code to the correct Malaysian MOH CPG, and the scope-refusal mechanism correctly identifies out-of-corpus cases as a first-class event rather than generating an unsupported answer. Retrieval recall and hit-rate targets are passed; ranking quality (nDCG@10) falls short of the published target and is acknowledged as a gap.

**Objective 2 — Transparent, auditable second opinion within the consultation window.** Substantially met on transparency; partially met on the consultation-window requirement. The per-stage reasoning trace exposes the DDx shortlist, routing D-level, retrieved evidence scores, and safety-flag sources in a way no peer system reviewed in Chapter 1 can match. The expert evaluator confirmed ceiling scores on Reasoning Transparency and Reasoning Visibility. The consultation-window requirement is not met: end-to-end latency is approximately 2.5 minutes, which the same evaluator explicitly identified as the primary adoption barrier.

**Objective 3 — Medication safety via dual-source critic.** Met for the cases evaluated. The system surfaces KG-sourced drug interactions the clinician did not prompt, vetoes an existing medication against the patient's pregnancy state, and pre-empts a not-yet-prescribed drug against a current regimen. The expert evaluator scored Safety at the ceiling across all three evaluated scenarios.

**Objective 4 — Structured, executable care plan carried longitudinally.** The care-plan schema is fully implemented and structurally validated. The prior-visit summary loop is implemented in the data layer. The gap is that the Supabase data layer has not been integration-tested, so longitudinal persistence under real load rests on design intent rather than measured behaviour.

---

## 5.3 Limitations

**Latency (~2.5 min end-to-end).** The dominant limitation for clinical adoption. Stage 5 synthesis accounts for ~43% of total wall time. The published target of `p95 < 8 s` was calibrated for a simpler retrieval pipeline; the realistic target for this architecture is `p95 < 60 s`, which has not been achieved.

**Faithfulness gap (mean 0.864 vs ≥0.90 target).** The residual ~3.6 pp gap traces to a small number of hard cases where synthesis paraphrases knowledge not present in the retrieved chunks. The number is methodology-clean and should not be rounded up.

**Retrieval ranking (nDCG@10 below target).** Recall and hit-rate pass; nDCG misses because most queries surface only 1–3 relevant chunks, making a high-ranking nDCG structurally difficult without chunk-level tuning.

**Non-determinism in co-equal-diagnosis cases.** Top-1 diagnosis is stable only when a single dominant diagnosis exists. When two diagnoses are co-equally explicit, the seedless reranker flips the primary across runs. The query itself is byte-identical; the variance is isolated to one component.

**Application-tier tests not executed.** Supabase data layer, authentication, and Doctor UI test suites are defined but have not run. This is the single fastest-to-close testing gap.

**Single expert evaluation (n=1, unblinded).** Directional, not statistically reportable. A blinded multi-clinician evaluation with competitor outputs is the next validation event.

**KG coverage not formally audited.** The drug knowledge graph covers the medication space in the 30-CPG corpus but has no published recall figure against a gold interaction set.

---

## 5.4 Future Improvements

**1. Reduce latency.** Stream Stage 5 output section-by-section so the clinician sees recommendations before the full plan completes. Cache DDx and routing results for repeat presentations. Target: `p50 < 60 s`.

**2. Execute application-tier test suites.** Run the Supabase, Vitest, and Playwright suites against a staging environment. Converts "rests on design intent" into measured behaviour — achievable in days, not weeks.

**3. Summary-mode UI.** A fast-triage view rendering only medications (P2), referrals (P6), and red flags (P7), with the full plan on demand. Directly addresses the expert evaluator's Workflow Fit score of 2/5.

**4. Multi-clinician blinded evaluation.** Recruit ≥3 clinicians across Cardiology, Endocrinology, and O&G. The rubric, scoring formula, and competitor output preparation guide are already designed; the blocking step is IRB approval.

**5. Seed the DDx re-ranker.** Move Stage-2 re-ranking to a seedable backend to stabilise top-1 for co-equal-diagnosis cases. Requires A1 re-validation before deployment.

**6. KG coverage audit and expansion.** Compare the current interaction edge set against a standard pharmacological reference to quantify coverage, then extend to drug classes outside the 30-CPG space.

---

## 5.5 SWOT Analysis

| **Strengths** | **Weaknesses** |
|---|---|
| ICD-11 anchored routing with first-class scope refusal | ~2.5 min end-to-end latency — fails the 10-minute consultation |
| Dual grounding (vector + KG) — structurally unreachable by reprompting | Application-tier test suites designed but not yet executed |
| Schema-validated executable care plan (START / CHANGE / CONTINUE / STOP) | Single expert evaluation (n=1, unblinded) |
| Malaysian MOH-specific corpus with per-stage audit trace | Drug knowledge graph coverage not formally audited |

| **Opportunities** | **Threats** |
|---|---|
| Malaysia's National Digital Health Blueprint and rural clinic digitisation programme | General LLMs improving rapidly; structural advantage narrows over time |
| rPPG contactless vitals as a differentiator in resource-scarce settings | Patient data privacy and local regulatory compliance requirements |
| Telehealth and asynchronous consultation workflows post-pandemic | Clinician adoption resistance without published outcome data |
| MOH CPG revision cycles create natural re-deployment milestones | Corpus maintenance cost per MOH revision without dedicated engineering support |

---

## 5.6 Cost Model

Understanding the per-consultation cost is necessary for any deployment conversation with a public-health partner.

**Per-consultation LLM cost.** A typical full pipeline run (Stage 2 DDx rerank + Stage 5 synthesis + Stage 6 safety critic) sends approximately 4,000–8,000 tokens to cloud LLM endpoints and receives approximately 2,000–4,000 tokens in return. At current API pricing for the models used (Gemini Flash-class and MiMo-class inference), this yields an estimated per-consultation cost of **USD 0.05–0.15 (approximately RM 0.25–0.70)**. Scope-refusal eliminates the Stage 5 call for out-of-scope presentations, reducing cost to under USD 0.01 for those cases.

**Monthly infrastructure.** At pilot scale (< 500 consultations/month):

| Component | Tier | Est. Monthly Cost |
|---|---|---|
| Neon Serverless Postgres (pgvector) | Launch plan | ~USD 19 |
| Neo4j Aura (KG) | Free / Professional | USD 0–65 |
| FastAPI hosting (containerised) | Small cloud VM | ~USD 10–20 |
| **Total infrastructure** | | **~USD 30–100/mo** |

**At 100 consultations/day** the LLM cost is USD 5–15/day and infrastructure is absorbed. Total monthly operating cost at that scale is approximately **USD 200–550 (RM 1,000–2,600)** — less than the salary of one half-day locum physician.

**Return on intervention.** A single avoided secondary-care referral saves the patient RM 200–500 in transport and clinic fees. An averted inpatient medication error — the type the dual-source safety critic is designed to prevent — saves multiples of that in treatment cost alone. At even a modest catch rate, the system pays for its inference cost within the first week of deployment.

**Corpus maintenance cost.** Each Malaysian MOH CPG revision requires re-ingestion, re-chunking, embedding regeneration, and an evaluation harness regression run — approximately 2–4 hours of engineering time per affected CPG. With the pipeline documented and the eval harness runnable without specialist knowledge, the per-revision cost is low and predictable.

---

## 5.7 Concluding Remarks

ClearPath demonstrates that a compound, deterministic-first system can reliably surface CPG-aligned, safety-checked care plans for multi-comorbid rural primary care presentations. The reasoning backend is sound, the safety contract holds for the cases tested, and the per-stage audit trace gives clinicians the transparency to trust — or override — the system's recommendations.

The honest picture includes what is not finished: latency that keeps the tool out of the fast triage window, application-tier tests that have not run, and a full clinical validation that requires IRB. These are not concealed — they are the precise agenda for the next phase.

The system is a credible, evaluated infrastructure artefact designed for a community that structural healthcare gaps have underserved for decades. Making it fast enough for the 10-minute rural consultation, and demonstrating its clinical impact through deployment, is the work that follows.
