# CPG Scope Review — regenerated 2026-05-08T14:01:32.307320+00:00

Source of truth is the `documents` table. Edit the lists below to correct any scope, then mark Approve / Edit / Reject. The Step 04 verifier will parse this file.

Groups: 24

---

## Atrial-Fibrillation(2012)
- Rows in DB: 10
- Last classified: 2026-05-08T13:48:07.294617+00:00
- Proposed icd11_scope: `BC81.30`, `BC81.31`, `BC81.32`, `BC81.33`, `BC81.3Y`, `BC81.3Z`
- Proposed procedure_scope: `referral_pathway`, `clinical_audit`, `quality_assurance`, `warfarin_initiation`, `inr_monitoring`, `dose_adjustment`, `perioperative_bridging`
- Rationale: Specific AF guidance maps to BC81.3 (Atrial fibrillation) under the cardiac arrhythmia hierarchy.
- ICD-11 hierarchy: Chapter 11 (Diseases of the circulatory system) > Block BC60-BC9Z (Cardiac arrhythmia) > Category BC80-BC8Z (Supraventricular rhythm disturbance) > Section BC81 (Supraventricular tachyarrhythmia) > Specific BC81.3 (Atrial fibrillation)
- [ ] Approve / [x] Edit / [ ] Reject

---

## Breast-Cancer(3rd Edition)
- Rows in DB: 14
- Last classified: 2026-05-08T13:48:07.294617+00:00
- Proposed icd11_scope: `2C60`, `2C61.0`, `2C61.1`, `2C61.2`, `2C61.3`, `2C61.4`, `2C62`, `2C63`, `2C64`, `2C65`, `2C6Y`, `2C6Z`
- Proposed procedure_scope: (none)
- Rationale: Malignant neoplasms of breast (2C60-2C6Z).
- ICD-11 hierarchy: Chapter 02 (Neoplasms) > Malignant neoplasms of breast range 2C60-2C6Z > Verified examples from API search include 2C60, 2C63, 2C65, 2C6Y, and 2C6Z
- [x] Approve / [ ] Edit / [ ] Reject

---

## CVD-Prevention-Women(2016)
- Rows in DB: 8
- Last classified: 2026-05-08T14:01:21.563348+00:00
- Proposed icd11_scope: `BA00.0`, `BA00.1`, `BA00.2`, `BA00.Y`, `BA00.Z`, `BA01`, `BA02`, `BA03`, `BA04.0`, `BA04.1`, `BA04.2`, `BA04.Y`, `BA04.Z`, `BA40.0`, `BA40.1`, `BA40.Y`, `BA40.Z`, `BA41.0`, `BA41.1`, `BA41.Z`, `BA42.0`, `BA42.1`, `BA42.Z`, `BD10`, `BD11.0`, `BD11.1`, `BD11.2`, `BD11.Z`, `BD12`, `BD13`, `8B11.0`, `8B11.1`, `8B11.20`, `8B11.21`, `8B11.22`, `8B11.2Y`, `8B11.2Z`, `8B11.3`, `8B11.40`, `8B11.41`, `8B11.42`, `8B11.43`, `8B11.44`, `8B11.50`, `8B11.51`, `8B11.5Z`, `5C80.00`, `5C80.01`, `5C80.0Z`, `5C80.1`, `5C80.2`, `5C80.3`, `5C80.Y`, `5C80.Z`, `5A11`, `BD40.0`, `BD40.1`, `BD40.2`, `BD40.3`, `BD40.Y`, `BD40.Z`, `BD50.00`, `BD50.01`, `BD50.02`, `BD50.0Y`, `BD50.0Z`, `BD50.10`, `BD50.11`, `BD50.12`, `BD50.1Y`, `BD50.1Z`, `BD50.20`, `BD50.21`, `BD50.22`, `BD50.2Y`, `BD50.2Z`, `BD50.30`, `BD50.31`, `BD50.32`, `BD50.3Y`, `BD50.3Z`, `BD50.40`, `BD50.41`, `BD50.4Y`, `BD50.4Z`, `BD50.50`, `BD50.51`, `BD50.52`, `BD50.5Y`, `BD50.5Z`, `BD50.Z`, `BC81.30`, `BC81.31`, `BC81.32`, `BC81.33`, `BC81.3Y`, `BC81.3Z`, `5B81.00`, `5B81.01`, `5B81.1`, `5B81.Y`, `5B81.Z`, `GB61.0`, `GB61.1`, `GB61.2`, `GB61.3`, `GB61.4`, `GB61.5`, `GB61.Z`
- Proposed procedure_scope: (none)
- Rationale: Systemic cardiovascular prevention strategy covering major circulatory endpoints and metabolic drivers, including chronic kidney disease as a high-risk cardiovascular equivalent.
- ICD-11 hierarchy: Chapter 11 (Circulatory) -> Hypertension (BA00-BA04), IHD (BA40-BA42), Heart Failure (BD10-BD13), Arrhythmia (BC81.3), Peripheral Vascular (BD40, BD50); Chapter 05 (Metabolic) -> Diabetes (5A11), Dyslipidaemia (5C80), Obesity (5B81), Metabolic Syndrome (5C40); Chapter 08 (Nervous) -> Ischaemic Stroke (8B11); Chapter 16 (Genitourinary) -> Chronic Kidney Disease (GB61)
- [ ] Approve / [x] Edit / [ ] Reject

