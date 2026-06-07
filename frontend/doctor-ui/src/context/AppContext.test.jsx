// @vitest-environment jsdom
/**
 * L2 — AppContext reducer unit tests.
 *
 * `appReducer` is the single source of truth for all consultation state. The
 * most safety-critical action is APPLY_SAFETY_DECISIONS: it mutates the care
 * plan when a clinician overrides a Stage-6 safety flag, matching by
 * case-insensitive substring across EVERY medication section (including
 * `contraindicated`). These tests pin that behaviour plus the generic care-item
 * and medication editors, the diagnosis-selection toggle, the pipeline
 * accumulators, and the PHI-leak guard (refresh resets to initialState).
 *
 * Heavy side-effect imports (`lib/supabase`, `lib/clinicalApi`) are mocked so
 * importing AppContext never spins up a real Supabase client; the reducer itself
 * is pure and exercised directly.
 */
import { describe, it, expect, vi } from 'vitest';

vi.mock('../lib/supabase', () => ({
  isSupabaseConfigured: () => false,   // called at module-eval — must be callable
  supabase: { channel: () => ({}), removeChannel: () => {} },
}));
vi.mock('../lib/clinicalApi', () => ({
  runClinicalPlan: vi.fn(),
  runDDxStream: vi.fn(),
  resynthesizePlanStream: vi.fn(),
  summarisePriorVisit: vi.fn(),
}));

import { appReducer, initialState, loadPersistedState } from './AppContext';

// A minimal carePlan with meds spread across sections (incl. contraindicated)
// and the three generic care sections.
const carePlanFixture = () => ({
  medications: {
    start:           [{ id: 1, name: 'Enalapril 5mg', dose: '5mg', accepted: true }],
    continue:        [{ id: 2, name: 'Metformin 1g', dose: '1g', accepted: true }],
    stop:            [],
    change:          [],
    contraindicated: [{ id: 3, name: 'Losartan 50mg', dose: '50mg', instructions: 'OD', accepted: true }],
  },
  interventions: [{ id: 10, name: 'Echocardiogram', accepted: true }],
  monitoring:    [{ id: 20, parameter: 'Potassium', schedule: '2 weeks', accepted: true }],
  lifestyle:     [{ id: 30, goal: 'Salt restriction', category: 'Diet', accepted: true }],
});

const withCarePlan = () => ({ ...initialState, carePlan: carePlanFixture() });

describe('APPLY_SAFETY_DECISIONS', () => {
  it('removes a flagged drug from EVERY section, including contraindicated', () => {
    const state = withCarePlan();
    const next = appReducer(state, {
      type: 'APPLY_SAFETY_DECISIONS',
      payload: { decisions: { 'k1': { decision: 'remove', drugs: ['Losartan'] } } },
    });
    expect(next.carePlan.medications.contraindicated).toHaveLength(0);
    // untouched sections survive
    expect(next.carePlan.medications.start).toHaveLength(1);
  });

  it('replace with a named alternative swaps the name, wipes the dose, and prepends [REPLACED from X]', () => {
    const state = withCarePlan();
    const next = appReducer(state, {
      type: 'APPLY_SAFETY_DECISIONS',
      payload: { decisions: { 'k1': { decision: 'replace', drugs: ['Losartan'], alternative: 'Labetalol' } } },
    });
    const med = next.carePlan.medications.contraindicated[0];
    expect(med.name).toBe('Labetalol');
    expect(med.dose).toBe('');
    expect(med.instructions).toMatch(/\[REPLACED from Losartan 50mg\]/);
  });

  it('generic replace (no alternative) tags a med that has instructions with the [NEEDS REPLACEMENT] prefix', () => {
    const state = withCarePlan();   // contraindicated Losartan has instructions 'OD'
    const next = appReducer(state, {
      type: 'APPLY_SAFETY_DECISIONS',
      payload: { decisions: { 'k1': { decision: 'replace', drugs: ['Losartan'] } } },
    });
    expect(next.carePlan.medications.contraindicated[0].instructions).toMatch(/\[NEEDS REPLACEMENT — safety flag\] OD/);
  });

  it('matches case-insensitively on a substring of the med name', () => {
    const state = withCarePlan();
    const next = appReducer(state, {
      type: 'APPLY_SAFETY_DECISIONS',
      payload: { decisions: { 'k1': { decision: 'remove', drugs: ['enalapril'] } } }, // lower-case
    });
    expect(next.carePlan.medications.start).toHaveLength(0);
  });

  it('"keep" and decisions without drugs are no-ops', () => {
    const state = withCarePlan();
    const next = appReducer(state, {
      type: 'APPLY_SAFETY_DECISIONS',
      payload: { decisions: {
        keepKey: { decision: 'keep', drugs: ['Losartan'] },
        noDrugs: { decision: 'remove' },
      } },
    });
    expect(next.carePlan.medications.contraindicated).toHaveLength(1);
  });

  it('returns state unchanged when there are no decisions or no medications', () => {
    const noMeds = { ...initialState, carePlan: null };
    expect(appReducer(noMeds, { type: 'APPLY_SAFETY_DECISIONS', payload: { decisions: { k: { decision: 'remove', drugs: ['x'] } } } })).toBe(noMeds);
    const state = withCarePlan();
    expect(appReducer(state, { type: 'APPLY_SAFETY_DECISIONS', payload: {} })).toBe(state);
  });

  it('does not mutate the input state (immutability)', () => {
    const state = withCarePlan();
    appReducer(state, {
      type: 'APPLY_SAFETY_DECISIONS',
      payload: { decisions: { k1: { decision: 'remove', drugs: ['Losartan'] } } },
    });
    expect(state.carePlan.medications.contraindicated).toHaveLength(1); // original intact
  });
});

