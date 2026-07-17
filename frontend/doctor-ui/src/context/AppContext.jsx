import React, { createContext, useContext, useState, useReducer, useEffect, useRef, useMemo } from 'react';
import {
  sampleDiagnosis,
  sampleCarePlan,
} from '../data/sampleData';
import { runClinicalPlan, runDDxStream, resynthesizePlanStream, summarisePriorVisit } from '../lib/clinicalApi';
// NOTE: generateCarePlanPDFBlob is no longer used — PDF upload now uses the DOM-captured blob
// from generatePdfFromElement() in OutputSection, ensuring the Supabase PDF matches the
// "Export PDF" output exactly.
import { mapDdxToDiagnosis, mapTreatmentPlanToCarePlan } from '../lib/clinicalMappers';
import { getCuratedInternationalGuidance } from '../data/internationalGuidanceData';
import {
  supabase,
  searchPatientByNRIC,
  savePatientVitals,
  isSupabaseConfigured,
  startConsultation,
  updateConsultation,
  updatePatientMedications,
  updatePatientRiskLevel,
  updatePatientStatus,
  uploadCarePlanPDF,
  writePriorVisitSummary,
  getLatestPriorVisitSummary,
  saveLiveVitals,
  saveConsultationSeverity,
} from '../lib/supabase';
import { getNowUTC8, getTodayUTC8 } from '../utils/timezone';

// Always use Supabase for patient data
const USE_SUPABASE = isSupabaseConfigured();

const AppContext = createContext();

export const initialState = {
  currentStep: 1, // 1: Input, 2: Diagnosis, 3: CarePlan, 4: Output
  patient: {
    name: '',
    dob: '',
    nsn: '',
    gender: '',
    age: null,
    vitalsHistory: [],
  },
  clinicalNotes: '',
  vitals: {
    bpSystolic: '',
    bpDiastolic: '',
    hr: '',
    temp: '',
    rr: '',
    spo2: '',
    weight: '',
    height: '',
  },
  vitalsSource: 'manual', // 'manual' | 'rppg' — how the current vitals were captured
  vitalsQuality: null,    // rPPG signal quality (%) when source === 'rppg'
  mpisData: {
    race: '',
    ethnicity: '',
    allergies: '',
    comorbidities: [],
    currentMeds: [],
  },
  severityStaging: {},
  mpisSynced: false,
  nextReviewDate: '', // TCA date from step 1
  patientStatus: 'active', // Patient status from step 3 (active, follow-up, discharged)
  currentConsultationId: null, // ID of the current consultation in progress
  currentConsultationNumber: null, // per-patient consultation_number (used by prior-visit RPCs)
  priorVisit: null, // PriorVisitSummary from previous consultation, surfaced into PatientCase
  priorVisitMeta: null, // { consultationId, consultationNumber, consultationTime } for the row that produced priorVisit
  clinicalPlanResponse: null,
  diagnosis: null,
  carePlan: null,
  isAnalyzing: false,
  isGeneratingPlan: false,
  pipelineEvents: [],      // ordered log: [...stage_updates, ...sub_steps]
  pipelineThinking: {},    // { [nodeName: string]: string }  accumulated thinking text
  pipelineSummary: null,   // { elapsed_ms, ddxCount, cpgCount, chunkCount } set on final_result
  resynthOverride: null,   // { codes: string[], major_code: string } set when clinician override runs
  safetyReport: null,      // SafetyReport | null — set on safety_review SSE event
  ddxSuggestion: null,     // DDxSuggestion payload (top-5 candidates + headless default) — captured before tier selection
  ddxQualityDrops: [],     // [{tier, code, expected_slots, actual_slots}] from stage3_quality_drop SSE
  ddxExcludedCodes: [],    // accumulated ICD codes already shown across Step-2 regenerations (union of every top-5 seen)
  isRegeneratingDdx: false,// true while a Step-2 "Regenerate differentials" run is in flight
  ddxRegenExhausted: false,// true when the last regenerate returned no further distinct candidates
  ebmEvidence: [],         // EBM literature evidence — set on ebm_evidence SSE event during plan generation
};

// Snapshot persistence intentionally disabled — refreshes start from a clean
// state so a previous patient's fields can't leak into a new-patient entry.
const PERSIST_KEY = 'cpg.consultation.v1';
initialState.internationalGuidanceCheckEnabled = false;
initialState.internationalGuidanceDecision = 'local';
initialState.internationalGuidanceRationale = '';

export function loadPersistedState() {
  try { sessionStorage.removeItem(PERSIST_KEY); } catch { /* ignore */ }
  return initialState;
}

function clearPersistedState() {
  try { sessionStorage.removeItem(PERSIST_KEY); } catch { /* ignore */ }
}

