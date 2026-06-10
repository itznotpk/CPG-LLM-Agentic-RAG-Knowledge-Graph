# CHAPTER 3: DETAILED DESIGN

## 3.1 Overall System Architecture

ClearPath was implemented as an integrated, cloud-native clinical decision-support system that
produces an audited, executable care plan from a single patient consultation, with the explicit
constraint that the entire process must complete inside a ten-minute consultation window. Rather
than routing a clinical question through a single large language model, the system was architected
as a hybrid deterministic-agentic pipeline. Every routing, retrieval, and verification decision
that could be expressed as a deterministic rule, a vector computation, or a graph query was
implemented as such, and a language model was reserved only for the steps that require genuine
clinical reasoning. This principle, which we summarise as "deterministic wherever possible,
generative only where necessary", governed the design of every stage, because it is the property
that makes the system's output auditable, reproducible, and safe to operate in a setting where no
senior clinician or pharmacist is present to catch an error.

The pipeline consists of seven primary stages that operate as a continuous data-processing chain.
Each stage transforms one typed, validated object into the next, and each stage streams its
progress to the clinician in real time. The system-level architecture and the high-level data flow
between the stages are shown in Fig. 3.1, which serves as the master reference for the detailed
specifications that follow in this chapter.

> **[FIGURE 3.1: System-Level Architecture of the ClearPath System.]**
> *Insert the full-width architecture diagram by rendering the Mermaid source in §3.1.1
> (diagram D-ARCH) at high export scale. The figure names the seven stage components (Intake Module,
> Differential Diagnosis Engine, Routing Module, Retrieval Engine, KG Injection Module, Synthesis
> Engine, Safety Critic, and the Clinician Delivery Surface), with the two grounding stores (the
> pgvector Vector Store and the Neo4j Knowledge Graph) drawn as side cylinders and their data
> dependencies drawn as dashed edges.*

As shown, the system operates as a directed pipeline in which each stage carries a single,
well-defined responsibility:

- **Stage 1, Clinical Intake (deterministic).** The process begins at the clinician's workspace,
  where patient demographics, history, current medications, allergies, and vital signs (captured
  either manually or contactlessly through remote photoplethysmography) are assembled into one
  typed `PatientCase` object. This object is the canonical input consumed by every downstream
  stage.
- **Stage 2, Differential Diagnosis (LLM-assisted).** The patient's symptom narrative is
  distilled, embedded, and matched against the World Health Organization ICD-11 catalogue of 3,914
  diagnosis codes through a parallel vector search, then re-ranked by a context-aware language
  model into a clinician-approvable shortlist of named diagnoses.
- **Stage 3, Deterministic Scoped Routing (deterministic).** Each confirmed ICD-11 code is
  resolved to the set of Malaysian Ministry of Health (MoH) Clinical Practice Guidelines (CPGs)
  that govern it, through a deterministic multi-tier cascade. When no guideline applies, the
  system declares the case out of scope and returns no plan rather than fabricating one.
- **Stage 4, Evidence-Graded Scoped Retrieval (LLM-assisted).** A language model writes focused
  search queries, which are executed against the vector store strictly scoped to the routed CPGs
  so that no evidence from an unrelated guideline can enter the result set. Hierarchical section
  context and cross-referenced passages are retrieved alongside each matched chunk.
- **Stage 4.5, Pre-Synthesis Knowledge-Graph Injection (deterministic).** A Neo4j knowledge graph
  is queried for the structural "prefer this drug, avoid that drug" relationships that the
  retrieved prose may not state explicitly.
- **Stage 5, Care Plan Synthesis (LLM-assisted).** A language model assembles the patient data,
  the retrieved evidence, and the graph constraints into a Pydantic-validated, eight-section
  executable care plan, which then passes through an eight-layer deterministic validator chain.
- **Stage 6, Hybrid Adversarial Safety Critic (hybrid).** Two independent graders, an LLM
  clinical-pharmacist critic and a deterministic Neo4j plan-verifier, audit the finished plan in
  parallel, and either grader can block sign-off.

The audited plan and its safety report are then streamed to the clinician over a single
Server-Sent Events (SSE) contract that is shared identically by the React Doctor UI and the
terminal CLI. After review, the clinician may override and re-synthesise, sign off, and optionally
deliver a localized PDF to the patient (Stage 7).

### 3.1.1 The deterministic and agentic split

A defining characteristic of the architecture, and one that distinguishes it from a conventional
retrieval-augmented-generation (RAG) chatbot, is the deliberate and audited separation between
deterministic steps and language-model steps. Only four of the core pipeline stages issue a
language-model call; the remainder are rule-based, vector-based, or graph-based and are therefore
fully reproducible. Table 3.1 records this split explicitly, because the integrity of the system
depends on it being stated accurately rather than overstated.

**Table 3.1: Per-stage deterministic versus LLM classification (verified against source).**

| Stage | Job | Engine | LLM call |
|---|---|---|---|
| 1, Intake | Assemble `PatientCase`, derive BMI | Typed assembly, rPPG/manual vitals | No |
| 2, DDx | Symptom to ICD-11 differential | pgvector over 3,914 codes, plus LLM rerank | Yes (rerank) |
| 3, Route | Scope to verified CPGs | Deterministic 9-tier cascade | No |
| 4, Retrieve | Pull evidence-graded chunks | LLM query-gen, then scoped pgvector | Yes (query-gen) |
| 4.5, KG inject | "prefer Y, avoid X" edges | Neo4j Cypher | No |
| 5, Synthesize | 8-section care plan | LLM, then post-synthesis validators | Yes (synthesis) |
| 6, Critic | Independent safety audit | LLM pharmacist and Neo4j verifier | Yes (LLM arm) |

None of these LLM steps is an autonomous agent in the strict sense; there is no self-directed tool
use and no open-ended looping. Each is a single-pass language-model call embedded inside a
deterministic orchestration. The component that most closely matches the definition of an agent is
the Stage 6 safety critic, which independently reviews the finished plan and holds veto power over
sign-off, following the established critic pattern. This distinction is maintained consistently
throughout the report so that the system is neither under-described nor over-claimed.

This split also underpins the system's transparency design. Because each stage is a discrete,
typed step rather than one opaque generation, every intermediate decision can be exposed as part of
an auditable chain of thought, which is documented in detail in §3.11.4.

> **[FIGURE 3.2: End-to-End Consultation Process Flow.]**
> *Insert Mermaid diagram D-FLOW (§3.1.2). This is the compact happy-path process view together with
> the two branch points, the out-of-scope stop and the safety block, suitable as a smaller inset
> beside Fig. 3.1.*

### 3.1.2 Diagram sources for §3.1

The two diagrams are reproduced as renderable Mermaid sources below. They render at
<https://mermaid.live>; teal denotes an LLM reasoning step, cyan a deterministic step, and amber
the safety-critic agent.

**Diagram D-ARCH, system-level architecture by component (Fig. 3.1):**

```mermaid
flowchart TB
    subgraph S1["Stage 1 · Intake Module"]
        direction TB
        A1["PatientCase Assembler"]
        A2["rPPG + STT Capture"]
        A3["Derived BMI"]
    end

    subgraph S2["Stage 2 · Differential Diagnosis Engine"]
        direction TB
        B1["pgvector ICD-11 Search"]
        B2["Context-Aware LLM Re-ranker"]
    end

    subgraph S3["Stage 3 · Routing Module"]
        direction TB
        C1["Deterministic D1–D6 Scope Cascade"]
    end

    subgraph S4["Stage 4 · Retrieval Engine"]
        direction TB
        D1["LLM Query Generator"]
        D2["Scoped pgvector Search"]
        D3["Hierarchical Prefetch + Cross-Refs"]
    end

    subgraph S45["Stage 4.5 · KG Injection Module"]
        direction TB
        E1["Neo4j Cypher Lookup"]
        E2["Prefer / Avoid Edges"]
    end

    subgraph S5["Stage 5 · Synthesis Engine"]
        direction TB
        F1["LLM Care-Plan Planner"]
        F2["Post-Synthesis Validators"]
    end

    subgraph S6["Stage 6 · Safety Critic"]
        direction TB
        G1["LLM Pharmacist Critic"]
        G2["Neo4j KG Verifier"]
    end

    subgraph S7["Stage 7 · Clinician Delivery Surface"]
        direction TB
        H1["React Doctor UI + CLI"]
        H2["SSE Stream"]
        H3["PDF Delivery"]
    end

    PG[("Vector Store<br/>Postgres + pgvector · Neon")]
    KG[("Knowledge Graph<br/>Neo4j Aura")]

    S1 --> S2 --> S3 --> S4 --> S45 --> S5 --> S6 --> S7
    PG -. embeddings .-> S2
    PG -. scope embedding .-> S3
    PG -. scoped chunks .-> S4
    KG -. prefer / avoid .-> S45
    KG -. structural verify .-> S6
    S7 -. override to re-synthesis .-> S5

    classDef agent fill:#f0fdfa,stroke:#0d9488,color:#134e4a;
    classDef det fill:#ecfeff,stroke:#0891b2,color:#164e63;
    classDef crit fill:#fffbeb,stroke:#f59e0b,color:#92400e;
    classDef store fill:#f8fafc,stroke:#64748b,color:#334155;
    class A1,A2,A3,B1,C1,D2,D3,E1,E2,F2,H1,H2,H3 det;
    class B2,D1,F1 agent;
    class G1,G2 crit;
    class PG,KG store;
```

**Diagram D-FLOW, pipeline overview with the two distinctive branches (Fig. 3.2):**

```mermaid
flowchart TD
    A([Patient Intake]) --> B["DDx · ICD-11 differential"]
    B --> C{"Route · D1–D6 cascade"}
    C -- out of scope --> Z([Graceful stop · no fabricated plan])
    C -- in scope --> D["Retrieve · LLM query-gen + scoped CPG chunks"]
    D --> E["KG inject · prefer / avoid edges"]
    E --> F["Synthesize · 8-section care plan"]
    F --> G{{"Safety Critic · LLM and KG in parallel"}}
    G -- any CRITICAL/MAJOR --> H[/BLOCK sign-off · surface flags/]
    G -- safe_to_proceed --> I[Stream to clinician UI]
    I --> J{Clinician override?}
    J -- yes --> F
    J -- no --> K([Sign off · optional PDF delivery])

    classDef agent fill:#f0fdfa,stroke:#0d9488,color:#134e4a;
    classDef det fill:#ecfeff,stroke:#0891b2,color:#164e63;
    classDef stop fill:#fef2f2,stroke:#dc2626,color:#991b1b;
    classDef ok fill:#f0fdfa,stroke:#0d9488,color:#134e4a;
    class B,D,F agent;
    class C,E det;
    class Z,H stop;
    class I,K ok;
```

---

## 3.2 Technology Stack

This section records the implemented technology stack; the rationale for choosing each database and
framework over its alternatives is given in the concept-selection analysis of Chapter 2 and is not
repeated here.

The system is a three-tier architecture unified by one streaming contract. The reasoning backend
(Python 3.11, FastAPI) exposes the entire pipeline over a single Server-Sent Events (SSE) stream,
consumed identically by the React clinician frontend and a terminal CLI (`clinical_cli.py`) for
headless end-to-end runs. Figure 3.3 summarises the full stack as three layers — the application and
interface, the data and knowledge stores (vector store, knowledge graph, and application store), and
the AI model services that supply the system's reasoning and embeddings. All vector embeddings are
produced by AWS Bedrock Titan at 1536 dimensions; the two grounding stores are detailed in §3.2.2 and
the application store in §3.11.6.

> **[FIGURE 3.3: Technology-stack chevron — three layers.]**
> *A three-chevron strip read left-to-right from the clinician-facing surface to the AI core, each
> chevron a labelled layer with its logos and a one-line role label:*
> - ***Layer 1 — Application & Interface:** Python and FastAPI (backend API) · React, Tailwind, and
>   Vite (the Doctor UI).*
> - ***Layer 2 — Data & Knowledge Stores:** PostgreSQL with pgvector on Neon (vector store) · Neo4j
>   Aura through Graphiti (knowledge graph) · Supabase (application store).*
> - ***Layer 3 — AI Model Services:** Google Vertex AI serving Gemini 2.5 Flash (fast interactive
>   steps) · Xiaomi MiMo v2.5 Pro (care-plan synthesis) · AWS Bedrock serving Titan Text v1
>   embeddings and Claude Haiku 4.5 (offline graph build). This layer mirrors the model tiering of
>   Table 3.2.*