---

## Dyslipidaemia(6th-Edition)
- Rows in DB: 15
- Last classified: 2026-05-08T13:48:07.294617+00:00
- Proposed icd11_scope: `5C80.00`, `5C80.01`, `5C80.0Z`, `5C80.1`, `5C80.2`, `5C80.3`, `5C80.Y`, `5C80.Z`, `5C81.0`, `5C81.1`, `5C81.Y`, `5C81.Z`, `5C8Y`, `5C8Z`
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
- Proposed icd11_scope: `BD10`, `BD11.0`, `BD11.1`, `BD11.2`, `BD11.Z`, `BD12`, `BD13`, `BD14`, `BD1Y`, `BD1Z`
- Proposed procedure_scope: (none)
- Rationale: Comprehensive management of the heart failure clinical syndrome, including congestive, left ventricular, right ventricular, biventricular, and unspecified heart failure presentations.
- ICD-11 hierarchy: Chapter 11 (Diseases of the circulatory system) > Heart failure range BD10-BD1Z
- [ ] Approve / [x] Edit / [ ] Reject

---

## Hypertension(5th Edition)
- Rows in DB: 15
- Last classified: 2026-05-08T13:48:07.294617+00:00
- Proposed icd11_scope: `BA00.0`, `BA00.1`, `BA00.2`, `BA00.Y`, `BA00.Z`, `BA01`, `BA02`, `BA03`, `BA04.0`, `BA04.1`, `BA04.2`, `BA04.Y`, `BA04.Z`
- Proposed procedure_scope: (none)
- Rationale: Hypertensive diseases: essential, secondary, hypertensive crisis (BA00-BA04).
- [x] Approve / [ ] Edit / [ ] Reject

---

## Ischaemic-Stroke(3rd Edition)
- Rows in DB: 18
- Last classified: 2026-05-08T13:17:44.569519+00:00
- Proposed icd11_scope: `8B11.0`, `8B11.1`, `8B11.20`, `8B11.21`, `8B11.22`, `8B11.2Y`, `8B11.2Z`, `8B11.3`, `8B11.40`, `8B11.41`, `8B11.42`, `8B11.43`, `8B11.44`, `8B11.50`, `8B11.51`, `8B11.5Z`
- Proposed procedure_scope: `endovascular_thrombectomy`, `stroke_workflow`, `revascularization`
- Rationale: The 3rd Edition CPG specifically manages acute cerebral ischaemic stroke (8B11) and reperfusion therapy. 8B10 (TIA) is excluded as it has distinct management; 8B20 is a pre-imaging triage code; 8B25 (Late effects) covers rehabilitation, not acute treatment.
- ICD-11 hierarchy: Chapter 08 (Nervous system diseases) > Cerebrovascular diseases > Cerebral ischaemia > 8B11 Cerebral ischaemic stroke
- [ ] Approve / [x] Edit / [ ] Reject

