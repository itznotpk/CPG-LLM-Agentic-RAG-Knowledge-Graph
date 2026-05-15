"""
Audit and standardize CPG markdown files.

Rules enforced (see tasks/Next-Step/Markdown_Standardization_And_Cross_Reference_Guide.md):

  R1. NUMERIC headings (## ###, ####, #####) use a colon after the number.
        ## 3.1: General anaesthesia
        ### 3.1.1: Handling of inhalational agents
        #### 3.1.1.2: Volatile agents
      Letter prefixes (a., b.) and roman prefixes (i., ii.) are LEFT ALONE —
      only sentence case is applied to their title text.
  R2. Headings are sentence case. ALL-CAPS headings are converted; acronyms are preserved.
        # SECTION 3: SAFE USE...  ->  # Section 3: Safe use of...
        First word capitalized; first word after each colon capitalized.
  R3. Table/Figure lines are not headings. They are demoted to plain prose
      so they stay inside the parent H2/H3 chunk and embed cleanly.
        ### Table 1: ...  ->  Table 1: ...
      Exception: lines inside a parent_only_reference_start/end block keep their hash level.
  R4. cross_ref target_heading strings are auto-synced to the (possibly renamed)
      heading in the target file. Unresolvable references are reported.
  R5. Detect-only: report "refer to Section X" / "refer to Appendix Y" /
      "refer to Table Z" / "refer to Figure W" prose sentences that have NO
      adjacent cross_ref marker AND have no unambiguous auto-insert candidate.
  R6. Whitespace normalization:
        - strip trailing whitespace on every line
        - exactly 1 blank line BEFORE every heading
        - 0 blank lines AFTER a heading (heading welds to its content)
        - 0 blank lines between a colon-lead-in line and its bullet/numbered list
            "context...:"
                            <- this blank is removed
            "- item 1"
        - collapse runs of 3+ blank lines to 1 (preserves paragraph breaks)
  R7. Auto-insert cross_ref markers for UNAMBIGUOUS prose references.
      When "refer to Section X" / "refer to Appendix Y" has exactly one
      matching target in the heading index, the marker is inserted at
      end-of-line. Ambiguous matches fall through to R5 advisory output.
  R8. Detect-only: flag files containing more than one `# H1` heading.
      Cannot auto-fix — the demotion decision is editorial.

Usage:
  python audit_markdown.py                     # audit all of markdown/, dry-run
  python audit_markdown.py --fix               # apply fixes in place
  python audit_markdown.py <folder>            # narrow to one folder
  python audit_markdown.py <folder> --fix
  python audit_markdown.py --rules R1,R3       # only run specific rules
  python audit_markdown.py --no-cross-ref      # skip cross_ref sync (R4)
"""

import argparse
import io
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Enable Windows ANSI escape codes (Win10+). No-op elsewhere.
if os.name == 'nt':
    os.system('')

DEFAULT_ROOT = r"c:\Users\chinp\OneDrive\Documents\Agentic RAG\CPG LLM\markdown"

# ANSI color codes — toggled off when --no-color or output is not a TTY.
class _C:
    enabled = True

    @classmethod
    def wrap(cls, code: str, text: str) -> str:
        return f"\x1b[{code}m{text}\x1b[0m" if cls.enabled else text

    # Severity / status
    @classmethod
    def header(cls, t): return cls.wrap('1;36', t)      # bold cyan — section headers
    @classmethod
    def folder(cls, t): return cls.wrap('1;35', t)      # bold magenta — folder banner
    @classmethod
    def file(cls, t):   return cls.wrap('1;37', t)      # bold white — file name
    @classmethod
    def fixed(cls, t):  return cls.wrap('1;32', t)      # bold green — [FIXED]
    @classmethod
    def dry(cls, t):    return cls.wrap('1;33', t)      # bold yellow — [DRY-RUN]
    @classmethod
    def advisory(cls, t): return cls.wrap('1;34', t)    # bold blue — [ADVISORY]
    @classmethod
    def minus(cls, t):  return cls.wrap('31', t)        # red — before
    @classmethod
    def plus(cls, t):   return cls.wrap('32', t)        # green — after
    @classmethod
    def dim(cls, t):    return cls.wrap('2', t)         # dim — context / notes
    @classmethod
    def loc(cls, t):    return cls.wrap('36', t)        # cyan — line numbers

    # Per-rule tag colors
    RULE_COLORS = {
        'R1': '33',   # yellow
        'R2': '35',   # magenta
        'R3': '36',   # cyan
        'R4': '32',   # green
        'R5': '34',   # blue
        'R6': '93',   # bright yellow
        'R7': '92',   # bright green
        'R8': '91',   # bright red
    }

    @classmethod
    def rule(cls, tag: str) -> str:
        code = cls.RULE_COLORS.get(tag.strip(), '37')
        return cls.wrap(f'1;{code}', tag)

# Acronyms that must remain uppercase even inside a sentence-case heading.
ACRONYMS = {
    "AF", "CVD", "CV", "IV", "IM", "PO", "SC", "ECG", "EKG", "MRI", "CT",
    "NMBA", "IMR", "HKLAAC", "PCA", "RA", "TML", "CVC", "MH", "LAST",
    "POH", "POA", "MCT", "IE", "FRS", "LDL", "HDL", "CKD", "DM", "HF",
    "OT", "PCI", "NSTE-ACS", "STEMI", "UA-NSTEMI", "ICU", "ED", "ER",
    "PPE", "TIVA", "TCI", "DBT", "FFDM", "US", "MS", "PAH", "ACS",
    "BP", "HR", "ICD", "WHO", "MOH", "GP", "FBC", "RBC", "WBC", "Hb",
    "INR", "PT", "APTT", "BUN", "GFR", "eGFR", "BMI", "BNP", "LFT",
    "RRM", "RRSO", "RTM", "QT", "QTc", "GERD", "PEEP", "FiO2",
    "ICU", "PICU", "NICU", "DVT", "PE", "VTE", "MI", "CKD", "ARB",
    "ACEi", "CCB", "MRA", "SGLT2", "GLP-1", "DPP-4",
    "ST", "NSTE", "EHRA", "CHADS", "CHADS2", "VKA", "AFL",
}

# Title Case style — every word is capitalized (including 'of', 'in', 'and').
# Acronyms in ACRONYMS stay uppercase; intentional mixed-case (HbA1c, mRNA) is preserved.
LOWERCASE_WORDS: set[str] = set()

PARENT_ONLY_START = "parent_only_reference_start"
PARENT_ONLY_END = "parent_only_reference_end"

# Heading patterns -------------------------------------------------------------
HEADING_RE = re.compile(r'^(#{1,6})\s+(.*?)\s*$')