### 3.2.1 Language-model composition: spending reasoning where it matters

ClearPath was implemented as a multi-model system, and the governing principle was to spend latency,
cost, and reasoning capacity only on the steps where they change output quality. Most pipeline steps
are bounded extraction, classification, or query-rewriting tasks that run inside the interactive
consultation, so they were assigned a fast, low-cost model in order to protect the ten-minute
consultation budget. The single step that carries the deepest reasoning load, care-plan synthesis,
was assigned a dedicated reasoning model, and the one-time offline graph build was assigned a cheap
model because it never runs in the live path. Table 3.2 records this tiering and the rationale for
each assignment.

**Table 3.2: Model assignment by tier (verified against `.env` and `providers.py`).**

| Tier | Stages / steps | Model | Why this tier |
|---|---|---|---|
| Fast (interactive) | Stage 2 symptom extraction and hypothesis generation; Stage 2 DDx rerank; Stage 4 query rewriting; Stage 6 LLM critic; prep brief; STT-to-SOAP summary | Gemini 2.5 Flash (1M context) | • Latency-sensitive, runs in the live consult<br/>• Bounded extraction or judgement, no heavy reasoning needed<br/>• Light "thinking" tokens only on rerank and critic<br/>• Critic kept off the synthesis model, so no self-grading |
| Reasoning (quality-critical) | Stage 5 care-plan synthesis; prior-visit summariser | MiMo v2.5 Pro (128k context) | • Deepest reasoning, longest evidence assembly<br/>• Output quality matters most here<br/>• Large context holds evidence + KG edges + patient state |
| Offline (one-time) | CPG triple extraction during ingestion | Claude Haiku 4.5 | • High-volume per-chunk extraction; cost scales with corpus size<br/>• §3.3.1 guards (not the model) catch false edges, so Sonnet/Opus adds cost for no gain<br/>• Offline on Bedrock |
| Embeddings | All vector representations (codes, chunks, scope) | Bedrock Titan Text v1 (1536-dim) | • Defines the shared vector space (codes, chunks, scope); all must use one model and dimension<br/>• 1536-dim v1 pinned to pgvector + ivfflat; switching (e.g. Titan v2) forces a full re-embed and re-index<br/>• Client cached against cold-start cost |

### 3.2.2 Data-store architecture and the dual-grounding philosophy

A deliberate and defining design decision was to ground the system's reasoning in two complementary
stores rather than one. This dual-grounding split is not incidental infrastructure; it is a core
architectural decision, because each store answers a different kind of clinical question that the
other cannot answer on its own. A third store, Supabase, holds the application's operational state,
but it is not a reasoning store and is owned by the frontend, so it is introduced here only briefly
and documented alongside the Doctor UI in §3.11.6.

- **Vector store, PostgreSQL with pgvector (Neon).** This store answers questions of semantic
  similarity, such as which ICD-11 code is closest to a given symptom narrative and which guideline
  passage is most relevant to a given query. It holds the 1536-dimension Titan embeddings of all
  3,914 ICD-11 codes, every CPG chunk, and each guideline's `scope_embedding`. It is well suited to
  fuzzy, meaning-based matching, but it is blind to structured relationships: it can establish that
  two passages read similarly, not that two drugs interact.
- **Knowledge graph, Neo4j Aura (through Graphiti).** This store answers questions of structural
  relationship, such as whether a drug is contraindicated in a condition, what monitoring a drug
  requires, and what the first-line therapy for a diagnosis is. The graph is a biomedical ontology
  of roughly 13,800 nodes across about eleven entity types (the largest being `Condition`,
  `Procedure`, `Drug` at approximately 1,630 nodes, `AdverseEvent`, `DiagnosticTool`, `RiskFactor`,
  `Dosage`, `PatientProfile`, and `Specialty`) connected by roughly 18,700 typed edges across about
  fifteen relation types, shown in Fig. 3.3c. The runtime pipeline queries the safety-relevant
  subset of these relations, principally `CONTRAINDICATED_WITH` (approximately 980 edges),
  `INTERACTS_WITH` (approximately 290), `REQUIRES_MONITORING`, `REQUIRES_REFERRAL`, and the positive
  prescribing edges (`FIRST_LINE_FOR`, `RECOMMENDED_FOR`, and similar). A graph traversal can
  therefore surface a hazard, such as a teratogen on the patient's current medication list, that no
  retrieved passage happens to mention, which is the gap a vector-only system cannot close.
- **Application store, Supabase (Postgres).** Held separately from both grounding stores, this
  contains the operational state of the clinic: clinician authentication, patient records,
  consultations, vitals history, prior-visit summaries, generated PDFs, and feedback signals. It is
  owned by the frontend (the FastAPI backend never reads it, with the single exception of the
  background delivery worker) and is documented with the Doctor UI in §3.11.6.

The resulting design can be stated as: vectors for semantic recall, a graph for structural safety,
and a separate operational database for everything stateful. The two grounding stores are built
offline (§3.3) and treated as read-only at consultation time, while the application store is read
and written during a live consultation. This dual-grounding design is what makes the dual-source
safety critic of §3.10 possible: the LLM arm reasons over the text retrieved from the vector store,
the KG arm reasons over the edges held in the graph store, and because the two arms fail in
different ways, a hazard that is invisible to one is still caught by the other.

Each field within these schemas is provisioned to serve a specific stage of the reasoning pipeline.
Within the document store, `documents.icd11_scope` constitutes the array against which Stage 3
routing matches a predicted ICD-11 code, whereas `documents.scope_embedding` provides the semantic
fallback invoked when no exact code is matched. Within the chunk store, the `chunks.embedding`
column, a 1536-dimension vector indexed with IVFFlat for cosine search, serves as the shared
retrieval surface for both Stage 2 differential diagnosis and Stage 4 evidence retrieval; the
`chunks.chunk_level` field, which encodes the heading tier (`h1`–`h3` or `h1_leaf`), together with
the `chunks.parent_chunk_id` self-reference, enables Stage 4 to retrieve a precise leaf passage and
subsequently widen to its parent section for additional context. Within the knowledge graph, the
`CONTRAINDICATED_WITH` and `INTERACTS_WITH` edges are consumed at two distinct stages: by the Stage
4.5 knowledge-graph injection, which supplies prefer/avoid guidance to synthesis, and by the Stage 6
safety critic, which verifies the finished plan structurally. As these edges are derived from
clinical-guideline prose rather than from a curated pharmacological database, their coverage is
necessarily bounded by the relationships the guidelines explicitly state. Each schema therefore
constitutes the formal contract between a grounding store and the stages that consume it.

The schema of the vector store is shown in Fig. 3.3b, and a safety subgraph of the knowledge graph
in Fig. 3.3c. The knowledge-graph edges are not bare links: each one carries its own provenance,
namely the evidence sentence it was extracted from, the source CPG document and chunk, a severity,
and, where the contraindication is conditional, a structured threshold (for example, contraindicated
when AF duration exceeds seven days). Fig. 3.3d shows this edge-level metadata, which is what makes a
knowledge-graph-sourced safety flag auditable back to the exact CPG sentence that produced it.

> **[FIGURE 3.3b: Vector-store schema (PostgreSQL with pgvector, Neon).]**
> *Insert an entity-relationship diagram of the three grounding tables `documents`
> (`icd11_scope`, `scope_embedding`), `chunks` (chunk text, embedding, section hierarchy,
> cross-refs), and `icd11_codes` (code, title, parent_code, embedding). Generate it as a real
> diagram, not a screenshot, with these steps:*
> 1. *Export the schema DDL of only the relevant tables:*
>    `pg_dump --schema-only --no-owner -t documents -t chunks -t icd11_codes "$env:DATABASE_URL" > pgvector_schema.sql`
> 2. *Open <https://dbdiagram.io>, choose **Import → PostgreSQL**, and paste `pgvector_schema.sql`.*
> 3. *Export the rendered ER diagram as PNG or PDF.*
> *Alternative (GUI): connect DBeaver to `DATABASE_URL`, select the three tables, right-click,
> "Generate ER Diagram", and export. The `vector` columns will appear as a `USER-DEFINED` type,
> which is expected.*

> **[FIGURE 3.3c: Knowledge-graph safety subgraph (Neo4j Aura, Warfarin example).]**
> *Insert the Neo4j screenshot of a single-drug ego network (Query 3 in
> `docs/kg_figure_queries.cypher`, run on Warfarin), showing the safety-relevant edges
> `CONTRAINDICATED_WITH`, `REQUIRES_MONITORING`, and `CAUSES` radiating from one drug. Tidy the
> layout, dismiss any duplicate condition nodes, and export PNG or SVG from the result panel's
> download icon.*

> **[FIGURE 3.3d: Knowledge-graph edge provenance (Neo4j Aura).]**
> *Insert the Neo4j screenshot of a selected `CONTRAINDICATED_WITH` edge with its property panel
> open, showing that each edge carries its evidence sentence (`evidence`), CPG citation
> (`source_document`, `cpg_chunk_id`), `severity`, and a structured conditional threshold
> (`threshold_param`, `threshold_op`, `threshold_value`, `threshold_unit`). Click any edge in the
> graph view to open this panel.*

---

## 3.3 Data Foundation and CPG Ingestion Pipeline

Before any consultation can be served, two grounding stores have to be built offline: the vector
store (ICD-11 codes and CPG passage embeddings, in pgvector) and the knowledge graph (drug,
condition, and parameter relationships, in Neo4j). The live pipeline only reads these stores; it
never writes to them. This section documents how a static MoH CPG PDF, often exceeding one hundred
pages, was transformed into queryable, structured knowledge.

> **[FIGURE 3.4: CPG ingestion pipeline.]**
> *Insert Mermaid diagram D-INGEST (below). This is the project's methodology figure, the
> software-system equivalent of a hardware build diagram.*

The corpus currently comprises approximately 30 Malaysian MoH Clinical Practice Guidelines spanning
the cardiovascular, metabolic, oncological, obstetric, and related domains. Each guideline was
processed through the following build sequence (`backend/ingestion/`), which combines deterministic
steps with one offline LLM extraction step:

1. **Markdown conversion.** The source PDF was converted to structured markdown using an isolated
   `docling` toolchain, preserving the heading hierarchy (H1 to H2 to H3) that later powers
   contextual retrieval.
2. **Hierarchical chunking (`chunker.py`).** The markdown was split into retrieval chunks that
   retain their position in the section tree, their cross-references (`§X.Y` anchors), and their
   metadata (evidence grade, and category drawn from a 13-value controlled vocabulary).
3. **Embedding (`ingest.py` to Bedrock Titan).** Each chunk was embedded to a 1536-dimension vector
   and written to pgvector under an ivfflat index.
4. **ICD-11 scope wiring.** Each guideline row in the `documents` table carries an `icd11_scope`
   array, the set of ICD-11 codes the guideline governs, together with a `scope_embedding` used by
   the semantic-fallback routing tier. This field is the basis on which Stage 3 routing is
   deterministic.
5. **Knowledge-graph construction (`graph_builder.py` to Claude Haiku 4.5).** A language model
   extracts `(subject, relation, object)` triples from the CPG prose into the biomedical ontology
   shown in Fig. 3.3c. The safety-relevant relations include
   `(:Drug)-[:CONTRAINDICATED_WITH]->(:Condition)`, `(:Drug)-[:INTERACTS_WITH]->(:Drug)`,
   `(:Drug)-[:REQUIRES_MONITORING]->(:DiagnosticTool)`, and
   `(:Condition)-[:REQUIRES_REFERRAL]->(:Specialty)`, alongside the positive prescribing edges such
   as `FIRST_LINE_FOR` and `RECOMMENDED_FOR`.

Each chunk's `category` (step 2) is drawn from the fixed 13-value controlled vocabulary in Table 3.10.
A section may carry more than one category, and the vocabulary is what the Stage-4 category-aware
ranking (§3.7) keys off when it promotes decision-relevant sections — chiefly *Treatment*,
*Supportive Treatment*, and *Assessment* — over incidental prose.

**Table 3.10: The 13-value chunk-category controlled vocabulary (`documents/METADATA_README.md`).**

