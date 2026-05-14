# MedRace — Implementation Plan
> **Handoff to:** Sonnet (implementing engineer)
> **Folder:** `SULAM/MedRace/` — standalone Vite + React app, do NOT modify anything outside this folder
> **Backend:** Calls existing `POST /chat/stream` endpoint on `http://localhost:8058` — same pattern as `cli.py`. Do NOT modify `cli.py` or any backend files.

---

## 1. What is MedRace?

**"MedRace — Human vs AI. Who finds the answer faster?"**

A split-screen interactive booth game for secondary school students. One student manually hunts through 10 CPG knowledge cards to find the answer. Another student types the same question into an AI chat box. A live timer runs for both sides. The goal is to viscerally demonstrate that grounded AI finds accurate, cited answers in seconds while manual search takes minutes.

**Teaching point:** The AI doesn't just "know" the answer — it retrieves it from the same real clinical guidelines shown on the cards. That's Retrieval-Augmented Generation (RAG).

---

## 2. App Name & Branding

| Element | Value |
|---------|-------|
| App name | **MedRace** |
| Tagline | *Human vs AI — who finds the answer faster?* |
| Left side label | 🧑 Manual Search |
| Right side label | 🤖 AI Search |
| Theme | Same blue + heath tokens as SULAM parent (`theme.css`) |
| Port | `5177` (dev) |

---

## 3. The 5 Question Bank

Questions are direct and factual. Each has one specific correct answer embedded in exactly one card. Distractors make other cards plausible so students can't just skim.

---

### Q1 — Salt Intake
> **"According to the World Health Organization, what is the maximum amount of salt an adult should eat per day?"**

- **Expected answer:** Less than **5 grams of salt per day** (equivalent to less than 2 g of sodium — about one teaspoon)
- **Why not obvious at a glance:** Card 1 contains multiple numbers (201 mmol, 66 mmol, 7.8/2.7 mmHg, 3.4–3.8 g sodium excretion in Malaysia) — student must read carefully to isolate the WHO recommendation
- **Source card:** Card 1 (Hypertension Section 4.2)

---

### Q2 — Exercise for Cholesterol
> **"How many minutes of moderate-intensity exercise per week does the clinical guideline recommend to help manage high cholesterol?"**

- **Expected answer:** At least **150 minutes** of moderate-intensity exercise per week (or 75 minutes of vigorous-intensity)
- **Why not obvious at a glance:** Card 2 lists five TLC components (diet, exercise, smoking, alcohol, weight) — the specific number is buried in the exercise bullet
- **Source card:** Card 2 (Dyslipidaemia Section 7.1 TLC)

---

### Q3 — Heart Failure Warning Sign
> **"A heart failure patient is weighing themselves every day at home. What specific weight change should make them call their doctor immediately?"**

- **Expected answer:** Weight gain of more than **2 kg in 3 days**
- **Why not obvious at a glance:** Card 3 contains a long list of self-care instructions (medication, diet, telemedicine, end-of-life planning) — the weight threshold is one sentence among many
- **Source card:** Card 3 (Heart Failure Section 8.1)

---

### Q4 — Statin Effectiveness
> **"By roughly how much can a high-intensity statin drug reduce a person's LDL (bad) cholesterol level?"**

- **Expected answer:** More than **50%** reduction in LDL-C
- **Why not obvious at a glance:** Card 4 lists different reduction percentages for high-intensity (>50%), moderate-intensity (30–50%), and also mentions TG and HDL effects — student must identify the high-intensity figure
- **Source card:** Card 4 (Dyslipidaemia Section 7.2.1.1)

---

### Q5 — Blood Pressure Target
> **"What is the target blood pressure that doctors aim for in adults under 80 years old who have hypertension?"**

- **Expected answer:** Systolic BP **less than 140 mmHg** AND Diastolic BP **less than 90 mmHg**
- **Why not obvious at a glance:** Card 5 also mentions targets for age ≥80 (<150/90) and high-risk groups (<130/80) — student must identify the right population group
- **Source card:** Card 5 (Hypertension Section 5.1c)

---

## 4. The 10 CPG Cards

Cards are shuffled randomly on-screen each game. Each card shows:
- **Front (face-down):** CPG name + section title + "Click to reveal"
- **Back (face-up):** The paragraph text

Cards 1–5 contain answers. Cards 6–10 are plausible distractors.

---

### Card 1 — Hypertension: Sodium Intake
**CPG:** CPG Management of Hypertension (5th Edition)
**Source file:** `markdown/Hypertension(5th Edition)/section-4-non-pharmacological-management-hypertension.md` — Section 4.2

