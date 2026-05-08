-- ==============================================================================
-- MHNEXUS CPG-LLM SIMPLIFIED SCHEMA (Phase 1)
-- ==============================================================================
-- This is a MINIMAL schema to get started with:
--   1. Clinicians (profiles) - doctors/nurses who use the system
--   2. Patients - with fields needed for MPIS sync
--
-- Run this SQL in Supabase: Dashboard → SQL Editor → New Query → Paste & Run
-- ==============================================================================

-- ==============================================================================
-- 0. CLEAN UP - DROP ALL EXISTING TABLES AND OBJECTS
-- ==============================================================================
-- WARNING: This will delete ALL existing data in ALL tables!

-- Drop ALL tables first (CASCADE will automatically drop dependent triggers)
DROP TABLE IF EXISTS public.usage_metrics CASCADE;
DROP TABLE IF EXISTS public.audit_log CASCADE;
DROP TABLE IF EXISTS public.cds_alerts CASCADE;
DROP TABLE IF EXISTS public.care_plan_investigations CASCADE;
DROP TABLE IF EXISTS public.care_plan_interventions CASCADE;
DROP TABLE IF EXISTS public.care_plan_medications CASCADE;
DROP TABLE IF EXISTS public.care_plans CASCADE;
DROP TABLE IF EXISTS public.diagnoses CASCADE;
DROP TABLE IF EXISTS public.consultations CASCADE;
DROP TABLE IF EXISTS public.vitals CASCADE;
DROP TABLE IF EXISTS public.appointments CASCADE;
DROP TABLE IF EXISTS public.patient_medications CASCADE;
DROP TABLE IF EXISTS public.patient_comorbidities CASCADE;
DROP TABLE IF EXISTS public.patient_allergies CASCADE;
DROP TABLE IF EXISTS public.patients CASCADE;
DROP TABLE IF EXISTS public.profiles CASCADE;

-- Drop ALL functions (CASCADE handles dependencies)
DROP FUNCTION IF EXISTS update_updated_at_column() CASCADE;
DROP FUNCTION IF EXISTS handle_new_user() CASCADE;
DROP FUNCTION IF EXISTS search_patient_by_nric(TEXT) CASCADE;
DROP FUNCTION IF EXISTS register_patient(TEXT, TEXT, DATE, gender_type, TEXT, TEXT, TEXT, TEXT[], UUID) CASCADE;
DROP FUNCTION IF EXISTS update_patient_from_mpis(TEXT, TEXT, TEXT[], JSONB, JSONB) CASCADE;
DROP FUNCTION IF EXISTS calculate_vital_status() CASCADE;
DROP FUNCTION IF EXISTS calculate_patient_risk() CASCADE;
DROP FUNCTION IF EXISTS log_audit_event() CASCADE;
DROP FUNCTION IF EXISTS update_usage_metrics(UUID, TEXT, INTEGER) CASCADE;

-- Drop ALL enum types
DROP TYPE IF EXISTS care_plan_status CASCADE;
DROP TYPE IF EXISTS vital_status CASCADE;
DROP TYPE IF EXISTS medication_action CASCADE;
DROP TYPE IF EXISTS risk_level CASCADE;
DROP TYPE IF EXISTS priority_level CASCADE;
DROP TYPE IF EXISTS appointment_status CASCADE;
DROP TYPE IF EXISTS patient_status CASCADE;
DROP TYPE IF EXISTS gender_type CASCADE;

-- ==============================================================================
-- 1. ENABLE EXTENSIONS
-- ==============================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ==============================================================================
-- 2. ENUM TYPES
-- ==============================================================================

-- Gender enum
CREATE TYPE gender_type AS ENUM ('male', 'female', 'other');

-- Patient status enum
CREATE TYPE patient_status AS ENUM ('active', 'discharged', 'follow-up', 'deceased');

-- Risk level enum
CREATE TYPE risk_level AS ENUM ('low', 'moderate', 'high', 'critical');

-- ==============================================================================
-- 3. PROFILES (Clinicians/Doctors) TABLE
-- ==============================================================================
-- This table extends Supabase auth.users
-- When a user signs up, a profile is automatically created

