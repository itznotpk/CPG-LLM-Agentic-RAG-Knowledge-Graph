# Markdown Standardization and Cross-Reference Guide

Use this guide when aligning CPG markdown for Phase A Step 2 parent-child re-ingest. It covers heading structure, file naming, cross-reference markers, and parent-only reference blocks.

Recent applied examples:

- `markdown/Anaesthesia-Medication-Safety/` has been renamed into standard section files such as `section-0-appendix-AM.md`, `section-3-safe-use-of-medication-anaesthesia.md`, and `section-5-safe-medication-practice-anaethesia.md`.
- Anaesthesia Medication Safety sections now use `# H1` parent sections, `## H2` retrievable children, and `### H3` / `#### H4` nested details.
- Anaesthesia Section 2 uses `parent_only_reference_start/end` for shared tables such as TML examples and CVC medication examples.
- `markdown/Atrial-Fibrillation(2012)/section-3-initial-management.md` has been aligned toward the same parent-child hierarchy.

---

## Section 1: Heading structure

Use exactly one `# H1` as the parent section for each markdown file.

Use `## H2` for retrievable clinical child chunks.

Use `### H3` for numbered subsections inside an H2, such as `3.1.1:`, `3.1.2:`, and `3.1.3:`.

Use `### H3` for tables that belong directly under the current H2 (but see Section 6 — Table/Figure lines should generally be demoted to bold prose, not kept as headings).

Use `#### H4` and lower headings when a subsection or table falls under an H3.

Do not keep duplicate `# H1` headings inside the same file. If the source document repeats the section title after a front matter or overview block, convert the repeated title to plain text, remove it, or demote it to `##` only if it should become a retrievable child chunk.

### Simple rule

```text
Main clinical section that should be retrieved:
  use ## H2

Details that belong inside that section:
  use ### H3 or lower

Numbered subtopics like 3.1.1:
  use ### H3 under ## 3.1

Tables directly under an H2:
  use ### H3

Tables or details under an H3 group:
  use #### H4 or lower

Shared table/form/reference copied for parent context only:
  put inside parent_only_reference_start/end
  use ### H3 or lower inside the block
```

### Numbering rule

Hash level must match the numeric depth — this is what the audit script enforces (R1):

```text
# Section N: Title                       H1   "Section N" prefix only, no dotted number
## N.M: Title                            H2   exactly 2 parts (e.g. 6.1, 3.2)
### N.M.P: Title                         H3   exactly 3 parts (e.g. 6.3.1)
#### N.M.P.Q: Title                      H4   exactly 4 parts (e.g. 8.2.2.3)
#### a: Title / #### b:                  H4   letter prefix also valid at H4
```

Avoid:

```text
## 6: Title           — bare "## 6" duplicates the H1 'Section 6'; remove or merge
### 6.1: Title        — should be ## 6.1 (2-part number = H2)
#### 6.3.1: Title     — should be ### 6.3.1 (3-part number = H3)
### 8.2.2.3: Title    — should be #### 8.2.2.3 (4-part number = H4)
```

Example:

```text
# Section 3: Estimation of global cardiovascular risk    H1 parent
## 3.1: Primary prevention                               H2 child
### 3.1.1: Information required                          H3 inside 3.1
### 3.1.2: Risk stratification                           H3 inside 3.1
Table 7: Prevalence...                                   plain prose inside 3.1 (not a heading)
Table 1A: Points for men                                 plain prose (not a heading)
```

### H2 child boundary rule

```text
An H2 child starts at a ## heading.
It includes paragraphs, lists, tables, and H3/H4 headings under that H2.
It ends before the next ## heading or next # heading.
```

Do not use `##` for decorative labels or minor subtopics. Use `###` instead when the content should remain inside the current H2 child.

---

## Section 2: File naming rule

Use standard section filenames so ingestion can sort and audit sections predictably:

```text
section-0-appendix.md
section-1-introduction.md
section-2-key-principles.md
section-3-safe-use-of-medication.md
section-5-safe-medication-practice.md
```

Rules:

```text
Use lowercase filenames.
Use section number first.
Use hyphen-separated descriptive slugs.
Rename vague files like section-3.md when the section title is known.
Keep appendix files as section-0-appendix.md when they support the whole CPG.
```

---

## Section 3: Applied examples from current repo

### Anaesthesia Medication Safety — section 2

