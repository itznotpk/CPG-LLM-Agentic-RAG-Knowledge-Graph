-- ============================================================================
-- apply_documents_scope.sql
-- Populate documents.icd11_scope / procedure_scope / scope_rationale and flip
-- scope_verified = TRUE, driven by tasks/cpg_scope_review.md (review 2026-05-08).
--
-- SAFETY: This script is wrapped in BEGIN ... ROLLBACK. As written it CHANGES
--         NOTHING -- it runs the preflight + update + verification inside a
--         transaction and then rolls back. Inspect the output, and ONLY when
--         the preflight match counts look right, change the final ROLLBACK to
--         COMMIT and re-run.
--
-- Idempotent: re-running sets the same values; no duplication. Safe to repeat.
--
-- Scope is keyed on metadata->>'cpg_name'. Labels below are RECONCILED against
-- the LIVE DB as of 2026-05-22 (389 docs, 29 distinct CPG groups) -- they use
-- the DB's actual cpg_name strings, NOT the review-file headings (which differ
-- by edition/year suffix for ~11 groups). The PREFLIGHT below re-confirms the
-- match counts before you commit.
--
-- Reconciliation notes (review file -> live DB):
--   * 11 groups renamed in DB with edition/year suffixes (e.g. review
--     "Erectile-Dysfunction" -> DB "Erectile-Dysfunction(2024)"). Mapped below.
--   * Cancer-Pain Part A + Part B (review) are a SINGLE group in DB
--     "Cancer-Pain(2nd Edition)". Both had identical ICD scope (MG30.1*), so the
--     merge is lossless for icd11_scope; procedure_scope is the union.
--   * "Nasopharyngeal-Carcinoma" (11 rows) was missing from the review file;
--     scope added 2026-05-22 (2B6B family, verified against live icd11_codes)
--     and back-filled into cpg_scope_review.md.
--   * Review heading "Type-2-Diabetes-Mellitus(6th Edition)" = folder/cpg_name
--     "T2-Diabetes-Mellitus(6th-Edition)" -- NOT yet ingested (no DB rows).
--     Entry kept (commented, under the folder name) for when it lands.
--
-- VALIDATED 2026-05-22 against live Neon: all 29 live CPG groups now have a
-- scope entry below (28 from the review file + Nasopharyngeal-Carcinoma added
-- 2026-05-22). Only T2-Diabetes-Mellitus(6th-Edition) lacks DB rows.
-- ============================================================================

BEGIN;

-- ----------------------------------------------------------------------------
-- 1. Mapping table: one row per CPG group from cpg_scope_review.md
--    icd11_scope = '{}' means "reviewed, intentionally no disease scope"
--    (procedure-only guideline) -- it still gets scope_verified = TRUE.
-- ----------------------------------------------------------------------------
CREATE TEMP TABLE _scope_map (
    cpg_name        text PRIMARY KEY,
    icd11_scope     text[],
    procedure_scope text[],
    scope_rationale text
) ON COMMIT DROP;

INSERT INTO _scope_map (cpg_name, icd11_scope, procedure_scope, scope_rationale) VALUES

-- ---- Groups WITH rows already in the live documents table -------------------

('Atrial-Fibrillation(2012)',
 ARRAY['BC81.3','BC81.30','BC81.31','BC81.32','BC81.33','BC81.3Y','BC81.3Z'],
 ARRAY['referral_pathway','clinical_audit','quality_assurance','warfarin_initiation','inr_monitoring','dose_adjustment','perioperative_bridging'],
 'Specific AF guidance maps to BC81.3 (Atrial fibrillation) under the cardiac arrhythmia hierarchy.'),

('Breast-Cancer(3rd Edition)',
 ARRAY['2C60','2C61','2C61.0','2C61.1','2C61.2','2C61.3','2C61.4','2C62','2C63','2C64','2C65','2C6Y','2C6Z'],
 '{}'::text[],
 'Malignant neoplasms of breast (2C60-2C6Z).'),

