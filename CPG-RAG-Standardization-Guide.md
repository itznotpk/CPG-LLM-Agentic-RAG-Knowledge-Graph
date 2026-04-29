# CPG Markdown Standardization & RAG Chunking Guide

> **Purpose:** A step-by-step SOP for standardizing CPG (Clinical Practice Guideline) markdown files for high-fidelity RAG retrieval. This document covers the golden-baseline markdown format, the parent-child chunking architecture, and the code changes made to support evidence-grade metadata extraction.

---

## Table of Contents

1. [Overview](#1-overview)
2. [SOP: Post-Docling Markdown Standardization](#2-sop-post-docling-markdown-standardization)
3. [Golden Baseline Format](#3-golden-baseline-format)
4. [RAG Chunking Architecture](#4-rag-chunking-architecture)
5. [Code Changes Summary](#5-code-changes-summary)
6. [How It Helps the LLM](#6-how-it-helps-the-llm)

---

## 1. Overview

After Docling converts a CPG PDF to raw markdown, the output requires **manual standardization** before it can be ingested into the vector database. This guide documents the exact format established using the **CVD-Prevention-Women(2016)** suite (`section-0-summary.md` through `section-8-appendices.md`) as the golden reference.

### Key Principles
- **Self-contained sections:** Each `.md` file must be a standalone RAG unit — it should contain all reference tables (Grades, Levels, Abbreviations) needed to interpret its content without needing to look up another file.
- **Semantic pointers:** Cross-references to other sections/tables use a standardized `(refer ...)` format so the LLM can resolve them consistently.
- **Evidence tagging:** Every clinical recommendation is tagged with `[Grade X, Level Y]` inline so the chunker can extract it as structured metadata.

---

## 2. SOP: Post-Docling Markdown Standardization

> [!TIP]
> **Start with the LAST section file first** (e.g. `section-8-appendices.md`). This file contains all Appendices, reference tables, Grades of Recommendation, Levels of Evidence, and the master Abbreviations list. By verifying and aligning the Appendix file first, you establish the authoritative source material that all other sections will overlap from. Working backwards prevents cascading errors.

### Step-by-Step Workflow

```
Step 1: Verify & Align Appendices (section-8)
    │
Step 2: Standardize File Names
    │
Step 3: Align Header Hierarchy
    │
Step 4: Standardize "refer" Pointers
    │
Step 5: Apply Overlap Blocks (Tables, Grades, Abbreviations)
    │
Step 6: Verify [Grade, Level] Tags
    │
Step 7: Final Scan & Validation
```

---

### Step 1: Verify & Align Appendices First

Open the appendix file (e.g. `section-8-appendices.md`) and verify:
- All Appendix tables match the source PDF verbatim

This is your **single source of truth** for overlap content.

---

### Step 2: Standardize File Names

Each file must be named to match its H1 title. Format: `section-{N}-{slug}.md`

| H1 Title | File Name |
|---|---|
| `# SECTION 0: SUMMARY AND KEY GENERAL RECOMMENDATIONS` | `section-0-summary.md` |
| `# SECTION 1: SCOPE OF THE PROBLEM` | `section-1-scope-of-problem.md` |
| `# SECTION 2: TYPES OF CVD IN WOMEN` | `section-2-types-of-cvd.md` |
| `# SECTION 3: OTHER DISEASES...` | `section-3-other-diseases.md` |
| `# SECTION 4: CARDIOVASCULAR RISK FACTORS` | `section-4-cardiovascular-risk-factors.md` |
| `# SECTION 5: TOTAL CARDIOVASCULAR RISK ASSESSMENT` | `section-5-cvd-risk-assessment.md` |
| `# SECTION 6: RECOMMENDATIONS FOR PREVENTION...` | `section-6-recommendations.md` |
| `# SECTION 7: ADHERENCE, COMPLIANCE AND QUALITY ASSURANCE` | `section-7-adherence-compliance.md` |
| `# SECTION 8: APPENDICES` | `section-8-appendices.md` |

---

### Step 3: Align Header Hierarchy

Every section file must follow a consistent header structure:

```markdown
# SECTION X: TITLE                    ← H1 (one per file, used as parent chunk)
## X.1 Sub-Topic                      ← H2 (mid-level chunk)
### X.1.1 Specific Topic              ← H3 (child chunk — this is where Grade/Level lives)
#### X.1.1.1 Detail                   ← H4 (stays inside the H3 chunk, not split further)
```

> [!IMPORTANT]
> The chunker splits at `#`, `##`, and `###`. Everything under a `###` header (including `####` and `#####` sub-headers) stays together as one chunk. This keeps clinical topics cohesive.

---

### Step 4: Standardize "refer" Pointers

All cross-references must use this exact format:

```
(refer [Reference Name]: [Full Title])
```

**Examples:**
```markdown
✅ CORRECT:
(refer Table 1: Classification of CVD Risk in Women)
(refer Appendix 6: Audit of Clinical Diabetes)
(refer Section 5: Total Cardiovascular Risk Assessment)

❌ WRONG:
(refer to page 78)
(see Table 1)
(refer to Table 1)
```

**Why this format?**
- The LLM can parse the pointer name and title consistently
- It acts as a semantic link — the LLM knows *what* is being referenced and *where* to find it
- No page numbers (pages don't exist in chunked vector databases)

---

### Step 5: Apply Overlap Blocks

Overlap blocks embed reference material directly into each section file so it is **self-contained for RAG retrieval**. There are three types of overlap:

#### 5A. Grades of Recommendation & Levels of Evidence

**When to include:** In ANY section that contains `[Grade X, Level Y]` tags.

**Placement:** At the END of the section file, BEFORE the Abbreviations block.

**Format:**
```markdown
<!-- ============================================================ -->
<!-- OVERLAP CONTENT FROM: GRADES OF RECOMMENDATION & EVIDENCE    -->
<!-- Purpose: Defines clinical evidence codes used in this CPG    -->
<!-- ============================================================ -->

### Grades of Recommendation

| Grade | Definition |
|---|---|
| **I** | Conditions for which there is evidence and/or general agreement that a given procedure/therapy is beneficial, useful and/or effective. |
| **II** | Conditions for which there is conflicting evidence and/or a divergence of opinion about the usefulness/efficacy of a given procedure/therapy. |
| **II-a** | Weight of evidence/opinion is in favour of usefulness/efficacy. |
| **II-b** | Usefulness/efficacy is less well established by evidence/opinion. |
| **III** | Conditions for which there is evidence and/or general agreement that the procedure/therapy is not useful/effective and in some cases may be harmful. |

### Levels of Evidence

| Level | Definition |
|---|---|
| **A** | Data derived from multiple randomized clinical trials or meta-analyses. |
| **B** | Data derived from a single randomized clinical trial or large non-randomized studies. |
| **C** | Only consensus of opinions of experts, case studies or standard of care. |

<!-- END OVERLAP FROM: GRADES OF RECOMMENDATION & EVIDENCE -->
```

#### 5B. Appendix / Table Overlaps

**When to include:** When a section references a table or appendix from `section-8-appendices.md` using a `(refer ...)` pointer.

**Placement:** Directly after the paragraph that references it, OR at a logical break in the section where the table data is most relevant.

**Format:**
```markdown
<!-- ============================================================ -->
<!-- OVERLAP CONTENT FROM: APPENDIX 4C                            -->
<!-- Purpose: Choice of Anti-Hypertensive Drugs reference table   -->
<!-- ============================================================ -->

[Full table content copied verbatim from section-8-appendices.md]

<!-- END OVERLAP FROM: APPENDIX 4C -->
```

> [!NOTE]
> Do NOT add a separate title like "Overlapped Reference Tables". The overlap block integrates naturally — the `###` header inside the overlap IS the title.

#### 5C. Abbreviations

**When to include:** In EVERY section file.

**Placement:** At the very END of the file (last block before EOF).

**Format:**
```markdown
<!-- ============================================================ -->
<!-- OVERLAP CONTENT FROM: ABBREVIATIONS                          -->
<!-- Purpose: Localized list of clinical abbreviations used in Section X -->
<!-- ============================================================ -->

### Abbreviations

| Abbreviation | Full Term |
|---|---|
| BMI | Body mass index |
| BP | Blood pressure |
| CVD | Cardiovascular disease |
| ... | ... |

<!-- END OVERLAP FROM: ABBREVIATIONS -->
```

> [!IMPORTANT]
> The abbreviation list must be **section-specific**. Scan the entire section file and include ONLY the abbreviations that appear in that section. Do not blindly copy the full master list from section-8.

---

### Step 6: Verify [Grade, Level] Tags

Every clinical recommendation must be tagged inline with the evidence grade:

```markdown
✅ CORRECT:
**[Grade I, Level A]** The target BP in most patients < 80 years should be < 140/90 mmHg.

- **[Grade I, Level C]** Women at risk who do not achieve their target levels should be considered for pharmacological intervention.

❌ WRONG:
The target BP should be < 140/90 mmHg. (Grade I, Level A)
[I, A] The target BP should be...
```

**Rules:**
- Tags are wrapped in `**bold**` for visual clarity
- Format is always `[Grade X, Level Y]` — capital G, capital L
- Tags appear at the START of the recommendation sentence or bullet point
- Valid Grades: `I`, `II-a`, `II-b`, `III`
- Valid Levels: `A`, `B`, `C`

---

### Step 7: Final Scan & Validation

Run through the completed file and check:
- [ ] File name matches H1 title
- [ ] Only ONE `# H1` header per file
- [ ] All `(refer ...)` pointers follow the standardized format
- [ ] All `[Grade, Level]` tags are properly formatted
- [ ] Grades/Levels overlap tables are present (if file contains Grade tags)
- [ ] Abbreviations block is at the end of file
- [ ] All abbreviations used in the section are listed
- [ ] No orphaned page references (e.g. "page 78") remain
- [ ] Tables are properly aligned with `|---|---|` syntax

---

## 3. Golden Baseline Format

The complete file structure of a standardized section looks like this:

```markdown
# SECTION X: TITLE

<!-- METADATA
category: clinical_guidelines
use_case: ...
patient_input: 
output: 
-->

> **Context:** Brief description of what this section covers.

---

## X.1 Sub-Topic

### X.1.1 Specific Clinical Topic

**[Grade I, Level A]** Clinical recommendation text here.

(refer Table Y: Full Table Title)

[Overlapped table content if applicable]

---

## X.2 Another Sub-Topic

### X.2.1 ...

---

<!-- OVERLAP: Grades of Recommendation & Levels of Evidence -->
[Tables here]

---

<!-- OVERLAP: Abbreviations -->
[Table here]
```

---

## 4. RAG Chunking Architecture

### 4.1 Previous Approach (H1-Only)

Previously, the chunker split documents only at `# H1` headers. This meant:
- Each entire section file = 1 giant chunk
- A file with 30+ `[Grade, Level]` tags had NO way to assign specific grades to metadata
- Entity extraction was noisy (mixed medications from different sub-topics)
- Retrieval returned massive irrelevant blocks of text

### 4.2 New Approach: Parent-Child Chunks (H1 → H2 → H3)

The updated chunker splits at three levels:

```
# SECTION 6: RECOMMENDATIONS           → PARENT chunk (chunk_type: "parent")
  ## 6.1 General Recommendations        → MID chunk    (chunk_type: "mid")
    ### 6.1.1 Nutrition                  → CHILD chunk  (chunk_type: "child")
    ### 6.1.2 Physical Activity          → CHILD chunk  (chunk_type: "child")
    ### 6.1.5 Aspirin                    → CHILD chunk  (chunk_type: "child")
  ## 6.2 High Risk Patients             → MID chunk    (chunk_type: "mid")
    ### 6.2.1 Dyslipidaemia             → CHILD chunk  (chunk_type: "child")
    ### 6.2.2 Hypertension              → CHILD chunk  (chunk_type: "child")
```

Each **child chunk** now gets its own isolated metadata:

```json
{
  "chunk_type": "child",
  "parent_header": "6.2 High Risk Patients",
  "context_path": "SECTION 6: RECOMMENDATIONS > 6.2 High Risk > 6.2.1 Dyslipidaemia",
  "evidence_grades": ["I"],
  "evidence_levels": ["A", "C"],
  "subsection": "6.2.1 Dyslipidaemia"
}
```

### 4.3 Why H3 is the Right Chunk Size

| Split Level | Typical Chunk Size | Problem |
|---|---|---|
| `#` H1 only | 2,000 - 8,000 words | Way too large, metadata is meaningless |
| `##` H2 only | 500 - 2,000 words | Still mixes sub-topics |
| `###` H3 ✅ | 150 - 500 words | Perfect: one clinical topic per chunk |
| `####` H4 | 20 - 100 words | Too small, loses surrounding context |

The `###` level groups a complete clinical topic (e.g. "Dyslipidaemia") with all its sub-details (`#### Targets of Therapy`, `#### Primary Prevention`, `#### Secondary Prevention`) into one focused, coherent chunk.

### 4.4 Retrieval Flow

```
User Query: "What is the evidence for aspirin in women?"
    │
    ├── 1. Vector search matches CHILD chunk "6.1.5 Aspirin"
    │       metadata: { evidence_grades: ["III", "I"], evidence_levels: ["A"] }
    │
    ├── 2. System also fetches PARENT chunk "Section 6" for broader context
    │
    └── 3. LLM generates answer with:
          - Specific recommendation from child chunk
          - Evidence strength from metadata (Grade III = NOT recommended)
          - Grades/Levels overlap table defines what "Grade III" means
          - Full section context from parent chunk
```

### 4.5 Handling Overlap Content (Deduplication)

**Problem:** If every section file has overlapped Grades + Levels + Abbreviations tables, and we chunk at `###`, those overlap tables become standalone chunks — **near-duplicates across 8+ files**. The vector search would return 3 copies of the "Grades" table instead of the actual clinical answer.

**Solution:** The chunker **strips overlap blocks before chunking**, then **re-attaches them as context to the last real chunk.**

```
BEFORE (what happens in the file):
┌─────────────────────────────────────────────────┐
│ section-6-recommendations.md                     │
│                                                  │
│   ### 6.1.1 Nutrition        → chunk (clinical)  │
│   ### 6.2.1 Dyslipidaemia    → chunk (clinical)  │
│   ### 6.2.2 Hypertension     → chunk (clinical)  │
│   <!-- OVERLAP FROM: GRADES OF RECOMMENDATION --> │
│   ### Grades of Recommendation → STRIPPED ❌       │
│   ### Levels of Evidence       → STRIPPED ❌       │
│   <!-- END OVERLAP -->                           │
│   <!-- OVERLAP FROM: ABBREVIATIONS -->           │
│   ### Abbreviations            → STRIPPED ❌       │
│   <!-- END OVERLAP -->                           │
└─────────────────────────────────────────────────┘

AFTER (what ends up in the database):
  Chunk 1: "6.1.1 Nutrition"        ← searchable
  Chunk 2: "6.2.1 Dyslipidaemia"    ← searchable
  Chunk 3: "6.2.2 Hypertension"     ← searchable, PLUS Grades/Levels/
                                       Abbreviations attached as reference
                                       context (NOT a separate chunk)
```

**How it works in the code:**
1. The `_strip_overlap_blocks()` method detects the `<!-- OVERLAP CONTENT FROM: ... -->` / `<!-- END OVERLAP FROM: ... -->` comment markers
2. It removes those blocks from the markdown BEFORE the splitter runs
3. After chunking, the stripped content is **appended to the last real chunk** with a `<!-- REFERENCE CONTEXT -->` marker
4. The last chunk's metadata gets `"has_overlap_context": true`

> [!IMPORTANT]
> **This is why the overlap comment markers are critical.** Without the standardized `<!-- OVERLAP CONTENT FROM: ... -->` / `<!-- END OVERLAP FROM: ... -->` wrapping, the chunker cannot distinguish overlap content from real clinical content. Always use the exact comment format from Step 5 of the SOP.

---

## 5. Code Changes Summary

### 5.1 File Changed: `ingestion/chunker.py`

#### Change 1: Header Split Levels

```diff
- # Only split on H1 (#) - keeps all subsections together
- self.headers_to_split_on = [
-     ("#", "doc_title"),
- ]

+ # Split on H1, H2, H3 to isolate clinical topics and recommendations
+ self.headers_to_split_on = [
+     ("#", "doc_title"),
+     ("##", "section"),
+     ("###", "subsection")
+ ]
```

**Effect:** Documents are now split into smaller, topic-specific chunks at three levels of header hierarchy instead of one.

#### Change 2: Evidence Grade & Level Extraction

Added regex extraction that scans each chunk's content for `[Grade X, Level Y]` tags and stores them as structured metadata arrays:

```python
# Extract Evidence Grade and Level tags
grades = []
levels = []
for match in re.finditer(
    r'\[Grade\s+(I{1,3}[-]?[a-c]?),\s*Level\s+([A-D])\]',
    chunk_content, re.IGNORECASE
):
    grade_val = match.group(1).upper()
    level_val = match.group(2).upper()
    if grade_val not in grades:
        grades.append(grade_val)
    if level_val not in levels:
        levels.append(level_val)
```

**Effect:** Each chunk's metadata now contains `evidence_grades: ["I", "II-A"]` and `evidence_levels: ["A", "B"]` arrays, enabling filtered retrieval by evidence strength.

#### Change 3: Parent-Child Relationship Tracking

Added logic to determine each chunk's position in the hierarchy and record its parent:

```python
# Calculate parent relationship from headers
parent_id = None
chunk_type = "parent"
if "subsection" in doc.metadata:
    chunk_type = "child"
    parent_id = doc.metadata.get("section") or doc.metadata.get("doc_title")
elif "section" in doc.metadata:
    chunk_type = "mid"
    parent_id = doc.metadata.get("doc_title")
```

**Effect:** Every chunk now has `chunk_type` (`parent`, `mid`, or `child`) and `parent_header` in its metadata, enabling hierarchical retrieval strategies.

#### Change 4: Overlap Block Stripping (Deduplication)

Added a pre-processing step that detects and removes overlap blocks before the splitter runs, then re-attaches them to the last chunk as non-searchable context:

```python
# Pre-processing: strip overlap blocks
stripped_content, overlap_blocks = self._strip_overlap_blocks(content)
docs = self.splitter.split_text(stripped_content)  # chunk overlap-free content

# Post-processing: re-attach to last chunk
if final_chunks and overlap_blocks:
    combined_overlap = "\n\n---\n\n".join(overlap_blocks)
    last_chunk = final_chunks[-1]
    last_chunk.content += f"\n\n---\n<!-- REFERENCE CONTEXT -->\n\n{combined_overlap}"
    last_chunk.metadata["has_overlap_context"] = True
```

**Effect:** Grades, Levels, and Abbreviation overlap tables are no longer duplicated as standalone searchable chunks across files. They remain available as embedded context in the last chunk of each document.

### 5.2 Database Compatibility

> [!NOTE]
> **No SQL changes were needed.** The existing `chunks` table already has:
> - `metadata` column (JSONB) — accepts any key-value pairs dynamically
> - `parent_chunk_id` column (UUID) — pre-built for parent-child relationships
> - `section_hierarchy` column (ARRAY) — pre-built for header path tracking
>
> The new metadata fields (`evidence_grades`, `evidence_levels`, `chunk_type`, `parent_header`, `has_overlap_context`) are stored inside the JSONB `metadata` column automatically.

---

## 6. How It Helps the LLM

### Before (H1 Chunking)

```
Query: "What grade of evidence supports statin therapy in high-risk women?"

Retrieved: Entire Section 6 (22KB, 4000+ words)
Metadata:  { "title": "SECTION 6: RECOMMENDATIONS" }  ← no grade info

LLM must: Read 4000 words to find the answer buried in paragraph 47
Result:   Slow, noisy, potentially hallucinated
```

### After (H3 Parent-Child Chunking)

```
Query: "What grade of evidence supports statin therapy in high-risk women?"

Retrieved: Child chunk "6.2.1 Dyslipidaemia" (300 words)
Metadata:  {
             "evidence_grades": ["I"],
             "evidence_levels": ["A", "C"],
             "chunk_type": "child",
             "parent_header": "6.2 High Risk Patients"
           }

LLM sees:  A focused, relevant chunk with pre-extracted evidence tags
Result:    Fast, precise, auditable
```

### The Confidence-Weighted Retrieval Pattern

The metadata enables a powerful retrieval strategy:

1. **Filter by evidence strength:** Only retrieve chunks where `evidence_grades` contains `"I"` (highest evidence)
2. **Prioritize child chunks:** Search `chunk_type = "child"` first for specific answers
3. **Expand to parent:** If the child chunk lacks context, fetch the parent via `parent_header`
4. **Audit trail:** The LLM can cite exactly which Grade and Level backs its answer

This transforms the RAG system from a "search and hope" approach into a **clinically auditable, evidence-aware retrieval engine**.