```md
# Section 2: Key principles of safe use of medication in anaesthesia

## 2.1: Aims of safe medication administration

## 2.2: Responsibilities of anaesthesia healthcare professionals

## 2.9: Medication administration

### 2.9.1: Introduction

### 2.9.2: Safe practice

<!-- parent_only_reference_start -->
### Shared reference: Tall man lettering examples
...
<!-- parent_only_reference_end -->
```

Behavior:

```text
Section 2 file:
  one H1 parent

2.1, 2.2, 2.9:
  H2 child chunks retrievable by vector search

2.9.1 and 2.9.2:
  H3 content inside H2 child 2.9

Shared tables:
  stored in H1 parent context only
  not emitted as independent H2 children
```

### Anaesthesia Medication Safety — section 3

```md
# Section 3: Safe use of medication in specific areas

## 3.1: General anaesthesia

### 3.1.1: Handling of inhalational agents/volatile agents

### 3.1.2: Medical gases

#### a: Storage of medical gas cylinders

#### b: Handling medical gas cylinders

## 3.2: Regional anaesthesia

### 3.2.1: Safe administration of drugs in regional anaesthesia (RA)
```

Behavior:

```text
H2 child 3.1 includes:
  3.1.1
  3.1.2
  H4 lettered details a, b, c, etc.

H2 child 3.1 ends before:
  ## 3.2 Regional Anaesthesia
```

### Atrial Fibrillation — section 3

```md
# Section 3: Initial management

## 3.1: Clinical history, physical examination and investigations

### 3.1.1: Detection

#### 3.1.1.1: Electrocardiogram
```

Behavior:

```text
H1 parent:
  full initial management section

H2 child 3.1:
  includes 3.1.1 and 3.1.1.1
  ends before the next H2 or next H1
```

### General example — Infective Endocarditis section 3

```md
# Section 3: Diagnosis of infective endocarditis

## 3.1: Blood cultures
Blood cultures should be taken before antibiotics...

### 3.1.1: Timing
Collect samples before antimicrobial therapy where possible.

### 3.1.2: Number of sets
At least three sets may be required depending on clinical context.

Table 1: Blood culture collection summary
| Topic | Detail |
|---|---|
| Timing | Before antibiotics |
| Sets | Multiple sets if clinically indicated |

## 3.2: Echocardiography
Echo is recommended when IE is suspected...

### 3.2.1: Transthoracic echocardiography
Use as the initial imaging test when appropriate.

### 3.2.2: Transoesophageal echocardiography
Use when suspicion remains high or image quality is inadequate.

Table 2A: Echocardiography indications
| Indication | Imaging approach |
|---|---|
| Suspected IE | Initial echo |
| Persistent suspicion | Further imaging |
```

Behavior:

```text
H1 parent:
  full Section 3 content

H2 child 3.1:
  includes 3.1 Blood Cultures
  includes all H3/H4 content under 3.1, including 3.1.1 and tables
  ends before 3.2 Echocardiography

H2 child 3.2:
  includes 3.2 Echocardiography
  includes all H3/H4 content under 3.2, including nested H4 tables
  ends before next H2 or next H1
```

### General example — CVD risk section 3

```md
# Section 3: Estimation of global cardiovascular risk

## 3.1: Primary prevention

Table 7: Prevalence of CV risk factors among adults >=18 years of age in Malaysia
| Age Group | Hypercholesterolaemia (%) | Hypertension (%) |
|---|---|---|
| 18-19 | ... | ... |

### 3.1.1: Information required for CV risk assessment

Text for the required information...

### 3.1.2: CV risk stratification using the FRS general CVD risk score

Text for risk stratification...

Table 1 & 2: Framingham risk score for assessment of CVD risk

Table 1A: Estimation of 10-year CVD points for men
| Points | Age, yr | HDL-C |
|---|---|---|
| 0 | 30-34 | 1.2-<1.3 |

Table 1B: CVD risk for men
| Total Points | 10-year Risk % |
|---|---|
| 0 | 1.6 |

## 3.2: Secondary prevention

Text for secondary prevention...
```

Behavior:

```text
H2 child 3.1 includes:
  Table 7
  3.1.1
  3.1.2
  Table 1 & 2
  Table 1A / 1B / 2A / 2B as H4 under Table 1 & 2

H2 child 3.1 ends before:
  ## 3.2 Secondary Prevention
```

---

## Section 4: Parent-only reference block