| # | Category | Captures |
|---|---|---|
| 1 | Methodology | Executive summary, evidence grading, guideline-development process |
| 2 | Introduction | Disease burden, CPG rationale, healthcare context |
| 3 | Pathophysiology | Disease mechanisms, biological pathways, genetic susceptibility |
| 4 | Epidemiology | Prevalence, incidence, risk factors, prognosis, natural history |
| 5 | Classification | Staging and taxonomy (WHO / NYHA / TNM / Dana Point) |
| 6 | Screening | Early detection, high-risk identification, screening modalities |
| 7 | Diagnosis | Clinical assessment, diagnostic criteria, investigation and referral pathways |
| 8 | Assessment | Risk stratification, severity scoring, operability and prognostic assessment |
| 9 | Treatment | Pharmacological therapy, surgical intervention, acute/chronic management |
| 10 | Supportive Treatment | Rehabilitation, palliative care, symptom and psychosocial management |
| 11 | Prevention | Secondary prevention, surveillance, lifestyle modification, risk reduction |
| 12 | Special Populations | Age/sex/comorbidity-specific care — pregnancy, paediatrics, fertility |
| 13 | Reference | Appendices, algorithm flowcharts, reference tables, trial data |

### 3.3.1 Relation-extraction guardrails

During development we found that the negative-edge extractor was the single largest source of false
safety flags. A language model tends to latch onto a "contraindicated" verb in a chunk and, finding
no explicit object in the sentence, silently substitutes the chunk's section heading as the object,
which manufactures a contraindication the guideline never stated. To prevent this class of
hallucinated edge from reaching Neo4j, four layered guards were implemented in `graph_builder.py`:

1. **Prompt-level explicit-complement rule.** A `CONTRAINDICATED_WITH` edge may be emitted only when
   the sentence contains an explicit `contraindicated <with|in|for|during|to> <noun>` complement; a
   bare "X is contraindicated" must not emit an edge.
2. **Prompt-level initiating-trigger blocker.** Clauses inside a "Drug X should be initiated when:"
   bullet list describe triggers for X, so no negative edge is emitted for other drugs named as
   preconditions inside those bullets.
3. **Code-level post-extraction complement check.** Any `CONTRAINDICATED_WITH` triple whose evidence
   sentence fails a complement-pattern match is dropped at extraction time with a warning.
4. **Code-level internal-contradiction guard.** When the same `(subject, object)` pair carries both a
   contraindication and a positive edge within one CPG, the conflict is logged for human review
   before the graph is written.

These guards operate at extraction time, so they keep bad edges out of the graph rather than
filtering them at runtime. That choice keeps the live safety-critic path fast and keeps the graph
itself trustworthy as a source of truth.

**Diagram D-INGEST, CPG ingestion pipeline (Fig. 3.4):**

```mermaid
flowchart LR
    A[CPG PDF] --> A2["docling to CPG markdown<br/>(H1→H2→H3 preserved)"]
    A2 --> B["Chunker<br/>hierarchical, cross-refs, metadata"]
    B --> C["Embeddings<br/>Bedrock Titan 1536-dim"]
    B --> D["Graph builder<br/>Claude Haiku 4.5 triple extraction"]
    C --> E[("pgvector<br/>chunk + ICD-11 scope store")]
    D --> F{Relation guardrails<br/>complement rule · trigger blocker<br/>regex check · contradiction guard}
    F -- pass --> G[("Neo4j KG<br/>drug / condition / parameter edges")]
    F -- drop --> X[/Rejected false<br/>'contraindicated' edge/]

    classDef store fill:#f8fafc,stroke:#64748b,color:#334155;
    classDef guard fill:#fffbeb,stroke:#f59e0b,color:#92400e;
    class E,G store;
    class F guard;
```

---

## 3.4 Stage 1: Patient Intake and Vitals Ingestion

The pipeline initializes by aggregating all available patient data including demographics, medical
history, concurrent medications, allergies, vital signs, and prior-visit summaries into a unified,
strictly typed `PatientCase` object validated via Pydantic. This standardized schema centralizes
data ingestion, establishing a stable, immutable data contract for all subsequent processing stages
and eliminating the structural unreliability of ad-hoc dictionaries.

> **[FIGURE 3.5: Step 1 intake screen (Data Input).]**
> *Insert a screenshot of the Doctor UI consultation wizard Step 1, showing the
> demographics/history/medications form together with the vitals panel and the rPPG scan
> affordance.*

Derived clinical metrics, notably Body Mass Index (BMI), are computed symmetrically across both the
frontend and backend API to ensure consistent data structures regardless of the entry vector. This
redundancy guarantees that downstream clinical referral triggers, which strictly depend on BMI
thresholds, reliably receive populated values, preventing undefined state evaluations.

The principal fields of this contract are summarised in Table 3.3.

**Table 3.3: Principal fields of the standardized patient intake record (`PatientCase`).**

| Field | Purpose |
|---|---|
| `chief_complaint` | Required free-text presenting complaint and relevant history |
| `age`, `sex` | Patient age and biological sex |
| `comorbidities` | Free-text past and current diagnoses (legacy path) |
| `staged_comorbidities` | Structured comorbidities with confirmed ICD codes |
| `current_medications` | Current medication regimen |
| `allergies` | Known drug and substance allergies |
| `vitals` | Recorded vital signs (e.g. sbp, dbp, hr, spo2, bmi) |
| `severity_staging` | Structured disease severity staging (e.g. eGFR band, NYHA class) |
| `prior_visit` | Summary of the most recent prior consultation (returning patients) |

Most of these fields are entered directly in the Step 1 form. To reduce that manual burden, this
stage incorporates two independent, contactless capture subsystems. Architected as self-contained
engineering modules, they enrich the `PatientCase` prior to its ingestion into the core reasoning
pipeline: an rPPG subsystem populates the `vitals` map from a face-camera recording, and a
voice-intake subsystem derives the clinical-note narrative from a recorded consultation. Each is
documented below.

### 3.4.1 rPPG vitals-capture ecosystem

Remote photoplethysmography (rPPG) infers vital signs from a short face-camera recording, so that a
clinic with no pulse oximeter or sphygmomanometer to hand can still populate the vitals panel. The
proof-of-concept (`rppg-poc/rppg_vitals.py`) runs as its own FastAPI server with a WebSocket stream
and is surfaced in the Doctor UI as `RPPGScanModal.jsx`. Its output is written through
`saveLiveVitals` and `saveRPPGVitals` into the Supabase `live_vitals` table and is tagged with the
vitals source and a quality indicator.

> **[FIGURE 3.5b: rPPG signal-processing pipeline.]**
> *Insert Mermaid diagram D-RPPG (below), or a screenshot of the RPPGScanModal capture screen with
> the live HR, BP, and SpO2 read-out.*

The signal-processing chain was implemented as follows:

1. **Face landmarking.** MediaPipe Face Mesh (468 facial landmarks) isolates three anatomical
   regions of interest, the forehead and the two cheeks, which are averaged to improve the
   signal-to-noise ratio over a single region.
2. **Blood-volume-pulse (BVP) extraction.** The mean RGB time series of each region is detrended by
   regularised least squares and converted to a BVP signal by the POS algorithm
   (Plane-Orthogonal-to-Skin, Wang et al. 2017), with a second-order Butterworth band-pass of 0.75
   to 2.5 Hz (45 to 150 bpm) applied through zero-phase filtering.
3. **Heart rate** is read from the dominant frequency of the BVP periodogram (FFT).
4. **SpO2** is estimated from the ratio of the AC and DC components of the red and blue channels
   (`SpO2 ≈ 110 − 25 × ratio`), clipped to a physiological range.
5. **Respiratory rate** is recovered from the amplitude modulation of the BVP envelope, accepted in
   the 6 to 30 breaths-per-minute range.
6. **Blood pressure** is estimated from a pseudo pulse-transit-time proxy, namely the phase delay
   between the forehead and cheek BVP signals, combined with an augmentation-index correction
   applied to a baseline systolic and diastolic estimate.

Because rPPG estimates, and cuffless blood pressure in particular, are approximate, the values are
explicitly tagged with a quality and confidence indicator and treated as a screening aid the
clinician can override, rather than as a substitute for a measured cuff reading. This framing is
preserved in the UI so that the limitation is visible at the point of use.

**Diagram D-RPPG, rPPG signal-processing pipeline (Fig. 3.5b):**

```mermaid
flowchart LR
    CAM[Face-camera frames] --> ROI["MediaPipe Face Mesh · 468 landmarks<br/>3 ROIs: forehead + L/R cheek"]
    ROI --> RGB[Mean RGB per ROI per frame]
    RGB --> POS["Detrend + POS algorithm (Wang 2017)<br/>band-pass 0.75–2.5 Hz"]
    POS --> BVP[BVP signal]
    BVP --> HR["Heart rate (FFT)"]
    BVP --> RR["Respiratory rate (envelope)"]
    RGB --> SPO2["SpO2 (red/blue AC·DC ratio)"]
    BVP --> BP["Blood pressure (forehead–cheek PTT + AIx)"]
    HR --> OUT([live_vitals + quality tag to Supabase])
    RR --> OUT
    SPO2 --> OUT
    BP --> OUT

    classDef det fill:#ecfeff,stroke:#0891b2,color:#164e63;
    class ROI,RGB,POS,HR,RR,SPO2,BP det;
```

### 3.4.2 Voice-intake (STT to SOAP) ecosystem

A full doctor and patient consultation can be recorded and turned into a structured SOAP note
appended to the clinical notes, so that the clinician's attention remains on the patient rather than
on typing. Like rPPG, this is intake tooling that never touches the Stage 2 to 6 pipeline. The audio
is never persisted: it is deleted immediately after transcription, with a one-day storage lifecycle
rule retained only as a crash safety net, and the transcript itself is not stored either.

> **[FIGURE 3.5c: Voice-intake (STT to SOAP) pipeline.]**
> *Insert Mermaid diagram D-STT (below). A screenshot of the GCS bucket is not recommended, because
> the staging bucket is emptied on every request and would show no meaningful state.*

The implementation (`POST /clinical/consultation/process`, with `gcs_audio.py` and
`summarise_consultation`) proceeds as follows:

1. **Upload to Google Cloud Storage.** The raw audio is uploaded to GCS and referenced by a `gs://`
   URI. This step is a non-obvious but necessary design choice, because Google Speech caps inline
   audio at approximately one minute, whereas a five to ten minute consultation must be passed by
   URI.
2. **Diarized long-running transcription.** Google Speech `longrunningrecognize` is invoked with a
   two-speaker diarization configuration, and the operation is polled to completion under a timeout
   that returns HTTP 504 rather than hanging.
3. **Blob cleanup.** The GCS object is deleted in a `finally` block regardless of outcome.
4. **Speaker grouping.** The word-level `speakerTag` stream is grouped into turns, with the first
   speaker labelled Doctor, producing a clean two-party transcript.
5. **SOAP summarisation.** A language model (`CONSULTATION_SUMMARY_MODEL`, Gemini Flash) condenses
   the labelled transcript into a SOAP-style note, which the frontend appends to the clinical notes
   field.

A separate lightweight endpoint, `POST /clinical/stt`, serves short dictation clips for the legacy
"dictate" mode. One operational subtlety is documented in the deployment notes: the Speech-to-GCS
read hop authenticates as Google Speech's own service agent rather than the backend's credentials,
and that agent must hold object-viewer permission on the bucket, an IAM binding that is easy to
overlook.

**Diagram D-STT, voice-intake transcription pipeline (Fig. 3.5c):**

```mermaid
flowchart LR
    AUD[Consultation audio] --> GCS["Upload to GCS<br/>gs:// URI (bypasses ~1 min inline cap)"]
    GCS --> REC["Google Speech longrunningrecognize<br/>2-speaker diarization · polled with 504 timeout"]
    REC --> GRP["Group speakerTag stream into turns<br/>first speaker = Doctor"]
    GRP --> SOAP["Gemini Flash summariser<br/>labelled transcript to SOAP note"]
    SOAP --> NOTE([Appended to clinical notes])
    GCS -.->|finally block| DEL["Delete GCS blob<br/>(audio never persisted)"]
    REC -.-> DEL

    classDef det fill:#ecfeff,stroke:#0891b2,color:#164e63;
    class GCS,REC,GRP,DEL det;
```

---

## 3.5 Stage 2: Symptom-to-ICD-11 Differential Diagnosis

The objective of Stage 2 was to convert a free-text symptom narrative into a ranked,
clinician-approvable shortlist of named ICD-11 diagnoses (codes, not prose), drawn from the WHO
catalogue of 3,914 codes. The central engineering challenge is twofold: the Bedrock Titan embedding
space is biased toward generic symptom and "unspecified" codes, and task-framed visits, such as a
post-PCI review with no symptom narrative, produce brittle and non-reproducible queries. Stage 2
therefore layers several deterministic stabilisers around the language-model steps.

