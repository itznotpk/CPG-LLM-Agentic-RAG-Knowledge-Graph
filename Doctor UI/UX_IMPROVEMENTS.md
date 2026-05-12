# Home Tab — UX Improvement Proposal

**Scope:** Doctor UI Home tab metrics, framed for a remote *Klinik Kesihatan* (KK) context.
**Lens:** UX only — no implementation, no engineering scope. Focused on whether the surfaced metrics actually help a KK MO (Medical Officer) make a better decision in the next 60 seconds of their shift.

---

## 1. The current four metrics — honest critique

| Card | What it shows | What a KK MO actually does with it |
|---|---|---|
| **Total Appointments** | `6` | Glances once at start of clinic. Vanity number after that. |
| **Waiting** | `6` | Duplicate of "Total" before clinic starts. Becomes useful only mid-clinic, but the schedule list below already conveys this visually. |
| **Emergency** | `critical` count | Useful — but only as an *alert*, not a *metric*. A count of "1" demands an action ("see Raj Kumar now"), not a number to track. |
| **High Risk** | `high` count | Same problem — a count is the wrong shape for a triage cue. |

**Core UX problem:** all four cards answer *"how many?"* — a question a KK MO rarely asks. KK clinicians work patient-by-patient, not in aggregate. The dashboard reads like a hospital admin dashboard, not a frontline clinical cockpit.

**Worse:** none of these metrics communicate *why this product exists*. A clinician opening this screen for the first time sees "6 appointments, 1 emergency" — which any paper register also tells them. The Agentic RAG value (CPG-grounded reasoning, time saved on care-plan synthesis, evidence traceability, MOH-aligned decisions) is **completely invisible** at the entry point.

---

## 2. Re-framing — what KK clinics actually need at a glance

A KK MO in a rural setting has a different cognitive load than a hospital specialist:

- **Solo or near-solo practice** — no junior to delegate to. Every minute on documentation is a minute off the next patient (KK average load: 60–120 patients/day per MO).
- **Limited specialist access** — referral decisions are high-stakes; the MO needs confidence that "manage locally vs refer" is the right call.
- **CPG adherence pressure** — MOH audits and KPI reporting expect documented alignment with national CPGs (DM, HTN, asthma, antenatal).
- **Intermittent connectivity** — sync state and queued actions matter more than absolute counts.
- **Continuity gaps** — patients seen by different MOs across visits; the *handover surface* matters more than the *appointment count*.

The Home tab should answer three questions in the first 3 seconds:

1. **"What needs me right now?"** (triage signal, not a count)
2. **"Is the AI earning its keep today?"** (impact metric tied to the value prop)
3. **"What can go wrong if I don't act?"** (overdue follow-ups, missed CPG actions, sync failures)

---

## 3. Proposed metric set — tied to problem & needs statements

Replace the four "how many?" cards with a **two-row layout**: a top row of *clinical impact* (the value story) and a contextual strip of *operational signal* (what to do next).

### Row A — Agentic RAG Impact (the "why we built this" row)

| Card | Metric | Why it matters at a KK | Source |
|---|---|---|---|
| **Time reclaimed today** | `≈ 47 min saved` (vs manual care-plan writing baseline) | Directly maps to "more patients seen / less burnout" — the #1 KK pain point. | Sum of `careplan.generationTime` deltas vs baseline (e.g. 8 min manual → 90 s AI). |
| **CPG-aligned plans** | `12 / 14 plans · 86%` | MOH KPI proxy. Tells the MO their documentation is audit-ready without opening each chart. | Care plans where every recommendation has a `cpgReference`. |
| **Evidence-backed decisions** | `38 citations issued today` | Surfaces the *traceability* differentiator — every AI suggestion is attributable. Builds trust with the clinician. | Count of `cpgReference` chips rendered across today's plans. |
| **Referral confidence** | `3 referrals · all CPG-justified` | Speaks to the "manage locally vs refer" dilemma. Shows the AI is supporting, not just generating noise. | Care plans flagged `referralRecommended: true` with a CPG anchor. |

These four metrics tell a coherent story: *"the assistant saved you time, kept you compliant, gave you receipts, and backed your hardest calls."* That is the product narrative the current cards completely miss.