# X, X.Y, X.Y.Z, X.Y.Z.W ... possibly with a trailing dot, colon, or paren before whitespace
NUMERIC_PREFIX_RE = re.compile(
    r'^(?P<num>\d+(?:\.\d+)*)\s*(?P<sep>[:.\)]?)\s+(?P<title>.*)$'
)
# single letter prefix: "a. Title", "A) Title", "b: Title"
LETTER_PREFIX_RE = re.compile(
    r'^(?P<letter>[A-Za-z])\s*(?P<sep>[:.\)])\s+(?P<title>.*)$'
)
# roman numeral prefix: "i. Title", "iv) Title"  (only when heading is at H4/H5)
ROMAN_PREFIX_RE = re.compile(
    r'^(?P<roman>[ivxIVX]{1,5})\s*(?P<sep>[:.\)])\s+(?P<title>.*)$'
)
# Stage/Step/Phase/Appendix N: already-colon style — leave alone for prefix, but apply sentence case to title
KEYWORD_PREFIX_RE = re.compile(
    r'^(?P<kw>Stage|Step|Phase|Appendix|Section)\s+(?P<id>\w+)\s*(?P<sep>:?)\s*(?P<title>.*)$',
    re.IGNORECASE,
)

TABLE_FIGURE_RE = re.compile(r'^(Table|Figure)\b[^\n]*', re.IGNORECASE)
# Bold-wrapped Table/Figure label, e.g. "**Table 11: CHADS₂ Score**".
# Matches anywhere on a line — the wrapping `**` is stripped from the label
# itself; surrounding prose on the same line is left untouched.
BOLD_TABLE_FIGURE_RE = re.compile(
    r'\*\*\s*(?P<body>(?:Table|Figure)\b[^*\n]*?)\s*\*\*',
    re.IGNORECASE,
)

# cross_ref marker
CROSS_REF_RE = re.compile(
    r'<!--\s*cross_ref\s+(?P<attrs>.*?)\s*-->'
)
ATTR_RE = re.compile(r'(\w+)\s*=\s*"([^"]*)"')


# ------------------------------------------------------------------------------
# Sentence case
# ------------------------------------------------------------------------------

def is_acronym(token: str) -> bool:
    """A token like 'AF', 'CVD', 'NSTE-ACS', or 'HDL-C' counts as an acronym."""
    if not token:
        return False
    # Check the hyphen-preserving form first (catches 'NSTE-ACS' which is stored
    # with the hyphen in ACRONYMS).
    if token.upper() in ACRONYMS:
        return True
    bare = re.sub(r'[^A-Za-z0-9]', '', token)
    if bare and bare.upper() in ACRONYMS:
        return True
    # Hyphenated acronym where every part is a KNOWN acronym (e.g. 'HDL-C' if
    # both halves are listed). We can't trust `part.isupper()` alone — that
    # mis-flags ALL-CAPS prose like ACUTE-ONSET or LONG-TERM.
    if "-" in token:
        parts = [p for p in token.split("-") if p]
        if len(parts) >= 2 and all(p.upper() in ACRONYMS for p in parts):
            return True
    return False


def smart_case_word(token: str) -> str:
    """
    Recase a single token to Title Case (every word capitalized).
    Acronyms preserved. Mixed-case originals (e.g. 'mRNA', 'HbA1c') preserved.
    """
    if not token:
        return token

    # Preserve tokens that already mix case (likely intentional: HbA1c, mRNA).
    # Hyphenated tokens are exempt — they're handled by the hyphen-aware branch
    # below so 'Point-of-care' and 'POINT-of-care' normalize identically.
    has_upper = any(c.isupper() for c in token)
    has_lower = any(c.islower() for c in token)
    if has_upper and has_lower and "-" not in token:
        # Only override if the whole token is title-like ('Word') — leave intentional mixed-case alone
        if not (token[0].isupper() and token[1:].islower()):
            return token

    # Strip punctuation around the word for matching but reattach
    m = re.match(r'^(?P<lead>[^\w]*)(?P<core>[\w\-]+)(?P<trail>[^\w]*)$', token)
    if not m:
        return token
    lead, core, trail = m.group('lead'), m.group('core'), m.group('trail')

    if is_acronym(core):
        return f"{lead}{core.upper() if core.upper() in ACRONYMS else core}{trail}"

    # Title Case: capitalize every word. Acronyms (handled above) keep uppercase.
    # Hyphenated tokens: capitalize each segment (Acute-Onset, Long-Term), unless
    # the segment is itself a known acronym (then keep uppercase: Non-ST).
    if "-" in core:
        segments = []
        for seg in core.split("-"):
            if not seg:
                segments.append(seg)
            elif seg.upper() in ACRONYMS:
                segments.append(seg.upper())
            else:
                segments.append(seg.lower().capitalize())
        recased = "-".join(segments)
    else:
        recased = core.lower().capitalize()
    return f"{lead}{recased}{trail}"


def to_sentence_case(text: str) -> str:
    """
    Convert heading title text to Title Case (every word capitalized).
    Despite the legacy name, this is now Title Case per the project rule:
      - Every word capitalized, including 'of', 'in', 'and'.
      - Acronyms preserved (AF, CVD, INR, ...).
      - Mixed-case originals preserved (HbA1c, mRNA, CHA₂DS₂-VASc).
    """
    if not text:
        return text

    segments = re.split(r'(\s*:\s*)', text)
    out = []
    for seg in segments:
        if re.fullmatch(r'\s*:\s*', seg):
            out.append(seg)
            continue
        tokens = seg.split(' ')
        out.append(' '.join(smart_case_word(tok) if tok else tok for tok in tokens))
    return ''.join(out)


# ------------------------------------------------------------------------------
# Heading rewriting
# ------------------------------------------------------------------------------