> **[FIGURE 3.6: Stage 2 DDx sub-pipeline.]**
> *Insert Mermaid diagram D-DDX (below). This is the internal process view; its Mode A versus Mode B
> branch is explained in §3.5.1, and the clinician-facing output of this stage is shown separately in
> Fig. 3.6b.*

The stage is composed of the following sub-steps. Every generative step here runs on the fast tier,
Gemini 2.5 Flash, consistent with the model tiering in Table 3.2, because each is a bounded
extraction or ranking task rather than deep synthesis, and the parallel search uses the shared
Bedrock Titan v1 embedding model that defines the vector space.

- **Symptom extractor (15-word distiller, Gemini 2.5 Flash).** A language model rewrites the clinical
  notes into a single short phrase, capped at fifteen words, optimised for embedding. The cap is
  enforced in code, with truncation as a secondary guard.
- **Hypothesis generator (Gemini 2.5 Flash).** A complementary language-model call proposes candidate
  named conditions, which widens the candidate pool beyond what the symptom phrase alone retrieves.
- **Clinician-named (CC) boost (Gemini 2.5 Flash extraction, Titan vector resolution).** Diagnoses the
  clinician wrote explicitly in the chief-complaint, history, or examination text are lifted out,
  resolved from name to code by vector lookup, and flagged to the contextual re-ranker as a strong
  soft signal — a hard prompt rule requires an explicitly clinician-named diagnosis to surface in the
  top three — so that a clinician-stated diagnosis outranks the strongest symptom hit. This signal is
  carried in the score trace for audit but, by design, does not enter the deterministic `math_rank`
  formula below. The system never trusts an LLM-emitted ICD code,
  because language models hallucinate digit-leading codes; the name-to-code resolution step removes
  that class of failure.
- **Multi-query parallel vector search (Bedrock Titan v1, 1536-dim).** The symptom phrase, the
  generated hypotheses, and the resolved CC hints are embedded and searched against the 3,914-code
  ICD-11 store in parallel (`asyncio.gather`), with the ivfflat probe count raised
  (`SET ivfflat.probes = 100`) to avoid silently dropping correct codes.
- **Deterministic relevance scoring (the `math_rank`).** Before any language model re-orders the
  pool, each candidate is scored deterministically from the WHO ICD-11 metadata attached to its code.
  An ICD-11 code carries, besides its title and hierarchy position, a set of *inclusion* terms
  (synonyms and indexed sub-entities that legitimately resolve to that code) and *exclusion*
  cross-references ("see-other" pointers redirecting a near-miss query to a different, correct code).
  The score adjusts the raw embedding cosine accordingly: a hit against an inclusion synonym adds a
  weighted boost, and a query that actually matches an exclusion cross-reference is penalised, so that
  `final_score = base_similarity + inclusion_match − exclusion_penalty`. This produces a purely
  deterministic ordering, the `math_rank`, on which the contextual re-ranker below then operates. A
  strong inclusion boost can lift `final_score` above 1.0; the value is clamped to `[0, 1]` for display
  only, and the raw percent is never shown on the clinician card.
- **Contextual LLM re-ranker (Gemini 2.5 Flash, reasoning tokens enabled).** A language model with
  reasoning tokens re-ranks the merged candidate pool using the patient's age, sex, comorbidities,
  and medications as context. Two prompt rules counter the Titan bias: a specificity preference (for
  example NSTEMI `BA41.1` over the unspecified `BA41`) and a distinct-disease preference (codes
  sharing a four-character ICD stem collapse to a single conceptual slot, so that one strong vector
  hit cannot fill the top five with its own siblings). The re-ranked order is the displayed
  `AI_rank`; the per-card "Why this rank?" disclosure surfaces the `math_rank → AI_rank` delta so that
  any model-driven reordering away from the deterministic score remains auditable.

### 3.5.1 Two intake paths: symptom-driven (Mode A) and task-framed (Mode B)

Before any of the sub-steps run, Stage 2 decides which of two paths a `PatientCase` follows, because
the two kinds of visit demand different handling. This is the first branch in Fig. 3.6.

- **Mode A, symptom-driven.** The default path for a patient presenting with a complaint. The notes
  carry a genuine symptom narrative, so the LLM symptom extractor and hypothesis generator are run to
  distil and then widen the query before the vector search.
- **Mode B, task-framed.** Procedural and review encounters (post-operative review, antenatal
  booking, medication review, routine follow-up) carry no presenting symptom to extract, and forcing
  an LLM extractor over them produces brittle, non-reproducible phrasing. A cheap regex
  (`_is_task_framed`) detects a task marker and bypasses the extractor entirely, assembling the query
  deterministically (`_assemble_task_framed_phrase`) from the chief complaint, history, and
  comorbidities, so the same case always yields the same query string.

Separating the two paths matters because a task-framed visit gives the embedding space no symptom to
latch onto, so routing it through the symptom pipeline is both wasteful and a source of run-to-run
drift. Mode B removes that failure at its root, which is why it also appears as the fourth layer of
the reproducibility stack below.

### 3.5.2 Reproducibility: the four-layer determinism stack

Because the same patient must receive the same differential on every run, which is a non-negotiable
property for an auditable clinical tool, Stage 2 was hardened with four reproducibility layers:

1. **Seed-pinning** of every Stage 2 LLM call, applied where the backend accepts a seed. Gemini's
   OpenAI-compatibility layer rejects the seed field, so the seed is stripped for that backend and
   reproducibility there rests on `temperature=0` together with the deterministic tie-break in layer
   four.
2. **Regex disease-to-ICD fallback,** a scan of the notes for approximately sixty disease aliases
   (NSTEMI, AF, T2DM, HFrEF, and others) that augments the LLM hints rather than replacing them,
   filling gaps the LLM missed.
3. **In-process phrase cache,** keyed on a hash of model and notes, which removes per-run extraction
   jitter within a process.
4. **Mode-B rule-based bypass** (§3.5.1), which removes LLM phrasing jitter on task-framed visits,
   together with a co-equal-primary tie-break that orders two clinician-named diagnoses
   alphabetically when their scores fall within an epsilon.

The output is a ranked DDx list that the clinician approves before the system spends any compute on
Stages 3 to 6. The reproducibility of this stage is the strongest empirical result of the project
and is reported in Chapter 4.

> **[FIGURE 3.6b: Step 2 Diagnosis screen (clinician-facing ranked differential).]**
> *Insert a screenshot of the Doctor UI Step 2, showing the ranked ICD-11 differential cards with
> their High/Moderate/Low tier badges, the clinician selection controls, and the "Why this rank?"
> disclosure that exposes the math-rank to AI-rank delta and any clinical override.*

**Diagram D-DDX, Stage 2 differential-diagnosis sub-pipeline (Fig. 3.6):**

```mermaid
flowchart TB
    PC([PatientCase]) --> MODE{Mode-A vs Mode-B?}
    MODE -- "Mode B (task-framed)" --> TPL["Deterministic template query<br/>(no LLM)"]
    MODE -- "Mode A (symptom)" --> EX["Symptom Extractor<br/>15-word distiller (LLM)"]
    EX --> HY["Hypothesis Generator (LLM)"]
    CC["Clinician-named dx to name→ICD<br/>vector resolve, then boost"] --> POOL
    TPL --> POOL
    HY --> POOL
    POOL["Parallel pgvector search<br/>3,914 ICD-11 codes · probes=100"] --> RR["Contextual LLM re-ranker<br/>specificity + distinct-disease rules"]
    RR --> COL["Deterministic sibling-cluster collapse"]
    COL --> DDX([Ranked ICD-11 differential · clinician-approved])

    classDef agent fill:#f0fdfa,stroke:#0d9488,color:#134e4a;
    classDef det fill:#ecfeff,stroke:#0891b2,color:#164e63;
    class EX,HY,RR agent;
    class TPL,POOL,COL det;
```

---

## 3.6 Stage 3: Deterministic Scoped Routing

Stage 3 is the architectural centre of the system's safety design, and it contains no language
model. Its objective was to map each clinician-approved ICD-11 code to the exact set of MoH CPGs
that govern it, and, equally important, to return no plan when no guideline applies rather than
fabricate a plausible but ungoverned answer. This refusal behaviour was a primary design goal,
because a system that always synthesises from whatever it retrieved would produce confident advice
for conditions it holds no guideline for.

The reliability of this mapping rests on the provenance of each guideline's scope. The `icd11_scope`
of every guideline, the explicit set of ICD-11 codes it governs, was established against the WHO
ICD-11 reference rather than inferred by a model. Each candidate code was resolved through the WHO
ICD-11 API to obtain its authoritative title, definition, inclusions, exclusions (the synonym and
cross-reference terms introduced in §3.5), parent hierarchy, and chapter, and these details were
recorded per code. The resulting scope assignments were then
reviewed and clinically verified by a practising clinician, who approved, edited, or rejected the
proposed scope of each guideline.

A single guideline's scope is therefore a set of related ICD-11 codes rather than one code. The
Heart-Failure (5th Edition) guideline, for example, is scoped to the heart-failure block together
with its subtypes and the residual `.Y`/`.Z` variants, as shown in Table 3.4.

**Table 3.4: ICD-11 scope of the Heart-Failure (5th Edition) guideline.**

| ICD-11 code | Title |
|---|---|
| `BD10` | Congestive heart failure |
| `BD11` | Left ventricular failure |
| `BD11.0` | Left ventricular failure with preserved ejection fraction |
| `BD11.1` | Left ventricular failure with mid range ejection fraction |
| `BD11.2` | Left ventricular failure with reduced ejection fraction |
| `BD11.Z` | Left ventricular failure, unspecified |
| `BD12` | High output syndromes |
| `BD13` | Right ventricular failure |
| `BD14` | Biventricular failure |
| `BD1Y` | Other specified heart failure |
| `BD1Z` | Heart failure, unspecified |

It is this set that the routing cascade in §3.6.1 matches a predicted code against. The full
per-guideline scope assignment is enumerated in Appendix [TODO: appendix ref].

> **[FIGURE 3.7 — insert WHO ICD-11 browser screenshot of the heart-failure block here.]**
>
> **Figure 3.7 — WHO ICD-11 browser: the heart-failure block (`BD10`–`BD1Z`).** Left pane: the
> parent–child code hierarchy that the Stage 3 routing cascade (§3.6.1) walks when an exact match is
> absent. Right pane: the "Exclusions from above levels" list for `BD11.0` — the WHO cross-references
> that the deterministic `exclusion_penalty` (§3.5) keys off — and the authoritative source against
> which this guideline's scope in Table 3.4 was verified.

This procedure is also the system's scaling contract. The first version of the scope was verified by
a single clinician; broadening the corpus toward production scale will require the same codes to be
reviewed by multiple clinicians so that the mapping does not rest on one practitioner's judgement,
and every newly ingested CPG must pass through the identical classify-then-clinically-verify
procedure before it is allowed to participate in routing.

The corpus routed against at the time of writing comprises thirty clinically verified MoH CPGs,
organised under the four MoH clinical domains the system primarily targets — cardiovascular disease,
endocrine disease, cancer, and anaesthesiology — together with a single erectile-dysfunction
guideline, as summarised in Table 3.5.

**Table 3.5: The thirty-guideline CPG corpus by MoH clinical domain.**

| Clinical domain | CPGs | Conditions |
|---|---|---|
| Cardiovascular disease | 15 | Heart failure, Hypertension, Atrial fibrillation, STEMI, NSTE-ACS, UA/NSTEMI, Stable coronary artery disease, Percutaneous coronary intervention, Ischaemic stroke, Infective endocarditis, Pulmonary arterial hypertension, Dyslipidaemia, CVD prevention, CVD prevention in women, Heart disease in pregnancy |
| Endocrine disease | 6 | Type 2 diabetes, Type 1 diabetes (children), Diabetes in pregnancy, Thyroid disorders, Obesity, Growth hormone |
| Cancer | 5 | Cancer pain, Breast cancer, Colorectal carcinoma, Nasopharyngeal carcinoma, Cervical cancer |
| Anaesthesiology | 3 | Pre-anaesthetic assessment, Medication safety in anaesthesia, Patient safety & minimal monitoring |
| Erectile dysfunction | 1 | Erectile dysfunction |