**Paragraph text (copy verbatim):**
> High salt intake is associated with increased risk of stroke, stroke mortality, and coronary heart disease mortality. Reducing sodium intake significantly reduces blood pressure in adults. WHO recommends a reduction of sodium intake to <2 g/day or <5 g/day of salt (about one teaspoon of salt) in adults. A recent Cochrane review has shown that a reduction of sodium intake from a high average of 201 mmol/day (11.6g of salt) to an average level of 66 mmol/day (3.8g of salt), resulted in a decrease in BP of 7.8/2.7 mmHg in Asian people with hypertension. In Malaysia, the estimated mean sodium excretion of normotensive people was 3.4 to 3.8 g, equivalent to 8.7 to 9.5 g of salt intake per day. This exceeds the recommended salt intake and hence salt reduction is recommended for most people especially the hypertensive population.

**Answer hidden inside:** `<5 g/day of salt`

---

### Card 2 — Dyslipidaemia: Therapeutic Lifestyle Changes
**CPG:** CPG Management of Dyslipidaemia (6th Edition)
**Source file:** `markdown/Dyslipidaemia(6th-Edition)/section-7-1-tlc-dyslipidaemia.md` — Section 7.1 Introduction

**Paragraph text (copy verbatim):**
> Therapeutic lifestyle changes (TLC) are a critical component of health promotion and CV risk reduction efforts, both prior to and after commencement of lipid-lowering therapies. These measures should be promoted as a population-based strategy for the primary prevention of CVD. TLC refers to: adhering to healthy dietary patterns; regular exercise — ≥150 minutes of moderate intensity exercise per week or 75 minutes a week of vigorous-intensity exercise or an equivalent combination; avoidance of tobacco smoking; alcohol restriction; and maintenance of an ideal weight — BMI 20–23.5 kg/m² and waist circumference <90 cm (men), <80 cm (women).

**Answer hidden inside:** `≥150 minutes of moderate intensity exercise per week`

---

### Card 3 — Heart Failure: Self-Monitoring Warning Sign
**CPG:** CPG Management of Heart Failure (5th Edition)
**Source file:** `markdown/Heart-Failure(5th Edition)/section-8-non-pharmacological-heartfailure.md` — Section 8.1

**Paragraph text (copy verbatim):**
> HF patients and their family members should be educated on the definition, causes, signs, symptoms, and the progressive and relapsing nature of the disease, emphasizing self-care wherever possible. Patients and their family should be educated on self-care which includes maintenance (e.g., taking medication, exercising, and adhering to a healthy diet), monitoring (e.g., regular weighing), and management (e.g., changing diuretic dose in response to symptoms). They should recognize the changes in their signs and symptoms — a sudden weight gain of more than 2 kg in 3 days is a sign of worsening HF. They must also know when to contact their healthcare provider and understand the indication, dosing, side effects and drug interaction of each medication they are prescribed.

**Answer hidden inside:** `more than 2 kg in 3 days`

---

### Card 4 — Dyslipidaemia: Statin LDL Reduction
**CPG:** CPG Management of Dyslipidaemia (6th Edition)
**Source file:** `markdown/Dyslipidaemia(6th-Edition)/section-7-2-drugs-dyslipidaemia.md` — Section 7.2.1.1

**Paragraph text (copy verbatim):**
> The degree of LDL-C reduction seen with the different statins is dose-dependent. A high intensity statin (i.e. atorvastatin 40–80 mg, rosuvastatin 20 mg) can, on average, reduce LDL-C by >50%. A moderate-intensity statin reduces LDL-C by about 30–50%. Statins reduce TG levels by 10–20% from baseline values. High intensity statins have moderate effect in lowering TG and in elevating HDL-C. Statins also have other pleiotropic effects — anti-inflammatory and antioxidant effects — that are potentially relevant for the prevention of CVD.

**Answer hidden inside:** `reduce LDL-C by >50%`

---

### Card 5 — Hypertension: Blood Pressure Targets
**CPG:** CPG Management of Hypertension (5th Edition)
**Source file:** `markdown/Hypertension(5th Edition)/section-5-pharmacological-management-hypertension.md` — Section 5.1c

**Paragraph text (copy verbatim):**
> Efforts must be made to achieve target BP. For patients <80 years old, the target SBP should be <140 mmHg and DBP <90 mmHg. For patients aged 80 years and above, aim for a target of <150/90 mmHg. For high/very high risk individuals the target is <130/80 mmHg. If BP is still >140/90 mmHg with three drugs, including a diuretic at optimal tolerated doses, there is a need to exclude medication non-adherence and isolated office hypertension. After excluding these causes of uncontrolled hypertension, the patient is then defined as having resistant hypertension.

