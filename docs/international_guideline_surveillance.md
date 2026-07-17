# International Guideline Check and Comparison Layer

## Purpose

ClearPath currently uses Malaysian Ministry of Health (MoH) Clinical Practice
Guidelines (CPGs) as its local clinical standard and retrieves recent published
evidence through its EBM integration. This proposal adds an optional
international-guidance check for a clinician-selected working diagnosis.

The purpose is to make potentially newer international guidance visible without
silently replacing the Malaysian CPG, which may differ because of local
medicines, service availability, referral pathways, regulation, and population
needs.

## What Already Exists: EBM Synthesis

The existing EBM feature is patient-level and is already part of the care-plan
workflow:

```text
Patient case -> DDx -> Malaysian CPG + knowledge graph -> draft care plan
             -> Europe PMC literature search -> refined care plan -> safety review
```

It searches recent published literature after a draft plan has been created.
It may support a Malaysian CPG recommendation or, when no routed Malaysian CPG
addresses the question, surface a clearly labelled literature-based suggestion.
It is an evidence-retrieval and synthesis feature; it does not determine whether
one formal guideline edition supersedes another.

## Proposed Feature: International Guideline Check

The new layer is guideline-level rather than patient-level. It checks approved
international guideline publishers for newer or materially different guidance
for the clinician's selected diagnosis, then compares it with the active
Malaysian CPG.

```text
Selected working diagnosis
        -> optional international-guidance check
        -> approved-source retrieval and version check
        -> local-versus-international comparison
        -> clinician review and documented choice
```

The Malaysian MoH CPG remains the active local standard. International guidance
is supplementary until it has been reviewed and formally approved for reuse by
an authorised clinical/governance reviewer.

## UI Workflow / Clinician Journey

### 1. Review DDx and choose the working diagnosis

ClearPath presents the ranked differential diagnoses. The clinician selects the
working diagnosis that will guide the care-plan workflow.

### 2. Choose whether to check international guidance

After diagnosis selection, display an optional control:

```text
International guidance check                                  [ Off / On ]
Check approved international guideline sources for newer guidance.
Malaysian MoH CPG remains the active local standard.
```

The default is **Off** to preserve the fast standard workflow. When enabled,
ClearPath runs the check for the selected diagnosis while preparing the plan.

### 3. Generate the Malaysian CPG-grounded plan

The plan continues to use the routed Malaysian CPG and existing safety checks
as its baseline. The feature must not block a plan if an external source cannot
be reached.

### 4. Present the evidence view

Display two view controls in the care-plan evidence area:

```text
[ Malaysian guidance ]  [ Compare international guidance ]
```

**Malaysian guidance** is the default view. It shows the active CPG source and
the recommendations used in the plan.

**Compare international guidance** shows a structured comparison only when a
relevant approved source is found:

| Malaysian guidance (active local standard) | International guidance (supplementary) |
| --- | --- |
| CPG title, edition, publisher, date | Publisher, guideline version, date |
| Relevant local recommendation | Newer or differing recommendation |
| Citation and section | Citation, link, and evidence status |
| Local applicability | Localisation cautions: formulary, service, referral, regulation |

If no relevant update is found, state that clearly rather than implying that the
Malaysian CPG has been verified as current worldwide.

### 5. Clinician action

Below the comparison, offer actions that preserve clinical control:

- **Use Malaysian guidance** — keeps the active local plan; this is the default.
- **Consider international guidance for this patient** — records a
  citation-backed, explicitly supplementary consideration in this consultation.
  It does not overwrite Malaysian CPG recommendations.
- **Flag for governance review** — creates a review item for authorised clinical
  reviewers to assess whether the international change should become a reusable
  local overlay or future CPG update request.

### 6. Final plan and audit trail

The signed-off plan records:

- active Malaysian CPG title and version;
- whether the international check was enabled;
- sources and versions returned by the check;
- the clinician's chosen action and rationale, if international guidance was
  considered; and
- any governance-review reference.

Example status:

> **Active standard:** Malaysian MoH CPG.  
> **International guidance check:** completed; one potentially relevant update
> found.  
> **Use in this plan:** Malaysian guidance retained; international guidance
> documented as a supplementary consideration.

## Safety and Authority Rules

1. Malaysian MoH CPGs remain authoritative for the default plan.
2. The system must never silently replace a local recommendation with an
   international recommendation.
3. Only curated, approved guideline publishers may be searched; this is not a
   general web-search feature.
4. A treating clinician may make and document a patient-level decision.
5. Only an authorised clinical/governance reviewer may approve an international
   recommendation as a reusable system-wide local overlay.
6. Every comparison and clinician action requires source, version, date, and
   provenance information.
7. External-source failure is non-blocking; ClearPath continues with the
   Malaysian CPG-grounded workflow and states that the international check was
   unavailable.

## Relationship to the Existing EBM Work

| Area | Existing EBM integration | Proposed international-guidance layer |
| --- | --- | --- |
| Primary unit | Patient case and draft plan | Selected diagnosis and CPG recommendation |
| Main source | Europe PMC literature | Curated official guideline publishers |
| Primary question | What recent evidence supports or fills a care-plan gap? | Is there a newer or materially different formal guideline? |
| Output | Literature evidence used in refined synthesis | Local-versus-international comparison and update alert |
| Authority | Supporting evidence; no silent CPG override | Supplementary comparison; no silent local-standard replacement |
| Approval | Treating clinician reviews evidence for this case | Clinician chooses case-level handling; governance approves reusable overlays |

The two capabilities should share diagnosis input, citation rendering, provenance
models, audit logging, and safety review. However, the international-guidance
layer requires separate version tracking, source governance, comparison logic,
and approval states.

## Deliverables

### Product and UI

- DDx-stage **International guidance check** toggle, off by default.
- Malaysian-guidance and comparison view controls in the care-plan evidence area.
- Side-by-side local-versus-international recommendation comparison.
- Clear source/version/date badges and localisation-caution labels.
- Clinician actions: use local guidance, consider internationally sourced
  guidance for this patient, and flag for governance review.
- Final plan status and audit-trail display.

### Backend and Data

- A curated source registry by diagnosis/specialty, not open web search.
- Source adapters for approved guideline publishers.
- Guideline metadata store: publisher, title, version, publication/update date,
  URL, condition scope, and retrieval timestamp.
- Recommendation comparison output with a structured difference summary and
  localisation considerations.
- Consultation-level audit fields for check status, sources, clinician action,
  rationale, and governance-review identifier.
- Governance-review queue and an approved local-overlay/versioning model.

### Safety and Quality

- Explicit authority rules enforced in synthesis and UI.
- Tests for no-result, timeout, contradictory guidance, and unavailable source
  handling.
- Tests proving that international guidance cannot silently change the active
  Malaysian plan.
- Evaluation set covering version accuracy, comparison accuracy, provenance,
  clinician-action logging, and local-CPG retention.

## Suggested Delivery Phases

1. **Phase 1 — Read-only comparison:** one or two curated sources, diagnosis
   toggle, source/version display, and local-versus-international comparison.
2. **Phase 2 — Case-level documentation:** clinician action buttons and audit
   trail; international content remains supplementary.
3. **Phase 3 — Governance workflow:** review queue, approved local overlays,
   version history, and periodic scheduled surveillance.

No MCP or autonomous agent is required for Phase 1. A conventional backend
service with controlled source adapters is easier to test, safer to govern, and
fits the existing EBM architecture. MCP connectors can be introduced later if
they provide reliable access to approved guideline publishers.
