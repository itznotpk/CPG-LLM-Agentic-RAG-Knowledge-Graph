# Markdown Cross-Reference Marker Guide

Use a `cross_ref` marker only when the referenced content lives outside the current H1 parent section.

Do not add a `cross_ref` marker if the referenced table, form, appendix excerpt, or reference material is already copied into the current H1 using a parent-only reference block.

## Parent-Only Reference Block

Use this when shared reference material should be visible during synthesis but should not become its own retrievable child chunk.

```md
<!-- parent_only_reference_start -->
### Reference Table: Global CVD Risk Categories

| Risk category | Criteria |
|---|---|
| Low risk | ... |
| High risk | ... |
<!-- parent_only_reference_end -->
```

Behavior:

```text
Stored in H1 parent context: yes
Embedded as retrievable H2 child: no
Fetched separately by cross_ref: no
```

## Cross-Reference Marker

Use this when the sentence says "refer to Section..." and the target is outside the current H1 parent.

```md
For estimation of global CVD risk, refer to Section 3: Estimation of Global CVD Risk.
<!-- cross_ref target_file="section-3-estimation-of-global-cvd-risk.md" target_heading="Section 3: Estimation of Global CVD Risk" target_kind="h1_section" -->
```

During ingestion:

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

Example child metadata:

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

## Required Fields

```text
target_file
target_heading
target_kind
```

## Allowed target_kind Values

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

## Simple Rule

```text
Referenced content already pasted inside current H1 parent_only_reference block:
  no cross_ref marker needed

Referenced content lives outside current H1:
  add cross_ref marker
```