**Answer hidden inside:** `target SBP should be <140 mmHg and DBP <90 mmHg`

---

### Card 6 — DISTRACTOR: Stroke Risk Factors in Malaysia
**CPG:** CPG Management of Ischaemic Stroke (3rd Edition)
**Source file:** `markdown/Ischaemic-Stroke(3rd Edition)/section-5-prevention-of-stroke-ischaemic.md` — Section 5.1.1

**Paragraph text (copy verbatim):**
> Data from the National Stroke Registry showed that first ever strokes contributed to about 79.2% of all stroke cases in Malaysia, while 20.8% were due to recurrent strokes. Top modifiable risk factors associated with first ever strokes among Malaysians were hypertension (69.9%), diabetes mellitus (41.4%), smoking (26.3%), hyperlipidaemia (24.4%), family history of stroke (5.8%), ischaemic heart disease and atrial fibrillation (3.4%). The INTERSTROKE study identified ten modifiable risk factors which accounted for 90% of population-adjustable risk of stroke, including hypertension, diabetes, hyperlipidaemia, waist-hip-ratio, poor diet, smoking, alcohol, cardiac cause, apo-lipoprotein levels and psychosocial factors.

**Distractor purpose:** Contains percentages and risk factors — students looking for a "number answer" may read this first, but it doesn't answer any question.

---

### Card 7 — DISTRACTOR: What is Heart Failure?
**CPG:** CPG Management of Heart Failure (5th Edition)
**Source file:** `markdown/Heart-Failure(5th Edition)/section-2-definition-heartfailure.md` — Section 2

**Paragraph text (copy verbatim):**
> Heart failure (HF) is a clinical syndrome due to any structural or physiological abnormality of the heart resulting in its inability to meet the metabolic demands of the body, or its ability to do so only at higher-than-normal filling pressures. Patients may have typical symptoms such as breathlessness, ankle swelling and fatigue, and signs such as elevated jugular venous pressure, ankle oedema, pulmonary crackles and displaced apex beat. Most commonly, HF is due to myocardial dysfunction — either systolic, diastolic, or both. However, pathology of the valves, pericardium, and endocardium, and abnormalities of heart rhythm and conduction can also cause HF.

**Distractor purpose:** Conceptual definition — no specific numeric answer to any question.

---

### Card 8 — DISTRACTOR: Atrial Fibrillation Stroke Risk Score
**CPG:** CPG Management of Atrial Fibrillation (2012)
**Source file:** `markdown/Atrial-Fibrillation(2012)/section-6-thromboembolism-prevention-af.md` — Section 6.1

**Paragraph text (copy verbatim):**
> The CHADS₂ stroke risk stratification scheme should be used as an initial, rapid, and easy-to-remember means of assessing stroke risk. The CHADS₂ score is based on a point system in which 2 points are assigned for a history of stroke or TIA and 1 point each is assigned for age >75 years, a history of hypertension, diabetes, or recent cardiac failure. In patients with a CHADS₂ score ≥2, chronic oral anticoagulant therapy with a VKA is recommended to achieve an INR target of 2.5 (range 2.0–3.0), unless contraindicated. Patients aged less than 60 years with 'lone AF' carry a very low cumulative stroke risk, estimated to be 1.3% over 15 years.

**Distractor purpose:** Contains numbers (2 points, 1 point, INR 2.5, 1.3%) — looks like it might contain an answer but doesn't match any question.

---

### Card 9 — DISTRACTOR: Heart Failure Symptoms
**CPG:** CPG Management of Heart Failure (5th Edition)
**Source file:** `markdown/Heart-Failure(5th Edition)/section-6-diagnosis-heartfailure.md` — Section 6.1

**Paragraph text (copy verbatim):**
> Breathlessness with orthopnea, paroxysmal nocturnal dyspnea, reduced exercise tolerance and ankle swelling are the characteristic symptoms of heart failure. Signs which are more specific for HF are an elevated jugular venous pulse (JVP) and a third heart sound. These signs are associated with adverse outcomes in patients with HF and asymptomatic LV dysfunction. The presence of a raised JVP, a positive jugulo-venous reflux and hepatomegaly generally indicate a raised right atrial pressure of >8 mmHg. A raised JVP has a good sensitivity (70%) and specificity (79%) of left-sided congestion.

**Distractor purpose:** Plausible distractor for Q3 (HF warning sign) — talks about HF but describes symptoms on examination, not the self-monitoring weight threshold.