---

## NSTE-ACS(3rd Edition)
- Rows in DB: 12
- Last classified: 2026-05-08T13:48:07.294617+00:00
- Proposed icd11_scope: `BA40.0`, `BA40.1`, `BA40.Y`, `BA40.Z`, `BA41.0`, `BA41.1`, `BA41.Z`
- Proposed procedure_scope: `cardiac_rehabilitation`, `exercise_training`, `smoking_cessation`, `lifestyle_modification`
- Rationale: Non-ST-elevation acute coronary syndromes: unstable angina (BA40) and acute MI (BA41). NSTE-ACS is differentiated from STEMI by the absence of persistent ST-segment elevation and sub-classified based on troponin.
- ICD-11 hierarchy: Chapter 11 (Diseases of the circulatory system) > Ischaemic heart diseases > Acute ischaemic heart disease > BA40 Angina pectoris and BA41 Acute myocardial infarction
- [x] Approve / [ ] Edit / [ ] Reject

---

## NSTEMI(2011)
- Rows in DB: 10
- Last classified: 2026-05-08T13:48:07.294617+00:00
- Proposed icd11_scope: `BA41.0`, `BA41.1`, `BA41.Z`
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
- Proposed icd11_scope: `BA40.0`, `BA40.1`, `BA40.Y`, `BA40.Z`, `BA41.0`, `BA41.1`, `BA41.Z`, `BA42.0`, `BA42.1`, `BA42.Z`
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
- Proposed icd11_scope: `BB01.0`, `BB01.1`, `BB01.2`, `BB01.3`, `BB01.4`, `BB01.5`, `BB01.Z`
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

---

## Heart-Disease-in-Pregnancy
- Rows in DB: pending ingestion/classification
- Last classified: 2026-05-16T15:34:11.7530062+08:00
- Proposed icd11_scope: `BA00.0`, `BA00.1`, `BA00.2`, `BA00.Y`, `BA00.Z`, `BA01`, `BA02`, `BA03`, `BA04.0`, `BA04.1`, `BA04.2`, `BA04.Y`, `BA04.Z`, `BA40.0`, `BA40.1`, `BA40.Y`, `BA40.Z`, `BA41.0`, `BA41.1`, `BA41.Z`, `BA42.0`, `BA42.1`, `BA42.Z`, `BD10`, `BD11.0`, `BD11.1`, `BD11.2`, `BD11.Z`, `BD12`, `BD13`, `8B11.0`, `8B11.1`, `8B11.20`, `8B11.21`, `8B11.22`, `8B11.2Y`, `8B11.2Z`, `8B11.3`, `8B11.40`, `8B11.41`, `8B11.42`, `8B11.43`, `8B11.44`, `8B11.50`, `8B11.51`, `8B11.5Z`, `5C80.00`, `5C80.01`, `5C80.0Z`, `5C80.1`, `5C80.2`, `5C80.3`, `5C80.Y`, `5C80.Z`, `5B81.00`, `5B81.01`, `5B81.1`, `5B81.Y`, `5B81.Z`, `BD40.0`, `BD40.1`, `BD40.2`, `BD40.3`, `BD40.Y`, `BD40.Z`, `BD50.00`, `BD50.01`, `BD50.02`, `BD50.0Y`, `BD50.0Z`, `BD50.10`, `BD50.11`, `BD50.12`, `BD50.1Y`, `BD50.1Z`, `BD50.20`, `BD50.21`, `BD50.22`, `BD50.2Y`, `BD50.2Z`, `BD50.30`, `BD50.31`, `BD50.32`, `BD50.3Y`, `BD50.3Z`, `BD50.40`, `BD50.41`, `BD50.4Y`, `BD50.4Z`, `BD50.50`, `BD50.51`, `BD50.52`, `BD50.5Y`, `BD50.5Z`, `BD50.Z`, `BC81.30`, `BC81.31`, `BC81.32`, `BC81.33`, `BC81.3Y`, `BC81.3Z`, `GB61.0`, `GB61.1`, `GB61.2`, `GB61.3`, `GB61.4`, `GB61.5`, `GB61.Z`
- Proposed procedure_scope: `preconception_counselling`, `pregnancy_cardiac_risk_assessment`, `antenatal_cardiology_referral`, `multidisciplinary_pregnancy_care`, `labour_delivery_planning`, `postpartum_cardiac_follow_up`
- Rationale: Heart disease in pregnancy is scoped to the major cardiovascular conditions and cardiometabolic risk drivers that affect maternal cardiac risk assessment and management.
- ICD-11 hierarchy: Chapter 11 (Diseases of the circulatory system) > Hypertensive diseases (BA00-BA04), Ischaemic heart diseases (BA40-BA42), Heart failure (BD10-BD13), Cardiac arrhythmia (BC81.3), Peripheral vascular disease (BD40, BD50); Chapter 08 (Nervous) > Ischaemic stroke (8B11); Chapter 05 (Metabolic) > Lipidaemias (5C80), Obesity (5B81); Chapter 16 (Genitourinary) > Chronic kidney disease (GB61).
- [ ] Approve / [x] Edit / [ ] Reject