The grouping follows the MoH CPG portal's own domain taxonomy, so guidelines that span more than one
organ system are placed where MoH files them — Dyslipidaemia and Heart-Disease-in-Pregnancy under
cardiovascular disease, Diabetes-in-Pregnancy under endocrine disease. The distribution shows the
corpus's deliberate cardiovascular and cardiometabolic focus.

> **[FIGURE 3.7b: Nine-tier deterministic routing cascade.]**
> *Insert Mermaid diagram D-ROUTE (below), drawn as a descending ladder so that the progression
> from exact match, through broadening, to semantic fallback and refusal is legible.*

### 3.6.1 The routing cascade

Routing was implemented as a deterministic cascade that attempts the most precise match first and
broadens only as far as necessary. Although it is summarised in design materials as the "D1 to D6
ladder", the implementation in `backend/agent/routing.py` is a nine-tier cascade, each tier
representing a strictly weaker structural claim than the one before it. Table 3.9 defines each tier,
with one ICD-11 family — `5B80.00` *(Overweight in infants, children or adolescents)* — threaded
through the examples so that the progressive broadening is legible row to row.

**Table 3.9: The nine-tier deterministic routing cascade (`backend/agent/routing.py`).**

| # | Match tier | What it matches | Example |
|---|---|---|---|
| 1 | `exact` | Predicted code appears directly in a guideline's `icd11_scope` | `5B80.00` → `5B80.00` |
| 2 | `sibling` | Same-parent siblings, including the `.Y`/`.Z` residual variants | `5B80.00` → `5B80.01`, `5B80.0Z` |
| 3 | `ancestor_d1` | The direct (one-decimal) parent | `5B80.00` → `5B80.0` |
| 4 | `ancestor_d1_sibling` | Peer categories of that parent | `5B80.00` → `5B80.1` |
| 5 | `ancestor_d1_sibling_child` | Children of those peer categories | children of `5B80.1` |
| 6 | `ancestor_d2` | The no-decimal block (grandparent) ancestor | `5B80.00` → `5B80` |
| 7 | `procedure_scope` | Tag overlap with a caller-supplied procedure context | PCI context → PCI-tagged scope |
| 8 | `semantic_scope` | Cosine similarity between the code embedding and the guideline's `scope_embedding`, at or above the calibrated `0.32` floor — captures cross-chapter conditions the structural tiers miss | similarity ≥ `0.32` |
| 9 | `out_of_scope` | No guideline matched — the system returns no plan | — |

The three distant structural-walk tiers (4–6) and the semantic tier (8) are additionally gated by the
scope-confidence floor described in §3.6.2; the precise tiers (1–3) are never floored, as they
represent genuine scope membership.

### 3.6.2 Calibration and gates

Three design details make this cascade trustworthy:

- **Semantic threshold `SEMANTIC_SCOPE_THRESHOLD = 0.32`.** The semantic-fallback tier admits a code
  only when its cosine similarity to a guideline's `scope_embedding` meets this floor. The value was
  not chosen by intuition but calibrated through a systematic procedure. A labelled validation set of
  code-to-guideline pairs was assembled and partitioned into known in-scope and known out-of-scope
  pairs; every pair was scored, and the floor was placed inside the separation margin between the
  highest out-of-scope similarity and the lowest in-scope similarity, leaving headroom on each side
  so that neither class is clipped. The ground-truth labels for this set were taken from the same
  clinician-verified scope assignments described in §3.6, so the threshold is validated against
  clinically approved labels rather than self-generated ones, and it is the same clinician who
  established the first version of the scope routing who validated this benchmark. The value is
  therefore treated as a calibrated constant and must not be retuned without rerunning the
  calibration procedure against the validation set. The same floor also gates the distant
  structural-walk tiers, so a code that reaches a guideline only through a remote hierarchy walk
  cannot present itself as in scope.
- **D3 exclusion-penalty gate.** The exclusion penalty applied to "other specified" chunks is gated
  on the condition `exclusion_sim > base_score`, so that a generic exclusion chunk cannot
  self-penalise the correct subtype out of scope.
- **Sex-incompatibility filter.** After the cascade returns candidates, male patients are routed away
  from female-only guidelines (Heart-Disease-in-Pregnancy, Diabetes-in-Pregnancy, Cervical-Cancer,
  CVD-Prevention-Women, Breast-Cancer), and the exclusion is recorded in the trace. Applying the
  filter after the cascade ensures that a male patient with an exact-match pregnancy code still ends
  `out_of_scope`.

A further optimisation, the staged-comorbidity short-circuit, allows a comorbidity whose ICD code
the clinician already confirmed in the intake UI to bypass the vector path entirely (0 ms versus
roughly 4 s), routing the confirmed code directly.

**Diagram D-ROUTE, Stage 3 deterministic routing cascade (Fig. 3.7b):**

```mermaid
flowchart TB
    DDX([Approved ICD-11 codes]) --> T1{1 · exact in icd11_scope?}
    T1 -- yes --> SEX
    T1 -- no --> T2{2 · sibling / .Y / .Z?}
    T2 -- yes --> SEX
    T2 -- no --> T3{3 · direct parent ancestor_d1?}
    T3 -- yes --> SEX
    T3 -- no --> T46{4–6 · distant ancestor / block walk?}
    T46 -- yes --> FLOOR{also clears 0.32 sim?}
    T46 -- no --> T7{7 · procedure-tag overlap?}
    FLOOR -- yes --> SEX
    FLOOR -- no --> OOS
    T7 -- yes --> SEX
    T7 -- no --> T8{8 · sim >= 0.32 alone?}
    T8 -- yes --> SEX
    T8 -- no --> OOS([9 · out_of_scope · no plan returned])
    SEX["Sex-incompatibility filter<br/>(drop female-only CPGs for male)"] --> CPG([Matched CPG set])

    classDef det fill:#ecfeff,stroke:#0891b2,color:#164e63;
    classDef stop fill:#fef2f2,stroke:#dc2626,color:#991b1b;
    class T1,T2,T3,T46,T7,T8,FLOOR,SEX det;
    class OOS stop;
```

---

## 3.7 Stage 4: Evidence-Graded Scoped Retrieval

With the governing guidelines identified, Stage 4 retrieves the specific evidence passages needed to
write the plan. The objective was high-recall retrieval that is strictly contained to the routed
guidelines, bringing the relevant passages to the clinician quickly while making cross-guideline
contamination structurally impossible. This stage does involve a language model, because the search
queries are written by one; the assumption that retrieval is purely deterministic does not hold
here.

The sub-steps are:

- **Targeted Query Generation (LLM).** A language model drafts up to seven focused,
  domain-specific queries from the patient context and the top DDx codes. These are supplemented by
  three universal anchor queries (baseline investigations, lifestyle modifications, and specialist
  referrals) and by condition-specific pillar anchors derived from the primary code, so that
  high-leverage sections are not omitted when the LLM fails to seed a query for them.
- **Scoped pgvector Search.** Each query is executed against the vector store pinned by a
  `document_id_filter` to the routed guidelines only. Because the filter is applied at the database
  query, evidence from an unrelated guideline cannot enter the evidence pack; this is the structural
  guarantee behind the system's grounded, in-corpus claim. All queries run in parallel.
- **Category-aware ranking and top-20 cut.** The deduplicated pool is re-weighted using each chunk's
  `category` metadata (the 13-value controlled vocabulary of Table 3.10, assigned at ingestion), then
  sorted by that boosted score and **truncated to the top 20 chunks**. The cap serves two ends: it
  bounds the evidence pack so it fits inside the Stage-5 synthesis token budget, and it prevents
  context dilution — feeding the synthesiser a smaller set of high-value passages keeps its attention
  concentrated on decision-relevant evidence rather than spread thin across marginal, lower-ranked
  prose. The category boost is what ensures the 20 survivors are the decision-relevant sections —
  chiefly pharmacological management and monitoring — rather than the highest-similarity incidental
  prose.
- **Hierarchical Prefetching (H3 to H2 to H1).** For every matched leaf chunk,
  `_prefetch_parent_content` pulls its grandparent section headers up the tree, so that local
  abbreviations, the section's level of evidence, and Malaysian-context callouts accompany the chunk
  rather than being stranded.
- **Cross-Reference Resolution.** `_resolve_cross_refs` scans the matched chunks, and their parent
  chain, for inline `§X.Y` anchors that point to other sections or guidelines, fetches the best
  matching target chunks, and appends them to the evidence pack, following the guideline's own
  internal citation graph.

The deduplicated, evidence-graded chunk set is the output. Each chunk carries its original MoH
evidence grade, so that the synthesiser can stamp every recommendation with its provenance.

**Diagram D-RETRIEVE, Stage 4 evidence-graded scoped retrieval (Fig. 3.7c):** the three inputs are
carried in from earlier stages (each tagged with its source stage), and every process node is named
to match the sub-steps above.

```mermaid
flowchart TB
    S1["Stage 1 · Intake"] --> I1
    S2["Stage 2 · DDx"] --> I2
    S3["Stage 3 · Routing"] --> I3
    I1(["Patient context"]) --> QG
    I2(["Top DDx codes"]) --> QG
    I3(["Routed CPGs · document_id_filter"]) --> SEARCH

    QG["Targeted Query Generation<br/>(LLM · up to 7 + anchor queries)"] --> SEARCH
    SEARCH["Scoped pgvector Search<br/>(parallel · pinned to routed CPGs)"] --> DEDUP
    OTHER[("Unrelated CPGs")] -. blocked by document_id_filter .- SEARCH
    DEDUP["Deduplication"] --> RANK
    RANK["Category-Aware Ranking and Top-20 Cut"] --> PREF
    PREF["Hierarchical Prefetching<br/>(H3 → H2 → H1 parents)"] --> XREF
    XREF["Cross-Reference Resolution<br/>(§X.Y anchors)"] --> OUT
    OUT(["Evidence-Graded Chunk Set → Stage 5"])

    classDef tag fill:#f1f5f9,stroke:#94a3b8,color:#475569;
    classDef input fill:#f8fafc,stroke:#64748b,color:#334155;
    classDef llm fill:#ccfbf1,stroke:#0d9488,color:#134e4a;
    classDef det fill:#ecfeff,stroke:#0891b2,color:#164e63;
    classDef block fill:#fef2f2,stroke:#dc2626,color:#991b1b;
    class S1,S2,S3 tag;
    class I1,I2,I3,OUT input;
    class QG llm;
    class SEARCH,DEDUP,RANK,PREF,XREF det;
    class OTHER block;
```

---

## 3.8 Stage 4.5: Pre-Synthesis Knowledge-Graph Injection

Stage 4.5 is a short, fully deterministic stage that runs between retrieval and synthesis. Its
objective was to surface the structural drug-safety and drug-preference relationships that the
retrieved prose may not state explicitly, that is, the knowledge held in the graph rather than in
the text. It is implemented as plain Neo4j Cypher; despite sitting between two LLM steps, it
contains no language model.

Two complementary arms run against the same graph backend:

- **The "avoid" arm (`clinical_graph_lookup`).** Candidate drugs are gathered from the retrieved
  chunks and, importantly, from the patient's current medications, because a teratogen the patient
  is already taking will never appear in a recommended-regimen chunk, and omitting current
  medications would allow exactly that class of risk, such as an existing ARB in pregnancy, to
  escape safety review. Both lists are expanded to their drug-class names, for example Losartan to
  Angiotensin Receptor Blocker and ARB, so that class-level edges such as
  `(ARB)-[:CONTRAINDICATED_WITH]->(Pregnancy)` fire, given that the Cypher performs name-normalised
  set membership rather than pattern matching. Comorbidity strings are likewise aliased, for example
  "Pregnancy 30 weeks (primigravida)" to `pregnancy`, so that they match canonical graph nodes.
- **The "prefer" arm (`graph_navigator.py`).** This arm walks the positive prescribing edges
  (`FIRST_LINE_FOR`, `SECOND_LINE_FOR`, `RECOMMENDED_FOR`) keyed by the DDx titles and
  comorbidities, so that the synthesiser sees "prefer Y" alongside "avoid X" in one merged evidence
  block.

Both arms apply a routed-chunk scope filter, under which an edge is kept only when its source chunk
belongs to a routed guideline, which prevents cross-CPG drift, and a paediatric-source filter, which
drops paediatric evidence when the patient is an adult. Both arms fail open: if Postgres is
unavailable the filter is simply not applied, rather than dropping every edge, and if the graph is
unreachable the edge list is empty. Neither failure blocks synthesis. This fail-open posture is a
recurring safety theme, discussed further in §3.14.