---

### Card 10 — DISTRACTOR: Healthy Diet for Cholesterol
**CPG:** CPG Management of Dyslipidaemia (6th Edition)
**Source file:** `markdown/Dyslipidaemia(6th-Edition)/section-7-1-tlc-dyslipidaemia.md` — Section 7.1.1 (MNT)

**Paragraph text (copy verbatim):**
> Medical Nutrition Therapy (MNT) aims at optimizing lipid levels while maintaining a balanced diet, weight management (5–10% weight loss for overweight individuals), and empowering behavioural changes. Studies have shown that MNT by a trained dietitian with multiple visits over six to twelve weeks can result in reduction in TC by 7% to 21%, LDL-C by 7% to 22% and TG by 11% to 31%. A healthy diet consists of primarily fruits and vegetables; foods made with whole grains; healthy sources of protein mostly plant-based such as tofu, beans, lentils, and legumes; fish and seafood — eating ≥2 fish meals per week is beneficial; and liquid plant oils. The Malaysian Healthy Plate guideline recommends the #QuarterQuarterHalf diet: a quarter of the plate being carbohydrates, a quarter being protein, and half being fruits and vegetables.

**Distractor purpose:** Plausible distractor for Q2 (exercise minutes) and Q4 (statin %) — it's from the same Dyslipidaemia CPG but covers diet not exercise/drugs.

---

## 5. Backend Integration — Mimicking cli.py

`cli.py` sends to `POST /chat/stream`. The MedRace AI panel does the same:

```js
// src/lib/medRaceApi.js
const BASE = import.meta.env.VITE_CLINICAL_API_URL || 'http://localhost:8058';

export async function streamAIAnswer(question, onText, onTools) {
  const response = await fetch(`${BASE}/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message: question,
      session_id: null,
      user_id: 'medrace_player',
      search_type: 'hybrid',
    }),
  });

  if (!response.ok) throw new Error(`API ${response.status}`);

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop();
    for (const line of lines) {
      if (!line.startsWith('data: ')) continue;
      try {
        const data = JSON.parse(line.slice(6));
        if (data.type === 'text')  onText(data.content || '');
        if (data.type === 'tools') onTools(data.tools || []);
        if (data.type === 'end')   return;
      } catch { continue; }
    }
  }
}
```

---

## 6. Directory Layout

```
SULAM/MedRace/
├── IMPLEMENTATION.md       ← this file
├── package.json
├── vite.config.js
├── index.html
├── .env.example            ← VITE_CLINICAL_API_URL=http://localhost:8058
└── src/
    ├── main.jsx
    ├── App.jsx             ← game state machine: lobby → playing → results
    ├── index.css           ← imports from ../src/theme.css (or copy tokens)
    ├── data/
    │   ├── questions.js    ← 5 questions with id, text, expectedAnswer, sourceCardId
    │   └── cards.js        ← 10 cards with id, cpg, sectionTitle, paragraph, isAnswerCard
    ├── lib/
    │   └── medRaceApi.js   ← streamAIAnswer() as above
    └── components/
        ├── Lobby.jsx            ← question selector + "Start Race" button
        ├── RaceScreen.jsx       ← split layout orchestrator
        ├── ManualSide.jsx       ← left: card grid + answer input + timer
        ├── CPGCard.jsx          ← flippable card (front = CPG name, back = paragraph)
        ├── AISide.jsx           ← right: chat bubble + streaming text + tools badge
        └── ResultsScreen.jsx    ← side-by-side comparison: times, answers, AI source
