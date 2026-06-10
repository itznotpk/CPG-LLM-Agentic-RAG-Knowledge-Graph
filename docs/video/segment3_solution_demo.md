# SEGMENT 3 — Solution Demo [1:00–3:30]
*Screen recording — ClearPath UI, 13 scenes, one continuous uninterrupted flow*

**General recording instructions:**
- Record at 1080p minimum, 60fps preferred
- Do not stop between scenes — this is one seamless screen recording
- Use the real demo case throughout: *CHUA, 041206-10-1597, 21 yrs, Male — T2DM + Erectile Dysfunction post-PCI*
- Slow, deliberate cursor movements — never rush a scroll
- Overlay cards are small, bottom-left corner only — never cover UI content
- Zoom-punch into key UI elements in post (CapCut / Premiere / DaVinci)
- Pre-load the demo account (Dr Chin Pei Kang) so login is instant

---

## Part A — System Introduction [1:00–2:10]

---

### Scene 3a — Landing Page [1:00–1:08]

**Main focus — screen:**
The ClearPath official landing page is on screen. Cursor idles — let the interface breathe for 3 seconds. Page is fully loaded: headline, feature stats (30 CPGs, 248 codes, 5-stage pipeline, 100% audit-logged), and the "Sign in" button visible.

**Overlay card (bottom-left, small, fades in after 2 seconds):**
> `ClearPath — Evidence-Based Clinical Practice Guidance System`

**Narration:**
> "This is ClearPath — a clinical decision support system built on Malaysia's Ministry of Health guidelines. Every decision it makes is grounded in evidence, auditable, and patient-specific."

---

### Scene 3b — Sign In [1:08–1:18]

**Main focus — screen:**
Click "Sign in →". The login screen slides in — left panel shows the ClearPath brand panel with ECG animation; right panel shows the sign-in form. Email and password fields are pre-filled (or typed slowly). Click "Sign in →".

**No overlay card needed here.**

**Narration:**
> "Access is role-gated. Each clinician logs in to their own workspace — consultation history, patients, and performance metrics are all personal to them."

---

### Scene 3c — Main Dashboard [1:18–1:30]

**Main focus — screen:**
The main dashboard loads. Visible: today's patient queue (Scheduled 2, In Queue 2), the clinician's name (Dr Chin Pei Kang), and the "Assistant Impact Today" panel on the right — Time Saved, CPG Align, Citations, Referrals.

Cursor moves slowly across the queue, pausing on one patient card.

**Overlay card (bottom-left):**
> `Home — Today's queue + performance at a glance`

**Narration:**
> "The home screen gives the clinician their full day: who's waiting, who's in queue, and a live tally of how the AI assistant has impacted their practice today — time saved, CPG alignment rate, and evidence-backed citations."

---

### Scene 3d — Patient Dashboard [1:30–1:45]

**Main focus — screen:**
Click "My Patients" in the sidebar. The patient list loads — 18 patients total, "Follow-up Required (3)" tab visible. Click to expand one patient (UI 4 — 55-year-old with T2DM and Erectile Dysfunction). The expanded row shows:
- Comorbidities: Stable CAD, T2DM, Obesity, Erectile Dysfunction (new)
- Consultation history: 2 records, latest 09 Jun 2026
- Clinical notes panel: eGFR, HbA1c, chief complaint summary
- Current medications: Metformin 1g BD

Cursor hovers the "Latest" consultation record.

**Overlay card (bottom-left):**
> `My Patients — Full history, pre-loaded from last consultation`

**Narration:**
> "Every patient's record is persistent. Comorbidities, current medications, allergy flags, and consultation history are all pre-loaded — so the clinician walks in already informed, not starting from scratch."

---

### Scene 3e — Start Consultation [1:45–1:55]

**Main focus — screen:**
Click "Consultation" in the sidebar. The consultation wizard opens at Step 1 of 4 — "Data Input". A Patient Lookup box is centred on screen. Cursor moves to the IC field, types an IC number slowly (e.g. `600521-04-1834`). Click "Continue →".

**Overlay card (bottom-left):**
> `Step 1 — Patient Lookup: IC-matched record retrieval`

**Narration:**
> "Starting a consultation takes one step — enter the patient's IC number. The system retrieves their full record instantly."

---

### Scene 3f — Clinical Assessment Input [1:55–2:05]

**Main focus — screen:**
The full data input form loads. Left panel: demographics auto-filled (name, DOB, sex, allergies, comorbidities, current medications). Right panel: Vital signs form (BP, HR, RR, SpO₂, weight, height), Severity staging (optional), and Clinical notes (CC / HPI / PE fields).

