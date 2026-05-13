# Phase A — Step 2: Parent-Child Re-ingest (NeonDB + KG)

> **Position in rollout:** Step 2 of 3. Runs **after** Step 1 (synthesis cap fixes — see `Phase_A_Step1_Synthesis_Fixes_Now.md`) and **before** Step 3 (performance pass — see `Phase_A_Step3_Performance_Pass.md`).
> **Status:** Three solution paths documented — choose based on willingness to re-chunk.
> **Recommendation:** Option A (H2 re-chunk). Cleanest single-source-of-truth — same H2 UUID serves retrieval and KG citation.
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

## 2. Decision Guide — Which Option to Use

> **Re-embedding is mandatory in both options.** The existing 51k+ H1 vectors were built from incomplete input — `text-embedding-3-small` truncates at ~8,191 tokens (~32k chars), so the late portion of every oversized H1 was never represented in its vector. No retrieval-time trick can fix a vector that was built from incomplete input. The only choice is **where the new H2 embeddings live**, not whether to re-embed.

Two solution paths:

| Option | Where H2 embeddings live | Re-chunk `chunks` table? | Fixes P1 (precision) | Fixes P2 (citation link) | Fixes P3 (boundary) | Effort |
|--------|-------------------------|--------------------------|---------------------|--------------------------|---------------------|--------|
| **A — H2 Re-chunk** | New H2 rows in `chunks` (alongside H1 parent rows) | **Yes** — `chunks` rebuilt | Full | Full (same UUID for retrieval + KG) | Full | High |
| **B — Segment Index** | New `chunk_segments` table; `chunks` untouched | No — `chunks` rows stable | Full | Full (via `segment_id` on triple) | Full | Medium |

**Recommendation: Option A.**
- New CPGs are about to be added — the re-ingest pass happens anyway. Cleanest to handle it as one operation.
- Single source of truth: the same H2 UUID is both the embedded vector and the KG citation target.
- The H1 parent row is kept (unembedded) so the synthesis stage can still pull full context.
- Option B remains a fallback if a fresh re-ingest of existing CPGs is blocked for unrelated reasons.

---

## 3. Option A — H2 Re-chunking (Full Solution, Requires Re-ingest)

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

### Chunker Change

**File:** [ingestion/chunker.py:81-318](../../ingestion/chunker.py)

Add `##` (H2) splitting to `MarkdownHeaderTextSplitter`. For each markdown file:
- Pass 1: split at `#` → H1 parent chunk (stored, `embedding=NULL`)
- Pass 2: split at `##` within each H1 → H2 child chunks (stored, embedded)
- Fallback: if no H2 headers exist, H1 chunk becomes both parent and leaf (`chunk_level='h1_leaf'`, embedded)
- Cap: H2 chunk > 8,000 chars → split at `###` with same parent-child logic

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

### Implementation Steps

| Step | Action | Files | Risk |
|------|--------|-------|------|
| A-1 | Add `chunk_level` column (`parent_chunk_id` already exists in `chunks` from prior migration) | Migration SQL | Low — additive |
| A-2 | Update `MarkdownChunker` for H1→H2 split (cap H2 > 8k → split at H3) | `chunker.py` L81–318 | Medium |
| A-3 | Update `ingest.py` to read H2 chunks for KG (filter `chunk_level = 'h2'`) | `ingest.py` | Low |
| A-4 | Update `db_utils.py` vector search filter (`WHERE chunk_level = 'h2'`) | `db_utils.py` L369–522 | Low |
| A-5 | Update `tools.py` to return `{child, parent}` with `build_parent_context()` helper from Step 1 | `tools.py` L142–257 | Low |
| **A-6** | **ICD-11 scope wiring for new CPGs** — see §3.1 below | `classify_cpg_scope.py`, `verify_cpg_scope.py` | Medium |
| A-7 | Re-ingest all CPGs (existing + new) | CLI batch run | Medium |
| A-8 | Re-run Neo4j extraction from new H2 chunks; `DETACH DELETE` old graph first | `graph_builder.py`, Cypher | Medium |

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