---

## Cancer-Pain(Part A)
- Rows in DB: pending ingestion/classification
- Last classified: 2026-05-16T15:34:11.7530062+08:00
- Proposed icd11_scope: `MG30.10`, `MG30.11`, `MG30.1Y`, `MG30.1Z`
- Proposed procedure_scope: `pain_assessment`, `analgesic_ladder`, `opioid_initiation`, `opioid_titration`, `opioid_rotation`, `breakthrough_pain_management`, `adjuvant_analgesia`, `interventional_pain_management`, `palliative_care`
- Rationale: Cancer pain guidance is primarily symptom and supportive-care focused across cancer types, so the narrowest disease scope is chronic cancer-related pain rather than all malignant neoplasm codes.
- ICD-11 hierarchy: Chapter 21 (Symptoms, signs or clinical findings) > Chronic pain > MG30.1 Chronic cancer-related pain.
- [ ] Approve / [ ] Edit / [ ] Reject

---

## Cancer-Pain(Part B)
- Rows in DB: pending ingestion/classification
- Last classified: 2026-05-16T15:34:11.7530062+08:00
- Proposed icd11_scope: `MG30.10`, `MG30.11`, `MG30.1Y`, `MG30.1Z`
- Proposed procedure_scope: `paediatric_pain_assessment`, `paediatric_analgesia`, `opioid_titration`, `procedural_pain_management`, `psychosocial_support`, `caregiver_education`, `palliative_care`
- Rationale: Part B continues cancer pain management with paediatric assessment, treatment, and supportive-care workflows; it remains scoped to chronic cancer-related pain rather than individual tumour sites.
- ICD-11 hierarchy: Chapter 21 (Symptoms, signs or clinical findings) > Chronic pain > MG30.1 Chronic cancer-related pain.
- [ ] Approve / [ ] Edit / [ ] Reject

---

## Cervical-Cancer(Second Edition)
- Rows in DB: pending ingestion/classification
- Last classified: 2026-05-16T15:34:11.7530062+08:00
- Proposed icd11_scope: `2C77.0`, `2C77.1`, `2C77.2`, `2C77.3`, `2C77.Y`, `2C77.Z`
- Proposed procedure_scope: `cancer_referral`, `cancer_staging`, `surgical_management`, `chemoradiotherapy`, `follow_up_surveillance`, `recurrent_disease_management`, `palliative_care`
- Rationale: The guideline gives diagnosis, staging, treatment, follow-up, recurrent disease, and palliative-care recommendations for malignant neoplasms of cervix uteri.
- ICD-11 hierarchy: Chapter 02 (Neoplasms) > Malignant neoplasms of female genital organs > 2C77 Malignant neoplasms of cervix uteri.
- [ ] Approve / [ ] Edit / [ ] Reject