Cursor moves slowly across each section, pausing briefly on:
1. The comorbidities chip list (already populated)
2. The vital signs fields (ready to fill)
3. The "rPPG scan" button — highlighted with a hover

Then cursor moves to the Clinical notes field, pauses on the "Record Consult" microphone button.

**Overlay card (bottom-left):**
> `Step 1 — Assessment: Patient context + vitals + clinical notes`

**Narration:**
> "The assessment form captures everything in one place. Patient context is pre-filled from their record. Vitals are entered manually — or captured in seconds with two built-in tools that keep the workflow seamless."

---

### Scene 3g — rPPG and STT Callout [2:05–2:10]

**Main focus — screen:**
Two quick close-up cuts (zoom-punch in post):

1. **rPPG button** — cursor hovers the "rPPG scan" button on the vitals panel. Hold 2 seconds. Tooltip: `Remote Photoplethysmography — contactless HR & SpO₂`.
2. **Record Consult button** — cursor hovers the microphone icon next to Clinical notes. Hold 2 seconds. Label: `Speech-to-Text — dictate CC, HPI, PE directly`.

**Overlay card (bottom-left):**
> `rPPG — contactless vitals   ·   STT — dictation to structured notes`

**Narration:**
> "The rPPG scanner reads heart rate and oxygen saturation from the camera — no contact required. The speech-to-text engine transcribes the clinician's dictation directly into structured clinical notes. Both tools eliminate manual entry so the doctor can stay focused on the patient."

---

## Part B — Agentic Pipeline Demo [2:10–3:30]

---

### Scene 4a — AI Reasoning Trace (Analysis Loading) [2:10–2:20]

**Main focus — screen:**
After clicking "Analyze assessment →" in Scene 3f, the screen transitions to the consultation pipeline view. The step indicator shows "Analysing..." (spinning icon between Data input and Diagnosis). The central panel shows the **AI Reasoning Trace** with 4 pipeline stages listed:

1. **DDx Analysis** — *Parses clinical notes to extract symptoms and rank candidate diagnoses*
2. **CPG Routing** — *Routes confirmed diagnoses to matching clinical practice guidelines (runs on Confirm)*
3. **Evidence Retrieval** — *Retrieves relevant clinical rules, recommendations, and evidence (runs on Confirm)*
4. **Plan Synthesis** — *Synthesises guideline-backed care recommendations and performs safety checks (runs on Confirm)*

All 4 stages are visible but only DDx Analysis is running (spinning). Patient header: `CHUA · 041206-10-1597 · 21 yrs · Male`. Footer: `Powered by Gemini 2.5 Flash · Evidence grounded in Malaysian CPGs`.

Cursor idles — let the loading state sit for 3 seconds so all pipeline stages are readable.

**Overlay card (bottom-left):**
> `Agentic Pipeline — 4-stage reasoning, transparent at every step`

**Narration:**
> "The moment the assessment is submitted, ClearPath begins a four-stage agentic pipeline — differential diagnosis analysis, CPG routing, evidence retrieval, and plan synthesis. Every stage is visible in real time. The clinician is never waiting on a black box."

---

### Scene 4b — Differential Diagnosis + ICD-11 Mapping [2:20–2:45]

**Main focus — screen:**
DDx Analysis completes. Screen lands on **Step 2 of 4 — Diagnosis**. Two panels visible:

**Left panel (AI Reasoning Trace):**
- 5 candidates, top: 5A11
- Extracted symptom query: *"Insidious onset erectile dysfunction, organic pattern, 6 months"*
- Condition hypotheses: Erectile dysfunction, CAD status post PCI, T2DM, Dyslipidaemia
- Regex-injected codes (CC-boost): 5A11, BB00
- CC priority codes: HA01.1 (clinician-named), 5A13.3 (clinician-named), BA86 (95%)
- Ranked: #1 5A11 T2DM (0.82), #2 HA01.1 Male erectile dysfunction (0.70), #3 5A13.3 (0.57), #4 BA5Z Coronary atherosclerosis (0.78), #5 5C80.0 Hypercholesterolaemia (0.72)

**Right panel (Differential Diagnosis — 5 candidates):**
Each card shows: name + ICD-11 code + confidence bar (green = High, orange = Moderate) + Off/Minor/Major toggle + "System suggests" chip.

Cursor moves slowly down the right panel, hovering each card 1–2 seconds. Then:
1. Zoom-in on card #1 — T2DM — confidence bar 0.82, "System suggests Major" chip
2. Cursor clicks "Major" on card #1
3. Cursor hovers card #2 — Male erectile dysfunction — override note visible: *"Override: HA01.1 better fits patient's complaint than MF41"*
4. Cursor clicks "Minor" on card #2