('CVD-Prevention-Women(2016)',
 ARRAY['BA00','BA00.0','BA00.1','BA00.2','BA00.Y','BA00.Z','BA01','BA02','BA03','BA04','BA04.0','BA04.1','BA04.2','BA04.Y','BA04.Z','BA40','BA40.0','BA40.1','BA40.Y','BA40.Z','BA41','BA41.0','BA41.1','BA41.Z','BA42','BA42.0','BA42.1','BA42.Z','BD10','BD11','BD11.0','BD11.1','BD11.2','BD11.Z','BD12','BD13','8B11','8B11.0','8B11.1','8B11.20','8B11.21','8B11.22','8B11.2Y','8B11.2Z','8B11.3','8B11.40','8B11.41','8B11.42','8B11.43','8B11.44','8B11.50','8B11.51','8B11.5Z','5C80','5C80.00','5C80.01','5C80.0Z','5C80.1','5C80.2','5C80.3','5C80.Y','5C80.Z','5A11','BD40','BD40.0','BD40.1','BD40.2','BD40.3','BD40.Y','BD40.Z','BD50','BD50.00','BD50.01','BD50.02','BD50.0Y','BD50.0Z','BD50.10','BD50.11','BD50.12','BD50.1Y','BD50.1Z','BD50.20','BD50.21','BD50.22','BD50.2Y','BD50.2Z','BD50.30','BD50.31','BD50.32','BD50.3Y','BD50.3Z','BD50.40','BD50.41','BD50.4Y','BD50.4Z','BD50.50','BD50.51','BD50.52','BD50.5Y','BD50.5Z','BD50.Z','BC81.3','BC81.30','BC81.31','BC81.32','BC81.33','BC81.3Y','BC81.3Z','5B81','5B81.00','5B81.01','5B81.1','5B81.Y','5B81.Z','GB61','GB61.0','GB61.1','GB61.2','GB61.3','GB61.4','GB61.5','GB61.Z'],
 '{}'::text[],
 'Systemic cardiovascular prevention strategy covering major circulatory endpoints and metabolic drivers, including chronic kidney disease as a high-risk cardiovascular equivalent.'),

('Dyslipidaemia(6th-Edition)',
 ARRAY['5C80','5C80.00','5C80.01','5C80.0Z','5C80.1','5C80.2','5C80.3','5C80.Y','5C80.Z','5C81','5C81.0','5C81.1','5C81.Y','5C81.Z','5C8Y','5C8Z'],
 '{}'::text[],
 'Comprehensive management of lipoprotein metabolism disorders, including primary and secondary hypercholesterolaemia, hypertriglyceridaemia, and mixed dyslipidaemias.'),

('Erectile-Dysfunction(2024)',
 ARRAY['HA01.10','HA01.11','HA01.12','HA01.13','HA01.1Z'],
 '{}'::text[],
 'Direct mapping for male erectile dysfunction, covering lifelong, acquired, situational, and generalized presentations.'),

('Heart-Failure(5th Edition)',
 ARRAY['BD10','BD11','BD11.0','BD11.1','BD11.2','BD11.Z','BD12','BD13','BD14','BD1Y','BD1Z'],
 '{}'::text[],
 'Comprehensive management of the heart failure clinical syndrome, including congestive, left ventricular, right ventricular, biventricular, and unspecified heart failure presentations.'),

('Hypertension(5th Edition)',
 ARRAY['BA00','BA00.0','BA00.1','BA00.2','BA00.Y','BA00.Z','BA01','BA02','BA03','BA04','BA04.0','BA04.1','BA04.2','BA04.Y','BA04.Z'],
 '{}'::text[],
 'Hypertensive diseases: essential, secondary, hypertensive crisis (BA00-BA04).'),