def rewrite_heading(level: int, content: str, inside_parent_only: bool):
    """
    Returns (new_line_text, issues:list[str]).
    new_line_text starts with the hashes (or is the bold-prose replacement for tables).
    """
    issues = []
    hashes = '#' * level

    # R3. Table / Figure demotion (skip inside parent_only_reference blocks).
    # Render as plain text (no bold) — keeps embeddings clean while still
    # removing the heading hashes so the label stays inside its parent chunk.
    if TABLE_FIGURE_RE.match(content) and not inside_parent_only:
        issues.append("R3: Table/Figure used as heading")
        title = to_sentence_case(content)
        return title, issues

    # Try numeric prefix (## 3.1, ### 3.1.1, etc.)
    m = NUMERIC_PREFIX_RE.match(content)
    if m:
        num = m.group('num')
        sep = m.group('sep')
        title = m.group('title')
        if sep != ':':
            issues.append(f"R1: numeric heading '{num}' missing colon (was '{sep or 'space'}')")

        # R1 depth rule: numeric-part count must match the heading hash level.
        #   1 part (N)     -> H1   (but normally written as "Section N", not "N")
        #   2 parts (N.M)  -> H2
        #   3 parts (N.M.P)-> H3
        #   4+ parts       -> too deep; the guide says use letter sub-prefix instead.
        parts = num.split('.')
        expected_level = len(parts) + 1  # 1-part -> H2 if no "Section" keyword (rare); 2-part -> H2 ...
        # The convention is: bare numeric ## 6, ### 6.1, #### 6.1.1 maps to
        #   parts=1 -> H2 (e.g. '## 6: ...' is unusual but used)
        #   parts=2 -> H2 (e.g. '## 6.1: ...')
        #   parts=3 -> H3
        #   parts=4 -> H4 (deprecated; should be a letter under H3)
        # Per the guide rule: H1 = 'Section N' only, H2 = N.M, H3 = N.M.P,
        # H4 = N.M.P.Q, and so on (parts >= 6 are clamped to H6).
        if len(parts) == 1:
            expected_level = 2  # bare '## 6' allowed as H2 (advisory flags if it duplicates H1)
        else:
            expected_level = min(len(parts), 6)

        if level != expected_level:
            issues.append(
                f"R1: numeric depth '{num}' ({len(parts)} parts) should be H{expected_level}, "
                f"was H{level}"
            )
            hashes = '#' * expected_level

        title_cased = to_sentence_case(title)
        if title_cased != title:
            issues.append("R2: sentence case applied to title")
        return f"{hashes} {num}: {title_cased}", issues

    # Letter prefix (#### a. Title) — colon NOT inserted (preserve original separator).
    # Only apply sentence case to the title.
    if level >= 4:
        m = LETTER_PREFIX_RE.match(content)
        if m:
            letter = m.group('letter').lower()
            sep = m.group('sep')
            title = m.group('title')
            title_cased = to_sentence_case(title)
            if title_cased != title:
                issues.append("R2: sentence case applied to title")
            return f"{hashes} {letter}{sep} {title_cased}", issues

        m = ROMAN_PREFIX_RE.match(content)
        if m:
            roman = m.group('roman').lower()
            sep = m.group('sep')
            title = m.group('title')
            title_cased = to_sentence_case(title)
            if title_cased != title:
                issues.append("R2: sentence case applied to title")
            return f"{hashes} {roman}{sep} {title_cased}", issues

    # Stage/Step/Phase/Appendix/Section already-keyword style
    m = KEYWORD_PREFIX_RE.match(content)
    if m:
        kw_raw = m.group('kw')
        kw = kw_raw.capitalize()
        ident = m.group('id')
        sep = m.group('sep')
        title = m.group('title')
        if sep != ':':
            issues.append(f"R1: '{kw} {ident}' missing colon")
        if kw_raw != kw:
            issues.append("R2: keyword prefix recased")
        # Section number stays digits; Appendix can be letter/number
        title_cased = to_sentence_case(title) if title else ''
        if title and title_cased != title:
            issues.append("R2: sentence case applied to title")
        # If there is no title (e.g. just "Section 3:"), keep prefix only
        if title_cased:
            return f"{hashes} {kw} {ident}: {title_cased}", issues
        return f"{hashes} {kw} {ident}", issues

    # Plain prose heading (e.g. "### Abbreviations"): apply sentence case only
    cased = to_sentence_case(content)
    if cased != content:
        issues.append("R2: sentence case applied")
    return f"{hashes} {cased}", issues


# ------------------------------------------------------------------------------
# Cross-reference sync (R4)
# ------------------------------------------------------------------------------

def collect_headings(root: str):
    """
    Build {filename: {'h1': 'Heading text', 'h2': {anchor_key: 'Heading text', ...}}}
    Filename key uses basename for matching cross_ref target_file values.
    """
    index = {}
    for dirpath, _, files in os.walk(root):
        for f in files:
            if not f.endswith('.md'):
                continue
            path = os.path.join(dirpath, f)
            entry = {'path': path, 'h1': None, 'headings': []}
            with open(path, 'r', encoding='utf-8') as fh:
                for line in fh:
                    m = HEADING_RE.match(line)
                    if m:
                        lvl = len(m.group(1))
                        text = m.group(2).strip()
                        if lvl == 1 and entry['h1'] is None:
                            entry['h1'] = text
                        entry['headings'].append((lvl, text))
            index[f] = entry
    return index


def normalize_for_match(text: str) -> str:
    """Normalize a heading string for fuzzy comparison."""
    return re.sub(r'\s+', ' ', text.strip().lower())


def find_best_heading(entry, target_kind: str, original_target: str):
    """
    Given a target_kind and the (possibly stale) original target_heading,
    find the current heading text in `entry` that best matches.
    """
    if not entry or not entry.get('headings'):
        return None
    norm_orig = normalize_for_match(original_target)
    # Pull out the leading numeric or "Appendix N" prefix from original for stable matching
    prefix_match = re.match(r'^(?:section\s+\d+|appendix\s+\w+|\d+(?:\.\d+)*)', norm_orig)
    prefix = prefix_match.group(0) if prefix_match else None

    best = None
    best_score = -1
    for lvl, text in entry['headings']:
        norm = normalize_for_match(text)
        score = 0
        if prefix and norm.startswith(prefix):
            score += 10
        # token overlap
        orig_tokens = set(re.findall(r'\w+', norm_orig))
        cand_tokens = set(re.findall(r'\w+', norm))
        if orig_tokens:
            score += len(orig_tokens & cand_tokens) / len(orig_tokens)
        # prefer matching level for h1_section
        if target_kind == 'h1_section' and lvl == 1:
            score += 5
        if target_kind == 'h2_section' and lvl == 2:
            score += 3
        if target_kind == 'appendix' and re.match(r'(?i)appendix', text):
            score += 5
        if score > best_score:
            best_score = score
            best = text
    # Require either a strong prefix match or decent token overlap
    if best_score >= 5:
        return best
    return None


# Detect prose references that need a cross_ref marker.
# Triggers caught:
#   - "refer to / referring to / referred to Section X"
#   - "see Section X" / "See Section X"
#   - "as specified|described|shown|outlined in Section X"
#   - "(as) per Section X" / "per Table 11"
#   - parenthetical refs like "(Section 3)" or "(see Table 4)" without any trigger
# Target tokens: Section N(.M...), Appendix X, Table N[A], Table N & M, Figure N[A], Chapter N.
_TARGET_PATTERN = (
    r'Section\s+\d+(?:\.\d+)*'
    r'|Appendix\s+[A-Za-z0-9]+'
    r'|Table\s+\d+[A-Za-z]?(?:\s*&\s*\d+[A-Za-z]?)?'
    r'|Figure\s+\d+[A-Za-z]?'
    r'|Chapter\s+\d+'
)

REFER_TO_RE = re.compile(
    r'(?:'
    # Verb-style triggers
    r'\b(?:refer(?:ring|red)?\s+to|see|as\s+(?:specified|described|shown|outlined)\s+in|(?:as\s+)?per)\s+'
    # OR: parenthetical refs like "(Section 3)", "(see Table 4)", "(Figure 1)"
    r'|\(\s*(?:see\s+)?(?=(?:' + _TARGET_PATTERN + r')\s*\))'
    r')'
    r'(?P<target>' + _TARGET_PATTERN + r')'
    r'(?P<rest>[^.\n]{0,200})',
    re.IGNORECASE,
)