**Validation queries before considering A-6 complete:**

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

### 3.2 Sequencing inside A-6/A-7

For new CPGs, the order is strict:

1. `ingest.py --skip-graph --skip-classify <new-cpg-dir>` — creates `documents` + H1/H2 chunks with embeddings.
2. `classify_cpg_scope.py --cpg <new-cpg-name>` — adds `icd11_scope`.
3. **Manual review** of `tasks/cpg_scope_review.md`.
4. `verify_cpg_scope.py` — flips `scope_verified = TRUE`.
5. `ingest.py --graph-only <new-cpg-dir>` — runs `graph_builder.py` against the verified H2 chunks (ephemeral sub-windowing per §8).

For **existing CPGs** being re-ingested at H2 level: scope is already verified, so steps 2–4 are skipped — only steps 1 and 5 run. The existing `documents.icd11_scope` values survive because `ingest.py` should `UPSERT` on `documents.source` rather than wiping the row.

> **Safety check before A-7:** confirm `ingest.py` preserves `icd11_scope`, `scope_verified`, `verified_at`, `verified_by` on UPSERT. If it doesn't, the re-ingest will silently un-verify all 16 existing CPGs and Stage 3 routing breaks. Patch `ingest.py` to `ON CONFLICT DO UPDATE SET content = EXCLUDED.content, updated_at = NOW()` only — never touch the scope columns.

---

## 4. Option B — Segment Index (No Re-chunk, New Table)

### Architecture

NeonDB `chunks` table is **completely unchanged** — all existing H1 chunk_ids remain stable. A new `chunk_segments` table stores H2-level embeddings alongside the position within the parent H1 chunk.

```
chunks table (UNCHANGED)
└── chunk_id: "a1b2-h1"  content: full 51k chars  embedding: [old H1 vector, kept]

chunk_segments table (NEW)
├── segment_id: "seg-3.1"  chunk_id: "a1b2-h1"  h2_header: "3.1 Clinical evaluation"
│   start_char: 500   end_char: 3200   embedding: [focused H2 vector]
│
├── segment_id: "seg-3.2"  chunk_id: "a1b2-h1"  h2_header: "3.2 Investigations"
│   start_char: 3200  end_char: 10400  embedding: [focused H2 vector]
│
├── segment_id: "seg-3.3"  chunk_id: "a1b2-h1"  h2_header: "3.3 Imaging"
│   start_char: 10400 end_char: 20800  embedding: [focused H2 vector]
│
└── segment_id: "seg-3.4"  chunk_id: "a1b2-h1"  h2_header: "3.4 Diagnostic criteria"
    start_char: 20800 end_char: 29300  embedding: [focused H2 vector]

Neo4j triple
└── r.cpg_chunk_id = "a1b2-h1"   (original H1 UUID — unchanged)
    r.segment_id   = "seg-3.3"   (NEW — points to the H2 segment in chunk_segments)
    r.subchunk_start_char = 14200 (offset within segment)
```

### Query Path

```
User query: "What are the Duke criteria for diagnosing IE?"
│
├─ Step 1: Embed query → cosine search against chunk_segments.embedding
│
├─ Step 2: Top-K segment hits
│          → "seg-3.4" (3.4 Diagnostic criteria) similarity: 0.91
│
├─ Step 3: Fetch parent H1 chunk: SELECT content FROM chunks WHERE chunk_id = "a1b2-h1"
│          Slice focused context: content[20800:29300]  (start_char:end_char)
│
└─ Step 4: LLM receives:
           [SEGMENT — citation] segment: "seg-3.4" | sliced content "Modified Duke criteria..."
           [PARENT — context]   chunk: "a1b2-h1"  | full H1 content (or sliced wider window)
```

### New Table Schema

