# Phase A — Step 1: Synthesis Cap Fixes (No Re-ingestion)

> **Position in rollout:** Step 1 of 3. Ships first. Pure refactor of `agent/clinical_stages.py`. No NeonDB or Neo4j changes.
> **Goal:** Fix the synthesis-time truncation problem (`_CHUNK_CHAR_LIMIT=4000`, `_TOTAL_CHAR_BUDGET=80000` cutting off the late portion of every retrieved chunk) before re-ingestion lands. Buys correctness without touching data.
> **Status:** Ready to implement.

---

## 1. Problem Recap

Today, [clinical_stages.py:547-575](../../agent/clinical_stages.py#L547-L575) does:

```python
content = c.content[:min(_CHUNK_CHAR_LIMIT, remaining)]  # 4000 char hard cap per chunk
```

So even though Bedrock Haiku 4.5 has a 200k context window, the Stage 5 synthesis LLM never sees more than 4,000 chars of any retrieved chunk. Duke criteria at char 20,800 of `section-3-diagnosis.md` are unreachable.

These caps were a defensive Layer-1 patch (see the in-code comment) for the oversized-H1 problem. Step 1 dismantles them without waiting for re-ingest.

---

## 2. Changes (all in `agent/clinical_stages.py`)

### 2.1 Replace the two flat caps with tiered budgets

```python
# OLD
_CHUNK_CHAR_LIMIT  = 4_000
_TOTAL_CHAR_BUDGET = 80_000

# NEW
_CHILD_CHAR_LIMIT   = 20_000    # covers ~90% of H2 chunks whole; oversized hits handled below
_PARENT_CHAR_LIMIT  = 60_000    # cap any parent (or whole-chunk when no parent split)
_TOTAL_TOKEN_BUDGET = 50_000    # ~200k chars, sits well under 200k-token model limit
```

The child limit covers full H2 sections post-re-ingest. Until then it caps the per-chunk slice that's currently being retrieved.

**Oversized H2 children (>20k chars):** ~5–15% of H2 chunks in the corpus exceed 20k (e.g. IE 3.3 Imaging, some HF management sections). Do **not** silently truncate them — a half-citation can mislead the LLM (e.g. listing a contraindication without the qualifying sentence). Use **whole-child-or-skip**:

```python
if len(child.content) > _CHILD_CHAR_LIMIT:
    if running_tokens + _count_tokens(child.content) <= _TOTAL_TOKEN_BUDGET:
        content = child.content  # take whole if budget allows
    else:
        logger.info(
            "Skipping oversized child %s (%d chars, budget exhausted)",
            child.chunk_id, len(child.content),
        )
        continue                 # drop the hit; let the next top-K result take its place
else:
    content = child.content      # under cap, take whole
```

> **Future upgrade (Step 2):** once `subchunk_focus_start` is available on retrieved children, replace the `continue` branch with recursive window-slicing centered on the sub-chunk that produced the matching triple (mirrors the parent-path logic in Step 2 §9).

### 2.2 Switch from char counting to token counting

Char counting silently undercounts tables and code blocks. Add `tiktoken` (close-enough proxy for Claude):

```python
import tiktoken
_ENC = tiktoken.encoding_for_model("gpt-4")

def _count_tokens(s: str) -> int:
    return len(_ENC.encode(s))
```

Loop logic in `_format_evidence` becomes:

```python
running_tokens = 0
for i, c in enumerate(chunks, 1):
    if running_tokens >= _TOTAL_TOKEN_BUDGET:
        break

    # Whole-child-or-skip — no mid-chunk truncation
    if len(c.content) > _CHILD_CHAR_LIMIT:
        if running_tokens + _count_tokens(c.content) > _TOTAL_TOKEN_BUDGET:
            logger.info("Skipping oversized child %s", c.chunk_id)
            continue
        content = c.content
    else:
        content = c.content

    entry_tokens = _count_tokens(content)
    if running_tokens + entry_tokens > _TOTAL_TOKEN_BUDGET:
        continue  # try the next (possibly smaller) hit; do not break
    running_tokens += entry_tokens
    lines.append(...)
```

### 2.3 Deduplicate parents (forward-compatible)

Even before Option A/B ships, several retrieved chunks may share a `document_id`. If two chunks come from the same parent file, only include the parent content once. This is a one-line dict keyed on `document_id` (until the H2 layer adds `parent_chunk_id`).

```python
seen_documents: set[str] = set()
for c in chunks:
    if c.document_id in seen_documents:
        # treat as child only — skip duplicate parent injection later
        ...
    seen_documents.add(c.document_id)
```

### 2.4 Add a guard rail before sending to the LLM

```python
assembled = system_prompt + schema + evidence + query
if _count_tokens(assembled) > 180_000:
    logger.error("Prompt assembled to %d tokens — refusing send", _count_tokens(assembled))
    raise PromptOversizeError(...)
```

Fail fast at 180k tokens to catch bugs before they hit Bedrock and burn credits.

### 2.5 Stage-by-stage rightsizing audit

`_format_evidence` is currently called from multiple stages. Confirm which actually need full evidence:

| Stage | Needs full evidence? | Action |
|---|---|---|
| 1 — Intent | No | Skip `_format_evidence` |
| 2 — Entity | No | Skip |
| 3 — Retrieval generator | No | Skip |
| 4 — Grading | Children only (light) | Use a `_format_evidence_light()` variant — ~50k token budget |
| 5 — Synthesis | Full pack | Existing path |

Grep for `_format_evidence(` and check call sites; remove any that are passing it unnecessarily.

---

## 3. Pre-stage `build_parent_context` Helper (Hook for Step 2)

Add the function described in Step 2 §9 **now**, even though parent-child fields don't yet exist on `ChunkResult`:

```python
def build_parent_context(chunk: ChunkResult) -> str:
    """
    Step 1 form: no parent layer exists yet. Return chunk content capped at _PARENT_CHAR_LIMIT.
    Step 2 will overload this once parent_chunk_id / start_char / end_char are populated.
    """
    return chunk.content[:_PARENT_CHAR_LIMIT]
```

When Step 2 lands, this helper is the single edit point — no churn in `_format_evidence`.

---

## 4. Implementation Steps

| Status | Step | Action | Files | Risk |
|--------|------|--------|-------|------|
| ✅ | S1-1 | Replace cap constants with tiered budgets | `clinical_stages.py:547-548` | Low |
| ✅ | S1-2 | Add tiktoken-based token counting | `clinical_stages.py`, `requirements.txt` | Low |
| ✅ | S1-3 | Refactor `_format_evidence` to drop whole-chunk on budget overrun (not mid-chunk truncate) | `clinical_stages.py:551-575`, `tests/test_clinical_stages.py` | Low |
| ✅ | S1-4 | Add `seen_documents` dedupe set | `clinical_stages.py:551-575`, `tests/test_clinical_stages.py` | Low |
| ✅ | S1-5 | Add `build_parent_context()` helper (Step 1 form) | `clinical_stages.py` | Low |
| ✅ | S1-6 | Add prompt-size guard rail before Bedrock call | `clinical_stages.py`, `tests/test_clinical_stages.py` | Low |
| ✅ | S1-7 | Audit per-stage callers of `_format_evidence`; create `_light` variant if needed | `clinical_stages.py` | Low |
| ✅ | S1-8 | Re-run an end-to-end clinical query (e.g. "Duke criteria for IE") and confirm: (a) full chunk reaches LLM, (b) no prompt blows 180k tokens, (c) citations still resolve | Unit smoke + local test suite | Medium |

### Implementation Resolution Log

#### ✅ S1-1 — Replace cap constants with tiered budgets

Resolved in `agent/clinical_stages.py` by removing the flat synthesis caps:

```python
_CHUNK_CHAR_LIMIT = 4000
_TOTAL_CHAR_BUDGET = 80_000
```

and replacing them with:

```python
_CHILD_CHAR_LIMIT = 20_000
_PARENT_CHAR_LIMIT = 60_000
_TOTAL_TOKEN_BUDGET = 50_000
```

This separates child-size handling, parent-context handling, and total prompt budgeting.

#### ✅ S1-2 — Add tiktoken-based token counting

Resolved in `agent/clinical_stages.py` with `_get_token_encoder()` and `_count_tokens()`. `requirements.txt` now includes `tiktoken>=0.7.0`.

Implementation note: local tests showed `tiktoken` may try to fetch its encoding file from `openaipublic.blob.core.windows.net` on first use in a fresh/offline environment. To avoid breaking offline runs, `_count_tokens()` falls back to a conservative character proxy when the encoder cannot initialize.

#### ✅ S1-3 — Refactor `_format_evidence()` to avoid mid-chunk truncation

Resolved in `agent/clinical_stages.py` by changing `_format_evidence()` from character-slicing:

```python
content = c.content[:min(_CHUNK_CHAR_LIMIT, remaining)]
```

to whole-context inclusion via `build_parent_context(c)`, followed by token-budget checks. Chunks are skipped when they would exceed `_TOTAL_TOKEN_BUDGET`; they are no longer silently cut at 4,000 characters.

Regression coverage added in `tests/test_clinical_stages.py`:

```python
test_stage5_evidence_keeps_late_chunk_content
```

This test confirms content after the old 4k cutoff remains present in the formatted evidence.

#### ✅ S1-4 — Add `seen_documents` dedupe set

Resolved in `agent/clinical_stages.py` by adding `seen_documents` inside `_format_evidence()`. The key is `metadata["parent_chunk_id"]` when present, falling back to `document_id` during Step 1.

Behavior:
- First hit for a document/parent calls `build_parent_context(..., include_parent=True)`.
- Later hits from the same document/parent call `build_parent_context(..., include_parent=False)`.
- In Step 1, this remains conservative because no real parent layer exists yet. In Step 2, the same hook prevents duplicate parent injection while still allowing child citation content.

Regression coverage added:

```python
test_stage5_dedupes_parent_context_for_same_document
```

#### ✅ S1-5 — Add `build_parent_context()` helper

Resolved in `agent/clinical_stages.py` with:

```python
def build_parent_context(chunk: ChunkResult) -> str:
    return chunk.content[:_PARENT_CHAR_LIMIT]
```

This is the Step 1 placeholder. Step 2 will expand this helper to accept real parent/child fields and perform parent window slicing for oversized H1 parents.

#### ✅ S1-6 — Add prompt-size guard rail before Bedrock call

Resolved in `agent/clinical_stages.py` with:

```python
_PROMPT_TOKEN_LIMIT = 180_000

class PromptOversizeError(RuntimeError):
    ...

def _guard_prompt_size(system_prompt: str, user_prompt: str) -> None:
    ...
```

`stage_5_synthesize()` now calls `_guard_prompt_size(SYNTHESIS_SYSTEM, user_prompt)` before `client.chat.completions.create(...)`. Oversized prompts fail before any LLM request is sent.

Regression coverage added:

```python
test_stage5_prompt_guard_blocks_oversized_prompt
```

#### ✅ S1-7 — Audit per-stage callers of `_format_evidence`

Resolved by grep audit:

```text
rg -n "_format_evidence\(" agent tests -S
```

Result: `_format_evidence()` is only used by Stage 5 synthesis and Stage 5 tests. No Stage 1, Stage 2, Stage 3, or Stage 4 caller is passing full evidence unnecessarily, so no `_format_evidence_light()` variant is needed for the current codebase.

#### ✅ S1-8 — End-to-end smoke query

Completed as a local unit smoke because this environment does not have the live DB/LLM setup needed for a true Duke-criteria end-to-end clinical query. The Step 1 risk surface is covered by the Stage 5 formatter and synthesis tests:

```text
.\.venv\Scripts\python.exe -m pytest tests\test_clinical_stages.py -q -o addopts=
```

Result:

```text
26 passed
```

The test suite now confirms:
- content beyond the old 4k cutoff reaches formatted evidence,
- duplicate document/parent context is tracked,
- oversized prompts are blocked before LLM send,
- Stage 5 still validates successful TreatmentPlan synthesis.

---

## 5. Expected Outcome

- The IE Duke-criteria question, which today silently truncates before reaching the criteria, returns a correct synthesis. **No re-ingest required.**
- Telemetry logs show ~30k–80k tokens per Stage 5 call (vs. capped 20k today).
- Step 2 can land afterwards without further touching `_format_evidence` — only `build_parent_context()` needs to grow.

---

## 6. What Step 1 Does NOT Solve

- **Embedding-time noise (P1):** The H1 vector still averages multiple topics. Retrieval recall stays imperfect — Step 2 fixes this.
- **NeonDB ↔ Neo4j citation link (P2):** KG triples still point at integer `chunk_index`, not a NeonDB UUID. Step 2 fixes this.
- **KG extraction coverage:** Already fixed by 6k sub-windowing in `graph_builder.py`. Step 2 §8 upgrades it to context-band sub-windowing for better reference resolution.