**Overlay card (bottom-left):**
> `DDx Analysis — ICD-11 mapped · Confidence ranked · Clinician confirms`

**Narration:**
> "The differential diagnosis layer extracts symptoms from the clinical notes, maps them to ICD-11 codes, and ranks each candidate by retrieval confidence. The clinician sees the AI's reasoning — extracted symptom queries, hypothesis generation, code injection logic — not just a final answer. They confirm or override each diagnosis before anything proceeds."

---

### Scene 4c — CPG Routing [2:45–3:00]

**Main focus — screen:**
After clicking "Confirm →", screen transitions to **"Generating Care Plan"**. Pipeline progress panel shows 4 stage cards:
- **CPG Routing** — ACTIVE (teal border): *"Routing 2 clinician-selected code(s); major=5A13.3"*
- Evidence Retrieval, Plan Synthesis, Safety Review — queued

Top counters: `2 CPG ROUTES` incrementing, `– CHUNKS` pending.

**Live Activity feed (bottom-left):**
- `CPG ROUTING · CC priority codes: HA01.1, 5A13.3 (clinician-named), BA86 (95%)`
- `CPG ROUTING · Regex-injected codes (fallback): 5A11, BB00`
- `CPG ROUTING · Condition hypotheses: Erectile dysfunction, CAD status post PCI, T2DM, Dyslipidaemia`

**"What Is Happening" panel (bottom-right):**
- Active Phase Stage 3: CPG Routing — ACTIVE
- CPG Registry Scanner v0.3
- 5A11 T2DM — ICD valid · Parent code resolved · Searching registry
- 5A13.3 Diabetes mellitus due to endocrinopathies — ICD valid · Parent code resolved · Searching registry
- Status: *"Querying Malaysian CPG database index..."*

Cursor idles on the "What Is Happening" panel — let the registry scan output sit for 5–6 seconds.

**Overlay card (bottom-left):**
> `CPG Routing — ICD-11 codes matched to governing Malaysian MOH guidelines`

**Narration:**
> "CPG Routing maps each confirmed diagnosis to its governing Malaysian Ministry of Health guideline. The system validates ICD codes, resolves parent hierarchies, and excludes CPGs that don't apply — for example, a female-only guideline is automatically excluded for a male patient. Only relevant, matched guidelines proceed."

---

### Scene 4d — Evidence Retrieval [3:00–3:10]

**Main focus — screen:**
CPG Routing card turns green. **Evidence Retrieval** card activates:
*"Retrieving guideline evidence... · Generating 7 targeted queries..."*

CPG Routes: `2`. Chunks counter increments from `–` upward.

**"What Is Happening" panel (bottom-right):**
- Active Phase Stage 4: Evidence Retrieval — ACTIVE
- `0 QUERIES RUN` → incrementing, `– CHUNKS FOUND` → incrementing, `>0.72 COSINE SIM`
- RAG Match Quality Index bar: Min Cutoff (0.72) — Mean Match (0.88) — Max Match (1.00), bar in optimal zone
- Retrieval Indexer ticking green: Cosine similarity index active · Filtering boilerplate paragraphs · Vectorising query formulations

**Live Activity feed (bottom-left):**
- `EVIDENCE RETRIEVAL · Generating 7 targeted queries...`
- `CPG ROUTING · T2-Diabetes-Mellitus(6th-Edition) — exact`
- `CPG ROUTING · Co-consideration 5A11 backed by 1 CPG (expected 2) — under_evidenced`

Cursor hovers the RAG Match Quality Index bar — hold 2 seconds.

**Overlay card (bottom-left):**
> `Evidence Retrieval — Hybrid RAG · Cosine similarity · Boilerplate filtered`

**Narration:**
> "Evidence retrieval fires seven targeted queries against the matched CPGs — not a single broad search, but a structured retrieval strategy. Each chunk is scored for cosine similarity; anything below the quality threshold is filtered out. The mean match score and retrieval quality index are shown live."

---

### Scene 4e — Recommended Care Plan + Safety Review [3:10–3:22]

**Main focus — screen:**
Screen lands on **Step 3 of 4 — Recommended Care Plan**. This is the most content-rich screen — allocate the most time here.

**Left panel:**
- Diagnoses: Diabetes mellitus due to endocrinopathies (5A13.3), T2DM (5A11)
- Allergies: None known
- AI Reasoning Trace: 112.2s · 2 ICD codes · 2 CPGs (cursor expands briefly)
- Unresolved Questions (6 — orange): 1 Medication Interaction, 5 Evidence Gaps

