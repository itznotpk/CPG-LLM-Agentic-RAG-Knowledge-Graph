"""
Markdown document chunker for RAG systems.

Three-tier chain model:
  Pass 1 — split at # (H1) → one H1 parent row per section (no embedding).
  Pass 2 — split each H1 at ## (H2) → embedded child chunks (chunk_level='h2').
  Cap     — H2 > 8 000 chars becomes an unembedded intermediate (chunk_level='h2',
            cap_split=True); its ### subsections become embedded chunk_level='h3' rows
            that point at the cap-split H2 via parent_chunk_id (H3 → H2 → H1 chain).
  Fallback — if no ## exists, the whole H1 becomes chunk_level='h1_leaf' (embedded).
"""

import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

from langchain_text_splitters import MarkdownHeaderTextSplitter

try:
    import tiktoken
    _enc = tiktoken.encoding_for_model("text-embedding-3-small")
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False

logger = logging.getLogger(__name__)

_H2_MAX_CHARS = 8_000


@dataclass
class ChunkingConfig:
    """Configuration for chunking."""
    chunk_size: int = 1000
    chunk_overlap: int = 200

    def __post_init__(self):
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("Chunk overlap must be less than chunk size")


@dataclass
class DocumentChunk:
    """Represents a document chunk."""
    content: str
    index: int
    start_char: int
    end_char: int
    metadata: Dict[str, Any]
    chunk_level: str = 'h1_leaf'   # 'h1' | 'h2' | 'h3' | 'h1_leaf'
    token_count: Optional[int] = None

    def __post_init__(self):
        if self.token_count is None:
            if TIKTOKEN_AVAILABLE:
                self.token_count = len(_enc.encode(self.content))
            else:
                self.token_count = len(self.content) // 4


# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

OVERLAP_BLOCK_PATTERN = re.compile(
    r'(?:'
        r'<!--\s*OVERLAP CONTENT\s*-->'
        r'\s*\n'
        r'(.*?)'
        r'<!--\s*END OVERLAP CONTENT\s*-->'
    r'|'
        r'<!--\s*=+\s*-->\s*\n'
        r'<!--\s*OVERLAP CONTENT FROM:.*?-->\s*\n'
        r'(?:<!--.*?-->\s*\n)*'
        r'(.*?)'
        r'<!--\s*END OVERLAP FROM:.*?-->'
    r')',
    re.DOTALL
)

METADATA_BLOCK_PATTERN = re.compile(
    r'<!--\s*METADATA\s*\n.*?\n\s*-->',
    re.DOTALL | re.IGNORECASE
)

PARENT_ONLY_BLOCK_PATTERN = re.compile(
    r'<!--\s*parent_only_reference_start\s*-->'
    r'(.*?)'
    r'<!--\s*parent_only_reference_end\s*-->',
    re.DOTALL | re.IGNORECASE
)

CROSS_REF_PATTERN = re.compile(
    r'<!--\s*cross_ref'
    r'(?:\s+target_file="(?P<target_file>[^"]*)")?'
    r'(?:\s+target_heading="(?P<target_heading>[^"]*)")?'
    r'(?:\s+target_kind="(?P<target_kind>[^"]*)")?'
    r'\s*-->',
    re.IGNORECASE
)

_VALID_TARGET_KINDS = {'h1_section', 'h2_section', 'h3_section', 'algorithm_flowchart', 'appendix'}

# Evidence tag patterns. Three grading schemes coexist in the corpus and use
# disjoint token sets, so a single union regex is safe — we never need to
# disambiguate which scheme a captured token belongs to at extract time:
#   ESC     : Grade I/IIa/IIb/III   Level A/B/C
#   USPSTF  : Grade A/B/C           Level I/II-1/II-2/II-3/III
#   SIGN50  : Grade A/B/C/D + ✓     Level 1++/1+/1-/2++/2+/2-/3/4
# Order the SIGN50 plus-suffix alternatives longest-first so "1++" matches
# before "1+", and so on. The trailing "✓ good-practice point" marker is
# emitted only in definition tables in the corpus, not as an inline tag,
# so it is intentionally NOT captured here.
_GRADE_TOKEN = r'(?:I{1,3}[-]?[a-c]?|A|B|C|D)'
# Level tokens, longest-first to avoid greedy mis-segmentation:
#   IV                              (Thyroid CPG extends USPSTF Levels to IV)
#   I/II/III with optional "-N"     (USPSTF II-1/II-2/II-3, also ESC II-a captured by Grade)
#   1++ / 1+ / 1- / 2++ / 2+ / 2-   (SIGN50 — longest first so "1++" wins over "1+")
#   bare digit with optional "-N"   (plain 3 / 4, plus any future numeric range)
#   A/B/C                           (ESC Level)
_LEVEL_TOKEN = (
    r'(?:IV'
    r'|I{1,3}(?:\s*-\s*\d+)?'
    r'|1\+\+|1\+|1-|2\+\+|2\+|2-'
    r'|\d+(?:\s*-\s*\d+)?'
    r'|[A-C])'
)


