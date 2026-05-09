# CPG Scope Review — regenerated 2026-05-08T14:01:32.307320+00:00

Source of truth is the `documents` table. Edit the lists below to correct any scope, then mark Approve / Edit / Reject. The Step 04 verifier will parse this file.

Groups: 16

---

## Atrial-Fibrillation(2012)
- Rows in DB: 10
- Last classified: 2026-05-08T13:48:07.294617+00:00
- Proposed icd11_scope: `BC81.3`
- Proposed procedure_scope: `referral_pathway`, `clinical_audit`, `quality_assurance`, `warfarin_initiation`, `inr_monitoring`, `dose_adjustment`, `perioperative_bridging`
- Rationale: Specific AF guidance maps to BC81.3 (Atrial fibrillation) under the cardiac arrhythmia hierarchy.
- ICD-11 hierarchy: Chapter 11 (Diseases of the circulatory system) > Block BC60-BC9Z (Cardiac arrhythmia) > Category BC80-BC8Z (Supraventricular rhythm disturbance) > Section BC81 (Supraventricular tachyarrhythmia) > Specific BC81.3 (Atrial fibrillation)
- [ ] Approve / [x] Edit / [ ] Reject

---

## Breast-Cancer(3rd Edition)
- Rows in DB: 14
- Last classified: 2026-05-08T13:48:07.294617+00:00
- Proposed icd11_scope: `2C60`, `2C61`, `2C62`, `2C63`, `2C64`, `2C65`, `2C6Y`, `2C6Z`
- Proposed procedure_scope: (none)
- Rationale: Malignant neoplasms of breast (2C60-2C6Z).
- ICD-11 hierarchy: Chapter 02 (Neoplasms) > Malignant neoplasms of breast range 2C60-2C6Z > Verified examples from API search include 2C60, 2C63, 2C65, 2C6Y, and 2C6Z
- [x] Approve / [ ] Edit / [ ] Reject

---

## CVD-Prevention-Women(2016)
- Rows in DB: 8
- Last classified: 2026-05-08T14:01:21.563348+00:00
- Proposed icd11_scope: `BA00`, `BA01`, `BA02`, `BA03`, `BA04`, `BA40`, `BA41`, `BA42`, `BD10`, `BD11`, `BD12`, `BD13`, `8B11`, `5C80`, `5A11`, `BD40`, `BD50`, `BC81.3`, `5B81`, `GB61`
- Proposed procedure_scope: (none)
- Rationale: Systemic cardiovascular prevention strategy covering major circulatory endpoints and metabolic drivers, including chronic kidney disease as a high-risk cardiovascular equivalent.
- ICD-11 hierarchy: Chapter 11 (Circulatory) -> Hypertension (BA00-BA04), IHD (BA40-BA42), Heart Failure (BD10-BD13), Arrhythmia (BC81.3), Peripheral Vascular (BD40, BD50); Chapter 05 (Metabolic) -> Diabetes (5A11), Dyslipidaemia (5C80), Obesity (5B81), Metabolic Syndrome (5C40); Chapter 08 (Nervous) -> Ischaemic Stroke (8B11); Chapter 16 (Genitourinary) -> Chronic Kidney Disease (GB61)
- [ ] Approve / [x] Edit / [ ] Reject

---

## Dyslipidaemia(6th-Edition)
- Rows in DB: 15
- Last classified: 2026-05-08T13:48:07.294617+00:00
- Proposed icd11_scope: `5C80`, `5C81`, `5C8Y`, `5C8Z`
- Proposed procedure_scope: (none)
- Rationale: Comprehensive management of lipoprotein metabolism disorders, including primary and secondary hypercholesterolaemia, hypertriglyceridaemia, and mixed dyslipidaemias.
- ICD-11 hierarchy: Chapter 05 (Endocrine, nutritional or metabolic diseases) > Metabolic disorders > Disorders of lipoprotein metabolism or other lipidaemias range 5C80-5C8Z
- [ ] Approve / [x ] Edit / [ ] Reject