('Ischaemic-Stroke(3rd Edition)',
 ARRAY['8B11','8B11.0','8B11.1','8B11.20','8B11.21','8B11.22','8B11.2Y','8B11.2Z','8B11.3','8B11.40','8B11.41','8B11.42','8B11.43','8B11.44','8B11.50','8B11.51','8B11.5Z'],
 ARRAY['endovascular_thrombectomy','stroke_workflow','revascularization'],
 'The 3rd Edition CPG specifically manages acute cerebral ischaemic stroke (8B11) and reperfusion therapy. 8B10 (TIA) is excluded as it has distinct management; 8B20 is a pre-imaging triage code; 8B25 (Late effects) covers rehabilitation, not acute treatment.'),

('NSTE-ACS(3rd Edition)',
 ARRAY['BA40','BA40.0','BA40.1','BA40.Y','BA40.Z','BA41','BA41.0','BA41.1','BA41.Z'],
 ARRAY['cardiac_rehabilitation','exercise_training','smoking_cessation','lifestyle_modification'],
 'Non-ST-elevation acute coronary syndromes: unstable angina (BA40) and acute MI (BA41). NSTE-ACS is differentiated from STEMI by the absence of persistent ST-segment elevation and sub-classified based on troponin.'),

('NSTEMI(2011)',
 ARRAY['BA41','BA41.0','BA41.1','BA41.Z'],
 '{}'::text[],
 'Acute myocardial infarction -- non-ST-elevation subtype (BA41).'),

('Patient-Safety-Minimal-Monitoring',
 '{}'::text[],
 ARRAY['pre_op_assessment','anaesthetic_equipment_safety','anaesthetic_safety'],
 'The CPG focuses on anaesthesia safety, equipment checks, and pre-operative assessment rather than specific diseases.'),

('Percutaneous-Coronary-Intervention',
 ARRAY['BA40','BA40.0','BA40.1','BA40.Y','BA40.Z','BA41','BA41.0','BA41.1','BA41.Z','BA42','BA42.0','BA42.1','BA42.Z'],
 ARRAY['percutaneous_coronary_intervention','coronary_angiography','coronary_stenting','intravascular_imaging'],
 'Ischaemic heart disease conditions treated by PCI: unstable angina (BA40), acute myocardial infarction (BA41), chronic ischaemic heart disease (BA42).'),

('Pre-Anaesthetic-Assessment',
 '{}'::text[],
 ARRAY['pre_op_assessment','investigation_selection','risk_assessment','anaesthetic_planning'],
 'CPG focuses on pre-anaesthetic assessment, investigation selection based on patient factors and surgery type, risk assessment and anaesthetic planning, not on specific disease treatment.'),

('Prevention-Diagnosis-Management-of-IE',
 ARRAY['BB40','BB41','BB42','BB4Y','BB4Z'],
 '{}'::text[],
 'Captures the full spectrum of acute/subacute endocarditis including infectious (BB40), related inflammations (BB41, BB42), and catch-all categories for other specified (BB4Y) or unspecified (BB4Z) presentations.'),

('Pulmonary-Arterial-Hypertension(2011)',
 ARRAY['BB01','BB01.0','BB01.1','BB01.2','BB01.3','BB01.4','BB01.5','BB01.Z'],
 '{}'::text[],
 'Pulmonary arterial hypertension (Group 1). This stem code covers idiopathic, heritable, and associated forms of PAH defined in the 2011 CPG.'),

('STEMI(4th Edition)',
 ARRAY['BA41.0'],
 '{}'::text[],
 'Specifically identifies ST-elevation myocardial infarction. The parent code BA41 is too broad as it includes NSTEMI (BA41.1), which is managed under a different clinical pathway.'),

-- ---- Groups marked "pending ingestion/classification" in the review file ----
-- These will hit 0 rows until their documents are ingested. Kept here so the
-- same script scopes them automatically once they land.