---

## Colorectal-Carcinoma(2017)
- Rows in DB: pending ingestion/classification
- Last classified: 2026-05-16T15:34:11.7530062+08:00
- Proposed icd11_scope: `2B90.00`, `2B90.0Y`, `2B90.0Z`, `2B90.10`, `2B90.1Y`, `2B90.1Z`, `2B90.20`, `2B90.2Y`, `2B90.2Z`, `2B90.30`, `2B90.3Y`, `2B90.3Z`, `2B90.Y`, `2B90.Z`, `2B91.0`, `2B91.Y`, `2B91.Z`, `2B92.0`, `2B92.1`, `2B92.Y`, `2B92.Z`
- Proposed procedure_scope: `colorectal_screening`, `surveillance_colonoscopy`, `genetic_counselling`, `cancer_referral`, `cancer_staging`, `colorectal_surgery`, `chemotherapy`, `radiotherapy`, `follow_up_surveillance`
- Rationale: The guideline covers screening, diagnosis, staging, treatment, and surveillance for colon, rectosigmoid, and rectal carcinoma.
- ICD-11 hierarchy: Chapter 02 (Neoplasms) > Malignant neoplasms of digestive organs > malignant neoplasms of colon, rectosigmoid junction, and rectum.
- [ ] Approve / [ ] Edit / [ ] Reject

---

## Primary-Secondary-Prevention-CVD(2017)
- Rows in DB: pending ingestion/classification
- Last classified: 2026-05-16T15:34:11.7530062+08:00
- Proposed icd11_scope: `BA00.0`, `BA00.1`, `BA00.2`, `BA00.Y`, `BA00.Z`, `BA01`, `BA02`, `BA03`, `BA04.0`, `BA04.1`, `BA04.2`, `BA04.Y`, `BA04.Z`, `BA40.0`, `BA40.1`, `BA40.Y`, `BA40.Z`, `BA41.0`, `BA41.1`, `BA41.Z`, `BA42.0`, `BA42.1`, `BA42.Z`, `BD10`, `BD11.0`, `BD11.1`, `BD11.2`, `BD11.Z`, `BD12`, `BD13`, `8B11.0`, `8B11.1`, `8B11.20`, `8B11.21`, `8B11.22`, `8B11.2Y`, `8B11.2Z`, `8B11.3`, `8B11.40`, `8B11.41`, `8B11.42`, `8B11.43`, `8B11.44`, `8B11.50`, `8B11.51`, `8B11.5Z`, `5C80.00`, `5C80.01`, `5C80.0Z`, `5C80.1`, `5C80.2`, `5C80.3`, `5C80.Y`, `5C80.Z`, `5B81.00`, `5B81.01`, `5B81.1`, `5B81.Y`, `5B81.Z`, `BD40.0`, `BD40.1`, `BD40.2`, `BD40.3`, `BD40.Y`, `BD40.Z`, `BD50.00`, `BD50.01`, `BD50.02`, `BD50.0Y`, `BD50.0Z`, `BD50.10`, `BD50.11`, `BD50.12`, `BD50.1Y`, `BD50.1Z`, `BD50.20`, `BD50.21`, `BD50.22`, `BD50.2Y`, `BD50.2Z`, `BD50.30`, `BD50.31`, `BD50.32`, `BD50.3Y`, `BD50.3Z`, `BD50.40`, `BD50.41`, `BD50.4Y`, `BD50.4Z`, `BD50.50`, `BD50.51`, `BD50.52`, `BD50.5Y`, `BD50.5Z`, `BD50.Z`, `BC81.30`, `BC81.31`, `BC81.32`, `BC81.33`, `BC81.3Y`, `BC81.3Z`, `GB61.0`, `GB61.1`, `GB61.2`, `GB61.3`, `GB61.4`, `GB61.5`, `GB61.Z`
- Proposed procedure_scope: `cardiovascular_risk_assessment`, `lifestyle_modification`, `smoking_cessation`, `exercise_prescription`, `dietary_intervention`, `secondary_prevention`, `cardiac_rehabilitation`
- Rationale: Integrated primary and secondary prevention guidance for major cardiovascular outcomes and risk drivers, including hypertension, ischaemic heart disease, heart failure, stroke, dyslipidaemia, obesity, peripheral vascular disease, atrial fibrillation, and chronic kidney disease.
- ICD-11 hierarchy: Chapter 11 (Circulatory) > Hypertension (BA00-BA04), IHD (BA40-BA42), Heart failure (BD10-BD13), Arrhythmia (BC81.3), Peripheral vascular disease (BD40, BD50); Chapter 08 (Nervous) > Ischaemic stroke (8B11); Chapter 05 (Metabolic) > Lipidaemias (5C80), Obesity (5B81); Chapter 16 (Genitourinary) > Chronic kidney disease (GB61).
- [ ] Approve / [x] Edit / [ ] Reject