---

## Erectile-Dysfunction
- Rows in DB: 13
- Last classified: 2026-05-08T13:48:07.294617+00:00
- Proposed icd11_scope: `HA01.10`, `HA01.11`, `HA01.12`, `HA01.13`, `HA01.1Z`
- Proposed procedure_scope: (none)
- Rationale: Direct mapping for male erectile dysfunction, covering lifelong, acquired, situational, and generalized presentations.
- ICD-11 hierarchy: Chapter 17 (Conditions related to sexual health) > Sexual dysfunctions > Sexual arousal dysfunctions > Male erectile dysfunction range HA01.10-HA01.1Z
- [ ] Approve / [x] Edit / [ ] Reject

---

## Heart-Failure(5th Edition)
- Rows in DB: 24
- Last classified: 2026-05-08T13:48:07.294617+00:00
- Proposed icd11_scope: `BD10`, `BD11`, `BD12`, `BD13`, `BD14`, `BD1Y`, `BD1Z`
- Proposed procedure_scope: (none)
- Rationale: Comprehensive management of the heart failure clinical syndrome, including congestive, left ventricular, right ventricular, biventricular, and unspecified heart failure presentations.
- ICD-11 hierarchy: Chapter 11 (Diseases of the circulatory system) > Heart failure range BD10-BD1Z
- [ ] Approve / [x] Edit / [ ] Reject

---

## Hypertension(5th Edition)
- Rows in DB: 15
- Last classified: 2026-05-08T13:48:07.294617+00:00
- Proposed icd11_scope: `BA00`, `BA01`, `BA02`, `BA03`, `BA04`
- Proposed procedure_scope: (none)
- Rationale: Hypertensive diseases: essential, secondary, hypertensive crisis (BA00-BA04).
- [x] Approve / [ ] Edit / [ ] Reject

---

## Ischaemic-Stroke(3rd Edition)
- Rows in DB: 18
- Last classified: 2026-05-08T13:17:44.569519+00:00
- Proposed icd11_scope: `8B11`
- Proposed procedure_scope: `endovascular_thrombectomy`, `stroke_workflow`, `revascularization`
- Rationale: The 3rd Edition CPG specifically manages acute cerebral ischaemic stroke (8B11) and reperfusion therapy. 8B10 (TIA) is excluded as it has distinct management; 8B20 is a pre-imaging triage code; 8B25 (Late effects) covers rehabilitation, not acute treatment.
- ICD-11 hierarchy: Chapter 08 (Nervous system diseases) > Cerebrovascular diseases > Cerebral ischaemia > 8B11 Cerebral ischaemic stroke
- [ ] Approve / [x] Edit / [ ] Reject

---

## NSTE-ACS(3rd Edition)
- Rows in DB: 12
- Last classified: 2026-05-08T13:48:07.294617+00:00
- Proposed icd11_scope: `BA40`, `BA41`
- Proposed procedure_scope: `cardiac_rehabilitation`, `exercise_training`, `smoking_cessation`, `lifestyle_modification`
- Rationale: Non-ST-elevation acute coronary syndromes: unstable angina (BA40) and acute MI (BA41). NSTE-ACS is differentiated from STEMI by the absence of persistent ST-segment elevation and sub-classified based on troponin.
- ICD-11 hierarchy: Chapter 11 (Diseases of the circulatory system) > Ischaemic heart diseases > Acute ischaemic heart disease > BA40 Angina pectoris and BA41 Acute myocardial infarction
- [x] Approve / [ ] Edit / [ ] Reject

---

## NSTEMI(2011)
- Rows in DB: 10
- Last classified: 2026-05-08T13:48:07.294617+00:00
- Proposed icd11_scope: `BA41`
- Proposed procedure_scope: (none)
- Rationale: Acute myocardial infarction — non-ST-elevation subtype (BA41).
- [X] Approve / [ ] Edit / [ ] Reject

---

