/**
 * Unit tests for the pure backend-JSON -> UI-state mappers.
 *
 * These guard two documented bug-classes (see CLAUDE.md):
 *  1. The Stage-2 DDx `final_score` can exceed 1.0 (base + incl_boost − excl_penalty
 *     with a red-flag boost). The card must never render >100% — mapDdxToDiagnosis
 *     clamps to [0,1].
 *  2. The "phantom carePlan.disposition" trap: mapTreatmentPlanToCarePlan returns
 *     referrals/interventions/lifestyle/monitoring at the TOP LEVEL of carePlan;
 *     reads via a non-existent `carePlan.disposition.*` silently persisted NULLs
 *     for ~4 weeks. These tests pin the real top-level shape.
 */
import { describe, it, expect } from 'vitest';
import { mapDdxToDiagnosis, mapTreatmentPlanToCarePlan } from './clinicalMappers';

describe('mapDdxToDiagnosis — score clamping', () => {
  it('clamps a final_score > 1.0 to 100% (JA21 pre-eclampsia: 0.83 + 0.24 boost = 1.07)', () => {
    const out = mapDdxToDiagnosis(
      [{ title: 'Pre-eclampsia', code: 'O14', score_breakdown: { final_score: 1.07 } }],
      [],
    );
    expect(out.differentials[0].probability).toBe(100);
    expect(out.differentials[0].probability).toBeLessThanOrEqual(100);
  });

  it('clamps a negative final_score to 0%', () => {
    const out = mapDdxToDiagnosis(
      [{ title: 'Excluded Dx', code: 'X00', score_breakdown: { final_score: -0.3 } }],
      [],
    );
    expect(out.differentials[0].probability).toBe(0);
  });

  it('falls back to similarity when no score_breakdown is present', () => {
    const out = mapDdxToDiagnosis([{ title: 'Dx', code: 'D1', similarity: 0.62 }], []);
    expect(out.differentials[0].probability).toBe(62);
  });

  it('assigns risk tiers at the documented 0.75 / 0.45 thresholds', () => {
    const out = mapDdxToDiagnosis(
      [
        { title: 'High', code: 'H', score_breakdown: { final_score: 0.80 } },
        { title: 'Edge-high', code: 'EH', score_breakdown: { final_score: 0.75 } },
        { title: 'Mid', code: 'M', score_breakdown: { final_score: 0.50 } },
        { title: 'Edge-mid', code: 'EM', score_breakdown: { final_score: 0.45 } },
        { title: 'Low', code: 'L', score_breakdown: { final_score: 0.20 } },
      ],
      [],
    );
    expect(out.differentials.map((d) => d.risk)).toEqual([
      'high', 'high', 'medium', 'medium', 'low',
    ]);
  });

  it('auto-selects the top differential and passes cpgsMatched through', () => {
    const out = mapDdxToDiagnosis(
      [
        { title: 'A', code: 'A', score_breakdown: { final_score: 0.9 } },
        { title: 'B', code: 'B', score_breakdown: { final_score: 0.4 } },
      ],
      ['CPG Hypertension'],
    );
    expect(out.selectedDiagnosisIds).toEqual([1]);
    expect(out.cpgsMatched).toEqual(['CPG Hypertension']);
  });

  it('returns an empty selection for an empty ddx list', () => {
    const out = mapDdxToDiagnosis([], []);
    expect(out.differentials).toEqual([]);
    expect(out.selectedDiagnosisIds).toEqual([]);
  });
});

describe('mapTreatmentPlanToCarePlan — top-level shape (no phantom disposition)', () => {
  const plan = {
    summary: 'Test plan',
    recommendations: [
      { type: 'pharmacological', action: 'start', intervention: 'Enalapril 5mg OD', rationale: 'HFrEF — ACEi first line', cpg_source: 'CPG Heart Failure §4.1' },
      { type: 'pharmacological', action: 'contraindicated', intervention: 'Losartan 50mg', rationale: 'Pregnancy 30 weeks — ARB teratogenic', cpg_source: 'CPG Heart-Disease-in-Pregnancy §2' },
      { type: 'referral', intervention: 'Refer to Cardiology (urgent)', rationale: 'LVEF 25%', cpg_source: 'CPG Heart Failure §6' },
      { type: 'lifestyle', intervention: 'Salt restriction — reduce sodium intake', rationale: 'Fluid overload', cpg_source: 'CPG Heart Failure §5' },
      { type: 'procedure', intervention: 'Echocardiogram — reassess LVEF', rationale: 'Baseline function', cpg_source: 'CPG Heart Failure §3' },
    ],
    monitoring: ['Serum potassium', { parameter: 'eGFR', schedule: 'in 2 weeks', target: '>30' }],
    follow_up: ['Review in 4 weeks'],
  };

  it('exposes referrals / interventions / lifestyle / monitoring at the TOP level (not under disposition)', () => {
    const cp = mapTreatmentPlanToCarePlan(plan);
    expect(cp.disposition).toBeUndefined();           // the phantom path must NOT exist
    expect(Array.isArray(cp.referrals)).toBe(true);
    expect(Array.isArray(cp.interventions)).toBe(true);
    expect(Array.isArray(cp.lifestyle)).toBe(true);
    expect(Array.isArray(cp.monitoring)).toBe(true);
  });

  it('splits pharmacological recs into action sections, keeping contraindicated visible', () => {
    const cp = mapTreatmentPlanToCarePlan(plan);
    expect(cp.medications.start.map((m) => m.name)).toContain('Enalapril');
    // contraindicated MUST survive — the Stage-6 critic flags entries here; if
    // dropped, the clinician sees safety flags about drugs they can't audit.
    expect(cp.medications.contraindicated.map((m) => m.name)).toContain('Losartan');
  });

  it('derives referral department + urgency from prose', () => {
    const cp = mapTreatmentPlanToCarePlan(plan);
    const cardio = cp.referrals.find((r) => /cardiology/i.test(r.specialty));
    expect(cardio).toBeTruthy();
    expect(cardio.urgency).toBe('Urgent');
  });

  it('normalises monitoring entries whether string or object', () => {
    const cp = mapTreatmentPlanToCarePlan(plan);
    expect(cp.monitoring[0]).toMatchObject({ parameter: 'Serum potassium', schedule: null });
    expect(cp.monitoring[1]).toMatchObject({ parameter: 'eGFR', schedule: 'in 2 weeks', target: '>30' });
  });

  it('builds CPG references from cpg_source and resolves the full guideline name', () => {
    const cp = mapTreatmentPlanToCarePlan(plan);
    expect(cp.cpgReferences.length).toBeGreaterThan(0);
    const hf = cp.cpgReferences.find((r) => r.cpgFullName === 'Management of Heart Failure');
    expect(hf).toBeTruthy();
    expect(hf.section).toBe('Section 4.1');
  });
});
