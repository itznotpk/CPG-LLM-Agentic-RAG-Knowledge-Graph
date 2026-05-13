# Phase A — Step 2: Parent-Child Re-ingest (NeonDB + KG)

> **Position in rollout:** Step 2 of 3. Runs **after** Step 1 (synthesis cap fixes — see `Phase_A_Step1_Synthesis_Fixes_Now.md`) and **before** Step 3 (performance pass — see `Phase_A_Step3_Performance_Pass.md`).
> **Status:** Option A selected — H2 re-chunk with full re-ingest.
> **Recommendation:** Proceed with H2 re-chunk. Cleanest single-source-of-truth — same H2 UUID serves retrieval and KG citation.
> **Trigger:** Query — "if an answer falls in the middle of a 6k sub-chunk split, does the system know what's before and after?"

---

## 1. Root Problem Summary

**Current state:** Every section markdown file (e.g., `section-3-diagnosis.md`, 1,266 lines, ~51k chars) is stored as **one H1 chunk** in NeonDB with one embedding. The 6k sub-chunking in `graph_builder.py` is ephemeral (KG extraction only) and never stored. This creates three compounding problems:

| # | Problem | Impact |
|---|---------|--------|
| P1 | **Noisy H1 embedding** | One vector covers 5 clinical sub-topics → poor retrieval precision for specific questions |
| P2 | **No shared chunk ID between NeonDB and Neo4j** | KG triples store an integer `chunk_index`; NeonDB stores a UUID `chunk_id` → no clickable citation path |
| P3 | **Context lost at 6k sub-chunk boundaries** | 500-char overlap is too narrow for multi-paragraph clinical recommendations |

---

## 2. Selected Path — H2 Re-chunk with Full Re-ingest

> **Re-embedding is mandatory.** The existing 51k+ H1 vectors were built from incomplete input — `text-embedding-3-small` truncates at ~8,191 tokens (~32k chars), so the late portion of every oversized H1 was never represented in its vector. No retrieval-time trick can fix a vector that was built from incomplete input.

**Decision: Option A / H2 re-chunk.**
- New CPGs are about to be added — the re-ingest pass happens anyway. Cleanest to handle it as one operation.
- Single source of truth: the same H2 UUID is both the embedded vector and the KG citation target.
- The H1 parent row is kept (unembedded) so the synthesis stage can still pull full context.

**Readiness check after Step 1:** Step 1 completion is sufficient to begin Step 2 coding because Stage 5 no longer hard-truncates evidence, has parent-context budgeting, dedupes repeated parents, and refuses oversized prompts. It is **not** sufficient to run re-ingest yet. Re-ingest should only start after the Step 2 schema, markdown alignment guide compliance, chunker, parent-only reference parsing, `cross_ref` metadata parsing, ingestion persistence, H2 retrieval, parent/cross-ref resolver, KG extraction, and ICD-11 scope checks are implemented and dry-run verified.

---

## 3. H2 Re-chunking Architecture

### Architecture

```
markdown/Prevention-Diagnosis-Management-of-IE/section-3-diagnosis.md
│
│  NeonDB — Two levels stored
│
├── H1 PARENT chunk (stored for context, NOT embedded)
│   chunk_id: "a1b2-h1"   content: full 51k chars   embedding: NULL
│   chunk_level: "h1"      parent_chunk_id: NULL
│
├── H2 CHILD chunk — 3.1 Clinical evaluation
│   chunk_id: "c3d4-3.1"  content: ~3,000 chars     embedding: [vector]
│   chunk_level: "h2"      parent_chunk_id: "a1b2-h1"
│
├── H2 CHILD chunk — 3.2 Investigations
│   chunk_id: "e5f6-3.2"  content: ~7,000 chars     embedding: [vector]
│   chunk_level: "h2"      parent_chunk_id: "a1b2-h1"
│
├── H2 CHILD chunk — 3.3 Imaging
│   chunk_id: "g7h8-3.3"  content: ~10,000 chars    embedding: [vector]
│   chunk_level: "h2"      parent_chunk_id: "a1b2-h1"
│
└── H2 CHILD chunk — 3.4 Diagnostic criteria (Duke)
    chunk_id: "i9j0-3.4"  content: ~8,000 chars     embedding: [vector]
    chunk_level: "h2"      parent_chunk_id: "a1b2-h1"

  Neo4j — Triples extracted from H2 child chunks
  └── (:Condition)-[:ASSESSED_BY]->(:DiagnosticTool)
        r.cpg_chunk_id = "g7h8-3.3"  ← same UUID as NeonDB H2 chunk → direct citation
```

