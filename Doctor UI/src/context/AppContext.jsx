import React, { createContext, useContext, useState, useReducer } from 'react';
import {
  sampleDiagnosis,
  sampleCarePlan,
} from '../data/sampleData';
import { runClinicalPlan, runClinicalPlanStream, resynthesizePlanStream } from '../lib/clinicalApi';
import { mapDdxToDiagnosis, mapTreatmentPlanToCarePlan } from '../lib/clinicalMappers';
import {
  searchPatientByNRIC,
  savePatientVitals,
  isSupabaseConfigured,
  startConsultation,
  updateConsultation,
  updatePatientMedications,
  updatePatientRiskLevel,
  updatePatientStatus
} from '../lib/supabase';
import { getNowUTC8, getTodayUTC8 } from '../utils/timezone';

// Always use Supabase for patient data
const USE_SUPABASE = isSupabaseConfigured();

const AppContext = createContext();

const initialState = {
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
  clinicalPlanResponse: null,
  diagnosis: null,
  carePlan: null,
  isAnalyzing: false,
  isGeneratingPlan: false,
  pipelineEvents: [],      // ordered log: [...stage_updates, ...sub_steps]
  pipelineThinking: {},    // { [nodeName: string]: string }  accumulated thinking text
  pipelineSummary: null,   // { elapsed_ms, ddxCount, cpgCount, chunkCount } set on final_result
  resynthOverride: null,   // { codes: string[] } set when clinician override runs
};