**Centre top — Safety banner (RED, critical):**
> `Safety concerns require acknowledgement — 1 Critical`
> `PDE-5 inhibitor + nitrates — severe hypotension interaction`
> `Consider: Ensure patient is not on any form of nitrate (including PRN) and counsel thoroughly on this absolute contraindication before initiating PDE-5 inhibitors. Consider a cardiology review to confirm no current or anticipated nitrate use.`

Buttons: **Replace** | **Keep + acknowledge risk** | **Remove from plan**

Cursor hovers the red safety banner — hold 3 seconds. Then zoom-in (post-edit) on the banner text. This is the visual centrepiece of the entire demo.

**Centre tabs — Overview (cursor scrolls slowly through each section, 2–3 seconds each):**

1. **Clinical Summary:**
   > *"21-year-old male with T2DM and BMI 31 presenting with organic-type erectile dysfunction for 6 months. Post-PCI 18 months ago, angina-free. Pattern consistent with vasculogenic aetiology. ED is a marker for potential CVD risk and warrants CHD screening per T2DM CPG."*

2. **Medication changes (3):**
   - Metformin 500mg OD orally, titrate to 1000mg BD — `A 1st-line` badge — START
   - SGLT2-i (e.g. dapagliflozin 10mg OD or empagliflozin 10mg OD) — START
   - PDE-5 inhibitor (e.g. sildenafil, tadalafil or vardenafil) — START

3. **Red Flags (4):**
   - Symptomatic hypoglycaemia
   - Chest pain or exertional dyspnoea
   - Severe hypotension with PDE-5i
   - Glycaemic deterioration

4. **Follow-up Plan:**
   - 4 WEEKS — reassess glycaemic control, BP, medication tolerability and PDE-5i response
   - 3 MONTHS — repeat HbA1c, lipid profile, renal function
   - 6 MONTHS — review IIEF-5 score, testosterone results, glycaemic target achievement
   - ANNUALLY — comprehensive complication screening (eyes, feet, DKD, CVD, dental)

Cursor clicks "Keep + acknowledge risk" — banner resolves, "I have reviewed these concerns and accept clinical responsibility" button activates.

**Overlay card (bottom-left):**
> `Care Plan — Safety-flagged · CPG-cited · Clinician sign-off required`

**Narration:**
> "The care plan arrives structured into five sections — a clinical summary, medication changes with evidence grades, care and monitoring instructions, red flags, and a follow-up timeline. But before the clinician can approve anything, the safety layer has already flagged a critical concern: PDE-5 inhibitors combined with nitrates risk severe hypotension. The system blocks sign-off until the clinician explicitly acknowledges it. The plan cannot be silently accepted."

---

### Scene 4f — Final Care Plan Document + Approval [3:22–3:30]

**Main focus — screen:**
After clicking "Confirm Care Plan", screen transitions to **Step 4 of 4 — Final Care Plan**. All four step indicators are green checkmarks. Document renders:

**Header:**
- ClearPath logo + `CLINIC · NO.12 JALAN BUKIT DAMANSARA, KL`
- `ENC-2026-058463 · 10 Jun 2026 · 17:34`
- Patient: CHUA · 21 y · Male | MRN: MRN-1597 | Provider: Chin Pei Kang · MMC—

**Document (cursor scrolls slowly):**
- **S — Subjective** (Patient-Reported History)
- **O — Objective**: BP 128/80 · HR 64 bpm · SpO₂ 98% · Temp 36.6°C · Weight 95kg · BMI 31 (red — above range)

**Right sidebar:**
- STATUS: `Ready for Final Approval`
- **"Approve Care Plan"** button (teal, prominent)
- DISTRIBUTE: Export PDF · Print copy · Pending upload · Email to Patient

Cursor hovers "Approve Care Plan" — hold 2 seconds — click.

**Overlay card (bottom-left):**
> `Final Care Plan — Approved · Saved · Ready to distribute`

**Narration:**
> "The final output is a SOAP-structured clinical document — complete with vitals, diagnoses, medications, and follow-up plan. One click approves and saves it to the patient record. It can be exported as PDF, printed, or emailed directly to the patient. The entire consultation, from data input to approved care plan, is fully auditable."

---

## Production Notes

### Key zoom-punch moments (flag all for post-editing)

