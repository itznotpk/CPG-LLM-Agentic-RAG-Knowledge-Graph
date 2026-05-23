# CPG Scope Review — regenerated 2026-05-08T14:01:32.307320+00:00

Source of truth is the `documents` table. Edit the lists below to correct any scope, then mark Approve / Edit / Reject. The Step 04 verifier will parse this file.

Groups: 30

> **TODO — recalibrate `SEMANTIC_SCOPE_THRESHOLD` (D2):** currently 0.65 in `agent/routing.py` — **confirmed too high; D2 would never fire.** Decision: **set to `0.40` (single absolute floor, no margin rule)**, but apply the change to `agent/routing.py` only *after all CPGs are embedded* so the floor is set against the full picture.
>
> **Calibration probe (RE-RUN at 27 CPGs embedded, 2026-05-23), best cosine(icd_emb, scope_emb):**
> | class | range | examples |
> |---|---|---|
> | positives (correct CPG, in-scope) | **0.42–0.70** | thyroid 0.42 (lowest), colorectal 0.51, breast 0.50, HTN 0.53, cancer-pain 0.53, HF 0.54, PAH 0.54, T1DM 0.55, stroke 0.56, cervical 0.57, AF 0.59, ED 0.60, IE 0.67, MI 0.70 |
> | cardiac near-miss (adjacent, not in scope) | **0.35–0.36** | valve 0.364, cardiomyopathy 0.363, pericarditis 0.350 |
> | unrelated orphans (in table) | **0.14–0.28** | cardiac-arrest 0.276, UTI 0.265, lung-ca→breast 0.245, migraine 0.220, epilepsy 0.144 |
>
> **Clean separator confirmed:** min positive (thyroid **0.417**) > max orphan (valve **0.364**). 0.40 sits in the 0.364–0.417 gap. Note: thyroid at 0.417 is the tightest positive (only 0.017 above 0.40); **0.38** is an equally valid choice that buys more headroom below thyroid while still rejecting valve (0.364). Both fine; 0.40 is the conservative round number.
>
> **Why 0.40, why no margin:** 0.40 sits cleanly above every orphan (≤0.27, incl. the confident-but-wrong lung-ca→breast 0.245) and below every true positive (≥0.50). The **margin rule fails**: good near-miss has a tiny gap (cardiomyopathy 0.029 → margin would wrongly reject) while a bad orphan has a big gap (lung-ca→breast 0.193 → margin would wrongly accept). 0.40 treats cardiac near-misses as out_of_scope (conservative — safer to say "no CPG" than route to the wrong guideline); lower to **0.33** later if D2 should recover those adjacencies.
>
> **Structural caveats:** (1) `icd11_codes` is a curated subset, not all of ICD-11 — many model-predicted codes (fractures, derm, COPD, etc.) aren't in the table, so D2 returns `[]` (no embedding) → out_of_scope regardless of threshold; D2's firing population is already narrow. (2) D2 cannot recover **broad-CPG members** — diabetes/obesity/CKD are in CVD's scope but score only 0.15–0.32 semantically; the broad rationale doesn't surface them. They MUST be caught by D1 (they are). (3) Numbers re-derived at 14 then 27 CPGs and the 0.364–0.417 gap held both times; one final re-run after the last 3 CPGs (Obesity, T2-DM, Nasopharyngeal) is the only thing left before flipping the constant — Titan v1 compression means absolute values may shift slightly as the last few join, but the gap has been stable.

---

## Atrial-Fibrillation(2012) ✅
- Rows in DB: 12
- Last classified: 2026-05-08T13:48:07.294617+00:00
- Proposed icd11_scope: `BC81.3`, `BC81.30`, `BC81.31`, `BC81.32`, `BC81.33`, `BC81.3Y`, `BC81.3Z`
- Proposed procedure_scope: `referral_pathway`, `clinical_audit`, `quality_assurance`, `warfarin_initiation`, `inr_monitoring`, `dose_adjustment`, `perioperative_bridging`
- icd11_rationale: Specific AF guidance maps to BC81.3 (Atrial fibrillation) under the cardiac arrhythmia hierarchy.
- cpg_scope_rationale: This guideline covers atrial fibrillation as a supraventricular tachyarrhythmia spectrum including paroxysmal, persistent, long-standing persistent, permanent, and unspecified atrial fibrillation. Relevant patient population includes adults with confirmed or suspected atrial fibrillation, irregular pulse, palpitations, thromboembolic risk, or anticoagulation management needs. Clinical decisions and interventions include diagnostic confirmation, stroke risk stratification, bleeding risk assessment, warfarin initiation, INR monitoring, dose adjustment, perioperative bridging, rate control, rhythm control, follow-up, referral pathway, audit, and quality assurance. Relevant comorbidities and key risk factors include hypertension, ischaemic heart disease, heart failure, valvular heart disease, diabetes mellitus, chronic kidney disease, older age, prior stroke, transient ischaemic attack, and cardiovascular risk factors.
- ICD-11 hierarchy: Chapter 11 (Diseases of the circulatory system) > Block BC60-BC9Z (Cardiac arrhythmia) > Category BC80-BC8Z (Supraventricular rhythm disturbance) > Section BC81 (Supraventricular tachyarrhythmia) > Specific BC81.3 (Atrial fibrillation)
- [x] Approve / [ ] Edit / [ ] Reject

---

## Breast-Cancer(3rd Edition) ✅
- Rows in DB: 13
- Last classified: 2026-05-08T13:48:07.294617+00:00
- Proposed icd11_scope: `2C60`, `2C61`, `2C61.0`, `2C61.1`, `2C61.2`, `2C61.3`, `2C61.4`, `2C62`, `2C63`, `2C64`, `2C65`, `2C6Y`, `2C6Z`
- Proposed procedure_scope: (none)
- icd11_rationale: Malignant neoplasms of breast (2C60-2C6Z).
- cpg_scope_rationale: This guideline covers malignant neoplasms of the breast including ductal carcinoma, lobular carcinoma, carcinoma in situ, invasive carcinoma, locally advanced breast cancer, metastatic breast cancer, recurrent breast cancer, and unspecified breast carcinoma. Relevant patient population includes adults with suspected or confirmed breast cancer detected by screening, breast mass, nipple discharge, skin change, axillary disease, or recurrence after prior treatment. Clinical decisions and interventions include breast imaging, biopsy, histopathology, staging, receptor assessment, molecular assessment, surgery, radiotherapy, systemic chemotherapy, endocrine therapy, targeted therapy, follow-up surveillance, supportive care, and multidisciplinary oncology referral. Relevant comorbidities and key risk factors include age, family history, hereditary cancer syndromes, oestrogen receptor status, HER2 status, nodal disease, fertility considerations, pregnancy context, and metastatic burden.
- ICD-11 hierarchy: Chapter 02 (Neoplasms) > Malignant neoplasms of breast range 2C60-2C6Z > Verified examples from API search include 2C60, 2C63, 2C65, 2C6Y, and 2C6Z
- [x] Approve / [ ] Edit / [ ] Reject

---

## CVD-Prevention-Women(2016) ✅
- Rows in DB: 9
- Last classified: 2026-05-08T14:01:21.563348+00:00
- Proposed icd11_scope: `BA00`, `BA00.0`, `BA00.1`, `BA00.2`, `BA00.Y`, `BA00.Z`, `BA01`, `BA02`, `BA03`, `BA04`, `BA04.0`, `BA04.1`, `BA04.2`, `BA04.Y`, `BA04.Z`, `BA40`, `BA40.0`, `BA40.1`, `BA40.Y`, `BA40.Z`, `BA41`, `BA41.0`, `BA41.1`, `BA41.Z`, `BA42`, `BA42.0`, `BA42.1`, `BA42.Z`, `BD10`, `BD11`, `BD11.0`, `BD11.1`, `BD11.2`, `BD11.Z`, `BD12`, `BD13`, `8B11`, `8B11.0`, `8B11.1`, `8B11.20`, `8B11.21`, `8B11.22`, `8B11.2Y`, `8B11.2Z`, `8B11.3`, `8B11.40`, `8B11.41`, `8B11.42`, `8B11.43`, `8B11.44`, `8B11.50`, `8B11.51`, `8B11.5Z`, `5C80`, `5C80.00`, `5C80.01`, `5C80.0Z`, `5C80.1`, `5C80.2`, `5C80.3`, `5C80.Y`, `5C80.Z`, `5A11`, `BD40`, `BD40.0`, `BD40.1`, `BD40.2`, `BD40.3`, `BD40.Y`, `BD40.Z`, `BD50`, `BD50.00`, `BD50.01`, `BD50.02`, `BD50.0Y`, `BD50.0Z`, `BD50.10`, `BD50.11`, `BD50.12`, `BD50.1Y`, `BD50.1Z`, `BD50.20`, `BD50.21`, `BD50.22`, `BD50.2Y`, `BD50.2Z`, `BD50.30`, `BD50.31`, `BD50.32`, `BD50.3Y`, `BD50.3Z`, `BD50.40`, `BD50.41`, `BD50.4Y`, `BD50.4Z`, `BD50.50`, `BD50.51`, `BD50.52`, `BD50.5Y`, `BD50.5Z`, `BD50.Z`, `BC81.3`, `BC81.30`, `BC81.31`, `BC81.32`, `BC81.33`, `BC81.3Y`, `BC81.3Z`, `5B81`, `5B81.00`, `5B81.01`, `5B81.1`, `5B81.Y`, `5B81.Z`, `GB61`, `GB61.0`, `GB61.1`, `GB61.2`, `GB61.3`, `GB61.4`, `GB61.5`, `GB61.Z`
- Proposed procedure_scope: (none)
- icd11_rationale: Systemic cardiovascular prevention strategy covering major circulatory endpoints and metabolic drivers, including chronic kidney disease as a high-risk cardiovascular equivalent.
- cpg_scope_rationale: This guideline covers cardiovascular disease prevention in women across hypertension, ischaemic heart disease, myocardial infarction, heart failure, atrial fibrillation, cerebrovascular disease, peripheral arterial disease, dyslipidaemia, diabetes mellitus, obesity, chronic kidney disease, and cardiometabolic risk states. Relevant patient population includes women needing primary cardiovascular prevention, women needing secondary prevention after cardiovascular disease, and women with life-course or sex-specific risk contexts. Clinical decisions and interventions include cardiovascular risk assessment, blood pressure control, lipid management, glycaemic risk management, smoking cessation, dietary intervention, physical activity, weight reduction, antiplatelet consideration, anticoagulant consideration, cardiac rehabilitation, and follow-up. Relevant comorbidities and key risk factors include pregnancy history, menopause, metabolic syndrome, hypertension, diabetes mellitus, dyslipidaemia, obesity, chronic kidney disease, smoking, stroke history, and vascular risk clustering.
- ICD-11 hierarchy: Chapter 11 (Circulatory) -> Hypertension (BA00-BA04), IHD (BA40-BA42), Heart Failure (BD10-BD13), Arrhythmia (BC81.3), Peripheral Vascular (BD40, BD50); Chapter 05 (Metabolic) -> Diabetes (5A11), Dyslipidaemia (5C80), Obesity (5B81), Metabolic Syndrome (5C40); Chapter 08 (Nervous) -> Ischaemic Stroke (8B11); Chapter 16 (Genitourinary) -> Chronic Kidney Disease (GB61)
- [x] Approve / [ ] Edit / [ ] Reject

