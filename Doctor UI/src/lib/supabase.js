/**
 * Supabase Client Configuration
 * ==============================
 * 
 * This file initializes the Supabase client for the MHNexus CPG-LLM application.
 * 
 * Setup Instructions:
 * 1. Create a project at https://app.supabase.com
 * 2. Go to Project Settings → API
 * 3. Copy your Project URL and anon/public key
 * 4. Create a .env file in the project root with:
 *    VITE_SUPABASE_URL=your_project_url
 *    VITE_SUPABASE_ANON_KEY=your_anon_key
 * 5. Restart the Vite dev server
 */

import { createClient } from '@supabase/supabase-js';

// Get environment variables
const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

// Validate configuration
if (!supabaseUrl || !supabaseAnonKey) {
  console.error(
    '⚠️ Supabase configuration missing!\n\n' +
    'Please create a .env file in the project root with:\n' +
    '  VITE_SUPABASE_URL=your_project_url\n' +
    '  VITE_SUPABASE_ANON_KEY=your_anon_key\n\n' +
    'Get these values from: Supabase Dashboard → Project Settings → API'
  );
}

// Create and export the Supabase client
export const supabase = createClient(supabaseUrl || '', supabaseAnonKey || '', {
  auth: {
    // Persist session to localStorage
    persistSession: true,
    // Automatically refresh tokens before expiry
    autoRefreshToken: true,
    // Detect session from URL (for OAuth callbacks)
    detectSessionInUrl: true,
    // Storage key for session
    storageKey: 'mhnexus-auth',
  },
  db: {
    // Use public schema
    schema: 'public',
  },
  global: {
    // Custom headers for all requests
    headers: {
      'x-application-name': 'MHNexus-CPG-LLM',
    },
  },
});

/**
 * Check if Supabase is properly configured
 * @returns {boolean} True if configuration is valid
 */
export const isSupabaseConfigured = () => {
  return Boolean(supabaseUrl && supabaseAnonKey);
};

/**
 * Get current authenticated user
 * @returns {Promise<User|null>} Current user or null
 */
export const getCurrentUser = async () => {
  const { data: { user } } = await supabase.auth.getUser();
  return user;
};

/**
 * Get current session
 * @returns {Promise<Session|null>} Current session or null
 */
export const getCurrentSession = async () => {
  const { data: { session } } = await supabase.auth.getSession();
  return session;
};

/**
 * Sign out the current user
 * @returns {Promise<void>}
 */
export const signOut = async () => {
  const { error } = await supabase.auth.signOut();
  if (error) throw error;
};

/**
 * Subscribe to auth state changes
 * @param {Function} callback - Callback function (event, session)
 * @returns {Function} Unsubscribe function
 */
export const onAuthStateChange = (callback) => {
  const { data: { subscription } } = supabase.auth.onAuthStateChange(callback);
  return () => subscription.unsubscribe();
};

// ==============================================================================
// PATIENT FUNCTIONS (MPIS Integration)
// ==============================================================================

/**
 * Search for a patient by NRIC
 * @param {string} nric - Patient's NRIC (e.g., "580315-08-1234")
 * @returns {Promise<{found: boolean, patient: Object|null, error: Error|null}>}
 */
export const searchPatientByNRIC = async (nric) => {
  try {
    // Call the NEW database function v2
    const { data, error } = await supabase
      .rpc('search_patient_v2', { p_nric: nric });

    if (error) {
      console.error('Error searching patient:', error);
      return { found: false, patient: null, error };
    }

    if (data && data.length > 0) {
      const patient = data[0];
      return {
        found: true,
        patient: {
          id: patient.nric, // Using NRIC as the primary identifier
          nsn: patient.nric,
          name: patient.full_name,
          dob: patient.date_of_birth,
          age: patient.age,
          gender: patient.gender === 'male' ? 'Male' : patient.gender === 'female' ? 'Female' : 'Other',
          race: patient.race,
          allergies: patient.allergies,
          comorbidities: patient.comorbidities || [],
          currentMeds: patient.current_medications || [],
          riskLevel: patient.risk_level,
          mpisSyncedAt: patient.mpis_synced_at,
          vitalsHistory: patient.vitals_history || [],
        },
        error: null
      };
    }

    return { found: false, patient: null, error: null };
  } catch (err) {
    console.error('Exception searching patient:', err);
    return { found: false, patient: null, error: err };
  }
};

