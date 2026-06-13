# SEGMENT 3 — Solution Demo [~1:12 screen · ~1:06 narration]
*Screen recording — ClearPath UI, one continuous uninterrupted flow*

**General recording instructions:**
- Record at 1080p minimum, 60fps preferred
- Do not stop between scenes — this is one seamless screen recording
- Use the real demo case throughout: *CHUA, 041206-10-1597, 21 yrs, Male — T2DM + Erectile Dysfunction post-PCI*
- Slow, deliberate cursor movements — never rush a scroll
- Overlay cards are small, bottom-left corner only — never cover UI content
- Zoom-punch into key UI elements in post (CapCut / Premiere / DaVinci)
- Pre-load the demo account (Dr Chin Pei Kang) so login is instant

---

## Part A — System Introduction [~0:26 screen · ~0:23 narration]

---

### Scene 1 — Patient Records [~10s]

**Main focus — screen:**
Click "My Patients" in the sidebar. The patient list loads — 18 patients total, "Follow-up Required (3)" tab visible. Click to expand one patient (UI 4 — 55-year-old with T2DM and Erectile Dysfunction). The expanded row shows:
- Comorbidities: Stable CAD, T2DM, Obesity, Erectile Dysfunction (new)
- Consultation history: 2 records, latest 09 Jun 2026
- Current medications: Metformin 1g BD

Cursor hovers the "Latest" consultation record.

**Overlay card (bottom-left):**
> `My Patients — Full history, pre-loaded from last consultation`

**Narration (~9s):**
> "Every patient record is persistent — comorbidities, medications, and history all pre-loaded before the clinician walks in."

---

### Scene 2 — IC Lookup [~4s]

**Main focus — screen:**
Click "Consultation" in the sidebar. The consultation wizard opens — Patient Lookup box centred on screen. Cursor moves to the IC field, types IC number quickly (`600521-04-1834`). Click "Continue →".

**No overlay card — keep it moving.**

**Narration (~4s):**
> "We key in the patient IC — full record retrieves instantly."

---

### Scene 3 — Assessment Form + rPPG + STT [~12s]

**Main focus — screen:**
The full data input form loads. Left panel: demographics auto-filled (name, DOB, sex, allergies, comorbidities, current medications). Right panel: Vital signs form, Clinical notes fields.

Cursor moves across the form, then:
1. Hover the **rPPG scan** button — hold 2s. Tooltip: `Remote Photoplethysmography — contactless HR & SpO₂`
2. Hover the **Record Consult** microphone icon — hold 2s. Label: `Speech-to-Text — dictate CC, HPI, PE directly`

**Overlay card (bottom-left):**
> `Assessment — Patient context + vitals + notes`

**Narration (~12s):**
> "Now we input patient data. Context is pre-filled from their record. With rPPG we capture vitals contactlessly, and speech-to-text transcribes the consultation directly into structured notes."

---

## Part B — Agentic Pipeline Demo [~0:46 screen · ~0:41 narration]

---

### Scene 4 — Pipeline Loading → DDx Result [~12s]

**Main focus — screen:**
Click "Analyze assessment →". Screen transitions to the pipeline view — step indicator shows "Analysing..." with 4 stages listed (DDx, CPG Routing, Evidence Retrieval, Plan Synthesis). DDx Analysis is running (spinning). Let it sit for 3–4 seconds, then DDx completes and the diagnosis cards appear.

Patient header: `CHUA · 041206-10-1597 · 21 yrs · Male`

**Overlay card (bottom-left):**
> `Agentic Pipeline — 4-stage reasoning, transparent at every step`

**Narration (~7s):**
> "Submit the assessment — ClearPath begins a four-stage pipeline. Every stage visible in real time. No black box."

---

### Scene 5 — DDx Confirm (Dr selects, live trace) [~8s]

**Main focus — screen:**
Screen lands on Step 2 of 4 — Diagnosis. Left panel shows the AI Reasoning Trace (symptom extraction, hypothesis generation, ICD code injection). Right panel shows 5 diagnosis cards ranked by confidence.

Cursor moves down the cards:
1. Click "Major" on T2DM (5A11, confidence 0.82)
2. Click "Minor" on Male erectile dysfunction (HA01.1, override note visible)

**Overlay card (bottom-left):**
> `DDx Analysis — ICD-11 mapped · Confidence ranked · Clinician confirms`

**Narration (~8s):**
> "Differential diagnosis maps symptoms to ICD-11 codes ranked by confidence. The doctor reviews the live reasoning trace and confirms each diagnosis."

---

### Scene 6 — CPG Routing + Evidence Retrieval [~2s]

**Main focus — screen:**
After clicking "Confirm →", screen transitions to "Generating Care Plan". Pipeline shows CPG Routing ACTIVE — live activity feed ticking. CPG Routing turns green, Evidence Retrieval activates — chunks counter incrementing, RAG Match Quality Index bar visible (Mean Match 0.88).

