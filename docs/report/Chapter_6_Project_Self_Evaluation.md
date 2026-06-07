# CHAPTER 6: PROJECT SELF-EVALUATION

## 6.1 Reflections on Design

The central design decision — deterministic wherever possible, generative only where genuine clinical reasoning is required — proved to be the right governing principle, though its costs were underestimated.

The deterministic layers delivered exactly what they promised. Building the routing layer as an explicit ICD-11 scope table rather than a retrieved similarity score meant the system could produce a first-class `out_of_scope` refusal instead of a confident answer backed by no clinical authority. This property cannot be added later by improving the retrieval model; it requires an architectural choice made upfront. Making it early was correct.

The dual-grounding architecture — CPG chunks in pgvector and typed drug-interaction edges in Neo4j — was the design decision with the clearest clinical payoff. Keeping the two stores independent and merging their outputs at Stage 6 (rather than concatenating everything into one context window) is what makes the dual-source safety claim structurally true: the KG flags what the graph knows regardless of whether the retrieved text discusses that drug pair. Any single-grounding system — however well prompted — cannot replicate this.

The choice to design the care plan as a Pydantic-validated typed schema, not a prose blob, paid off in every downstream layer: structured safety checks, consistent frontend rendering, and discrete claim-unit scoring for faithfulness evaluation. This should be the default for any clinical AI system with a defined output contract.

The unresolved tension is latency. A sequential seven-stage pipeline with two heavy LLM calls was designed for correctness, not speed. At ~2.5 minutes end-to-end it cannot fit the 10-minute rural consultation in its current form. This is a design debt that requires an architectural response — streaming Stage 5 output, parallelising independent stages — not a prompt change.

One design gap that only surfaced during evaluation: no coverage metric was built for the drug knowledge graph from the start. Without a recall figure against a gold interaction set, the safety critic's KG arm can only be characterised as "flags what the graph knows." Building a coverage audit into the design plan would have converted this from a limitation into a measured boundary.

---

## 6.2 Reflections on Implementation

Three honest lessons from the build:

**Safety-contract testing must be planned, not added late.** The silent-degradation probes were added near the end of implementation, when the pipeline was believed to be stable. The first run exposed four fail-silent bugs — a zero-chunk retrieval returning a confident plan, a Stage 4 exception that fell through to synthesis on empty evidence, and others. None would have been caught by happy-path unit tests. Probing what the system does when dependencies fail, not just when they succeed, should be in the testing plan from day one for any system with a safety claim.

**Gold-set correctness determines what the metrics actually measure.** Early evaluation runs produced numbers that appeared to indicate severe defects (routing accuracy of 18.2%, Stage-4 negative lift). Investigation in each case traced the result to gold-set artefacts — wrong ICD codes, non-existent sub-codes, a gold set designed for single-query evaluation being fed to a multi-query pipeline. The lesson is not that the system was fine all along; it is that investing in gold-set correctness before collecting metrics avoids expensive false diagnosis cycles.

**Determinism is a layered property.** The implementation work established that the pipeline has a well-defined deterministic surface (the candidate query is byte-identical across runs) and a well-defined stochastic surface (the seedless reranker, the synthesis model). Knowing this precisely — rather than treating determinism as a binary pass/fail — is the useful output of the reproducibility work. For a clinical system, knowing exactly which component introduces variance is the prerequisite for closing it.

---

## 6.3 Environmental Considerations, Sustainability, and Cost

**Environmental footprint.** The system's computational cost is dominated by two LLM inference calls per consultation. This is proportionate for a rural-clinic context: the clinical benefit of a correctly grounded, safety-checked care plan that prevents a medication error or an unnecessary secondary referral outweighs the marginal energy cost of the inference call that produced it. Scope refusal — halting the pipeline before Stage 5 for out-of-scope cases — reduces unnecessary inference at no clinical cost. The deterministic early stages (routing, retrieval scoring) carry negligible energy cost compared to the LLM steps.

**Economic sustainability.** At estimated API pricing, each full consultation costs approximately **RM 0.25–0.70 in inference** and the monthly infrastructure bill at pilot scale (< 500 consultations/month) is approximately **RM 150–500**. Against this, a single avoided secondary-care referral saves the patient RM 200–500 in transport and clinic fees; an averted medication error saves multiples of that. The system is economically self-justifying at a modest catch rate. Longer-term sustainability depends on keeping the CPG corpus current: each MOH guideline revision requires re-ingestion, re-chunking, and an evaluation harness regression run — approximately 2–4 hours of engineering time per affected document, low and predictable with the pipeline fully documented.