/**
 * Register a new patient
 * @param {Object} patientData - Patient data
 * @returns {Promise<{success: boolean, patientId: string|null, error: Error|null}>}
 * Note: patientId is now the NRIC (primary key) instead of UUID
 */
export const registerPatient = async (patientData) => {
  try {
    const { data, error } = await supabase
      .rpc('register_patient', {
        p_nric: patientData.nric,
        p_full_name: patientData.fullName,
        p_date_of_birth: patientData.dateOfBirth,
        p_gender: patientData.gender.toLowerCase(),
        p_race: patientData.race || null,
        p_allergies: patientData.allergies || null,
        p_comorbidities: patientData.comorbidities || null,
        p_created_by: patientData.createdBy || null,
      });

    if (error) {
      console.error('Error registering patient:', error);
      return { success: false, patientId: null, error };
    }

    return { success: true, patientId: data, error: null };
  } catch (err) {
    console.error('Exception registering patient:', err);
    return { success: false, patientId: null, error: err };
  }
};

/**
 * Update patient data from MPIS sync
 * @param {string} nric - Patient's NRIC
 * @param {Object} mpisData - Data from MPIS
 * @returns {Promise<{success: boolean, error: Error|null}>}
 */
export const updatePatientFromMPIS = async (nric, mpisData) => {
  try {
    const { data, error } = await supabase
      .rpc('update_patient_from_mpis', {
        p_nric: nric,
        p_allergies: mpisData.allergies || null,
        p_comorbidities: mpisData.comorbidities || null,
        p_current_medications: mpisData.currentMeds || [],
        p_mpis_data: mpisData || {},
      });

    if (error) {
      console.error('Error updating patient from MPIS:', error);
      return { success: false, error };
    }

    return { success: data, error: null };
  } catch (err) {
    console.error('Exception updating patient from MPIS:', err);
    return { success: false, error: err };
  }
};

/**
 * Save new vital signs reading for a patient
 * @param {string} nric - Patient's NRIC
 * @param {Object} vitals - Vital signs data
 * @returns {Promise<{success: boolean, history: Array|null, error: Error|null}>}
 */
export const savePatientVitals = async (nric, vitals) => {
  try {
    const { data, error } = await supabase
      .rpc('push_patient_vitals', {
        p_nric: nric,
        p_vitals: [vitals] // Pass array directly, Supabase will handle JSONB conversion
      });

    if (error) {
      console.error('Error saving patient vitals:', error);
      return { success: false, history: null, error };
    }

    return { success: true, history: data, error: null };
  } catch (err) {
    console.error('Exception saving patient vitals:', err);
    return { success: false, history: null, error: err };
  }
};

/**
 * Update patient medications from care plan
 * This syncs the care plan medication changes to the patient's current_medications
 * @param {string} nric - Patient's NRIC
 * @param {Object} medications - Care plan medications object with stop, start, change, continue arrays
 * @returns {Promise<{success: boolean, medications: Array|null, error: Error|null}>}
 */