Cursor hovers the RAG Match Quality Index bar — hold 2 seconds.

**Overlay cards (bottom-left):**
> `CPG Routing — matched to Malaysian MOH guidelines`
> *(transitions to)* `Evidence Retrieval — Hybrid RAG · Cosine similarity · Boilerplate filtered`

**Narration (~11s):**
> "CPG Routing matches each diagnosis to its governing Malaysian MOH guideline, then fires targeted evidence retrieval — only high-quality, locally scoped chunks proceed."

---

### Scene 7 — Care Plan + Safety Banner [~10s]

**Main focus — screen:**
Screen lands on Step 3 of 4 — Recommended Care Plan.

**Centre top — Safety banner (RED, critical):**
> `Safety concerns require acknowledgement — 1 Critical`
> `PDE-5 inhibitor + nitrates — severe hypotension interaction`

Cursor hovers the red safety banner — hold 3 seconds (visual centrepiece of the demo). Then scrolls through: Medications (Metformin `A 1st-line` badge, SGLT2-i, PDE-5i) · Red Flags · Follow-up timeline.

Cursor clicks "Keep + acknowledge risk".

**Overlay card (bottom-left):**
> `Care Plan — Safety-flagged · CPG-cited · Clinician sign-off required`

**Narration (~10s):**
> "The care plan arrives structured — medications, red flags, follow-up timeline. A critical safety flag blocks sign-off until the clinician explicitly acknowledges it."

---

### Scene 8 — Final Document + Approve [~6s]

**Main focus — screen:**
Step 4 of 4 — Final Care Plan. All four step indicators green. SOAP document visible: vitals, diagnoses, medications. Right sidebar: "Approve Care Plan" button (teal).

Cursor hovers "Approve Care Plan" — hold 2 seconds — click.

**Overlay card (bottom-left):**
> `Final Care Plan — Approved · Saved · Ready to distribute`

**Narration (~5s):**
> "One click approves, saves to record, and distributes. Fully auditable end to end."

---

## Production Notes

### Key zoom-punch moments (flag all for post-editing)
- Scene 1: zoom in on comorbidity chips — especially "Erectile Dysfunction (new)"
- Scene 1: zoom in on Latest consultation record showing diagnosis + ICD tag
- Scene 3: zoom-punch rPPG button with tooltip
- Scene 3: zoom-punch Record Consult microphone icon
- Scene 5: zoom in on confidence bar + "System suggests Major" chip on T2DM
- Scene 5: zoom in on override note on Erectile Dysfunction card
- Scene 6: zoom in on RAG Match Quality Index bar — Mean Match 0.88
- Scene 7: zoom in on red safety banner — hold 3s before acknowledging
- Scene 7: zoom in on "A 1st-line" evidence badge on Metformin
- Scene 8: zoom in on BMI value (31, red — above range)

---

### Timing summary

| Scene | UI Page | Screen | Narration |
|---|---|---|---|
| 1 | Patient records | ~10s | ~9s |
| 2 | IC lookup | ~4s | ~4s |
| 3 | Assessment form + rPPG + STT | ~12s | ~12s |
| 4 | Pipeline loading → DDx result | ~12s | ~7s |
| 5 | DDx confirm + live trace | ~8s | ~8s |
| 6 | CPG Routing + Evidence Retrieval | ~2s | ~11s |
| 7 | Care Plan + Safety banner | ~10s | ~10s |
| 8 | Final doc + Approve | ~6s | ~5s |
| **Total** | | **~1:04** | **~1:06** |

---

### Screen recording checklist
- [ ] Demo account (Dr Chin Pei Kang) pre-loaded — start directly at dashboard
- [ ] Patient record UI 4 expanded and ready — do not hunt for it on camera
- [ ] IC number ready to type: `600521-04-1834`
- [ ] Assessment form shows a pre-loaded patient (comorbidities filled)
- [ ] rPPG tooltip visible in Scene 4 — test hover behaviour before recording
- [ ] Full run-through recorded first as master take before isolated scene re-records
- [ ] Safety banner (Scene 8) — let the red colour sit before acknowledging; do not rush
- [ ] Care plan tabs (Scene 8) — scroll through: Medications, Red Flags, Follow-up
- [ ] Approval click (Scene 9) — slow hover on button before clicking

---

### Narration files for this segment
- [ ] `narration_seg3_scene1.mp3` — Patient records
- [ ] `narration_seg3_scene2.mp3` — IC lookup
- [ ] `narration_seg3_scene3.mp3` — Assessment form + rPPG + STT
- [ ] `narration_seg3_scene4.mp3` — Pipeline loading → DDx result
- [ ] `narration_seg3_scene5.mp3` — DDx confirm
- [ ] `narration_seg3_scene6.mp3` — CPG Routing + Evidence Retrieval
- [ ] `narration_seg3_scene7.mp3` — Care Plan + Safety banner
- [ ] `narration_seg3_scene8.mp3` — Final doc + Approve