### Query Path (Parent-Child Retrieval)

```
User query: "What are the Duke criteria for diagnosing IE?"
│
├─ Step 1: Embed query → cosine search against H2 child embeddings only (chunk_level = 'h2')
│
├─ Step 2: Top-K child hits
│          → "i9j0-3.4" (3.4 Diagnostic criteria) similarity: 0.91  ← precise hit
│          → "c3d4-3.1" (3.1 Clinical evaluation)  similarity: 0.61
│
├─ Step 3: For each child hit, fetch its H1 parent by parent_chunk_id
│          → "a1b2-h1" (full section-3-diagnosis, 51k chars)
│
└─ Step 4: LLM receives:
           [CHILD — citation source]  chunk: "i9j0-3.4" | "Modified Duke criteria include..."
           [PARENT — full context]    chunk: "a1b2-h1"  | (full section 3 for synthesis)
```

### NeonDB Schema Change

```sql
ALTER TABLE chunks ADD COLUMN chunk_level TEXT DEFAULT 'h1';
ALTER TABLE chunks ADD COLUMN parent_chunk_id UUID REFERENCES chunks(chunk_id);
```

Vector search in [agent/db_utils.py:369-522](../../agent/db_utils.py): filter `WHERE chunk_level = 'h2'` for retrieval; fetch `WHERE chunk_id = $parent_chunk_id` for context.

### Markdown Alignment Inputs

Before re-ingest, align markdown against both guides:

- [Markdown_Parent_Child_Standardization_Guide.md](./Markdown_Parent_Child_Standardization_Guide.md): controls standard section filenames, exactly-one-H1-per-file structure, H1/H2/H3/H4 hierarchy, H2 child boundaries, table heading levels, parent-only reference block placement, and cleanup before ingestion.
- [Markdown_Cross_Reference_Marker_Guide.md](./Markdown_Cross_Reference_Marker_Guide.md): controls `cross_ref` markers when a visible "refer to..." sentence points outside the current H1 parent.

There is no conflict between the two guides:

```text
Parent-child guide:
  structures the current H1 parent and its H2/H3/H4 content

Cross-reference guide:
  links to content outside the current H1 parent

Shared rule:
  if referenced content is already copied into parent_only_reference,
  do not add a cross_ref marker
```

Use the current repo examples as alignment references before ingestion:

```text
Anaesthesia Medication Safety:
  standard section filenames such as section-0-appendix.md
  one H1 parent per file
  H2 retrievable clinical children
  H3/H4 nested details and table groups
  parent_only_reference blocks for shared TML/CVC examples

Atrial Fibrillation (2012) Section 3:
  one H1 parent
  H2 child sections
  H3/H4 nested clinical details
```

### Chunker Change

**File:** [ingestion/chunker.py:81-318](../../ingestion/chunker.py)

Add `##` (H2) splitting to `MarkdownHeaderTextSplitter`. For each markdown file:
- Require standard `section-{number}-{slug}.md` naming for newly aligned markdown files.
- Require exactly one `# H1` parent per markdown file; remove, demote, or convert duplicate `#` headings before ingestion.
- Pass 1: split at `#` → H1 parent chunk (stored, `embedding=NULL`)
- Pass 2: split at `##` within each H1 → H2 child chunks (stored, embedded)
- Keep `###` numbered subsections such as `3.1.1`, `3.1.2`, and `3.1.3` inside the owning H2 child.
- Keep `### Table ...` headings inside the owning H2 child when the table belongs directly under that H2.
- Keep `#### Table ...` or lower headings inside the owning H3 group when the table/detail falls under an H3.
- Fallback: if no H2 headers exist, H1 chunk becomes both parent and leaf (`chunk_level='h1_leaf'`, embedded)
- Cap: H2 chunk > 8,000 chars → split at `###` with same parent-child logic

