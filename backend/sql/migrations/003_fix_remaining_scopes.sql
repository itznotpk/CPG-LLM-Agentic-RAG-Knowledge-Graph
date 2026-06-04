-- Migration 003: corrections for the 3 CPGs left untouched after migration 002.
-- These had plausible-but-wrong scopes from the Step 03 LLM (MiMo) classifier.
-- Idempotent. scope_verified is left FALSE so Step 04 review still applies.
--
-- Applied 2026-05-08.

BEGIN;

-- 1. CVD-Prevention-Women(2016)
--    Was: BA20-BA24, BB30-BB34, BB61, BB90-BB94, BC00-BC07, BC20-BC24
--    These ranges include non-CVD-prevention areas (BB30s = paragangliomas,
--    BC00s = various non-CVD codes). A CVD-prevention CPG should cover the
--    major CVD disease groups it advises preventing:
--      BA00-BA04 hypertension, BA40-BA42 IHD, BD10-BD13 heart failure,
--      8B11 ischaemic stroke, 5C80 lipid disorders, 5A11 type 2 diabetes.
UPDATE documents
SET icd11_scope     = ARRAY[
        'BA00','BA01','BA02','BA03','BA04',
        'BA40','BA41','BA42',
        'BD10','BD11','BD12','BD13',
        '8B11',
        '5C80',
        '5A11'
    ]::TEXT[],
    scope_rationale = 'CVD prevention covering major cardiovascular disease groups: hypertension (BA00-BA04), ischaemic heart disease (BA40-BA42), heart failure (BD10-BD13), ischaemic stroke (8B11), dyslipidaemia (5C80), and type 2 diabetes (5A11).',
    classified_at   = NOW(),
    scope_verified  = FALSE
WHERE metadata->>'cpg_name' = 'CVD-Prevention-Women(2016)';

-- 2. Percutaneous-Coronary-Intervention
--    Was: BA20-BA24 (hypertensive heart disease — wrong)
--    PCI treats ischaemic heart disease: unstable angina (BA40), acute MI
--    (BA41), and chronic / stable IHD (BA42).
UPDATE documents
SET icd11_scope     = ARRAY['BA40','BA41','BA42']::TEXT[],
    scope_rationale = 'Ischaemic heart disease conditions treated by PCI: unstable angina (BA40), acute myocardial infarction (BA41), chronic ischaemic heart disease (BA42).',
    classified_at   = NOW(),
    scope_verified  = FALSE
WHERE metadata->>'cpg_name' = 'Percutaneous-Coronary-Intervention';

-- 3. Prevention-Diagnosis-Management-of-IE
--    Was: 1D86, BA20-BA2Z (BA20-BA2Z is hypertensive heart disease — wrong;
--    rationale even claimed "Enterobacteriaceae (BA20-BA2Z)" which is nonsense)
--    Infective endocarditis lives in the BB40 block in ICD-11.
UPDATE documents
SET icd11_scope     = ARRAY['BB40','BB41','BB42','BB43','BB44']::TEXT[],
    scope_rationale = 'Infective endocarditis: native valve, prosthetic valve, right-sided, and device-related (BB40-BB44).',
    classified_at   = NOW(),
    scope_verified  = FALSE
WHERE metadata->>'cpg_name' = 'Prevention-Diagnosis-Management-of-IE';

-- Sanity check: rollback if any of the 3 expected groups is missing.
DO $$
DECLARE
    expected_groups TEXT[] := ARRAY[
        'CVD-Prevention-Women(2016)',
        'Percutaneous-Coronary-Intervention',
        'Prevention-Diagnosis-Management-of-IE'
    ];
    g TEXT;
    n INTEGER;
BEGIN
    FOREACH g IN ARRAY expected_groups LOOP
        SELECT COUNT(*) INTO n FROM documents WHERE metadata->>'cpg_name' = g;
        IF n = 0 THEN
            RAISE EXCEPTION 'No rows found for cpg_name = %', g;
        END IF;
    END LOOP;
END $$;

COMMIT;