---

## Stable-Coronary-Artery-Disease(2nd Edition)
- Rows in DB: pending ingestion/classification
- Last classified: 2026-05-16T15:34:11.7530062+08:00
- Proposed icd11_scope: `BA40.0`, `BA40.1`, `BA40.Y`, `BA40.Z`, `BA42.0`, `BA42.1`, `BA42.Z`
- Proposed procedure_scope: `cardiovascular_risk_assessment`, `non_invasive_cardiac_testing`, `coronary_angiography`, `antianginal_therapy`, `lifestyle_modification`, `secondary_prevention`, `revascularization_referral`
- Rationale: Stable coronary artery disease guidance covers stable angina presentation and chronic ischaemic heart disease, including diagnostic testing, medical therapy, prevention, and referral for revascularisation when indicated.
- ICD-11 hierarchy: Chapter 11 (Diseases of the circulatory system) > Ischaemic heart diseases > BA40 Angina pectoris and BA42 Chronic ischaemic heart disease.
- [ ] Approve / [ ] Edit / [ ] Reject

---

## Safe-Use-Medication-Anaesthesia(2024)
- Rows in DB: pending ingestion/classification
- Last classified: 2026-05-16T15:34:11.7530062+08:00
- Proposed icd11_scope: (none)
- Proposed procedure_scope: `anaesthetic_medication_safety`, `medication_labelling`, `medication_storage`, `high_alert_medication`, `drug_allergy_management`, `malignant_hyperthermia_management`, `safe_medication_practice`, `medication_waste_management`
- Rationale: The guideline is procedure and safety focused for medication handling in anaesthesia practice, not disease-specific treatment.
- ICD-11 hierarchy: N/A (procedure-only anaesthesia medication safety guideline).
- [ ] Approve / [ ] Edit / [ ] Reject

---

# ICD-11 MMS Scope Expansion Audit

Source: WHO ICD-11 2024-01 MMS API

Scope lines changed: 18

## Parent Codes Expanded
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

## Changed Scope Lines
- Line 12: 1 codes -> 6 codes
- Line 23: 8 codes -> 12 codes
- Line 34: 20 codes -> 109 codes
- Line 45: 4 codes -> 14 codes
- Line 67: 7 codes -> 10 codes
- Line 78: 5 codes -> 13 codes
- Line 88: 1 codes -> 16 codes
- Line 99: 2 codes -> 7 codes
- Line 110: 1 codes -> 3 codes
- Line 130: 3 codes -> 10 codes
- Line 163: 1 codes -> 7 codes
- Line 185: 19 codes -> 108 codes
- Line 196: 1 codes -> 4 codes
- Line 207: 1 codes -> 4 codes
- Line 218: 1 codes -> 6 codes
- Line 229: 3 codes -> 21 codes
- Line 240: 19 codes -> 108 codes
- Line 251: 2 codes -> 7 codes
