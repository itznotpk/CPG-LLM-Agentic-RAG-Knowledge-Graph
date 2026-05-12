# MHNexus CPG LLM — Validation Plan

> Final-report validation strategy covering **Technical Validation** (measurable system metrics) and **Stakeholder Validation** (clinician usability + clinical trust).

---

## 1. Why both kinds of validation

| Dimension | Question it answers | Output for the report |
|---|---|---|
| **Technical** | "Does the system retrieve and reason correctly?" | Numerical scorecard (accuracy, recall, latency) |
| **Stakeholder** | "Would a real doctor actually use this in a klinik kesihatan?" | Qualitative themes + Likert/SUS/TAM scores |

Strong projects need both — technical numbers alone don't prove clinical usefulness, and stakeholder praise alone doesn't prove correctness.

---

## 2. Technical Validation

Our architecture has distinct layers, and each must be tested on its **own** before end-to-end evaluation. Testing only the final answer masks where errors come from.

### 2.1 Architecture layers → what to measure where

```
[User query]
   │
   ▼
[Query rewriting / agent planner]      ── Layer A
   │
   ▼
[Retrieval (vector + keyword/BM25)]    ── Layer B  ← most important
   │
   ▼
[Re-ranker / context filter]           ── Layer C
   │
   ▼
[LLM generation w/ citations]          ── Layer D
   │
   ▼
[End-to-end agentic workflow]          ── Layer E (DDx, tools, multi-hop)
```

### 2.2 Layer-by-layer metrics

#### Layer B — Retrieval (the make-or-break layer for RAG)

Build a **gold-standard evaluation set**: 100–200 clinical questions, each manually mapped to the *exact CPG passages* that should be retrieved.

Sources of questions:
- Real MOH CPG documents (paraphrase section headings into clinician-style questions)
- Past-year MMed / MRCP / family-medicine exam vignettes
- Common rural-clinic presentations (hypertension, T2DM, dengue, TB, antenatal care)

Metrics:

| Metric | Formula | Target |
|---|---|---|
| **Recall@k** (k=5, 10) | fraction of gold passages appearing in top-k | ≥ 0.85 @ k=10 |
| **Precision@k** | relevant retrieved / k | ≥ 0.5 @ k=5 |
| **MRR** (Mean Reciprocal Rank) | 1 / rank of first relevant doc | ≥ 0.7 |
| **nDCG@10** | rank-weighted relevance | ≥ 0.75 |
| **Hit Rate@k** | % queries with ≥1 relevant in top-k | ≥ 0.95 |

Tools: `ragas`, `trulens`, or a hand-rolled scorer over your gold set. Report a table comparing **vector-only vs hybrid (BM25 + vector) vs hybrid + re-ranker** — this directly justifies design decisions.

#### Layer C — Re-ranker

Compare top-k *before* and *after* re-ranking on the same gold set. Show nDCG lift.

#### Layer D — Generation faithfulness

Even with perfect retrieval, the LLM can hallucinate. Measure:

| Metric | How |
|---|---|
| **Faithfulness / Groundedness** | % of answer sentences supported by retrieved context (LLM-as-judge via Ragas, or manual review of 50 answers) |
| **Citation accuracy** | % of cited passages that actually contain the claimed fact (manual, 50 samples) |
| **Answer relevancy** | Does the answer address the question? (Ragas `answer_relevancy`) |
| **Hallucination rate** | % of answers with ≥1 unsupported clinical claim |

Target: faithfulness ≥ 0.90, hallucination rate ≤ 5%.

#### Layer E — End-to-end agentic / clinical correctness

Build a **clinical Q&A benchmark** (50–100 items) where each item has a known-correct answer from the CPG:

- Single-fact lookup ("First-line antihypertensive in T2DM with proteinuria?")
- Dose / threshold questions ("HbA1c target for elderly frail patient?")
- Workflow questions ("When to refer suspected TB to chest clinic?")
- Differential diagnosis vignettes (DDx module)

Score with two judges (you + 1 clinician if possible) on a 0/1 or 0–2 rubric:
- **Exact correctness** (matches CPG)
- **Clinical safety** (no dangerous advice even if not exact)
- **Completeness** (mentions red flags, referral criteria)

#### Layer A — Query rewriting / planner (if you use an agent)

- % of multi-hop queries decomposed correctly
- Tool-selection accuracy (did the agent pick the right tool: search vs DDx vs calculator?)

### 2.3 Non-accuracy metrics (still required for the report)

| Metric | Why it matters in rural deployment |
|---|---|
| **End-to-end latency** (p50, p95) | Klinik kesihatan internet is slow — target p95 < 8s |
| **Token / cost per query** | Sustainability for MOH |
| **Robustness to typos / Manglish / BM mixing** | Real clinician input isn't clean English |
| **Refusal correctness** | Does it refuse / escalate out-of-scope queries? |

### 2.4 Comparative baselines (this is what examiners love)

Run the same gold set through:
1. Vanilla GPT/Claude (no RAG)
2. Naive RAG (vector-only, no agent)
3. **Your full system**

Show a bar chart of faithfulness + recall — the delta justifies the entire project.

---

## 3. Stakeholder Validation

### 3.1 Who to recruit

| Group | Why this group | Target n |
|---|---|---|
| **Urban MO / specialists (HKL, UMMC, HUSM)** | Gold-standard clinical accuracy check | 3–5 |
| **Klinik kesihatan MOs (Sabah / Sarawak rural)** | True target users — limited specialist access, intermittent internet | 5–8 |
| **Family Medicine Specialists (FMS)** | They *write* and *teach* CPGs | 2–3 |
| **Medical students / housemen** | Edge user group — adoption signal | 5–10 |
| **MOH / KKM digital health rep** (stretch) | Policy-level buy-in for the report | 1 |