> **Figure 3.8b — KG "avoid" arm: pregnancy contraindication fan-out with edge provenance.**
> *Multiple drugs and drug classes (RAS blocker, orlistat, phentermine, liraglutide) share one
> `CONTRAINDICATED_WITH` target — the central Pregnancy node. The selected Orlistat edge's*
> *Relationship details panel shows the provenance every safety edge carries: `severity = MAJOR`, the*
> *verbatim CPG `evidence`, and the `cpg_chunk_id` / `source_document` tracing it to a specific*
> *guideline section. Captured via `MATCH p=(d:Drug)-[:CONTRAINDICATED_WITH]->(c:Condition) WHERE*
> *c.name_normalised CONTAINS 'pregnan' RETURN p`. Stage 4.5 also appears as the cyan "KG inject" node*
> *in the master architecture diagram (Fig. 3.1).*

---

## 3.9 Stage 5: Evidence-Graded Care Plan Synthesis

Stage 5 executes the core language-model reasoning using MiMo v2.5 Pro, synthesising patient
data, retrieved CPG evidence, prior-visit summaries, and knowledge-graph constraints into a unified
treatment plan. To minimise clinician cognitive load under time constraints, the system generates a
structured, executable, eight-section care plan rather than dense prose.

Every recommendation is strictly cited and evidence-graded. The final output is enforced as a
Pydantic-validated `TreatmentPlan` object, ensuring that structurally malformed plans fail safely
during validation rather than rendering partially.

> **[FIGURE 3.8: Step 3 Care Plan screen (8-section renderer).]**
> *Insert a screenshot of the Doctor UI Step 3, showing the action-tagged medication chips, the
> monitoring trip-wires, the urgency-coloured referrals, and the contraindicated-medications panel.*

### 3.9.1 The eight-section executable plan

The `TreatmentPlan` schema was structured to render as the eight canonical sections evaluated in the
test cases, as shown in Table 3.6.

**Table 3.6: The eight-section care plan and its backing fields.**

| # | Section | Source field |
|---|---|---|
| P1 | Clinical Summary | `TreatmentPlan.summary` |
| P2 | Medications | `recommendations`, with `action ∈ {start, stop, change, continue, contraindicated}` |
| P3 | Procedures and Investigations | `recommendations` (investigation type) |
| P4 | Monitoring | `monitoring` (time-anchored schedules and targets) |
| P5 | Lifestyle | `recommendations` (lifestyle type) |
| P6 | Referrals | `recommendations` (referral type, with urgency) |
| P7 | Safety Netting / Red Flags | monitoring trip-wires and `SafetyReport` |
| P8 | Follow-up Plan | `follow_up` |

P7 red flags are *patient-facing* trip-wires — the symptoms or vital thresholds that should prompt the
patient to return or escalate. They are distinct from the plan's **unresolved questions**
(`TreatmentPlan.unresolved_questions`), which are *clinician-facing* gaps the model raises about its
own reasoning — missing data, load-bearing assumptions, coverage gaps, or refused computations. One
tells the patient what to watch for; the other tells the clinician what the system could not resolve.

Every recommendation is stamped with its original MoH evidence grade. The corpus contains three
mutually incompatible grading schemes (ESC, USPSTF, SIGN50), for example an ESC-style "Class I, Level
A", and the system never normalises across schemes, because a fabricated cross-scheme equivalence
would misrepresent the strength of the underlying evidence.

### 3.9.2 The eight-layer post-synthesis validator chain

A raw LLM plan is not accepted as-is. After synthesis, the plan passes through eight deterministic
validators that address the language model's characteristic failure modes
(`backend/agent/clinical_stages.py`):

1. **Medication de-duplication,** run twice (after LLM synthesis and again after KG injection), using
   exact-name matching and a substring-overlap threshold of at least 85 percent.
2. **Referral de-duplication** with urgency prioritisation (emergency over urgent over routine),
   keyed on an inferred specialty so that eight distinct specialties do not collapse into one entry.
3. **Urgency and severity harmonisation,** which auto-upgrades a "routine" referral to urgent or
   emergency when the assessed case severity warrants it.
4. **Coverage-gap detector,** which checks that each condition's first-line therapy is present,
   counting the patient's current medications, and surfaces a gap as an unresolved question without
   ever fabricating a prescription.
5. **Specialist and medication cross-check,** which flags a specialist-initiated drug recommended
   without the corresponding referral, kept deliberately tight so that GP-initiable drugs do not
   false-fire.
6. **STOP-with-switch splitter,** which recovers the implicit start recommendation when the LLM
   collapses a drug swap into a single "stop X, switch to Y" line.
7. **Assumption flagger,** which extracts the load-bearing clinical assumptions, for example "assumes
   eGFR above 30; if below, this drug is contraindicated", so that the clinician can verify them
   before acting.
8. **Gate-audit per-CPG cap,** which prevents one broad-comorbidity guideline from overwhelming the
   audit trail with referral triggers unrelated to the visit.

Every validator was implemented to fail open: an error is logged as non-fatal and synthesis
continues, because a validator crash must never deny the clinician a plan.

---

## 3.10 Stage 6: Hybrid Adversarial Safety Critic

Stage 6 is the only stage with two independent, grounded sources of truth, and it is the component
that most closely matches the behaviour of an agent: an adversarial reviewer that inspects the
finished plan and can block sign-off. The objective was to catch medication harm that a
single-source tool would miss, and to do so through two mechanisms that fail in different ways, so
that the absence of a hazard from one source does not hide it from the clinician.

> **[FIGURE 3.9: Stage 6 safety-acknowledgement banner.]**
> *Insert a screenshot of the Stage 6 safety banner on a blocked plan, showing the severity-grouped
> flags (Critical / Major / Moderate), each with its evidence expander and per-flag Replace /
> Keep+acknowledge / Remove decision controls, and the acknowledgement progress gate. The banner
> surfaces the merged union of concerns from both critics. Pair with Mermaid diagram D-CRITIC
> (Fig. 3.9b) below.*

The two graders run concurrently through `asyncio.gather`:

- **LLM clinical-pharmacist critic** (`_llm_critic`, Gemini 2.5 Flash) follows a generator and
  evaluator pattern, runs blind to the Stage 5 reasoning chain, and audits for drug allergies
  (including sulfonamide cross-reactivity), drug-drug interactions, dosing in organ impairment (for
  example metformin in stage-4 CKD), and absolute contraindications (for example non-selective
  beta-blockers in severe asthma).
- **Neo4j KG plan-verifier** (`_kg_verify_plan`, deterministic Cypher) runs structural queries
  against the final plan's recommendations, catches violations that no retrieved passage happened to
  mention, and maps each offending drug node back to its recommendation index.

### 3.10.1 Merge without de-duplication and the sign-off gate

The two flag lists are merged without de-duplication: an `llm`-sourced flag and a `graph`-sourced
flag for the same drug are both shown, because the surface a clinician sees in a pharmacist-vacant
clinic must display every independent concern. `safe_to_proceed` is then recomputed across the
merged union, and any CRITICAL or MAJOR flag blocks sign-off. Both critics fail open, returning an
empty flag list on error, which follows the same principle as Stage 4.5: an unreliable connection
must never silently suppress a safety concern.

The dual-source design is illustrated by Case 11 (Fig. 3.9): a man with stable coronary artery
disease maintained on isosorbide mononitrate, with comorbid type 2 diabetes on metformin and
liraglutide, presenting for treatment of erectile dysfunction. The two critics surface complementary
concerns, and the banner shows both. The LLM critic flags the interaction between a PDE5 inhibitor
and the patient's nitrate as CRITICAL — a life-threatening hypotension risk, and a severity that only
the reasoning arm emits, since the knowledge-graph arm never raises a flag to CRITICAL. The graph
verifier independently contributes the second flag, the metformin–liraglutide interaction, drawn from
a typed drug–drug edge; it reaches the clinician as a MODERATE concern precisely because graph-verified
flags are exempt from the moderate-severity noise filter that suppresses the model's own low-severity
chatter. The two lists are merged without de-duplication, `safe_to_proceed` is set to false, and the
plan is blocked until the clinician decides on both. Because the graph catch is a traversal over typed
edges rather than a phrase the model happened to surface, it is reproducible by structure — a guarantee
a text-retrieval-only design does not have the data to provide.

### 3.10.2 Audit logging

Every flag, verdict, and clinician override is recorded for medico-legal traceability. When a
clinician overrides a blocked plan and proceeds, the acknowledgement is persisted with the
authenticated user and a timestamp (`safe_to_proceed`, `safety_acknowledged`, `_by`, `_at`), so that
the decision trail can be reconstructed afterwards.

**Figure 3.9b — Diagram D-CRITIC, Stage 6 dual-source safety critic:**

```mermaid
flowchart TB
    S5["Stage 5 · Synthesis"] --> I1
    S1["Stage 1 · Intake"] --> I2
    I1(["Drafted Treatment Plan"]) --> DISP["Concurrent Dispatch<br/>(asyncio.gather)"]
    I2(["Patient Case Context<br/>allergies · comorbidities · current meds · organ function"]) --> DISP

    DISP --> LLM
    DISP --> KG

    subgraph LLM["LLM Pharmacist Critic"]
        direction TB
        LA["Allergy & Cross-Reactivity"]
        LD["Drug–Drug Interactions"]
        LO["Organ-Impairment Dosing"]
        LC["Absolute Contraindications"]
    end

    subgraph KG["Neo4j KG Plan Verifier"]
        direction TB
        KC["Drug–Condition Contraindications"]
        KI["Drug–Drug Interactions"]
        KM["Monitoring Requirements"]
        KX["Recommendation-Index Mapping"]
    end

    LLM --> MERGE["Merging Without Deduplication"]
    KG --> MERGE
    MERGE --> REPORT(["SafetyReport<br/>dual-source flags"])
    REPORT --> VERDICT{"Any CRITICAL or<br/>MAJOR Flag?"}
    VERDICT -- yes --> BLOCK["Blocked Sign-Off<br/>override recorded to audit log"]
    VERDICT -- no --> PROCEED(["Cleared Sign-Off"])

    classDef tag fill:#f1f5f9,stroke:#94a3b8,color:#475569;
    classDef input fill:#f8fafc,stroke:#64748b,color:#334155;
    classDef llm fill:#f0fdfa,stroke:#0d9488,color:#134e4a;
    classDef det fill:#ecfeff,stroke:#0891b2,color:#164e63;
    classDef block fill:#fef2f2,stroke:#dc2626,color:#991b1b;
    class S5,S1 tag;
    class I1,I2,REPORT,PROCEED input;
    class LA,LD,LO,LC llm;
    class KC,KI,KM,KX det;
    class DISP,MERGE,VERDICT det;
    class BLOCK block;
    style LLM fill:#f0fdfa,stroke:#0d9488,stroke-dasharray: 6 4,color:#134e4a;
    style KG fill:#ecfeff,stroke:#0891b2,stroke-dasharray: 6 4,color:#164e63;
```

---

## 3.11 Clinician User Interface Design (Stage 7 Delivery Surface)

The user interface was designed around a single constraint: it must fit inside a ten-minute
consultation and demand minimal cognitive overhead, while remaining fully transparent and auditable.
The clinician has to be able to see the system's reasoning, because they cannot be asked to trust, or
to be medico-legally accountable for, a process they cannot inspect.

> **[FIGURE 3.10: Doctor UI dashboard and CLI side by side.]**
> *Insert the two existing screenshots (`assets/doctor_ui_dashboard.png` and
> `assets/clinical_cli_terminal.png`) side by side, to show the shared SSE contract.*

### 3.11.1 Design philosophy and information architecture

The frontend is a Vite, React 18, and Tailwind single-page application organised as a four-step
consultation wizard (Input, Diagnosis, Care Plan, Output) that mirrors the clinician's existing
workflow. All consultation state lives in a single reducer-backed context (`AppContext`), and
session persistence was intentionally disabled, so that a page refresh resets to a clean state and no
previous patient's data can carry into the next consultation. The application shell nests its
providers deliberately, from `AuthProvider` (clinician identity, outermost) through `ThemeProvider`
and `AppProvider` (consultation state) to `ToastProvider`, so that every screen has the authenticated
clinician in scope and no consultation view can render without an identity.

Beyond the consultation wizard, the shell exposes a separate Clinical Performance analytics view
(route `/analytics`), driven by a single time-window selector, that aggregates volume, output, and
feedback metrics directly from the application store. It is documented here as a delivery surface
because it reads only persisted consultation data and never the live pipeline.