**Project cost and schedule.** The project ran from August 2025 to June 2026 across four phases:

| Phase | Period | Work |
|---|---|---|
| 1 — Requirements & corpus | Aug–Oct 2025 | Stakeholder interviews, 30-CPG ingestion, ICD-11 scope table, KG construction |
| 2 — Pipeline & UI | Oct 2025–Jan 2026 | Seven-stage backend, Doctor UI, Supabase data layer, rPPG integration |
| 3 — Evaluation | Jan–May 2026 | Eval harness, validation runs (A1/A2/B/C/D), expert clinician review |
| 4 — Report & deployment prep | May–Jun 2026 | Chapter writeup, robustness probes, determinism runs, final fixes |

Development used no dedicated hardware budget — the pipeline runs on cloud-managed serverless and hosted graph infrastructure. Total cloud spend during development (Neon, Aura free/trial tiers, API credits) is estimated at **USD 200–400** over the project lifetime. The primary resource consumed was engineering time.

---

## 6.4 Addressing the Local Community: Rural Malaysian Primary Care

The project was motivated by, and designed for, a specific community: rural and district primary care clinicians in Sabah and Sarawak, and the patients they serve under conditions of systematic resource constraint.

Every architectural choice in the system was informed by that context. The CPG corpus is exclusively Malaysian MOH guidelines — not American Heart Association or European Society of Cardiology guidelines adopted without local adaptation. The DDx and routing evaluation gold sets use ICD-11 codes verified against the Malaysian clinical context. The safety-critic logic reflects Malaysian prescribing practice, not global defaults. The Doctor UI was designed for a solo medical officer or medical assistant working under time pressure, not for a specialist in a resource-rich tertiary centre.

The three faces of clinical decision isolation identified in §1.2 — no colleague, no guideline, no pharmacist — map directly onto three architectural capabilities. The DDx stage and the care-plan synthesis address the absence of a colleague by providing a structured second opinion grounded in evidence. The CPG routing and retrieval stages address the absence of a usable guideline by surfacing the relevant sections from the locally validated corpus within the consultation. The dual-source safety critic addresses the absence of a pharmacist by performing a structured medication audit — checking the patient's existing and proposed medications against both LLM pharmacological reasoning and a typed graph of interactions and contraindications.

These are not generic clinical AI features. They are a response to a documented pattern of care in Malaysian rural practice: the 39.3% CPG non-adherence rate driven by time constraints and search friction [6]; the 88% second-assessment revision rate among complex cases [3]; the medication-related harm that accounts for roughly half of preventable harm globally when no pharmacist is present [18]. ClearPath was designed to be the second pair of eyes that rural clinics structurally lack, not to replace the clinician.

The cultural and contextual dimensions of the local community also shaped what the system does not do. The scope is primary care within the 30-CPG corpus — the system does not attempt to cover traditional or complementary medicine, does not generate recommendations outside its validated scope, and produces a first-class refusal event (rather than a low-confidence answer) when a case falls outside its competence. This is a deliberate cultural choice: in a setting where a wrong recommendation from a trusted system could cause significant harm with no specialist to catch it, silence is safer than reach. The `out_of_scope` event is not a failure mode; it is the system acknowledging the boundary of its validated knowledge and routing the decision back to the clinician's judgement.

The single expert evaluation conducted (Universiti Malaya, n=1) provided a meaningful data point. The evaluator confirmed that ClearPath's clinical content and safety surfacing match a strong LLM baseline, that reasoning transparency and override control are excellent, and that the primary gap for rural adoption is speed and output simplification. This feedback directly shapes the priority ordering in §5.4: latency reduction and summary-mode UI are the first-order engineering tasks before any further capability expansion.

The validation gap — the absence of a blinded multi-clinician evaluation with real rural practitioners — is acknowledged explicitly. Clinical evidence that ClearPath improves decisions under real rural-consultation conditions has not been collected; the system has demonstrated that its recommendations are guideline-grounded, safety-checked, and clinician-endorsed in a structured evaluation setting, but the step from laboratory validation to demonstrated clinical impact requires deployment, IRB, and a prospective study that is beyond the scope of this project. That step is the next one.

The project's contribution to the local healthcare context is therefore best described as a credible infrastructure artefact: a functional, evaluated, and honestly documented clinical decision support system designed specifically for Malaysian rural primary care, ready for the deployment and prospective validation work that will determine whether it improves care in practice. That is what the evidence supports, and that is what this report claims.