export function appReducer(state, action) {
  switch (action.type) {
    case 'SET_PATIENT':
      return { ...state, patient: { ...state.patient, ...action.payload } };
    case 'SET_CLINICAL_NOTES':
      return { ...state, clinicalNotes: action.payload };
    case 'SET_NEXT_REVIEW_DATE':
      return { ...state, nextReviewDate: action.payload };
    case 'SET_PATIENT_STATUS':
      return { ...state, patientStatus: action.payload };
    case 'SET_CONSULTATION_ID':
      return { ...state, currentConsultationId: action.payload };
    case 'SET_CONSULTATION_NUMBER':
      return { ...state, currentConsultationNumber: action.payload };
    case 'SET_PRIOR_VISIT':
      return { ...state, priorVisit: action.payload?.summary ?? null, priorVisitMeta: action.payload?.meta ?? null };
    case 'SET_VITALS':
      // Manual edits reset the source to 'manual' unless the dispatch explicitly
      // tags it (rPPG apply passes source/quality so the live_vitals row is labelled).
      return {
        ...state,
        vitals: { ...state.vitals, ...action.payload },
        vitalsSource: action.source || 'manual',
        vitalsQuality: action.source === 'rppg' ? (action.quality ?? null) : null,
      };
    case 'SET_SEVERITY_STAGING':
      return { ...state, severityStaging: action.payload };
    case 'SET_MPIS_DATA':
      return { ...state, mpisData: action.payload, mpisSynced: true };
    case 'SET_CLINICAL_PLAN_RESPONSE':
      return { ...state, clinicalPlanResponse: action.payload };
    case 'SET_DIAGNOSIS':
      return { ...state, diagnosis: action.payload };
    case 'SET_INTERNATIONAL_GUIDANCE_CHECK':
      return { ...state, internationalGuidanceCheckEnabled: Boolean(action.payload) };
    case 'SET_INTERNATIONAL_GUIDANCE_DECISION':
      return { ...state, internationalGuidanceDecision: action.payload };
    case 'SET_INTERNATIONAL_GUIDANCE_RATIONALE':
      return { ...state, internationalGuidanceRationale: action.payload };
    case 'SELECT_DIAGNOSIS': {
      const currentSelected = state.diagnosis?.selectedDiagnosisIds || [];
      const diagnosisId = action.payload;
      const isAlreadySelected = currentSelected.includes(diagnosisId);
      const newSelected = isAlreadySelected
        ? currentSelected.filter(id => id !== diagnosisId)
        : [...currentSelected, diagnosisId];
      return {
        ...state,
        diagnosis: {
          ...state.diagnosis,
          selectedDiagnosisIds: newSelected
        }
      };
    }
    case 'SET_CARE_PLAN':
      return { ...state, carePlan: action.payload };
    case 'SET_STEP':
      return { ...state, currentStep: action.payload };
    case 'SET_ANALYZING':
      return { ...state, isAnalyzing: action.payload };
    case 'SET_GENERATING_PLAN':
      return { ...state, isGeneratingPlan: action.payload };
    case 'UPDATE_CARE_PLAN_ITEM':
      return {
        ...state,
        carePlan: {
          ...state.carePlan,
          [action.payload.section]: updateItemAcceptance(
            state.carePlan[action.payload.section],
            action.payload.id,
            action.payload.accepted
          ),
        },
      };
    case 'UPDATE_MEDICATION':
      return {
        ...state,
        carePlan: {
          ...state.carePlan,
          medications: {
            ...state.carePlan.medications,
            [action.payload.type]: state.carePlan.medications[action.payload.type].map((med) =>
              med.id === action.payload.id ? { ...med, accepted: action.payload.accepted } : med
            ),
          },
        },
      };
    case 'ADD_MEDICATION': {
      const newMed = {
        id: `new-${Date.now()}`,
        name: '',
        dose: '',
        reason: '',
        instructions: '',
        kiv: '',
        cpgRef: 'Manual entry',
        displayAction: 'continue',
      };
      return {
        ...state,
        carePlan: {
          ...state.carePlan,
          medications: {
            ...state.carePlan.medications,
            continue: [...(state.carePlan.medications?.continue || []), newMed],
          },
        },
      };
    }
    case 'UPDATE_MEDICATION_FIELD': {
      // Update a single field on a medication within its action category
      const { actionType, medId, field, value } = action.payload;
      return {
        ...state,
        carePlan: {
          ...state.carePlan,
          medications: {
            ...state.carePlan.medications,
            [actionType]: (state.carePlan.medications[actionType] || []).map((med) =>
              med.id === medId ? { ...med, [field]: value } : med
            ),
          },
        },
      };
    }
    case 'CHANGE_MEDICATION_ACTION': {
      // Move a medication from one action category to another
      const { fromAction, toAction, medId: moveMedId } = action.payload;
      if (fromAction === toAction) return state;
      const fromList = state.carePlan.medications[fromAction] || [];
      const medToMove = fromList.find((m) => m.id === moveMedId);
      if (!medToMove) return state;
      return {
        ...state,
        carePlan: {
          ...state.carePlan,
          medications: {
            ...state.carePlan.medications,
            [fromAction]: fromList.filter((m) => m.id !== moveMedId),
            [toAction]: [...(state.carePlan.medications[toAction] || []), medToMove],
          },
        },
      };
    }
    case 'DELETE_MEDICATION': {
      const { actionType: delAction, medId: delMedId } = action.payload;
      return {
        ...state,
        carePlan: {
          ...state.carePlan,
          medications: {
            ...state.carePlan.medications,
            [delAction]: (state.carePlan.medications[delAction] || []).filter((m) => m.id !== delMedId),
          },
        },
      };
    }
    case 'ADD_CARE_ITEM': {
      // section ∈ 'interventions' | 'monitoring' | 'lifestyle'
      const { section: addSection } = action.payload;
      const blanks = {
        interventions: { name: '', rationale: '', urgency: 'Routine', cpgRef: 'Manual entry' },
        monitoring:    { parameter: '', schedule: '', target: '', cpgRef: 'Manual entry' },
        lifestyle:     { goal: '', category: 'Lifestyle', cpgRef: 'Manual entry' },
      };
      const newItem = { id: `new-${Date.now()}`, accepted: true, ...(blanks[addSection] || {}) };
      return {
        ...state,
        carePlan: {
          ...state.carePlan,
          [addSection]: [...(state.carePlan[addSection] || []), newItem],
        },
      };
    }
    case 'DELETE_CARE_ITEM': {
      const { section: delSection, id: delId } = action.payload;
      return {
        ...state,
        carePlan: {
          ...state.carePlan,
          [delSection]: (state.carePlan[delSection] || []).filter((i) => i.id !== delId),
        },
      };
    }
    case 'UPDATE_CARE_ITEM_FIELD': {
      const { section: updSection, id: updId, field: updField, value: updValue } = action.payload;
      return {
        ...state,
        carePlan: {
          ...state.carePlan,
          [updSection]: (state.carePlan[updSection] || []).map((i) =>
            i.id === updId ? { ...i, [updField]: updValue } : i
          ),
        },
      };
    }
    case 'APPLY_SAFETY_DECISIONS': {
      // Dynamic mutation of carePlan.medications driven by the safety banner's
      // per-flag decisions: { [flagKey]: { decision, drugs?, alternative?, reason? } }
      // Matches by case-insensitive substring on med.name — works for any
      // drug list (no hard-coded mapping) so new drug additions don't need
      // a code change.
      const { decisions } = action.payload || {};
      if (!decisions || !state.carePlan?.medications) return state;

      const meds = { ...state.carePlan.medications };
      const sections = Object.keys(meds);
      const matches = (medName, drugs) => {
        if (!medName || !drugs?.length) return false;
        const low = medName.toLowerCase();
        return drugs.some((d) => d && low.includes(d.toLowerCase()));
      };

      for (const entry of Object.values(decisions)) {
        const { decision, drugs, alternative } = entry || {};
        if (!decision || decision === 'keep') continue;
        if (!drugs?.length) continue;

        for (const section of sections) {
          const list = meds[section] || [];
          if (decision === 'remove') {
            meds[section] = list.filter((m) => !matches(m.name, drugs));
          } else if (decision === 'replace') {
            meds[section] = list.map((m) => {
              if (!matches(m.name, drugs)) return m;
              if (alternative) {
                // Named alternative — swap drug name; dose & instructions are
                // now stale, so wipe them so the clinician must re-confirm.
                return {
                  ...m,
                  name: alternative,
                  dose: '',
                  instructions: m.instructions ? `[REPLACED from ${m.name}] ${m.instructions}` : `Replaced from ${m.name} per safety review`,
                };
              }
              // Generic "Replace" without a named alternative — flag the rec
              // by appending a tag so the clinician can see it needs attention.
              return { ...m, instructions: m.instructions ? `[NEEDS REPLACEMENT — safety flag] ${m.instructions}` : 'Needs replacement — safety flag fired' };
            });
          }
        }
      }

      return { ...state, carePlan: { ...state.carePlan, medications: meds } };
    }
    case 'APPEND_PIPELINE_EVENT':
      return { ...state, pipelineEvents: [...state.pipelineEvents, action.payload] };
    case 'SET_PIPELINE_SUMMARY':
      return { ...state, pipelineSummary: action.payload };
    case 'RESET_PIPELINE':
      return { ...state, pipelineEvents: [], pipelineThinking: {}, pipelineSummary: null, resynthOverride: null, safetyReport: null };
    case 'RESET_PIPELINE_FROM_STAGE': {
      const fromStage = action.payload;
      return {
        ...state,
        pipelineEvents: state.pipelineEvents.filter((e) => (e.stage || 0) < fromStage),
        pipelineSummary: null,
      };
    }
    case 'SET_RESYNTH_OVERRIDE':
      return { ...state, resynthOverride: action.payload };
    case 'SET_DDX_SUGGESTION':
      return { ...state, ddxSuggestion: action.payload };
    case 'SET_DDX_EXCLUDED_CODES':
      return { ...state, ddxExcludedCodes: action.payload || [] };
    case 'SET_REGENERATING_DDX':
      return { ...state, isRegeneratingDdx: !!action.payload };
    case 'SET_DDX_REGEN_EXHAUSTED':
      return { ...state, ddxRegenExhausted: !!action.payload };
    case 'SET_DDX_QUALITY_DROPS':
      return { ...state, ddxQualityDrops: action.payload || [] };
    case 'APPEND_DDX_QUALITY_DROP':
      return { ...state, ddxQualityDrops: [...(state.ddxQualityDrops || []), action.payload] };
    case 'SET_SAFETY_REPORT':
      return { ...state, safetyReport: action.payload };
    case 'SET_EBM_EVIDENCE':
      return { ...state, ebmEvidence: action.payload || [] };
    case 'APPEND_THINKING_CHUNK': {
      const { node, chunk } = action.payload;
      return {
        ...state,
        pipelineThinking: {
          ...state.pipelineThinking,
          [node]: (state.pipelineThinking[node] || '') + chunk,
        },
      };
    }
    case 'RESET':
      return initialState;
    default:
      return state;
  }
}

