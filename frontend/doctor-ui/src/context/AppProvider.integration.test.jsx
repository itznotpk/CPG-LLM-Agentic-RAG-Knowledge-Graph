// @vitest-environment jsdom
/**
 * L4 — AppProvider data-flow / integration tests.
 *
 * These drive the REAL provider (not just the reducer) with the API boundary
 * mocked — `lib/supabase` and `lib/clinicalApi` are stubbed, so no network/SSE,
 * but the provider's orchestration logic runs for real. They guard the L4
 * invariants documented in CLAUDE.md:
 *
 *  1. NULL-referrals regression — `finalizePlan` must read the care-plan fields
 *     off the TOP LEVEL (`carePlan.referrals`, not `carePlan.disposition.*`) and
 *     pass them to `updateConsultation`. Reading the phantom path persisted NULLs
 *     for ~4 weeks.
 *  2. Stage-6 audit — the safety verdict + acknowledgement reach the RPC.
 *  3. Empty-selection guard — `confirmDiagnosis` throws (fail-loud) rather than
 *     routing an empty selection into a silent degraded plan.
 *  4. SSE → state — a DDx run records the terminal stage_update event and lands
 *     the wizard on Step 2 with the mapped diagnosis + consultation id.
 *
 * (MSW-over-SSE is deliberately not used: the SSE wire parsing lives inside
 * clinicalApi.js and is coverable on its own; here we test the provider that
 * consumes its already-parsed result.)
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, act, cleanup } from '@testing-library/react';
import React, { useEffect } from 'react';

const sb = vi.hoisted(() => ({
  isSupabaseConfigured: vi.fn(() => true),
  searchPatientByNRIC: vi.fn(),
  startConsultation: vi.fn(),
  updateConsultation: vi.fn(),
  updatePatientMedications: vi.fn(),
  updatePatientRiskLevel: vi.fn(),
  updatePatientStatus: vi.fn(),
  uploadCarePlanPDF: vi.fn(),
  writePriorVisitSummary: vi.fn(),
  getLatestPriorVisitSummary: vi.fn(),
  saveLiveVitals: vi.fn(),
  saveConsultationSeverity: vi.fn(),
  savePatientVitals: vi.fn(),
}));
const api = vi.hoisted(() => ({
  runClinicalPlan: vi.fn(),
  runDDxStream: vi.fn(),
  resynthesizePlanStream: vi.fn(),
  summarisePriorVisit: vi.fn(),
}));

vi.mock('../lib/supabase', () => ({
  ...sb,
  // chainable realtime channel stub so the provider's subscribe effect is inert
  supabase: {
    channel: () => {
      const ch = {};
      ch.on = () => ch;
      ch.subscribe = () => ch;
      return ch;
    },
    removeChannel: () => {},
  },
}));
vi.mock('../lib/clinicalApi', () => api);

import { AppProvider, useApp } from './AppContext';

// Capture the live context value each render so tests can dispatch + call actions.
const ctx = { current: null };
function Harness() {
  ctx.current = useApp();
  return null;
}
const mountProvider = () => render(<AppProvider><Harness /></AppProvider>);

beforeEach(() => {
  vi.clearAllMocks();
  sb.isSupabaseConfigured.mockReturnValue(true);
  sb.searchPatientByNRIC.mockResolvedValue({ found: false });
  sb.startConsultation.mockResolvedValue({ success: true, consultationId: 5, consultationNumber: 1 });
  sb.updateConsultation.mockResolvedValue({ success: true });
  sb.updatePatientMedications.mockResolvedValue({ success: true });
  sb.updatePatientRiskLevel.mockResolvedValue({ success: true });
  sb.updatePatientStatus.mockResolvedValue({ success: true });
  sb.saveLiveVitals.mockResolvedValue({});
  sb.saveConsultationSeverity.mockResolvedValue({});
  sb.getLatestPriorVisitSummary.mockResolvedValue({ summary: null, visitMeta: null });
  sb.writePriorVisitSummary.mockResolvedValue({ success: true });
});
afterEach(() => cleanup());

const seededCarePlan = () => ({
  clinicalSummary: 'HFrEF plan',
  medications: { start: [{ id: 1, name: 'Enalapril' }], stop: [], change: [], continue: [], contraindicated: [] },
  interventions: [{ id: 10, name: 'Echocardiogram' }],
  monitoring: [{ id: 20, parameter: 'Potassium' }],
  referrals: [{ id: 1, specialty: 'Cardiology', urgency: 'Urgent' }],
  lifestyle: [{ id: 30, goal: 'Salt restriction' }],
  cpgReferences: [{ cpgFullName: 'Management of Heart Failure' }],
});

describe('finalizePlan — top-level care-plan persistence (NULL-referrals guard)', () => {
  it('passes the TOP-LEVEL referrals/interventions/monitoring/lifestyle to updateConsultation', async () => {
    mountProvider();
    await act(async () => {
      ctx.current.dispatch({ type: 'SET_PATIENT', payload: { nsn: '900101-01-1234', name: 'Test' } });
      ctx.current.dispatch({ type: 'SET_CONSULTATION_ID', payload: 5 });
      ctx.current.dispatch({ type: 'SET_CARE_PLAN', payload: seededCarePlan() });
    });
    await act(async () => { await ctx.current.finalizePlan({}); });

    expect(sb.updateConsultation).toHaveBeenCalledTimes(1);
    const [id, payload] = sb.updateConsultation.mock.calls[0];
    expect(id).toBe(5);
    // The regression: these would be null if read via carePlan.disposition.*
    expect(payload.referrals).toEqual([{ id: 1, specialty: 'Cardiology', urgency: 'Urgent' }]);
    expect(payload.interventions).toHaveLength(1);
    expect(payload.monitoring).toHaveLength(1);
    expect(payload.lifestyleGoals).toHaveLength(1);     // mapped from carePlan.lifestyle
    expect(payload.cpgReferences).toHaveLength(1);
  });

  it('maps the Stage-6 safety report + override into the audit fields', async () => {
    mountProvider();
    await act(async () => {
      ctx.current.dispatch({ type: 'SET_PATIENT', payload: { nsn: '900101-01-1234' } });
      ctx.current.dispatch({ type: 'SET_CONSULTATION_ID', payload: 5 });
      ctx.current.dispatch({ type: 'SET_CARE_PLAN', payload: seededCarePlan() });
      ctx.current.dispatch({ type: 'SET_SAFETY_REPORT', payload: {
        safe_to_proceed: false,
        flags: [{ severity: 'CRITICAL', title: 'Losartan teratogen', detail: 'ARB in pregnancy', flag_type: 'contraindication', source: 'graph' }],
      } });
    });
    await act(async () => {
      await ctx.current.finalizePlan({ safetyOverride: { acknowledged: true, by: 'Dr Tey', at: '2026-06-08T00:00:00Z' } });
    });

    const payload = sb.updateConsultation.mock.calls[0][1];
    expect(payload.safeToProceed).toBe(false);
    expect(payload.safetyAcknowledged).toBe(true);
    expect(payload.safetyAcknowledgedBy).toBe('Dr Tey');
    expect(payload.safetyFlags).toHaveLength(1);
    expect(payload.safetyFlags[0]).toMatchObject({ severity: 'CRITICAL', source: 'graph', flag_type: 'contraindication' });
  });
});

describe('confirmDiagnosis — empty-selection fail-loud guard', () => {
  it('throws instead of routing an empty selection', async () => {
    mountProvider();
    await act(async () => {
      ctx.current.dispatch({ type: 'SET_DIAGNOSIS', payload: { differentials: [], selectedDiagnosisIds: [] } });
    });
    await expect(ctx.current.confirmDiagnosis()).rejects.toThrow(/No diagnosis selected/i);
    // It must not have attempted a plan synthesis with nothing selected.
    expect(api.resynthesizePlanStream).not.toHaveBeenCalled();
  });
});

describe('analyzeAssessment — SSE result → state slices', () => {
  it('records the terminal stage_update, maps the DDx, and lands on Step 2 with a consultation id', async () => {
    api.runDDxStream.mockImplementation(async (patient, vitals, notes, mpis, onStage) => {
      onStage({ stage: 2, name: 'Differential Diagnosis', status: 'complete', detail: '1 DDx' });
      return { ddx: [{ title: 'Hypertension', code: 'I10', score_breakdown: { final_score: 0.82 } }] };
    });

    mountProvider();
    await act(async () => {
      ctx.current.dispatch({ type: 'SET_PATIENT', payload: { nsn: '900101-01-1234', name: 'Test' } });
    });
    await act(async () => { await ctx.current.analyzeAssessment(); });

    expect(ctx.current.state.currentConsultationId).toBe(5);              // startConsultation wired in
    expect(ctx.current.state.currentStep).toBe(2);                       // wizard advanced
    expect(ctx.current.state.diagnosis.differentials).toHaveLength(1);
    expect(ctx.current.state.diagnosis.differentials[0].icdCode).toBe('I10');
    // The terminal stage_update (status: complete) is recorded — the event the
    // display-layer counting rule reads off.
    const terminal = ctx.current.state.pipelineEvents.find((e) => e.stage === 2 && e.status === 'complete');
    expect(terminal).toBeTruthy();
  });
});