describe('generic care-item editors (interventions / monitoring / lifestyle)', () => {
  it.each(['interventions', 'monitoring', 'lifestyle'])('ADD_CARE_ITEM appends a blank accepted item to %s', (section) => {
    const next = appReducer(withCarePlan(), { type: 'ADD_CARE_ITEM', payload: { section } });
    const list = next.carePlan[section];
    expect(list).toHaveLength(2);
    expect(list[1].accepted).toBe(true);
    expect(String(list[1].id)).toMatch(/^new-/);
  });

  it('DELETE_CARE_ITEM removes by id', () => {
    const next = appReducer(withCarePlan(), { type: 'DELETE_CARE_ITEM', payload: { section: 'interventions', id: 10 } });
    expect(next.carePlan.interventions).toHaveLength(0);
  });

  it('UPDATE_CARE_ITEM_FIELD updates a single field', () => {
    const next = appReducer(withCarePlan(), { type: 'UPDATE_CARE_ITEM_FIELD', payload: { section: 'monitoring', id: 20, field: 'schedule', value: 'weekly' } });
    expect(next.carePlan.monitoring[0].schedule).toBe('weekly');
  });
});

describe('medication editors', () => {
  it('ADD_MEDICATION appends to the continue section', () => {
    const next = appReducer(withCarePlan(), { type: 'ADD_MEDICATION' });
    expect(next.carePlan.medications.continue).toHaveLength(2);
    expect(next.carePlan.medications.continue[1].displayAction).toBe('continue');
  });

  it('DELETE_MEDICATION removes from the named section', () => {
    const next = appReducer(withCarePlan(), { type: 'DELETE_MEDICATION', payload: { actionType: 'start', medId: 1 } });
    expect(next.carePlan.medications.start).toHaveLength(0);
  });

  it('UPDATE_MEDICATION_FIELD edits a field within a section', () => {
    const next = appReducer(withCarePlan(), { type: 'UPDATE_MEDICATION_FIELD', payload: { actionType: 'start', medId: 1, field: 'dose', value: '10mg' } });
    expect(next.carePlan.medications.start[0].dose).toBe('10mg');
  });

  it('UPDATE_MEDICATION toggles acceptance', () => {
    const next = appReducer(withCarePlan(), { type: 'UPDATE_MEDICATION', payload: { type: 'start', id: 1, accepted: false } });
    expect(next.carePlan.medications.start[0].accepted).toBe(false);
  });

  it('CHANGE_MEDICATION_ACTION moves a med between sections', () => {
    const next = appReducer(withCarePlan(), { type: 'CHANGE_MEDICATION_ACTION', payload: { fromAction: 'start', toAction: 'stop', medId: 1 } });
    expect(next.carePlan.medications.start).toHaveLength(0);
    expect(next.carePlan.medications.stop.map((m) => m.id)).toContain(1);
  });

  it('CHANGE_MEDICATION_ACTION is a no-op for same section or missing med', () => {
    const state = withCarePlan();
    expect(appReducer(state, { type: 'CHANGE_MEDICATION_ACTION', payload: { fromAction: 'start', toAction: 'start', medId: 1 } })).toBe(state);
    expect(appReducer(state, { type: 'CHANGE_MEDICATION_ACTION', payload: { fromAction: 'start', toAction: 'stop', medId: 999 } })).toBe(state);
  });
});