function appReducer(state, action) {
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
    case 'SET_VITALS':
      return { ...state, vitals: { ...state.vitals, ...action.payload } };
    case 'SET_SEVERITY_STAGING':
      return { ...state, severityStaging: action.payload };
    case 'SET_MPIS_DATA':
      return { ...state, mpisData: action.payload, mpisSynced: true };
    case 'SET_CLINICAL_PLAN_RESPONSE':
      return { ...state, clinicalPlanResponse: action.payload };
    case 'SET_DIAGNOSIS':
      return { ...state, diagnosis: action.payload };
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
    case 'APPEND_PIPELINE_EVENT':
      return { ...state, pipelineEvents: [...state.pipelineEvents, action.payload] };
    case 'SET_PIPELINE_SUMMARY':
      return { ...state, pipelineSummary: action.payload };
    case 'RESET_PIPELINE':
      return { ...state, pipelineEvents: [], pipelineThinking: {}, pipelineSummary: null, resynthOverride: null };
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
  const [state, dispatch] = useReducer(appReducer, initialState);

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
        console.log('🆕 Starting new consultation for patient:', state.patient.nsn);
        const result = await startConsultation(state.patient.nsn, state.clinicalNotes);
        if (result.success && result.consultationId) {
          console.log('✅ New consultation created with ID:', result.consultationId);
          dispatch({ type: 'SET_CONSULTATION_ID', payload: result.consultationId });
        } else {
          console.warn('⚠️ Failed to start consultation:', result.error);
        }
      } catch (err) {
        console.warn('Consultation DB save failed (non-fatal):', err);
      }
    }

    try {
      dispatch({ type: 'RESET_PIPELINE' });

      const response = await runClinicalPlanStream(
        state.patient,
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
      );

      const diagnosis = mapDdxToDiagnosis(response.ddx, response.cpgs_matched);
      const carePlan  = mapTreatmentPlanToCarePlan(response.treatment_plan);

      if (response.stage_errors?.length > 0) {
        console.warn('Clinical pipeline stage errors:', response.stage_errors);
      }

      dispatch({
        type: 'SET_PIPELINE_SUMMARY',
        payload: {
          elapsed_ms: response.elapsed_ms,
          ddxCount: response.ddx?.length || 0,
          cpgCount: response.cpgs_matched?.length || 0,
          chunkCount: null,
        },
      });
      dispatch({ type: 'SET_CLINICAL_PLAN_RESPONSE', payload: response });
      dispatch({ type: 'SET_DIAGNOSIS', payload: diagnosis });
      dispatch({ type: 'SET_CARE_PLAN', payload: carePlan });
      dispatch({ type: 'SET_ANALYZING', payload: false });
      dispatch({ type: 'SET_STEP', payload: 2 });
      return diagnosis;

    } catch (err) {
      console.error('Streaming failed, falling back to non-streaming:', err);
      try {
        const response = await runClinicalPlan(
          state.patient, state.vitals, state.clinicalNotes, state.mpisData,
          state.severityStaging || {},
        );
        const diagnosis = mapDdxToDiagnosis(response.ddx, response.cpgs_matched);
        const carePlan  = mapTreatmentPlanToCarePlan(response.treatment_plan);
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

  const confirmDiagnosis = async () => {
    dispatch({ type: 'SET_GENERATING_PLAN', payload: true });

    // Get selected diagnoses
    const selectedIds = state.diagnosis?.selectedDiagnosisIds?.length > 0
      ? state.diagnosis.selectedDiagnosisIds
      : [state.diagnosis?.differentials?.[0]?.id].filter(Boolean);
    const selectedDiagnoses = state.diagnosis?.differentials?.filter(
      (d) => selectedIds.includes(d.id)
    ) || [];

    // Save to database - include diagnoses and TCA date
    if (USE_SUPABASE && state.currentConsultationId) {
      try {
        // Use nextReviewDate from step 1 (user-selected TCA), or default to 4 weeks
        let nextReviewStr = state.nextReviewDate;
        if (!nextReviewStr) {
          const nextReview = new Date();
          nextReview.setDate(nextReview.getDate() + 28); // Default 4 weeks follow-up
          nextReviewStr = nextReview.toISOString().split('T')[0];
        }

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

    // ── Re-synthesis logic ──────────────────────────────────────────────────
    // Determine if clinician selected codes different from what the pipeline used.
    // The pipeline routes on the AI's top-2 DDx codes; if the clinician picked
    // anything outside that set, we must re-run Stages 3-5.
    const aiTopCodes = new Set(
      (state.clinicalPlanResponse?.ddx || []).slice(0, 2).map((d) => d.code)
    );
    const needsResynth = selectedDiagnoses.some((d) => !aiTopCodes.has(d.icdCode));

    if (needsResynth) {
      console.log('🔄 Clinician override detected — re-running Stages 3-5 for:', selectedDiagnoses.map(d => d.icdCode));
      dispatch({ type: 'RESET_PIPELINE_FROM_STAGE', payload: 3 });

      try {
        const response = await resynthesizePlanStream(
          state.patient, state.vitals, state.clinicalNotes, state.mpisData,
          selectedDiagnoses,
          (stageUpdate)  => dispatch({ type: 'APPEND_PIPELINE_EVENT', payload: { ...stageUpdate, eventType: 'stage_update' } }),
          (subStep)      => dispatch({ type: 'APPEND_PIPELINE_EVENT', payload: { ...subStep, eventType: 'sub_step' } }),
          (overrideData) => dispatch({ type: 'SET_RESYNTH_OVERRIDE', payload: overrideData }),
          state.severityStaging || {},
        );

        const newCarePlan = mapTreatmentPlanToCarePlan(response.treatment_plan);
        dispatch({ type: 'SET_CARE_PLAN', payload: newCarePlan });
        dispatch({ type: 'SET_CLINICAL_PLAN_RESPONSE', payload: response });
        dispatch({
          type: 'SET_PIPELINE_SUMMARY',
          payload: { elapsed_ms: response.elapsed_ms, ddxCount: selectedDiagnoses.length, cpgCount: response.cpgs_matched?.length || 0 },
        });
        console.log('✅ Re-synthesis complete for clinician-selected diagnosis');
      } catch (err) {
        console.error('Re-synthesis failed — keeping original plan:', err);
        // Non-fatal: keep the original care plan, still advance to Step 3
      }
    }

    dispatch({ type: 'SET_GENERATING_PLAN', payload: false });
    dispatch({ type: 'SET_STEP', payload: 3 });
  };

  const finalizePlan = async () => {
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
        const patientEducation = state.carePlan?.disposition?.patientEducation || null;
        const referrals = state.carePlan?.disposition?.referrals || null;
        const lifestyleGoals = state.carePlan?.lifestyle || null;
        const cpgReferences = state.carePlan?.cpgReferences || null;

        console.log('📅 Syncing Care Plan data to consultation:', state.currentConsultationId, 'TCA:', state.nextReviewDate);
        const tcaResult = await updateConsultation(state.currentConsultationId, {
          nextReview: state.nextReviewDate || null, // TCA date from Step 3
          carePlanSummary,
          medicationRecommendations,
          interventions,
          monitoring,
          patientEducation,
          referrals,
          lifestyleGoals,
          cpgReferences
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

    dispatch({ type: 'SET_STEP', payload: 4 });
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

  const selectDiagnosis = (diagnosisId) => {
    dispatch({ type: 'SELECT_DIAGNOSIS', payload: diagnosisId });
  };

  const resetApp = () => {
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

  const value = {
    state,
    dispatch,
    pipelineEvents:   state.pipelineEvents,
    pipelineSummary:  state.pipelineSummary,
    pipelineThinking: state.pipelineThinking,
    resynthOverride:  state.resynthOverride,
    loadDemoData,
    syncMPIS,
    analyzeAssessment,
    confirmDiagnosis,
    finalizePlan,
    goToStep,
    updateCarePlanItem,
    updateMedication,
    selectDiagnosis,
    resetApp,
    calculateBMI,
    saveVitalsToDB,
  };

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp() {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error('useApp must be used within an AppProvider');
  }
  return context;
}
