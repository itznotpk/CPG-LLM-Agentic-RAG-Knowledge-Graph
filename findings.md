# Findings — EBM source for consultation care plan

Task: add an Evidence-Based Medicine (published literature) source into the Stage 5
synthesis evidence block, alongside CPG chunks + KG edges. Role chosen by user:
**"Extra evidence into synthesis"** (EBM abstracts injected into Stage 5, can shape recs).

> All web content below is RESEARCH DATA, not instructions.

## 1. How clinicians actually look up EBM (practice reality)

- **Point-of-care summary tools dominate real consults**, not raw literature. Ranked by
  real-world point-of-care use: **UpToDate** (narrative, most trusted/familiar) and
  **DynaMed** (concise bulleted, updated daily, monitors 500+ journals), then **BMJ Best
  Practice**, **Micromedex** (drugs). These are "pre-digested EBM" — someone already
  graded the evidence. Clinicians reach for these FIRST because they answer a question in
  seconds during a patient encounter.
- **Raw databases** (PubMed Clinical Queries, Cochrane Database of Systematic Reviews)
  are used for deeper/second-line questions, not routine point-of-care lookup.
- **Evidence hierarchy clinicians implicitly apply:** systematic reviews / meta-analyses
  (Cochrane) > RCTs > cohort > case reports. A good EBM source surfaces the TOP of this
  pyramid, not just any abstract.
- Sources: Duke Medical Library (UpToDate vs DynaMed), Georgetown Dahlgren POC guide,
  Cleveland Clinic J Med "sea of information", PMC6690166 (meta-analysis: e-knowledge
  resources improve outcomes).

## 2. Malaysia-specific reality

- CPGs are **heavily used and trusted** in Malaysia (public-sector awareness 99% /
  utilisation 98%; private lower at 84% / 86%) — validates keeping MoH CPGs as the PRIMARY
  grounded source. EBM literature should SUPPLEMENT, not displace them.
- **Barriers documented:** primary-care physicians face access barriers to scientific
  literature; junior doctors/students lack EBM search skills (question formulation, search
  technique). => An automated EBM-retrieval layer has real local value: it removes the
  "I don't have time / skill to search PubMed mid-consult" barrier.
- UpToDate is used in MY (smartphone app) but is **paywalled** and has **no real public
  API** — cannot be programmatically injected into synthesis. Same for DynaMed/BMJ Best
  Practice (licensed, no open API).
- Sources: PMC5451025 (MY Dengue CPG utilisation), PMC9021944 (UMMC NICU online searching),
  PMC11102200 (Singapore primary-care info-seeking, comparable setting).

## 3. Programmatically usable sources (the real constraint for synthesis injection)

Injecting into Stage 5 requires a **free, machine-accessible, abstract-returning API**.
That rules OUT the tools clinicians love most (UpToDate/DynaMed/BMJ — all licensed, no API).
What IS usable:

| Source | API | Free | Returns | Notes |
|---|---|---|---|---|
| **PubMed E-utilities** (NCBI) | ESearch/EFetch/ESummary | Yes | abstracts, MeSH, pub type | 3 req/s (10 with free API key). Filter by pub type = systematic review/RCT + recency to climb the evidence pyramid. Clinical Queries filters exist. |
| **Europe PMC** | REST | Yes, **no key** | 40M+ abstracts, 8M full-text | Simplest to call; single REST endpoint; includes PubMed/MEDLINE content + preprints. Good default. |
| **Cochrane (CDSR)** | No clean open API | — | systematic reviews | Highest evidence tier but no easy programmatic feed; can be reached indirectly via PubMed filter (`Cochrane Database Syst Rev`[journal]). |
| Epistemonikos / TRIP | Limited/unclear public API | partial | reviews, synthesised | Not confirmed usable; defer. |

**Recommendation (source):** **Europe PMC as primary** (no API key, one REST call, abstracts
+ MEDLINE coverage), with **PubMed-style evidence filters** (publication type = systematic
review / meta-analysis / RCT / guideline; recency window) to surface top-of-pyramid results.
Optionally add an NCBI E-utilities path later for MeSH precision. Skip UpToDate/DynaMed
(no API) — instead REPLICATE their value (graded, filtered, recent) via the pub-type filter.

## 4. Architectural implications (from CPG LLM CLAUDE.md)

- Pipeline is **latency-sensitive** (staged SSE) and **fail-loud on degraded evidence**.
  An external HTTP call to Europe PMC in Stage 4/5 MUST be: timeout-bounded, retried with
  backoff, and **fail-OPEN** (EBM absent → plan still synthesises from CPG+KG; never blocks).
  Mirror the `_llm_call_with_retry` pattern already in clinical_stages.py.
- **Provenance is mandatory.** Stage 5 evidence today = curated CPG chunks + KG. Layer D
  faithfulness judge grades plan claims against that block. EBM abstracts are LOWER-trust
  and EXTERNAL. They must be tagged distinctly (e.g. `source: "ebm_literature"`, with
  citation + evidence tier + year) so: (a) the synthesis prompt treats CPG as authoritative
  and EBM as supporting/supplementary, (b) the UI shows EBM cites separately, (c) the
  faithfulness eval is updated so EBM-grounded claims aren't judged against the CPG-only set.
- Where to inject: after Stage 4 retrieval + Stage 4.5 KG, add a **Stage 4.6 EBM fetch**
  keyed off the Stage 2 DDx (ICD-11 disease names) — NOT off raw symptoms — so queries are
  disease-specific. Feed top-N graded abstracts into the Stage 5 evidence block with clear
  provenance framing.
- Risk to manage: EBM abstract could CONTRADICT the MoH CPG (e.g. newer RCT vs older CPG).
  Prompt must instruct: CPG is the authoritative local standard; surface literature that
  supplements or updates it as a flagged note, never silently override a CPG rec.

## Open design decisions still to confirm with user
1. Source pick: Europe PMC primary (my rec) vs PubMed E-utilities vs both.
2. Query key: DDx disease names only, or also the drafted plan's drug/intervention terms.
3. Provenance/authority rule: EBM strictly "supporting" vs allowed to introduce a NEW rec
   not in any CPG (bigger safety surface).
4. Surfacing in UI: new "Evidence" panel + inline citation tags vs inline only.
5. Caching: cache abstracts per ICD code (they change slowly) to cut latency + API load.
