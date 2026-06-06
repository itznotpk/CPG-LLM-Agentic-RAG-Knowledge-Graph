# CHAPTER 1: INTRODUCTION

> Rewrite of the RM-1 Chapter 1 per the Chapter-2 cross-check verdict: adds a
> "why not just naïve RAG" beat to §1.1, restructures §1.2 around the *clinical
> decision isolation* umbrella and its three faces (colleague / guideline /
> pharmacist) — which surfaces **medication safety** as a first-class problem for
> the first time — tightens §1.3 to four verifiable objectives, and realigns §1.4
> to the realistic competitive set (general LLM · NotebookLM · Qmed AskCPG), with
> Med-PaLM 2 noted but excluded as not like-for-like.
>
> Citation markers `[N]` reuse the RM-1 reference list; new sources flagged at the
> foot of the file under "New references to add."

---

## 1.1 Background

Primary healthcare systems are fundamental to early diagnosis, continuity of care, and effective disease management. In rural and underserved regions, however, clinicians operate under severe constraints: workforce shortages, high patient loads, limited access to specialist expertise, and fragmented health information systems [4], [5]. These pressures are acute in Malaysia's rural and district clinics, where a single medical officer — or, in many cases, a medical assistant — is expected to manage a wide spectrum of conditions with minimal decision support, relying heavily on personal experience and manual reference methods [4], [5].

The scale of this isolation is well documented. In Sarawak, 45.6% of rural clinics (98 of 215) have no resident doctor and are staffed only by medical assistants and nurses [1]. Sabah reports a comparable strain, with the state estimating a shortfall of more than 4,500 doctors against national manpower targets [2]. Where a doctor is present, they typically work without the support structures taken for granted in urban hospitals: no senior colleague to consult, no specialist on call, and, in many clinics, no pharmacist to review prescriptions. The clinical cost of this absent "second opinion" is significant — among complex cases sent for review, a second clinical assessment changes or refines the original diagnosis in up to 88% of cases [3].

Compounding the workforce gap is a knowledge-access gap. Clinical Practice Guidelines (CPGs) are intended to standardise care and promote evidence-based decisions, but their practical use in rural settings remains limited by time constraints, weak workflow integration, and the difficulty of navigating lengthy guideline documents during a short consultation [6], [7]. This creates a "grey zone" in practice — particularly for uncommon or comorbid presentations that do not map cleanly onto routine cases — and pushes clinicians toward conservative strategies such as patient stabilisation and early referral [7]. The downstream effect is variable care quality, a higher documentation burden, and reduced continuity of patient management [10], [11].

These observations were reinforced through direct clinical and industry engagement. In an interview on 24 October 2025 with MHNexus Sdn. Bhd., Mr Billy (Chief Operating Officer) and Dr Teh (Digital Health Officer) identified the absence of structured, real-time decision guidance as a major barrier to rural healthcare delivery; although Malaysia's CPGs are publicly available, they are not accessible in a practical, point-of-care format suitable for time-pressured environments. A follow-up interview on 29 October 2025 with Dr Teh confirmed that decision-making in rural and district clinics depends largely on individual experience and manual documentation, consistent with prior studies of rural primary care [8].

Recent advances in large language models (LLMs) suggest a path to closing both gaps, but general-purpose models cannot be trusted directly in a clinical setting. Independent benchmarks show that medical LLMs reproduce false clinical information in a majority of adversarial cases, and that prompt-based safeguards reduce but never fully eliminate this behaviour [12]. Clinicians are accordingly reluctant to adopt systems whose reasoning they cannot inspect, repeatedly identifying transparency and explainability as preconditions for trust [13].

Yet retrieval alone does not make a language model safe. The naïve retrieval-augmented pattern — embed the query, pull the nearest guideline passages, and let the model write the answer — inherits the model's failure modes wherever the retrieved text is silent: it will still answer a question that belongs to no guideline, still miss a drug interaction the retrieved paragraph never names, and still present its reasoning as an opaque block the clinician cannot audit. The limit is architectural rather than a matter of model scale — across six leading models a planted false clinical fact was reproduced in 65.9% of cases (up to 83%), and a safety-oriented prompt reduced but never eliminated it [12]. The field's consensus response is that clinical reliability comes from *compound systems* that wrap the model in retrieval grounding, explicit scope control, and an independent verification layer — not from a larger model or a single retrieval step [17]. A clinically useful system must therefore be grounded in verified guidelines, cite its sources, recognise when a case falls outside its competence, and refuse to endorse unsafe recommendations — properties that depend on system architecture rather than model size alone.

