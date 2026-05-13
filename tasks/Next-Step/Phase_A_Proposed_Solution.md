# Phase A — Sub-chunk Context Tracing: Problem Analysis & Solutions

> **Status:** Analysis complete. Three solution paths documented — choose based on willingness to re-chunk.
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

Three solution paths exist, ordered by invasiveness:

| Option | Re-chunk NeonDB? | DB schema change? | Fixes P1 (precision) | Fixes P2 (citation link) | Fixes P3 (boundary) | Effort |
|--------|-----------------|------------------|---------------------|--------------------------|---------------------|--------|
| **A — H2 Re-chunk** | Yes — full re-ingest | Add 2 columns to `chunks` | Full | Full | Full | High |
| **B — Segment Index** | No — new table only | New `chunk_segments` table | Full | Full | Full | Medium |
| **C — Runtime Reranking** | No changes | No changes | Partial | None | Partial | Low |

**Recommendation:**
- If long-term citation traceability matters (KG triple → NeonDB chunk → UI): pick **Option A or B**.
- Option A is cleaner (one source of truth), but requires re-ingestion.
- Option B preserves all existing chunk_ids (zero risk to stable citations) and adds a separate index table.
- Option C is the fastest to ship but does not fix the NeonDB↔Neo4j link at all.

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
| A-1 | Add `chunk_level` + `parent_chunk_id` columns | Migration SQL | Low — additive |
| A-2 | Update `MarkdownChunker` for H1→H2 split | `chunker.py` L81–318 | Medium |
| A-3 | Update `ingest.py` to read H2 chunks for KG | `ingest.py` | Low |
| A-4 | Update `db_utils.py` vector search filter | `db_utils.py` L369–522 | Low |
| A-5 | Update `tools.py` to return `{child, parent}` | `tools.py` L142–257 | Low |
| A-6 | Re-ingest all CPGs | CLI batch run | Medium |

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

## 5. Option C — Runtime H2 Reranking (Zero DB Changes)

### Architecture

No NeonDB changes at all. After H1 chunks are retrieved by the existing vector search, a lightweight second-pass splits each H1 chunk at H2 headers in memory and reranks the sections against the query.

```
User query: "What are the Duke criteria for diagnosing IE?"
│
├─ Step 1: Existing vector search → top-K H1 chunks (unchanged)
│          → "a1b2-h1" (section-3-diagnosis, 51k chars) similarity: 0.72
│
├─ Step 2 (NEW): Split each retrieved H1 chunk at ## headers in memory
│          → sections: [3.1 (500-3200), 3.2 (3200-10400), 3.3 (10400-20800), 3.4 (20800-29300)]
│
├─ Step 3 (NEW): Score each section against the query
│          Method A (fast): BM25 / TF-IDF keyword overlap
│          Method B (precise): embed each section + cosine against query embedding
│          → 3.4 Diagnostic criteria: score 0.91  ← top section
│
└─ Step 4: LLM receives:
           [FOCUSED — citation] "3.4 Diagnostic criteria": "Modified Duke criteria include..."
           [FULL — context]     full H1 chunk for surrounding clinical context
```

### Code Change (Retrieval Layer Only)

**File:** [agent/tools.py:142-257](../../agent/tools.py)

```python
def _rerank_h2_sections(chunk_content: str, query_embedding: list[float]) -> dict:
    """Split H1 content at ## headers, find most relevant H2 section."""
    import re
    sections = re.split(r'\n(?=## )', chunk_content)
    if len(sections) <= 1:
        return {"section_text": chunk_content, "start_char": 0}
    best, best_score, offset = None, -1, 0
    for sec in sections:
        sec_embedding = embed(sec[:6000])          # embed first 6k of section
        score = cosine_similarity(query_embedding, sec_embedding)
        if score > best_score:
            best_score, best = score, {"section_text": sec, "start_char": offset}
        offset += len(sec)
    return best

# In retrieval tool, after vector_search():
for chunk in retrieved_chunks:
    focused = _rerank_h2_sections(chunk.content, query_embedding)
    chunk.citation_text = focused['section_text']
    chunk.citation_start = focused['start_char']
```

### Limitations of Option C

| Limitation | Impact |
|-----------|--------|
| Extra embedding call per retrieved chunk | +100–300 ms latency per query |
| No fix for NeonDB↔Neo4j citation link | KG triple `chunk_index` still doesn't map to a NeonDB UUID |
| H1 embedding noise not fixed at ingestion | Retrieval recall is still limited by the noisy H1 vector — a query may not even retrieve the right H1 chunk to rerank |
| No persistent position tracking | `start_char` is computed at runtime, not stored — cannot reconstruct citation from a saved triple |

**Option C is best used as a quick interim fix while planning Option A or B.**

---

## 6. Shared Fix — graph_builder Sub-chunk Improvements (All Options)

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

| Check | Option A | Option B | Option C |
|-------|----------|----------|----------|
| Query "Duke criteria IE" → correct section retrieved | H2 child chunk at rank 1 | Segment at rank 1 | H2 section reranked to top |
| Neo4j triple → NeonDB chunk (clickable citation) | `cpg_chunk_id` = H2 UUID | `segment_id` → parent `chunk_id` | Not fixed |
| section-3-diagnosis chunk count in NeonDB | 5 rows (1 H1 + 4 H2) | 1 row (unchanged) + 4 segments | 1 row (unchanged) |
| Sub-chunk position tracking | `subchunk_start_char` in triple | `subchunk_start_char` in triple | `start_char` computed at runtime |
| KG extraction LLM calls for IE section 3 | 4 H2 chunks × 1–2 sub-chunks | Same (reads segments instead of H1) | Unchanged (H1 → 9 sub-chunks) |