> **[FIGURE 3.10c: Clinical Performance analytics view.]**
> *Insert a screenshot of the `/analytics` view, showing the 7/30/90-day window selector together
> with the volume and approval-rate metric cards and the feedback-insights panel (most-amended CPGs
> and recent clinician comments).*

### 3.11.2 The four-step consultation UX flow

The wizard is the spine of the clinician experience, and its data flow was made precise about which
backend and which call fires at each step. This step-by-step contract is what prevents the expensive
reasoning stages from running before the clinician has committed to a differential.

> **[FIGURE 3.10b: Consultation wizard data flow.]**
> *Insert Mermaid diagram D-WIZARD (below). This figure shows only the four-step flow; the detailed
> per-step screens appear once each in their stage sections (Step 1 in Fig. 3.5, Step 2 in Fig. 3.6b,
> Step 3 in Fig. 3.8, Step 4 in Fig. 3.10d) and are not repeated here.*

- **Step 1, Data Input.** The clinician keys the patient's NRIC. For a returning patient, `syncMPIS`
  loads the prior-visit summary and current medications, and a read-only "Step 0" prep brief renders
  (§3.12). Vitals are captured (manually or by rPPG, §3.4.1), `startConsultation` creates the
  Supabase consultation row, and the Stage-2-only SSE call (`POST /clinical/plan/ddx/stream`) streams
  the differential.
- **Step 2, Diagnosis.** The clinician reviews the ranked DDx cards and selects the diagnoses to
  carry forward. Only on confirmation does the Stages 3 to 6 call
  (`POST /clinical/plan/resynthesize/stream`) fire, which is the first and only full plan generation
  (§3.13). An empty selection is blocked at three layers.
- **Step 3, Care Plan.** The streamed eight-section plan renders, the Stage 6 safety banner
  classifies and gates the flags, and the clinician edits inline (add, edit dose, start, stop,
  change, delete); the surviving items constitute the finalized prescription. `finalizePlan` persists
  the full plan, the safety flags, and the Stage 6 acknowledgement, and then triggers the prior-visit
  summariser.
- **Step 4, Output.** The plan is exported to PDF (`uploadCarePlanPDF`), and, with consent, "Send to
  patient" enqueues the deterministic Gmail delivery (§3.11.5), with delivery status polled until it
  reaches `sent` or `failed`.

**Diagram D-WIZARD, consultation wizard data flow (Fig. 3.10b):**

```mermaid
flowchart TB
    S1["Step 1 · Data Input<br/>intake + vitals (manual/rPPG)"]
    PREP[/"returning patient to syncMPIS<br/>+ read-only Prep Brief (Step 0)"/]
    S1 -. NRIC known .-> PREP
    S1 -->|startConsultation RPC| S1B["POST /clinical/plan/ddx/stream<br/>(Stage 2 only · SSE)"]
    S1B --> S2["Step 2 · Diagnosis<br/>clinician selects DDx"]
    S2 -->|selection >= 1 · 3-layer guard| S2B["POST /clinical/plan/resynthesize/stream<br/>(Stages 3–6 · SSE)"]
    S2B --> S3["Step 3 · Care Plan<br/>8-section render + safety banner + inline edit"]
    S3 -. clinician override .-> S2B
    S3 -->|finalizePlan to update_consultation| S3B["Prior-visit summariser (MiMo)"]
    S3 --> S4["Step 4 · Output<br/>PDF export to Gmail delivery"]

    classDef ui fill:#f0fdfa,stroke:#0d9488,color:#134e4a;
    classDef ro fill:#eef2ff,stroke:#6366f1,color:#3730a3;
    class S1,S2,S3,S4 ui;
    class PREP ro;
```

### 3.11.3 Real-time streaming as a design decision

Pipeline progress is streamed to the UI over Server-Sent Events rather than returned in a single
blocking response. This was a deliberate choice: the clinician watches the stages (differential,
routing, retrieval, synthesis, safety review) resolve live, which keeps the interface responsive
during the multi-second pipeline and makes the reasoning visible as it happens. The identical event
stream drives the terminal CLI, so the two surfaces cannot drift apart.

### 3.11.4 Transparency and auditable chain-of-thought

Transparency was treated as a first-class design requirement rather than a presentation feature,
because a clinician cannot be asked to trust, or to be medico-legally accountable for, a
recommendation whose derivation they cannot inspect. The system was therefore designed so that the
reasoning path of every consultation is exposed and reconstructable, and so that the chain of
intermediate decisions, not only the final plan, is visible to the clinician and recorded for
audit. This subsection documents how that chain of thought is produced, surfaced, and retained.

**The typed per-stage trace is the chain of thought.** The pipeline does not emit a single opaque
answer. Each stage emits typed SSE events as it runs (`stage_update`, `sub_step`, `ddx`,
`ddx_ready`, `routing`, `retrieval`, `graph_navigator`, `plan`, `safety_review`, `final_result`,
`out_of_scope`, and `clinician_override`), and during synthesis the model's reasoning tokens are
streamed as `thinking_delta` events. The ordered sequence of these events is the chain of thought
made concrete: it records what each stage decided and why, in the order the decisions were taken.
Because the same event stream is consumed by both the React UI and the terminal CLI, the trace is
identical regardless of surface.

**What each stage exposes.** Transparency was built into the data each stage emits, not bolted on
afterwards. Table 3.7 records the auditable output of each stage.

**Table 3.7: Per-stage transparency artifacts.**

| Stage | Reasoning artifact exposed |
|---|---|
| 2, DDx | The full ranked differential, each candidate carrying its `math_rank` (vector rank), its post-rerank position, the `rank_delta` between them, and an `override_reason` string when the LLM moved a candidate against the vector order |
| 3, Route | The matched CPG set with the `match_type` that admitted each one (exact, sibling, ancestor, semantic, and so on), plus the CPGs excluded by the sex-incompatibility filter, all recorded in the trace |
| 4, Retrieve | The queries that were issued and the evidence chunks returned, each chunk tagged with its source CPG section and MoH evidence grade |
| 4.5, KG inject | The "prefer Y" and "avoid X" edges that were injected, with their source guideline |
| 5, Synthesize | Every recommendation cites its `cpg_source` and evidence grade; `gate_audit` lists referrals that were considered and ruled out with the gate's reason; `unresolved_questions` and the assumption flags surface what the system could not resolve |
| 6, Critic | Every safety flag carries its `source` (`llm` or `graph`), `severity`, and the recommendation index it refers to, so the provenance of each concern is explicit in the audit trail |

**How the trace is surfaced in the UI.** Three complementary surfaces present this material at the
right level of detail. The `PipelineProgress` component renders the live per-stage event log as the
consultation runs, so the clinician sees the reasoning unfold. The `TraceDrawer` shared component
exposes the full ordered SSE event stream for inspection and debugging, which is the complete,
unabridged decision record. Per-recommendation citations and the dual-source safety provenance are
rendered inline on the care plan. To keep the scannable surface uncluttered while preserving
auditability, engineering detail is kept one click away rather than on the card face: each DDx card
shows only a qualitative High, Moderate, or Low tier badge, with the underlying score mathematics,
the `math_rank` to post-rerank delta, the clinical-override indicator, and the `override_reason`
placed behind a per-card "Why this rank?" disclosure. This design satisfies two goals at once, a
clean glanceable view for the time-pressured common case and a complete audit trail one interaction
away.

**Override controls keep the clinician in the loop.** Transparency is paired with control. The Stage
6 safety banner classifies each flag as `plan`, `current-only`, or `class-or-noise`, requires a
per-flag decision (Replace, Keep and acknowledge, or Remove) only for flags that touch a planned
medication, and gates the acknowledge button on every such decision being recorded. The acknowledged
decisions, together with the authenticated clinician's identity and a timestamp, are persisted as
the Stage 6 audit trail described in §3.10.2, so the override itself becomes part of the permanent
reasoning record rather than an undocumented action.

### 3.11.5 Delivery (Stage 7)

On sign-off the plan can be exported to PDF and, with patient consent, delivered by a deterministic
Gmail module (`delivery.py` together with a background worker polling a `delivery_jobs` table), with
no language model in the delivery loop. The email subject is validated against a PHI-token blocklist,
the body is localized (English, Malay, Chinese), and the job is retried up to three times before
being marked permanently failed.

> **[FIGURE 3.10d: Step 4 final care plan and PDF export.]**
> *Insert a screenshot of the wizard Step 4 (Output), showing the finalized care-plan summary, the
> export-to-PDF affordance, and the "Send to patient" delivery control with its status indicator.*

### 3.11.6 Application-data tier: Supabase (auth, patient records, persistence)

The Doctor UI's entire operational state is backed by Supabase (Postgres), accessed exclusively
through `src/lib/supabase.js` on the frontend. The separation is clean and bidirectional: the FastAPI
reasoning backend never touches Supabase (the sole exception is the background delivery worker, which
reads `delivery_jobs` through a direct asyncpg pool), and the Supabase layer never calls the backend.
Patient-identifiable data and clinical reasoning are therefore kept in different tiers with different
security postures, which is the reason this tier is documented with the UI that owns it rather than
with the reasoning stores of §3.2.2. The application schema is shown in Fig. 3.11b.

> **[FIGURE 3.11b: Application-store schema (Supabase / Postgres).]**
> *Insert an entity-relationship diagram of the application tables (`patients`, `consultations`,
> `live_vitals`, `human_signals`, `machine_signals`, `delivery_jobs`, and the prior-visit summary
> store), showing the `nric TEXT` and `consultation_id INTEGER` keys. Supabase renders this
> directly, so no SQL is required:*
> 1. *Open the Supabase dashboard and go to **Database → Schema Visualizer**.*
> 2. *Select the `public` schema; the ER diagram with foreign keys renders automatically.*
> 3. *Use the export control to download a PNG, or screenshot the diagram.*
> *Alternative (matches the Fig. 3.3b method): `pg_dump --schema-only --no-owner "$env:SUPABASE_DB_URL" > supabase_schema.sql`, then **Import → PostgreSQL** at <https://dbdiagram.io> and export.*

- **Clinician authentication.** Supabase Auth provides the identity layer (`signIn`, `getSession`,
  `onAuthStateChange`, `signOut`), wrapped by the `AuthProvider` that sits outermost in the provider
  tree (§3.11.1). The authenticated clinician's identity is what later signs the Stage 6 safety
  acknowledgement and the patient PDF cover, so authentication is load-bearing for the medico-legal
  audit trail, not merely for access control.
- **Patient records.** Patient create, read, and update operations flow through stored-procedure
  RPCs rather than raw table writes, namely `search_patient_v2` (NRIC lookup), `register_patient`,
  `update_patient_from_mpis`, `push_patient_vitals`, and `update_patient_medications`. Routing the
  CRUD operations through RPCs keeps the data-access contract in one auditable place.
- **Consultations and continuity.** A consultation row is created by `start_consultation`, which
  returns the integer `consultation_id` and `consultation_number`, updated by `update_consultation`
  with the full care plan, the safety flags, and the Stage 6 acknowledgement audit, and closed out by
  `update_prior_visit_summary_bypass`, which is the persistence half of the longitudinal loop in
  §3.12.
- **Vitals.** Step-1 vitals (manual or rPPG) are written once per consultation to a `live_vitals`
  table (one row per consultation, upserted on conflict), and a trigger mirrors each row into the
  patient's longitudinal vitals history.
- **Realtime metrics.** Dashboard surfaces subscribe to Supabase `postgres_changes`, so that volume,
  approval-rate, and feedback tiles refresh live as consultations are written.

> **Schema note (design constraint):** `consultations.id` is an `INTEGER`, and the `patients`
> primary key is `nric TEXT` (there is no patient `id` column). Every foreign key and RPC parameter is
> typed to match, a constraint that any future migration must respect.

---

## 3.12 Returning-Patient Longitudinal Design

A core design objective was that the patient should be represented as a persistent typed object
rather than a fresh prompt on each visit. Two language-model steps, both sitting outside the Stage 2
to 6 pipeline, provide the system's longitudinal memory. Neither step runs for a first-time patient,
and both fail open.

> **[FIGURE 3.11: Returning-patient memory loop.]**
> *Insert Mermaid diagram D-MEMORY (below), together with a screenshot of the read-only
> PrepBriefCard shown above the intake form for a returning patient.*