('Heart-Disease-in-Pregnancy(2nd Edition)',
 ARRAY['BA00','BA00.0','BA00.1','BA00.2','BA00.Y','BA00.Z','BA01','BA02','BA03','BA04','BA04.0','BA04.1','BA04.2','BA04.Y','BA04.Z','BA40','BA40.0','BA40.1','BA40.Y','BA40.Z','BA41','BA41.0','BA41.1','BA41.Z','BA42','BA42.0','BA42.1','BA42.Z','BD10','BD11','BD11.0','BD11.1','BD11.2','BD11.Z','BD12','BD13','8B11','8B11.0','8B11.1','8B11.20','8B11.21','8B11.22','8B11.2Y','8B11.2Z','8B11.3','8B11.40','8B11.41','8B11.42','8B11.43','8B11.44','8B11.50','8B11.51','8B11.5Z','5C80','5C80.00','5C80.01','5C80.0Z','5C80.1','5C80.2','5C80.3','5C80.Y','5C80.Z','5B81','5B81.00','5B81.01','5B81.1','5B81.Y','5B81.Z','BD40','BD40.0','BD40.1','BD40.2','BD40.3','BD40.Y','BD40.Z','BD50','BD50.00','BD50.01','BD50.02','BD50.0Y','BD50.0Z','BD50.10','BD50.11','BD50.12','BD50.1Y','BD50.1Z','BD50.20','BD50.21','BD50.22','BD50.2Y','BD50.2Z','BD50.30','BD50.31','BD50.32','BD50.3Y','BD50.3Z','BD50.40','BD50.41','BD50.4Y','BD50.4Z','BD50.50','BD50.51','BD50.52','BD50.5Y','BD50.5Z','BD50.Z','BC81.3','BC81.30','BC81.31','BC81.32','BC81.33','BC81.3Y','BC81.3Z','GB61','GB61.0','GB61.1','GB61.2','GB61.3','GB61.4','GB61.5','GB61.Z'],
 ARRAY['preconception_counselling','pregnancy_cardiac_risk_assessment','antenatal_cardiology_referral','multidisciplinary_pregnancy_care','labour_delivery_planning','postpartum_cardiac_follow_up'],
 'Heart disease in pregnancy is scoped to the major cardiovascular conditions and cardiometabolic risk drivers that affect maternal cardiac risk assessment and management.'),

-- Cancer-Pain Part A + Part B (review file) are ONE group in DB; ICD scope
-- identical (MG30.1*), procedure_scope below is the union of both parts.
('Cancer-Pain(2nd Edition)',
 ARRAY['MG30.1','MG30.10','MG30.11','MG30.1Y','MG30.1Z'],
 ARRAY['pain_assessment','analgesic_ladder','opioid_initiation','opioid_titration','opioid_rotation','breakthrough_pain_management','adjuvant_analgesia','interventional_pain_management','palliative_care','paediatric_pain_assessment','paediatric_analgesia','procedural_pain_management','psychosocial_support','caregiver_education'],
 'Cancer pain guidance (adult Part A + paediatric Part B) is symptom and supportive-care focused across cancer types, scoped to chronic cancer-related pain rather than all malignant neoplasm codes.'),

('Cervical-Cancer(2nd Edition)',
 ARRAY['2C77','2C77.0','2C77.1','2C77.2','2C77.3','2C77.Y','2C77.Z'],
 ARRAY['cancer_referral','cancer_staging','surgical_management','chemoradiotherapy','follow_up_surveillance','recurrent_disease_management','palliative_care'],
 'The guideline gives diagnosis, staging, treatment, follow-up, recurrent disease, and palliative-care recommendations for malignant neoplasms of cervix uteri.'),

('Colorectal-Carcinoma(2017)',
 ARRAY['2B90','2B90.00','2B90.0Y','2B90.0Z','2B90.10','2B90.1Y','2B90.1Z','2B90.20','2B90.2Y','2B90.2Z','2B90.30','2B90.3Y','2B90.3Z','2B90.Y','2B90.Z','2B91','2B91.0','2B91.Y','2B91.Z','2B92','2B92.0','2B92.1','2B92.Y','2B92.Z'],
 ARRAY['colorectal_screening','surveillance_colonoscopy','genetic_counselling','cancer_referral','cancer_staging','colorectal_surgery','chemotherapy','radiotherapy','follow_up_surveillance'],
 'The guideline covers screening, diagnosis, staging, treatment, and surveillance for colon, rectosigmoid, and rectal carcinoma.'),

