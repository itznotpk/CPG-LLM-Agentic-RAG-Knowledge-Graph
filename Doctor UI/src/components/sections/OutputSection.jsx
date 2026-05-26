import React, { useRef } from 'react';
import { useApp } from '../../context/AppContext';
import { generatePdfFromElement } from '../../utils/htmlToPdf';
import { FinalCarePlan } from './finalCarePlan/FinalCarePlan';
import './finalCarePlan/finalCarePlan.css';

export function OutputSection() {
  const { state, resetApp, goToStep } = useApp();
  const {
    patient, patientData, carePlan, diagnosis, vitals,
    clinicalNotes, nextReviewDate, mpisData, currentUser,
    consultationId, consultationDuration,
  } = state;

  const fcpRef = useRef(null);

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

  // Provider — wire to currentUser when available
  const provider = currentUser?.name
    ? {
        name: currentUser.name,
        role: currentUser.role || 'Clinician',
        mmcNo: currentUser.mmcNo || '—',
        clinic: currentUser.clinic || 'Clinic',
      }
    : {
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

  const handleExportPDF = async () => {
    const paperEl = fcpRef.current?.getPaperElement?.();
    if (!paperEl) {
      console.warn('Paper element not found, cannot export PDF');
      return;
    }
    const fileName = `CarePlan_${resolvedPatient?.name?.replace(/\s+/g, '_') || 'Patient'}_${new Date().toISOString().split('T')[0]}.pdf`;
    await generatePdfFromElement(paperEl, { fileName, download: true });
  };
  const handlePrint = () => window.print();
  const handleNewAssessment = () => resetApp();
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
    />
  );
}

