-- Migration 002: manual corrections of hallucinated ICD-11 scopes
-- Applies to 10 CPG groups whose Step 03 LLM proposals were demonstrably wrong.
-- Idempotent: re-running produces the same result. scope_verified is left FALSE
-- so the clinician review (Step 04) is still required.
--
-- Applied 2026-05-08.

BEGIN;

-- 1. Erectile-Dysfunction: GB84 (wrong) -> HA01.1 (Male erectile dysfunction)
UPDATE documents
SET icd11_scope     = ARRAY['HA01.1']::TEXT[],
    scope_rationale = 'Male erectile dysfunction (ICD-11 HA01.1).',
    classified_at   = NOW(),
    scope_verified  = FALSE
WHERE metadata->>'cpg_name' = 'Erectile-Dysfunction';

-- 2. Hypertension(5th Edition): BA90-BA9Z (wrong) -> BA00-BA04
UPDATE documents
SET icd11_scope     = ARRAY['BA00','BA01','BA02','BA03','BA04']::TEXT[],
    scope_rationale = 'Hypertensive diseases: essential, secondary, hypertensive crisis (BA00-BA04).',
    classified_at   = NOW(),
    scope_verified  = FALSE
WHERE metadata->>'cpg_name' = 'Hypertension(5th Edition)';

-- 3. Heart-Failure(5th Edition): BC40-BC4Z (wrong) -> BD10-BD13
UPDATE documents
SET icd11_scope     = ARRAY['BD10','BD11','BD12','BD13']::TEXT[],
    scope_rationale = 'Heart failure (HFrEF, HFpEF, HF with mildly reduced EF, HF NOS) — BD10-BD13.',
    classified_at   = NOW(),
    scope_verified  = FALSE
WHERE metadata->>'cpg_name' = 'Heart-Failure(5th Edition)';

-- 4. Pulmonary-Arterial-Hypertension(2011): BA21 (wrong, was pulmonary embolism) -> BB01
UPDATE documents
SET icd11_scope     = ARRAY['BB01']::TEXT[],
    scope_rationale = 'Pulmonary arterial hypertension (BB01).',
    classified_at   = NOW(),
    scope_verified  = FALSE
WHERE metadata->>'cpg_name' = 'Pulmonary-Arterial-Hypertension(2011)';

-- 5. Breast-Cancer(3rd Edition): 2C20-2C2Z (hepatobiliary) -> 2C60-2C6Z (breast)
UPDATE documents
SET icd11_scope     = ARRAY['2C60-2C6Z']::TEXT[],
    scope_rationale = 'Malignant neoplasms of breast (2C60-2C6Z).',
    classified_at   = NOW(),
    scope_verified  = FALSE
WHERE metadata->>'cpg_name' = 'Breast-Cancer(3rd Edition)';

-- 6. STEMI(4th Edition): BA40-BA4Z (over-broad) -> BA41 (acute MI block)
UPDATE documents
SET icd11_scope     = ARRAY['BA41']::TEXT[],
    scope_rationale = 'Acute myocardial infarction — ST-elevation subtype (BA41).',
    classified_at   = NOW(),
    scope_verified  = FALSE
WHERE metadata->>'cpg_name' = 'STEMI(4th Edition)';

-- 7. NSTEMI(2011): DA20-DA24 (digestive — clear hallucination) -> BA41
UPDATE documents
SET icd11_scope     = ARRAY['BA41']::TEXT[],
    scope_rationale = 'Acute myocardial infarction — non-ST-elevation subtype (BA41).',
    classified_at   = NOW(),
    scope_verified  = FALSE
WHERE metadata->>'cpg_name' = 'NSTEMI(2011)';

-- 8. Dyslipidaemia(6th-Edition): DE70-DE74 (wrong chapter) -> 5C80
UPDATE documents
SET icd11_scope     = ARRAY['5C80']::TEXT[],
    scope_rationale = 'Lipoprotein metabolism disorders (5C80).',
    classified_at   = NOW(),
    scope_verified  = FALSE
WHERE metadata->>'cpg_name' = 'Dyslipidaemia(6th-Edition)';

-- 9. Atrial-Fibrillation(2012): BC81, BC82 -> BC81 only (BC82 not a valid block)
UPDATE documents
SET icd11_scope     = ARRAY['BC81']::TEXT[],
    scope_rationale = 'Atrial fibrillation and atrial flutter (BC81).',
    classified_at   = NOW(),
    scope_verified  = FALSE
WHERE metadata->>'cpg_name' = 'Atrial-Fibrillation(2012)';

-- 10. NSTE-ACS(3rd Edition): BA20-BA24 (broad IHD) -> BA40 + BA41 (UA + acute MI)
UPDATE documents
SET icd11_scope     = ARRAY['BA40','BA41']::TEXT[],
    scope_rationale = 'Non-ST-elevation acute coronary syndromes: unstable angina (BA40) and acute MI (BA41).',
    classified_at   = NOW(),
    scope_verified  = FALSE
WHERE metadata->>'cpg_name' = 'NSTE-ACS(3rd Edition)';

-- Sanity check (will roll back if any of the 10 expected groups had zero rows updated)
DO $$
DECLARE
    expected_groups TEXT[] := ARRAY[
        'Erectile-Dysfunction',
        'Hypertension(5th Edition)',
        'Heart-Failure(5th Edition)',
        'Pulmonary-Arterial-Hypertension(2011)',
        'Breast-Cancer(3rd Edition)',
        'STEMI(4th Edition)',
        'NSTEMI(2011)',
        'Dyslipidaemia(6th-Edition)',
        'Atrial-Fibrillation(2012)',
        'NSTE-ACS(3rd Edition)'
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