---

## Dyslipidaemia(6th-Edition) ✅
- Rows in DB: 15
- Last classified: 2026-05-08T13:48:07.294617+00:00
- Proposed icd11_scope: `5C80`, `5C80.00`, `5C80.01`, `5C80.0Z`, `5C80.1`, `5C80.2`, `5C80.3`, `5C80.Y`, `5C80.Z`, `5C81`, `5C81.0`, `5C81.1`, `5C81.Y`, `5C81.Z`, `5C8Y`, `5C8Z`
- Proposed procedure_scope: (none)
- icd11_rationale: Comprehensive management of lipoprotein metabolism disorders, including primary and secondary hypercholesterolaemia, hypertriglyceridaemia, and mixed dyslipidaemias.
- cpg_scope_rationale: This guideline covers disorders of lipoprotein metabolism and other lipidaemias including hypercholesterolaemia, hypertriglyceridaemia, mixed dyslipidaemia, familial dyslipidaemia, primary dyslipidaemia, secondary dyslipidaemia, low HDL cholesterol, elevated LDL cholesterol, non-HDL cholesterol, lipoprotein(a), and unspecified lipid abnormalities. Relevant patient population includes adults and high-risk groups undergoing cardiovascular risk evaluation, primary prevention, and secondary prevention after atherosclerotic cardiovascular disease. Clinical decisions and interventions include fasting lipid measurement, non-fasting lipid measurement, risk stratification, lipid targets, medical nutrition therapy, physical activity, weight management, smoking cessation, statins, ezetimibe, fibrates, PCSK9 inhibitors, combination lipid-lowering therapy, adverse-effect monitoring, and adherence review. Relevant comorbidities and key risk factors include diabetes mellitus, chronic kidney disease, hypertension, obesity, metabolic syndrome, premature coronary artery disease, stroke, and peripheral arterial disease.
- ICD-11 hierarchy: Chapter 05 (Endocrine, nutritional or metabolic diseases) > Metabolic disorders > Disorders of lipoprotein metabolism or other lipidaemias range 5C80-5C8Z
- [x] Approve / [ ] Edit / [ ] Reject

---

## Erectile-Dysfunction(2024) ✅
- Rows in DB: 10
- Last classified: 2026-05-08T13:48:07.294617+00:00
- Proposed icd11_scope: `HA01.10`, `HA01.11`, `HA01.12`, `HA01.13`, `HA01.1Z`
- Proposed procedure_scope: (none)
- icd11_rationale: Direct mapping for male erectile dysfunction, covering lifelong, acquired, situational, and generalized presentations.
- cpg_scope_rationale: This guideline covers male erectile dysfunction as a sexual arousal disorder including lifelong, acquired, generalized, situational, psychogenic, vasculogenic, neurogenic, endocrine, medication-related, and mixed erectile dysfunction presentations. Relevant patient population includes adult men with persistent or recurrent inability to attain or maintain an erection sufficient for satisfactory sexual activity. Clinical decisions and interventions include history taking, validated symptom assessment, sexual evaluation, psychosocial evaluation, cardiovascular risk assessment, endocrine investigation, testosterone assessment, lifestyle modification, phosphodiesterase type 5 inhibitor therapy, vacuum device therapy, intracavernosal therapy, intraurethral therapy, penile prosthesis referral, counselling, partner-factor assessment, follow-up, and referral. Relevant comorbidities and key risk factors include diabetes mellitus, hypertension, dyslipidaemia, obesity, smoking, depression, hypogonadism, benign prostatic disease, pelvic surgery, and cardiovascular disease.
- ICD-11 hierarchy: Chapter 17 (Conditions related to sexual health) > Sexual dysfunctions > Sexual arousal dysfunctions > Male erectile dysfunction range HA01.10-HA01.1Z
- [x] Approve / [ ] Edit / [ ] Reject

---

## Heart-Failure(5th Edition) ✅
- Rows in DB: 29
- Last classified: 2026-05-08T13:48:07.294617+00:00
- Proposed icd11_scope: `BD10`, `BD11`, `BD11.0`, `BD11.1`, `BD11.2`, `BD11.Z`, `BD12`, `BD13`, `BD14`, `BD1Y`, `BD1Z`
- Proposed procedure_scope: (none)
- icd11_rationale: Comprehensive management of the heart failure clinical syndrome, including congestive, left ventricular, right ventricular, biventricular, and unspecified heart failure presentations.
- cpg_scope_rationale: This guideline covers heart failure clinical syndrome across acute, chronic, congestive, left ventricular, right ventricular, biventricular, preserved ejection fraction, mildly reduced ejection fraction, reduced ejection fraction, improved ejection fraction, advanced, pregnancy-associated, cardio-oncology, arrhythmia-related, cardiomyopathy-related, and unspecified presentations. Relevant patient population includes adults with suspected heart failure, newly diagnosed heart failure, stable chronic heart failure, decompensated heart failure, or advanced heart failure. Clinical decisions and interventions include symptom assessment, sign assessment, natriuretic peptide testing, imaging, echocardiography, staging, precipitant assessment, guideline-directed medical therapy, diuretics, device therapy, rehabilitation, monitoring, discharge planning, referral, transplant pathway, mechanical circulatory support pathway, palliative care, and multidisciplinary follow-up. Relevant comorbidities and key risk factors include hypertension, ischaemic heart disease, atrial fibrillation, chronic kidney disease, diabetes mellitus, valvular heart disease, cardiomyopathy, COVID-19, pregnancy, and anaemia.
- ICD-11 hierarchy: Chapter 11 (Diseases of the circulatory system) > Heart failure range BD10-BD1Z
- [x] Approve / [ ] Edit / [ ] Reject

---

## Hypertension(5th Edition) ✅
- Rows in DB: 14
- Last classified: 2026-05-08T13:48:07.294617+00:00
- Proposed icd11_scope: `BA00`, `BA00.0`, `BA00.1`, `BA00.2`, `BA00.Y`, `BA00.Z`, `BA01`, `BA02`, `BA03`, `BA04`, `BA04.0`, `BA04.1`, `BA04.2`, `BA04.Y`, `BA04.Z`
- Proposed procedure_scope: (none)
- icd11_rationale: Hypertensive diseases: essential, secondary, hypertensive crisis (BA00-BA04).
- cpg_scope_rationale: This guideline covers hypertensive diseases including essential hypertension, secondary hypertension, hypertensive urgency, hypertensive emergency, masked hypertension, white-coat hypertension, resistant hypertension, and target-organ risk states. Relevant patient population includes adolescents and adults undergoing blood pressure screening, hypertension diagnosis, cardiovascular risk assessment, and long-term hypertension management in primary care or specialist settings. Clinical decisions and interventions include office blood pressure measurement, out-of-office blood pressure measurement, ambulatory monitoring, home monitoring, risk stratification, secondary cause investigation, lifestyle modification, pharmacological treatment, treatment target selection, adherence review, follow-up, and referral. Relevant comorbidities and key risk factors include diabetes mellitus, dyslipidaemia, chronic kidney disease, obesity, smoking, ischaemic heart disease, heart failure, stroke, pregnancy potential, obstructive sleep apnoea, endocrine disease, and renal disease.
- [x] Approve / [ ] Edit / [ ] Reject

---

