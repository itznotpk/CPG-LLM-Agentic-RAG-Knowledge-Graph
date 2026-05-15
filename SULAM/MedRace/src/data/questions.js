export const QUESTIONS = [

  // ── HYPERTENSION (5) ─────────────────────────────────────────────────────

  {
    id: 'q1',
    text: 'According to the World Health Organization, what is the maximum amount of salt an adult should eat per day?',
    hint: 'Look in the Hypertension guideline under sodium intake.',
    expectedAnswer: 'Less than 5 grams of salt per day (about one teaspoon), which equals less than 2 g of sodium.',
    sourceCardId: 'c1',
    topic: 'Hypertension — Sodium Intake',
    options: [
      { id: 'A', text: 'Less than 10 grams per day' },
      { id: 'B', text: 'Less than 5 grams per day (~1 teaspoon)' },
      { id: 'C', text: 'Less than 2 grams per day' },
      { id: 'D', text: 'Less than 8 grams per day' },
    ],
    correctOption: 'B',
    cards: [
      { id: 'q1c1', cpg: 'CPG Hypertension (5th Ed.)', section: 'Section 4.2 — Sodium Intake', summary: 'WHO recommends adults eat less than 5 g of salt per day (about one teaspoon), equal to less than 2 g of sodium.' },
      { id: 'q1c2', cpg: 'CPG Hypertension (5th Ed.)', section: 'Section 4.2 — Blood Pressure Effects', summary: 'Reducing sodium intake significantly lowers blood pressure. High salt is linked to stroke and heart disease mortality.' },
      { id: 'q1c3', cpg: 'CPG Stroke (3rd Ed.)', section: 'Section 5.1 — Risk Factors', summary: 'Hypertension is the top modifiable stroke risk factor in Malaysia, affecting 69.9% of first-ever stroke patients.' },
      { id: 'q1c4', cpg: 'CPG Hypertension (5th Ed.)', section: 'Section 4 — Lifestyle Changes', summary: 'Malaysians consume an estimated 8.7–9.5 g of salt per day on average, well above the recommended limit.' },
    ],
  },

  {
    id: 'q5',
    text: 'What is the target blood pressure that doctors aim for in adults under 80 years old who have hypertension?',
    hint: 'Look in the Hypertension guideline under target BP.',
    expectedAnswer: 'Target SBP (systolic) should be less than 140 mmHg and DBP (diastolic) less than 90 mmHg.',
    sourceCardId: 'c5',
    topic: 'Hypertension — BP Targets',
    options: [
      { id: 'A', text: 'SBP < 160 mmHg and DBP < 100 mmHg' },
      { id: 'B', text: 'SBP < 130 mmHg and DBP < 80 mmHg' },
      { id: 'C', text: 'SBP < 140 mmHg and DBP < 90 mmHg' },
      { id: 'D', text: 'SBP < 120 mmHg and DBP < 70 mmHg' },
    ],
    correctOption: 'C',
    cards: [
      { id: 'q5c1', cpg: 'CPG Hypertension (5th Ed.)', section: 'Section 5.1c — BP Targets', summary: 'For patients under 80 years old, the target is SBP below 140 mmHg and DBP below 90 mmHg.' },
      { id: 'q5c2', cpg: 'CPG Hypertension (5th Ed.)', section: 'Section 5.1c — Elderly Targets', summary: 'For patients aged 80 and above, the target is slightly higher: below 150/90 mmHg.' },
      { id: 'q5c3', cpg: 'CPG Hypertension (5th Ed.)', section: 'Section 5.1c — High Risk', summary: 'High or very high risk patients have a tighter target of below 130/80 mmHg.' },
      { id: 'q5c4', cpg: 'CPG Hypertension (5th Ed.)', section: 'Section 5.1c — Resistant Hypertension', summary: 'If BP stays above 140/90 mmHg on three drugs including a diuretic, the patient may have resistant hypertension.' },
    ],
  },

  {
    id: 'q6',
    text: 'For patients aged 80 years and above with hypertension, what is the recommended target blood pressure?',
    hint: 'Look in the Hypertension guideline under target BP for the elderly.',
    expectedAnswer: 'For patients aged 80 and above, the target blood pressure is below 150/90 mmHg.',
    sourceCardId: 'c5',
    topic: 'Hypertension — Elderly BP Target',
    options: [
      { id: 'A', text: 'Below 120/80 mmHg' },
      { id: 'B', text: 'Below 130/80 mmHg' },
      { id: 'C', text: 'Below 140/90 mmHg' },
      { id: 'D', text: 'Below 150/90 mmHg' },
    ],
    correctOption: 'D',
    cards: [
      { id: 'q6c1', cpg: 'CPG Hypertension (5th Ed.)', section: 'Section 5.1c — Elderly Targets', summary: 'For patients aged 80 and above, the recommended BP target is below 150/90 mmHg.' },
      { id: 'q6c2', cpg: 'CPG Hypertension (5th Ed.)', section: 'Section 5.1c — Under 80 Targets', summary: 'Patients under 80 have a stricter target of below 140/90 mmHg.' },
      { id: 'q6c3', cpg: 'CPG Hypertension (5th Ed.)', section: 'Section 5.1c — High Risk Target', summary: 'High or very high cardiovascular risk patients aim for below 130/80 mmHg regardless of age.' },
      { id: 'q6c4', cpg: 'CPG Hypertension (5th Ed.)', section: 'Section 4 — Lifestyle', summary: 'Lifestyle changes such as reduced salt and regular exercise are part of BP management at any age.' },
    ],
  },

  {
    id: 'q7',
    text: 'Which of the following is NOT listed as a recommended lifestyle change for managing hypertension in the CPG?',
    hint: 'Look in the Hypertension guideline lifestyle modification section.',
    expectedAnswer: 'Taking vitamin supplements is not a recommended lifestyle change. The guideline recommends reducing salt, exercising, quitting smoking, limiting alcohol, and maintaining healthy weight.',
    sourceCardId: 'c1',
    topic: 'Hypertension — Lifestyle Changes',
    options: [
      { id: 'A', text: 'Reducing salt intake to less than 5 g per day' },
      { id: 'B', text: 'Regular moderate-intensity physical activity' },
      { id: 'C', text: 'Taking daily vitamin supplements' },
      { id: 'D', text: 'Limiting alcohol consumption' },
    ],
    correctOption: 'C',
    cards: [
      { id: 'q7c1', cpg: 'CPG Hypertension (5th Ed.)', section: 'Section 4 — Non-Pharmacological Treatment', summary: 'Recommended lifestyle changes include reducing salt, exercising regularly, quitting smoking, and limiting alcohol.' },
      { id: 'q7c2', cpg: 'CPG Hypertension (5th Ed.)', section: 'Section 4.2 — Sodium Reduction', summary: 'Reducing sodium to under 5 g/day of salt is strongly recommended to lower blood pressure.' },
      { id: 'q7c3', cpg: 'CPG Dyslipidaemia (6th Ed.)', section: 'Section 7.1 — Lifestyle Changes', summary: 'Lifestyle changes for CV risk reduction include diet, exercise, and avoiding tobacco — no vitamin supplement recommendation.' },
      { id: 'q7c4', cpg: 'CPG Hypertension (5th Ed.)', section: 'Section 4.3 — Alcohol', summary: 'Excessive alcohol intake raises blood pressure; the guideline advises restriction as part of lifestyle management.' },
    ],
  },

  {
    id: 'q8',
    text: 'A patient with hypertension remains above 140/90 mmHg despite taking three drugs including a diuretic at optimal doses. What is this condition called?',
    hint: 'Look in the Hypertension guideline under uncontrolled BP.',
    expectedAnswer: 'This is defined as resistant hypertension, after excluding medication non-adherence and isolated office hypertension.',
    sourceCardId: 'c5',
    topic: 'Hypertension — Resistant Hypertension',
    options: [
      { id: 'A', text: 'Secondary hypertension' },
      { id: 'B', text: 'Malignant hypertension' },
      { id: 'C', text: 'Resistant hypertension' },
      { id: 'D', text: 'Labile hypertension' },
    ],
    correctOption: 'C',
    cards: [
      { id: 'q8c1', cpg: 'CPG Hypertension (5th Ed.)', section: 'Section 5.1c — Resistant Hypertension', summary: 'BP above 140/90 mmHg on three drugs including a diuretic at optimal doses defines resistant hypertension.' },
      { id: 'q8c2', cpg: 'CPG Hypertension (5th Ed.)', section: 'Section 5.1c — Exclusions', summary: 'Before labelling resistant hypertension, exclude medication non-adherence and isolated office (white-coat) hypertension.' },
      { id: 'q8c3', cpg: 'CPG Hypertension (5th Ed.)', section: 'Section 5.1c — BP Targets', summary: 'Standard target for under-80 patients is below 140/90 mmHg; failure to reach this on adequate therapy is a clinical red flag.' },
      { id: 'q8c4', cpg: 'CPG Stroke (3rd Ed.)', section: 'Section 5.1 — Risk Factors', summary: 'Uncontrolled hypertension is the leading risk factor for stroke in Malaysia, making BP control critical.' },
    ],
  },

  // ── DYSLIPIDAEMIA (5) ────────────────────────────────────────────────────

  {
    id: 'q2',
    text: 'How many minutes of moderate-intensity exercise per week does the clinical guideline recommend to help manage high cholesterol?',
    hint: 'Look in the Dyslipidaemia guideline under lifestyle changes.',
    expectedAnswer: 'At least 150 minutes of moderate-intensity exercise per week (or 75 minutes of vigorous-intensity).',
    sourceCardId: 'c2',
    topic: 'Dyslipidaemia — Exercise',
    options: [
      { id: 'A', text: 'At least 60 minutes per week' },
      { id: 'B', text: 'At least 90 minutes per week' },
      { id: 'C', text: 'At least 150 minutes per week' },
      { id: 'D', text: 'At least 300 minutes per week' },
    ],
    correctOption: 'C',
    cards: [
      { id: 'q2c1', cpg: 'CPG Dyslipidaemia (6th Ed.)', section: 'Section 7.1 — Lifestyle Changes', summary: 'Guidelines recommend at least 150 minutes of moderate-intensity exercise per week, or 75 minutes of vigorous exercise.' },
      { id: 'q2c2', cpg: 'CPG Dyslipidaemia (6th Ed.)', section: 'Section 7.1.1 — Nutrition Therapy', summary: 'A healthy diet with fruits, vegetables, whole grains, and at least 2 fish meals per week helps improve cholesterol levels.' },
      { id: 'q2c3', cpg: 'CPG Dyslipidaemia (6th Ed.)', section: 'Section 7.1 — Weight & Smoking', summary: 'Therapeutic lifestyle changes also include avoiding tobacco, limiting alcohol, and maintaining a healthy body weight.' },
      { id: 'q2c4', cpg: 'CPG Dyslipidaemia (6th Ed.)', section: 'Section 7.1.1 — Weight Management', summary: 'A 5–10% weight loss in overweight individuals can meaningfully reduce total cholesterol and LDL levels.' },
    ],
  },

  {
    id: 'q4',
    text: "By roughly how much percentage can a high-intensity statin drug reduce a person's LDL (bad) cholesterol level?",
    hint: 'Look in the Dyslipidaemia guideline under statin effects.',
    expectedAnswer: 'A high-intensity statin can reduce LDL-C by more than 50% on average.',
    sourceCardId: 'c4',
    topic: 'Dyslipidaemia — Statins',
    options: [
      { id: 'A', text: 'More than 20%' },
      { id: 'B', text: 'More than 30%' },
      { id: 'C', text: 'More than 50%' },
      { id: 'D', text: 'More than 70%' },
    ],
    correctOption: 'C',
    cards: [
      { id: 'q4c1', cpg: 'CPG Dyslipidaemia (6th Ed.)', section: 'Section 7.2.1 — Statin Effects', summary: 'High-intensity statins (e.g. atorvastatin 40–80 mg) can reduce LDL cholesterol by more than 50% on average.' },
      { id: 'q4c2', cpg: 'CPG Dyslipidaemia (6th Ed.)', section: 'Section 7.2.1 — Statin Intensity', summary: 'Moderate-intensity statins reduce LDL by 30–50%. The reduction is dose-dependent across all statin types.' },
      { id: 'q4c3', cpg: 'CPG Dyslipidaemia (6th Ed.)', section: 'Section 7.2.1 — Other Effects', summary: 'Statins also lower triglycerides by 10–20% and have anti-inflammatory effects that help prevent cardiovascular disease.' },
      { id: 'q4c4', cpg: 'CPG Dyslipidaemia (6th Ed.)', section: 'Section 7.1 — Treatment Goals', summary: 'Lipid-lowering therapy is used alongside lifestyle changes, not as a replacement. Both are needed for best outcomes.' },
    ],
  },

  {
    id: 'q9',
    text: 'By how much can Medical Nutrition Therapy (MNT) reduce LDL cholesterol when delivered by a trained dietitian over 6–12 weeks?',
    hint: 'Look in the Dyslipidaemia guideline under Medical Nutrition Therapy.',
    expectedAnswer: 'MNT can reduce LDL-C by 7–22% and total cholesterol by 7–21% over 6–12 weeks.',
    sourceCardId: 'c4',
    topic: 'Dyslipidaemia — Nutrition Therapy',
    options: [
      { id: 'A', text: 'LDL reduced by 1–5%' },
      { id: 'B', text: 'LDL reduced by 7–22%' },
      { id: 'C', text: 'LDL reduced by 25–40%' },
      { id: 'D', text: 'LDL reduced by 50–60%' },
    ],
    correctOption: 'B',
    cards: [
      { id: 'q9c1', cpg: 'CPG Dyslipidaemia (6th Ed.)', section: 'Section 7.1.1 — Medical Nutrition Therapy', summary: 'MNT by a trained dietitian over 6–12 weeks can reduce LDL-C by 7–22% and total cholesterol by 7–21%.' },
      { id: 'q9c2', cpg: 'CPG Dyslipidaemia (6th Ed.)', section: 'Section 7.1.1 — Healthy Diet', summary: 'A healthy diet includes primarily fruits, vegetables, whole grains, plant-based proteins, fish, and liquid plant oils.' },
      { id: 'q9c3', cpg: 'CPG Dyslipidaemia (6th Ed.)', section: 'Section 7.1.1 — Malaysian Plate', summary: 'The Malaysian Healthy Plate recommends the QuarterQuarterHalf diet: ¼ carbs, ¼ protein, ½ fruits and vegetables.' },
      { id: 'q9c4', cpg: 'CPG Dyslipidaemia (6th Ed.)', section: 'Section 7.1 — Weight Management', summary: 'A 5–10% weight reduction in overweight patients also improves lipid levels alongside dietary changes.' },
    ],
  },

  {
    id: 'q10',
    text: 'A moderate-intensity statin reduces LDL cholesterol by approximately what range?',
    hint: 'Look in the Dyslipidaemia guideline under statin intensity classifications.',
    expectedAnswer: 'A moderate-intensity statin reduces LDL-C by about 30–50%.',
    sourceCardId: 'c4',
    topic: 'Dyslipidaemia — Statin Intensity',
    options: [
      { id: 'A', text: 'Less than 10%' },
      { id: 'B', text: '10–30%' },
      { id: 'C', text: '30–50%' },
      { id: 'D', text: 'More than 50%' },
    ],
    correctOption: 'C',
    cards: [
      { id: 'q10c1', cpg: 'CPG Dyslipidaemia (6th Ed.)', section: 'Section 7.2.1 — Statin Intensity', summary: 'Moderate-intensity statins reduce LDL-C by about 30–50%. High-intensity statins reduce it by more than 50%.' },
      { id: 'q10c2', cpg: 'CPG Dyslipidaemia (6th Ed.)', section: 'Section 7.2.1 — Dose Dependence', summary: 'LDL reduction from statins is dose-dependent — higher doses of the same statin give greater LDL lowering.' },
      { id: 'q10c3', cpg: 'CPG Dyslipidaemia (6th Ed.)', section: 'Section 7.2.1 — Triglycerides & HDL', summary: 'Statins also reduce triglycerides by 10–20% and have a moderate effect on raising HDL (good) cholesterol.' },
      { id: 'q10c4', cpg: 'CPG Dyslipidaemia (6th Ed.)', section: 'Section 7.1 — Lifestyle First', summary: 'Lifestyle changes should be promoted before and alongside statin therapy as part of comprehensive CV risk reduction.' },
    ],
  },

  {
    id: 'q11',
    text: 'The Malaysian Healthy Plate recommends the "QuarterQuarterHalf" diet. What does each portion represent?',
    hint: 'Look in the Dyslipidaemia guideline under Medical Nutrition Therapy.',
    expectedAnswer: 'A quarter carbohydrates, a quarter protein, and half fruits and vegetables.',
    sourceCardId: 'c4',
    topic: 'Dyslipidaemia — Healthy Plate',
    options: [
      { id: 'A', text: '½ carbs, ¼ protein, ¼ vegetables' },
      { id: 'B', text: '¼ carbs, ¼ protein, ½ fruits & vegetables' },
      { id: 'C', text: '¼ carbs, ½ protein, ¼ fruits' },
      { id: 'D', text: '⅓ carbs, ⅓ protein, ⅓ vegetables' },
    ],
    correctOption: 'B',
    cards: [
      { id: 'q11c1', cpg: 'CPG Dyslipidaemia (6th Ed.)', section: 'Section 7.1.1 — Malaysian Healthy Plate', summary: 'The Malaysian Healthy Plate guideline recommends: ¼ carbohydrates, ¼ protein, ½ fruits and vegetables.' },
      { id: 'q11c2', cpg: 'CPG Dyslipidaemia (6th Ed.)', section: 'Section 7.1.1 — Protein Sources', summary: 'Healthy protein sources are mostly plant-based — tofu, beans, legumes — plus fish and seafood at least twice a week.' },
      { id: 'q11c3', cpg: 'CPG Dyslipidaemia (6th Ed.)', section: 'Section 7.1.1 — Healthy Fats', summary: 'Liquid plant oils (e.g. olive, canola) are preferred over saturated fats as part of a heart-healthy diet.' },
      { id: 'q11c4', cpg: 'CPG Dyslipidaemia (6th Ed.)', section: 'Section 7.1 — MNT Goals', summary: 'MNT aims to optimise lipid levels while maintaining a balanced diet and empowering long-term behaviour change.' },
    ],
  },

  // ── HEART FAILURE (5) ────────────────────────────────────────────────────

  {
    id: 'q3',
    text: 'A heart failure patient weighs themselves every day at home. What specific weight change should make them call their doctor immediately?',
    hint: 'Look in the Heart Failure guideline under patient self-care.',
    expectedAnswer: 'A sudden weight gain of more than 2 kg in 3 days is a warning sign of worsening heart failure.',
    sourceCardId: 'c3',
    topic: 'Heart Failure — Self-Care',
    options: [
      { id: 'A', text: 'More than 1 kg in 1 day' },
      { id: 'B', text: 'More than 5 kg in 1 week' },
      { id: 'C', text: 'More than 2 kg in 3 days' },
      { id: 'D', text: 'More than 3 kg in 5 days' },
    ],
    correctOption: 'C',
    cards: [
      { id: 'q3c1', cpg: 'CPG Heart Failure (5th Ed.)', section: 'Section 8.1 — Self-Care', summary: 'A sudden weight gain of more than 2 kg in 3 days is a warning sign of worsening heart failure — call your doctor.' },
      { id: 'q3c2', cpg: 'CPG Heart Failure (5th Ed.)', section: 'Section 8.1 — Monitoring', summary: 'Daily weighing is a key self-monitoring task. Patients should track trends and act on sudden increases promptly.' },
      { id: 'q3c3', cpg: 'CPG Heart Failure (5th Ed.)', section: 'Section 6.1 — Symptoms', summary: 'Breathlessness, ankle swelling, and reduced exercise tolerance are common heart failure symptoms to watch for.' },
      { id: 'q3c4', cpg: 'CPG Heart Failure (5th Ed.)', section: 'Section 2 — Definition', summary: "Heart failure means the heart cannot meet the body's needs. It is progressive and patients need ongoing self-management." },
    ],
  },

  {
    id: 'q12',
    text: 'Heart failure is defined as a clinical syndrome where the heart is unable to do what?',
    hint: 'Look in the Heart Failure guideline under the definition section.',
    expectedAnswer: "Heart failure is the heart's inability to meet the metabolic demands of the body, or its ability to do so only at higher-than-normal filling pressures.",
    sourceCardId: 'c3',
    topic: 'Heart Failure — Definition',
    options: [
      { id: 'A', text: 'Maintain a normal heart rate' },
      { id: 'B', text: 'Meet the metabolic demands of the body' },
      { id: 'C', text: 'Pump blood to the lungs' },
      { id: 'D', text: 'Respond to medication' },
    ],
    correctOption: 'B',
    cards: [
      { id: 'q12c1', cpg: 'CPG Heart Failure (5th Ed.)', section: 'Section 2 — Definition', summary: "Heart failure is the heart's inability to meet the body's metabolic demands, or doing so only at higher filling pressures." },
      { id: 'q12c2', cpg: 'CPG Heart Failure (5th Ed.)', section: 'Section 2 — Causes', summary: 'Most HF is due to myocardial dysfunction (systolic or diastolic), but valve, pericardial, and rhythm problems can also cause it.' },
      { id: 'q12c3', cpg: 'CPG Heart Failure (5th Ed.)', section: 'Section 6.1 — Symptoms', summary: 'Typical symptoms include breathlessness, ankle swelling, and fatigue. Signs include raised jugular venous pressure.' },
      { id: 'q12c4', cpg: 'CPG Heart Failure (5th Ed.)', section: 'Section 8.1 — Patient Education', summary: "Patients should understand HF's progressive and relapsing nature and the importance of self-care." },
    ],
  },

  {
    id: 'q13',
    text: 'Which two clinical signs of heart failure are described as more specific and associated with adverse outcomes?',
    hint: 'Look in the Heart Failure guideline under symptoms and signs.',
    expectedAnswer: 'An elevated jugular venous pulse (JVP) and a third heart sound are the more specific signs associated with adverse outcomes.',
    sourceCardId: 'c3',
    topic: 'Heart Failure — Clinical Signs',
    options: [
      { id: 'A', text: 'Ankle oedema and fatigue' },
      { id: 'B', text: 'Raised JVP and a third heart sound' },
      { id: 'C', text: 'Breathlessness and reduced exercise tolerance' },
      { id: 'D', text: 'Pulmonary crackles and displaced apex beat' },
    ],
    correctOption: 'B',
    cards: [
      { id: 'q13c1', cpg: 'CPG Heart Failure (5th Ed.)', section: 'Section 6.1 — Specific Signs', summary: 'Elevated jugular venous pulse (JVP) and a third heart sound are the more specific signs for heart failure.' },
      { id: 'q13c2', cpg: 'CPG Heart Failure (5th Ed.)', section: 'Section 6.1 — JVP Accuracy', summary: 'A raised JVP has 70% sensitivity and 79% specificity for left-sided congestion in heart failure.' },
      { id: 'q13c3', cpg: 'CPG Heart Failure (5th Ed.)', section: 'Section 6.1 — Symptoms', summary: 'Breathlessness, orthopnoea, paroxysmal nocturnal dyspnoea, and ankle swelling are characteristic but less specific.' },
      { id: 'q13c4', cpg: 'CPG Heart Failure (5th Ed.)', section: 'Section 2 — Definition', summary: 'HF results from structural or physiological abnormalities of the heart affecting its pumping or filling function.' },
    ],
  },

  {
    id: 'q14',
    text: 'In heart failure self-care, what does the "monitoring" component specifically involve?',
    hint: 'Look in the Heart Failure guideline under patient self-care education.',
    expectedAnswer: 'Monitoring involves regular weighing and recognising changes in signs and symptoms, such as sudden weight gain.',
    sourceCardId: 'c3',
    topic: 'Heart Failure — Monitoring',
    options: [
      { id: 'A', text: 'Taking medication correctly every day' },
      { id: 'B', text: 'Changing diuretic dose when symptoms worsen' },
      { id: 'C', text: 'Regular weighing and recognising symptom changes' },
      { id: 'D', text: 'Attending outpatient clinic every month' },
    ],
    correctOption: 'C',
    cards: [
      { id: 'q14c1', cpg: 'CPG Heart Failure (5th Ed.)', section: 'Section 8.1 — Self-Care Components', summary: 'HF self-care has three parts: maintenance (taking medication, exercising), monitoring (weighing, tracking symptoms), and management (adjusting treatment).' },
      { id: 'q14c2', cpg: 'CPG Heart Failure (5th Ed.)', section: 'Section 8.1 — Monitoring', summary: 'The monitoring component specifically includes regular weighing and recognising changes in signs and symptoms.' },
      { id: 'q14c3', cpg: 'CPG Heart Failure (5th Ed.)', section: 'Section 8.1 — Warning Signs', summary: 'A sudden weight gain of more than 2 kg in 3 days is the key warning sign patients must know to act on immediately.' },
      { id: 'q14c4', cpg: 'CPG Heart Failure (5th Ed.)', section: 'Section 8.1 — Patient Education', summary: 'Patients should also know their medications — indication, dose, side effects, and drug interactions.' },
    ],
  },

  {
    id: 'q15',
    text: 'What does a raised JVP (jugular venous pulse) with hepatomegaly and positive jugulo-venous reflux generally indicate?',
    hint: 'Look in the Heart Failure guideline under symptoms and signs.',
    expectedAnswer: 'These findings generally indicate a raised right atrial pressure of greater than 8 mmHg.',
    sourceCardId: 'c3',
    topic: 'Heart Failure — JVP',
    options: [
      { id: 'A', text: 'Raised right atrial pressure > 8 mmHg' },
      { id: 'B', text: 'Low cardiac output syndrome' },
      { id: 'C', text: 'Aortic stenosis' },
      { id: 'D', text: 'Pulmonary embolism' },
    ],
    correctOption: 'A',
    cards: [
      { id: 'q15c1', cpg: 'CPG Heart Failure (5th Ed.)', section: 'Section 6.1 — JVP Findings', summary: 'A raised JVP, positive jugulo-venous reflux, and hepatomegaly indicate a raised right atrial pressure of more than 8 mmHg.' },
      { id: 'q15c2', cpg: 'CPG Heart Failure (5th Ed.)', section: 'Section 6.1 — JVP Accuracy', summary: 'Raised JVP has 70% sensitivity and 79% specificity for detecting left-sided congestion in heart failure patients.' },
      { id: 'q15c3', cpg: 'CPG Heart Failure (5th Ed.)', section: 'Section 6.1 — Adverse Outcomes', summary: 'Elevated JVP and third heart sound are associated with adverse outcomes in HF and asymptomatic LV dysfunction.' },
      { id: 'q15c4', cpg: 'CPG Heart Failure (5th Ed.)', section: 'Section 2 — Causes', summary: 'Abnormalities of heart rhythm, valves, pericardium, and endocardium can all contribute to raised filling pressures in HF.' },
    ],
  },
];