In response, this project developed an Evidence-Based Clinical Practice Guidance System (ClearPath) that delivers real-time, guideline-grounded clinical advisory tailored to rural primary care. Built on a deterministic-first principle — deterministic wherever possible, generative only where genuine clinical reasoning is required — the system embeds explainable, source-cited guidance directly into everyday practice to reduce clinical uncertainty, support decision-making in complex scenarios, and promote consistent adherence to MOH and international clinical standards [9].

---

## 1.2 Problem Statements

Rural primary healthcare in Malaysia, particularly in the East Malaysian states of Sabah and Sarawak, faces a severe workforce crisis. Sabah alone faces a critical shortage of 4,526 doctors, with a doctor-to-population ratio of approximately 1:795 — far below national and WHO benchmarks [2], [5] — a disparity that has persisted for over five decades [1]. These workforce, knowledge, and safety pressures converge into a single condition that defines the rural consultation: **clinical decision isolation**. At the moment a decision must be made, the rural clinician is cut off from the three forms of support an urban colleague takes for granted — a senior to consult, the guideline itself, and a pharmacist to check the prescription.

**Cut off from a colleague.** With rural clinics frequently operating without a resident physician [4], clinicians face substantially greater diagnostic ambiguity than their urban counterparts, often managing complex or multimorbid cases without timely specialist input [7]. The cost is measurable: among complex cases referred for review, a second clinical assessment changes or refines the original diagnosis in up to 88% of cases [3]. Yet no structured, real-time second opinion is available at the point of care.

**Cut off from the guideline.** Although CPGs issued by the Malaysian Ministry of Health are intended to standardise evidence-based care, non-adherence rates reach as high as 39.3% [6]. With each CPG exceeding 100 pages and consultations averaging just 10.5 minutes, clinicians have neither the time nor the tools to retrieve and apply guideline recommendations in real time, defaulting instead to individual experience or early referral [8], [10]. Existing digital tools deepen rather than close this gap: general-purpose LLMs operate on global medical knowledge rather than locally validated Malaysian MOH CPGs and cannot explain or audit their reasoning [12], [13], while passive tools such as NotebookLM summarise documents without any clinical decision logic.

**Cut off from a pharmacist.** In clinics without an on-site pharmacist, no independent check guards the prescription. This matters because medication-related harm accounts for roughly half of all preventable harm in health care — an estimated US$42 billion per year globally [18] — and drug–drug interactions, allergy cross-reactivity, and organ-impairment dosing errors slip through unnoticed where no second reviewer is present. No existing point-of-care tool performs a structural safety audit against the patient's full medication profile.

Taken together, these three faces of isolation manifest as four cross-cutting failures of current rural care delivery: **clinical decision isolation** (no structured second opinion aligned to local CPGs), **ungoverned, non-local retrieval** (AI grounded in global rather than Malaysian-validated sources), **lack of auditable reasoning** (recommendations that cannot be verified against evidence), and **lack of executable output** (guidelines returned as unstructured prose rather than actionable care plans) — with **medication-safety vulnerability** running through all three [10], [11]. The absence of an integrated, CPG-grounded, and safety-enforcing clinical decision support system represents a critical infrastructure gap — one directly linked to inconsistent guideline adherence, increased documentation burden, and reduced care continuity in Malaysia's most underserved healthcare settings [8], [13].

---

## 1.3 Objectives

- To develop a unified, machine-interpretable knowledge base that centralises Malaysian Ministry of Health CPGs with ICD-11 clinical terminology, enabling real-time, scope-controlled retrieval grounded in locally validated guidelines rather than general medical knowledge.
- To deliver a transparent, auditable second opinion within the consultation window, with per-stage reasoning traces that support clinician trust, auditability, and accountability.
- To enforce medication safety through a dual-source critic that combines LLM pharmacological reasoning with a structured drug knowledge graph, blocking sign-off until all critical flags are acknowledged.
- To produce a structured, executable care plan carried longitudinally across patient visits, integrating decision support into routine clinical workflows to promote consistent, explainable, evidence-based practice.

---

## 1.4 Review on Existing Solutions

Recent advances in large language models (LLMs) have generated significant interest in their potential to support clinical reasoning, medical question answering, and guideline summarisation [11], [14]. Yet their application to structured, guideline-driven clinical decision support in rural primary care remains limited by persistent challenges in reliability, traceability, local alignment, and workflow integration [12], [13]. The three tools a Malaysian clinician could realistically reach for today — a general-purpose conversational LLM, a document-grounded research assistant, and a CPG-native clinical search tool — are reviewed below, each by its capability and its ceiling.

