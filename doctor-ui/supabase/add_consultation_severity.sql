-- ============================================================================
-- MIGRATION: Add severity_staging to consultations
-- Run in Supabase Dashboard → SQL Editor → New Query → Paste & Run
--
-- Stores the Step-1 severity/staging map (e.g. NYHA class, GOLD stage, tumour
-- stage) as a queryable JSONB column per consultation. Previously this was only
-- string-embedded into clinical_notes (a [Severity/Staging] block), which is not
-- queryable. Written via a direct supabase.from('consultations').update(...) in
-- saveConsultationSeverity() — NOT the update_consultation RPC — so no RPC
-- overload rebuild is required.
-- ============================================================================

ALTER TABLE consultations
  ADD COLUMN IF NOT EXISTS severity_staging JSONB;