```sql
CREATE TABLE chunk_segments (
    segment_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chunk_id       UUID NOT NULL REFERENCES chunks(chunk_id) ON DELETE CASCADE,
    h2_header      TEXT,               -- e.g., "3.4 Diagnostic criteria"
    segment_index  INT,                -- position within parent chunk (0-based)
    start_char     INT NOT NULL,       -- char offset in parent chunk content
    end_char       INT NOT NULL,       -- char offset in parent chunk content
    embedding      vector(1536),       -- H2-level focused embedding
    created_at     TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX ON chunk_segments USING ivfflat (embedding vector_cosine_ops);
CREATE INDEX ON chunk_segments (chunk_id);
```

### Ingestion Change (Segment Population)

Add a post-chunking pass in `ingest.py` or a standalone `ingestion/segment_builder.py`:

```python
# For each existing H1 chunk in NeonDB:
# 1. Parse content at ## boundaries → extract H2 sections with start/end char positions
# 2. Embed each H2 section text
# 3. INSERT into chunk_segments

def build_segments_for_chunk(chunk_id, content):
    sections = split_at_h2_headers(content)  # returns [{header, start, end, text}, ...]
    for i, sec in enumerate(sections):
        embedding = embed(sec['text'])
        db.execute("""
            INSERT INTO chunk_segments (chunk_id, h2_header, segment_index, start_char, end_char, embedding)
            VALUES ($1, $2, $3, $4, $5, $6)
        """, chunk_id, sec['header'], i, sec['start'], sec['end'], embedding)
```

This can be run as a **one-time backfill against existing NeonDB data** — no re-chunking of the `chunks` table.

### KG Extraction Change

For KG extraction, graph_builder still reads from `chunks` (H1), but now also receives the segment boundaries to pass into `_extract_triples_with_llm`. The triple is tagged with both the parent `chunk_id` and the matching `segment_id`:

```python
# In build_relationship_graph: iterate segments for this chunk
segments = db.query("SELECT * FROM chunk_segments WHERE chunk_id = $1", chunk.chunk_id)
for seg in segments:
    sub_text = chunk.content[seg.start_char:seg.end_char]
    triples = await self._extract_triples_with_llm(sub_text, ...)
    for t in triples:
        t['cpg_chunk_id'] = chunk.chunk_id    # original stable H1 UUID
        t['segment_id']   = seg.segment_id    # H2 segment pointer
        t['subchunk_start_char'] = seg.start_char
```

### Trade-offs

| Decision | Trade-off |
|----------|-----------|
| Existing chunk_ids untouched | All stable citations remain valid. NeonDB `chunks` table needs no migration. |
| New table required | One migration script + index build. Segment table must be kept in sync if chunks are re-ingested later. |
| H1 embedding kept | H1 vector still exists; retrieval must explicitly query `chunk_segments` not `chunks` to get H2 precision. Old code querying `chunks` still works but with lower precision. |
| Neo4j gains `segment_id` | No `DETACH DELETE` required. Existing triples get `segment_id` added via a backfill update after segmentation. |

### Implementation Steps

| Step | Action | Files | Risk |
|------|--------|-------|------|
| B-1 | Create `chunk_segments` table + index | Migration SQL | Low |
| B-2 | Write `segment_builder.py` — backfill segments from existing chunks | New file | Low |
| B-3 | Run backfill against NeonDB (no re-ingestion) | CLI | Low |
| B-4 | Update `graph_builder.py` to read segments for KG extraction | `graph_builder.py` L566–614 | Low |
| B-5 | Update `db_utils.py` vector search to query `chunk_segments` | `db_utils.py` L369–522 | Low |
| B-6 | Update `tools.py` to return `{segment, parent_chunk}` | `tools.py` L142–257 | Low |
| B-7 | Backfill `segment_id` onto existing Neo4j triples | Cypher batch | Low |

---

## 6. Shared Fix — graph_builder Sub-chunk Improvements (Both Options)