CREATE TABLE public.profiles (
    -- Primary key links to Supabase auth
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    
    -- Basic info
    email TEXT UNIQUE NOT NULL,
    full_name TEXT NOT NULL,
    title TEXT DEFAULT 'Dr.',
    
    -- Professional info
    specialty TEXT,
    license_number TEXT,
    phone TEXT,
    facility TEXT,
    department TEXT,
    
    -- Profile picture
    avatar_url TEXT,
    
    -- Role in the system
    role TEXT DEFAULT 'doctor' CHECK (role IN ('doctor', 'nurse', 'admin', 'pharmacist')),
    
    -- User settings (theme, notifications, etc.)
    settings JSONB DEFAULT '{
        "theme": "dark",
        "accentColor": "cyan",
        "notifications": {
            "email": true,
            "push": true,
            "emergencyAlerts": true
        }
    }'::jsonb,
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ==============================================================================
-- 4. PATIENTS TABLE
-- ==============================================================================
-- Fields aligned with your UI's "Sync from MPIS" feature
-- When clinician enters NRIC, these fields are populated

CREATE TABLE public.patients (
    -- =====================
    -- PATIENT IDENTIFIERS
    -- =====================
    nric TEXT PRIMARY KEY,                        -- National Registration IC (e.g., 580315-08-1234) - PRIMARY KEY
    
    -- =====================
    -- DEMOGRAPHICS (Shown in UI after MPIS sync)
    -- =====================
    full_name TEXT NOT NULL,
    date_of_birth DATE NOT NULL,
    -- NOTE: Age is calculated in the application layer, not as a generated column
    -- because PostgreSQL requires generated columns to use immutable expressions
    gender gender_type NOT NULL,
    race TEXT,                                     -- Malay, Chinese, Indian, Other
    
    -- =====================
    -- MEDICAL DATA (from MPIS sync)
    -- =====================
    allergies TEXT,                                -- e.g., "Penicillin", "Sulfa drugs"
    comorbidities TEXT[],                          -- Array: ["Hypertension", "Type 2 Diabetes"]
    current_medications JSONB DEFAULT '[]'::jsonb, -- Array of {name, dose, frequency}
    
    -- =====================
    -- STATUS & RISK
    -- =====================
    status patient_status DEFAULT 'active',
    risk_level risk_level DEFAULT 'low',
    
    -- =====================
    -- MPIS SYNC TRACKING
    -- =====================
    mpis_synced_at TIMESTAMPTZ,                    -- When was data last synced from MPIS
    mpis_data JSONB DEFAULT '{}'::jsonb,           -- Raw MPIS response (for debugging)
    
    -- =====================
    -- AUDIT FIELDS
    -- =====================
    created_by UUID REFERENCES public.profiles(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ==============================================================================
-- 5. INDEXES (For fast lookups)
-- ==============================================================================

-- Fast NRIC lookups (most common search)
CREATE INDEX idx_patients_nric ON public.patients(nric);

-- Name search
CREATE INDEX idx_patients_name ON public.patients(full_name);

-- Status filtering
CREATE INDEX idx_patients_status ON public.patients(status);

-- ==============================================================================
-- 6. FUNCTIONS
-- ==============================================================================

-- Auto-update the updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create user profile when they sign up
CREATE OR REPLACE FUNCTION handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.profiles (id, email, full_name)
    VALUES (
        NEW.id,
        NEW.email,
        COALESCE(NEW.raw_user_meta_data->>'full_name', split_part(NEW.email, '@', 1))
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to search patient by NRIC (for MPIS sync)
CREATE OR REPLACE FUNCTION search_patient_by_nric(p_nric TEXT)
RETURNS TABLE (
    nric TEXT,
    full_name TEXT,
    date_of_birth DATE,
    age INTEGER,
    gender gender_type,
    race TEXT,
    allergies TEXT,
    comorbidities TEXT[],
    current_medications JSONB,
    risk_level risk_level,
    mpis_synced_at TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        p.nric,
        p.full_name,
        p.date_of_birth,
        EXTRACT(YEAR FROM age(CURRENT_DATE, p.date_of_birth))::INTEGER AS age,
        p.gender,
        p.race,
        p.allergies,
        p.comorbidities,
        p.current_medications,
        p.risk_level,
        p.mpis_synced_at
    FROM public.patients p
    WHERE p.nric = p_nric;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to register a new patient
CREATE OR REPLACE FUNCTION register_patient(
    p_nric TEXT,
    p_full_name TEXT,
    p_date_of_birth DATE,
    p_gender gender_type,
    p_race TEXT DEFAULT NULL,
    p_allergies TEXT DEFAULT NULL,
    p_comorbidities TEXT[] DEFAULT NULL,
    p_created_by UUID DEFAULT NULL
)
RETURNS TEXT AS $$
BEGIN
    INSERT INTO public.patients (
        nric,
        full_name,
        date_of_birth,
        gender,
        race,
        allergies,
        comorbidities,
        created_by,
        mpis_synced_at
    ) VALUES (
        p_nric,
        p_full_name,
        p_date_of_birth,
        p_gender,
        p_race,
        p_allergies,
        COALESCE(p_comorbidities, ARRAY[]::TEXT[]),
        p_created_by,
        NOW()
    );
    
    RETURN p_nric;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to update patient from MPIS sync
CREATE OR REPLACE FUNCTION update_patient_from_mpis(
    p_nric TEXT,
    p_allergies TEXT DEFAULT NULL,
    p_comorbidities TEXT[] DEFAULT NULL,
    p_current_medications JSONB DEFAULT NULL,
    p_mpis_data JSONB DEFAULT NULL
)
RETURNS BOOLEAN AS $$
BEGIN
    UPDATE public.patients
    SET 
        allergies = COALESCE(p_allergies, allergies),
        comorbidities = COALESCE(p_comorbidities, comorbidities),
        current_medications = COALESCE(p_current_medications, current_medications),
        mpis_data = COALESCE(p_mpis_data, mpis_data),
        mpis_synced_at = NOW(),
        updated_at = NOW()
    WHERE nric = p_nric;
    
    RETURN FOUND;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ==============================================================================
-- 7. TRIGGERS
-- ==============================================================================

-- Auto-update timestamps
CREATE TRIGGER update_profiles_updated_at
    BEFORE UPDATE ON public.profiles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_patients_updated_at
    BEFORE UPDATE ON public.patients
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Create profile when user signs up
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION handle_new_user();

-- ==============================================================================
-- 8. ROW LEVEL SECURITY (RLS)
-- ==============================================================================

-- Enable RLS
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.patients ENABLE ROW LEVEL SECURITY;

-- Profiles: Users can view all profiles, but only edit their own
CREATE POLICY "Profiles are viewable by authenticated users"
    ON public.profiles FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY "Users can update own profile"
    ON public.profiles FOR UPDATE
    TO authenticated
    USING (auth.uid() = id);

CREATE POLICY "Users can insert own profile"
    ON public.profiles FOR INSERT
    TO authenticated
    WITH CHECK (auth.uid() = id);

-- Patients: SELECT for public, INSERT/UPDATE for authenticated only
-- (Aligned with consultations table policies)
CREATE POLICY "Patients viewable by public"
    ON public.patients FOR SELECT
    TO public
    USING (true);

CREATE POLICY "Patients insertable by authenticated users"
    ON public.patients FOR INSERT
    TO authenticated
    WITH CHECK (true);

CREATE POLICY "Patients updatable by authenticated users"
    ON public.patients FOR UPDATE
    TO authenticated
    USING (true);

-- ==============================================================================
-- 9. SAMPLE DATA - Ahmad bin Abdullah
-- ==============================================================================

INSERT INTO public.patients (
    nric,
    full_name,
    date_of_birth,
    gender,
    race,
    allergies,
    comorbidities,
    current_medications,
    risk_level,
    mpis_synced_at
) VALUES (
    '580315-08-1234',
    'Ahmad bin Abdullah',
    '1958-03-15',
    'male',
    'Malay',
    'Penicillin',
    ARRAY['Type 2 Diabetes Mellitus (10 years)', 'Hypertension (15 years)', 'Dyslipidemia'],
    '[
        {"name": "Metformin", "dose": "1000mg", "frequency": "BD"},
        {"name": "Amlodipine", "dose": "10mg", "frequency": "OD"},
        {"name": "Atorvastatin", "dose": "40mg", "frequency": "ON"}
    ]'::jsonb,
    'high',
    NOW()
);

-- ==============================================================================
-- DONE! Your database now has:
-- ==============================================================================
-- 
-- TABLES:
--   ✓ public.profiles - Clinicians (doctors, nurses, etc.)
--   ✓ public.patients - Patient records with MPIS sync fields
--
-- FUNCTIONS:
--   ✓ search_patient_by_nric(nric) - For MPIS lookup
--   ✓ register_patient(...) - Create new patient
--   ✓ update_patient_from_mpis(...) - Update from MPIS sync
--   ✓ handle_new_user() - Auto-create profile on signup
--
-- SAMPLE DATA:
--   ✓ Ahmad bin Abdullah (NRIC: 580315-08-1234)
--
-- TEST IT:
--   SELECT * FROM search_patient_by_nric('580315-08-1234');
--
-- ==============================================================================