def suggest_cross_ref_marker(target_phrase: str, index: dict, current_file: str) -> tuple[str, str]:
    """
    Build a paste-ready <!-- cross_ref ... --> marker suggestion for a prose ref.
    Returns (marker_text, status) where status describes confidence:
      - "auto"      : single unambiguous match (R7 would have already inserted this)
      - "best-guess": multiple files matched; first/most-likely candidate filled in
      - "template"  : no match found; placeholders left for manual fill

    target_phrase examples: "Section 3", "Section 3.1.1", "Appendix 1", "Table 4", "Figure 7"
    """
    phrase = target_phrase.strip()
    low = phrase.lower()

    # 1) Try the unambiguous resolver first (handles Section/Appendix cleanly)
    resolved = find_unambiguous_target(phrase, index)
    if resolved:
        marker = (
            f'<!-- cross_ref '
            f'target_file="{resolved["target_file"]}" '
            f'target_heading="{resolved["target_heading"]}" '
            f'target_kind="{resolved["target_kind"]}" -->'
        )
        return marker, "auto"

    # 2) Table/Figure refs: locate the label in body text, then resolve UPWARD
    # to the enclosing # H1 / ## H2 — that is the retrievable chunk the marker
    # should point at (H3/H4 are never returned on their own). Search is scoped
    # to the current file's folder first, since CPG cross-refs almost always
    # stay within a single guideline folder.
    table_match = re.match(r'(?i)^(Table|Figure)\s+(\d+[A-Za-z]?)', phrase)
    if table_match:
        kind = table_match.group(1).capitalize()
        num = table_match.group(2)
        label_re = re.compile(rf'(?i)\b{kind}\s+{re.escape(num)}\b\s*[:\-–]?\s*([^\n|]{{0,160}})')
        current_basename = os.path.basename(current_file) if current_file else ''
        current_dir = ''
        if current_basename and current_basename in index:
            current_dir = os.path.dirname(index[current_basename]['path'])

        # (filename, enclosing_heading_text, enclosing_level, in_parent_only, label_for_note)
        candidates: list[tuple[str, str, int, bool, str]] = []
        for fname, entry in index.items():
            # Restrict to same folder as the referencing file
            if current_dir and os.path.dirname(entry['path']) != current_dir:
                continue
            try:
                with open(entry['path'], 'r', encoding='utf-8') as fh:
                    body = fh.read()
            except OSError:
                continue

            lines = body.splitlines()
            # Track headings + parent_only state while scanning so we can
            # snapshot the enclosing H1/H2 at the moment we hit the label.
            h1_text: str | None = None
            h2_text: str | None = None
            inside_parent_only = False
            found = False
            for line in lines:
                if PARENT_ONLY_START in line:
                    inside_parent_only = True
                    continue
                if PARENT_ONLY_END in line:
                    inside_parent_only = False
                    continue
                hm = HEADING_RE.match(line)
                if hm:
                    lvl = len(hm.group(1))
                    htext = hm.group(2).strip()
                    if lvl == 1:
                        h1_text = htext
                        h2_text = None
                    elif lvl == 2:
                        h2_text = htext
                    continue
                lm = label_re.search(line)
                if lm:
                    title = lm.group(1).strip().rstrip('.').rstrip('*').strip()
                    label_for_note = f"{kind} {num}: {title}" if title else f"{kind} {num}"
                    # Parent-only table: addressable only via the H1 parent.
                    if inside_parent_only and h1_text:
                        candidates.append((fname, h1_text, 1, True, label_for_note))
                    elif h2_text:
                        candidates.append((fname, h2_text, 2, False, label_for_note))
                    elif h1_text:
                        candidates.append((fname, h1_text, 1, False, label_for_note))
                    found = True
                    break
            if found:
                continue

        if candidates:
            # Prefer the current file if the table lives there.
            candidates.sort(key=lambda c: 0 if c[0] == current_basename else 1)
            fname, enclosing_heading, lvl, in_parent_only, _label = candidates[0]
            if in_parent_only:
                target_kind = 'h1_section'
            elif kind == 'Figure':
                target_kind = 'algorithm_flowchart'
            else:
                target_kind = 'h2_section' if lvl == 2 else 'h1_section'
            marker = (
                f'<!-- cross_ref '
                f'target_file="{fname}" '
                f'target_heading="{enclosing_heading}" '
                f'target_kind="{target_kind}" -->'
            )
            status = "auto" if len(candidates) == 1 else "best-guess"
            return marker, status

    # 3) Appendix template fallback
    if low.startswith('appendix'):
        return (
            f'<!-- cross_ref target_file="<filename.md>" '
            f'target_heading="{phrase}: <fill in>" target_kind="appendix" -->'
        ), "template"

    # 4) Section template fallback
    if low.startswith('section'):
        return (
            f'<!-- cross_ref target_file="<filename.md>" '
            f'target_heading="{phrase}: <fill in>" target_kind="h1_section" -->'
        ), "template"

    return (
        f'<!-- cross_ref target_file="<filename.md>" '
        f'target_heading="<fill in>" target_kind="<h1_section|h2_section|appendix|algorithm_flowchart>" -->'
    ), "template"


def collect_table_figure_h2_locations(text: str) -> dict[str, str]:
    """
    Walk the file and return {label_key: enclosing_h2_text} for every
    Table/Figure/Appendix/Section label found outside parent_only_reference
    blocks. Appendix/Section labels are also picked up directly from `##`
    headings (e.g. `## Appendix 11: ...`).
      label_key example: "Table 11", "Appendix 11"  (kind + number, no title)
    Used by R5 to suppress refs whose target lives in the same file —
    same-H1 refs do not need a cross_ref marker.
    """
    out: dict[str, str] = {}
    inside_parent_only = False
    h2_text: str | None = None
    body_label_re = re.compile(r'\b(Table|Figure)\s+(\d+[A-Za-z]?)\b', re.IGNORECASE)
    heading_label_re = re.compile(
        r'^(Appendix|Section|Table|Figure)\s+(\d+[A-Za-z]?)\b',
        re.IGNORECASE,
    )
    for line in text.splitlines():
        if PARENT_ONLY_START in line:
            inside_parent_only = True
            continue
        if PARENT_ONLY_END in line:
            inside_parent_only = False
            continue
        if inside_parent_only:
            continue
        hm = HEADING_RE.match(line)
        if hm:
            lvl = len(hm.group(1))
            heading_text = hm.group(2).strip()
            if lvl == 1:
                h2_text = None
            elif lvl == 2:
                h2_text = heading_text
                # Heading itself can BE the label target (e.g. ## Appendix 11: ...)
                hlm = heading_label_re.match(heading_text)
                if hlm:
                    key = f"{hlm.group(1).capitalize()} {hlm.group(2)}"
                    out.setdefault(key, h2_text)
            continue
        if h2_text is None:
            continue
        for m in body_label_re.finditer(line):
            key = f"{m.group(1).capitalize()} {m.group(2)}"
            out.setdefault(key, h2_text)
    return out


def build_line_to_h2_map(text: str) -> dict[int, str | None]:
    """Return {line_no (1-indexed): enclosing_h2_text or None} for the whole file."""
    mapping: dict[int, str | None] = {}
    h2_text: str | None = None
    for i, line in enumerate(text.splitlines()):
        hm = HEADING_RE.match(line)
        if hm:
            lvl = len(hm.group(1))
            if lvl == 1:
                h2_text = None
            elif lvl == 2:
                h2_text = hm.group(2).strip()
        mapping[i + 1] = h2_text
    return mapping


def collect_parent_only_targets(text: str) -> set[str]:
    """
    Return the set of labels (e.g. "Table 1", "Figure 7", "Appendix 11",
    "Section 3") that live inside any parent_only_reference block in this
    file. Refs to these targets do NOT need a cross_ref marker — per
    Section 4 of the guide, the content is already copied into the H1
    parent's context.
    """
    targets: set[str] = set()
    inside = False
    label_re = re.compile(
        r'\b(Table|Figure|Appendix|Section)\s+(\d+[A-Za-z]?)',
        re.IGNORECASE,
    )
    for line in text.splitlines():
        if PARENT_ONLY_START in line:
            inside = True
            continue
        if PARENT_ONLY_END in line:
            inside = False
            continue
        if not inside:
            continue
        for m in label_re.finditer(line):
            kind = m.group(1).capitalize()
            num = m.group(2)
            targets.add(f"{kind} {num}")
    return targets