export const updatePatientMedications = async (nric, medications) => {
  try {
    console.log('💊 Updating medications for patient:', nric);
    console.log('📋 Care plan medications:', medications);

    // First, get current medications for this patient
    const { data: patientData, error: fetchError } = await supabase
      .from('patients')
      .select('current_medications')
      .eq('nric', nric)
      .single();

    if (fetchError) {
      console.error('Error fetching patient medications:', fetchError);
    }

    let currentMeds = patientData?.current_medications || [];

    // Safety check: if currentMeds is somehow a string (due to previous corruption), parse it
    if (typeof currentMeds === 'string') {
      try {
        currentMeds = JSON.parse(currentMeds);
      } catch (e) {
        currentMeds = [];
      }
    }

    if (!Array.isArray(currentMeds)) currentMeds = [];

    console.log('📦 Current medications in DB:', currentMeds);

    // Remove STOP medications
    if (medications.stop && medications.stop.length > 0) {
      const stopNames = medications.stop.map(m => (m.name || m.medication || '').toLowerCase());
      console.log('🛑 Stopping medications:', stopNames);
      currentMeds = currentMeds.filter(m => {
        const medName = (m.name || m.medication || '').toLowerCase();
        return medName && !stopNames.includes(medName);
      });
    }

    // Update CHANGE medications (update dose)
    if (medications.change && medications.change.length > 0) {
      console.log('🔄 Changing medications:', medications.change);
      medications.change.forEach(changedMed => {
        const existingIndex = currentMeds.findIndex(m =>
          (m.name || m.medication || '').toLowerCase() === (changedMed.name || changedMed.medication || '').toLowerCase()
        );
        if (existingIndex !== -1) {
          // Update the dose
          currentMeds[existingIndex] = {
            name: changedMed.name || changedMed.medication,
            dose: changedMed.newDose || changedMed.dose,
            frequency: changedMed.frequency || currentMeds[existingIndex].frequency || 'OD'
          };
        } else {
          // Medication not in current list, add it with new dose
          currentMeds.push({
            name: changedMed.name || changedMed.medication,
            dose: changedMed.newDose || changedMed.dose,
            frequency: changedMed.frequency || 'OD'
          });
        }
      });
    }

    // Add START medications (if not already present)
    if (medications.start && medications.start.length > 0) {
      console.log('🟢 Starting medications:', medications.start);
      medications.start.forEach(newMed => {
        const alreadyExists = currentMeds.some(m =>
          (m.name || m.medication || '').toLowerCase() === (newMed.name || newMed.medication || '').toLowerCase()
        );
        if (!alreadyExists) {
          currentMeds.push({
            name: newMed.name || newMed.medication,
            dose: newMed.dose,
            frequency: newMed.frequency || 'OD'
          });
        }
      });
    }

    // Ensure CONTINUE medications are also in the list
    if (medications.continue && medications.continue.length > 0) {
      medications.continue.forEach(contMed => {
        const alreadyExists = currentMeds.some(m =>
          (m.name || m.medication || '').toLowerCase() === (contMed.name || contMed.medication || '').toLowerCase()
        );
        if (!alreadyExists) {
          currentMeds.push({
            name: contMed.name || contMed.medication,
            dose: contMed.dose,
            frequency: contMed.frequency || 'OD'
          });
        }
      });
    }

    console.log('📝 Final medications to save:', currentMeds);

    // Use RPC function to bypass RLS
    const { data: rpcData, error: rpcError } = await supabase
      .rpc('update_patient_medications', {
        p_nric: nric,
        p_medications: currentMeds
      });

    if (rpcError) {
      console.error('RPC Error updating patient medications:', rpcError);

      // Fallback: Try direct update
      console.log('⚠️ Trying direct update as fallback...');
      const { data: directData, error: directError } = await supabase
        .from('patients')
        .update({
          current_medications: currentMeds,
          updated_at: new Date().toISOString()
        })
        .eq('nric', nric);

      if (directError) {
        console.error('Direct update also failed:', directError);
        return { success: false, medications: null, error: directError };
      }

      console.log('✅ Patient medications updated via direct update:', currentMeds);
      return { success: true, medications: currentMeds, error: null };
    }

    console.log('✅ Patient medications updated via RPC:', currentMeds);
    return { success: true, medications: currentMeds, error: null };
  } catch (err) {
    console.error('Exception updating patient medications:', err);
    return { success: false, medications: null, error: err };
  }
};

/**
 * Update patient risk level based on selected diagnoses
 * @param {string} nric - Patient's NRIC
 * @param {string} riskLevel - Risk level to set (critical, high, moderate, low)
 * @returns {Promise<{success: boolean, error: Error|null}>}
 */
export const updatePatientRiskLevel = async (nric, riskLevel) => {
  try {
    console.log('🎯 Updating risk level for patient:', nric, 'to:', riskLevel);

    const { data, error } = await supabase
      .from('patients')
      .update({
        risk_level: riskLevel,
        updated_at: new Date().toISOString()
      })
      .eq('nric', nric);

    if (error) {
      console.error('Error updating patient risk level:', error);
      return { success: false, error };
    }

    console.log('✅ Patient risk level updated to:', riskLevel);
    return { success: true, error: null };
  } catch (err) {
    console.error('Exception updating patient risk level:', err);
    return { success: false, error: err };
  }
};

/**
 * Update patient status (active, follow-up, discharged)
 * Uses RPC function to bypass RLS for demo purposes
 * @param {string} nric - Patient's NRIC
 * @param {string} status - Status to set (active, follow-up, discharged)
 * @returns {Promise<{success: boolean, error: Error|null}>}
 */