- **Prior-visit summariser (MiMo).** At sign-off, and only at sign-off rather than on every save, the
  finished consultation is compressed into a five-field `PriorVisitSummary` (visit date, prior
  primary ICD, plan summary, key-labs delta, and what changed), under hard character caps and a
  prompt that forbids invention. It is persisted to Supabase and auto-loaded on the next visit, where
  it is injected into both Stage 4 query generation and Stage 5 synthesis.
- **Pre-consultation prep brief (Gemini Flash).** When a clinician keys the NRIC of a returning
  patient, a read-only "Step 0" briefing fires before the wizard, producing three telegram-style
  fields (since last visit, medication watch-outs, and what to ask today), each capped at 120
  characters. It is strictly read-only: it produces no input to the diagnostic pipeline and is gated
  so that it cannot render for a first-time patient.

The summariser compresses a finished visit, and the prep brief expands that record into a clinician
orientation at the start of the next visit. These are two distinct jobs served by two models.

**Diagram D-MEMORY, returning-patient longitudinal loop (Fig. 3.11):**

```mermaid
flowchart TB
    subgraph V1["Visit N · full consultation"]
        P1[Stage 2–6 pipeline] --> F1[Clinician signs off]
        F1 --> SUM["Prior-visit summariser · MiMo<br/>5-field PriorVisitSummary"]
    end
    SUM -->|RPC bypass| DB[("Supabase<br/>prior_visit_summary")]
    subgraph V2["Visit N+1 · returning patient"]
        K[Clinician keys NRIC] --> LOAD["Load latest summary"]
        LOAD --> PREP["Prep-brief LLM · Step 0 · Gemini Flash<br/>3 fields, <= 120 chars"]
        PREP --> CARD[/PrepBriefCard · read-only<br/>never touches Stage 2–6/]
        LOAD -. prior_visit injected .-> PIPE["Stage 4 query-gen + Stage 5 synthesis"]
    end
    DB --> LOAD

    classDef agent fill:#f0fdfa,stroke:#0d9488,color:#134e4a;
    classDef store fill:#f8fafc,stroke:#64748b,color:#334155;
    classDef ro fill:#eef2ff,stroke:#6366f1,color:#3730a3;
    class SUM,PREP agent;
    class DB store;
    class CARD ro;
```

---

## 3.13 Clinician Override and Re-Synthesis Design

The plan flow was deliberately split into two HTTP calls so that the clinician confirms the
differential diagnosis before the system commits to the more expensive Stages 3 to 6. This enacts the
design's central principle — the clinician, not the model, is the decision-maker:

```
Step 1 (Data Input)     POST /clinical/plan/ddx/stream          (Stage 2 only)
Step 2 (DDx selection)  POST /clinical/plan/resynthesize/stream (Stages 3–6)
Step 3 (Care Plan)      renders the audited plan
```

The split is a core design decision rather than an optimisation: it guarantees that the authoritative
care plan is never generated against a diagnosis the clinician has not seen and confirmed.

**Defence in depth against empty selection.** Because an empty diagnosis selection would route nothing
and degrade silently to `out_of_scope`, it is blocked at three independent layers: a disabled-button
gate validated against the live candidate set; a submit guard that raises a visible banner; and an API
contract that rejects an empty selection with HTTP 422 before any language-model cost is incurred. A
separate contract requirement holds the re-synthesis path to the same comorbidity routing as the
one-shot path, so that the clinician UI and the evaluation scripts cannot produce clinically different
plans from identical input.

**Inline editing as the in-the-loop check.** Once the plan is rendered at Step 3, the clinician
retains full editorial control: any recommendation can be added, modified, or removed on the plan
surface, and each CRITICAL or MAJOR safety flag is resolved through an explicit per-flag decision
(Replace, Keep and acknowledge, or Remove). These edits and decisions update the working plan and are
persisted with the finalised consultation. The dual-source safety review runs once, during the Step-2
resynthesis; at Step 3 the clinician is the safety check, and every flag that touches a planned
medication must carry a recorded decision before the plan can close.

**Safety-acknowledgement gate.** So that a flagged hazard can never be silently shipped, the plan
cannot be finalised until every CRITICAL or MAJOR flag touching a planned medication has an explicit
decision; the approval control stays disabled until the set is resolved. Each decision is persisted
with the acknowledging clinician's identity and a timestamp on the consultation row (`safe_to_proceed`,
`safety_acknowledged`, `_by`, `_at`), forming the medico-legal audit trail described in §3.11.5.

**Override signalling.** When the clinician's Step-2 selection differs from the AI's top pick, the
resynthesis stream emits a single `clinician_override` event as its first event, carrying the
clinician-selected codes and the designated major diagnosis. This marks the trace explicitly as
clinician-directed, so both the reasoning log and the UI record that the plan was generated against
the clinician's choice rather than the model's — closing the loop between the human decision and the
machine's subsequent reasoning.

---

## 3.14 Fail-Loud, Degradation, and Anti-Hallucination Design

The system was engineered to fail loudly on absent evidence and to fail open on infrastructure
unreliability. These two postures are deliberately opposite and are encoded in the codebase as a
contract validated by a dedicated degradation test suite. The governing principle throughout is that
the system declares degraded output rather than concealing it. Table 3.14.1 sets out each contract.

**Table 3.14.1: Degradation and anti-hallucination contracts.**

| Condition | System response | Why |
|---|---|---|
| Stage 4 retrieval throws an exception | Skip Stage 5; return a zero-confidence (`0.0`) plan, with the failure noted in `unresolved_questions` | Never build a plan on absent evidence |
| Stage 4 succeeds but returns no chunks | Still synthesise, but cap confidence at ≤ `0.25` and append an empty-evidence note | An empty result differs from an exception — graded by degree (`0.0` vs ≤ `0.25`) so neither reads as confident |
| Data-store connection error | Return HTTP `503`, not a generic `500` | Flags a transient outage as retryable, distinct from a logic fault |
| LLM emits an ICD code in the DDx | Discard the code; resolve diagnoses only by name-to-code vector lookup | Model-emitted codes are untrusted; codes must come from a controlled source |
| An `unresolved_question` claims a field is missing that is actually present | Drop the entry before returning the plan | A synthesis artefact that would mislead the clinician about what data exists |
| False contraindication edges during relation extraction | Filtered out at ingestion by the §3.3.1 guardrails | Stage 6 should verify against a clean graph, not patch errors at runtime |

---

## 3.15 Observability and Offline Resilience Design

Because the target deployment is a rural clinic with unreliable power and connectivity, the pipeline
was engineered to be observable and recoverable. Five layers provide this capability
(`backend/agent/offline_log.py` and the surrounding orchestration):

1. **Rotating SSE event log.** Every event is written to disk (10 MB across five rotating files)
   before it is streamed, so that a frontend crash after the stream closes loses nothing.
2. **Append-only failed-job log.** Every pipeline failure is recorded as a JSONL record and can be
   replayed with `scripts/replay_failed_jobs.py`.
3. **Correlation IDs.** An `X-Request-ID`, taken from the request header or generated as a fresh
   UUID, stamps every log line, SSE event, failed-job record, and database row, so that a single
   identifier links the entire lifecycle of one consultation.
4. **Per-stage timings.** The `pipeline_timings` are persisted as JSONB after the final result, both
   for performance auditing and as the source of the sub-minute latency figure.
5. **LLM health probe.** The `/health` endpoint pings the synthesis and safety-critic endpoints with
   a 2 s timeout and reports each as `ok`, `degraded`, or `unknown`.

Together with the fail-open posture of Stages 4.5 and 6, these layers ensure that an unreliable
connection degrades the system gracefully and recoverably rather than silently dropping a clinical
concern.

---

## 3.16 Feedback Ecosystem (Layer 3) Design

A feedback ecosystem was built to capture real-world clinician and pipeline signals for offline
analysis, without touching the Stage 2 to 6 reasoning outputs. This was a deliberate decision,
because keeping feedback out of the live path means that changes here require no re-validation of the
pipeline. Two append-only Supabase tables back it:

- **`human_signals`** records the clinician's approve, reject, or regenerate action and free-text
  comment from the care-plan approval box, written by a direct insert that deliberately bypasses the
  overload-prone consultation RPC, together with whether a blocked plan was overridden.
- **`machine_signals`** records pipeline insights that the workflow already computes but previously
  discarded (gate failures, coverage gaps, and stage errors), harvested once per consultation.

Both feeds surface in a client-side-aggregated analytics dashboard and are append-only and fail-open:
an empty database renders empty states rather than mocked data. This "Layer 3" approach was chosen
over an in-pipeline semantic cache precisely because it is out of band and therefore safe to iterate
on independently of the reasoning path.

---

## 3.17 Prompt-Engineering Methodology

Each language-model step has its own instruction file, kept separate from the program code so the exact
wording behind any decision can be reviewed on its own. Nothing is hidden in later processing, which is
what makes the system's reasoning auditable end to end. Five controls do the work:

- **Fixed output format.** Models must answer as a structured object, automatically checked before use;
  anything malformed is rejected rather than shown to the clinician as a half-finished plan.
- **Override rules.** The treatment-planning prompt opens with seven rules that outrank everything
  else: cite a source or say "unknown"; copy doses exactly; don't repeat medical myths; flag when two
  guidelines conflict; refuse to turn a population statistic into a personal risk figure; don't
  over-treat stable conditions during an emergency; and treat patient notes as information, never as
  instructions.
- **Names, not codes.** The model proposes disease *names* and picks only from a supplied shortlist of
  codes — never writing a code from memory — so invented codes are impossible by design.
- **Self-checking.** Prompts require the model to audit its own answer against a checklist, and to name
  one finding that argues *against* its top diagnosis, forcing real reasoning over rubber-stamping.
- **Independent safety review.** The final step acts as a separate pharmacist who hasn't seen how the
  plan was made; it must raise a concern even if the plan already addresses it — double-checking, not
  confirming.

Underpinning all five, model settings are fixed (pinned seed, zero temperature) so the same input
reliably produces the same output.

---

> **Figure checklist (for the report author):**
> - **Fig. 3.1:** full 7-stage architecture (Mermaid D-ARCH), the primary architecture figure, full
>   width.
> - **Fig. 3.2:** pipeline overview with branches (Mermaid D-FLOW).
> - **Fig. 3.3:** technology-stack logo strip.
> - **Fig. 3.3b:** vector-store schema, pgvector ER diagram (generate via pg_dump to dbdiagram.io).
> - **Fig. 3.3c:** knowledge-graph safety subgraph, Neo4j screenshot (Query 3, Warfarin).
> - **Fig. 3.3d:** knowledge-graph edge provenance, Neo4j edge-property panel screenshot.
> - **Fig. 3.4:** CPG ingestion pipeline (Mermaid D-INGEST).
> - **Fig. 3.5:** Step 1 intake and vitals screenshot.
> - **Fig. 3.5b:** rPPG signal-processing pipeline (Mermaid D-RPPG) with RPPGScanModal screenshot.
> - **Fig. 3.6:** Stage 2 DDx sub-pipeline (Mermaid D-DDX) or Step 2 screenshot.
> - **Fig. 3.7:** WHO ICD-11 browser — Heart-Failure block hierarchy and exclusions (screenshot).
> - **Fig. 3.7b:** nine-tier deterministic routing cascade (Mermaid D-ROUTE).
> - **Fig. 3.7c:** Stage 4 evidence-graded scoped retrieval (Mermaid D-RETRIEVE).
> - **Fig. 3.8:** Step 3 care-plan renderer screenshot.
> - **Fig. 3.8b:** pregnancy contraindication fan-out, KG "avoid" arm (Neo4j screenshot, pregnancy query).
> - **Fig. 3.9:** Stage 6 safety-acknowledgement banner screenshot.
> - **Fig. 3.9b:** Stage 6 dual-source safety critic (Mermaid D-CRITIC).
> - **Fig. 3.10:** Doctor UI and CLI side-by-side screenshots.
> - **Fig. 3.10b:** consultation wizard data flow (Mermaid D-WIZARD) with the four step screenshots.
> - **Fig. 3.11:** returning-patient memory loop (Mermaid D-MEMORY) with PrepBriefCard screenshot.
> - **Fig. 3.11b:** application-store schema, Supabase Schema Visualizer ER diagram.
>
> All Mermaid sources render at <https://mermaid.live>; export SVG at high scale for print. The
> colour convention used throughout is: teal for an LLM reasoning step, cyan for a deterministic
> step, amber for the safety-critic agent, red for a stop or block, and a slate cylinder for a data
> store.