('Primary-Secondary-Prevention-of-CVD(2017)',
 ARRAY['BA00','BA00.0','BA00.1','BA00.2','BA00.Y','BA00.Z','BA01','BA02','BA03','BA04','BA04.0','BA04.1','BA04.2','BA04.Y','BA04.Z','BA40','BA40.0','BA40.1','BA40.Y','BA40.Z','BA41','BA41.0','BA41.1','BA41.Z','BA42','BA42.0','BA42.1','BA42.Z','BD10','BD11','BD11.0','BD11.1','BD11.2','BD11.Z','BD12','BD13','8B11','8B11.0','8B11.1','8B11.20','8B11.21','8B11.22','8B11.2Y','8B11.2Z','8B11.3','8B11.40','8B11.41','8B11.42','8B11.43','8B11.44','8B11.50','8B11.51','8B11.5Z','5C80','5C80.00','5C80.01','5C80.0Z','5C80.1','5C80.2','5C80.3','5C80.Y','5C80.Z','5B81','5B81.00','5B81.01','5B81.1','5B81.Y','5B81.Z','BD40','BD40.0','BD40.1','BD40.2','BD40.3','BD40.Y','BD40.Z','BD50','BD50.00','BD50.01','BD50.02','BD50.0Y','BD50.0Z','BD50.10','BD50.11','BD50.12','BD50.1Y','BD50.1Z','BD50.20','BD50.21','BD50.22','BD50.2Y','BD50.2Z','BD50.30','BD50.31','BD50.32','BD50.3Y','BD50.3Z','BD50.40','BD50.41','BD50.4Y','BD50.4Z','BD50.50','BD50.51','BD50.52','BD50.5Y','BD50.5Z','BD50.Z','BC81.3','BC81.30','BC81.31','BC81.32','BC81.33','BC81.3Y','BC81.3Z','GB61','GB61.0','GB61.1','GB61.2','GB61.3','GB61.4','GB61.5','GB61.Z'],
 ARRAY['cardiovascular_risk_assessment','lifestyle_modification','smoking_cessation','exercise_prescription','dietary_intervention','secondary_prevention','cardiac_rehabilitation'],
 'Integrated primary and secondary prevention guidance for major cardiovascular outcomes and risk drivers, including hypertension, ischaemic heart disease, heart failure, stroke, dyslipidaemia, obesity, peripheral vascular disease, atrial fibrillation, and chronic kidney disease.'),

('Stable-Coronary-Artery-Disease(2nd Edition)',
 ARRAY['BA40','BA40.0','BA40.1','BA40.Y','BA40.Z','BA42','BA42.0','BA42.1','BA42.Z'],
 ARRAY['cardiovascular_risk_assessment','non_invasive_cardiac_testing','coronary_angiography','antianginal_therapy','lifestyle_modification','secondary_prevention','revascularization_referral'],
 'Stable coronary artery disease guidance covers stable angina presentation and chronic ischaemic heart disease, including diagnostic testing, medical therapy, prevention, and referral for revascularisation when indicated.'),

('Anaesthesia-Medication-Safety',
 '{}'::text[],
 ARRAY['anaesthetic_medication_safety','medication_labelling','medication_storage','high_alert_medication','drug_allergy_management','malignant_hyperthermia_management','safe_medication_practice','medication_waste_management'],
 'The guideline is procedure and safety focused for medication handling in anaesthesia practice, not disease-specific treatment.'),