export const updatePatientStatus = async (nric, status) => {
  try {
    console.log('📋 Updating status for patient:', nric, 'to:', status);

    // Use RPC function to bypass RLS
    const { data, error } = await supabase
      .rpc('update_patient_status_bypass', {
        p_patient_nric: nric,
        p_status: status
      });

    if (error) {
      console.error('Error updating patient status:', error);
      return { success: false, error };
    }

    console.log('✅ Patient status updated to:', status, data);
    return { success: true, error: null };
  } catch (err) {
    console.error('Exception updating patient status:', err);
    return { success: false, error: err };
  }
};

/**
 * Get all patients (for My Patients page)
 * @param {Object} options - Query options
 * @returns {Promise<{patients: Array, error: Error|null}>}
 */
export const getAllPatients = async (options = {}) => {
  try {
    let query = supabase
      .from('patients')
      .select('*')
      .order('updated_at', { ascending: false });

    // Apply status filter
    if (options.status && options.status !== 'all') {
      query = query.eq('status', options.status);
    }

    // Apply search filter (search both with and without dashes for NRIC)
    if (options.search) {
      const normalizedSearch = options.search.replace(/-/g, ''); // Remove dashes
      query = query.or(`full_name.ilike.%${options.search}%,nric.ilike.%${options.search}%,nric.ilike.%${normalizedSearch}%`);
    }

    // Apply limit
    if (options.limit) {
      query = query.limit(options.limit);
    }

    const { data, error } = await query;

    if (error) {
      console.error('Error fetching patients:', error);
      return { patients: [], error };
    }

    console.log('Supabase returned patients:', data); // Debug log

    // Transform to UI format
    const patients = data.map(p => ({
      id: p.nric, // Using NRIC as the primary identifier
      nsn: p.nric,
      name: p.full_name,
      dob: p.date_of_birth,
      age: p.date_of_birth ? Math.floor((new Date() - new Date(p.date_of_birth)) / (365.25 * 24 * 60 * 60 * 1000)) : null,
      gender: p.gender === 'male' ? 'Male' : p.gender === 'female' ? 'Female' : 'Other',
      race: p.race,
      allergies: p.allergies,
      comorbidities: p.comorbidities || [],
      currentMeds: p.current_medications || [],
      riskLevel: p.risk_level || 'low',
      status: p.status || 'active',
      mpisSyncedAt: p.mpis_synced_at,
      updatedAt: p.updated_at,
      // UI-required fields with defaults (diagnoses come from consultations table, not here)
      lastVisit: p.updated_at ? new Date(p.updated_at).toISOString().split('T')[0] : null,
      nextReview: null, // Not in DB yet
      tcaDays: null, // Not in DB yet
      phone: null, // Removed from schema
      email: null, // Removed from schema
      vitalsHistory: p.vitals_history || [],
    }));

    return { patients, error: null };
  } catch (err) {
    console.error('Exception fetching patients:', err);
    return { patients: [], error: err };
  }
};

// ==============================================================================
// PROFILE FUNCTIONS
// ==============================================================================

/**
 * Get current user's profile
 * @returns {Promise<{profile: Object|null, error: Error|null}>}
 */
export const getCurrentProfile = async () => {
  try {
    const user = await getCurrentUser();
    if (!user) {
      return { profile: null, error: null };
    }

    const { data, error } = await supabase
      .from('profiles')
      .select('*')
      .eq('id', user.id)
      .single();

    if (error) {
      console.error('Error fetching profile:', error);
      return { profile: null, error };
    }

    return { profile: data, error: null };
  } catch (err) {
    console.error('Exception fetching profile:', err);
    return { profile: null, error: err };
  }
};

/**
 * Update current user's profile
 * @param {Object} updates - Fields to update
 * @returns {Promise<{success: boolean, error: Error|null}>}
 */
export const updateProfile = async (updates) => {
  try {
    const user = await getCurrentUser();
    if (!user) {
      return { success: false, error: new Error('Not authenticated') };
    }

    const { error } = await supabase
      .from('profiles')
      .update(updates)
      .eq('id', user.id);

    if (error) {
      console.error('Error updating profile:', error);
      return { success: false, error };
    }

    return { success: true, error: null };
  } catch (err) {
    console.error('Exception updating profile:', err);
    return { success: false, error: err };
  }
};