Cleanup before parsing: remove redundant `---` separators, normalize excessive blank lines, keep table headers directly above tables, and remove temporary run/log files from the repo.

Heading levels are based on document hierarchy, not visual size:

```text
# Section 3                         H1 parent
## 3.1 Primary Prevention           H2 child
### 3.1.1 Information Required      H3 inside 3.1
### Table 7: Prevalence...          H3 table inside 3.1
#### Table 1A: Points for Men       H4 table under an H3 table group
```

#### Parent-only shared references

Use this rule for shared or overlap material such as cross-cutting tables, criteria lists, dosing reference tables, and appendix-style content that should support synthesis but should not become an independent vector hit:

```text
Retrievable children = clinically specific H2 sections
Parent context = full H1, including shared/overlap tables
Parent-only references = visible to synthesis, invisible to direct child retrieval
```

Recommended markdown marker:

```md
<!-- parent_only_reference_start -->
### Shared Reference: Modified Duke Criteria

| Criteria | Details |
|---|---|
| Major criteria | ... |
| Minor criteria | ... |
<!-- parent_only_reference_end -->
```

Chunker behavior:
- Keep the marked block inside the H1 parent content.
- Do not emit the marked block as a retrievable H2 child or embed it separately.
- If a nearby H2 child from the same H1 is retrieved, include the parent context so the marked reference is still visible to Stage 5 synthesis.
- Prefer `###` or lower headings inside the marked block. Avoid `##` inside the block unless the parser removes/masks parent-only blocks before H2 splitting.

#### Cross-reference markers

Use `cross_ref` markers only when the referenced content lives outside the current H1 parent. Do not add `cross_ref` if the target table/form/appendix excerpt is already copied into the current H1 using `parent_only_reference`.

Example:

```md
For estimation of global CVD risk, refer to Section 3: Estimation of Global CVD Risk.
<!-- cross_ref target_file="section-3-estimation-of-global-cvd-risk.md" target_heading="Section 3: Estimation of Global CVD Risk" target_kind="h1_section" -->
```

Allowed `target_kind` values:

```text
h1_section
h2_section
algorithm_flowchart
appendix
```

Chunker/ingestion behavior:
- Keep the visible human sentence in the child text.
- Parse the `cross_ref` marker into `cross_refs` metadata on the H2 child chunk where the "refer to..." sentence appears.
- Strip the marker itself from embedding text and normal LLM prompt text.
- Optionally aggregate cross-refs onto the H1 parent for audit/debugging, but retrieval must follow the child metadata.

Retrieval behavior:
- Retrieve the primary H2 child normally.
- Fetch its own H1 parent context.
- If `child.metadata.cross_refs` exists, resolve the target evidence before Stage 5 synthesis.
- For `h1_section`, prefer the best matching H2 under the target H1; use capped/windowed target H1 only when a specific H2 cannot be resolved.
- Do not blindly attach two full H1 parents by default.

### KG Extraction Change

Read H2 child chunks from NeonDB instead of H1:
```sql
SELECT chunk_id, content, metadata FROM chunks
WHERE document_id = $1 AND chunk_level = 'h2'
  AND metadata->>'category' = ANY($category_whitelist)
ORDER BY chunk_index;
```

IE section-3: was 1 H1 → 9 sub-chunks (51k ÷ 6k). Now: 4 H2 → 0–2 sub-chunks each.

### Trade-offs

| Decision | Trade-off |
|----------|-----------|
| Re-ingest NeonDB | Existing H1 chunk_ids change → any hardcoded UUID references break. Acceptable if vector store not in production. |
| H1 not embedded | H1 content unreachable by semantic search; only loadable via parent_chunk_id join. |
| Neo4j re-ingest | Phase D1 `DETACH DELETE` + re-extraction from H2 chunks required. Old `chunk_index` integers abandoned. |

### Implementation Steps After Step 1 Completion