Rural representation is the differentiator — flag it explicitly in your report as addressing a real equity gap.

### 3.2 What to ask them to do

**Session structure (~45 min per clinician, can be remote via Zoom):**

1. **Pre-survey (5 min)** — demographics, current CPG-lookup habits, comfort with AI tools.
2. **Think-aloud task scenarios (25 min)** — give 3–4 realistic vignettes:
   - *"55F, BP 162/98, T2DM, eGFR 45 — what's your next step per Malaysian CPG?"*
   - *"Antenatal mother, GDM screening positive — what protocol?"*
   - *"Suspected dengue with warning signs in a 12yo — admit or observe?"*
   - One **deliberately out-of-CPG-scope** question to test refusal behaviour.
   They use the tool live; you observe but don't help.
3. **Post-task questionnaire (10 min)** — see 3.3 below.
4. **Semi-structured interview (5–10 min)** — open-ended.

### 3.3 What to measure (quantitative instruments)

Use **validated** instruments so your numbers are defensible in a thesis:

| Instrument | What it measures | Output |
|---|---|---|
| **SUS** (System Usability Scale, 10 items) | Usability | Score /100; >68 = above average |
| **TAM** (Technology Acceptance Model) | Perceived usefulness + ease of use → intent to adopt | 5-point Likert per construct |
| **NASA-TLX** (short form) | Cognitive workload of using the tool vs flipping a PDF | Workload score |
| **Trust in Automation scale** (Jian et al.) | Clinical trust — critical for medical AI | 7-item Likert |
| **Custom clinical rubric** (you design) | Per-answer rating: *Clinically correct? Safe? Actionable?* on 5-point | Mean + IRR (inter-rater) |

### 3.4 What to ask in the interview (qualitative — high signal)

Open-ended, recorded with consent, transcribed, then **thematic analysis** (Braun & Clarke 6-step) for the report:

1. *"Walk me through when you'd actually use this in clinic — and when you wouldn't."*
2. *"What did the tool get wrong? Did you notice, or would you have trusted it?"* ← surfaces hallucination risk
3. *"In your klinik in Sabah/Sarawak, what would block you from using this?"* (bandwidth, language, MOH approval, electricity, device)
4. *"Did the citations help you trust the answer? Did you click through?"*
5. *"Would you rather have this, the printed CPG, or ask a specialist on WhatsApp?"* ← competitive baseline
6. *"What's missing? What should v2 do?"*
7. *"If MOH offered this tomorrow, would you use it? Why / why not?"*

### 3.5 What you'll *gain* from rural-clinician feedback (justify it in the report)

- **Generalisability evidence** — proves the tool isn't only for tertiary hospitals.
- **Latency / offline requirements** — real bandwidth constraints you can't simulate.
- **Language coverage gaps** — Manglish, BM, code-switching during consults.
- **Workflow fit** — they may need it on mobile, not desktop; during consult vs after.
- **Safety surface** — rural MOs often manage *broader* scope without specialist backup, so an unsafe answer there has higher consequence. Their scrutiny is the strongest safety signal.
- **Equity narrative** — strengthens the social-impact section of your final report.

### 3.6 Practical recruitment tips

- Approach via **MMA (Malaysian Medical Association)**, **Family Medicine Specialists Association**, faculty contacts (UM, USM, UMS, UNIMAS).
- Offer a small token (e.g., RM30 e-wallet) — ethics-compliant, increases follow-through.
- Submit for **IRB / JEPeM / MREC ethics approval** *before* collecting data — required for any thesis using human participants. Start this 6–8 weeks early.
- Get signed **informed consent** + data-handling statement (no PHI in test prompts).

---

## 4. Reporting Template (for the final report)

Structure your validation chapter as:

1. **Evaluation methodology** (this document, condensed)
2. **Technical results**
   - Retrieval table (Recall/MRR/nDCG across 3 system variants)
   - Generation faithfulness chart
   - Latency / cost
   - End-to-end clinical Q&A accuracy
3. **Stakeholder results**
   - Participant demographics table (urban vs rural split)
   - SUS / TAM / Trust scores with mean ± SD
   - Per-vignette clinician correctness rating
   - Thematic analysis: 4–6 themes with verbatim quotes
4. **Triangulation** — where technical metrics agree/disagree with clinician perception (e.g., "faithfulness was 92% but rural MOs flagged 3 unsafe answers we'd scored as correct — discussion of why").
5. **Limitations** (small n, single-site, English-only, etc. — naming these strengthens the report).
6. **Recommendations for v2**.

---

## 5. Suggested Timeline (8 weeks before submission)

| Week | Activity |
|---|---|
| 1 | Build gold-standard retrieval + Q&A sets; submit ethics application |
| 2 | Run technical eval (Layers B, C, D); iterate on retrieval if Recall@10 < 0.8 |
| 3 | Lock system; freeze for stakeholder testing; finalise survey instruments |
| 4–5 | Recruit + run urban clinician sessions (5) |
| 5–6 | Recruit + run rural KK clinician sessions (5–8) — likely remote |
| 7 | Transcribe, code thematic analysis, compute SUS/TAM |
| 8 | Write validation chapter; produce charts |

---

## 6. Minimum Viable Validation (if time is tight)

If full plan isn't feasible, the **defensible minimum** for the report is:

- 50-question retrieval gold set → Recall@10 + MRR
- 30-question clinical Q&A → faithfulness + correctness (manual)
- One baseline comparison (naive RAG vs full system)
- **3 clinicians** (1 urban specialist, 2 rural MOs) × SUS + 5 interview questions

This still gives you both axes of validation, just with smaller n — and you call that out honestly as a limitation.