def detect_missing_cross_refs(text: str, index: dict | None = None, current_file: str = '') -> list[dict]:
    """
    R5: Scan prose for 'refer to Section/Appendix/Table/Figure ...' that lacks
    a cross_ref marker. A marker counts as 'adjacent' if it appears anywhere
    on the same line OR on the following non-blank line.

    Skips refs whose target is already copied into the same file's
    parent_only_reference block (per Section 4 of the guide).

    When `index` is supplied, each finding also carries a paste-ready
    marker suggestion in `suggested_marker` along with a `confidence` tag
    ('auto', 'best-guess', or 'template').
    """
    findings = []
    lines = text.splitlines()
    inside_parent_only = False
    parent_only_targets = collect_parent_only_targets(text)
    label_h2_locations = collect_table_figure_h2_locations(text)

    for i, line in enumerate(lines):
        if PARENT_ONLY_START in line:
            inside_parent_only = True
            continue
        if PARENT_ONLY_END in line:
            inside_parent_only = False
            continue
        if inside_parent_only:
            continue

        # Skip the section-level "> **Context:**" blockquote summary at the top
        # of every section md file. It paraphrases what the section covers and
        # is not a real "refer to..." cross-reference.
        stripped = line.lstrip()
        if stripped.startswith('>') and re.search(r'\*\*Context:?\*\*', stripped, re.IGNORECASE):
            continue

        for m in REFER_TO_RE.finditer(line):
            target_phrase = m.group('target').strip()
            # Skip refs whose label (Table/Figure/Appendix/Section N) is already
            # copied into the file's parent_only block
            norm_target = re.sub(r'\s+', ' ', target_phrase)
            label_m = re.match(
                r'(?i)^(Table|Figure|Appendix|Section)\s+(\d+[A-Za-z]?)',
                norm_target,
            )
            if label_m:
                key = f"{label_m.group(1).capitalize()} {label_m.group(2)}"
                if key in parent_only_targets:
                    continue
                # Skip if the target label lives anywhere in the SAME file
                # (same H1). Per the parent-child spec, within-file refs do
                # not need a cross_ref marker — the chain walk delivers the
                # whole H1 parent (with all its H2 children) to synthesis.
                if key in label_h2_locations:
                    continue

            if CROSS_REF_RE.search(line):
                continue
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            next_line = lines[j] if j < len(lines) else ''
            if CROSS_REF_RE.search(next_line):
                continue
            finding = {
                'line': i + 1,
                'rules': ['R5'],
                'note': f"missing cross_ref marker for '{target_phrase}'",
                'context': line.strip()[:120],
            }
            if index is not None:
                marker, confidence = suggest_cross_ref_marker(target_phrase, index, current_file)
                finding['suggested_marker'] = marker
                finding['confidence'] = confidence
            findings.append(finding)
    return findings


REQUIRED_CROSS_REF_ATTRS = ('target_file', 'target_heading', 'target_kind')


def rewrite_cross_refs(text: str, index: dict, findings: list) -> str:
    """
    R4 — validate AND auto-sync target_heading on every cross_ref marker.

    Reports:
      - Missing required attribute (target_file / target_heading / target_kind).
      - target_file points to a file not in the index.
      - target_heading matches no heading in the target file (stale or wrong)
        when the matcher's confidence is too low to auto-replace.
      - Auto-fix performed (before -> after diff).
    """
    # Pre-compute line numbers for each marker so findings carry an L<n>.
    marker_lines = {}
    for i, line in enumerate(text.splitlines()):
        for m in CROSS_REF_RE.finditer(line):
            marker_lines[m.group(0)] = i + 1

    def replace(match):
        raw = match.group(0)
        line_no = marker_lines.get(raw)
        attrs_text = match.group('attrs')
        attrs = dict(ATTR_RE.findall(attrs_text))
        target_file = attrs.get('target_file', '')
        target_heading = attrs.get('target_heading', '')
        target_kind = attrs.get('target_kind', '')

        # Missing required attributes
        missing = [a for a in REQUIRED_CROSS_REF_ATTRS if not attrs.get(a)]
        if missing:
            findings.append({
                'line': line_no,
                'rules': ['R4'],
                'note': f"cross_ref missing required attribute(s): {', '.join(missing)}",
                'context': raw[:140],
            })
            return raw

        # target_file not in index
        entry = index.get(target_file)
        if entry is None:
            findings.append({
                'line': line_no,
                'rules': ['R4'],
                'note': f"target_file not found in index: '{target_file}'",
                'context': raw[:140],
            })
            return raw

        # Determine the best candidate heading in the target file
        if target_kind == 'h1_section' and entry['h1']:
            new_heading = entry['h1']
            confident = True
        else:
            best = find_best_heading(entry, target_kind, target_heading)
            new_heading = best or target_heading
            confident = best is not None

        # Stale / wrong: target_heading not present in target file and matcher had no confident replacement
        heading_texts = {h[1] for h in entry['headings']}
        if target_heading not in heading_texts and not confident:
            findings.append({
                'line': line_no,
                'rules': ['R4'],
                'note': (
                    f"target_heading does not match any heading in '{target_file}' "
                    f"and no confident replacement found — review manually"
                ),
                'context': f'target_heading="{target_heading}" target_kind="{target_kind}"',
            })
            return raw

        # target_kind sanity check: does the resolved heading's actual level match?
        # h1_section -> level 1, h2_section -> level 2, appendix -> any level whose
        # text starts with "Appendix", algorithm_flowchart -> not level-checked.
        matched_level = next((lvl for lvl, t in entry['headings'] if t == new_heading), None)
        if matched_level is not None:
            kind_ok = True
            if target_kind == 'h1_section' and matched_level != 1:
                kind_ok = False
            elif target_kind == 'h2_section' and matched_level != 2:
                kind_ok = False
            if not kind_ok:
                findings.append({
                    'line': line_no,
                    'rules': ['R4'],
                    'note': (
                        f"target_kind='{target_kind}' does not match the resolved heading "
                        f"level (H{matched_level}) in '{target_file}' — review manually"
                    ),
                    'context': f'target_heading="{new_heading}"',
                })

        # Auto-fix when matcher found a confident new heading
        if new_heading and new_heading != target_heading:
            findings.append({
                'line': line_no,
                'rules': ['R4'],
                'before': f'target_heading="{target_heading}"',
                'after': f'target_heading="{new_heading}"',
                'note': f"target_file={target_file}",
            })
            attrs['target_heading'] = new_heading

        new_attrs = ' '.join(f'{k}="{v}"' for k, v in attrs.items())
        return f'<!-- cross_ref {new_attrs} -->'

    return CROSS_REF_RE.sub(replace, text)


# ------------------------------------------------------------------------------
# R6: Whitespace normalization
# ------------------------------------------------------------------------------