Step 1 must be merged first because Stage 5 now accepts larger evidence packs and has the `build_parent_context()` hook that Step 2 will expand. Step 1 completion is enough to begin Step 2 implementation, but it is not enough to run re-ingest immediately. Re-ingest starts only after A-1 through A-11 are implemented/verified.

Status meaning:

```text
[x] Done / double-checked
[done] Already resolved in Step 1
[now] Can be solved before tomorrow ingestion
[manual] Needs reviewer or teammate confirmation
[tomorrow] Run during ingestion/rebuild
```

Execute Step 2 in this order:

| Status | Step | Action | Files / Area | Exit Gate |
|--------|------|--------|--------------|-----------|
| [x] Done / double-checked | A-0 | Confirm Step 1 is complete and green enough to proceed: tiered budgets, token counting, whole-chunk formatting, parent dedupe, prompt-size guard, caller audit, and `build_parent_context()` are present. Resolution: already completed in Phase A Step 1 and double-checked for Step 2 readiness. | `agent/clinical_stages.py`, `requirements.txt`, `tests/test_clinical_stages.py` | Tick: complete. `tests/test_clinical_stages.py` passed locally; this gates Step 2 coding, not re-ingest |
| [now] Can solve before ingestion | A-1 | Add/confirm parent-child schema columns: `chunk_level`, `parent_chunk_id`, and child position fields needed for parent slicing (`start_char`, `end_char` if not already present) | Migration SQL, `chunks` table | `chunks` can store H1 parent rows and H2 child rows with parent links |
| [now] Can solve before ingestion | A-2 | Update `MarkdownChunker` to emit H1 parent chunks and H2 child chunks according to the parent-child standardization guide. Preserve H3/H4 numbered subsections and table headings inside the owning H2; split oversized H2 children at H3 only when required | `ingestion/chunker.py`, `Markdown_Parent_Child_Standardization_Guide.md` | Unit/sample parse shows `# H1` parent plus expected `## H2` children; H3/H4 content remains inside the correct H2 |
| [now] Can solve before ingestion | A-3 | Implement parent-only reference handling before H2 splitting: keep `parent_only_reference` blocks inside the H1 parent, but do not emit/embed them as retrievable children | `ingestion/chunker.py`, `Markdown_Parent_Child_Standardization_Guide.md` | Marked shared tables remain in parent content and are absent from child embeddings |
| [now] Can solve before ingestion | A-4 | Implement `cross_ref` marker parsing according to the cross-reference guide. Store `cross_refs` metadata on the H2 child chunk containing the reference sentence; strip marker comments from embedding/prompt text | `ingestion/chunker.py`, metadata helpers, `Markdown_Cross_Reference_Marker_Guide.md` | Sample H2 child has clean content plus `metadata.cross_refs`; no `cross_ref` is created for content already copied into `parent_only_reference` |
| [now] Can solve before ingestion | A-5 | Update ingestion persistence so H1 parent rows are stored with `embedding=NULL`, H2 child rows are embedded, and H2 rows store `parent_chunk_id`, `start_char`, `end_char`, and metadata (`cross_refs` when present) | `ingestion/ingest.py`, DB insert/upsert helpers | Re-ingest of one CPG produces linked H1/H2 rows |
| [now] Can solve before ingestion | A-6 | Protect document-scope metadata during re-ingest. Existing `documents.icd11_scope`, `scope_verified`, `verified_at`, and `verified_by` must survive document UPSERTs | `ingestion/ingest.py` | Existing verified CPGs remain verified after dry-run re-ingest |
| [now] Can solve before ingestion | A-7 | Update vector retrieval to search only embedded H2 children by default (`chunk_level = 'h2'`) and ignore unembedded H1 parents | `agent/db_utils.py` | Retrieval SQL returns H2 child chunks only |
| [now] Can solve before ingestion | A-8 | Update tool response shape to carry child plus parent context. Fetch parent by `parent_chunk_id`, resolve `child.metadata.cross_refs` when present, and use the Step 1 `build_parent_context()` path for synthesis formatting | `agent/tools.py`, `agent/clinical_stages.py` | Stage 5 evidence can include child citation content, parent context, and resolved cross-reference evidence |
| [now] Can solve before ingestion | A-9 | Update KG extraction to read H2 child chunks, not old H1 chunks. Keep H2 UUID as `cpg_chunk_id` for citation resolution | `ingestion/ingest.py`, `ingestion/graph_builder.py` | New triples point to H2 `chunks.chunk_id` |
| [now] Can solve before ingestion | A-10 | Implement KG sub-window context bands for oversized H2 children and stamp `subchunk_focus_start` on emitted triples | `ingestion/graph_builder.py`, prompt text | Unit test confirms `[BEFORE]`, `[FOCUS]`, `[AFTER]` behavior and metadata |
| [manual] Confirm before ingestion | A-11 | Run ICD-11 scope pipeline for any newly added CPGs, then clinician review and verification | `classify_cpg_scope.py`, `verify_cpg_scope.py`, `tasks/cpg_scope_review.md` | All documents have non-empty `icd11_scope` and `scope_verified = TRUE` |
| [tomorrow] Ingestion dry run | A-12 | Re-ingest one small CPG as a dry run, preferably Erectile-Dysfunction | CLI batch run | Counts show H1 parent + H2 children; retrieval query returns H2 hits; parent context resolves |
| [tomorrow] Full ingestion | A-13 | Re-ingest all existing and new CPGs with H1/H2 parent-child chunks | CLI batch run | Expected H2 count exists across corpus; no verified scope metadata lost |
| [tomorrow] Graph rebuild | A-14 | Backup Neo4j, wipe old graph, then rebuild KG from new H2 chunks | Cypher, `ingestion.ingest --graph-only` | Typed clinical relations exist; no old Graphiti residue required for citation |
| [tomorrow] Smoke test | A-15 | End-to-end verification: Duke criteria IE, cross-reference resolution, citation click-through, parent context inclusion, and prompt budget logs | Clinical pipeline smoke test | Correct answer, H2 citation resolves, referenced evidence attaches when needed, parent context present, no prompt oversize |

