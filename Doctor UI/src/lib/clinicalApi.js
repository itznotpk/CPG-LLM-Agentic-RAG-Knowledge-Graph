const CLINICAL_API_BASE = import.meta.env.VITE_CLINICAL_API_URL || 'http://localhost:8058';

// ─── shared helper ────────────────────────────────────────────────────────────
function buildClinicalPlanBody(patientState, vitals, clinicalNotes, mpisData, stagingData, structuredComorbidities, consultationId) {
  return {
    ...(consultationId != null ? { consultation_id: consultationId } : {}),
    case: {
      chief_complaint: clinicalNotes || patientState.chiefComplaint || '',
      history: patientState.history || null,
      age: patientState.age || null,
      sex: patientState.gender === 'Male' ? 'M'
         : patientState.gender === 'Female' ? 'F'
         : patientState.gender ? 'other' : null,
      comorbidities: mpisData?.comorbidities || [],
      current_medications: (mpisData?.currentMeds || []).map(
        (m) => (typeof m === 'string' ? m : m.name || m.medication || '')
      ).filter(Boolean),
      allergies: mpisData?.allergies
        ? (typeof mpisData.allergies === 'string'
            ? mpisData.allergies.split(',').map((a) => a.trim()).filter(Boolean)
            : mpisData.allergies)
        : [],
      vitals: vitals ? {
        ...(vitals.bpSystolic  ? { sbp: Number(vitals.bpSystolic) }  : {}),
        ...(vitals.bpDiastolic ? { dbp: Number(vitals.bpDiastolic) } : {}),
        ...(vitals.hr          ? { hr:  Number(vitals.hr) }           : {}),
        ...(vitals.temp        ? { temp: Number(vitals.temp) }         : {}),
        ...(vitals.rr          ? { rr:  Number(vitals.rr) }           : {}),
        ...(vitals.spo2        ? { spo2: Number(vitals.spo2) }         : {}),
        ...(vitals.weight      ? { weight: Number(vitals.weight) }     : {}),
        ...(vitals.height      ? { height: Number(vitals.height) }     : {}),
        ...(vitals.weight && vitals.height
            ? { bmi: +(Number(vitals.weight) / ((Number(vitals.height) / 100) ** 2)).toFixed(1) }
            : {}),
      } : {},
      severity_staging: stagingData || {},
      ...(structuredComorbidities?.length ? { staged_comorbidities: structuredComorbidities } : {}),
      ...(patientState?.priorVisit ? { prior_visit: patientState.priorVisit } : {}),
    },
  };
}

/**
 * Generate the lean PriorVisitSummary JSON for a just-finalised consultation.
 * Called ONLY after the clinician explicitly agrees on the final care plan.
 * Caller is responsible for writing the returned JSON back into Supabase via
 * update_prior_visit_summary_bypass().
 *
 * @returns {Promise<Object>} { visit_date, prior_icd_primary, prior_plan_summary, key_labs_delta, what_changed }
 */
export async function summarisePriorVisit({
  consultationDate,
  clinicalNotes,
  carePlanSummary,
  priorIcdPrimary,
  medicationRecommendations,
}) {
  const resp = await fetch(`${CLINICAL_API_BASE}/clinical/summarise-prior`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      consultation_date: consultationDate,
      clinical_notes: clinicalNotes || '',
      care_plan_summary: carePlanSummary || null,
      prior_icd_primary: priorIcdPrimary || null,
      medication_recommendations: medicationRecommendations || null,
    }),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(err.detail || 'summarise-prior request failed');
  }
  return resp.json();
}

/**
 * Run the full clinical pipeline for a patient case.
 * Maps Doctor UI state → PatientCase → POST /clinical/plan → response.
 */
export async function runClinicalPlan(patientState, vitals, clinicalNotes, mpisData, stagingData, structuredComorbidities) {
  const body = buildClinicalPlanBody(patientState, vitals, clinicalNotes, mpisData, stagingData, structuredComorbidities);

  const resp = await fetch(`${CLINICAL_API_BASE}/clinical/plan`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(err.detail || 'Clinical plan request failed');
  }

  return resp.json();   // ClinicalPlanResponse shape
}

// ─── stop-and-confirm phase 1: DDx only ───────────────────────────────────────
/**
 * Run ONLY Stage 2 (DDx) and stream it, then stop for clinician confirmation.
 *
 * Resolves with the candidate list (from the terminal `ddx_ready` event). The UI
 * then renders the confirm/override gate and calls resynthesizePlanStream to run
 * Stages 3–5 on the agreed diagnosis.
 *
 * @returns {Promise<{ddx: Array}>}  resolves with the DDx candidates
 */
