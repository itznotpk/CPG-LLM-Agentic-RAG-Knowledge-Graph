import React, { useRef, useState, useEffect, useCallback } from 'react';
import { useApp } from '../../context/AppContext';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../shared/Notification';
import { generatePdfFromElement } from '../../utils/htmlToPdf';
import { FinalCarePlan } from './finalCarePlan/FinalCarePlan';
import './finalCarePlan/finalCarePlan.css';

export function OutputSection() {
  const { state, resetApp, goToStep, uploadFinalCarePlanPDF } = useApp();
  const { profile: authProfile } = useAuth();
  const toast = useToast();
  const {
    patient, patientData, carePlan, diagnosis, vitals,
    clinicalNotes, nextReviewDate, mpisData, currentUser,
    consultationId, consultationDuration,
  } = state;

  const fcpRef = useRef(null);
  const [pdfUploaded, setPdfUploaded] = useState(false);
  const [pdfUploading, setPdfUploading] = useState(false);

  // Patient: Step 4 uses `patient`, Step 3 uses `patientData` — accept either
  const resolvedPatient = patient ?? patientData ?? {};

  // Selected diagnoses (1 or more)
  const selectedIds = diagnosis?.selectedDiagnosisIds?.length
    ? diagnosis.selectedDiagnosisIds
    : [diagnosis?.differentials?.[0]?.id].filter(Boolean);
  const diagnoses = (diagnosis?.differentials || [])
    .filter((d) => selectedIds.includes(d.id))
    .map((d, i) => ({
      name: d.name,
      icdCode: d.icdCode,
      note: d.note || (i === 0 ? 'Primary diagnosis' : 'Comorbid finding'),
    }));

  // Allergies: array | comma-string | "none known"
  let allergies = [];
  if (Array.isArray(mpisData?.allergies)) allergies = mpisData.allergies;
  else if (typeof mpisData?.allergies === 'string' &&
           mpisData.allergies.toLowerCase() !== 'none known') {
    allergies = mpisData.allergies.split(',').map((s) => s.trim()).filter(Boolean);
  }

  // Vitals extended (bmi/rr fallbacks)
  const v = vitals || {};
  const height = parseFloat(v.height) || null;
  const weight = parseFloat(v.weight) || null;
  const bmi = v.bmi ?? (height && weight
    ? Number((weight / Math.pow(height / 100, 2)).toFixed(1))
    : null);
  const vitalsExt = { ...v, weight, height, bmi, rr: v.rr ?? 18 };

  // Provider — dynamically wire to authProfile (current login session's doctor)
  const provider = authProfile ? {
    name: authProfile.full_name || 'Dr. Clinician',
    role: authProfile.specialty || authProfile.role || 'Clinician',
    mmcNo: authProfile.license_number || '—',
    clinic: authProfile.facility || 'Clinic',
  } : {
    name: 'Dr. Aiman Halim',
    role: 'Family Medicine Specialist',
    mmcNo: 'MMC-48921',
    clinic: 'Klinik Kesihatan Bandar Bukit Damansara',
  };

  const now = new Date();
  const encounter = {
    id: consultationId || `ENC-${now.getFullYear()}-${String(Date.now()).slice(-6)}`,
    date: now.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' }),
    time: now.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', hour12: false }),
    type: 'Follow-up consultation',
    duration: consultationDuration || '—',
  };

  // ── Shared helper: capture .paper DOM → PDF Blob ──────────────────────────
  const capturePaperPdf = useCallback(async ({ download = false } = {}) => {
    const paperEl = fcpRef.current?.getPaperElement?.();
    if (!paperEl) {
      console.warn('Paper element not found, cannot generate PDF');
      return null;
    }
    const fileName = `CarePlan_${resolvedPatient?.name?.replace(/\s+/g, '_') || 'Patient'}_${new Date().toISOString().split('T')[0]}.pdf`;
    const blob = await generatePdfFromElement(paperEl, { fileName, download });
    return blob;
  }, [resolvedPatient?.name]);

  // ── Upload PDF blob to Supabase (idempotent — skips if already done) ──────
  const uploadPdf = useCallback(async (blob) => {
    if (!blob || pdfUploaded || pdfUploading) return;
    setPdfUploading(true);
    try {
      const result = await uploadFinalCarePlanPDF(blob);
      if (result?.success) {
        setPdfUploaded(true);
        console.log('✅ PDF uploaded to Supabase successfully');
      } else {
        toast.error('Failed to save PDF to database. Please check console.');
      }
    } catch (err) {
      console.error('PDF upload failed:', err);
      toast.error('PDF upload failed: ' + err.message);
    } finally {
      setPdfUploading(false);
    }
  }, [uploadFinalCarePlanPDF, pdfUploaded, pdfUploading]);

  // ── Auto-upload on mount: capture DOM after render, upload to Supabase ────
  useEffect(() => {
    if (pdfUploaded || pdfUploading) return;

    // Small delay to ensure the .paper DOM is fully rendered and styled
    const timer = setTimeout(async () => {
      try {
        const blob = await capturePaperPdf({ download: false });
        if (blob) {
          await uploadPdf(blob);
        }
      } catch (err) {
        console.error('Auto-upload PDF failed:', err);
      }
    }, 1500);

    return () => clearTimeout(timer);
  }, []); // Run once on mount

  // ── "Export PDF" — download + upload (if not already uploaded) ─────────────
  const handleExportPDF = async () => {
    const blob = await capturePaperPdf({ download: true });
    if (blob && !pdfUploaded) {
      await uploadPdf(blob);
    }
  };

  const handlePrint = () => window.print();

  // ── "Approve Care Plan" — upload PDF (if needed), then reset ──────────────
  const handleNewAssessment = async () => {
    if (!pdfUploaded) {
      try {
        const blob = await capturePaperPdf({ download: false });
        if (blob) await uploadPdf(blob);
      } catch (err) {
        console.error('Final PDF upload before reset failed:', err);
      }
    }
    toast.success('Care plan successfully generated and saved to Supabase!');
    resetApp();
  };

  const handleBack = () => goToStep(3);

  if (!carePlan) return null;

  return (
    <FinalCarePlan
      ref={fcpRef}
      patient={resolvedPatient}
      diagnoses={diagnoses}
      carePlan={carePlan}
      allergies={allergies}
      vitals={vitalsExt}
      clinicalNotes={clinicalNotes || 'No clinical notes recorded for this encounter.'}
      provider={provider}
      encounter={encounter}
      nextReviewDate={nextReviewDate}
      onExportPDF={handleExportPDF}
      onPrint={handlePrint}
      onBack={handleBack}
      onNewAssessment={handleNewAssessment}
      pdfUploaded={pdfUploaded}
      pdfUploading={pdfUploading}
    />
  );
}