**General-purpose LLM (ChatGPT / GPT-4).** A general-purpose conversational LLM generates coherent, context-aware responses across clinical topics, including medication queries, symptom interpretation, and concept explanation [14], [16]. While useful for high-level reasoning, it is not designed to enforce adherence to jurisdiction-specific guidelines such as Malaysia's MOH CPGs. Responses are generated probabilistically and vary with prompt phrasing, with no built-in mechanism for grounding recommendations in authoritative local sources or standardised clinical codes; independent assurance testing shows such models reproduce planted false clinical facts at high rates, a behaviour that safety prompts reduce but never eliminate [12]. It is the fastest and most accessible option, and the least safe — unsuitable for direct clinical decision support where transparency, auditability, and regulatory alignment are required [13].

**NotebookLM.** NotebookLM takes a document-centric approach, allowing users to upload reference materials and query them, which reduces hallucination by restricting responses to user-provided content. However, its functionality is limited to information retrieval and summarisation rather than structured clinical decision-making. It lacks clinical reasoning logic, consistent terminology mapping to standards such as ICD-11, and the rule-aware validation needed to manage contraindications, comorbidities, and drug interactions. Without structured care-plan output or safety checking, NotebookLM functions as a passive reference tool, not an active decision-support system.

**Qmed AskCPG.** Qmed AskCPG is CPG-native and cites guidelines at page granularity, making it the closest existing analogue to a grounded clinical assistant. Its ceilings are nonetheless structural: it draws on a single grounding source, so a drug interaction is surfaced only if the retrieved paragraph happens to name the pair; its reasoning is opaque, presenting a verdict without the diagnostic shortlist or routing path behind it; it returns long-form prose the clinician must re-read and mentally extract under time pressure; it performs no independent safety audit against the patient's existing medication profile; and it carries no patient object across visits.

**Med-PaLM 2 (noted, excluded from like-for-like comparison).** Med-PaLM 2 demonstrates expert-level performance on medical question-answering benchmarks and clinical reasoning tasks [15], but it is evaluated in controlled research settings and is not openly deployable for regional, CPG-grounded, real-time point-of-care use; its substantial computational requirements also make it impractical for resource-constrained rural environments [11]. It is therefore noted as a research baseline but excluded from the deployable like-for-like comparison above.

**Where ClearPath differs.** All three deployable tools can cite a source — that capability is table stakes, not a differentiator. None can decline an out-of-scope case, produce a knowledge-graph-sourced safety flag from the patient's existing medications, or expose an auditable per-stage reasoning trace. ClearPath addresses these shortcomings through a hybrid agentic Retrieval-Augmented Generation (RAG) architecture [9] that grounds every recommendation exclusively in validated Malaysian MOH CPGs indexed via ICD-11 terminology, provides per-stage reasoning traces for full auditability, enforces medication safety through a dual-source critic combining LLM reasoning with a structured drug knowledge graph, and delivers structured, executable care plans within the consultation window. Unlike the systems reviewed, ClearPath is designed specifically for the operational realities of rural Malaysian primary care — and the capabilities that separate it are structural, reachable only by rebuilding a pure-retrieval pipeline, not by reprompting it [11], [13].

---

<!--
Reference notes (checked against the actual RM-1 reference list, refs [1]-[16]):

- [12] MISMATCH IN RM-1: it is titled "Sociodemographic biases in medical decision-making
  by large language models," but its URL (nature.com/articles/s43856-025-01021-3) is in fact
  the Omar et al. adversarial-hallucination paper — "Multi-model assurance analysis showing
  LLMs are highly vulnerable to adversarial hallucination attacks during clinical decision
  support," Communications Medicine 2025;5:330 — which is the actual source of the "65.9%
  (up to 83%)" figure used in 1.1. ACTION: correct the [12] TITLE to the adversarial-
  hallucination paper so title and URL agree. 1.1 and 1.4 above are written to use [12]
  consistently as that paper (the sociodemographic-bias wording was removed from 1.4).
- [9] Lewis et al., RAG (NeurIPS 2020) — supports "hybrid agentic RAG" in 1.4. OK as-is.
- [11] Sutton et al., npj Digital Medicine CDSS overview — supports 1.2 / 1.4. OK as-is.

New references to add to the RM-1 list:
[17] Zaharia M, Khattab O, et al. "The Shift from Models to Compound AI Systems," BAIR
     (Berkeley) blog, 2024. https://bair.berkeley.edu/blog/2024/02/18/compound-ai-systems/
     (Blog source — acceptable as the origin of the term; swap for a peer-reviewed
     RAG/compound-AI survey if a non-blog citation is preferred.)
[18] WHO. "Medication Without Harm" — 3rd Global Patient Safety Challenge
     (~50% of preventable harm; ~US$42 B/yr). https://www.who.int/initiatives/medication-without-harm
-->