### 3.1 ICD-11 Scope Wiring for New CPGs

Existing 16 CPGs already have `documents.icd11_scope` populated and `scope_verified = TRUE` (see `tasks/Done/STEP_02_extend_documents.md`). For **new CPG markdown directories** added before this re-ingest, the same pipeline must be run so Stage 3 routing works:

```
markdown/<new-cpg-name>/ ─┐
                          ├─►  ingest.py (creates documents row, icd11_scope = '{}')
                          │
                          ├─►  classify_cpg_scope.py
                          │    └─ groups CPG sections, calls OpenRouter (Gemini Flash),
                          │       upserts icd11_scope codes + scope_rationale,
                          │       sets scope_verified = FALSE, writes
                          │       tasks/cpg_scope_review.md
                          │
                          ├─►  CLINICIAN REVIEW (manual)
                          │    └─ Dr Chin edits tasks/cpg_scope_review.md
                          │       (Approve / Edit / Reject per CPG)
                          │
                          └─►  verify_cpg_scope.py
                               └─ parses review file, flips scope_verified = TRUE,
                                  writes verified_at / verified_by
```

**Validation queries before considering A-11 complete:**

```sql
-- Every CPG document must have at least one ICD-11 code in scope
SELECT title, icd11_scope, scope_verified
FROM documents
WHERE cardinality(icd11_scope) = 0 OR scope_verified = FALSE;
-- Expected: 0 rows.

-- Every code in any documents.icd11_scope must exist in icd11_codes
SELECT DISTINCT unnest(icd11_scope) AS code
FROM documents
WHERE NOT EXISTS (
    SELECT 1 FROM icd11_codes WHERE icd11_codes.code = unnest(documents.icd11_scope)
);
-- Expected: 0 rows. If non-empty, run ddx/ingest_icd11_full.py to backfill missing codes.
```

If any new CPG covers an ICD-11 code not yet in the `icd11_codes` table (e.g. a chapter not previously ingested), run `ddx/ingest_icd11_full.py` to fetch the missing codes from the WHO API **before** verification, so the `icd11_scope` reference is not dangling.