function updateItemAcceptance(items, id, accepted) {
  if (Array.isArray(items)) {
    return items.map((item) => (item.id === id ? { ...item, accepted } : item));
  }
  return items;
}

export function AppProvider({ children }) {
  const [state, dispatch] = useReducer(appReducer, initialState, loadPersistedState);

  // Mirror current state in a ref so Realtime callbacks (registered once per
  // NRIC/consult) can compare against the latest values without re-subscribing.
  const stateRef = useRef(state);
  useEffect(() => { stateRef.current = state; }, [state]);

  // ──────────────────────────────────────────────────────────────────────────
  // Sync the active consultation with Supabase. Eliminates ghost-patient and
  // stale-field UI by layering:
  //   1. Verify on mount (rehydrated NRIC)
  //   2. Re-verify on tab focus / visibilitychange / network online
  //   3. Periodic poll every 60s while tab is visible (fallback when
  //      Realtime is disabled on the table)
  //   4. Realtime: patients UPDATE → refresh slice; patients DELETE → RESET
  //   5. Realtime: consultations DELETE for the active row → clear consult id
  //
  // Reset-on-not-found only fires for definitive lookups (no RPC error), so
  // transient network failures never wipe an in-progress consult.
  // ──────────────────────────────────────────────────────────────────────────
  const currentNric = state.patient?.nsn || '';
  const currentConsultationId = state.currentConsultationId || null;

  useEffect(() => {
    if (!USE_SUPABASE || !currentNric) return;

    let cancelled = false;
    let pollTimer = null;

    const refreshPatient = async () => {
      try {
        const { found, patient, error } = await searchPatientByNRIC(currentNric);
        if (cancelled || error) return;
        if (!found) {
          // Only treat not-found as a deletion when this NRIC was previously
          // loaded from the DB (mpisSyncedAt is set only by searchPatientByNRIC).
          // Otherwise this is a New Patient flow — the clinician is typing a
          // brand-new NRIC and we must NOT wipe the form fields they're filling.
          if (stateRef.current.patient?.mpisSyncedAt) {
            clearPersistedState();
            dispatch({ type: 'RESET' });
          }
          return;
        }
        // Patient still exists — refresh slice in case fields changed
        // (name, allergies, meds, risk level, vitals history, …).
        dispatch({ type: 'SET_PATIENT', payload: patient });
        dispatch({
          type: 'SET_MPIS_DATA',
          payload: {
            race: patient.race,
            allergies: patient.allergies,
            comorbidities: patient.comorbidities,
            currentMeds: patient.currentMeds,
            vitalsHistory: patient.vitalsHistory,
          },
        });
      } catch {
        // best-effort
      }
    };

    refreshPatient();

    const onVisible = () => {
      if (document.visibilityState === 'visible') refreshPatient();
    };
    document.addEventListener('visibilitychange', onVisible);
    window.addEventListener('focus', refreshPatient);
    window.addEventListener('online', refreshPatient);

    // Poll fallback: every 60s while the tab is visible. Cheap RPC, and the
    // only thing that catches deletes when Realtime is disabled and the user
    // never blurs the tab.
    pollTimer = setInterval(() => {
      if (document.visibilityState === 'visible') refreshPatient();
    }, 60_000);

    // Realtime channel — single subscription per active NRIC + consult id.
    // If Realtime is off in the dashboard, .subscribe() is a no-op and the
    // verify/poll layers above still cover correctness (just not instant).
    const channelName = `consult-watch-${currentNric}-${currentConsultationId || 'none'}`;
    const channel = supabase
      .channel(channelName)
      .on(
        'postgres_changes',
        { event: 'UPDATE', schema: 'public', table: 'patients', filter: `nric=eq.${currentNric}` },
        () => { refreshPatient(); }
      )
      .on(
        'postgres_changes',
        { event: 'DELETE', schema: 'public', table: 'patients', filter: `nric=eq.${currentNric}` },
        () => {
          if (!stateRef.current.patient?.mpisSyncedAt) return; // new-patient flow — ignore
          clearPersistedState();
          dispatch({ type: 'RESET' });
        }
      );

    // INSERT on consultations for this patient. If we have no active consult
    // yet (e.g. another doctor / tab opened one for the same NRIC), adopt its
    // id and pull in clinical_notes / next_review. Don't touch diagnosis or
    // carePlan — those are derived from a fresh pipeline run, not persisted.
    channel.on(
      'postgres_changes',
      { event: 'INSERT', schema: 'public', table: 'consultations', filter: `patient_nric=eq.${currentNric}` },
      (payload) => {
        const row = payload?.new;
        if (!row?.id) return;
        if (stateRef.current.currentConsultationId) return; // user already has one
        dispatch({ type: 'SET_CONSULTATION_ID', payload: row.id });
        if (row.clinical_notes && row.clinical_notes !== stateRef.current.clinicalNotes) {
          dispatch({ type: 'SET_CLINICAL_NOTES', payload: row.clinical_notes });
        }
        if (row.next_review && row.next_review !== stateRef.current.nextReviewDate) {
          dispatch({ type: 'SET_NEXT_REVIEW_DATE', payload: row.next_review });
        }
      }
    );

    if (currentConsultationId) {
      channel
        .on(
          'postgres_changes',
          { event: 'UPDATE', schema: 'public', table: 'consultations', filter: `id=eq.${currentConsultationId}` },
          (payload) => {
            const row = payload?.new;
            if (!row) return;
            // Echo suppression: skip fields that already match local state, so
            // our own writes looping back don't clobber in-flight user edits.
            const nextNotes = row.clinical_notes ?? '';
            if (nextNotes !== (stateRef.current.clinicalNotes ?? '')) {
              dispatch({ type: 'SET_CLINICAL_NOTES', payload: nextNotes });
            }
            const nextReview = row.next_review ?? '';
            if (nextReview !== (stateRef.current.nextReviewDate ?? '')) {
              dispatch({ type: 'SET_NEXT_REVIEW_DATE', payload: nextReview });
            }
            // diagnoses/care_plan JSONB columns are write-only snapshots of the
            // last pipeline run; rehydrating them into the rich UI state would
            // require remapping that loses information, so we leave the local
            // pipeline-derived state authoritative.
          }
        )
        .on(
          'postgres_changes',
          { event: 'DELETE', schema: 'public', table: 'consultations', filter: `id=eq.${currentConsultationId}` },
          () => {
            // Patient still valid; only the consultation row is gone.
            // Drop the id so subsequent updateConsultation() calls don't write
            // to a tombstone, and clear downstream artefacts tied to it.
            dispatch({ type: 'SET_CONSULTATION_ID', payload: null });
            dispatch({ type: 'SET_DIAGNOSIS', payload: null });
            dispatch({ type: 'SET_CARE_PLAN', payload: null });
            dispatch({ type: 'RESET_PIPELINE' });
          }
        );
    }

    channel.subscribe();

    return () => {
      cancelled = true;
      if (pollTimer) clearInterval(pollTimer);
      document.removeEventListener('visibilitychange', onVisible);
      window.removeEventListener('focus', refreshPatient);
      window.removeEventListener('online', refreshPatient);
      supabase.removeChannel(channel);
    };
  }, [currentNric, currentConsultationId]);

  const loadDemoData = () => {
    dispatch({ type: 'LOAD_DEMO_DATA' });
  };

  const syncMPIS = async (nsn) => {
    // Try Supabase first if configured
    if (USE_SUPABASE) {
      console.log('🔍 Searching Supabase for NRIC:', nsn);
      const result = await searchPatientByNRIC(nsn);

      if (result.error) {
        console.warn('Supabase error, falling back to mock data:', result.error);
        // Fall through to mock data
      } else if (result.found) {
        console.log('✅ Patient found in Supabase:', result.patient.name);
        const patient = result.patient;
        dispatch({ type: 'SET_PATIENT', payload: patient });
        dispatch({
          type: 'SET_MPIS_DATA', payload: {
            race: patient.race,
            ethnicity: patient.ethnicity,
            allergies: patient.allergies,
            comorbidities: patient.comorbidities,
            currentMeds: patient.currentMeds,
            vitalsHistory: patient.vitalsHistory,
          }
        });
        // Fetch the latest prior-visit summary (best-effort; never block patient load).
        try {
          const { summary, visitMeta } = await getLatestPriorVisitSummary(nsn);
          if (summary) {
            console.log('📜 Loaded prior visit summary:', summary);
            dispatch({ type: 'SET_PRIOR_VISIT', payload: { summary, meta: visitMeta } });
          } else {
            dispatch({ type: 'SET_PRIOR_VISIT', payload: { summary: null, meta: null } });
          }
        } catch (e) {
          console.warn('prior visit summary load failed (non-fatal):', e);
        }
        return { found: true, patient: patient, mpisData: patient };
      } else {
        console.log('❌ Patient not found in Supabase');
        dispatch({ type: 'SET_PATIENT', payload: { nsn: nsn } });
        return { found: false, nsn: nsn };
      }
    }

    // Patient not found in Supabase - return not found
    console.log('❌ Patient not found in database for NRIC:', nsn);
    dispatch({ type: 'SET_PATIENT', payload: { nsn: nsn } });
    return { found: false };
  };

  const analyzeAssessment = async () => {
    dispatch({ type: 'SET_ANALYZING', payload: true });

    // Keep Supabase consultation creation (audit trail)
    if (USE_SUPABASE && state.patient.nsn) {
      try {
        // Embed severity/staging into clinical_notes (no dedicated column in consultations)
        const staging = state.severityStaging || {};
        const stagingKeys = Object.keys(staging).filter(k => staging[k] !== '' && staging[k] != null);
        const stagingBlock = stagingKeys.length > 0
          ? `[Severity/Staging]\n${stagingKeys.map(k => `- ${k}: ${staging[k]}`).join('\n')}\n\n`
          : '';
        const notesToSave = stagingBlock + (state.clinicalNotes || '');

        console.log('🆕 Starting new consultation for patient:', state.patient.nsn);
        const result = await startConsultation(state.patient.nsn, notesToSave);
        if (result.success && result.consultationId) {
          console.log('✅ New consultation created with ID:', result.consultationId, 'number:', result.consultationNumber);
          dispatch({ type: 'SET_CONSULTATION_ID', payload: result.consultationId });
          if (result.consultationNumber != null) {
            dispatch({ type: 'SET_CONSULTATION_NUMBER', payload: result.consultationNumber });
          }
          // Persist the Step-1 vitals snapshot to live_vitals NOW that the
          // consultation exists — links the row to consultations/patients via a
          // non-null consultation_id. Covers both manual entry and rPPG capture.
          try {
            await saveLiveVitals({
              nric:           state.patient.nsn,
              consultationId: result.consultationId,
              vitals:         state.vitals,
              source:         state.vitalsSource || 'manual',
              quality:        state.vitalsQuality,
            });
          } catch (vErr) {
            console.warn('live_vitals save failed (non-fatal):', vErr);
          }
          // Persist severity/staging to its dedicated column on the consultation.
          try {
            await saveConsultationSeverity(result.consultationId, staging);
          } catch (sErr) {
            console.warn('consultation severity save failed (non-fatal):', sErr);
          }
        } else {
          console.warn('⚠️ Failed to start consultation:', result.error);
        }
      } catch (err) {
        console.warn('Consultation DB save failed (non-fatal):', err);
      }
    }

    try {
      dispatch({ type: 'RESET_PIPELINE' });
      // Fresh consultation DDx → clear any accumulated regeneration exclusions.
      dispatch({ type: 'SET_DDX_EXCLUDED_CODES', payload: [] });
      dispatch({ type: 'SET_DDX_REGEN_EXHAUSTED', payload: false });

      // Stop-and-confirm phase 1: run ONLY Stage 2 (DDx) and pause.
      // The care plan (Stages 3–5) is NOT generated until the clinician confirms
      // a diagnosis in confirmDiagnosis() — so the authoritative plan is never
      // produced against an unvalidated diagnosis.
      const { ddx, request_id } = await runDDxStream(
        { ...state.patient, priorVisit: state.priorVisit },
        state.vitals,
        state.clinicalNotes,
        state.mpisData,
        (stageUpdate) => {
          dispatch({ type: 'APPEND_PIPELINE_EVENT', payload: { ...stageUpdate, eventType: 'stage_update' } });
        },
        (thinkingDelta) => {
          dispatch({
            type: 'APPEND_THINKING_CHUNK',
            payload: { node: thinkingDelta.node, chunk: thinkingDelta.chunk },
          });
        },
        (subStep) => {
          dispatch({ type: 'APPEND_PIPELINE_EVENT', payload: { ...subStep, eventType: 'sub_step' } });
        },
        state.severityStaging || {},
        undefined, // structuredComorbidities — not used in this call path
        (ddxSuggestion) => {
          // Capture the Major/Minor scaffolding so the DDxSelectionPanel can render
          // hint badges (system-suggested Major / co-primary) without re-deriving them.
          dispatch({ type: 'SET_DDX_SUGGESTION', payload: ddxSuggestion });
        },
      );

      const diagnosis = mapDdxToDiagnosis(ddx, []); // no CPGs yet — routing runs on confirm

      dispatch({
        type: 'SET_PIPELINE_SUMMARY',
        payload: {
          elapsed_ms: null,
          ddxCount: ddx?.length || 0,
          cpgCount: 0,
          chunkCount: null,
        },
      });
      // Stash DDx-only response so confirmDiagnosis can read the AI top picks.
      dispatch({ type: 'SET_CLINICAL_PLAN_RESPONSE', payload: { ddx, cpgs_matched: [], treatment_plan: null, request_id: request_id || null } });
      dispatch({ type: 'SET_DIAGNOSIS', payload: diagnosis });
      // Care plan intentionally left unset until confirmation.
      dispatch({ type: 'SET_ANALYZING', payload: false });
      dispatch({ type: 'SET_STEP', payload: 2 });
      return diagnosis;

    } catch (err) {
      console.error('Streaming failed, falling back to non-streaming:', err);
      try {
        const response = await runClinicalPlan(
          { ...state.patient, priorVisit: state.priorVisit }, state.vitals, state.clinicalNotes, state.mpisData,
          state.severityStaging || {},
        );
        const diagnosis = mapDdxToDiagnosis(response.ddx, response.cpgs_matched);
        const carePlan  = mapTreatmentPlanToCarePlan(response.treatment_plan, response.evidence);
        dispatch({ type: 'SET_CLINICAL_PLAN_RESPONSE', payload: response });
        dispatch({ type: 'SET_DIAGNOSIS', payload: diagnosis });
        dispatch({ type: 'SET_CARE_PLAN', payload: carePlan });
        dispatch({ type: 'SET_ANALYZING', payload: false });
        dispatch({ type: 'SET_STEP', payload: 2 });
        return diagnosis;
      } catch (fallbackErr) {
        console.error('Fallback also failed:', fallbackErr);
        dispatch({ type: 'SET_DIAGNOSIS', payload: sampleDiagnosis });
        dispatch({ type: 'SET_ANALYZING', payload: false });
        dispatch({ type: 'SET_STEP', payload: 2 });
        throw fallbackErr;
      }
    }
  };

  // Step-2 "Regenerate differentials": re-run ONLY Stage 2 with the previously
  // shown top-5 (accumulated across presses) excluded from the candidate pool, and
  // optional clinician free-text guidance steering retrieval + the rerank. Stays on
  // Step 2; never touches Stages 3–6 (those run later on Confirm).
  const regenerateDDx = async ({ feedback = '' } = {}) => {
    // Accumulate: union of every code seen so far + the current top-5.
    const currentTop = (state.diagnosis?.differentials || [])
      .slice(0, 5)
      .map((d) => d.icdCode)
      .filter(Boolean);
    const excludeCodes = Array.from(new Set([...(state.ddxExcludedCodes || []), ...currentTop]));

    dispatch({ type: 'SET_DDX_EXCLUDED_CODES', payload: excludeCodes });
    dispatch({ type: 'SET_DDX_REGEN_EXHAUSTED', payload: false });
    dispatch({ type: 'SET_REGENERATING_DDX', payload: true });
    // Clear the stale Stage-2 trace so the panel reflects this fresh run.
    dispatch({ type: 'RESET_PIPELINE_FROM_STAGE', payload: 2 });

    try {
      const { ddx, request_id } = await runDDxStream(
        { ...state.patient, priorVisit: state.priorVisit },
        state.vitals,
        state.clinicalNotes,
        state.mpisData,
        (stageUpdate) => dispatch({ type: 'APPEND_PIPELINE_EVENT', payload: { ...stageUpdate, eventType: 'stage_update' } }),
        (thinkingDelta) => dispatch({ type: 'APPEND_THINKING_CHUNK', payload: { node: thinkingDelta.node, chunk: thinkingDelta.chunk } }),
        (subStep) => dispatch({ type: 'APPEND_PIPELINE_EVENT', payload: { ...subStep, eventType: 'sub_step' } }),
        state.severityStaging || {},
        undefined,
        (ddxSuggestion) => dispatch({ type: 'SET_DDX_SUGGESTION', payload: ddxSuggestion }),
        { excludeCodes, regenFeedback: feedback?.trim() || undefined },
      );

      if (ddx && ddx.length > 0) {
        const diagnosis = mapDdxToDiagnosis(ddx, []); // routing still runs on Confirm
        dispatch({ type: 'SET_CLINICAL_PLAN_RESPONSE', payload: { ddx, cpgs_matched: [], treatment_plan: null, request_id: request_id || null } });
        dispatch({ type: 'SET_DIAGNOSIS', payload: diagnosis });
        dispatch({
          type: 'SET_PIPELINE_SUMMARY',
          payload: { elapsed_ms: null, ddxCount: ddx.length, cpgCount: 0, chunkCount: null },
        });
      } else {
        // Pool exhausted — keep the prior list and tell the clinician.
        dispatch({ type: 'SET_DDX_REGEN_EXHAUSTED', payload: true });
      }
      return ddx;
    } catch (err) {
      console.error('DDx regeneration failed:', err);
      throw err;
    } finally {
      dispatch({ type: 'SET_REGENERATING_DDX', payload: false });
    }
  };

  const confirmDiagnosis = async (options = {}) => {
    dispatch({ type: 'SET_GENERATING_PLAN', payload: true });

    // Get selected diagnoses. Override path: when the DDxSelectionPanel posts
    // {selected_codes, major_code}, prefer those over the legacy multi-select.
    const overrideCodes = Array.isArray(options.selectedCodes) ? options.selectedCodes : null;
    // Manual path: the clinician typed a diagnosis the AI never surfaced, so it
    // isn't in state.diagnosis.differentials. These come through verbatim and the
    // backend resolves each to an ICD-11 code (manual:true) before CPG routing.
    const manualDiagnoses = Array.isArray(options.manualDiagnoses) && options.manualDiagnoses.length
      ? options.manualDiagnoses
      : null;
    let overrideMajor = options.majorCode || (manualDiagnoses ? manualDiagnoses[0]?.icdCode : null) || null;

    let selectedDiagnoses;
    if (manualDiagnoses) {
      selectedDiagnoses = manualDiagnoses;
    } else if (overrideCodes && overrideCodes.length) {
      const codeSet = new Set(overrideCodes);
      selectedDiagnoses = (state.diagnosis?.differentials || []).filter((d) => codeSet.has(d.icdCode));
      // Order Major first so downstream (Stage 5 framing) treats it as primary.
      if (overrideMajor) {
        selectedDiagnoses.sort((a, b) =>
          (a.icdCode === overrideMajor ? -1 : 0) - (b.icdCode === overrideMajor ? -1 : 0)
        );
      }
    } else {
      const selectedIds = state.diagnosis?.selectedDiagnosisIds?.length > 0
        ? state.diagnosis.selectedDiagnosisIds
        : [state.diagnosis?.differentials?.[0]?.id].filter(Boolean);
      selectedDiagnoses = state.diagnosis?.differentials?.filter(
        (d) => selectedIds.includes(d.id)
      ) || [];
    }
    // Tag each diagnosis with its tier so resynthesize sends both `tier` and `major_code`.
    if (overrideMajor) {
      selectedDiagnoses = selectedDiagnoses.map((d) => ({
        ...d,
        tier: d.icdCode === overrideMajor ? 'major' : 'minor',
      }));
    }

    // Guard: the Confirm button only checks that a Major is set, not that the
    // chosen code maps to a live differential. On state desync the filter above
    // can resolve to []. Sending an empty selection makes the backend route
    // nothing and return a silent out_of_scope/degraded plan — fail loudly here
    // instead so the clinician re-picks rather than getting an empty care plan.
    if (!selectedDiagnoses || selectedDiagnoses.length === 0) {
      dispatch({ type: 'SET_GENERATING_PLAN', payload: false });
      throw new Error('No diagnosis selected — pick at least one diagnosis (and set a primary) before generating the care plan.');
    }

    // Save to database - include diagnoses and TCA date
    if (USE_SUPABASE && state.currentConsultationId) {
      try {
        // Use nextReviewDate from the Review & Approve section (user-selected TCA)
        // If not set, no follow-up is scheduled (null)
        let nextReviewStr = state.nextReviewDate || null;

        // Format diagnoses for storage with current timestamp (UTC+08:00)
        const now = getNowUTC8();
        const diagnosesForDB = selectedDiagnoses.map(d => ({
          id: d.id,
          name: d.name,
          icdCode: d.icdCode,
          probability: d.probability,
          risk: d.risk,
          recordedAt: now
        }));

        // Update the consultation with diagnoses using consultation ID
        const result = await updateConsultation(state.currentConsultationId, {
          nextReview: nextReviewStr,
          diagnoses: diagnosesForDB
        });

        if (result.success) {
          console.log('✅ Diagnoses saved to consultation:', state.currentConsultationId, diagnosesForDB);
        } else {
          console.warn('⚠️ Failed to save diagnoses:', result.error);
        }

        // Calculate highest risk level from selected diagnoses
        // Risk priority: critical > high > moderate > low
        const riskPriority = { critical: 4, high: 3, moderate: 2, medium: 2, low: 1 };
        let highestRisk = 'low';
        let highestPriority = 0;

        selectedDiagnoses.forEach(d => {
          const risk = (d.risk || 'low').toLowerCase();
          const priority = riskPriority[risk] || 1;
          if (priority > highestPriority) {
            highestPriority = priority;
            highestRisk = risk === 'medium' ? 'moderate' : risk; // Normalize 'medium' to 'moderate'
          }
        });

        console.log('🎯 Highest risk from diagnoses:', highestRisk, 'from', selectedDiagnoses.map(d => d.risk));

        // Update patient's risk level in database
        const riskResult = await updatePatientRiskLevel(state.patient.nsn, highestRisk);
        if (riskResult.success) {
          console.log('✅ Patient risk level updated to:', highestRisk);
        } else {
          console.warn('⚠️ Failed to update risk level:', riskResult.error);
        }
      } catch (err) {
        console.error('Error saving diagnoses to DB:', err);
      }
    }

    // ── Stop-and-confirm phase 2: synthesize the care plan ────────────────────
    // Phase 1 produced only DDx; the care plan (Stages 3–5) is generated HERE,
    // against the clinician-confirmed diagnosis. This always runs — whether the
    // clinician accepted the AI top pick or overrode it. If the selection differs
    // from the AI's top-2, flag it as an override for the trace.
    const aiTopCodes = new Set(
      (state.clinicalPlanResponse?.ddx || []).slice(0, 2).map((d) => d.code)
    );
    const isOverride = selectedDiagnoses.some((d) => !aiTopCodes.has(d.icdCode));
    console.log(
      isOverride
        ? '🔄 Clinician override — synthesizing plan for:'
        : '✅ Clinician confirmed AI diagnosis — synthesizing plan for:',
      selectedDiagnoses.map((d) => d.icdCode),
    );
    dispatch({ type: 'RESET_PIPELINE_FROM_STAGE', payload: 3 });
    let planGenerated = false;

    try {
      // Reset quality-drop accumulator each time a fresh routing pass starts.
      dispatch({ type: 'SET_DDX_QUALITY_DROPS', payload: [] });
      const response = await resynthesizePlanStream(
        { ...state.patient, priorVisit: state.priorVisit }, state.vitals, state.clinicalNotes, state.mpisData,
        selectedDiagnoses,
        (stageUpdate)  => dispatch({ type: 'APPEND_PIPELINE_EVENT', payload: { ...stageUpdate, eventType: 'stage_update' } }),
        (subStep)      => dispatch({ type: 'APPEND_PIPELINE_EVENT', payload: { ...subStep, eventType: 'sub_step' } }),
        (overrideData) => dispatch({ type: 'SET_RESYNTH_OVERRIDE', payload: overrideData }),
        state.severityStaging || {},
        undefined,
        (safetyReport) => dispatch({ type: 'SET_SAFETY_REPORT', payload: safetyReport }),
        state.currentConsultationId,
        overrideMajor,
        (qualityDropEvent) => {
          // T2.5: capture under-fill events so the care-plan view can surface them.
          const drops = qualityDropEvent?.drops || [];
          drops.forEach((d) => dispatch({ type: 'APPEND_DDX_QUALITY_DROP', payload: d }));
        },
        (p) => dispatch({ type: 'SET_EBM_EVIDENCE', payload: p.evidence }),
      );

      const newCarePlan = mapTreatmentPlanToCarePlan(response.treatment_plan, response.evidence);
      dispatch({ type: 'SET_CARE_PLAN', payload: newCarePlan });
      dispatch({ type: 'SET_CLINICAL_PLAN_RESPONSE', payload: response });
      const mappedDiag = mapDdxToDiagnosis(response.ddx, response.cpgs_matched);
      const previouslySelectedCodes = selectedDiagnoses.map(d => d.icdCode);
      const newSelectedIds = mappedDiag.differentials
        .filter(d => previouslySelectedCodes.includes(d.icdCode))
        .map(d => d.id);
      if (newSelectedIds.length > 0) {
        mappedDiag.selectedDiagnosisIds = newSelectedIds;
      }
      dispatch({ type: 'SET_DIAGNOSIS', payload: mappedDiag });
      dispatch({
        type: 'SET_PIPELINE_SUMMARY',
        payload: { elapsed_ms: response.elapsed_ms, ddxCount: selectedDiagnoses.length, cpgCount: response.cpgs_matched?.length || 0 },
      });
      planGenerated = true;
      console.log('✅ Plan synthesis complete for confirmed diagnosis');
    } catch (err) {
      console.error('Plan synthesis failed:', err);
      dispatch({
        type: 'APPEND_PIPELINE_EVENT',
        payload: {
          stage: 6,
          name: 'Safety Review',
          status: 'error',
          detail: err.message || 'Plan generation stopped before completion',
          eventType: 'stage_update',
        },
      });
      // Re-throw so the caller can show a visible banner — silent failure
      // here leaves the clinician stranded on the diagnosis page wondering
      // why nothing happened.
      dispatch({ type: 'SET_GENERATING_PLAN', payload: false });
      throw err;
    }

    dispatch({ type: 'SET_GENERATING_PLAN', payload: false });
    if (planGenerated) {
      dispatch({ type: 'SET_STEP', payload: 3 });
    }
  };

  // Clinician's diagnosis isn't among the AI's top-5 — route it directly instead
  // of regenerating. The free-text name is sent with manual:true; the backend
  // resolves it to an ICD-11 code (search_ddx) and runs the same Stage 3–5
  // synthesis path as a normal Confirm. Treated as the Major diagnosis.
  const confirmManualDiagnosis = async ({ name } = {}) => {
    const trimmed = (name || '').trim();
    if (!trimmed) {
      throw new Error('Enter a diagnosis name before routing.');
    }
    const manualDiagnosis = {
      id: `manual-${Date.now()}`,
      name: trimmed,
      icdCode: '',          // resolved server-side
      probability: 90,
      reasoning: ['Clinician-entered diagnosis (not in AI top-5)'],
      tier: 'major',
      manual: true,
    };
    await confirmDiagnosis({ manualDiagnoses: [manualDiagnosis] });
  };

  const finalizePlan = async ({ safetyOverride = null } = {}) => {
    // Sync medications from care plan to database
    console.log('🔄 Finalizing plan, current state:', {
      patientNric: state.patient.nsn,
      carePlan: state.carePlan,
      medications: state.carePlan?.medications
    });

    if (USE_SUPABASE && state.patient.nsn && state.carePlan?.medications) {
      try {
        console.log('💊 Triggering medication sync to DB...');
        const result = await updatePatientMedications(
          state.patient.nsn,
          state.carePlan.medications
        );
        if (result.success) {
          console.log('✅ Medications synced to database successfully:', result.medications);
        } else {
          console.error('❌ Failed to sync medications:', result.error);
        }
      } catch (err) {
        console.error('💥 Exception during medication sync:', err);
      }
    } else {
      console.warn('⚠️ Skipping medication sync:', {
        useSupabase: USE_SUPABASE,
        nsn: state.patient.nsn,
        hasMeds: !!state.carePlan?.medications
      });
    }

    // Sync patient status to database
    if (USE_SUPABASE && state.patient.nsn && state.patientStatus) {
      try {
        console.log('📋 Syncing patient status to DB:', state.patientStatus);
        const statusResult = await updatePatientStatus(state.patient.nsn, state.patientStatus);
        if (statusResult.success) {
          console.log('✅ Patient status synced:', state.patientStatus);
        } else {
          console.error('❌ Failed to sync status:', statusResult.error);
        }
      } catch (err) {
        console.error('💥 Exception during status sync:', err);
      }
    }

    // Sync all Care Plan data to consultation using consultation ID
    if (USE_SUPABASE && state.currentConsultationId) {
      try {
        const carePlanSummary = state.carePlan?.clinicalSummary || state.carePlan?.summary || null;
        const medicationRecommendations = state.carePlan?.medications || null;
        const interventions = state.carePlan?.interventions || null;
        const monitoring = state.carePlan?.monitoring || null;
        const referrals = state.carePlan?.referrals || null;
        const lifestyleGoals = state.carePlan?.lifestyle || null;
        const cpgReferences = state.carePlan?.cpgReferences || null;
        const guidanceSelectedIds = state.diagnosis?.selectedDiagnosisIds?.length
          ? state.diagnosis.selectedDiagnosisIds
          : [state.diagnosis?.differentials?.[0]?.id].filter(Boolean);
        const guidanceDiagnoses = (state.diagnosis?.differentials || [])
          .filter((d) => guidanceSelectedIds.includes(d.id));
        const guidanceComparison = getCuratedInternationalGuidance(guidanceDiagnoses);
        const internationalGuidanceAudit = {
          checked: Boolean(state.internationalGuidanceCheckEnabled),
          decision: state.internationalGuidanceDecision || 'local',
          rationale: state.internationalGuidanceRationale?.trim() || null,
          recorded_at: new Date().toISOString(),
          selected_diagnoses: guidanceDiagnoses.map((d) => ({ name: d.name, icd_code: d.icdCode })),
          comparison_status: state.internationalGuidanceCheckEnabled ? guidanceComparison.status : 'not_requested',
          comparison: guidanceComparison.status === 'available' ? {
            condition: guidanceComparison.record.condition,
            reviewed_on: guidanceComparison.record.reviewedOn,
            local: guidanceComparison.record.local,
            international: guidanceComparison.record.international,
          } : null,
        };
        const safetyFlags = state.safetyReport?.flags?.length
          ? state.safetyReport.flags.map(f => ({
              severity: f.severity,
              title: f.title,
              detail: f.detail,
              flag_type: f.flag_type,
              source: f.source,
            }))
          : null;

        console.log('📅 Syncing Care Plan data to consultation:', state.currentConsultationId, 'TCA:', state.nextReviewDate);
        const tcaResult = await updateConsultation(state.currentConsultationId, {
          nextReview: state.nextReviewDate || null, // TCA date from Step 3
          carePlanSummary,
          medicationRecommendations,
          interventions,
          monitoring,
          referrals,
          lifestyleGoals,
          cpgReferences,
          internationalGuidanceAudit,
          safetyFlags,
          // Stage-6 verdict + override audit trail. acknowledgement is only
          // meaningful when the critic blocked the plan (safe_to_proceed=false).
          safeToProceed: typeof state.safetyReport?.safe_to_proceed === 'boolean'
            ? state.safetyReport.safe_to_proceed
            : null,
          safetyAcknowledged: safetyOverride ? safetyOverride.acknowledged : null,
          safetyAcknowledgedBy: safetyOverride?.acknowledged ? safetyOverride.by : null,
          safetyAcknowledgedAt: safetyOverride?.acknowledged ? safetyOverride.at : null
        });

        if (tcaResult.success) {
          console.log('✅ Care Plan data synced to consultation:', state.currentConsultationId);
        } else {
          console.error('❌ Failed to sync:', tcaResult.error);
        }
      } catch (err) {
        console.error('💥 Exception during sync:', err);
      }
    }

    // NOTE: PDF upload is now deferred to Step 4 (OutputSection).
    // The DOM-captured PDF from generatePdfFromElement() is uploaded via
    // uploadFinalCarePlanPDF() to ensure Supabase stores the exact same
    // PDF the clinician sees and downloads.

    // PRIOR-VISIT SUMMARISER — fires ONLY here, after the clinician has agreed
    // and finalised the care plan. Best-effort: never blocks the step transition.
    if (USE_SUPABASE && state.currentConsultationId && state.currentConsultationNumber != null && state.patient?.nsn) {
      try {
        const carePlanSummary = state.carePlan?.clinicalSummary || state.carePlan?.summary || null;
        const priorIcdPrimary = state.carePlan?.icdPrimary
          || state.clinicalPlanResponse?.treatment_plan?.icd_primary
          || null;
        const medicationRecommendations = state.carePlan?.medications || null;

        console.log('📝 Generating prior-visit summary for next consultation...');
        const summary = await summarisePriorVisit({
          consultationDate: new Date().toISOString().split('T')[0],
          clinicalNotes: state.clinicalNotes || '',
          carePlanSummary,
          priorIcdPrimary,
          medicationRecommendations,
        });
        console.log('✅ Prior-visit summary generated:', summary);

        const writeResult = await writePriorVisitSummary(
          state.patient.nsn,
          state.currentConsultationNumber,
          summary,
        );
        if (writeResult.success) {
          console.log('✅ Prior-visit summary persisted to Supabase');
        } else {
          console.error('❌ Failed to persist prior-visit summary:', writeResult.error);
        }
      } catch (err) {
        console.error('💥 Exception during prior-visit summariser:', err);
      }
    }

    dispatch({ type: 'SET_STEP', payload: 4 });
  };

  /**
   * Upload a pre-generated PDF blob (from DOM capture) to Supabase Storage.
   * Called from OutputSection after the FinalCarePlan `.paper` element is
   * captured via html2canvas → jsPDF.  This ensures the stored PDF is
   * byte-identical to the one the clinician downloads via "Export PDF".
   *
   * @param {Blob} pdfBlob - The PDF blob from generatePdfFromElement()
   * @returns {Promise<{success: boolean, url: string|null}>}
   */
  const uploadFinalCarePlanPDF = async (pdfBlob) => {
    if (!USE_SUPABASE || !state.currentConsultationId || !state.patient?.nsn) {
      console.warn('⚠️ Cannot upload PDF — missing consultation ID or NRIC');
      return { success: false, url: null };
    }
    try {
      console.log('📤 Uploading DOM-captured care plan PDF to Supabase...');
      const { success, url, error: pdfErr } = await uploadCarePlanPDF(
        state.currentConsultationId,
        state.patient.nsn,
        pdfBlob,
      );
      if (success && url) {
        const updateRes = await updateConsultation(state.currentConsultationId, { reportPdfUrl: url });
        if (!updateRes.success) {
          console.warn('⚠️ PDF uploaded, but failed to update consultation row:', updateRes.error);
          return { success: false, url: null };
        }
        console.log('✅ Care plan PDF stored (DOM-captured):', url);
        return { success: true, url };
      } else {
        console.warn('⚠️ PDF upload failed:', pdfErr);
        return { success: false, url: null };
      }
    } catch (err) {
      console.error('💥 Exception uploading care plan PDF:', err);
      return { success: false, url: null };
    }
  };

  const saveVitalsToDB = async () => {
    if (!USE_SUPABASE || !state.patient.nsn) return;

    const newVital = {
      date: new Date().toISOString().split('T')[0],
      bpSystolic: parseInt(state.vitals.bpSystolic),
      bpDiastolic: parseInt(state.vitals.bpDiastolic),
      hr: parseInt(state.vitals.hr),
      temp: parseFloat(state.vitals.temp),
      rr: parseInt(state.vitals.rr),
      spo2: parseInt(state.vitals.spo2),
      weight: parseFloat(state.vitals.weight),
    };

    console.log('💾 Saving vitals to DB:', newVital);
    const result = await savePatientVitals(state.patient.nsn, newVital);

    if (result.success) {
      console.log('✅ Vitals saved successfully, new history:', result.history);
      dispatch({
        type: 'SET_PATIENT',
        payload: { vitalsHistory: result.history }
      });
      return true;
    } else {
      console.error('❌ Failed to save vitals:', result.error);
    }
    return false;
  };

  const goToStep = (step) => {
    dispatch({ type: 'SET_STEP', payload: step });
  };

  const updateCarePlanItem = (section, id, accepted) => {
    dispatch({ type: 'UPDATE_CARE_PLAN_ITEM', payload: { section, id, accepted } });
  };

  const updateMedication = (type, id, accepted) => {
    dispatch({ type: 'UPDATE_MEDICATION', payload: { type, id, accepted } });
  };

  const applySafetyDecisions = (decisions) => {
    dispatch({ type: 'APPLY_SAFETY_DECISIONS', payload: { decisions } });
  };

  const selectDiagnosis = (diagnosisId) => {
    dispatch({ type: 'SELECT_DIAGNOSIS', payload: diagnosisId });
  };

  const resetApp = () => {
    clearPersistedState();
    dispatch({ type: 'RESET' });
  };

  const calculateBMI = () => {
    const { weight, height } = state.vitals;
    if (weight && height) {
      const heightM = height / 100;
      return (weight / (heightM * heightM)).toFixed(1);
    }
    return null;
  };

  const value = useMemo(() => ({
    state,
    dispatch,
    pipelineEvents:   state.pipelineEvents,
    pipelineSummary:  state.pipelineSummary,
    pipelineThinking: state.pipelineThinking,
    resynthOverride:  state.resynthOverride,
    ddxSuggestion:    state.ddxSuggestion,
    ddxQualityDrops:  state.ddxQualityDrops,
    loadDemoData,
    syncMPIS,
    analyzeAssessment,
    regenerateDDx,
    confirmDiagnosis,
    confirmManualDiagnosis,
    finalizePlan,
    uploadFinalCarePlanPDF,
    goToStep,
    updateCarePlanItem,
    updateMedication,
    applySafetyDecisions,
    selectDiagnosis,
    resetApp,
    calculateBMI,
    saveVitalsToDB,
  }), [state]); // eslint-disable-line react-hooks/exhaustive-deps

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp() {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error('useApp must be used within an AppProvider');
  }
  return context;
}