def normalize_whitespace(text: str, findings: list) -> str:
    """
    R6 — applied as a single pass at the end:
      - strip trailing whitespace on every line
      - exactly 1 blank line BEFORE every heading
      - 0 blank lines AFTER a heading (heading welds to its content)
      - collapse runs of 3+ blank lines to 1
    Records a single summary finding per file when anything changes.
    """
    lines = text.splitlines()
    issues_count = 0

    # Pass 1: trailing whitespace
    stripped = [ln.rstrip() for ln in lines]
    trailing_count = sum(1 for a, b in zip(lines, stripped) if a != b)
    if trailing_count:
        issues_count += trailing_count

    LIST_ITEM_RE = re.compile(r'^\s*(?:[-*+]\s|\d+[.)]\s)')

    out: list[str] = []
    blank_after_heading_removed = 0
    blank_before_heading_inserted = 0
    blank_runs_collapsed = 0
    blank_after_colon_removed = 0

    i = 0
    while i < len(stripped):
        line = stripped[i]
        is_heading = bool(HEADING_RE.match(line))

        if is_heading:
            # Ensure exactly one blank line before this heading (skip at file start).
            if out:
                blanks = 0
                while out and out[-1] == '':
                    out.pop()
                    blanks += 1
                if blanks != 1:
                    blank_before_heading_inserted += 1
                out.append('')
            out.append(line)
            # Skip blank lines immediately AFTER the heading
            j = i + 1
            skipped = 0
            while j < len(stripped) and stripped[j] == '':
                j += 1
                skipped += 1
            if skipped:
                blank_after_heading_removed += 1
            i = j
            continue

        if line == '':
            j = i
            while j < len(stripped) and stripped[j] == '':
                j += 1
            run = j - i
            # Special case: "lead-in:" + blank(s) + "- bullet" -> drop the blanks
            prev_nonblank = out[-1] if out else ''
            next_line = stripped[j] if j < len(stripped) else ''
            if (prev_nonblank.rstrip().endswith(':')
                    and LIST_ITEM_RE.match(next_line)
                    and not is_heading):
                blank_after_colon_removed += 1
                i = j
                continue
            if run >= 3:
                blank_runs_collapsed += 1
                out.append('')
            else:
                out.extend([''] * run)
            i = j
            continue

        out.append(line)
        i += 1

    # Trim trailing blank lines at end of file to a single newline
    while out and out[-1] == '':
        out.pop()
    new_text = '\n'.join(out) + '\n' if out else ''

    if new_text != text:
        notes = []
        if trailing_count:
            notes.append(f"{trailing_count} line(s) with trailing whitespace")
        if blank_before_heading_inserted:
            notes.append(f"{blank_before_heading_inserted} heading(s) missing/extra blank line before")
        if blank_after_heading_removed:
            notes.append(f"{blank_after_heading_removed} heading(s) with blank line after")
        if blank_runs_collapsed:
            notes.append(f"{blank_runs_collapsed} run(s) of 3+ blank lines collapsed")
        if blank_after_colon_removed:
            notes.append(f"{blank_after_colon_removed} blank line(s) between colon lead-in and list removed")
        findings.append({
            'line': None,
            'rules': ['R6'],
            'note': '; '.join(notes) if notes else 'whitespace normalized',
        })

    return new_text


# ------------------------------------------------------------------------------
# R7: Auto-insert cross_ref markers for unambiguous prose references
# ------------------------------------------------------------------------------

def find_unambiguous_target(target_phrase: str, index: dict) -> dict | None:
    """
    Try to resolve "Section 3", "Appendix 1", etc. to a single (target_file,
    target_heading, target_kind). Returns None if zero or multiple candidates match.

    Strategy:
      - "Section N(.M...)" -> find files whose H1 starts with "Section N" (case-insensitive).
        If level deeper (3.1, 3.1.1) -> hunt for an h2/h3 inside those files.
      - "Appendix X" -> find any heading text starting with "Appendix X" in any file.
      - "Table N" / "Figure N" -> too ambiguous across files; return None (R5 will report).
    """
    phrase = target_phrase.strip()
    low = phrase.lower()

    # Table/Figure prose refs are not auto-inserted — too many cross-file collisions.
    if low.startswith(('table', 'figure', 'chapter')):
        return None

    if low.startswith('section'):
        m = re.match(r'section\s+(\d+(?:\.\d+)*)', low)
        if not m:
            return None
        num = m.group(1)
        parts = num.split('.')
        top = parts[0]
        # Files whose H1 begins with "Section <top>"
        candidates = []
        for fname, entry in index.items():
            if not entry.get('h1'):
                continue
            h1_low = entry['h1'].lower()
            if re.match(rf'^\s*section\s+{re.escape(top)}\b', h1_low):
                candidates.append((fname, entry))
        if len(candidates) != 1:
            return None
        fname, entry = candidates[0]

        if len(parts) == 1:
            return {
                'target_file': fname,
                'target_heading': entry['h1'],
                'target_kind': 'h1_section',
            }

        # Resolve UPWARD to the enclosing H2 — H3/H4 are not retrievable units.
        # "Section 3.1" -> the H2 starting with "3.1".
        # "Section 3.1.2" or "3.1.2.1" -> still the same H2 ("3.1: ...").
        h2_prefix = '.'.join(parts[:2])  # always X.Y
        h2_re = re.compile(rf'^\s*{re.escape(h2_prefix)}\s*[:.\s]')
        h2_candidates = [
            text for (lvl, text) in entry['headings']
            if lvl == 2 and h2_re.match(text.lower())
        ]
        if len(h2_candidates) == 1:
            return {
                'target_file': fname,
                'target_heading': h2_candidates[0],
                'target_kind': 'h2_section',
            }
        return None

    if low.startswith('appendix'):
        m = re.match(r'appendix\s+([A-Za-z0-9]+)', phrase, re.IGNORECASE)
        if not m:
            return None
        ident = m.group(1)
        # Find any heading "Appendix <ident>" across all files
        candidates = []
        for fname, entry in index.items():
            for lvl, text in entry['headings']:
                if re.match(rf'^\s*appendix\s+{re.escape(ident)}\b', text, re.IGNORECASE):
                    candidates.append((fname, text))
        # Unique-by-file: if all hits live in one file, pick the first one
        unique_files = {c[0] for c in candidates}
        if len(unique_files) != 1:
            return None
        fname = next(iter(unique_files))
        # Among candidates in that file, prefer the highest-level (closest to H2)
        candidates.sort(key=lambda c: 0)  # they're already in document order
        _, heading_text = candidates[0]
        return {
            'target_file': fname,
            'target_heading': heading_text,
            'target_kind': 'appendix',
        }

    return None