describe('diagnosis selection toggle', () => {
  const withDiag = () => ({ ...initialState, diagnosis: { differentials: [], selectedDiagnosisIds: [1] } });
  it('adds an unselected id', () => {
    expect(appReducer(withDiag(), { type: 'SELECT_DIAGNOSIS', payload: 2 }).diagnosis.selectedDiagnosisIds).toEqual([1, 2]);
  });
  it('removes an already-selected id', () => {
    expect(appReducer(withDiag(), { type: 'SELECT_DIAGNOSIS', payload: 1 }).diagnosis.selectedDiagnosisIds).toEqual([]);
  });
});

describe('pipeline accumulators + resets', () => {
  it('APPEND_PIPELINE_EVENT preserves order', () => {
    let s = initialState;
    s = appReducer(s, { type: 'APPEND_PIPELINE_EVENT', payload: { stage: 2, name: 'DDx' } });
    s = appReducer(s, { type: 'APPEND_PIPELINE_EVENT', payload: { stage: 3, name: 'Route' } });
    expect(s.pipelineEvents.map((e) => e.stage)).toEqual([2, 3]);
  });

  it('APPEND_THINKING_CHUNK concatenates per node', () => {
    let s = initialState;
    s = appReducer(s, { type: 'APPEND_THINKING_CHUNK', payload: { node: 'ddx', chunk: 'Hello ' } });
    s = appReducer(s, { type: 'APPEND_THINKING_CHUNK', payload: { node: 'ddx', chunk: 'world' } });
    expect(s.pipelineThinking.ddx).toBe('Hello world');
  });

  it('RESET_PIPELINE clears the pipeline slices', () => {
    const dirty = { ...initialState, pipelineEvents: [{ stage: 2 }], safetyReport: { flags: [] }, resynthOverride: {} };
    const next = appReducer(dirty, { type: 'RESET_PIPELINE' });
    expect(next.pipelineEvents).toEqual([]);
    expect(next.safetyReport).toBeNull();
    expect(next.resynthOverride).toBeNull();
  });

  it('RESET_PIPELINE_FROM_STAGE keeps only events before the given stage', () => {
    const dirty = { ...initialState, pipelineEvents: [{ stage: 2 }, { stage: 3 }, { stage: 5 }] };
    const next = appReducer(dirty, { type: 'RESET_PIPELINE_FROM_STAGE', payload: 3 });
    expect(next.pipelineEvents.map((e) => e.stage)).toEqual([2]);
  });
});

describe('vitals source tagging', () => {
  it('defaults the source to manual and clears quality', () => {
    const next = appReducer(initialState, { type: 'SET_VITALS', payload: { hr: '72' } });
    expect(next.vitalsSource).toBe('manual');
    expect(next.vitalsQuality).toBeNull();
  });
  it('tags rPPG source + quality when the dispatch declares it', () => {
    const next = appReducer(initialState, { type: 'SET_VITALS', payload: { hr: '72' }, source: 'rppg', quality: 88 });
    expect(next.vitalsSource).toBe('rppg');
    expect(next.vitalsQuality).toBe(88);
  });
});

describe('global resets / guards', () => {
  it('RESET returns initialState', () => {
    const dirty = { ...initialState, currentStep: 4, clinicalNotes: 'leak' };
    expect(appReducer(dirty, { type: 'RESET' })).toBe(initialState);
  });

  it('an unknown action returns the same state reference', () => {
    expect(appReducer(initialState, { type: 'NOPE' })).toBe(initialState);
  });

  it('PHI-leak guard: loadPersistedState clears storage and returns a clean initialState', () => {
    sessionStorage.setItem('cpg.consultation.v1', JSON.stringify({ patient: { name: 'Prev Patient' } }));
    const loaded = loadPersistedState();
    expect(loaded).toBe(initialState);
    expect(sessionStorage.getItem('cpg.consultation.v1')).toBeNull();
  });
});