## Ischaemic-Stroke(3rd Edition) ✅
- Rows in DB: 18
- Last classified: 2026-05-08T13:17:44.569519+00:00
- Proposed icd11_scope: `8B11`, `8B11.0`, `8B11.1`, `8B11.20`, `8B11.21`, `8B11.22`, `8B11.2Y`, `8B11.2Z`, `8B11.3`, `8B11.40`, `8B11.41`, `8B11.42`, `8B11.43`, `8B11.44`, `8B11.50`, `8B11.51`, `8B11.5Z`
- Proposed procedure_scope: `endovascular_thrombectomy`, `stroke_workflow`, `revascularization`
- icd11_rationale: The 3rd Edition CPG specifically manages acute cerebral ischaemic stroke (8B11) and reperfusion therapy. 8B10 (TIA) is excluded as it has distinct management; 8B20 is a pre-imaging triage code; 8B25 (Late effects) covers rehabilitation, not acute treatment.
- cpg_scope_rationale: This guideline covers cerebral ischaemic stroke including large artery atherosclerotic stroke, cardioembolic stroke, lacunar stroke, posterior circulation stroke, anterior circulation stroke, unspecified ischaemic stroke, and acute cerebral infarction presentations. Relevant patient population includes adults with suspected or confirmed acute focal neurological deficit due to cerebral ischaemia in emergency department, stroke unit, inpatient, and post-acute care settings. Clinical decisions and interventions include rapid recognition, neuroimaging, stroke workflow, reperfusion eligibility, intravenous thrombolysis, endovascular thrombectomy, antiplatelet timing, anticoagulation timing, blood pressure management, glucose management, dysphagia screening, secondary prevention, rehabilitation referral, complication management, and follow-up surveillance. Relevant comorbidities and key risk factors include atrial fibrillation, hypertension, diabetes mellitus, dyslipidaemia, smoking, carotid disease, prior stroke, transient ischaemic attack, chronic kidney disease, coronary disease, and peripheral vascular disease.
- ICD-11 hierarchy: Chapter 08 (Nervous system diseases) > Cerebrovascular diseases > Cerebral ischaemia > 8B11 Cerebral ischaemic stroke
- [x] Approve / [ ] Edit / [ ] Reject

---

## NSTE-ACS(3rd Edition) ✅
- Rows in DB: 12
- Last classified: 2026-05-08T13:48:07.294617+00:00
- Proposed icd11_scope: `BA40`, `BA40.0`, `BA40.1`, `BA40.Y`, `BA40.Z`, `BA41`, `BA41.0`, `BA41.1`, `BA41.Z`
- Proposed procedure_scope: `cardiac_rehabilitation`, `exercise_training`, `smoking_cessation`, `lifestyle_modification`
- icd11_rationale: Non-ST-elevation acute coronary syndromes: unstable angina (BA40) and acute MI (BA41). NSTE-ACS is differentiated from STEMI by the absence of persistent ST-segment elevation and sub-classified based on troponin.
- cpg_scope_rationale: This guideline covers non-ST-elevation acute coronary syndrome including unstable angina, non-ST-elevation myocardial infarction, acute myocardial ischaemia, dynamic electrocardiographic change, and troponin-positive or troponin-negative acute coronary presentations. Relevant patient population includes adults presenting with chest pain, equivalent ischaemic symptoms, abnormal cardiac biomarkers, dynamic ECG changes, or high clinical suspicion of acute coronary syndrome. Clinical decisions and interventions include early diagnosis, troponin interpretation, ECG risk assessment, antithrombotic therapy, anti-ischaemic therapy, invasive coronary angiography timing, risk stratification, revascularisation referral, discharge planning, cardiac rehabilitation, smoking cessation, lipid management, blood pressure management, and secondary prevention. Relevant comorbidities and key risk factors include diabetes mellitus, chronic kidney disease, hypertension, dyslipidaemia, heart failure, prior myocardial infarction, prior PCI, prior CABG, anaemia, bleeding risk, and older age.
- ICD-11 hierarchy: Chapter 11 (Diseases of the circulatory system) > Ischaemic heart diseases > Acute ischaemic heart disease > BA40 Angina pectoris and BA41 Acute myocardial infarction
- [x] Approve / [ ] Edit / [ ] Reject

---

## NSTEMI(2011) ✅
- Rows in DB: 13
- Last classified: 2026-05-08T13:48:07.294617+00:00
- Proposed icd11_scope: `BA41`, `BA41.0`, `BA41.1`, `BA41.Z`
- Proposed procedure_scope: (none)
- icd11_rationale: Acute myocardial infarction — non-ST-elevation subtype (BA41).
- cpg_scope_rationale: This guideline covers non-ST-elevation myocardial infarction as an acute myocardial infarction subtype with myocardial injury, ischaemic symptoms, biomarker elevation, and absence of persistent ST-segment elevation. Relevant patient population includes adults presenting with suspected acute coronary syndrome and troponin-positive non-ST-elevation infarction in emergency, inpatient, cardiology, and coronary care settings. Clinical decisions and interventions include diagnostic confirmation, ECG interpretation, biomarker interpretation, risk stratification, antiplatelet therapy, anticoagulant therapy, anti-ischaemic medication, invasive coronary angiography selection, revascularisation referral, complication management, discharge medication, rehabilitation, and secondary prevention. Relevant comorbidities and key risk factors include hypertension, dyslipidaemia, diabetes mellitus, chronic kidney disease, smoking, prior coronary artery disease, heart failure, older age, bleeding risk, and concurrent atrial fibrillation.
- [X] Approve / [ ] Edit / [ ] Reject

---

## Patient-Safety-Minimal-Monitoring ✅
- Rows in DB: 9
- Last classified: 2026-05-08T13:17:49.790774+00:00
- Proposed icd11_scope: (none)
- Proposed procedure_scope: `pre_op_assessment`, `anaesthetic_equipment_safety`, `anaesthetic_safety`
- icd11_rationale: The CPG focuses on anaesthesia safety, equipment checks, and pre-operative assessment rather than specific diseases.
- cpg_scope_rationale: This guideline covers perioperative patient safety and minimum monitoring standards during anaesthesia, procedural sedation, recovery, and anaesthetic system care. Relevant patient population includes adults, children, pregnant patients, high-risk patients, emergency cases, and patients undergoing surgery, obstetric procedures, diagnostic procedures, or procedural anaesthesia. Clinical decisions and interventions include pre-procedure safety checks, patient identification, anaesthetic equipment readiness, airway monitoring, oxygenation monitoring, ventilation monitoring, circulation monitoring, temperature monitoring, documentation, handover, recovery monitoring, escalation, audit, and quality assurance. Relevant comorbidities and key risk factors include difficult airway, haemodynamic instability, cardiorespiratory disease, obesity, pregnancy, paediatric age, emergency surgery, drug allergy, medication risk, equipment hazard, and human-factor hazard.
- [x] Approve / [ ] Edit / [ ] Reject

---

## Percutaneous-Coronary-Intervention ✅
- Rows in DB: 10
- Last classified: 2026-05-08T14:01:21.563348+00:00
- Proposed icd11_scope: `BA40`, `BA40.0`, `BA40.1`, `BA40.Y`, `BA40.Z`, `BA41`, `BA41.0`, `BA41.1`, `BA41.Z`, `BA42`, `BA42.0`, `BA42.1`, `BA42.Z`
- Proposed procedure_scope: `percutaneous_coronary_intervention`, `coronary_angiography`, `coronary_stenting`, `intravascular_imaging`
- icd11_rationale: Ischaemic heart disease conditions treated by PCI: unstable angina (BA40), acute myocardial infarction (BA41), chronic ischaemic heart disease (BA42).
- cpg_scope_rationale: This guideline covers percutaneous coronary intervention for ischaemic heart disease including coronary angiography, balloon angioplasty, coronary stenting, intravascular imaging, adjunctive pharmacotherapy, unstable angina intervention, myocardial infarction intervention, and chronic ischaemic heart disease revascularisation. Relevant patient population includes adults with obstructive coronary artery disease requiring invasive evaluation or coronary revascularisation in acute coronary syndrome or stable coronary syndrome contexts. Clinical decisions and interventions include patient selection, lesion assessment, access-site selection, antiplatelet therapy, anticoagulation, drug-eluting stent use, bare-metal stent use, complication management, contrast-risk management, restenosis monitoring, thrombosis prevention, follow-up, and secondary prevention. Relevant comorbidities and key risk factors include diabetes mellitus, chronic kidney disease, hypertension, dyslipidaemia, heart failure, prior PCI, prior CABG, bleeding risk, and multivessel disease.
- ICD-11 hierarchy: Chapter 11 (Diseases of the circulatory system) > Ischaemic heart diseases > BA40 Angina pectoris, BA41 Acute myocardial infarction, and BA42 Chronic ischaemic heart disease
- [x] Approve / [ ] Edit / [ ] Reject

---

## Pre-Anaesthetic-Assessment ✅
- Rows in DB: 9
- Last classified: 2026-05-08T13:17:54.174182+00:00
- Proposed icd11_scope: (none)
- Proposed procedure_scope: `pre_op_assessment`, `investigation_selection`, `risk_assessment`, `anaesthetic_planning`
- icd11_rationale: CPG focuses on pre-anaesthetic assessment, investigation selection based on patient factors and surgery type, risk assessment and anaesthetic planning, not on specific disease treatment.
- cpg_scope_rationale: This guideline covers pre-anaesthetic assessment as a perioperative evaluation process for anaesthesia, sedation, regional anaesthesia, and perioperative monitoring. Relevant patient population includes adults, children, pregnant patients, frail patients, and patients scheduled for elective, urgent, or emergency surgery or procedures requiring anaesthetic planning. Clinical decisions and interventions include medical history, physical examination, airway assessment, functional capacity assessment, medication review, allergy assessment, fasting review, investigation selection, risk stratification, comorbidity optimisation, anaesthetic planning, informed consent, referral, and perioperative communication. Relevant comorbidities and key risk factors include cardiovascular disease, respiratory disease, diabetes mellitus, chronic kidney disease, obesity, pregnancy, anaemia, anticoagulant use, frailty, paediatric age, difficult airway, previous anaesthetic complications, and perioperative medication risk.
- ICD-11 hierarchy: N/A (Focuses on perioperative procedures and safety planning rather than specific disease classifications)
- [x] Approve / [ ] Edit / [ ] Reject