// ==============================================================================
// CONSULTATION FUNCTIONS
// ==============================================================================

/**
 * Start a new consultation for a patient (creates new row in consultations table)
 * Called when "Analyze Clinical Assessment" button is pressed in Step 1
 * @param {string} patientNric - Patient's NRIC
 * @param {string} clinicalNotes - Clinical notes text
 * @returns {Promise<{success: boolean, consultationId: number|null, error: Error|null}>}
 */
export const startConsultation = async (patientNric, clinicalNotes) => {
  try {
    console.log('🆕 Starting new consultation for patient:', patientNric);

    const { data, error } = await supabase
      .rpc('start_consultation', {
        p_patient_nric: patientNric,
        p_clinical_notes: clinicalNotes
      });

    if (error) {
      console.error('Error starting consultation:', error);
      return { success: false, consultationId: null, error };
    }

    console.log('✅ Consultation started:', data);
    return {
      success: true,
      consultationId: data.consultation_id,
      consultationNumber: data.consultation_number,
      error: null
    };
  } catch (err) {
    console.error('Exception starting consultation:', err);
    return { success: false, consultationId: null, error: err };
  }
};

/**
 * Update an existing consultation by ID
 * Called during diagnosis confirmation (Step 2) and plan finalization (Step 3/4)
 * @param {number} consultationId - The consultation ID to update
 * @param {Object} updates - Fields to update
 * @returns {Promise<{success: boolean, error: Error|null}>}
 */
export const updateConsultation = async (consultationId, updates = {}) => {
  try {
    console.log('📝 Updating consultation:', consultationId, updates);

    const { data, error } = await supabase
      .rpc('update_consultation', {
        p_consultation_id: consultationId,
        p_clinical_notes: updates.clinicalNotes || null,
        p_next_review: updates.nextReview || null,
        p_diagnoses: updates.diagnoses || null,
        p_care_plan_summary: updates.carePlanSummary || null,
        p_medication_recommendations: updates.medicationRecommendations || null,
        p_interventions: updates.interventions || null,
        p_monitoring: updates.monitoring || null,
        p_patient_education: updates.patientEducation || null,
        p_referrals: updates.referrals || null,
        p_lifestyle_goals: updates.lifestyleGoals || null,
        p_cpg_references: updates.cpgReferences || null,
        p_report_pdf_url: updates.reportPdfUrl || null,
        p_safety_flags: updates.safetyFlags || null
      });

    if (error) {
      console.error('Error updating consultation:', error);
      return { success: false, error };
    }

    console.log('✅ Consultation updated:', data);
    return { success: true, error: null };
  } catch (err) {
    console.error('Exception updating consultation:', err);
    return { success: false, error: err };
  }
};

/**
 * Upload a care plan PDF blob to Supabase Storage and return the signed URL.
 * @param {number} consultationId - The consultation ID (used as filename)
 * @param {string} patientNric - Patient's NRIC (used as folder name)
 * @param {Blob} pdfBlob - The PDF blob from generateCarePlanPDFBlob()
 * @returns {Promise<{success: boolean, url: string|null, error: Error|null}>}
 */
export const uploadCarePlanPDF = async (consultationId, patientNric, pdfBlob) => {
  try {
    const dateStr = new Date().toISOString().split('T')[0];
    const path = `${patientNric}/CarePlan_${dateStr}_${consultationId}.pdf`;
    console.log('📤 Uploading care plan PDF:', path);

    const { error: uploadError } = await supabase.storage
      .from('care-plan-reports')
      .upload(path, pdfBlob, { contentType: 'application/pdf', upsert: true });

    if (uploadError) {
      console.error('Error uploading PDF:', uploadError);
      return { success: false, url: null, error: uploadError };
    }

    const { data: signedData, error: signError } = await supabase.storage
      .from('care-plan-reports')
      .createSignedUrl(path, 60 * 60 * 24 * 365); // 1 year

    if (signError) {
      console.error('Error creating signed URL:', signError);
      return { success: false, url: null, error: signError };
    }

    console.log('✅ PDF uploaded, signed URL created');
    return { success: true, url: signedData.signedUrl, error: null };
  } catch (err) {
    console.error('Exception uploading care plan PDF:', err);
    return { success: false, url: null, error: err };
  }
};