('Obesity-Management(2023)',
 ARRAY['5B80','5B80.0','5B80.1','5B81','5B81.0','5B81.00','5B81.01','5B81.1','5B81.Y','5B81.Z'],
 ARRAY['bmi_assessment','waist_circumference_assessment','lifestyle_modification','dietary_intervention','exercise_prescription','weight_monitoring','anti_obesity_pharmacotherapy','bariatric_surgery_referral'],
 'Obesity CPG covers diagnosis, risk stratification, prevention, lifestyle therapy, pharmacotherapy, and bariatric referral across overweight and obesity in children, adolescents, and adults.'),

-- NOT YET INGESTED -- no documents rows exist for this CPG as of 2026-05-22.
-- The source markdown folder is markdown/T2-Diabetes-Mellitus(6th-Edition)/
-- (17 sections), so the ingester will set cpg_name = 'T2-Diabetes-Mellitus(6th-Edition)'
-- (parent-folder name, per ingest.py). Just uncomment after ingestion -- the
-- label below already matches the folder name.
-- ('T2-Diabetes-Mellitus(6th-Edition)',
--  ARRAY['5A11'],
--  ARRAY['glycaemic_assessment','hba1c_monitoring','lifestyle_modification','dietary_intervention','oral_glucose_lowering_therapy','insulin_therapy','self_monitoring_blood_glucose','cardiovascular_risk_assessment','diabetes_complication_screening','sick_day_management'],
--  'The Type 2 Diabetes Mellitus guideline is disease-specific for diagnosis, glycaemic targets, non-pharmacological care, glucose-lowering therapy, complication screening, and long-term follow-up.'),

('Thyroid-Disorders(2019)',
 ARRAY['5A00','5A00.0','5A00.1','5A00.2','5A00.Z','5A01','5A01.0','5A01.1','5A01.2','5A01.Z','5A02','5A02.0','5A02.1','5A02.2','5A02.3','5A02.4','5A02.5','5A02.6','5A02.Y','5A02.Z','5A03','5A03.0','5A03.1','5A03.2','5A03.Y','5A03.Z','5A0Y','5A0Z'],
 ARRAY['thyroid_function_testing','thyroid_autoantibody_testing','thyroid_ultrasound','thyroid_nodule_assessment','levothyroxine_therapy','antithyroid_drug_therapy','radioactive_iodine_referral','endocrine_referral','thyroid_follow_up_monitoring'],
 'Thyroid disorders guidance covers hypothyroidism, nontoxic goitre, thyrotoxicosis, thyroiditis, and specified or unspecified thyroid gland or thyroid hormone system disorders.'),

('Diabetes-in-Pregnancy(2017)',
 ARRAY['JA63','JA63.0','JA63.1','JA63.2','JA63.Y','JA63.Z','5A10','5A11'],
 ARRAY['preconception_counselling','antenatal_diabetes_screening','ogtt','glucose_monitoring','insulin_therapy','medical_nutrition_therapy','fetal_surveillance','delivery_planning','postpartum_diabetes_screening'],
 'Diabetes in pregnancy guidance covers pre-existing type 1 and type 2 diabetes in pregnancy, gestational diabetes, antenatal glucose monitoring and therapy, fetal surveillance, delivery planning, and postpartum screening.'),

('Type-1-Diabetes-Mellitus-Children_Adolescents(2016)',
 ARRAY['5A10'],
 ARRAY['paediatric_diabetes_education','insulin_therapy','glucose_monitoring','hba1c_monitoring','hypoglycaemia_management','diabetic_ketoacidosis_prevention','sick_day_management','school_care_planning','transition_to_adult_care'],
 'The paediatric and adolescent Type 1 Diabetes Mellitus guideline is disease-specific for type 1 diabetes diagnosis, insulin treatment, monitoring, acute complication prevention, family education, school planning, and transition care.'),