Use this when shared tables, criteria lists, forms, or appendix excerpts should be visible in the H1 parent context but should not become their own retrievable H2 child.

Use this for shared or overlap material already copied into the current H1 parent, such as Anaesthesia Section 2 shared TML examples or CVC medication examples. Do not also add a `cross_ref` marker for the same copied content.

```md
# Section 3: Diagnosis of Infective Endocarditis

## 3.1 Blood Cultures
Blood cultures should be taken before antibiotics...

## 3.2 Echocardiography
Echo is recommended when IE is suspected...

<!-- parent_only_reference_start -->
### Modified Duke Criteria Table

| Major criteria | Minor criteria |
|---|---|
| Positive blood cultures | Fever |
| Endocardial involvement | Predisposing heart condition |
<!-- parent_only_reference_end -->
```

Behavior:

```text
Stored in H1 parent context: yes
Embedded as retrievable H2 child: no
Visible to Stage 5 synthesis when H1 parent is loaded: yes
Retrieved directly by vector search: no
Fetched separately by cross_ref: no
```

### Heading rule inside parent-only blocks

Inside a parent-only reference block, prefer `###` or lower headings.

Good:

```md
<!-- parent_only_reference_start -->
### Modified Duke Criteria Table
...
<!-- parent_only_reference_end -->
```

Avoid:

```md
<!-- parent_only_reference_start -->
## Modified Duke Criteria Table
...
<!-- parent_only_reference_end -->
```

Reason:

```text
The chunker splits retrievable children at ## headings.
Using ## inside parent_only_reference can accidentally create a child chunk
unless the parser masks parent-only blocks before H2 splitting.
```

---

## Section 5: Cross-reference marker

Use a `cross_ref` marker only when the referenced content lives outside the current H1 parent section.

Do not add a `cross_ref` marker if the referenced table, form, appendix excerpt, or reference material is already copied into the current H1 using a parent-only reference block.

### When to use

```text
Referenced content already pasted inside current H1 parent_only_reference block:
  no cross_ref marker needed

Referenced content lives outside current H1:
  add cross_ref marker
```

### Marker syntax

Use this when the sentence says "refer to Section..." and the target is outside the current H1 parent.

```md
For estimation of global CVD risk, refer to Section 3: Estimation of Global CVD Risk.
<!-- cross_ref target_file="section-3-estimation-of-global-cvd-risk.md" target_heading="Section 3: Estimation of Global CVD Risk" target_kind="h1_section" -->
```

Real examples from the repo:

```md
'General' measures are steps and processes, from purchasing, storage and supply should be adopted for all drugs including those used in regional anaesthesia, as specified in Section 2: Key Principles of Safe Use of Medication in Anaesthesia.
<!-- cross_ref target_file="section-2-key-principles-anaesthesia.md" target_heading="Section 2: Key Principles of Safe Use of Medication in Anaesthesia" target_kind="h1_section" -->

If MCT is to be tested in IMR, the test request form is shown in Appendix 1: IMR Allergy Request Form.
<!-- cross_ref target_file="section-0-appendix-AM.md" target_heading="Appendix 1: IMR Allergy Request Form" target_kind="appendix" -->

(Refer to Section 6: Safe Waste Management)
<!-- cross_ref target_file="section-6-safe-waste-management-anaethesia.md" target_heading="Section 6: Safe Waste Management" target_kind="h1_section" -->
```

### How the marker is processed during ingestion

```text
1. Keep the visible human sentence in markdown.
2. Parse the cross_ref marker into metadata on the child chunk where the reference appears.
3. Strip the marker from embedding text and normal LLM prompt text.
4. Retrieval code follows metadata and attaches the referenced evidence before Stage 5 synthesis.
```

Operational rule:

```text
Store cross_refs on the retrieved H2 child chunk that contains the "refer to..." sentence.
The H1 parent may aggregate cross_refs for audit/debugging, but retrieval should follow the child metadata.
```

### Example child metadata

```json
{
  "chunk_level": "h2",
  "heading": "2.1 Risk Assessment",
  "cross_refs": [
    {
      "target_file": "section-3-estimation-of-global-cvd-risk.md",
      "target_heading": "Section 3: Estimation of Global CVD Risk",
      "target_kind": "h1_section"
    }
  ]
}
```

### Required fields

```text
target_file     — filename of the referenced section or appendix
target_heading  — exact heading text as it appears in the target file (non-caps, matching current naming)
target_kind     — one of the allowed values below
```