export async function runDDxStream(
  patientState,
  vitals,
  clinicalNotes,
  mpisData,
  onStageUpdate,
  onThinkingChunk,
  onSubStep,
  stagingData,
  structuredComorbidities,
) {
  const body = buildClinicalPlanBody(patientState, vitals, clinicalNotes, mpisData, stagingData, structuredComorbidities);

  const response = await fetch(`${CLINICAL_API_BASE}/clinical/plan/ddx/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`DDx stream API error ${response.status}: ${text}`);
  }

  return new Promise((resolve, reject) => {
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let ddxResult = null;

    const pump = async () => {
      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) {
            // Stream closed: resolve with whatever we captured (or empty).
            resolve(ddxResult || { ddx: [] });
            return;
          }
          buffer += decoder.decode(value, { stream: true });

          const frames = buffer.split('\n\n');
          buffer = frames.pop();

          for (const frame of frames) {
            if (!frame.trim()) continue;
            let eventType = 'message', dataStr = '';
            for (const line of frame.split('\n')) {
              if (line.startsWith('event: ')) eventType = line.slice(7).trim();
              else if (line.startsWith('data: ')) dataStr = line.slice(6).trim();
            }
            if (!dataStr) continue;
            let payload;
            try { payload = JSON.parse(dataStr); } catch { continue; }

            if      (eventType === 'stage_update'   && onStageUpdate)   onStageUpdate(payload);
            else if (eventType === 'thinking_delta' && onThinkingChunk) onThinkingChunk(payload);
            else if (eventType === 'sub_step'       && onSubStep)       onSubStep(payload);
            else if (eventType === 'ddx_ready')                          ddxResult = payload;
            else if (eventType === 'error')                             reject(new Error(payload.detail || 'DDx pipeline error'));
            else if (eventType === 'done')                             { resolve(ddxResult || { ddx: [] }); return; }
          }
        }
      } catch (err) {
        reject(err);
      }
    };

    pump();
  });
}

// ─── streaming variant ────────────────────────────────────────────────────────
/**
 * Run the clinical pipeline and stream SSE stage-update + thinking events.
 *
 * @param {Object}   patientState
 * @param {Object}   vitals
 * @param {string}   clinicalNotes
 * @param {Object}   mpisData
 * @param {Function} onStageUpdate   - called with each stage_update payload
 * @param {Function} onThinkingChunk - called with each thinking_delta payload
 * @returns {Promise<ClinicalPlanResponse>}  resolves with the final_result payload
 */
export async function runClinicalPlanStream(
  patientState,
  vitals,
  clinicalNotes,
  mpisData,
  onStageUpdate,
  onThinkingChunk,
  onSubStep,
  stagingData,
  structuredComorbidities,
  onSafetyReview,
  consultationId,
) {
  const body = buildClinicalPlanBody(patientState, vitals, clinicalNotes, mpisData, stagingData, structuredComorbidities, consultationId);

  const response = await fetch(`${CLINICAL_API_BASE}/clinical/plan/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Clinical stream API error ${response.status}: ${text}`);
  }

  return new Promise((resolve, reject) => {
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    const pump = async () => {
      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) {
            reject(new Error('Stream ended without final_result'));
            return;
          }
          buffer += decoder.decode(value, { stream: true });

          // SSE frames are double-newline separated
          const frames = buffer.split('\n\n');
          buffer = frames.pop(); // keep incomplete trailing frame

          for (const frame of frames) {
            if (!frame.trim()) continue;

            let eventType = 'message';
            let dataStr = '';
            for (const line of frame.split('\n')) {
              if (line.startsWith('event: ')) eventType = line.slice(7).trim();
              else if (line.startsWith('data: ')) dataStr = line.slice(6).trim();
            }
            if (!dataStr) continue;

            let payload;
            try { payload = JSON.parse(dataStr); } catch { continue; }

            if      (eventType === 'stage_update'   && onStageUpdate)    onStageUpdate(payload);
            else if (eventType === 'thinking_delta' && onThinkingChunk)  onThinkingChunk(payload);
            else if (eventType === 'sub_step'       && onSubStep)        onSubStep(payload);
            else if (eventType === 'safety_review'  && onSafetyReview)  onSafetyReview(payload);
            else if (eventType === 'final_result') {
              if (payload?.safety_report && onSafetyReview) onSafetyReview(payload.safety_report);
              resolve(payload);
            }
            else if (eventType === 'error')                               reject(new Error(payload.detail || 'Pipeline error'));
            else if (eventType === 'done')                                return; // resolve already called
          }
        }
      } catch (err) {
        reject(err);
      }
    };

    pump();
  });
}

/**
 * Re-run Stages 3–5 with clinician-confirmed diagnoses.
 *
 * @param {Object}   patientState
 * @param {Object}   vitals
 * @param {string}   clinicalNotes
 * @param {Object}   mpisData
 * @param {Array}    selectedDiagnoses  — [{icdCode, name, probability, reasoning}]
 * @param {Function} onStageUpdate
 * @param {Function} onSubStep
 * @param {Function} onClinicianOverride  — called once with {codes:[]}
 * @returns {Promise<ClinicalPlanResponse>}
 */
export async function resynthesizePlanStream(
  patientState, vitals, clinicalNotes, mpisData,
  selectedDiagnoses,
  onStageUpdate,
  onSubStep,
  onClinicianOverride,
  stagingData,
  structuredComorbidities,
  onSafetyReview,
  consultationId,
) {
  const BASE_URL = import.meta.env.VITE_CLINICAL_API_URL || 'http://localhost:8058';

  const body = {
    ...(consultationId != null ? { consultation_id: consultationId } : {}),
    case: buildClinicalPlanBody(
      patientState, vitals, clinicalNotes, mpisData, stagingData, structuredComorbidities,
    ).case,
    selected_diagnoses: selectedDiagnoses.map((d) => ({
      code:        d.icdCode,
      title:       d.name,
      probability: (d.probability || 80) / 100,
      reasoning:   d.reasoning || [],
    })),
  };

  const response = await fetch(`${BASE_URL}/clinical/plan/resynthesize/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Re-synthesis API error ${response.status}: ${text}`);
  }

  return new Promise((resolve, reject) => {
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    const pump = async () => {
      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) { reject(new Error('Stream ended without final_result')); return; }
          buffer += decoder.decode(value, { stream: true });

          const frames = buffer.split('\n\n');
          buffer = frames.pop();

          for (const frame of frames) {
            if (!frame.trim()) continue;
            let eventType = 'message', dataStr = '';
            for (const line of frame.split('\n')) {
              if (line.startsWith('event: ')) eventType = line.slice(7).trim();
              else if (line.startsWith('data: ')) dataStr = line.slice(6).trim();
            }
            if (!dataStr) continue;
            let payload;
            try { payload = JSON.parse(dataStr); } catch { continue; }

            if      (eventType === 'stage_update'       && onStageUpdate)       onStageUpdate(payload);
            else if (eventType === 'sub_step'           && onSubStep)           onSubStep(payload);
            else if (eventType === 'clinician_override' && onClinicianOverride) onClinicianOverride(payload);
            else if (eventType === 'safety_review'      && onSafetyReview)     onSafetyReview(payload);
            else if (eventType === 'final_result') {
              if (payload?.safety_report && onSafetyReview) onSafetyReview(payload.safety_report);
              resolve(payload);
            }
            else if (eventType === 'error')                                      reject(new Error(payload.detail || 'Re-synthesis error'));
            else if (eventType === 'done')                                       return;
          }
        }
      } catch (err) { reject(err); }
    };
    pump();
  });
}

export async function enqueueDelivery(consultationId, clinicianName = null) {
  const r = await fetch(`${CLINICAL_API_BASE}/delivery/enqueue`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ consultation_id: consultationId, clinician_name: clinicianName }),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function getDeliveryStatus(consultationId) {
  const r = await fetch(`${CLINICAL_API_BASE}/delivery/status/${consultationId}`);
  return r.ok ? r.json() : null;
}

export async function getPrepBrief({ priorVisit, currentMedications, patientAge, patientSex, comorbidities, patientNric }) {
  const r = await fetch(`${CLINICAL_API_BASE}/clinical/prep-brief`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      patient_nric: patientNric,
      prior_visit: priorVisit,
      current_medications: currentMedications || [],
      patient_age: patientAge || null,
      patient_sex: patientSex || null,
      comorbidities: comorbidities || [],
    }),
  });
  if (!r.ok) return null;
  return r.json();
}