# A bracketed or parenthesised evidence-tag block. Body must begin with the
# keyword "Grade" or "Level"; ** wrappers and surrounding whitespace are
# tolerated. The block body is parsed by _parse_evidence_body below; if the
# body is not a strict sequence of {keyword? + token} segments, the whole
# block is rejected (so prose like "[Grade III pressure ulcer]" cannot
# false-match).
_EVIDENCE_BLOCK = re.compile(
    r'\*{0,2}'
    r'(?:\[(?P<bbody>(?:Grade|Level)[^\]]*?)\]'
    r'|\((?P<pbody>(?:Grade|Level)[^)]*?)\))'
    r'\*{0,2}',
    re.IGNORECASE,
)
# Splits a tag-block body into segments. Real-world separators observed in
# the corpus: comma, semicolon, slash, and the word "and" between bands.
_EVIDENCE_SEP = re.compile(r'\s*[,;/]\s*|\s+and\s+', re.IGNORECASE)
# Strict per-segment shape: optional Grade|Level keyword + exactly one token.
_EVIDENCE_SEGMENT = re.compile(
    rf'^(?:(?P<kw>Grade|Level)\s+)?(?P<tok>{_GRADE_TOKEN}|{_LEVEL_TOKEN})\s*$',
    re.IGNORECASE,
)


def _parse_evidence_body(body: str):
    """
    Parse a tag-block body into [(kind, token), ...].

    Handles every inline form seen in the corpus:
      [Grade A]                              · single grade
      [Level II-2]                           · single level (USPSTF / SIGN50)
      [Level IV]                             · Thyroid USPSTF extension
      [Grade I, Level A]   [Grade I Level A] · combined (comma or whitespace)
      [Level A, Grade I]                     · combined, level-first
      [Grade I, Level A/C]                   · combined with multi-level slash
      [Level I; Level II-1]                  · multi-level, semicolon, keyword repeated
      [Level I, Level II-3, Level III]       · multi-level, comma, keyword repeated
      [Level III, II]   [Level III, IV]      · multi-level, bare token inherits kind
      [Level A/B/C]                          · multi-level, slash separated
      (Grade A)   (Level II-2)               · parenthesised forms
      **[Grade D]**                          · bold-wrapped

    Returns None (and the caller discards the block) if any segment fails the
    strict shape — this prevents prose blocks like "[Grade III pressure ulcer]"
    from being mis-captured.
    """
    # Normalise: insert a comma before any non-leading "Grade "/"Level " keyword
    # so whitespace-separated combined forms like "[Grade I Level A]" parse as
    # two segments without further special-casing.
    body = re.sub(r'\s+(?=(?:Grade|Level)\b)', ',', body.strip(), flags=re.IGNORECASE)
    out = []
    current_kind = None
    for raw in _EVIDENCE_SEP.split(body):
        seg = raw.strip()
        if not seg:
            continue
        sm = _EVIDENCE_SEGMENT.match(seg)
        if not sm:
            return None  # extra prose or unrecognised token — reject block
        kw = sm.group('kw')
        if kw:
            current_kind = kw.capitalize()
        if not current_kind:
            return None  # bare token before any keyword — reject
        token = re.sub(r'\s+', '', sm.group('tok').upper())
        out.append((current_kind, token))
    return out or None