### 3.2 Sequencing inside A-11/A-13

For new CPGs, the order is strict:

1. `ingest.py --skip-graph --skip-classify <new-cpg-dir>` — creates `documents` + H1/H2 chunks with embeddings.
2. `classify_cpg_scope.py --cpg <new-cpg-name>` — adds `icd11_scope`.
3. **Manual review** of `tasks/cpg_scope_review.md`.
4. `verify_cpg_scope.py` — flips `scope_verified = TRUE`.
5. `ingest.py --graph-only <new-cpg-dir>` — runs `graph_builder.py` against the verified H2 chunks (ephemeral sub-windowing per §6).

For **existing CPGs** being re-ingested at H2 level: scope is already verified, so steps 2–4 are skipped — only steps 1 and 5 run. The existing `documents.icd11_scope` values survive because `ingest.py` should `UPSERT` on `documents.source` rather than wiping the row.

> **Safety check before A-13:** confirm `ingest.py` preserves `icd11_scope`, `scope_verified`, `verified_at`, `verified_by` on UPSERT. If it doesn't, the re-ingest will silently un-verify all 16 existing CPGs and Stage 3 routing breaks. Patch `ingest.py` to `ON CONFLICT DO UPDATE SET content = EXCLUDED.content, updated_at = NOW()` only — never touch the scope columns.

---

## 4. KG Sub-chunk Improvements

The following `graph_builder.py` changes apply to the selected H2 re-chunk path:

### Increase overlap 500 → 1,000 chars

**File:** [ingestion/graph_builder.py:535](../../ingestion/graph_builder.py)

```python
def _split_into_subchunks(self, text: str, max_chars: int = 6000, overlap: int = 1000):
```

### Add `subchunk_start_char` to triple metadata

In `_split_into_subchunks()` at lines 534–564, return `(text, start_offset)` tuples:
```python
subchunks.append((chunk, start))   # was: subchunks.append(chunk)
```

In `build_relationship_graph()` at lines 590–598, unpack and store:
```python
for sub_text, sub_start in subchunks:
    triples = await self._extract_triples_with_llm(text=sub_text, ...)
    for t in triples:
        t['subchunk_start_char'] = sub_start
```

Context reconstruction from any stored triple:
```python
# fetch H2 chunk content from NeonDB by cpg_chunk_id
# slice: content[subchunk_start_char : subchunk_start_char + 6000]
```

---

## 5. Verification Checklist

| Check | Expected result |
|-------|-----------------|
| Markdown alignment follows both guides | H2 children preserve H3/H4/table structure; parent-only blocks and `cross_ref` markers follow their separate rules |
| Query "Duke criteria IE" → correct section retrieved | H2 child chunk at rank 1 |
| Neo4j triple → NeonDB chunk (clickable citation) | `cpg_chunk_id` = H2 UUID |
| section-3-diagnosis chunk count in NeonDB | 5 rows (1 H1 + 4 H2) |
| Sub-chunk position tracking | `subchunk_focus_start` in triple |
| KG extraction LLM calls for IE section 3 | 4 H2 chunks × 1–2 sub-chunks |
| **All `documents.icd11_scope` populated + `scope_verified = TRUE`** | Yes — new CPGs pass through §3.1 pipeline |
| Every code in `documents.icd11_scope` exists in `icd11_codes` | No dangling refs |

---

## 6. KG Building — Ephemeral Sub-windowing with Context Bands

**Decision:** Keep H2 as the persisted citation unit. If an H2 child is still oversized (>8k chars), `graph_builder.py` chops it ephemerally into 6k focus windows with context bands on either side. The bands give the LLM enough surrounding text to resolve pronouns, scope conditions, and trailing grade-of-recommendation tags — but only the focus window is treated as an extraction target.

### Concept

```
[BEFORE — context only, do not extract triples from this]
<chars (focus_start - 2000) → focus_start>

[FOCUS — extract triples ONLY from this region]
<chars focus_start → focus_start + 6000>

[AFTER — context only, do not extract triples from this]
<chars (focus_start + 6000) → (focus_start + 8000)>
```