/**
 * Download a care plan PDF from Supabase Storage by its stored URL.
 * @param {string} reportPdfUrl - The URL stored in the consultation record
 * @param {string} fileName - Desired download filename
 * @returns {Promise<{success: boolean, error: Error|null}>}
 */
export const downloadCarePlanPDF = async (reportPdfUrl, fileName = 'care-plan.pdf') => {
  try {
    const res = await fetch(reportPdfUrl);
    if (!res.ok) throw new Error(`Failed to fetch PDF: ${res.status}`);
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = fileName;
    a.click();
    URL.revokeObjectURL(url);
    return { success: true, error: null };
  } catch (err) {
    console.error('Exception downloading care plan PDF:', err);
    return { success: false, error: err };
  }
};

/**
 * Legacy function - Save or update a consultation for a patient
 * @deprecated Use startConsultation() and updateConsultation() instead
 */
export const saveConsultation = async (patientNric, clinicalNotes, nextReview = null, diagnoses = [], carePlanSummary = null, medicationRecommendations = null, interventions = null, monitoring = null, patientEducation = null, referrals = null, lifestyleGoals = null, cpgReferences = null) => {
  console.warn('⚠️ saveConsultation is deprecated. Use startConsultation() and updateConsultation() instead.');
  // This function is kept for backward compatibility during migration
  // It will be removed in future versions
  return { success: false, data: null, error: new Error('Function deprecated') };
};

/**
 * Get the latest consultation for a patient by NRIC
 * @param {string} patientNric - Patient's NRIC
 * @returns {Promise<{found: boolean, consultation: Object|null, error: Error|null}>}
 */
export const getPatientConsultation = async (patientNric) => {
  try {
    // Get the most recent consultation for this patient
    const { data, error } = await supabase
      .from('consultations')
      .select(`
        *,
        doctor:created_by(full_name)
      `)
      .eq('patient_nric', patientNric)
      .order('consultation_time', { ascending: false })
      .limit(1)
      .maybeSingle();

    if (error) {
      console.error('Error fetching consultation:', error);
      return { found: false, consultation: null, error };
    }

    if (!data) {
      return { found: false, consultation: null, error: null };
    }

    return {
      found: true,
      consultation: {
        id: data.id,
        patientNric: data.patient_nric,
        clinicalNotes: data.clinical_notes,
        nextReview: data.next_review,
        diagnoses: data.diagnoses || [],
        consultationTime: data.consultation_time,
        createdBy: data.created_by,
        updatedBy: data.updated_by,
        createdAt: data.created_at,
        updatedAt: data.updated_at,
        doctorName: data.doctor?.full_name || 'Unknown'
      },
      error: null
    };
  } catch (err) {
    console.error('Exception fetching consultation:', err);
    return { found: false, consultation: null, error: err };
  }
};

/**
 * Get all consultations for a patient by NRIC
 * @param {string} patientNric - Patient's NRIC
 * @param {number} limit - Maximum number of consultations to return (default 10)
 * @returns {Promise<{consultations: Array, error: Error|null}>}
 */
export const getAllPatientConsultations = async (patientNric, limit = 10) => {
  try {
    const { data, error } = await supabase
      .from('consultations')
      .select(`
        *,
        doctor:created_by(full_name)
      `)
      .eq('patient_nric', patientNric)
      .order('consultation_time', { ascending: false })
      .limit(limit);

    if (error) {
      console.error('Error fetching consultations:', error);
      return { consultations: [], error };
    }

    const consultations = (data || []).map(c => ({
      id: c.id,
      patientNric: c.patient_nric,
      clinicalNotes: c.clinical_notes,
      nextReview: c.next_review,
      diagnoses: c.diagnoses || [],
      carePlanSummary: c.care_plan_summary,
      medicationRecommendations: c.medication_recommendations,
      reportPdfUrl: c.report_pdf_url || null,
      consultationTime: c.consultation_time,
      createdAt: c.created_at,
      updatedAt: c.updated_at,
      doctorName: c.doctor?.full_name || 'Unknown'
    }));

    return { consultations, error: null };
  } catch (err) {
    console.error('Exception fetching consultations:', err);
    return { consultations: [], error: err };
  }
};