def _extract_evidence_tags(text: str) -> Dict[str, list]:
    grades, levels, who_classes = [], [], []

    for m in _EVIDENCE_BLOCK.finditer(text):
        body = m.group('bbody') or m.group('pbody') or ''
        parsed = _parse_evidence_body(body)
        if not parsed:
            continue
        for kind, token in parsed:
            bucket = grades if kind == 'Grade' else levels
            if token not in bucket:
                bucket.append(token)

    # WHO classification — covers two scales that share the "WHO" word:
    #   * WHO Functional Class (symptom severity; PAH, stroke, etc.)
    #   * modified-WHO maternal-risk Class (Heart Disease in Pregnancy)
    # The mWHO scale has FIVE ordinal bands: I, II, II-III, III, IV — the
    # "II-III" band is its OWN category (between II and III), NOT a II+III
    # range, so it is emitted as a single token "II-III".
    #
    # Forms in the corpus (bracketed and bare prose, incl. OCR garble):
    #   [WHO Class IV]  ·  (WHO Class IV)  ·  WHO class III & IV
    #   [WHO Class II-III & III]  ·  NYHA/ WHO Class II-III, III & IV
    #   [WHO Class I-IV] (PAH range = all FC bands)  ·  WHO-FC II
    #   WHO functional class I  ·  WHO ClassII  ·  WHO CLASS Il / Ill (OCR L→I)
    # Numerals: explicit longest-first alternation so "IV"/"III" win over
    # shorter prefixes. OCR often renders roman "I" as lowercase "l", so the
    # body is normalised (l/L -> I) immediately after capture.
    # A trailing severity qualifier such as "III (severe)" is its OWN tier
    # in the Modified-WHO mortality table (plain III = 1-5%, III (severe) =
    # 5-15%), so it is preserved as a distinct token "III-severe".
    _RN = r'(?:IV|III|II|I)'
    _ORDER = ['I', 'II', 'III', 'IV']
    # Named group so positional numbering can never collide with groups
    # inside the body/short-form patterns.
    _QUAL = r'(?:\s*\(\s*(?P<qual>severe|mild|moderate)\s*\))?'

    def _emit(tokens):
        for w in tokens:
            if w and w not in who_classes:
                who_classes.append(w)

    def _expand_part(part):
        """A single band expression -> list of canonical band tokens."""
        rng = re.match(rf'^({_RN})\s*[-–]\s*({_RN})$', part)
        if rng:
            a, b = rng.group(1), rng.group(2)
            if a in _ORDER and b in _ORDER and _ORDER.index(a) < _ORDER.index(b):
                if a == 'II' and b == 'III':
                    # mWHO intermediate band — a single category, NOT a
                    # II+III split. Kept whole as "II-III".
                    return ['II-III']
                # Wider range (e.g. PAH "I-IV") = every band spanned.
                return _ORDER[_ORDER.index(a):_ORDER.index(b) + 1]
            return [part]
        if part in _ORDER or part == 'II-III':
            return [part]
        return None  # not a recognised band expression

    for m in re.finditer(
        r'WHO[\s\-]*(?:functional\s+)?(?:class|FC)\s*'
        r'(?P<body>[IVlL]{1,4}'                         # first band (OCR-safe)
        r'(?:\s*[-–]\s*[IVlL]{1,4})?'                    # optional "-III" range
        r'(?:\s*(?:&|,|\band\b)\s*[IVlL]{1,4}'           # connector list...
        r'(?:\s*[-–]\s*[IVlL]{1,4})?)*'                  # ...each maybe a range
        rf'){_QUAL}(?![A-Za-z])',                        # optional qualifier
        text, re.IGNORECASE,
    ):
        qual = (m.group('qual') or '').lower()
        # Normalise OCR lowercase-L -> roman I before parsing.
        body = m.group('body').replace('l', 'I').replace('L', 'I').upper()
        # Split on &/comma/"and" into separate band expressions; a bare
        # hyphen inside a part is a range (e.g. "II-III").
        parts = [p.strip() for p in re.split(r'\s*(?:&|,|\bAND\b)\s*', body) if p.strip()]
        for idx, part in enumerate(parts):
            tokens = _expand_part(part)
            if tokens is None:
                continue
            # The qualifier attaches only to the LAST band in the expression
            # (e.g. "WHO Class III (severe)" -> "III-severe").
            if qual and idx == len(parts) - 1 and len(tokens) == 1:
                tokens = [f'{tokens[0]}-{qual}']
            _emit(tokens)

    # Short inline form "WHO II" / "WHO III" (no Class/FC word) — only trust
    # it inside a WHO-classification region, else "WHO" + a stray numeral
    # would false-match. Anchor = a [WHO Class ...] tag or a "Modified WHO" /
    # "WHO Class |" table marker anywhere in the chunk. "or" is accepted as a
    # connector here (e.g. "not considered WHO I or IV").
    if re.search(r'\[WHO\s+Class|Modified\s+WHO|WHO\s+Class\s*\|', text, re.IGNORECASE):
        for m in re.finditer(
            rf'\bWHO\s+(?P<a>{_RN})'
            rf'(?:\s*(?:[-–]|&|,|\bor\b|\band\b)\s*(?P<b>{_RN}))?'
            rf'{_QUAL}(?![A-Za-z])',
            text, re.IGNORECASE,
        ):
            a = m.group('a').upper()
            b = (m.group('b') or '').upper()
            q = (m.group('qual') or '').lower()
            sep = m.group(0)
            if b:
                # A hyphen/en-dash between numerals = a range; &/,/or/and =
                # two separate bands.
                if re.search(r'[-–]\s*' + re.escape(b) + r'\b', sep):
                    toks = _expand_part(f'{a}-{b}') or [a, b]
                else:
                    toks = [a, b]
            else:
                toks = [a]
            if q and len(toks) == 1:
                toks = [f'{toks[0]}-{q}']
            _emit(toks)

    result = {}
    if grades: result["evidence_grades"] = grades
    if levels: result["evidence_levels"] = levels
    if who_classes: result["who_functional_classes"] = who_classes
    return result