### Allowed target_kind values

```text
h1_section
```
Use when referring to another `# H1` section/file.

```text
h2_section
```
Use when referring to a specific `## H2` section.

```text
algorithm_flowchart
```
Use when referring to an algorithm, flowchart, pathway, or step sequence.

```text
appendix
```
Use when referring to an appendix stored elsewhere and not copied into the current H1 parent-only block.

### Deep numeric references (Section 3.1.2, Section 3.1.2.1, Table N, Figure N, etc.)

`target_kind` selects a **retrieval unit**, not a heading level. Only `# H1` and `## H2` are independently retrievable chunks — `### H3` / `#### H4` live inside their enclosing H2 and are never returned on their own.

Therefore, resolve any reference deeper than H2 **upward** to the nearest enclosing retrievable unit:

```text
Visible prose                       target_heading                            target_kind
-------------------------------------------------------------------------------------------
"refer to Section 3"                "Section 3: Initial management"           h1_section
"refer to Section 3.1"              "3.1: Clinical history, ..."              h2_section
"refer to Section 3.1.2"            "3.1: Clinical history, ..."              h2_section
"refer to Section 3.1.2.1"          "3.1: Clinical history, ..."              h2_section
"refer to Table 11"                 (enclosing H2 of where Table 11 lives)    h2_section
"refer to Figure 1"                 (enclosing H2 of where Figure 1 lives)    algorithm_flowchart
```

Keep the visible sentence ("refer to Section 3.1.2.1") unchanged so the clinician still sees the exact pointer; the marker resolves to the H2 chunk the retriever can actually fetch.

**Exception** — if the referenced Table/Figure lives inside a `parent_only_reference_start/end` block in some file, set `target_heading` to that file's `# H1` and `target_kind="h1_section"`, since the table is only addressable via the parent context.

Examples:

```md
The simplest risk assessment scheme is the CHADS₂ score (refer to Table 11).
<!-- cross_ref target_file="section-6-thromboembolism-prevention-af.md" target_heading="6.2: Stroke risk stratification" target_kind="h2_section" -->

For ECG interpretation criteria, refer to Section 3.1.2.1.
<!-- cross_ref target_file="section-3-initial-management.md" target_heading="3.1: Clinical history, physical examination and investigations" target_kind="h2_section" -->
```

---

## Section 6: Heading format rule

All headings must follow three formatting rules: **(a) colon after the numeric/letter prefix**, **(b) sentence case (no all-caps)**, and **(c) no Table/Figure as heading**.

### 6a. Colon after numeric or letter prefix

Every numbered or lettered heading must use a colon immediately after the prefix, followed by one space, then the title in sentence case. This applies to `##`, `###`, `####`, and `#####`.

```text
Correct:   ## 3.1: General anaesthesia
Avoid:     ## 3.1 General anaesthesia
Avoid:     ## 3.1. General anaesthesia

Correct:   ### 3.1.1: Handling of inhalational agents
Avoid:     ### 3.1.1 Handling of inhalational agents
Avoid:     ### 3.1.1. Handling of inhalational agents

Correct:   #### a: Storage of medical gas cylinders
Avoid:     #### a. Storage of medical gas cylinders
Avoid:     #### a) Storage of medical gas cylinders

Correct:   ##### Stage 1: Initial assessment
(Stage/Step/Phase + number already uses colon naturally — keep as-is.)
```

Prefix patterns the rule covers:

```text
Numeric:        2.1, 3.1.1, 10.3.3.1
Letter:         a, b, c, A, B, C
Roman numeral:  i, ii, iii, iv (when promoted to heading level)
Stage/Step:     Stage 1, Step 2, Phase 3 (already use colon)
Appendix:       Appendix 1, Appendix A (already use colon)
```

### 6b. Title Case (no ALL-CAPS)

Use Title Case for all heading text — every word is capitalized, including short words like `of`, `in`, `and`, `the`. Preserve acronyms (AF, CVD, IV, NMBA, IMR, HKLAAC, PCA, RA, TML, CVC, MH, LAST, POH, POA, MCT, IE, FRS, LDL, HDL, CKD, DM, HF, OT, IMR, PCI, NSTE-ACS, STEMI, etc.) and intentional mixed-case tokens (HbA1c, mRNA, CHA₂DS₂-VASc).