---

## Prevention-Diagnosis-Management-of-IE ✅
- Rows in DB: 10
- Last classified: 2026-05-09T14:18:42.102345+00:00
- Proposed icd11_scope: `BB40`, `BB41`, `BB42`, `BB4Y`, `BB4Z`
- Proposed procedure_scope: (none)
- icd11_rationale: Captures the full spectrum of acute/subacute endocarditis including infectious (BB40), related inflammations (BB41, BB42), and catch-all categories for other specified (BB4Y) or unspecified (BB4Z) presentations.
- cpg_scope_rationale: This guideline covers infective endocarditis and related acute or subacute endocardial inflammatory disease involving native valves, prosthetic valves, intracardiac devices, and structurally abnormal hearts. Relevant patient population includes adults and high-risk patients with suspected or confirmed bacteraemia-associated endocarditis, fever with murmur, embolic phenomena, positive blood cultures, echocardiographic vegetation, abscess, or valvular destruction. Clinical decisions and interventions include prevention, antibiotic prophylaxis for high-risk procedures, diagnostic criteria, blood culture strategy, echocardiography, antimicrobial treatment, surgical referral, complication management, follow-up, and multidisciplinary care. Relevant comorbidities and key risk factors include rheumatic heart disease, congenital heart disease, prosthetic valves, previous endocarditis, haemodialysis, intravenous drug use, immunosuppression, indwelling catheters, and Staphylococcus aureus bacteraemia.
- ICD-11 hierarchy: Chapter 11 (Diseases of the circulatory system) > Endocarditis > Acute or subacute endocarditis range BB40-BB4Z.
- [x] Approve / [ ] Edit / [ ] Reject

---

## Pulmonary-Arterial-Hypertension(2011) ✅
- Rows in DB: 21
- Last classified: 2026-05-09T14:25:10.112456+00:00
- Proposed icd11_scope: `BB01`, `BB01.0`, `BB01.1`, `BB01.2`, `BB01.3`, `BB01.4`, `BB01.5`, `BB01.Z`
- Proposed procedure_scope: (none)
- icd11_rationale: Pulmonary arterial hypertension (Group 1). This stem code covers idiopathic, heritable, and associated forms of PAH defined in the 2011 CPG.
- cpg_scope_rationale: This guideline covers pulmonary arterial hypertension corresponding to Group 1 pulmonary hypertension including idiopathic PAH, heritable PAH, drug-induced PAH, toxin-associated PAH, connective tissue disease-associated PAH, congenital heart disease-associated PAH, portal hypertension-associated PAH, HIV-associated PAH, and other specified PAH phenotypes. Relevant patient population includes adults with suspected or confirmed pulmonary vascular disease presenting with exertional dyspnoea, syncope, right heart failure, reduced exercise tolerance, or elevated pulmonary arterial pressure. Clinical decisions and interventions include diagnostic workup, echocardiography, right heart catheterisation, functional class assessment, vasoreactivity testing, risk stratification, supportive care, anticoagulation consideration, PAH-specific therapy, expert centre referral, pregnancy counselling, follow-up, and advanced therapy consideration. Relevant comorbidities and key risk factors include congenital heart disease, connective tissue disease, chronic liver disease, HIV infection, thromboembolic disease differential, and right ventricular dysfunction.
- ICD-11 hierarchy: Chapter 11 (Diseases of the circulatory system) > Pulmonary heart disease or diseases of pulmonary circulation > Pulmonary hypertension > BB01 Pulmonary arterial hypertension.
- [x] Approve / [ ] Edit / [ ] Reject

---

## STEMI(4th Edition) ✅
- Rows in DB: 20
- Last classified: 2026-05-09T14:26:05.883120+00:00
- Proposed icd11_scope: `BA41.0`
- Proposed procedure_scope: (none)
- icd11_rationale: Specifically identifies ST-elevation myocardial infarction. The parent code BA41 is too broad as it includes NSTEMI (BA41.1), which is managed under a different clinical pathway.
- cpg_scope_rationale: This guideline covers ST-elevation myocardial infarction as an acute coronary occlusion syndrome with persistent ST-segment elevation, equivalent electrocardiographic patterns, acute coronary thrombosis, and immediate reperfusion need. Relevant patient population includes adults with acute chest pain, ischaemic equivalents, ECG evidence of STEMI, suspected coronary artery occlusion, or myocardial infarction complications in emergency, pre-hospital, catheterisation laboratory, and coronary care settings. Clinical decisions and interventions include rapid diagnosis, reperfusion strategy, primary PCI, fibrinolysis, rescue PCI, antiplatelet therapy, anticoagulant therapy, beta-blockers, statins, ACE inhibitors, ARBs, shock management, arrhythmia management, discharge planning, rehabilitation, and secondary prevention. Relevant comorbidities and key risk factors include diabetes mellitus, hypertension, dyslipidaemia, smoking, chronic kidney disease, prior coronary disease, older age, and heart failure.
- ICD-11 hierarchy: Chapter 11 (Diseases of the circulatory system) > Ischaemic heart disease > Acute myocardial infarction > BA41.0 ST elevation myocardial infarction.
- [x] Approve / [ ] Edit / [ ] Reject

---

## Heart-Disease-in-Pregnancy(2nd Edition) ✅
- Rows in DB: 21
- Last classified: 2026-05-16T19:30:00+08:00
- Proposed icd11_scope: `BA00`, `BA00.0`, `BA00.1`, `BA00.2`, `BA00.Y`, `BA00.Z`, `BA01`, `BA02`, `BA03`, `BA04`, `BA04.0`, `BA04.1`, `BA04.2`, `BA04.Y`, `BA04.Z`, `BA40`, `BA40.0`, `BA40.1`, `BA40.Y`, `BA40.Z`, `BA41`, `BA41.0`, `BA41.1`, `BA41.Z`, `BA42`, `BA42.0`, `BA42.1`, `BA42.Z`, `BD10`, `BD11`, `BD11.0`, `BD11.1`, `BD11.2`, `BD11.Z`, `BD12`, `BD13`, `8B11`, `8B11.0`, `8B11.1`, `8B11.20`, `8B11.21`, `8B11.22`, `8B11.2Y`, `8B11.2Z`, `8B11.3`, `8B11.40`, `8B11.41`, `8B11.42`, `8B11.43`, `8B11.44`, `8B11.50`, `8B11.51`, `8B11.5Z`, `5C80`, `5C80.00`, `5C80.01`, `5C80.0Z`, `5C80.1`, `5C80.2`, `5C80.3`, `5C80.Y`, `5C80.Z`, `5B81`, `5B81.00`, `5B81.01`, `5B81.1`, `5B81.Y`, `5B81.Z`, `BD40`, `BD40.0`, `BD40.1`, `BD40.2`, `BD40.3`, `BD40.Y`, `BD40.Z`, `BD50`, `BD50.00`, `BD50.01`, `BD50.02`, `BD50.0Y`, `BD50.0Z`, `BD50.10`, `BD50.11`, `BD50.12`, `BD50.1Y`, `BD50.1Z`, `BD50.20`, `BD50.21`, `BD50.22`, `BD50.2Y`, `BD50.2Z`, `BD50.30`, `BD50.31`, `BD50.32`, `BD50.3Y`, `BD50.3Z`, `BD50.40`, `BD50.41`, `BD50.4Y`, `BD50.4Z`, `BD50.50`, `BD50.51`, `BD50.52`, `BD50.5Y`, `BD50.5Z`, `BD50.Z`, `BC81.3`, `BC81.30`, `BC81.31`, `BC81.32`, `BC81.33`, `BC81.3Y`, `BC81.3Z`, `GB61`, `GB61.0`, `GB61.1`, `GB61.2`, `GB61.3`, `GB61.4`, `GB61.5`, `GB61.Z`
- Proposed procedure_scope: `preconception_counselling`, `pregnancy_cardiac_risk_assessment`, `antenatal_cardiology_referral`, `multidisciplinary_pregnancy_care`, `labour_delivery_planning`, `postpartum_cardiac_follow_up`
- icd11_rationale: Heart disease in pregnancy is scoped to the major cardiovascular conditions and cardiometabolic risk drivers that affect maternal cardiac risk assessment and management.
- cpg_scope_rationale: This guideline covers cardiovascular disease in pregnancy and the puerperium including hypertensive disease, ischaemic heart disease, cardiomyopathy, heart failure, valvular heart disease, congenital heart disease, pulmonary hypertension, arrhythmia, aortic disease, thromboembolism, infective endocarditis, and cardiometabolic risk states. Relevant patient population includes women contemplating pregnancy, pregnant patients, intrapartum patients, and postpartum patients with known or suspected cardiac disease. Clinical decisions and interventions include preconception counselling, contraception counselling, maternal risk stratification, antenatal surveillance, medication safety, multidisciplinary pregnancy heart team care, imaging, intervention timing, anticoagulation, labour planning, delivery planning, anaesthetic consideration, postpartum monitoring, and fetal consideration. Relevant comorbidities and key risk factors include diabetes mellitus, chronic kidney disease, obesity, dyslipidaemia, hypertension, stroke history, thrombophilia, congenital heart disease, and prior cardiac events.
- ICD-11 hierarchy: Chapter 11 (Diseases of the circulatory system) > Hypertensive diseases (BA00-BA04), Ischaemic heart diseases (BA40-BA42), Heart failure (BD10-BD13), Cardiac arrhythmia (BC81.3), Peripheral vascular disease (BD40, BD50); Chapter 08 (Nervous) > Ischaemic stroke (8B11); Chapter 05 (Metabolic) > Lipidaemias (5C80), Obesity (5B81); Chapter 16 (Genitourinary) > Chronic kidney disease (GB61).
- [x] Approve / [ ] Edit / [ ] Reject