**Part A:**
- Scene 3a: zoom in on the 4 stat counters — 30 CPGs, 248 codes, 5-stage, 100%
- Scene 3c: zoom in on "Assistant Impact Today" panel — Time Saved + CPG Align side by side
- Scene 3d: zoom in on the expanded patient comorbidity chips — especially "Erectile Dysfunction (new)"
- Scene 3d: zoom in on the Latest consultation record showing diagnosis + ICD tag
- Scene 3f: zoom in on the comorbidities chip list (pre-filled from record)
- Scene 3g: zoom-punch #1 — rPPG button with tooltip
- Scene 3g: zoom-punch #2 — Record Consult microphone icon

**Part B:**
- Scene 4b: zoom in on confidence bar + "System suggests Major" chip on T2DM card
- Scene 4b: zoom in on the override note on the Erectile Dysfunction card (orange text)
- Scene 4c: zoom in on the CPG Registry Scanner output showing ICD validation + exclusion logic
- Scene 4d: zoom in on the RAG Match Quality Index bar showing Mean Match 0.88
- Scene 4e: zoom in on the red safety banner — hold 3 seconds before acknowledging
- Scene 4e: zoom in on "A 1st-line" evidence badge on Metformin
- Scene 4f: zoom in on the BMI value (31, red — above range)

---

### Timing summary

| Scene | Content | Duration |
|---|---|---|
| **Part A** | | |
| 3a | Landing page | ~0:08 |
| 3b | Sign in | ~0:10 |
| 3c | Main dashboard | ~0:12 |
| 3d | Patient dashboard | ~0:15 |
| 3e | Start consultation — IC lookup | ~0:10 |
| 3f | Clinical assessment input form | ~0:10 |
| 3g | rPPG + STT callout (zoom-punch) | ~0:05 |
| *Part A subtotal* | | *~1:10* |
| **Part B** | | |
| 4a | AI Reasoning Trace loading | ~0:10 |
| 4b | DDx + ICD-11 mapping | ~0:25 |
| 4c | CPG Routing live activity | ~0:15 |
| 4d | Evidence Retrieval + RAG quality | ~0:10 |
| 4e | Care Plan + Safety Review | ~0:12 |
| 4f | Final document + Approve | ~0:08 |
| *Part B subtotal* | | *~1:20* |
| **Total** | | **~2:30** |

---

### Word count (narration pacing reference ~130 wpm)

| Scene | Words | Duration |
|---|---|---|
| 3a | ~30 | 0:08 |
| 3b | ~25 | 0:10 |
| 3c | ~35 | 0:12 |
| 3d | ~35 | 0:15 |
| 3e | ~20 | 0:10 |
| 3f | ~35 | 0:10 |
| 3g | ~45 | 0:05 |
| 4a | ~55 | 0:10 |
| 4b | ~80 | 0:25 |
| 4c | ~50 | 0:15 |
| 4d | ~50 | 0:10 |
| 4e | ~80 | 0:12 |
| 4f | ~45 | 0:08 |
| **Total** | **~585** | **~2:30** |

---

### Screen recording checklist
- [ ] Demo account (Dr Chin Pei Kang) pre-loaded and ready to log in instantly
- [ ] Landing page fully loaded before recording starts — no lazy-load flicker
- [ ] Sign-in fields pre-filled or typed very slowly
- [ ] Patient record UI 4 expanded and ready — do not hunt for it on camera
- [ ] IC number for Scene 3e ready to type: `600521-04-1834`
- [ ] Assessment form in Scene 3f shows a pre-loaded patient (comorbidities filled)
- [ ] rPPG tooltip visible in Scene 3g — test hover behaviour before recording
- [ ] Full run-through recorded first as master take before isolated scene re-records
- [ ] Safety banner (Scene 4e) — let the red colour sit before acknowledging; do not rush
- [ ] Care plan tabs (Scene 4e) — scroll through all: Overview, Medications, Red Flags, Follow-up
- [ ] Approval click (Scene 4f) — slow hover on the button before clicking

---

### Narration files for this segment
- [ ] `narration_seg3a.mp3` — Landing page
- [ ] `narration_seg3b.mp3` — Sign in
- [ ] `narration_seg3c.mp3` — Main dashboard
- [ ] `narration_seg3d.mp3` — Patient dashboard
- [ ] `narration_seg3e.mp3` — Start consultation
- [ ] `narration_seg3f.mp3` — Clinical assessment input
- [ ] `narration_seg3g.mp3` — rPPG and STT callout
- [ ] `narration_seg4a.mp3` — AI Reasoning Trace loading
- [ ] `narration_seg4b.mp3` — DDx + ICD mapping
- [ ] `narration_seg4c.mp3` — CPG Routing
- [ ] `narration_seg4d.mp3` — Evidence Retrieval
- [ ] `narration_seg4e.mp3` — Care Plan + Safety Review
- [ ] `narration_seg4f.mp3` — Final approval