Regardless of which option is chosen, the following `graph_builder.py` changes apply:

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
# fetch chunk content from NeonDB by cpg_chunk_id (or chunk_id / segment_id)
# slice: content[subchunk_start_char : subchunk_start_char + 6000]
```

---

## 7. Verification Checklist

| Check | Option A | Option B |
|-------|----------|----------|
| Query "Duke criteria IE" → correct section retrieved | H2 child chunk at rank 1 | Segment at rank 1 |
| Neo4j triple → NeonDB chunk (clickable citation) | `cpg_chunk_id` = H2 UUID | `segment_id` → parent `chunk_id` |
| section-3-diagnosis chunk count in NeonDB | 5 rows (1 H1 + 4 H2) | 1 row (unchanged) + 4 segments |
| Sub-chunk position tracking | `subchunk_focus_start` in triple | `subchunk_focus_start` in triple |
| KG extraction LLM calls for IE section 3 | 4 H2 chunks × 1–2 sub-chunks | Same (reads segments instead of H1) |
| **All `documents.icd11_scope` populated + `scope_verified = TRUE`** | Yes — new CPGs pass through §3.1 pipeline | Same |
| Every code in `documents.icd11_scope` exists in `icd11_codes` | No dangling refs | No dangling refs |

---

## 8. KG Building — Ephemeral Sub-windowing with Context Bands

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

The code changes (K-1..K-5) land first as a deploy. The KG itself is then rebuilt during **A-8** in the §3 implementation steps. Strict order:

| Order | Command | Purpose |
|-------|---------|---------|
| 1 | `pytest tests/test_graph_builder_subwindow.py` | Unit-test the new window dicts + prompt template before touching prod Bedrock spend |
| 2 | Backup current graph: `cypher-shell "CALL apoc.export.cypher.all('backups/kg_pre_step2.cypher', {format:'cypher-shell'})"` | Roll-back point. Skip only if previous backup `backups/kg_backup_2026-05-12.cypher` is recent enough |
| 3 | A-7 must be complete — verify `SELECT count(*) FROM chunks WHERE chunk_level = 'h2'` returns expected H2 count | KG build reads H2 rows; running before A-7 would extract from the old polluted H1 rows |
| 4 | `cypher-shell "MATCH (n) DETACH DELETE n"` | Wipe old graph (564 Graphiti edges + 13 old typed triples). Confirmed safe — see Phase_A_Findings.md open question 3 |
| 5 | `python -m ingestion.ingest --graph-only --all-cpgs` (or per-CPG: `--cpg <name>`) | Runs `build_relationship_graph` with new sub-window context bands against H2 chunks |
| 6 | Smoke-check: `MATCH ()-[r]->() RETURN type(r) AS rel, count(r) AS cnt ORDER BY cnt DESC` | Expect typed clinical relations (TREATS, INCREASES_RISK_OF, ASSESSED_BY, etc.) — no `MENTIONS` / `RELATES_TO` Graphiti residue |
| 7 | Sample triple → NeonDB resolution: pick one triple, confirm `r.cpg_chunk_id` exists in `chunks` and `chunk_level = 'h2'` | Validates the P2 citation link |

**Per-CPG dry run first.** Before the full `--all-cpgs` run, do one small CPG (Erectile-Dysfunction, 6 filtered chunks, ~$0.013) end-to-end through steps 4–7 to catch prompt-template bugs cheaply. Only proceed to `--all-cpgs` if the dry run looks clean.

**Cost expectation:** ~720 sub-windows × $0.0022 ≈ $1.60 across all CPGs at current size. With context bands (~+3k chars each) the figure rises to ~$2.10. Below the $50 threshold; no re-approval needed.

**Rate-limit safety:** if running A-8 unbatched takes >10 min for the full corpus, apply the `Semaphore(5)` batching from Step 3 §2.6 early. Functional equivalent — just paid down sooner if you need the wall time back.

---

## 9. Retrieval/Synthesis — Window Slicing as Outlier Handler

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

Note: this code can be written and merged in Step 1 *before* parent-child ingest exists — it just won't trigger until Option A/B lands a real `child.start_char` / `parent.content` pair. Until then, treat retrieved chunks as standalone (no parent) and skip the helper.