---

## Cancer-Pain(2nd Edition) ✅
- Rows in DB: 13
- Last classified: 2026-05-16T19:30:00+08:00
- Note: ingested as ONE CPG (adult Part A + paediatric Part B sections in one document group). Merged from the two original review proposals; ICD scope identical, procedure_scope is the union.
- Proposed icd11_scope: `MG30.1`, `MG30.10`, `MG30.11`, `MG30.1Y`, `MG30.1Z`
- Proposed procedure_scope: `pain_assessment`, `analgesic_ladder`, `opioid_initiation`, `opioid_titration`, `opioid_rotation`, `breakthrough_pain_management`, `adjuvant_analgesia`, `interventional_pain_management`, `palliative_care`, `paediatric_pain_assessment`, `paediatric_analgesia`, `procedural_pain_management`, `psychosocial_support`, `caregiver_education`
- icd11_rationale: Cancer pain guidance (adult Part A + paediatric Part B) is primarily symptom and supportive-care focused across cancer types, so the narrowest disease scope is chronic cancer-related pain rather than all malignant neoplasm codes.
- cpg_scope_rationale (adult, Part A): This guideline covers chronic cancer-related pain across solid tumours, haematological malignancies, nociceptive pain, neuropathic pain, visceral pain, somatic pain, bone pain, breakthrough pain, treatment-related pain, advanced disease pain, and palliative pain presentations. Relevant patient population includes adults with active cancer, metastatic disease, cancer survivorship pain, or end-of-life cancer pain requiring structured pain assessment and analgesic management. Clinical decisions and interventions include pain screening, multidimensional assessment, analgesic ladder use, non-opioid analgesia, opioid initiation, opioid titration, opioid rotation, breakthrough dosing, adverse-effect management, adjuvant analgesia, interventional pain procedure referral, radiotherapy coordination, psychosocial support, palliative care, misuse monitoring, and toxicity monitoring. Relevant comorbidities and key risk factors include renal impairment, hepatic impairment, frailty, older age, constipation, delirium risk, depression, bone metastases, neuropathy, and prior opioid exposure.
- cpg_scope_rationale (paediatric, Part B): This guideline covers paediatric and adolescent cancer-related pain including chronic cancer pain, procedure-related pain, breakthrough pain, treatment-related pain, neuropathic pain, bone pain, advanced malignancy pain, and palliative pain states. Relevant patient population includes infants, children, adolescents, caregivers, and families in oncology, inpatient, outpatient, procedural, and palliative care settings. Clinical decisions and interventions include developmentally appropriate pain assessment, behavioural pain tools, self-report tools, caregiver education, non-pharmacological support, paracetamol use, NSAID use, opioid selection, opioid titration, rescue dosing, procedural analgesia, sedation coordination, adjuvant medication, side-effect monitoring, psychosocial care, and end-of-life symptom control. Relevant comorbidities and key risk factors include young age, body weight, renal impairment, hepatic impairment, mucositis, neuropathy, anxiety, communication limitation, prior opioid exposure, and family support needs.
- ICD-11 hierarchy: Chapter 21 (Symptoms, signs or clinical findings) > Chronic pain > MG30.1 Chronic cancer-related pain.
- [x] Approve / [ ] Edit / [ ] Reject

---

## Cervical-Cancer(2nd Edition) ✅
- Rows in DB: 17
- Last classified: 2026-05-16T19:30:00+08:00
- Proposed icd11_scope: `2C77`, `2C77.0`, `2C77.1`, `2C77.2`, `2C77.3`, `2C77.Y`, `2C77.Z`
- Proposed procedure_scope: `cancer_referral`, `cancer_staging`, `surgical_management`, `chemoradiotherapy`, `follow_up_surveillance`, `recurrent_disease_management`, `palliative_care`
- icd11_rationale: The guideline gives diagnosis, staging, treatment, follow-up, recurrent disease, and palliative-care recommendations for malignant neoplasms of cervix uteri.
- cpg_scope_rationale: This guideline covers malignant neoplasms of the cervix uteri including squamous cell carcinoma, adenocarcinoma, adenosquamous carcinoma, locally advanced cervical cancer, early-stage cervical cancer, recurrent cervical cancer, metastatic cervical cancer, and palliative presentations. Relevant patient population includes women with suspected, newly diagnosed, staged, treated, recurrent, or advanced cervical cancer. Clinical decisions and interventions include symptom evaluation, cancer referral, colposcopy, biopsy, histopathological confirmation, FIGO staging, imaging, fertility-preserving treatment consideration, surgery, chemoradiotherapy, brachytherapy, systemic therapy, follow-up surveillance, recurrence management, complication management, survivorship care, and palliative care. Relevant comorbidities and key risk factors include persistent HPV infection, abnormal cervical screening, immunosuppression, HIV infection, smoking, reproductive history, renal compromise from obstruction, anaemia, and treatment toxicity.
- ICD-11 hierarchy: Chapter 02 (Neoplasms) > Malignant neoplasms of female genital organs > 2C77 Malignant neoplasms of cervix uteri.
- [x] Approve / [ ] Edit / [ ] Reject

---

## Colorectal-Carcinoma(2017) ✅
- Rows in DB: 10
- Last classified: 2026-05-16T19:30:00+08:00
- Proposed icd11_scope: `2B90`, `2B90.00`, `2B90.0Y`, `2B90.0Z`, `2B90.10`, `2B90.1Y`, `2B90.1Z`, `2B90.20`, `2B90.2Y`, `2B90.2Z`, `2B90.30`, `2B90.3Y`, `2B90.3Z`, `2B90.Y`, `2B90.Z`, `2B91`, `2B91.0`, `2B91.Y`, `2B91.Z`, `2B92`, `2B92.0`, `2B92.1`, `2B92.Y`, `2B92.Z`
- Proposed procedure_scope: `colorectal_screening`, `surveillance_colonoscopy`, `genetic_counselling`, `cancer_referral`, `cancer_staging`, `colorectal_surgery`, `chemotherapy`, `radiotherapy`, `follow_up_surveillance`
- icd11_rationale: The guideline covers screening, diagnosis, staging, treatment, and surveillance for colon, rectosigmoid, and rectal carcinoma.
- cpg_scope_rationale: This guideline covers colorectal carcinoma involving malignant neoplasms of colon, rectosigmoid junction, and rectum, including early-stage disease, locally advanced disease, metastatic disease, recurrent disease, hereditary-risk disease, and surveillance-detected disease. Relevant patient population includes adults with positive screening tests, colorectal symptoms, confirmed adenocarcinoma, high-risk family history, or post-treatment follow-up needs. Clinical decisions and interventions include screening, colonoscopy, biopsy, staging, imaging, molecular assessment, genetic assessment, multidisciplinary referral, surgery, neoadjuvant chemotherapy, adjuvant chemotherapy, radiotherapy for rectal cancer, metastatic disease management, stoma consideration, functional assessment, surveillance colonoscopy, recurrence detection, and palliative care. Relevant comorbidities and key risk factors include age, family history, hereditary colorectal cancer syndromes, inflammatory bowel disease, adenomatous polyps, obesity, diabetes mellitus, smoking, and prior malignancy.
- ICD-11 hierarchy: Chapter 02 (Neoplasms) > Malignant neoplasms of digestive organs > malignant neoplasms of colon, rectosigmoid junction, and rectum.
- [x] Approve / [ ] Edit / [ ] Reject

---