def auto_insert_cross_refs(text: str, index: dict, findings: list) -> str:
    """
    R7 — Scan prose for "refer to Section X" / "refer to Appendix Y" without
    an adjacent cross_ref marker. If the target resolves UNAMBIGUOUSLY in the
    index, append the marker at end of the line. Ambiguous refs are skipped
    (R5 will report them).
    """
    lines = text.splitlines()
    inside_parent_only = False
    inserted = 0

    for i, line in enumerate(lines):
        if PARENT_ONLY_START in line:
            inside_parent_only = True
            continue
        if PARENT_ONLY_END in line:
            inside_parent_only = False
            continue
        if inside_parent_only:
            continue

        # Skip lines that already have a marker
        if CROSS_REF_RE.search(line):
            continue
        # Skip if next non-blank line has a marker
        j = i + 1
        while j < len(lines) and not lines[j].strip():
            j += 1
        if j < len(lines) and CROSS_REF_RE.search(lines[j]):
            continue

        # Collect all "refer to X" matches on this line
        matches = list(REFER_TO_RE.finditer(line))
        if not matches:
            continue

        markers_to_add = []
        for m in matches:
            target_phrase = m.group('target')
            resolved = find_unambiguous_target(target_phrase, index)
            if resolved is None:
                continue
            marker = (
                f'<!-- cross_ref '
                f'target_file="{resolved["target_file"]}" '
                f'target_heading="{resolved["target_heading"]}" '
                f'target_kind="{resolved["target_kind"]}" -->'
            )
            markers_to_add.append((target_phrase, marker, resolved))

        if markers_to_add:
            # Append all markers at end of line, separated by spaces
            lines[i] = line.rstrip() + ' ' + ' '.join(m[1] for m in markers_to_add)
            for target_phrase, _, resolved in markers_to_add:
                findings.append({
                    'line': i + 1,
                    'rules': ['R7'],
                    'before': line.rstrip()[:120],
                    'after': f"<!-- cross_ref ... target_file=\"{resolved['target_file']}\" -->",
                    'note': f"auto-inserted marker for '{target_phrase}' -> {resolved['target_file']}",
                })
                inserted += 1

    return '\n'.join(lines) + ('\n' if text.endswith('\n') else '')


# ------------------------------------------------------------------------------
# R8: Duplicate H1 detection
# ------------------------------------------------------------------------------

def detect_h2_duplicates_h1_number(text: str, findings: list) -> None:
    """
    R1 (advisory part): when a file has '# Section N: Title' as H1 AND a bare
    '## N: Title' as H2 (same top-level number, no dotted sub-number), the H2
    is a duplicate of the H1 and should be removed or merged. Flagged for manual
    review — auto-deletion would silently change chunk boundaries.
    """
    h1_section_re = re.compile(r'^#\s+Section\s+(\d+)\b', re.IGNORECASE)
    # Bare ## N (not ## N.M) — digits NOT followed by another `.digit` part.
    h2_bare_re = re.compile(r'^##\s+(\d+)(?!\.\d)\s*[:\s]', re.IGNORECASE)
    h1_num = None
    for line in text.splitlines():
        m = h1_section_re.match(line)
        if m:
            h1_num = m.group(1)
            break
    if h1_num is None:
        return
    for i, line in enumerate(text.splitlines()):
        m = h2_bare_re.match(line)
        if m and m.group(1) == h1_num:
            findings.append({
                'line': i + 1,
                'rules': ['R1'],
                'note': (
                    f"H2 '## {h1_num}: ...' duplicates the H1 'Section {h1_num}' — "
                    f"remove or merge manually (auto-fix would shift chunk boundaries)"
                ),
                'context': line.strip()[:120],
            })


def detect_duplicate_h1(text: str, findings: list) -> None:
    """R8 — flag files with more than one `# H1` heading."""
    h1_lines = [
        (i + 1, line.strip())
        for i, line in enumerate(text.splitlines())
        if re.match(r'^#\s+\S', line)
    ]
    if len(h1_lines) > 1:
        for line_no, text_ in h1_lines[1:]:
            findings.append({
                'line': line_no,
                'rules': ['R8'],
                'note': f"duplicate H1 — file should have exactly one '# ...' heading",
                'context': text_[:120],
            })


# ------------------------------------------------------------------------------
# Main audit
# ------------------------------------------------------------------------------

def audit_file(path: str, rules: set, fix: bool, index: dict | None):
    """
    Returns (findings, changed) where findings is a list of dicts:
      {'line': int, 'rules': [...], 'before': str, 'after': str}  (heading fix)
      {'line': int, 'rules': ['R5'], 'note': str}                 (R5 detect-only)
      {'line': None, 'rules': ['R4'], 'note': str}                (R4 cross_ref sync)
    """
    with open(path, 'r', encoding='utf-8') as f:
        text = f.read()

    lines = text.splitlines(keepends=False)
    new_lines = []
    findings: list[dict] = []
    inside_parent_only = False

    for i, line in enumerate(lines):
        if PARENT_ONLY_START in line:
            inside_parent_only = True
            new_lines.append(line)
            continue
        if PARENT_ONLY_END in line:
            inside_parent_only = False
            new_lines.append(line)
            continue

        m = HEADING_RE.match(line)
        if not m:
            # R3 (non-heading variant): strip `**...**` wrapping from Table/Figure
            # labels so they embed as plain prose. Surrounding text on the line
            # is untouched. Skipped inside parent_only_reference blocks.
            if 'R3' in rules and not inside_parent_only and BOLD_TABLE_FIGURE_RE.search(line):
                new_line = BOLD_TABLE_FIGURE_RE.sub(lambda m: m.group('body').strip(), line)
                if new_line != line:
                    findings.append({
                        'line': i + 1,
                        'rules': ['R3'],
                        'before': line.rstrip(),
                        'after': new_line.rstrip(),
                    })
                    new_lines.append(new_line)
                    continue
            new_lines.append(line)
            continue

        level = len(m.group(1))
        content = m.group(2).strip()
        if not content:
            new_lines.append(line)
            continue

        new_line, line_issues = rewrite_heading(level, content, inside_parent_only)
        kept = [msg for msg in line_issues if any(r in msg for r in rules)]
        if kept:
            rule_tags = sorted({msg.split(':', 1)[0] for msg in kept})
            if new_line.rstrip() == line.rstrip():
                # Advisory: rule flagged the line but cannot auto-fix (e.g. 4-part
                # numeric heading — needs manual conversion to letter prefix).
                findings.append({
                    'line': i + 1,
                    'rules': rule_tags,
                    'note': '; '.join(kept),
                    'context': line.strip()[:120],
                })
                new_lines.append(line)
            else:
                findings.append({
                    'line': i + 1,
                    'rules': rule_tags,
                    'before': line.rstrip(),
                    'after': new_line,
                })
                new_lines.append(new_line)
        else:
            new_lines.append(line)

    new_text = '\n'.join(new_lines)
    if text.endswith('\n'):
        new_text += '\n'

    # R4: cross_ref sync (whole-file regex pass)
    if 'R4' in rules and index is not None:
        new_text = rewrite_cross_refs(new_text, index, findings)

    # R7: auto-insert unambiguous cross_ref markers (BEFORE R5 so R5 only
    # reports truly ambiguous refs that need manual review).
    if 'R7' in rules and index is not None:
        new_text = auto_insert_cross_refs(new_text, index, findings)

    # R5: detect missing cross_ref markers (report-only, never modifies text)
    if 'R5' in rules:
        findings.extend(detect_missing_cross_refs(new_text, index, os.path.basename(path)))

    # R8: duplicate H1 detection (report-only)
    if 'R8' in rules:
        detect_duplicate_h1(new_text, findings)

    # R1 advisory: H2 that duplicates the H1's section number (report-only).
    if 'R1' in rules:
        detect_h2_duplicates_h1_number(new_text, findings)

    # R6: whitespace normalization (must run LAST so heading/cross_ref edits
    # don't fight the blank-line rules).
    if 'R6' in rules:
        new_text = normalize_whitespace(new_text, findings)

    changed = new_text != text
    if fix and changed:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_text)

    return findings, changed