```text
Correct:   # Section 3: Safe Use Of Medication In Specific Areas
Avoid:     # SECTION 3: SAFE USE OF MEDICATION IN SPECIFIC AREAS
Avoid:     # Section 3: Safe use of medication in specific areas

Correct:   ## 3.1: General Anaesthesia
Avoid:     ## 3.1: GENERAL ANAESTHESIA

Correct:   ## 2.10: Administration Of Highly Concentrated Drugs, Electrolytes, Glucose, And Insulin

Correct:   ### 0.2: Critical Reference Tables
```

Acronyms remain uppercase even mid-heading:

```text
Correct:   ## 1.2: Types Of AF
Correct:   ## 3.1.4: TCI/TIVA Monitoring
Correct:   ### A: Introduction
```

### 6c. Tables and figures are not headings

Table and Figure rows must not be standalone headings. Demote them to **plain prose** (no bold, no hashes) so they remain part of the parent H2/H3 chunk and embed cleanly. Markdown formatting characters like `**` add token noise to the embedded text without improving retrieval — the label text alone is what clinicians search on.

```text
Correct:   Table 1: Blood culture collection summary
Avoid:     ### Table 1: Blood Culture Collection Summary
Avoid:     **Table 1: Blood culture collection summary**

Correct:   Figure 1: Algorithm for the management cascade for patients with AF
Avoid:     #### Figure 1: Algorithm for the Management Cascade for Patients with AF
Avoid:     **Figure 1: Algorithm for the management cascade for patients with AF**
```

Layout requirement — keep one blank line **before** the label and **no blank line** between the label and the table's header row, so the chunker keeps the caption welded to its table:

```md
Some prose ending here.

Table 1: Blood culture collection summary
| Topic | Detail |
|---|---|
| Timing | Before antibiotics |
```

Exception — when a Table/Figure sits inside a `parent_only_reference_start/end` block, it may keep an `###` heading because the chunker masks that block before H2 splitting (see Section 4).

### 6d. Why these rules

```text
Colon: gives the chunker a deterministic delimiter between number and title;
       makes retrieval headings and target_heading strings match exactly.

Title Case: gives a single consistent capitalization across all headings
       so target_heading strings in cross_ref markers match the actual heading
       text exactly; acronyms (AF, CVD, ...) stay uppercase as a separate rule.

Table/Figure demotion: prevents tables from becoming standalone H2/H3 chunks
       that lose their parent clinical context during vector retrieval.
```

Apply these rules when converting existing files. The `target_heading` field in `cross_ref` markers and the `(refer to ...)` text in prose must be updated to match the new heading text in the target file.

---

## Section 7: Cross-reference alignment checklist

When a file is renamed or its headings are changed to sentence case, check and update the following:

```text
1. All cross_ref markers in other files that point to this file:
   - target_file must match the current filename exactly
   - target_heading must match the current H1 (or H2) heading text exactly

2. All prose "(refer to ...)" text in other files that name this section:
   - update the human-readable name to match the new sentence-case heading

3. The current file's own cross_ref markers:
   - verify target_file and target_heading still match the linked file's actual name and heading
```

---

## Section 8: Running the audit script

The audit script `audit_markdown.py` lives at the repo root (`CPG LLM/audit_markdown.py`) and enforces all rules in this guide.

### Rules at a glance

```text
R1  Numeric headings: colon after the number, AND hash level matches numeric depth.
      # Section N: Title           (H1 — "Section N" prefix only, no dotted number)
      ## N.M: Title                (H2 — 2-part number)
      ### N.M.P: Title             (H3 — 3-part number)
      #### N.M.P.Q: Title          (H4 — 4-part number; letter prefix a/b/c also valid)
    Auto-fix: hash level is auto-promoted/demoted to match numeric depth
      (e.g. `### 3.1` -> `## 3.1`, `### 8.2.2.3` -> `#### 8.2.2.3`).
    Advisory: bare `## N:` that duplicates the H1 `Section N` is flagged for manual
      removal (auto-deletion would shift chunk boundaries).
    Letter (a., b.) and roman (i., ii.) prefixes are LEFT ALONE.