('Growth-Hormone-Children-Adults(2010)',
 ARRAY['5A61.3','5B11','MG44.12','MG44.13'],
 ARRAY['auxology_assessment','growth_velocity_monitoring','endocrine_referral','growth_hormone_stimulation_testing','growth_hormone_therapy','igf1_monitoring','adverse_effect_monitoring','treatment_response_monitoring'],
 'Growth hormone guidance is scoped to confirmed growth hormone deficiency and to early growth-presentation workflows where patients present before endocrine stimulation testing confirms the diagnosis.'),

-- Added 2026-05-22: ingested CPG that was missing from cpg_scope_review.md.
-- ICD codes verified against live icd11_codes (2B6B Malignant neoplasms of nasopharynx).
('Nasopharyngeal-Carcinoma',
 ARRAY['2B6B','2B6B.0','2B6B.1','2B6B.Y','2B6B.Z'],
 ARRAY['cancer_referral','cancer_staging','chemoradiotherapy','surgical_management','supportive_care','recurrent_disease_management','follow_up_surveillance','palliative_care'],
 'The guideline covers diagnosis, staging, treatment (chemoradiotherapy/surgery), supportive care, management of complications, and prognosis/follow-up for malignant neoplasms of the nasopharynx.')
;

-- ----------------------------------------------------------------------------
-- 2. PREFLIGHT -- read-only. Confirms which group labels actually match
--    documents rows. Reconcile any "doc_rows = 0" rows (renamed/pending groups)
--    BEFORE you commit. Nothing is written by this SELECT.
-- ----------------------------------------------------------------------------
SELECT
    m.cpg_name,
    cardinality(m.icd11_scope)     AS n_icd_codes,
    cardinality(m.procedure_scope) AS n_proc,
    COUNT(d.id)                    AS doc_rows
FROM _scope_map m
LEFT JOIN documents d
       ON d.metadata->>'cpg_name' = m.cpg_name
GROUP BY m.cpg_name, m.icd11_scope, m.procedure_scope
ORDER BY doc_rows ASC, m.cpg_name;

-- Reverse check: live CPG groups in documents that have NO entry in the map
-- (these would be left unscoped -- investigate name mismatches here).
SELECT
    d.metadata->>'cpg_name' AS unmapped_cpg_name,
    COUNT(*)                AS doc_rows
FROM documents d
LEFT JOIN _scope_map m
       ON d.metadata->>'cpg_name' = m.cpg_name
WHERE m.cpg_name IS NULL
  AND d.metadata->>'cpg_name' IS NOT NULL
GROUP BY d.metadata->>'cpg_name'
ORDER BY doc_rows DESC;

-- ----------------------------------------------------------------------------
-- 3. APPLY -- writes scope onto every matching documents row.
-- ----------------------------------------------------------------------------
UPDATE documents d
SET icd11_scope     = m.icd11_scope,
    procedure_scope = m.procedure_scope,
    scope_rationale = m.scope_rationale,
    scope_verified  = TRUE,
    classified_at   = COALESCE(d.classified_at, now()),
    verified_at     = now(),
    verified_by     = 'cpg_scope_review.md (2026-05-08 review)',
    updated_at      = now()
FROM _scope_map m
WHERE d.metadata->>'cpg_name' = m.cpg_name;

-- ----------------------------------------------------------------------------
-- 4. VERIFY -- post-update totals (still inside the transaction).
-- ----------------------------------------------------------------------------
SELECT
    COUNT(*) FILTER (WHERE scope_verified)                          AS rows_verified,
    COUNT(*) FILTER (WHERE cardinality(icd11_scope) > 0)           AS rows_with_icd_scope,
    COUNT(*) FILTER (WHERE cardinality(procedure_scope) > 0)       AS rows_with_proc_scope,
    COUNT(DISTINCT metadata->>'cpg_name')
        FILTER (WHERE scope_verified)                              AS verified_cpg_groups,
    COUNT(*)                                                        AS total_rows
FROM documents;

-- ----------------------------------------------------------------------------
-- 5. Dry run by default. Inspect the output above, then flip ROLLBACK -> COMMIT.
-- ----------------------------------------------------------------------------
ROLLBACK;
-- COMMIT;