## Primary-Secondary-Prevention-of-CVD(2017) ✅
- Rows in DB: 15
- Last classified: 2026-05-16T19:30:00+08:00
- Proposed icd11_scope: `BA00`, `BA00.0`, `BA00.1`, `BA00.2`, `BA00.Y`, `BA00.Z`, `BA01`, `BA02`, `BA03`, `BA04`, `BA04.0`, `BA04.1`, `BA04.2`, `BA04.Y`, `BA04.Z`, `BA40`, `BA40.0`, `BA40.1`, `BA40.Y`, `BA40.Z`, `BA41`, `BA41.0`, `BA41.1`, `BA41.Z`, `BA42`, `BA42.0`, `BA42.1`, `BA42.Z`, `BD10`, `BD11`, `BD11.0`, `BD11.1`, `BD11.2`, `BD11.Z`, `BD12`, `BD13`, `8B11`, `8B11.0`, `8B11.1`, `8B11.20`, `8B11.21`, `8B11.22`, `8B11.2Y`, `8B11.2Z`, `8B11.3`, `8B11.40`, `8B11.41`, `8B11.42`, `8B11.43`, `8B11.44`, `8B11.50`, `8B11.51`, `8B11.5Z`, `5C80`, `5C80.00`, `5C80.01`, `5C80.0Z`, `5C80.1`, `5C80.2`, `5C80.3`, `5C80.Y`, `5C80.Z`, `5B81`, `5B81.00`, `5B81.01`, `5B81.1`, `5B81.Y`, `5B81.Z`, `BD40`, `BD40.0`, `BD40.1`, `BD40.2`, `BD40.3`, `BD40.Y`, `BD40.Z`, `BD50`, `BD50.00`, `BD50.01`, `BD50.02`, `BD50.0Y`, `BD50.0Z`, `BD50.10`, `BD50.11`, `BD50.12`, `BD50.1Y`, `BD50.1Z`, `BD50.20`, `BD50.21`, `BD50.22`, `BD50.2Y`, `BD50.2Z`, `BD50.30`, `BD50.31`, `BD50.32`, `BD50.3Y`, `BD50.3Z`, `BD50.40`, `BD50.41`, `BD50.4Y`, `BD50.4Z`, `BD50.50`, `BD50.51`, `BD50.52`, `BD50.5Y`, `BD50.5Z`, `BD50.Z`, `BC81.3`, `BC81.30`, `BC81.31`, `BC81.32`, `BC81.33`, `BC81.3Y`, `BC81.3Z`, `GB61`, `GB61.0`, `GB61.1`, `GB61.2`, `GB61.3`, `GB61.4`, `GB61.5`, `GB61.Z`
- Proposed procedure_scope: `cardiovascular_risk_assessment`, `lifestyle_modification`, `smoking_cessation`, `exercise_prescription`, `dietary_intervention`, `secondary_prevention`, `cardiac_rehabilitation`
- icd11_rationale: Integrated primary and secondary prevention guidance for major cardiovascular outcomes and risk drivers, including hypertension, ischaemic heart disease, heart failure, stroke, dyslipidaemia, obesity, peripheral vascular disease, atrial fibrillation, and chronic kidney disease.
- cpg_scope_rationale: This guideline covers primary and secondary prevention of cardiovascular disease across atherosclerotic and cardiometabolic conditions including hypertension, angina pectoris, myocardial infarction, chronic ischaemic heart disease, heart failure, atrial fibrillation, ischaemic stroke, peripheral arterial disease, aortic aneurysm, dissection risk states, dyslipidaemia, obesity, diabetes mellitus, and chronic kidney disease. Relevant patient population includes adults requiring first-event cardiovascular risk reduction and adults after cardiovascular events requiring recurrence prevention. Clinical decisions and interventions include absolute risk assessment, lifestyle modification, smoking cessation, dietary intervention, exercise prescription, weight control, lipid lowering, blood pressure control, glycaemic risk management, antiplatelet therapy consideration, anticoagulation context, cardiac rehabilitation, adherence monitoring, and long-term follow-up. Relevant comorbidities and key risk factors include hypertension, diabetes mellitus, dyslipidaemia, obesity, chronic kidney disease, atrial fibrillation, smoking, prior stroke, coronary artery disease, peripheral vascular disease, and metabolic syndrome.
- ICD-11 hierarchy: Chapter 11 (Circulatory) > Hypertension (BA00-BA04), IHD (BA40-BA42), Heart failure (BD10-BD13), Arrhythmia (BC81.3), Peripheral vascular disease (BD40, BD50); Chapter 08 (Nervous) > Ischaemic stroke (8B11); Chapter 05 (Metabolic) > Lipidaemias (5C80), Obesity (5B81); Chapter 16 (Genitourinary) > Chronic kidney disease (GB61).
- [x] Approve / [ ] Edit / [ ] Reject

---

## Stable-Coronary-Artery-Disease(2nd Edition) ✅
- Rows in DB: 14
- Last classified: 2026-05-16T19:30:00+08:00
- Proposed icd11_scope: `BA40`, `BA40.0`, `BA40.1`, `BA40.Y`, `BA40.Z`, `BA42`, `BA42.0`, `BA42.1`, `BA42.Z`
- Proposed procedure_scope: `cardiovascular_risk_assessment`, `non_invasive_cardiac_testing`, `coronary_angiography`, `antianginal_therapy`, `lifestyle_modification`, `secondary_prevention`, `revascularization_referral`
- icd11_rationale: Stable coronary artery disease guidance covers stable angina presentation and chronic ischaemic heart disease, including diagnostic testing, medical therapy, prevention, and referral for revascularisation when indicated.
- cpg_scope_rationale: This guideline covers stable coronary artery disease and chronic coronary syndrome including stable angina pectoris, chronic ischaemic heart disease, prior myocardial infarction with stable symptoms, suspected obstructive coronary disease, and recurrent exertional chest discomfort in stable clinical settings. Relevant patient population includes adults undergoing outpatient or non-emergency assessment for chest pain, exertional dyspnoea, known coronary artery disease, or cardiovascular risk requiring diagnostic and therapeutic planning. Clinical decisions and interventions include clinical probability assessment, resting testing, stress testing, coronary CT referral, invasive angiography referral, antianginal therapy, antiplatelet therapy, lipid lowering, blood pressure control, lifestyle modification, exercise prescription, cardiac rehabilitation, risk-factor management, and revascularisation referral. Relevant comorbidities and key risk factors include diabetes mellitus, hypertension, dyslipidaemia, chronic kidney disease, heart failure, smoking, obesity, and peripheral vascular disease.
- ICD-11 hierarchy: Chapter 11 (Diseases of the circulatory system) > Ischaemic heart diseases > BA40 Angina pectoris and BA42 Chronic ischaemic heart disease.
- [x] Approve / [ ] Edit / [ ] Reject

---

## Anaesthesia-Medication-Safety ✅
- Rows in DB: 7
- Last classified: 2026-05-16T19:30:00+08:00
- Proposed icd11_scope: (none)
- Proposed procedure_scope: `anaesthetic_medication_safety`, `medication_labelling`, `medication_storage`, `high_alert_medication`, `drug_allergy_management`, `malignant_hyperthermia_management`, `safe_medication_practice`, `medication_waste_management`
- icd11_rationale: The guideline is procedure and safety focused for medication handling in anaesthesia practice, not disease-specific treatment.
- cpg_scope_rationale: This guideline covers safe use of medications in anaesthesia practice including anaesthetic drugs, sedatives, analgesics, neuromuscular blocking agents, vasoactive agents, emergency drugs, high-alert medications, drug preparation, and medication governance. Relevant patient population includes patients exposed to anaesthetic medication in operating theatre, procedural sedation, obstetric anaesthesia, paediatric anaesthesia, critical care, and recovery settings. Clinical decisions and interventions include medication prescribing, medication preparation, labelling, storage, standardisation, double-checking, allergy verification, look-alike sound-alike prevention, high-alert medication handling, syringe safety, infusion safety, controlled drug governance, malignant hyperthermia preparedness, medication waste management, incident reporting, and quality improvement. Relevant comorbidities and key risk factors include paediatric dosing, pregnancy, renal impairment, hepatic impairment, drug allergy, polypharmacy, emergency anaesthesia, difficult airway, haemodynamic instability, and human-factor error.
- ICD-11 hierarchy: N/A (procedure-only anaesthesia medication safety guideline).
- [x] Approve / [ ] Edit / [ ] Reject

---

## Obesity-Management(2023)
- Rows in DB: 5 of 10 sections ingested (Sections 5-9 pending re-ingestion)
- Last classified: 2026-05-16T19:30:00+08:00
- Proposed icd11_scope: `5B80`, `5B80.0`, `5B80.00`, `5B80.01`, `5B80.0Z`, `5B80.1`, `5B81`, `5B81.0`, `5B81.00`, `5B81.01`, `5B81.1`, `5B81.Y`, `5B81.Z`
- Proposed procedure_scope: `bmi_assessment`, `waist_circumference_assessment`, `lifestyle_modification`, `dietary_intervention`, `exercise_prescription`, `weight_monitoring`, `anti_obesity_pharmacotherapy`, `bariatric_surgery_referral`
- icd11_rationale: Obesity CPG covers diagnosis, risk stratification, prevention, lifestyle therapy, pharmacotherapy, and bariatric referral across overweight and obesity in children, adolescents, and adults.
- cpg_scope_rationale: This guideline covers overweight and obesity as chronic adiposity-related nutritional and metabolic disease including adult obesity, childhood obesity, adolescent obesity, drug-induced obesity, obesity due to energy imbalance, severe obesity, obesity with cardiometabolic complications, and unspecified obesity presentations. Relevant patient population includes children, adolescents, and adults undergoing BMI assessment, waist circumference assessment, comorbidity assessment, behavioural assessment, psychosocial assessment, prevention, or treatment. Clinical decisions and interventions include diagnosis, risk stratification, lifestyle modification, medical nutrition therapy, physical activity, behavioural intervention, weight monitoring, pharmacotherapy, bariatric surgery referral, childhood obesity management, relapse prevention, and long-term follow-up. Relevant comorbidities and key risk factors include type 2 diabetes mellitus, hypertension, dyslipidaemia, obstructive sleep apnoea, cardiovascular disease, non-alcoholic fatty liver disease, osteoarthritis, infertility, depression, and chronic kidney disease.
- ICD-11 hierarchy: Chapter 05 (Endocrine, nutritional or metabolic diseases) > Overweight (5B80, 5B80.0, 5B80.1) and Obesity (5B81), including obesity due to energy imbalance in children/adolescents and adults (5B81.0, 5B81.00, 5B81.01), drug-induced obesity (5B81.1), other specified obesity (5B81.Y), and obesity unspecified (5B81.Z). Obesity codes verified against WHO ICD-11 2024-01 MMS API; overweight codes proposed for Step 05 ingestion coverage.
- [x] Approve / [ ] Edit / [ ] Reject

---