R2  Title Case: every word capitalized (including 'of', 'in', 'and'); ALL-CAPS converted; acronyms preserved (AF, CVD, NMBA, etc.)
R3  Table/Figure lines demoted to **bold prose** (skipped inside parent_only_reference blocks).
R4  cross_ref markers validated AND auto-synced. Reports:
      - missing required attributes (target_file / target_heading / target_kind)
      - target_file not found in the markdown tree
      - target_heading doesn't match any heading in the target file (stale or wrong) and no confident replacement found — review manually
      - confident matches: auto-fix target_heading and show before/after diff
R5  Detect-only: prose "refer to Section/Appendix/Table/Figure ..." with no adjacent marker
    AND no unambiguous auto-insert candidate (those are handled by R7).
R6  Whitespace normalization (fixable):
      - strip trailing whitespace
      - exactly 1 blank line BEFORE every heading
      - 0 blank lines AFTER a heading (heading welds to its content)
      - 0 blank lines between a colon lead-in line and its bullet/numbered list
            "should concentrate on:"   ← lead-in
            "- Relief of symptoms"     ← list welded directly below
      - collapse runs of 3+ blank lines to 1
R7  Auto-insert cross_ref markers for UNAMBIGUOUS prose refs (fixable):
      "refer to Section 3" -> append <!-- cross_ref ... --> only when exactly one
      target file in the index has that H1. Table/Figure refs are NOT auto-inserted
      (too many cross-CPG collisions); they fall through to R5 for manual review.
R8  Detect-only: flag files containing more than one `# H1` heading
    (the parent-child rule allows only one H1 per file).
```

### Recommended workflow: folder by folder

Run dry-run first to review what will change, then apply with `--fix`:

```powershell
# 1. Dry-run a folder — review all findings, see before/after diffs
python "CPG LLM/audit_markdown.py" "CPG LLM/markdown/Anaesthesia-Medication-Safety"

# 2. Apply fixes once the diff looks correct
python "CPG LLM/audit_markdown.py" "CPG LLM/markdown/Anaesthesia-Medication-Safety" --fix

# 3. Re-run dry-run to confirm folder is clean
python "CPG LLM/audit_markdown.py" "CPG LLM/markdown/Anaesthesia-Medication-Safety"
```

### Full-tree commands

```powershell
# Dry-run across every CPG folder
python "CPG LLM/audit_markdown.py"

# Apply fixes across every CPG folder
python "CPG LLM/audit_markdown.py" --fix
```

### Run a single rule

```powershell
# Only check for missing cross_ref markers (R5 is report-only — safe to run anytime)
python "CPG LLM/audit_markdown.py" --rules R5

# Only fix heading colons + sentence case, skip Table/Figure and cross_ref work
python "CPG LLM/audit_markdown.py" --rules R1,R2 --fix

# Only sync cross_ref target_heading values (after renaming a target file)
python "CPG LLM/audit_markdown.py" --rules R4 --fix
```

### Skip cross_ref sync

```powershell
python "CPG LLM/audit_markdown.py" --fix --no-cross-ref
```

### What the output looks like

Each finding is shown with rule tag, line number, and a unified-diff style before/after pair so you can verify the change folder by folder:

```text
========================================================================
FOLDER: Atrial-Fibrillation(2012)
========================================================================

  [DRY-RUN] section-1-introduction-af.md  (5 findings)
    [R1    ] L16  Would fix:
             -  ### 1.1 Definition
             +  ### 1.1: Definition
    [R2    ] L1   Would fix:
             -  # SECTION 1: INTRODUCTION
             +  # Section 1: Introduction
    [R5    ] L91  missing cross_ref marker for 'Table 1'
             > Utilise tall-man lettering (refer to Table 1: Examples of...
```

`[FIXED]` replaces `[DRY-RUN]` once `--fix` is applied.

### After running --fix

Always do a follow-up dry-run on the same folder to confirm zero findings remain:

```powershell
python "CPG LLM/audit_markdown.py" "CPG LLM/markdown/<folder>"
```

R5 findings are advisory — they list `(refer to ...)` sentences that lack a `<!-- cross_ref ... -->` marker. The script never inserts these markers automatically because `target_file` and `target_kind` cannot be guessed safely. Add markers manually using the syntax in Section 5.

---

## Section 9: Cleanup rule

Before ingestion, clean markdown so chunk boundaries stay boring and predictable:

```text
Remove redundant horizontal separators like repeated --- lines.
Normalize excessive blank lines.
Keep list indentation consistent.
Keep table headers directly above their table.
Avoid decorative headings that look like real H2/H3 structure.
Remove temporary logs and generated run files from the repo.
```