```

---

## 7. Game State Machine

```
LOBBY  →  (host picks question + clicks Start)  →  RACING
RACING →  (either side submits answer OR timer hits 3 min)  →  RESULTS
RESULTS → (Reset button)  →  LOBBY
```

State shape (in `App.jsx`):
```js
{
  phase: 'lobby' | 'racing' | 'results',
  activeQuestion: null | { id, text, expectedAnswer, sourceCardId },
  manualState: {
    flippedCards: Set<cardId>,
    answer: '',
    submittedAt: null,      // ms since race start
    submitted: false,
  },
  aiState: {
    answer: '',             // accumulated text chunks
    toolsUsed: [],
    completedAt: null,      // ms since race start
    isStreaming: false,
    error: null,
  },
  startTime: null,          // Date.now() when race started
}
```

---

## 8. Implementation Steps (in order)

### Step 1 — Scaffold
`package.json`: react, react-dom, vite, @vitejs/plugin-react, lucide-react. No Tailwind, no Supabase.
Copy `../src/theme.css` import or duplicate the CSS tokens into `src/index.css`.

### Step 2 — Data files
Paste all 5 questions into `src/data/questions.js` and all 10 card paragraphs into `src/data/cards.js` exactly as written in §3 and §4. Shuffle card order randomly at runtime using `[...CARDS].sort(() => Math.random() - 0.5)`.

### Step 3 — API layer
Write `src/lib/medRaceApi.js` exactly as shown in §5.

### Step 4 — Lobby screen
- Show MedRace logo + tagline
- 5 question buttons — clicking one highlights it as selected
- "Start Race" button (disabled until a question is chosen)
- Brief explanation: "Left player: find the answer in the cards. Right player: type the question into the AI."

### Step 5 — RaceScreen layout
- Full-height split: left 50% (`ManualSide`) + right 50% (`AISide`)
- Top bar: question text (large, prominent) + elapsed timer (counts up, `mm:ss`)
- Divider line with "VS" badge in the middle

### Step 6 — ManualSide (left)
- 2×5 grid of `CPGCard` components (shuffled on each game start)
- Each `CPGCard`:
  - Face-down: shows CPG name + section title, cursor pointer, "Click to reveal"
  - On click: flips with CSS 3D transform (rotateY 0→180deg, 0.4s ease) to reveal paragraph text
  - Multiple cards can be open simultaneously
  - Flipped cards stay open (no re-flip)
- Below the grid: textarea "Your answer:" + "Submit Answer" button
- On submit: record timestamp, freeze the manual side, show green "✓ Submitted" banner

### Step 7 — AISide (right)
- On race start: automatically fires `streamAIAnswer(question.text, onText, onTools)` — no typing needed by the right-side player (the AI answers autonomously)
- Show animated "AI is searching…" with a pulsing dot while streaming
- Stream text appears in a chat bubble with a blinking cursor (like `ThinkingBox` in SULAM)
- When stream ends: show tools-used badges (e.g., "🔍 vector_search", "🕸 knowledge_graph") and record completion timestamp
- If backend unreachable: show friendly inline error "Backend offline — start the server on port 8058"

### Step 8 — ResultsScreen
Two columns, side by side:

| Left — Human | Right — AI |
|---|---|
| 🧑 Manual Search | 🤖 AI Search |
| Time taken: `mm:ss` | Time taken: `mm:ss` (or "still searching") |
| Their submitted answer | Full AI response |
| — | Tools used (chips) |
| — | "Source: found in CPG guidelines" |

Below both columns: show the **expected answer** highlighted in green, and which card contained it (name + section title).

Add a prominent message like: *"The AI found the answer in X seconds using RAG — retrieving from the same guidelines on these cards."*

"Play Again" button → back to Lobby.

### Step 9 — Styling notes
- Left side background: `var(--surface-soft)` (light)
- Right side background: `#0f1520` (dark, like GraphView) — creates a clear Human vs AI visual contrast
- Question bar: `var(--sidebar)` dark with white text
- Timer: monospace, large, primary colour when running, green when a side completes, yellow after 2 min
- Card flip: pure CSS `perspective: 800px; transform-style: preserve-3d`
- "VS" divider badge: `var(--primary)` pill

### Step 10 — README.md
How to start: same backend (port 8058), `npm install`, `npm run dev` (port 5177). Note the AI side needs the backend running; the card side works offline.

---

## 9. Definition of Done

- [ ] `npm run build` passes with zero errors
- [ ] Lobby shows 5 questions; picking one and clicking Start opens the race
- [ ] Left side: all 10 cards flip on click and reveal paragraphs; answer submission records time
- [ ] Right side: AI auto-starts, streams response, records completion time when done
- [ ] Results screen shows both times, both answers, expected answer highlighted, AI tools used
- [ ] Backend offline → AI side shows friendly error, manual side still fully functional
- [ ] No files outside `SULAM/MedRace/` are modified
- [ ] `SULAM/` main app still starts independently on its own port without any changes

---

## 10. Quick Reference — Endpoint Spec

```
POST http://localhost:8058/chat/stream
Content-Type: application/json

Body:
{
  "message": "<question string>",
  "session_id": null,
  "user_id": "medrace_player",
  "search_type": "hybrid"
}

SSE Response events (line format: "data: <json>\n"):
  { "type": "session", "session_id": "..." }
  { "type": "text",    "content": "..." }      ← stream these
  { "type": "tools",   "tools": [...] }         ← display after
  { "type": "end" }                             ← stream done
  { "type": "error",   "content": "..." }
```