## T2-Diabetes-Mellitus(6th-Edition)
- Rows in DB: pending ingestion (source folder has 17 sections, 0 ingested)
- Last classified: 2026-05-16T19:30:00+08:00
- Proposed icd11_scope: `5A11`
- Proposed procedure_scope: `glycaemic_assessment`, `hba1c_monitoring`, `lifestyle_modification`, `dietary_intervention`, `oral_glucose_lowering_therapy`, `insulin_therapy`, `self_monitoring_blood_glucose`, `cardiovascular_risk_assessment`, `diabetes_complication_screening`, `sick_day_management`
- icd11_rationale: The Type 2 Diabetes Mellitus guideline is disease-specific for diagnosis, glycaemic targets, non-pharmacological care, glucose-lowering therapy, complication screening, and long-term follow-up.
- cpg_scope_rationale: This guideline covers type 2 diabetes mellitus as a chronic metabolic disease of hyperglycaemia, insulin resistance, progressive beta-cell dysfunction, and multisystem vascular risk. Relevant patient population includes adults with suspected, newly diagnosed, established, uncontrolled, complicated, or long-standing type 2 diabetes in primary care, endocrine, inpatient, and chronic disease management settings. Clinical decisions and interventions include screening, diagnosis, HbA1c monitoring, glucose monitoring, glycaemic target selection, lifestyle therapy, medical nutrition therapy, oral glucose-lowering therapy, injectable therapy, insulin therapy, hypoglycaemia prevention, sick-day management, self-monitoring, cardiovascular risk reduction, renal protection, retinopathy screening, neuropathy screening, diabetic foot care, mental health care, complication screening, and follow-up. Relevant comorbidities and key risk factors include obesity, hypertension, dyslipidaemia, chronic kidney disease, atherosclerotic cardiovascular disease, heart failure, peripheral arterial disease, neuropathy, retinopathy, nephropathy, and diabetic foot risk.
- ICD-11 hierarchy: Chapter 05 (Endocrine, nutritional or metabolic diseases) > Diabetes mellitus > 5A11 Type 2 diabetes mellitus. Code verified against WHO ICD-11 2024-01 MMS API.
- [x] Approve / [ ] Edit / [ ] Reject

---

## Thyroid-Disorders(2019) ✅
- Rows in DB: 12
- Last classified: 2026-05-16T19:30:00+08:00
- Proposed icd11_scope: `5A00`, `5A00.0`, `5A00.1`, `5A00.2`, `5A00.Z`, `5A01`, `5A01.0`, `5A01.1`, `5A01.2`, `5A01.Z`, `5A02`, `5A02.0`, `5A02.1`, `5A02.2`, `5A02.3`, `5A02.4`, `5A02.5`, `5A02.6`, `5A02.Y`, `5A02.Z`, `5A03`, `5A03.0`, `5A03.1`, `5A03.2`, `5A03.Y`, `5A03.Z`, `5A0Y`, `5A0Z`
- Proposed procedure_scope: `thyroid_function_testing`, `thyroid_autoantibody_testing`, `thyroid_ultrasound`, `thyroid_nodule_assessment`, `levothyroxine_therapy`, `antithyroid_drug_therapy`, `radioactive_iodine_referral`, `endocrine_referral`, `thyroid_follow_up_monitoring`
- icd11_rationale: Thyroid disorders guidance covers hypothyroidism, nontoxic goitre, thyrotoxicosis, thyroiditis, and specified or unspecified thyroid gland or thyroid hormone system disorders.
- cpg_scope_rationale: This guideline covers disorders of the thyroid gland and thyroid hormone system including hypothyroidism, hyperthyroidism, thyrotoxicosis, Graves disease, toxic nodular goitre, non-toxic goitre, thyroid nodules, thyroiditis, drug-induced thyroid dysfunction, thyroid eye disease, thyroid emergencies, perioperative thyroid disease, pregnancy-related thyroid considerations, and specified or unspecified thyroid disorders. Relevant patient population includes adults and selected special groups with abnormal thyroid function tests, neck swelling, thyroid symptoms, ophthalmopathy, nodules, or treatment complications. Clinical decisions and interventions include thyroid function testing, thyroid autoantibody testing, ultrasound, radionuclide referral, cytology referral, levothyroxine therapy, antithyroid drug therapy, radioactive iodine referral, surgery referral, monitoring, emergency management, follow-up, and specialist referral. Relevant comorbidities and key risk factors include pregnancy, cardiovascular disease, osteoporosis risk, diabetes mellitus, autoimmune disease, amiodarone exposure, lithium exposure, renal disease, and older age.
- ICD-11 hierarchy: Chapter 05 (Endocrine, nutritional or metabolic diseases) > Disorders of the thyroid gland or thyroid hormones system: hypothyroidism (5A00 and direct child categories), nontoxic goitre (5A01 and direct child categories), thyrotoxicosis (5A02 and direct child categories), thyroiditis (5A03 and direct child categories), other specified thyroid disorders (5A0Y), and unspecified thyroid disorders (5A0Z). Codes verified against WHO ICD-11 2024-01 MMS API where queried; `5A0` itself is not a valid MMS code.
- [x] Approve / [ ] Edit / [ ] Reject

---

## Diabetes-in-Pregnancy(2017) ✅
- Rows in DB: 13
- Last classified: 2026-05-16T19:30:00+08:00
- Proposed icd11_scope: `JA63`, `JA63.0`, `JA63.1`, `JA63.2`, `JA63.Y`, `JA63.Z`, `5A10`, `5A11`
- Proposed procedure_scope: `preconception_counselling`, `antenatal_diabetes_screening`, `ogtt`, `glucose_monitoring`, `insulin_therapy`, `medical_nutrition_therapy`, `fetal_surveillance`, `delivery_planning`, `postpartum_diabetes_screening`
- icd11_rationale: Diabetes in pregnancy guidance covers pre-existing type 1 and type 2 diabetes in pregnancy, gestational diabetes, antenatal glucose monitoring and therapy, fetal surveillance, delivery planning, and postpartum screening.
- cpg_scope_rationale: This guideline covers diabetes mellitus in pregnancy including pre-existing type 1 diabetes, pre-existing type 2 diabetes, gestational diabetes mellitus, diabetes first detected during pregnancy, postpartum glucose risk, and fetal or neonatal complications related to maternal hyperglycaemia. Relevant patient population includes women planning pregnancy, pregnant patients, intrapartum patients, postpartum women, fetuses, and neonates affected by maternal diabetes. Clinical decisions and interventions include preconception counselling, antenatal screening, oral glucose tolerance testing, glycaemic target selection, medical nutrition therapy, glucose self-monitoring, insulin therapy, medication safety, fetal surveillance, timing of delivery, mode of delivery, intrapartum glucose management, neonatal monitoring, breastfeeding support, postpartum diabetes screening, and long-term prevention. Relevant comorbidities and key risk factors include obesity, previous gestational diabetes, family history, advanced maternal age, polycystic ovarian syndrome, macrosomia, hypertension, type 1 diabetes complications, and type 2 diabetes complications.
- ICD-11 hierarchy: Chapter 18 (Pregnancy, childbirth or the puerperium) > Diabetes mellitus in pregnancy (JA63) with pre-existing type 1 diabetes in pregnancy (JA63.0), pre-existing type 2 diabetes in pregnancy (JA63.1), diabetes mellitus arising in pregnancy (JA63.2), other specified (JA63.Y), and unspecified (JA63.Z); plus underlying Chapter 05 diabetes codes 5A10 and 5A11. Codes verified against WHO ICD-11 2024-01 MMS API.
- [x] Approve / [ ] Edit / [ ] Reject

---

## Type-1-Diabetes-Mellitus-Children_Adolescents(2016) ✅
- Rows in DB: 19
- Last classified: 2026-05-16T19:30:00+08:00
- Proposed icd11_scope: `5A10`
- Proposed procedure_scope: `paediatric_diabetes_education`, `insulin_therapy`, `glucose_monitoring`, `hba1c_monitoring`, `hypoglycaemia_management`, `diabetic_ketoacidosis_prevention`, `sick_day_management`, `school_care_planning`, `transition_to_adult_care`
- icd11_rationale: The paediatric and adolescent Type 1 Diabetes Mellitus guideline is disease-specific for type 1 diabetes diagnosis, insulin treatment, monitoring, acute complication prevention, family education, school planning, and transition care.
- cpg_scope_rationale: This guideline covers type 1 diabetes mellitus in children and adolescents including autoimmune beta-cell failure, insulin-dependent diabetes, new diagnosis, established paediatric diabetes, hypoglycaemia, diabetic ketoacidosis risk, psychosocial burden, school care needs, and transition to adult services. Relevant patient population includes infants, children, adolescents, families, caregivers, schools, and healthcare teams managing paediatric type 1 diabetes. Clinical decisions and interventions include diagnosis, insulin initiation, insulin adjustment, basal-bolus therapy, pump therapy, glucose monitoring, HbA1c target selection, nutrition therapy, carbohydrate counting, exercise guidance, hypoglycaemia prevention, hypoglycaemia treatment, diabetic ketoacidosis prevention, sick-day management, psychosocial support, education, school care planning, complication screening, referral, and transition care. Relevant comorbidities and key risk factors include coeliac disease, thyroid autoimmunity, obesity, mental health disorders, puberty-related insulin resistance, infections, and long-term microvascular risk.
- ICD-11 hierarchy: Chapter 05 (Endocrine, nutritional or metabolic diseases) > Diabetes mellitus > 5A10 Type 1 diabetes mellitus. Code verified against WHO ICD-11 2024-01 MMS API.
- [x] Approve / [ ] Edit / [ ] Reject