def main():
    parser = argparse.ArgumentParser(
        description="Audit and standardize CPG markdown files (heading colon, sentence case, table demotion, cross_ref sync)."
    )
    parser.add_argument("directory", nargs="?", default=DEFAULT_ROOT,
                        help=f"Folder to audit (default: {DEFAULT_ROOT})")
    parser.add_argument("--fix", action="store_true", help="Apply fixes in place")
    parser.add_argument("--rules", default="R1,R2,R3,R4,R5,R7,R8",
                        help="Comma-separated rules to apply. Default: R1,R2,R3,R4,R5,R7,R8")
    parser.add_argument("--no-cross-ref", action="store_true",
                        help="Skip R4 (cross_ref target_heading sync)")
    parser.add_argument("--no-color", action="store_true",
                        help="Disable ANSI colors in output")
    args = parser.parse_args()

    # Auto-disable color if stdout is being piped/redirected, unless user forces it off explicitly.
    if args.no_color or not sys.stdout.isatty():
        _C.enabled = False

    if not os.path.exists(args.directory):
        print(f"Error: Directory {args.directory} does not exist.")
        sys.exit(1)

    # Normalize to absolute paths so commonpath works regardless of how the
    # user invoked the script (relative or absolute argument). normpath/normcase
    # also fixes Windows drive-letter casing mismatches (C: vs c:).
    args.directory = os.path.normpath(os.path.abspath(args.directory))
    default_root_abs = os.path.normpath(os.path.abspath(DEFAULT_ROOT))

    rules = {r.strip().upper() for r in args.rules.split(',') if r.strip()}
    if args.no_cross_ref:
        rules.discard('R4')

    print(f"Auditing: {args.directory}")
    print(f"Fix mode: {'ON' if args.fix else 'OFF (dry-run)'}")
    print(f"Rules:    {sorted(rules)}\n")

    # Build heading index (for R4). Use the markdown root, not just the narrowed
    # folder, so cross_refs that point across folders still resolve.
    index = None
    if rules & {'R4', 'R5', 'R7'}:
        try:
            common = os.path.normcase(os.path.commonpath([args.directory, default_root_abs]))
            if common == os.path.normcase(default_root_abs):
                index_root = default_root_abs
            else:
                index_root = args.directory
        except ValueError:
            # Different drives — fall back to scanning just the target directory.
            index_root = args.directory
        print(f"Indexing headings under {index_root} for cross_ref sync...")
        index = collect_headings(index_root)
        print(f"Indexed {len(index)} markdown files.\n")

    total_files = 0
    total_findings = 0
    total_fixed = 0
    rule_counts: dict[str, int] = {}
    by_folder: dict[str, list[tuple[str, list[dict], bool]]] = {}

    # Allow `<file.md>` as well as `<folder>` — walk if directory, single-file if file.
    if os.path.isfile(args.directory):
        walk_iter = [(os.path.dirname(args.directory), [], [os.path.basename(args.directory)])]
        # Re-root output paths relative to the file's parent folder.
        display_root = os.path.dirname(args.directory)
    else:
        walk_iter = os.walk(args.directory)
        display_root = args.directory

    for dirpath, _, files in walk_iter:
        for f in sorted(files):
            if not f.endswith('.md'):
                continue
            total_files += 1
            full = os.path.join(dirpath, f)
            findings, changed = audit_file(full, rules, args.fix, index)
            if findings:
                folder = os.path.relpath(dirpath, display_root) or '.'
                by_folder.setdefault(folder, []).append((f, findings, changed))
                total_findings += len(findings)
                for fnd in findings:
                    for r in fnd['rules']:
                        rule_counts[r] = rule_counts.get(r, 0) + 1
                if args.fix and changed:
                    total_fixed += 1

    # Output
    action_verb = "Fixed" if args.fix else "Would fix"
    sep = '═' * 72
    for folder, entries in sorted(by_folder.items()):
        print(f"\n{_C.header(sep)}")
        print(_C.folder(f"FOLDER: {folder}"))
        print(_C.header(sep))
        for fname, findings, changed in entries:
            # Per-file status: did any finding actually modify the file?
            # R6 (whitespace) modifies but uses a summary note instead of before/after.
            # R7 (auto-insert) modifies. R5/R8 are advisory-only.
            fixable_rules = {'R1', 'R2', 'R3', 'R4', 'R6', 'R7'}
            fixable_count = sum(
                1 for f in findings
                if ('before' in f and 'after' in f) or any(r in fixable_rules for r in f['rules'])
            )
            advisory_count = len(findings) - fixable_count
            if args.fix and changed:
                status = _C.fixed("[FIXED]   ")
            elif fixable_count > 0:
                status = _C.dry("[DRY-RUN] ")
            else:
                status = _C.advisory("[ADVISORY]")
            count_str = f"{len(findings)} finding{'s' if len(findings) != 1 else ''}"
            print(f"\n  {status} {_C.file(fname)}  {_C.dim('(' + count_str + ')')}")

            for fnd in findings:
                rule_tag = ','.join(fnd['rules'])
                rule_str = _C.rule(f"{rule_tag:<4}")
                loc = _C.loc(f"L{fnd['line']}") if fnd.get('line') else _C.dim("  - ")
                if 'before' in fnd and 'after' in fnd:
                    verb = _C.fixed(action_verb) if args.fix else _C.dry(action_verb)
                    print(f"    [{rule_str}] {loc}  {verb}:")
                    print(f"             {_C.minus('-  ' + fnd['before'])}")
                    print(f"             {_C.plus('+  ' + fnd['after'])}")
                    if fnd.get('note'):
                        print(f"             {_C.dim('(' + fnd['note'] + ')')}")
                else:
                    note = fnd.get('note', '')
                    ctx = fnd.get('context', '')
                    print(f"    [{rule_str}] {loc}  {note}")
                    if ctx:
                        print(f"             {_C.dim('> ' + ctx)}")
                    if fnd.get('suggested_marker'):
                        conf = fnd.get('confidence', 'template')
                        conf_color = {
                            'auto': _C.fixed,        # green
                            'best-guess': _C.dry,    # yellow
                            'template': _C.advisory, # blue
                        }.get(conf, _C.dim)
                        print(f"             {conf_color('paste [' + conf + ']:')} {fnd['suggested_marker']}")

    print(f"\n{_C.header(sep)}")
    print(_C.header("SUMMARY"))
    print(_C.header(sep))
    print(f"  Directory:      {args.directory}")
    print(f"  Files checked:  {total_files}")
    print(f"  Findings:       {total_findings}")
    for r in sorted(rule_counts):
        n = rule_counts[r]
        # R5 and R8 are advisory; R1-R4, R6, R7 are fixable
        label = " (advisory)" if r in ('R5', 'R8') else ""
        print(f"     {_C.rule(r)}: {n}{_C.dim(label)}")
    if args.fix:
        print(f"  Files modified: {_C.fixed(str(total_fixed)) if total_fixed else total_fixed}")
        if total_findings > 0 and total_fixed == 0:
            print(_C.dim("\n  (all findings are advisory — R5 never auto-fixes; add cross_ref markers manually)"))
    else:
        print(_C.dim("\n  (dry-run — re-run with --fix to apply changes)"))


if __name__ == "__main__":
    main()