// ==============================================================================
// PRIOR VISIT SUMMARY FUNCTIONS
// ==============================================================================

/**
 * Persist a lean PriorVisitSummary JSON onto an existing consultation row.
 * Called AFTER the clinician finalises the care plan and the agent
 * /clinical/summarise-prior endpoint returns the JSON.
 *
 * @param {string} patientNric
 * @param {number} consultationNumber - per-patient consultation number
 * @param {Object} priorVisitSummary  - { visit_date, prior_icd_primary, prior_plan_summary, key_labs_delta, what_changed }
 */
export const writePriorVisitSummary = async (patientNric, consultationNumber, priorVisitSummary) => {
  try {
    const { data, error } = await supabase
      .rpc('update_prior_visit_summary_bypass', {
        p_patient_nric: patientNric,
        p_consultation_number: consultationNumber,
        p_prior_visit_summary: priorVisitSummary,
      });

    if (error) {
      console.error('Error writing prior_visit_summary:', error);
      return { success: false, error };
    }
    return { success: true, data, error: null };
  } catch (err) {
    console.error('Exception writing prior_visit_summary:', err);
    return { success: false, error: err };
  }
};

/**
 * Read the most recent non-null prior_visit_summary for a patient.
 * Used when opening a returning patient in DataInputSection — the result
 * should be passed into PatientCase.prior_visit (clinicalApi already wires
 * patientState.priorVisit through to the agent).
 *
 * @returns {Promise<{summary: Object|null, visitMeta: Object|null, error: Error|null}>}
 */
export const getLatestPriorVisitSummary = async (patientNric) => {
  try {
    const { data, error } = await supabase
      .rpc('get_latest_prior_visit_summary', { p_patient_nric: patientNric });

    if (error) {
      console.error('Error reading prior_visit_summary:', error);
      return { summary: null, visitMeta: null, error };
    }

    const summary = data?.prior_visit_summary ?? null;
    const visitMeta = data
      ? {
          consultationId: data.consultation_id ?? null,
          consultationNumber: data.consultation_number ?? null,
          consultationTime: data.consultation_time ?? null,
        }
      : null;
    return { summary, visitMeta, error: null };
  } catch (err) {
    console.error('Exception reading prior_visit_summary:', err);
    return { summary: null, visitMeta: null, error: err };
  }
};

export const saveRPPGVitals = async ({ nric, consultationId, vitals, quality }) => {
  const { hr, bpSystolic, bpDiastolic, spo2, rr, temp } = vitals;
  const { error } = await supabase.from('live_vitals').insert({
    patient_nric:    nric,
    consultation_id: consultationId || null,
    source:          'rppg',
    hr:              hr    ? Number(hr)    : null,
    spo2:            spo2  ? Number(spo2)  : null,
    sbp:             bpSystolic  ? Number(bpSystolic)  : null,
    dbp:             bpDiastolic ? Number(bpDiastolic) : null,
    rr:              rr    ? Number(rr)    : null,
    temp:            temp  ? Number(temp)  : null,
    quality:         quality != null ? +Number(quality).toFixed(1) : null,
    updated_at:      new Date().toISOString(),
  });
  return { error };
};

// Export types for TypeScript users (these work as documentation in JS too)
/**
 * @typedef {import('@supabase/supabase-js').User} User
 * @typedef {import('@supabase/supabase-js').Session} Session
 * @typedef {import('@supabase/supabase-js').AuthChangeEvent} AuthChangeEvent
 */

/**
 * Update patient email and email delivery consent.
 * Stamps email_consent_at = now() when consented = true; clears it when false.
 * @param {string} nric
 * @param {{ email: string, consented: boolean, preferredLanguage?: string }} opts
 */
export const updatePatientDeliveryPrefs = async (nric, { email, consented, preferredLanguage }) => {
  try {
    const updates = {
      email: email || null,
      email_consent_at: consented ? new Date().toISOString() : null,
    };
    if (preferredLanguage) updates.preferred_language = preferredLanguage;

    const { error } = await supabase
      .from('patients')
      .update(updates)
      .eq('nric', nric);

    if (error) {
      console.error('Error updating patient delivery prefs:', error);
      return { success: false, error };
    }
    return { success: true, error: null };
  } catch (err) {
    console.error('Exception updating patient delivery prefs:', err);
    return { success: false, error: err };
  }
};

export default supabase;