def _strip_cross_refs(text: str) -> Tuple[str, list]:
    """Remove cross_ref HTML comments; return (clean_text, list_of_ref_dicts)."""
    refs = []

    def collect(m):
        kind = m.group("target_kind") or ""
        if kind and kind not in _VALID_TARGET_KINDS:
            logger.warning("Unknown cross_ref target_kind=%r — kept as-is", kind)
        refs.append({
            k: v for k, v in {
                "target_file": m.group("target_file"),
                "target_heading": m.group("target_heading"),
                "target_kind": kind or None,
            }.items() if v
        })
        return ""

    clean = CROSS_REF_PATTERN.sub(collect, text)
    return clean, refs


def _strip_parent_only_blocks(text: str) -> Tuple[str, str]:
    """
    Return (child_text, parent_only_text).
    child_text has parent_only blocks removed.
    parent_only_text is the concatenated content of those blocks.
    """
    parent_only_parts = []

    def collect(m):
        parent_only_parts.append(m.group(1).strip())
        return ""

    child_text = PARENT_ONLY_BLOCK_PATTERN.sub(collect, text)
    parent_only_text = "\n\n".join(parent_only_parts)
    return child_text, parent_only_text


class MarkdownChunker:
    """
    Two-pass markdown chunker producing H1 parent + H2 child chunks.
    """

    def __init__(self, config: Optional[ChunkingConfig] = None):
        self.config = config or ChunkingConfig()
        self._h1_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=[("#", "doc_title")],
            strip_headers=False,
        )
        self._h2_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=[("##", "h2_title")],
            strip_headers=False,
        )
        self._h3_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=[("###", "h3_title")],
            strip_headers=False,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def chunk_document(
        self,
        content: str,
        title: str,
        source: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[DocumentChunk]:
        if not content.strip():
            return []

        base_meta = {
            "title": title,
            "source": source,
            "chunk_method": "markdown_header",
            **(metadata or {}),
        }

        # Strip overlap blocks (Grades/Levels/Abbreviations reference tables)
        stripped_content, overlap_blocks = self._strip_overlap_blocks(content)

        # Strip <!-- METADATA ... --> blocks — already parsed into document metadata
        # by _extract_document_metadata; keeping them in chunk text pollutes embeddings.
        stripped_content = METADATA_BLOCK_PATTERN.sub("", stripped_content)
        stripped_content = re.sub(r'\n{3,}', '\n\n', stripped_content).strip()

        # Pass 1 — split at H1
        h1_docs = self._h1_splitter.split_text(stripped_content)

        all_chunks: List[DocumentChunk] = []
        global_index = 0

        for h1_doc in h1_docs:
            h1_text = h1_doc.page_content

            # --- A-3: separate parent_only blocks from child-visible text ---
            h1_child_text, parent_only_text = _strip_parent_only_blocks(h1_text)
            # parent_only content is retained in H1 parent row but excluded from H2 children

            # Locate H1 position inside stripped_content
            h1_start = stripped_content.find(h1_text[:80] if len(h1_text) >= 80 else h1_text)
            if h1_start == -1:
                h1_start = 0
            h1_end = h1_start + len(h1_text)

            h1_meta = {
                **base_meta,
                **h1_doc.metadata,
                "context_path": h1_doc.metadata.get("doc_title", title),
            }

            # Emit H1 parent row (no embedding — stored for window context only)
            h1_chunk = DocumentChunk(
                content=h1_text.strip(),
                index=global_index,
                start_char=h1_start,
                end_char=h1_end,
                metadata={**h1_meta, "total_chunks": 0},  # updated after
                chunk_level="h1",
            )
            all_chunks.append(h1_chunk)
            h1_chunk_pos = len(all_chunks) - 1
            global_index += 1

            # Pass 2 — split H1 child text at ##
            h2_docs = self._h2_splitter.split_text(h1_child_text)

            # Fallback: no ## headings → whole section is h1_leaf (embedded, no parent)
            if len(h2_docs) <= 1 and not any("##" in d.page_content for d in h2_docs):
                leaf_text = h1_child_text.strip()
                if not leaf_text:
                    continue
                evidence = _extract_evidence_tags(leaf_text)
                clean_leaf, leaf_refs = _strip_cross_refs(leaf_text)
                leaf_meta = {**h1_meta, **evidence}
                if leaf_refs:
                    leaf_meta["cross_refs"] = leaf_refs
                # Promote the already-appended h1 to h1_leaf (no parent)
                all_chunks[h1_chunk_pos].chunk_level = "h1_leaf"
                all_chunks[h1_chunk_pos].content = clean_leaf
                all_chunks[h1_chunk_pos].metadata.update(leaf_meta)
                continue

            # H2 children exist — build child chunks
            child_chunks: List[DocumentChunk] = []
            child_pos = 0  # tracks position inside h1_child_text

            for h2_doc in h2_docs:
                # Skip preamble fragment — text before the first ## has no h2_title.
                # It is already stored verbatim in the H1 parent row; emitting it
                # again as a child would create a duplicate near-empty chunk.
                if not h2_doc.metadata.get("h2_title"):
                    continue

                h2_text = h2_doc.page_content

                # --- A-4: strip cross_ref markers from child embedding text ---
                h2_clean, cross_refs = _strip_cross_refs(h2_text)

                h2_start_in_parent = h1_child_text.find(
                    h2_text[:80] if len(h2_text) >= 80 else h2_text, child_pos
                )
                if h2_start_in_parent == -1:
                    h2_start_in_parent = child_pos
                h2_end_in_parent = h2_start_in_parent + len(h2_text)
                child_pos = h2_end_in_parent

                h2_meta = {
                    **h1_meta,
                    **h2_doc.metadata,
                    "context_path": " > ".join(filter(None, [
                        h1_doc.metadata.get("doc_title", ""),
                        h2_doc.metadata.get("h2_title", ""),
                    ])),
                    **_extract_evidence_tags(h2_clean),
                }
                if cross_refs:
                    h2_meta["cross_refs"] = cross_refs

                if len(h2_clean) <= _H2_MAX_CHARS:
                    child_chunks.append(DocumentChunk(
                        content=h2_clean.strip(),
                        index=global_index,
                        start_char=h2_start_in_parent,
                        end_char=h2_end_in_parent,
                        metadata={**h2_meta, "total_chunks": 0},
                        chunk_level="h2",
                    ))
                    global_index += 1
                else:
                    # Cap: H2 > 8 000 chars — store as unembedded intermediate,
                    # then sub-split at ### into embedded h3 children.
                    cap_h2_index = global_index
                    child_chunks.append(DocumentChunk(
                        content=h2_clean.strip(),
                        index=cap_h2_index,
                        start_char=h2_start_in_parent,
                        end_char=h2_end_in_parent,
                        metadata={**h2_meta, "total_chunks": 0, "cap_split": True},
                        chunk_level="h2",  # unembedded — ingest skips embedding for cap_split=True
                    ))
                    global_index += 1

                    h3_docs = self._h3_splitter.split_text(h2_clean)
                    h3_pos = 0
                    for h3_doc in h3_docs:
                        # Skip preamble before the first ### — splitter returns
                        # it without an h3_title tag, and it duplicates content
                        # already stored in the cap-split H2 parent row.
                        if not h3_doc.metadata.get("h3_title"):
                            continue
                        h3_text = h3_doc.page_content
                        # Splitter quirk: when ### immediately follows ## with no
                        # preamble, the first piece carries the parent ## heading
                        # line. Strip everything before the first ### so the h3
                        # row does not duplicate the cap-split H2's heading.
                        if h3_text.lstrip().startswith("##") and not h3_text.lstrip().startswith("###"):
                            idx = h3_text.find("###")
                            if idx >= 0:
                                h3_text = h3_text[idx:]
                        h3_text = h3_text.strip()
                        if not h3_text:
                            continue
                        h3_start = h2_start_in_parent + h2_clean.find(
                            h3_text[:80] if len(h3_text) >= 80 else h3_text, h3_pos
                        )
                        h3_end = h3_start + len(h3_text)
                        h3_pos = max(0, h3_end - h2_start_in_parent)
                        h3_clean, h3_refs = _strip_cross_refs(h3_text)
                        h3_meta = {**h2_meta, **h3_doc.metadata}
                        if h3_refs:
                            h3_meta["cross_refs"] = h3_meta.get("cross_refs", []) + h3_refs
                        h3_meta["cap_split_h2_index"] = cap_h2_index  # ingest resolves H2 UUID from this
                        child_chunks.append(DocumentChunk(
                            content=h3_clean.strip(),
                            index=global_index,
                            start_char=h3_start,
                            end_char=h3_end,
                            metadata={**h3_meta, "total_chunks": 0},
                            chunk_level="h3",
                        ))
                        global_index += 1

            all_chunks.extend(child_chunks)

        # Final re-index and total_chunks update
        total = len(all_chunks)
        for i, c in enumerate(all_chunks):
            c.index = i
            c.metadata["total_chunks"] = total

        if all_chunks:
            # Embedded = normal h2 + h3 + h1_leaf; excludes h1 and cap-split h2 intermediates
            embedded = [
                c for c in all_chunks
                if c.chunk_level not in ("h1",)
                and not (c.chunk_level == "h2" and c.metadata.get("cap_split"))
            ]
            sizes = [len(c.content) for c in embedded]
            if sizes:
                logger.info(
                    "Chunk stats for '%s': h1=%d, h2=%d, h3=%d, h1_leaf=%d, cap_split_h2=%d, "
                    "min=%d, max=%d, avg=%d",
                    title,
                    sum(1 for c in all_chunks if c.chunk_level == "h1"),
                    sum(1 for c in all_chunks if c.chunk_level == "h2" and not c.metadata.get("cap_split")),
                    sum(1 for c in all_chunks if c.chunk_level == "h3"),
                    sum(1 for c in all_chunks if c.chunk_level == "h1_leaf"),
                    sum(1 for c in all_chunks if c.chunk_level == "h2" and c.metadata.get("cap_split")),
                    min(sizes), max(sizes), sum(sizes) // len(sizes),
                )

        return all_chunks

    # ------------------------------------------------------------------
    # Static helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _strip_overlap_blocks(content: str) -> Tuple[str, list]:
        overlap_blocks = []

        def collect_and_remove(match):
            block_text = match.group(1) or match.group(2) or ""
            if block_text.strip():
                overlap_blocks.append(block_text.strip())
            return ""

        stripped = OVERLAP_BLOCK_PATTERN.sub(collect_and_remove, content)
        stripped = re.sub(r'\n{3,}', '\n\n', stripped)

        if overlap_blocks:
            logger.info("Stripped %d overlap block(s) before chunking", len(overlap_blocks))

        return stripped.strip(), overlap_blocks


# Convenience function
def create_chunker(config: Optional[ChunkingConfig] = None) -> MarkdownChunker:
    return MarkdownChunker(config)


if __name__ == "__main__":
    sample = """
# ED Treatment Algorithm

## Step 1: Assessment
- Medical history
- IIEF-5 questionnaire

## Step 2: Diagnosis

| Type | Description |
|------|-------------|
| Organic | Physical cause |
| Psychogenic | Psychological |

## Step 3: Treatment
### Mild ED
- Lifestyle changes
- PDE5 inhibitors
"""

    chunker = MarkdownChunker()
    chunks = chunker.chunk_document(sample, "ED Algorithm", "algorithm.md")

    for chunk in chunks:
        print(f"\n--- [{chunk.chunk_level}] {chunk.metadata.get('context_path', 'Root')} ---")
        print(f"{chunk.content[:120]}...")