Total payload per LLM call: ~10k chars. Only the middle 6k is the extraction target. Cost impact: ~$1.58 → ~$2.10 across the full corpus — negligible.

### Change shape — `graph_builder.py`

**File:** [graph_builder.py:534-564](../../ingestion/graph_builder.py#L534-L564)

Change `_split_into_subchunks` from returning `[(text, start_offset), ...]` to returning structured windows:

```python
def _split_into_subchunks(
    self,
    text: str,
    focus_size: int = 6000,
    band_size: int = 2000,
    stride: int = 6000,  # non-overlapping focus windows; bands provide the bridge
) -> list[dict]:
    """
    Yields windows of the form:
      {
        "before": str,         # context-only band (may be empty at start)
        "focus":  str,         # extraction target
        "after":  str,         # context-only band (may be empty at end)
        "focus_start": int,    # offset of focus within parent text
        "focus_end":   int,
        "is_first":    bool,
        "is_last":     bool,
      }
    """
    windows = []
    for focus_start in range(0, len(text), stride):
        focus_end = min(focus_start + focus_size, len(text))
        before_start = max(0, focus_start - band_size)
        after_end = min(len(text), focus_end + band_size)
        windows.append({
            "before": text[before_start:focus_start],
            "focus":  text[focus_start:focus_end],
            "after":  text[focus_end:after_end],
            "focus_start": focus_start,
            "focus_end":   focus_end,
            "is_first":    focus_start == 0,
            "is_last":     focus_end == len(text),
        })
        if focus_end == len(text):
            break
    return windows
```

In `_extract_triples_with_llm` (around [graph_builder.py:382](../../ingestion/graph_builder.py#L382)), build the prompt as labeled regions:

```python
before_label = "[BEFORE — none, this is the start of the section]" if window["is_first"] \
               else f"[BEFORE — context only, do not extract triples from this]\n{window['before']}"
after_label  = "[AFTER — none, this is the end of the section]" if window["is_last"] \
               else f"[AFTER — context only, do not extract triples from this]\n{window['after']}"

prompt_body = (
    f"{before_label}\n\n"
    f"[FOCUS — extract triples ONLY from this region]\n{window['focus']}\n\n"
    f"{after_label}"
)
```

### System prompt addition

Add to the triple-extraction system prompt:

```
You will see three regions: [BEFORE], [FOCUS], [AFTER].
Extract triples ONLY from facts stated within [FOCUS].
Use [BEFORE] and [AFTER] solely to resolve references (pronouns,
section scope, grade-of-recommendation tags). Do not emit triples
whose subject AND object both lie outside [FOCUS].
```

### Triple metadata

Each emitted triple gets stamped with:
- `cpg_chunk_id` = H2 chunk UUID (persistent citation)
- `subchunk_focus_start` = `window["focus_start"]` (for debugging / future H3 backfill)

The sub-window itself is **not persisted**. The H2 UUID remains the citation target.

### Implementation steps

| Step | Action | Files | Risk |
|------|--------|-------|------|
| K-1 | Rewrite `_split_into_subchunks` to emit window dicts | `graph_builder.py:534-564` | Low |
| K-2 | Update prompt template with three labeled regions | `graph_builder.py:382` + prompt file | Low |
| K-3 | Add "do not extract from bands" instruction to system prompt | prompt file | Low |
| K-4 | Stamp `subchunk_focus_start` onto each triple | `graph_builder.py:590-598` | Low |
| K-5 | Keep existing triple-dedup pass as safety net | unchanged | Low |

### KG rebuild — when to actually run the commands

The code changes (K-1..K-5) land first as a deploy. The KG itself is then rebuilt during **A-14** in the §3 implementation steps. Strict order:

| Order | Command | Purpose |
|-------|---------|---------|
| 1 | `pytest tests/test_graph_builder_subwindow.py` | Unit-test the new window dicts + prompt template before touching prod Bedrock spend |
| 2 | Backup current graph: `cypher-shell "CALL apoc.export.cypher.all('backups/kg_pre_step2.cypher', {format:'cypher-shell'})"` | Roll-back point. Skip only if previous backup `backups/kg_backup_2026-05-12.cypher` is recent enough |
| 3 | A-13 must be complete — verify `SELECT count(*) FROM chunks WHERE chunk_level = 'h2'` returns expected H2 count | KG build reads H2 rows; running before A-13 would extract from the old polluted H1 rows |
| 4 | `cypher-shell "MATCH (n) DETACH DELETE n"` | Wipe old graph (564 Graphiti edges + 13 old typed triples). Confirmed safe — see Phase_A_Findings.md open question 3 |
| 5 | `python -m ingestion.ingest --graph-only --all-cpgs` (or per-CPG: `--cpg <name>`) | Runs `build_relationship_graph` with new sub-window context bands against H2 chunks |
| 6 | Smoke-check: `MATCH ()-[r]->() RETURN type(r) AS rel, count(r) AS cnt ORDER BY cnt DESC` | Expect typed clinical relations (TREATS, INCREASES_RISK_OF, ASSESSED_BY, etc.) — no `MENTIONS` / `RELATES_TO` Graphiti residue |
| 7 | Sample triple → NeonDB resolution: pick one triple, confirm `r.cpg_chunk_id` exists in `chunks` and `chunk_level = 'h2'` | Validates the P2 citation link |

**Per-CPG dry run first.** Before the full `--all-cpgs` run, do one small CPG (Erectile-Dysfunction, 6 filtered chunks, ~$0.013) end-to-end through steps 4–7 to catch prompt-template bugs cheaply. Only proceed to `--all-cpgs` if the dry run looks clean.

**Cost expectation:** ~720 sub-windows × $0.0022 ≈ $1.60 across all CPGs at current size. With context bands (~+3k chars each) the figure rises to ~$2.10. Below the $50 threshold; no re-approval needed.

**Rate-limit safety:** if running A-14 unbatched takes >10 min for the full corpus, apply the `Semaphore(5)` batching from Step 3 §2.6 early. Functional equivalent — just paid down sooner if you need the wall time back.

---

## 7. Retrieval/Synthesis — Window Slicing as Outlier Handler

**Decision:** Most parents (under ~60k chars) are passed to the synthesis LLM in full. Window slicing is a **fallback for outliers** like IE section-3-diagnosis (97k) and section-4-management (131k) that would otherwise blow the evidence budget.

### Logic

```python
def build_parent_context(parent: Chunk, child: Chunk, limit: int = _PARENT_CHAR_LIMIT) -> str:
    if len(parent.content) <= limit:
        return parent.content  # whole parent fits
    # Outlier path: slice a window centered on the child's location inside the parent
    half = limit // 2
    window_start = max(0, child.start_char - half)
    window_end   = min(len(parent.content), child.end_char + half)
    return parent.content[window_start:window_end]
```

For IE section-4 (131k) with a child at chars 15k–60k and `_PARENT_CHAR_LIMIT=60_000`:
- `window_start = max(0, 15000 - 30000) = 0`
- `window_end   = min(131000, 60000 + 30000) = 90000`
- Result: chars 0–90k delivered (tail of 4.1 + all of 4.2 + 4.3) — 4.4 surgical timing is dropped.

### Frequency expectation

| Parent size | Slicing triggered? | % of IE corpus |
|---|---|---|
| ≤ 60k | No — full parent passed | 8 of 10 sections |
| > 60k | Yes — windowed | 2 of 10 sections (3, 4) |

### Implementation steps

| Step | Action | Files | Risk |
|------|--------|-------|------|
| W-1 | Add `build_parent_context()` helper in clinical_stages | `clinical_stages.py` | Low |
| W-2 | Update `_format_evidence` to call helper instead of raw `c.content` | `clinical_stages.py:551-575` | Low |
| W-3 | Log when slicing fires (parent size + child position) for telemetry | `clinical_stages.py` | Low |

Note: this code can be written and merged in Step 1 *before* parent-child ingest exists — it just won't trigger until the H2 re-ingest lands a real `child.start_char` / `parent.content` pair. Until then, treat retrieved chunks as standalone (no parent) and skip the helper.
