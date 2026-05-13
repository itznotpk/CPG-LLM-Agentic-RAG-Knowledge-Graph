# Markdown Parent-Child Standardization Guide

Use this guide when aligning CPG markdown for Phase A Step 2 parent-child re-ingest.

Recent applied examples:

- `markdown/Anaesthesia-Medication-Safety/` has been renamed into standard section files such as `section-0-appendix.md`, `section-3-safe-use-of-medication.md`, and `section-5-safe-medication-practice.md`.
- Anaesthesia Medication Safety sections now use `# H1` parent sections, `## H2` retrievable children, and `### H3` / `#### H4` nested details.
- Anaesthesia Section 2 uses `parent_only_reference_start/end` for shared tables such as TML examples and CVC medication examples.
- `markdown/Atrial-Fibrillation(2012)/section-3-initial-management.md` has been aligned toward the same parent-child hierarchy.

## Heading Structure

Use exactly one `# H1` as the parent section for each markdown file.

Use `## H2` for retrievable clinical child chunks.

Use `### H3` for numbered subsections inside an H2, such as `3.1.1`, `3.1.2`, and `3.1.3`.

Use `### H3` for tables that belong directly under the current H2.

Use `#### H4` and lower headings when a subsection or table falls under an H3.

Do not keep duplicate `# H1` headings inside the same file. If the source document repeats the section title after a front matter or overview block, convert the repeated title to plain text, remove it, or demote it to `##` only if it should become a retrievable child chunk.

## File Naming Rule

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

## Applied Examples From Current Repo

Anaesthesia Medication Safety Section 2:

```md
# SECTION 2: KEY PRINCIPLES OF SAFE USE OF MEDICATION IN ANAESTHESIA

## 2.1 AIMS OF SAFE MEDICATION ADMINISTRATION

## 2.2 RESPONSIBILITIES OF ANAESTHESIA HEALTHCARE PROFESSIONALS

## 2.9 MEDICATION ADMINISTRATION

### 2.9.1 Introduction

### 2.9.2 Safe Practice

<!-- parent_only_reference_start -->
### Shared Reference: Tall Man Lettering Examples
...
<!-- parent_only_reference_end -->
```

Behavior:

```text
SECTION 2 file:
  one H1 parent

2.1, 2.2, 2.9:
  H2 child chunks retrievable by vector search

2.9.1 and 2.9.2:
  H3 content inside H2 child 2.9

Shared tables:
  stored in H1 parent context only
  not emitted as independent H2 children
```

Anaesthesia Medication Safety Section 3:

```md
# SECTION 3: SAFE USE OF MEDICATION IN SPECIFIC AREAS

## 3.1 GENERAL ANAESTHESIA

### 3.1.1 Handling of Inhalational Agents/ Volatile Agents

### 3.1.2 Medical Gases

#### a. Storage of Medical Gas Cylinders

#### b. Handling Medical Gas Cylinders

## 3.2 REGIONAL ANAESTHESIA

### 3.2.1 Safe Administration of Drugs in Regional Anaesthesia (RA)
```

Behavior:

```text
H2 child 3.1 includes:
  3.1.1
  3.1.2
  H4 lettered details a, b, c, etc.

H2 child 3.1 ends before:
  ## 3.2 REGIONAL ANAESTHESIA
```

Atrial Fibrillation Section 3:

```md
# SECTION 3: INITIAL MANAGEMENT

## 3.1 Clinical History, Physical Examination and Investigations

### 3.1.1 Detection

#### 3.1.1.1 Electrocardiogram
```

Behavior:

```text
H1 parent:
  full initial management section

H2 child 3.1:
  includes 3.1.1 and 3.1.1.1
  ends before the next H2 or next H1
```

Example:

```md
# Section 3: Diagnosis of Infective Endocarditis

## 3.1 Blood Cultures
Blood cultures should be taken before antibiotics...

### 3.1.1 Timing
Collect samples before antimicrobial therapy where possible.

### 3.1.2 Number of Sets
At least three sets may be required depending on clinical context.

### Table 1: Blood Culture Collection Summary

| Topic | Detail |
|---|---|
| Timing | Before antibiotics |
| Sets | Multiple sets if clinically indicated |

## 3.2 Echocardiography
Echo is recommended when IE is suspected...

### Transthoracic Echocardiography
Use as the initial imaging test when appropriate.

### Transoesophageal Echocardiography
Use when suspicion remains high or image quality is inadequate.

#### Table 2A: Echocardiography Indications

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

## H2 Child Boundary Rule

```text
An H2 child starts at a ## heading.
It includes paragraphs, lists, tables, and H3/H4 headings under that H2.
It ends before the next ## heading or next # heading.
```

Do not use `##` for decorative labels or minor subtopics. Use `###` instead when the content should remain inside the current H2 child.

## Numbering Rule

Use heading levels by document hierarchy, not by visual size.

```text
# Section 3                         H1 parent
## 3.1 Primary Prevention           H2 child
### 3.1.1 Information Required      H3 inside 3.1
### 3.1.2 Risk Stratification       H3 inside 3.1
### Table 7: Prevalence...          H3 table inside 3.1
#### Table 1A: Points for Men       H4 table under an H3 table group
```

Example based on `section-3-estimation-of-global-cvd-risk.md`:

```md
# SECTION 3: ESTIMATION OF GLOBAL CARDIOVASCULAR RISK

## 3.1 Primary Prevention

### Table 7: Prevalence of CV Risk Factors among Adults >=18 years of age in Malaysia

| Age Group | Hypercholesterolaemia (%) | Hypertension (%) |
|---|---|---|
| 18-19 | ... | ... |

### 3.1.1 Information Required for CV Risk Assessment

Text for the required information...

### 3.1.2 CV Risk Stratification using the FRS General CVD Risk Score

Text for risk stratification...

### Table 1 & 2: FRAMINGHAM RISK SCORE FOR ASSESSMENT OF CVD RISK

#### Table 1A: Estimation of 10-year CVD Points for MEN

| Points | Age, yr | HDL-C |
|---|---|---|
| 0 | 30-34 | 1.2-<1.3 |

#### Table 1B: CVD Risk for Men

| Total Points | 10-year Risk % |
|---|---|
| 0 | 1.6 |

## 3.2 Secondary Prevention

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

## Parent-Only Reference Block

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
```

## Parent-Only Heading Rule

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

## Simple Rule

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

## Cleanup Rule

Before ingestion, clean markdown so chunk boundaries stay boring and predictable:

```text
Remove redundant horizontal separators like repeated --- lines.
Normalize excessive blank lines.
Keep list indentation consistent.
Keep table headers directly above their table.
Avoid decorative headings that look like real H2/H3 structure.
Remove temporary logs and generated run files from the repo.
```
