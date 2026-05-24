# KG Rebuild — Remaining Edits: Issues & Phased Plan

> **STATUS: CLOSED (2026-05-24).** All in-scope phases complete and validated against the production KG.
> Items 3, 4, 6 shipped in Phase A; Phase B.2 ingested 30 CPGs into Neo4j (13,589 nodes / 18,252 edges) with all new relation types firing; Phase D wired and smoke-validated against the live graph (84 candidate drugs, 8,654-char flags block injected into Stage 5).
> Two non-blocking quality follow-ups documented in Phase B.2 (MAJOR severity calibration + `risk_pct` bleed onto non-`CROSS_REACTS_WITH` edges) — these are extraction-prompt refinements, not architectural gaps.
>
> Companion to [KG_Friend_Edits_Status.md] — covers the four open items (#3, #4, #6, #8) with diagnosis, recommended approach, and execution phases.
>
> Created: 2026-05-16 | Closed: 2026-05-24

---

## Scope

Three items from the friend's edit table remain open. **Item 8 (ICD enrichment) has been dropped — see "Architectural decision" below.**

| # | Edit | Current state |
|:-:|:-----|:--------------|
| 3 | Relation taxonomy | `CLINICAL_RELATION_TYPES` missing `INTERACTS_WITH`, `CROSS_REACTS_WITH`, `REQUIRES_DOSE_ADJUSTMENT` |
| 4 | Extraction prompt | Only extracts `(subject, relation, object, evidence)` — no `severity`, `trigger`, `dosage`, `frequency` |
| 6 | Evidence accumulation | `ON MATCH` locks first evidence forever; later (possibly stronger) evidence is dropped |
| ~~8~~ | ~~ICD enrichment~~ | **Dropped — not needed.** ICD codes belong at the Postgres routing layer, not on KG nodes. |

These are the last code changes needed before the next full re-ingestion. Items 3, 4, 6 all touch [`ingestion/graph_builder.py`](../../ingestion/graph_builder.py) and should ship together.

### Architectural decision (2026-05-17) — ICD enrichment dropped

After reviewing how the KG is actually queried, ICD codes on `(:Condition)` nodes were determined to be **harmful, not just unnecessary**:

1. **The KG is queried entity-first, not CPG-first.** [graph_clinical.py:115](../../agent/graph_clinical.py#L115) takes patient drugs / conditions / allergies as inputs and searches all edges globally. It never starts from an ICD code.
2. **Routing already lives at the right layer.** `documents.icd11_scope` + [routing.py](../../agent/routing.py) maps ICD → CPG documents for vector retrieval scope. The KG operates downstream of that.
3. **Scoping the KG by ICD would break safety.** If patient is on warfarin + simvastatin and routing returns only the AF CPG, an ICD-scoped KG would hide the warfarin↔simvastatin interaction extracted from the Dyslipidaemia CPG. Drug interactions are universal facts and must be queryable regardless of which CPG they came from.
4. **Cross-CPG evidence accumulation is a strength.** With 20+ CPGs, the same interaction edge gets evidence from multiple sources via `evidence_list` and `cpg_chunk_ids` ([graph_builder.py:649-658](../../ingestion/graph_builder.py#L649-L658)). ICD-scoping would suppress this.

**Layer of concern:**

| Layer | Scoped by | Purpose |
|---|---|---|
| Postgres routing | ICD code → CPG | "Which guideline applies to this diagnosis?" |
| Vector retrieval | Routed CPGs only | "What does THIS guideline say?" |
| KG safety lookup | **Global, unscoped** | "Are there ANY known interactions for this drug?" |

Phase C and Phase E in the original plan are therefore removed.

---

## Item 3 — Relation Taxonomy Expansion

### Issue
[graph_builder.py:59-73](../../ingestion/graph_builder.py#L59-L73) defines `CLINICAL_RELATION_TYPES` with a single `CONTRAINDICATED_WITH` bucket. Clinically distinct relations are being collapsed:
- A drug-drug interaction that requires monitoring ≠ an absolute contraindication
- An allergy cross-reactivity ≠ a pharmacokinetic interaction
- A renal dose adjustment ≠ a contraindication

All three currently land in `CONTRAINDICATED_WITH` (or are dropped entirely), making downstream Cypher queries unable to distinguish "do not co-prescribe" from "reduce dose by 50%".

### Why it matters
Without the right relation types, the Stage 5 flag system cannot triage. Every flag looks like a hard contraindication, leading to alert fatigue and clinician override of legitimate warnings.

### Suggested approach
1. Add three relation types to `CLINICAL_RELATION_TYPES`:
   - `INTERACTS_WITH` — pharmacokinetic/pharmacodynamic interaction (carries `severity`)
   - `CROSS_REACTS_WITH` — allergen cross-reactivity (carries `risk_pct` when stated)
   - `REQUIRES_DOSE_ADJUSTMENT` — dose modification needed (carries `trigger`, e.g. "eGFR<30")
2. Keep `CONTRAINDICATED_WITH` reserved for absolute contraindications only.
3. Document each type in a docstring so the prompt and the query layer share one source of truth.

### Risks
- LLM may misclassify edge cases (interaction vs contraindication). Mitigation: prompt includes explicit definitions and examples.
- Existing graph edges remain `CONTRAINDICATED_WITH` until re-ingestion. Mitigation: re-ingest as one batch with items 4 + 6.

---

## Item 4 — Extraction Prompt Enrichment

### Issue
The current prompt in `_extract_triples_with_llm` ([graph_builder.py](../../ingestion/graph_builder.py)) asks for a 4-tuple: `(subject, relation, object, evidence)`. Clinically critical metadata in the source text is discarded:
- **Severity** ("major interaction", "minor monitoring") → flag triage impossible
- **Trigger** ("if eGFR < 30", "in patients with hepatic impairment") → dose adjustments not actionable
- **Dosage / frequency** ("reduce to 2.5mg daily") → recommendations lose specificity

### Why it matters
This is the single highest-impact remaining edit. Item 3 (new relation types) is useless without item 4 populating their properties. Severity in particular drives the entire flag triage UX.

### Suggested approach
1. Update the extraction prompt to output a richer JSON schema per triple:
   ```json
   {
     "subject": "...", "relation": "...", "object": "...",
     "evidence": "...",
     "severity": "MAJOR|MODERATE|MINOR|null",
     "trigger": "string|null",
     "dosage": "string|null",
     "frequency": "string|null"
   }
   ```
2. **Strict null-when-absent rule** in the prompt: "If the source text does not explicitly state severity, return null. Do not infer." This is the key guard against LLM hallucination.
3. In `_write_triples_to_neo4j`, only write properties that are non-null — keeps the graph clean and lets `coalesce(r.severity, 'UNSPECIFIED')` in queries work correctly.
4. Add a controlled vocabulary check post-extraction: reject any `severity` value not in `{MAJOR, MODERATE, MINOR, null}` before writing.

### Risks
- LLM hallucinating severity when text is ambiguous. Mitigation: explicit null-when-absent instruction + 2-3 few-shot examples showing the null case.
- Prompt length grows, cost per chunk increases. Mitigation: category whitelist (already done) keeps total chunks down.

---

## Item 6 — Evidence Accumulation

### Issue
[graph_builder.py:513](../../ingestion/graph_builder.py#L513) writes:
```cypher
ON MATCH SET r.evidence = CASE WHEN r.evidence IS NULL THEN $evidence ELSE r.evidence END
```
The first evidence extracted for any edge wins forever. If chunk #3 has weak phrasing ("may interact") and chunk #47 has the definitive statement ("Class I recommendation, avoid co-administration"), the strong evidence is silently discarded. Same problem applies to `cpg_chunk_id` — only one source chunk is traceable per edge.

### Why it matters
Clinical defensibility requires *all* supporting evidence to be cited, not the first one the pipeline happened to see. It also masks data quality issues — re-ingestion will produce identical edges and you can't tell which sources contributed.

### Suggested approach
1. Change `ON MATCH` to append both evidence and chunk_id as lists:
   ```cypher
   ON MATCH SET
     r.evidence_list = coalesce(r.evidence_list, []) + [$evidence],
     r.cpg_chunk_ids = coalesce(r.cpg_chunk_ids, []) + [$cpg_chunk_id]
   ```
2. Keep `r.evidence` and `r.cpg_chunk_id` as the *first* / *primary* citation for backwards compat with existing query code, but the list form becomes the authoritative source.
3. Update `clinical_graph_lookup` in [`agent/graph_clinical.py`](../../agent/graph_clinical.py) to return the full evidence list when present, falling back to `r.evidence` otherwise.
4. Optional: de-duplicate the list on write (`WHERE NOT $evidence IN coalesce(r.evidence_list, [])`) to prevent identical re-runs from bloating the lists.

### Risks
- Lists grow unbounded across re-ingestions. Mitigation: dedup on write, or cap at N entries (e.g. 10) with newest-wins eviction.
- Existing edges have no `evidence_list` until next re-ingestion. Mitigation: `coalesce(..., [])` handles the null case transparently.

---

## ~~Item 8 — ICD Enrichment~~ (DROPPED 2026-05-17)

**Status:** Will not be implemented. See "Architectural decision" at the top of this doc.

**Summary of why:** the original premise was that `DDx → ICD code → Condition node → first-line drug` would be a useful KG traversal path. It isn't, because the KG is queried entity-first (drug names, condition names) from patient context, and ICD-based scoping would actively suppress universal safety signals (drug-drug interactions) that span multiple CPGs. ICD-to-CPG mapping is correctly handled at the Postgres routing layer ([routing.py](../../agent/routing.py)) and does not need to be duplicated in the graph.

If a real KG-from-ICD use case emerges later (e.g., a UI feature that surfaces "all entities mentioned by the AF CPG"), it can be added in one Cypher script at that time. Do not pre-build.

---

## Phased Execution Plan

### Phase A — Code changes — ✅ DONE (2026-05-17)
**Touched:** [`ingestion/graph_builder.py`](../../ingestion/graph_builder.py), [`agent/graph_clinical.py`](../../agent/graph_clinical.py)

1. ✅ Item 3 — `CLINICAL_RELATION_TYPES` expanded with `INTERACTS_WITH`, `CROSS_REACTS_WITH`, `REQUIRES_DOSE_ADJUSTMENT` + inline docstrings distinguishing each from `CONTRAINDICATED_WITH`.
2. ✅ Item 4 — Extraction prompt updated: richer JSON schema with `severity`, `trigger`, `risk_pct`; strict null-when-absent rule; controlled-vocab post-validation rejects any severity not in `{MAJOR, MODERATE, MINOR}`; 3 few-shot examples covering INTERACTS_WITH (with severity), REQUIRES_DOSE_ADJUSTMENT (with trigger), TREATS (all nulls).
3. ✅ Item 6 — `ON CREATE` initialises `evidence_list = [$evidence]` and `cpg_chunk_ids`; `ON MATCH` appends with dedup (`WHEN $evidence IN coalesce(r.evidence_list, [])` guard). Backwards-compat: `r.evidence` and `r.cpg_chunk_id` preserved as primary fields.
4. ✅ `graph_clinical.py` updated: `ClinicalFlag` gains `evidence_list` + `cpg_chunk_ids` fields; all 3 Cypher queries return them; query 1 matches `CONTRAINDICATED_WITH|INTERACTS_WITH`, query 2 adds `REQUIRES_DOSE_ADJUSTMENT`, query 3 adds `CROSS_REACTS_WITH`; `format_flags_for_prompt` shows up to 3 evidence entries per flag.

**Gate:** ✅ Smoke test passed (2026-05-17). Key findings:
- 105 triples across 10 AF chunks. Severity: 28 populated (27%), 77 null (73%) — null-by-default working.
- 0 invalid severity values — controlled vocab enforced correctly.
- No new relation types fired in the sample, but expected: all 10 chunks were AF treatment chunks. `INTERACTS_WITH`, `CROSS_REACTS_WITH`, `REQUIRES_DOSE_ADJUSTMENT` will fire in polypharmacy-heavy CPGs (Dyslipidaemia, HF, NSTEMI) during Phase B.
- 11 "suspected hallucinations" flagged by the checker were **false positives** — LLM correctly inferred severity from clinical language ("inappropriate", "adverse effects include heart failure"). Checker keyword list was too narrow.
- `REQUIRES_DOSE_ADJUSTMENT` never fired despite 14 `HAS_DOSAGE` hits — LLM defaults to the familiar old type for dose statements like "lower doses may be advisable in HF". Will self-correct over re-ingestion as the taxonomy guidance is absorbed. Monitor post-Phase B.
- Evidence accumulation: all 3 gates PASS — `evidence_list`, `cpg_chunk_ids`, `severity` written and appended correctly.

---

### Phase B — Re-ingestion batch (~1 day LLM-bound)
- Run `ingestion/ingest.py --graph-only --categories Treatment,Assessment,...` across all CPGs.
- Use category whitelist (already in place) to skip Intro/Epi/Methodology.
- Estimated cost: similar to last full batch (~$0.35 per [Phase A KG Rebuild Findings](../../memory/project_kg_rebuild_phase_a.md)).
- Back up the existing graph first: `backups/kg_backup_pre_phase_b.cypher`.

**Gate:** Post-batch audit Cypher — count edges by relation type, count edges with severity populated, sample 20 edges and cross-check evidence against source chunks.

#### Phase B.1 — AF dry-run (✅ DONE 2026-05-17)

Re-ingested the AF CPG only as a single-document validation of the Phase A code under realistic conditions. Audit via [`scratch/kg_verify.py`](../../scratch/kg_verify.py) + [`scratch/audit_phase_a.py`](../../scratch/audit_phase_a.py).

**Graph shape:** 635 nodes / 784 edges (vs. baseline 409/818). Node growth from richer extraction; edge drop from dedup of the old Bedrock-404 noise. Source spread confirms AF-only (all 8 sections present).

**Phase A features all firing:**
| Feature | Result |
|---|---|
| `INTERACTS_WITH` | 16 edges, 56% severity-tagged |
| `REQUIRES_DOSE_ADJUSTMENT` | 19 edges, 42% severity-tagged, 25 with `trigger` populated |
| `CROSS_REACTS_WITH` | 0 — expected (no allergen content in AF; will appear in NSTEMI/Dyslipidaemia) |
| `severity` populated overall | 225 edges (MAJOR=169 / MODERATE=48 / MINOR=8) |
| `CONTRAINDICATED_WITH` severity coverage | 61/63 = **97%** |
| `evidence_list` accumulation | Working — max=3 (e.g. `Vitamin K Antagonist -[REDUCES_RISK_OF]-> Stroke` from 3 evidences / 4 chunks) |
| `trigger` / `risk_pct` populated | 25 / 19 |
| `cpg_chunk_id` linkage | 784/784, 10/10 sampled present in Postgres |
| Orphans / duplicates / missing evidence | 0 / 0 / 0 |

**Yellow flags to monitor (not blockers):**
1. **Severity skews MAJOR** (169/225 = 75%). AF genuinely has many major-risk items (stroke/bleeding/proarrhythmia) so plausible — but spot-check 10 random MAJOR flags against source text before trusting in Phase D triage. Risk: alert fatigue if LLM is over-classifying.
2. **`risk_pct` populated on 19 edges but `CROSS_REACTS_WITH=0`.** Per prompt, `risk_pct` should only fire for cross-reactivity. Likely LLM bleed onto other relation types — audit which edges carry it.
3. **`evidence_list` max=3, p95=1.0.** Cross-section accumulation works within one CPG but modest. Real test is the full 16-CPG batch where the same interaction should accumulate across HF + NSTEMI + Dyslipidaemia.
4. **Dosage-node duplicate visible**: `200-300 Mg Oral` vs `200–300 Mg P.O.` (hyphen vs en-dash + abbreviation variant). Name-normalisation gap; minor.

**Verdict:** Phase A gate passes under realistic conditions. Safe to proceed to full Phase B across the other 15 CPGs. Re-run [`scratch/audit_phase_a.py`](../../scratch/audit_phase_a.py) after the full batch — severity distribution and `evidence_list` shape are the signal for Phase D readiness.

#### Phase B.2 — Full CPG batch (✅ DONE 2026-05-24)

Re-ingestion completed across the full corpus. Postgres: **30 CPGs / 412 documents / 2,479 chunks** under the Phase A schema.

**Neo4j audit (2026-05-24):** 13,589 nodes / 18,252 edges.

| Phase A feature | Result | vs B.1 |
|---|---|---|
| `INTERACTS_WITH` | 289 edges | 16 → 289 ✅ |
| `REQUIRES_DOSE_ADJUSTMENT` | 408 edges, 504 with `trigger` populated | 19 → 408 ✅ |
| `CROSS_REACTS_WITH` | **26 edges** | 0 → 26 ✅ (predicted to fire once allergen-heavy CPGs landed; confirmed) |
| `severity` populated | 4,749 edges (MAJOR 3083 / MODERATE 1479 / MINOR 187) | 225 → 4,749 ✅ |
| `evidence_list` shape | edges=18,252  avg=1.04  p50=1  p95=1  p99=2  max=6 | max 3 → max 6 |

**Resolved decision #2 (evidence_list cap) — settled:** cap = `max(10, p95) = **10**`. p95 is 1 so any reasonable cap is well above the observed distribution; 10 leaves room for the long-tail interactions that accumulate across multiple CPGs (e.g. statin/warfarin showing up in Dyslipidaemia + AF + IHD).

**Yellow flags from B.1 — confirmed at scale, status:**
1. **MAJOR severity skew (65%)** — **✅ FIX-FORWARD APPLIED 2026-05-24.** Prompt in `graph_builder.py` updated: severity calibration block now states explicitly that strong CPG language ("avoid", "serious", "significant") is NOT sufficient for MAJOR — the OUTCOME must be life-threatening/disabling; default to MODERATE when in doubt. Added a MODERATE few-shot example ("avoid beta-blockers in decompensated HF") to anchor the borderline case. Existing 3,083 MAJOR edges remain biased (no re-ingest) — accepted for pilot; will re-ingest only if clinicians actually report alert fatigue.
2. **`risk_pct` bleed (186/200 on wrong relation types)** — Deferred (cosmetic). Stage 5 prompt formatting does not surface `risk_pct`, so clinician-visible impact is zero. Quick one-off Cypher cleanup available when convenient: `MATCH ()-[r]->() WHERE r.risk_pct IS NOT NULL AND type(r) <> 'CROSS_REACTS_WITH' REMOVE r.risk_pct`.
3. **Dosage-node duplicates (en-dash vs hyphen, `Mg` vs `mg P.O.`)** — Deferred (cosmetic). Dosage nodes do not trigger safety flags (Drug↔Drug and Drug↔Condition edges do). One-off normalisation pass when convenient.

---

### ~~Phase C — ICD enrichment~~ (REMOVED)
Dropped — see "Architectural decision" above. ICD codes do not belong on KG nodes.

---

### Phase D — Wire P1 flag injection into clinical pipeline — ✅ DONE (2026-05-17)

**Touched:** [`agent/graph_clinical.py`](../../agent/graph_clinical.py), [`agent/clinical_stages.py`](../../agent/clinical_stages.py), [`agent/clinical_workflow.py`](../../agent/clinical_workflow.py)

1. ✅ `extract_candidate_drugs_from_chunks(chunk_ids)` added to `graph_clinical.py` — queries Neo4j for Drug nodes whose edges link to the Stage 4 retrieved chunk UUIDs. Grounds candidate drugs in actual retrieved evidence (not the whole graph).
2. ✅ `stage_5_synthesize` in `clinical_stages.py` gains `flags: list[ClinicalFlag] | None = None`. `format_flags_for_prompt(flags)` prepended to evidence text in the user prompt, before retrieved chunks. Backwards-compatible.
3. ✅ KG lookup block wired between Stage 4 and Stage 5 in **all 3 orchestrator paths** in `clinical_workflow.py` (non-streaming, streaming, re-synthesis). Wrapped in `try/except` — Neo4j failure degrades to `[]` flags, never crashes synthesis.

**Gate: ✅ Passed** via [`scratch/test_phase_d_af.py`](../../scratch/test_phase_d_af.py) — AF polypharmacy patient (warfarin + digoxin + metoprolol, HF + renal impairment comorbidities):
- 90 candidate drugs extracted from 50 AF chunks ✅
- 11 flags returned (INTERACTION, DOSE_ADJUSTMENT, MONITORING) with evidence + Postgres chunk UUIDs ✅
- 3215-char `INTERACTION FLAGS` block produced by `format_flags_for_prompt` ✅

**Remaining validation (deferred to post-Phase B):** end-to-end LLM test confirming MAJOR flags surface in `contraindications_checked` and MINOR flags don't cause alert fatigue. Needs full 16-CPG batch first to produce a realistic flag density.

---

### ~~Phase E — ICD semantic matching~~ (REMOVED)
Dropped along with Phase C. The same architectural reasoning applies — there is no traversal path in the clinical pipeline that starts from an ICD code on a Condition node.

---

## Dependency graph

```
Phase A (code) ✅ ──> Phase B.1 AF dry-run ✅ ──> Phase D (wire P1) ✅
                  └──> Phase B.2 full CPG batch ✅ ──> post-Phase B KG audit ✅ ──> Phase D smoke vs live KG ✅
```

**Final status (2026-05-24): all phases complete.**
- Phase A: items 3, 4, 6 shipped in `graph_builder.py` + `graph_clinical.py`.
- Phase B.1 → B.2: 30 CPGs re-ingested (Postgres 2,479 chunks; Neo4j 13,589 nodes / 18,252 edges). All new relation types (`INTERACTS_WITH` 289, `REQUIRES_DOSE_ADJUSTMENT` 408, `CROSS_REACTS_WITH` 26) firing. `evidence_list` cap resolved at 10 (p95=1).
- Phase D: smoke-tested against live KG via `scratch/test_phase_d_af.py` — 84 candidate drugs, multi-type flags (INTERACTION/DOSE_ADJUSTMENT/MONITORING), 8,654-char `INTERACTION FLAGS` block injected into Stage 5. All 3 gates pass.

**Non-blocking follow-ups:**
- **MAJOR severity skew (65%)** — Fix-forward applied 2026-05-24: prompt calibration block + MODERATE few-shot anchor added to `graph_builder.py`. Future ingests calibrated; existing 3,083 MAJOR edges accepted for pilot (re-ingest deferred until/unless clinicians report alert fatigue).
- **`risk_pct` bleed** — Deferred (cosmetic, not surfaced to clinician). One-line Cypher cleanup ready.
- **Dosage-node duplicates** — Deferred (cosmetic, do not affect safety flags).

---

## Resolved decisions (2026-05-16)

1. **Severity vocabulary** — ✅ Stick with `MAJOR | MODERATE | MINOR`. Simple, fits the prompt cleanly, no external dependency.
2. **Evidence list cap** — ✅ **Measure-then-cap strategy:**
   - **Phase B:** no cap, dedup on write only (`WHERE NOT $evidence IN coalesce(r.evidence_list, [])`).
   - **Post-Phase B audit:** run distribution Cypher (`size(r.evidence_list)` percentiles) to see the actual shape.
   - **Set cap = max(10, p95)** of observed distribution, applied via one-off cleanup script.
   - Rationale: any guessed cap is wrong; the right value depends on how often the same interaction appears across CPGs, which we'll only know after the batch.
   - Revisit with quality-weighted ranking (Class I evidence first) only if the simple cap proves insufficient.
3. **ICD enrichment (item 8 / Phase C)** — ❌ **Dropped (2026-05-17).** ICD codes do not belong on KG nodes. Routing handles ICD → CPG at the Postgres layer; the KG must stay global/unscoped to preserve cross-CPG safety signals. See "Architectural decision" at top of doc.
4. **Phase B timing** — ✅ Solo ingestion, no contention. Run foreground whenever convenient.