---

## Growth-Hormone-Children-Adults(2010) ✅
- Rows in DB: 8
- Last classified: 2026-05-16T19:30:00+08:00
- Proposed icd11_scope: `5A61.3`, `5B11`, `MG44.12`, `MG44.13`
- Proposed procedure_scope: `auxology_assessment`, `growth_velocity_monitoring`, `endocrine_referral`, `growth_hormone_stimulation_testing`, `growth_hormone_therapy`, `igf1_monitoring`, `adverse_effect_monitoring`, `treatment_response_monitoring`
- icd11_rationale: Growth hormone guidance is scoped to confirmed growth hormone deficiency and to early growth-presentation workflows where patients present before endocrine stimulation testing confirms the diagnosis.
- cpg_scope_rationale: This guideline covers growth hormone disorders and growth hormone therapy decision making including confirmed growth hormone deficiency, short stature, impaired growth velocity, delayed growth and puberty, adult growth hormone deficiency, transition-phase growth hormone deficiency, and selected non-GHD indications. Relevant patient population includes children with growth failure, adolescents requiring transition assessment, and adults with pituitary disease, hypothalamic disease, low IGF-1, or suspected growth hormone deficiency. Clinical decisions and interventions include auxology assessment, height velocity monitoring, bone age assessment, endocrine referral, growth hormone stimulation testing, pituitary assessment, IGF-1 monitoring, treatment eligibility assessment, recombinant growth hormone dosing, adverse-effect monitoring, treatment response monitoring, discontinuation decision, transition care, and adult replacement decision. Relevant comorbidities and key risk factors include pituitary tumours, cranial irradiation, traumatic brain injury, genetic syndromes, chronic systemic disease, delayed puberty, obesity, diabetes risk, and intracranial hypertension.
- ICD-11 hierarchy: Chapter 05 (Endocrine, nutritional or metabolic diseases) > Hypofunction or certain other specified disorders of pituitary gland > 5A61.3 Growth hormone deficiency; plus nutritional/developmental growth presentation 5B11 Short stature, not elsewhere classified; plus Chapter 21 symptom presentation codes MG44.12 Short stature of child and MG44.13 Constitutional delay of growth and puberty for initial workup routing. Endocrine codes verified against WHO ICD-11 2024-01 MMS API; MG44.12 and MG44.13 proposed for Step 05 ingestion coverage.
- [x] Approve / [ ] Edit / [ ] Reject

---

## Nasopharyngeal-Carcinoma ✅
- Rows in DB: 11
- Last classified: 2026-05-22T00:00:00+08:00
- Proposed icd11_scope: `2B6B`, `2B6B.0`, `2B6B.1`, `2B6B.Y`, `2B6B.Z`
- Proposed procedure_scope: `cancer_referral`, `cancer_staging`, `chemoradiotherapy`, `surgical_management`, `supportive_care`, `recurrent_disease_management`, `follow_up_surveillance`, `palliative_care`
- icd11_rationale: The guideline covers diagnosis, staging, treatment (chemoradiotherapy/surgery), supportive care, management of complications, and prognosis/follow-up for malignant neoplasms of the nasopharynx.
- cpg_scope_rationale: This guideline covers malignant neoplasms of the nasopharynx including nasopharyngeal squamous cell carcinoma, non-keratinising carcinoma, undifferentiated carcinoma, unspecified epithelial nasopharyngeal carcinoma, locally advanced disease, recurrent disease, and metastatic presentations. Relevant patient population includes adults with suspected or confirmed nasopharyngeal carcinoma presenting with neck mass, epistaxis, nasal obstruction, hearing change, cranial nerve involvement, or recurrence after prior treatment. Clinical decisions and interventions include nasoendoscopy, biopsy, histopathology, EBV assessment, cross-sectional imaging, staging, radiotherapy, chemoradiotherapy, induction chemotherapy, surgical salvage, supportive care, recurrent-disease management, follow-up surveillance, and palliative care. Relevant comorbidities and key risk factors include EBV infection, family history, dietary nitrosamine exposure, smoking, advanced nodal stage, distant metastasis, and treatment-related toxicity.
- ICD-11 hierarchy: Chapter 02 (Neoplasms) > Malignant neoplasms of head, face or neck > 2B6B Malignant neoplasms of nasopharynx, with squamous cell carcinoma (2B6B.0), unspecified epithelial (2B6B.1), other specified (2B6B.Y), and unspecified (2B6B.Z). Codes verified against the live icd11_codes table 2026-05-22.
- [x] Approve / [ ] Edit / [ ] Reject

---

<!--
# ICD-11 MMS Scope Expansion Audit

Source: WHO ICD-11 2024-01 MMS API

Scope lines changed: 18

### Parent Codes Expanded
- `2B90` Malignant neoplasms of colon: 2B90.00, 2B90.0Y, 2B90.0Z, 2B90.10, 2B90.1Y, 2B90.1Z, 2B90.20, 2B90.2Y, 2B90.2Z, 2B90.30, 2B90.3Y, 2B90.3Z, 2B90.Y, 2B90.Z
- `2B91` Malignant neoplasms of rectosigmoid junction: 2B91.0, 2B91.Y, 2B91.Z
- `2B92` Malignant neoplasms of rectum: 2B92.0, 2B92.1, 2B92.Y, 2B92.Z
- `2C61` Invasive carcinoma of breast: 2C61.0, 2C61.1, 2C61.2, 2C61.3, 2C61.4
- `2C77` Malignant neoplasms of cervix uteri: 2C77.0, 2C77.1, 2C77.2, 2C77.3, 2C77.Y, 2C77.Z
- `5B81` Obesity: 5B81.00, 5B81.01, 5B81.1, 5B81.Y, 5B81.Z
- `5C80` Hyperlipoproteinaemia: 5C80.00, 5C80.01, 5C80.0Z, 5C80.1, 5C80.2, 5C80.3, 5C80.Y, 5C80.Z
- `5C81` Hypolipoproteinaemia: 5C81.0, 5C81.1, 5C81.Y, 5C81.Z
- `8B11` Cerebral ischaemic stroke: 8B11.0, 8B11.1, 8B11.20, 8B11.21, 8B11.22, 8B11.2Y, 8B11.2Z, 8B11.3, 8B11.40, 8B11.41, 8B11.42, 8B11.43, 8B11.44, 8B11.50, 8B11.51, 8B11.5Z
- `BA00` Essential hypertension: BA00.0, BA00.1, BA00.2, BA00.Y, BA00.Z
- `BA04` Secondary hypertension: BA04.0, BA04.1, BA04.2, BA04.Y, BA04.Z
- `BA40` Angina pectoris: BA40.0, BA40.1, BA40.Y, BA40.Z
- `BA41` Acute myocardial infarction: BA41.0, BA41.1, BA41.Z
- `BA42` Subsequent myocardial infarction: BA42.0, BA42.1, BA42.Z
- `BB01` Pulmonary hypertension: BB01.0, BB01.1, BB01.2, BB01.3, BB01.4, BB01.5, BB01.Z
- `BC81.3` Atrial fibrillation: BC81.30, BC81.31, BC81.32, BC81.33, BC81.3Y, BC81.3Z
- `BD11` Left ventricular failure: BD11.0, BD11.1, BD11.2, BD11.Z
- `BD40` Atherosclerotic chronic arterial occlusive disease: BD40.0, BD40.1, BD40.2, BD40.3, BD40.Y, BD40.Z
- `BD50` Aortic aneurysm or dissection: BD50.00, BD50.01, BD50.02, BD50.0Y, BD50.0Z, BD50.10, BD50.11, BD50.12, BD50.1Y, BD50.1Z, BD50.20, BD50.21, BD50.22, BD50.2Y, BD50.2Z, BD50.30, BD50.31, BD50.32, BD50.3Y, BD50.3Z, BD50.40, BD50.41, BD50.4Y, BD50.4Z, BD50.50, BD50.51, BD50.52, BD50.5Y, BD50.5Z, BD50.Z
- `GB61` Chronic kidney disease: GB61.0, GB61.1, GB61.2, GB61.3, GB61.4, GB61.5, GB61.Z
- `MG30.1` Chronic cancer related pain: MG30.10, MG30.11, MG30.1Y, MG30.1Z

### Changed Scope Lines
- Line 12: 6 codes -> 7 codes (parent retained with child block)
- Line 23: 12 codes -> 13 codes (parent retained with child block)
- Line 34: 109 codes -> 122 codes (parent retained with child block)
- Line 45: 14 codes -> 16 codes (parent retained with child block)
- Line 67: 10 codes -> 11 codes (parent retained with child block)
- Line 78: 13 codes -> 15 codes (parent retained with child block)
- Line 88: 16 codes -> 17 codes (parent retained with child block)
- Line 99: 7 codes -> 9 codes (parent retained with child block)
- Line 110: 3 codes -> 4 codes (parent retained with child block)
- Line 130: 10 codes -> 13 codes (parent retained with child block)
- Line 163: 7 codes -> 8 codes (parent retained with child block)
- Line 185: 108 codes -> 121 codes (parent retained with child block)
- Line 196: 4 codes -> 5 codes (parent retained with child block)
- Line 207: 4 codes -> 5 codes (parent retained with child block)
- Line 218: 6 codes -> 7 codes (parent retained with child block)
- Line 229: 21 codes -> 24 codes (parent retained with child block)
- Line 240: 108 codes -> 121 codes (parent retained with child block)
- Line 251: 7 codes -> 9 codes (parent retained with child block)
-->