### Row B — Operational signal (replaces today's strip, but reshaped as cues, not counts)

Instead of card-shaped counts, render this as a **single horizontal "Today's pulse" strip** with 3–4 inline cues:

- 🔴 **1 patient needs you now** — *Raj Kumar · hypertensive urgency · arrived 12 min ago* → click to open chart
- 🟡 **2 follow-ups overdue** — *Wong Kin Meng (TCA 3d ago), Fatimah Ismail (TCA 5d ago)* → click to bulk-reschedule
- 🔵 **Next 30 min:** Siti Nurhaliza (screening), Lee Mei Ling (antenatal 20w)
- ⚪ **Sync:** *MPIS up to date · last 2 min ago* (or red if stale > 30 min — critical for KK with patchy connectivity)

This converts "Emergency: 1" (a number) into "Raj Kumar — see him next" (an action). Same data, completely different cognitive cost.

---

## 4. Visual hierarchy fix

The current Home gives equal weight to *Total Appointments* and *Emergency* — they share a row, same card size, same visual weight. That is wrong: one is reference data, the other is a triage alert.

Recommended hierarchy:

1. **Greeting + date/time** — minimal (already good)
2. **"Today's pulse" strip** — actionable cues, full-width, highest density
3. **Agentic RAG Impact row** — 4 cards, slightly muted styling (information, not alert)
4. **Today's schedule** — the patient list (already the workhorse — give it more vertical space)

Drop the four current stat cards entirely.

---

## 5. Specific copy & micro-UX notes

- **"Welcome, Dr. Tay"** is generic. Try **"Selamat pagi, Dr. Tay — 6 patients on the list, Raj Kumar needs you first."** A one-line situational brief beats a generic greeting.
- **No raw counts without a verb.** "Emergency: 1" → "1 patient needs you now". "High Risk: 3" → "3 high-risk reviews queued".
- **Show baselines on impact metrics.** "47 min saved" is meaningless without "vs ~8 min/plan manual". A tiny "ⓘ how this is measured" affordance preserves trust.
- **Trend, not just today.** A sparkline behind each impact card (last 7 days) tells the MO if the AI is *consistently* helping or just had one good day.
- **Connectivity state is first-class** at a KK. A persistent "MPIS sync" indicator in the strip prevents the worst KK failure mode: *thinking* a patient was synced when they weren't.
- **No "URGENT" badge in red on a yellow card.** The Raj Kumar appointment row currently uses red bg + red badge — colour-blind users lose the badge. Use icon + text, reserve red for one element per row.

---

## 6. What to remove

- `Total Appointments` card (the schedule list answers this for free)
- `Waiting` card (visible in the schedule list via status pills)
- `Recent Activity` feed at the bottom — currently shows "Care plan generated 2 days ago" which is neither actionable nor proof-of-value. If kept, reshape as **"Last 24 h impact"** with concrete artifacts: *"You generated 8 care plans, 7 cited CPGs, 1 escalated to specialist."*

---

## 7. Mapping back to the problem & needs statements

| Problem statement | Old metric | New metric that answers it |
|---|---|---|
| KK MOs spend disproportionate time documenting vs treating | — (not surfaced) | **Time reclaimed today** |
| CPG adherence is hard to evidence at audit time | — | **CPG-aligned plans %** |
| Clinicians distrust black-box AI suggestions | — | **Evidence-backed decisions (citations)** |
| Referral decisions are high-stakes & under-supported | — | **Referral confidence** |
| Triage prioritisation in busy clinics | Emergency: 1 | **"Raj Kumar needs you now" cue** |
| Continuity & overdue follow-ups slip through | — | **Overdue TCA cue in pulse strip** |
| Intermittent connectivity hides sync failures | — | **MPIS sync state in pulse strip** |

Every new metric ties directly to a documented KK pain point. None of the current four do.

---

## 8. One-line summary

> The current Home tab tells the clinician *how busy they are* — which they already know. It should tell them *what the assistant did for them today* and *what to act on next*. Both are within reach using data already flowing through the care-plan pipeline.