## Patient-Safety-Minimal-Monitoring
- Rows in DB: 9
- Last classified: 2026-05-08T13:17:49.790774+00:00
- Proposed icd11_scope: (none)
- Proposed procedure_scope: `pre_op_assessment`, `anaesthetic_equipment_safety`, `anaesthetic_safety`
- Rationale: The CPG focuses on anaesthesia safety, equipment checks, and pre-operative assessment rather than specific diseases.
- [x] Approve / [ ] Edit / [ ] Reject

---

## Percutaneous-Coronary-Intervention
- Rows in DB: 9
- Last classified: 2026-05-08T14:01:21.563348+00:00
- Proposed icd11_scope: `BA40`, `BA41`, `BA42`
- Proposed procedure_scope: `percutaneous_coronary_intervention`, `coronary_angiography`, `coronary_stenting`, `intravascular_imaging`
- Rationale: Ischaemic heart disease conditions treated by PCI: unstable angina (BA40), acute myocardial infarction (BA41), chronic ischaemic heart disease (BA42).
- ICD-11 hierarchy: Chapter 11 (Diseases of the circulatory system) > Ischaemic heart diseases > BA40 Angina pectoris, BA41 Acute myocardial infarction, and BA42 Chronic ischaemic heart disease
- [x] Approve / [ ] Edit / [ ] Reject

---

## Pre-Anaesthetic-Assessment
- Rows in DB: 8
- Last classified: 2026-05-08T13:17:54.174182+00:00
- Proposed icd11_scope: (none)
- Proposed procedure_scope: `pre_op_assessment`, `investigation_selection`, `risk_assessment`, `anaesthetic_planning`
- Rationale: CPG focuses on pre-anaesthetic assessment, investigation selection based on patient factors and surgery type, risk assessment and anaesthetic planning, not on specific disease treatment.
- ICD-11 hierarchy: N/A (Focuses on perioperative procedures and safety planning rather than specific disease classifications)
- [x] Approve / [ ] Edit / [ ] Reject

---

## Prevention-Diagnosis-Management-of-IE
- Rows in DB: 9
- Last classified: 2026-05-09T14:18:42.102345+00:00
- Proposed icd11_scope: `BB40`, `BB41`, `BB42`, `BB4Y`, `BB4Z`
- Proposed procedure_scope: (none)
- Rationale: Captures the full spectrum of acute/subacute endocarditis including infectious (BB40), related inflammations (BB41, BB42), and catch-all categories for other specified (BB4Y) or unspecified (BB4Z) presentations.
- ICD-11 hierarchy: Chapter 11 (Diseases of the circulatory system) > Endocarditis > Acute or subacute endocarditis range BB40-BB4Z.
- [x] Approve / [ ] Edit / [ ] Reject

---

## Pulmonary-Arterial-Hypertension(2011)
- Rows in DB: 20
- Last classified: 2026-05-09T14:25:10.112456+00:00
- Proposed icd11_scope: `BB01`
- Proposed procedure_scope: (none)
- Rationale: Pulmonary arterial hypertension (Group 1). This stem code covers idiopathic, heritable, and associated forms of PAH defined in the 2011 CPG.
- ICD-11 hierarchy: Chapter 11 (Diseases of the circulatory system) > Pulmonary heart disease or diseases of pulmonary circulation > Pulmonary hypertension > BB01 Pulmonary arterial hypertension.
- [x] Approve / [ ] Edit / [ ] Reject

---

## STEMI(4th Edition)
- Rows in DB: 18
- Last classified: 2026-05-09T14:26:05.883120+00:00
- Proposed icd11_scope: `BA41.0`
- Proposed procedure_scope: (none)
- Rationale: Specifically identifies ST-elevation myocardial infarction. The parent code BA41 is too broad as it includes NSTEMI (BA41.1), which is managed under a different clinical pathway.
- ICD-11 hierarchy: Chapter 11 (Diseases of the circulatory system) > Ischaemic heart disease > Acute myocardial infarction > BA41.0 ST elevation myocardial infarction.
- [ ] Approve / [x] Edit / [ ] Reject