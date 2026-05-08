import jsPDF from 'jspdf';
import 'jspdf-autotable';

/**
 * Generates a PDF care plan document
 * @param {Object} data - The care plan data
 * @param {Object} data.patient - Patient demographics
 * @param {Object} data.diagnosis - Diagnosis information
 * @param {Object} data.carePlan - Care plan details
 * @returns {void} - Downloads the PDF
 */
export function generateCarePlanPDF({ patient, diagnosis, carePlan }) {
  const doc = new jsPDF();
  const pageWidth = doc.internal.pageSize.getWidth();
  const margin = 20;
  let yPos = 20;

  // Get selected diagnoses (supports multiple selection)
  const selectedIds = diagnosis?.selectedDiagnosisIds?.length > 0
    ? diagnosis.selectedDiagnosisIds
    : [diagnosis?.differentials?.[0]?.id].filter(Boolean);
  const selectedDiagnoses = diagnosis?.differentials?.filter(
    (d) => selectedIds.includes(d.id)
  ) || [];

  // Helper function to add section header
  const addSectionHeader = (title) => {
    if (yPos > 250) {
      doc.addPage();
      yPos = 20;
    }
    doc.setFillColor(59, 177, 156); // primary-600
    doc.rect(margin, yPos, pageWidth - 2 * margin, 8, 'F');
    doc.setTextColor(255, 255, 255);
    doc.setFontSize(11);
    doc.setFont('helvetica', 'bold');
    doc.text(title, margin + 3, yPos + 5.5);
    doc.setTextColor(0, 0, 0);
    yPos += 12;
  };

  // Helper function to add text
  const addText = (label, value, indent = 0) => {
    if (yPos > 270) {
      doc.addPage();
      yPos = 20;
    }
    doc.setFontSize(10);
    doc.setFont('helvetica', 'bold');
    doc.text(label + ':', margin + indent, yPos);
    doc.setFont('helvetica', 'normal');
    const labelWidth = doc.getTextWidth(label + ': ');

    // Handle long text with wrapping
    const maxWidth = pageWidth - margin * 2 - labelWidth - indent;
    const lines = doc.splitTextToSize(String(value || 'N/A'), maxWidth);
    doc.text(lines, margin + indent + labelWidth, yPos);
    yPos += 5 * lines.length;
  };

  // ===== HEADER =====
  doc.setFillColor(11, 94, 60); // primary-900
  doc.rect(0, 0, pageWidth, 35, 'F');

  doc.setTextColor(255, 255, 255);
  doc.setFontSize(20);
  doc.setFont('helvetica', 'bold');
  doc.text('MHNexus CPG LLM', margin, 15);

  doc.setFontSize(12);
  doc.setFont('helvetica', 'normal');
  doc.text('AI-Generated Care Plan Report', margin, 23);

  doc.setFontSize(9);
  doc.text(`Generated: ${new Date().toLocaleString()}`, margin, 30);

  doc.setTextColor(0, 0, 0);
  yPos = 45;

  // ===== PATIENT INFORMATION =====
  addSectionHeader('PATIENT INFORMATION');

  doc.autoTable({
    startY: yPos,
    margin: { left: margin, right: margin },
    theme: 'grid',
    headStyles: { fillColor: [212, 230, 241], textColor: [30, 41, 59], fontStyle: 'bold' },
    body: [
      ['Name', patient?.name || 'N/A', 'Age', patient?.age ? `${patient.age} years` : 'N/A'],
      ['Gender', patient?.gender || 'N/A', 'DOB', patient?.dob || 'N/A'],
      ['NRIC', patient?.nsn || 'N/A', '', ''],
    ],
    columnStyles: {
      0: { fontStyle: 'bold', cellWidth: 30 },
      1: { cellWidth: 55 },
      2: { fontStyle: 'bold', cellWidth: 30 },
      3: { cellWidth: 55 },
    },
  });
  yPos = doc.lastAutoTable.finalY + 10;

  // ===== DIAGNOSIS =====
  addSectionHeader(selectedDiagnoses.length > 1 ? 'DIAGNOSES' : 'PRIMARY DIAGNOSIS');

  selectedDiagnoses.forEach((diag, idx) => {
    if (selectedDiagnoses.length > 1) {
      doc.setFont('helvetica', 'bold');
      doc.text(`${idx + 1}. ${diag.name}`, margin, yPos);
      yPos += 5;
      addText('ICD-11 Code', diag.icdCode, 5);
      addText('Probability', `${diag.probability}%`, 5);
      addText('Risk Level', diag.risk?.toUpperCase(), 5);
      yPos += 3;
    } else {
      addText('Diagnosis', diag.name);
      addText('ICD-11 Code', diag.icdCode);
      addText('Probability', `${diag.probability}%`);
      addText('Risk Level', diag.risk?.toUpperCase());
    }
  });
  yPos += 5;

  // ===== CLINICAL SUMMARY =====
  if (carePlan?.clinicalSummary) {
    addSectionHeader('CLINICAL ASSESSMENT SUMMARY');
    doc.setFontSize(10);
    doc.setFont('helvetica', 'normal');
    const summaryLines = doc.splitTextToSize(carePlan.clinicalSummary, pageWidth - 2 * margin);
    doc.text(summaryLines, margin, yPos);
    yPos += 5 * summaryLines.length + 5;
  }

  // ===== MEDICATION CHANGES =====
  addSectionHeader('MEDICATION MANAGEMENT');

  // STOP medications
  const stopMeds = carePlan?.medications?.stop?.filter(m => m.accepted !== false) || [];
  if (stopMeds.length > 0) {
    doc.setFontSize(10);
    doc.setFont('helvetica', 'bold');
    doc.setTextColor(220, 38, 38); // red
    doc.text('STOP:', margin, yPos);
    doc.setTextColor(0, 0, 0);
    yPos += 5;
    stopMeds.forEach(med => {
      doc.setFont('helvetica', 'normal');
      doc.text(`• ${med.name} ${med.dose} - ${med.reason}`, margin + 5, yPos);
      yPos += 5;
    });
    yPos += 3;
  }

  // START medications
  const startMeds = carePlan?.medications?.start?.filter(m => m.accepted !== false) || [];
  if (startMeds.length > 0) {
    doc.setFontSize(10);
    doc.setFont('helvetica', 'bold');
    doc.setTextColor(22, 163, 74); // green
    doc.text('START:', margin, yPos);
    doc.setTextColor(0, 0, 0);
    yPos += 5;
    startMeds.forEach(med => {
      doc.setFont('helvetica', 'normal');
      doc.text(`• ${med.name} ${med.dose} - ${med.reason}`, margin + 5, yPos);
      yPos += 5;
    });
    yPos += 3;
  }

  // CONTINUE medications
  const continueMeds = carePlan?.medications?.continue || [];
  if (continueMeds.length > 0) {
    doc.setFontSize(10);
    doc.setFont('helvetica', 'bold');
    doc.setTextColor(37, 99, 235); // blue
    doc.text('CONTINUE:', margin, yPos);
    doc.setTextColor(0, 0, 0);
    yPos += 5;
    continueMeds.forEach(med => {
      doc.setFont('helvetica', 'normal');
      doc.text(`• ${med.name} ${med.dose}`, margin + 5, yPos);
      yPos += 5;
    });
    yPos += 3;
  }

  // ===== INTERVENTIONS =====
  const interventions = carePlan?.interventions?.filter(i => i.accepted !== false) || [];
  if (interventions.length > 0) {
    addSectionHeader('INTERVENTIONS & PROCEDURES');

    doc.autoTable({
      startY: yPos,
      margin: { left: margin, right: margin },
      theme: 'striped',
      headStyles: { fillColor: [59, 177, 156], textColor: [255, 255, 255] },
      head: [['Intervention', 'Code', 'Urgency']],
      body: interventions.map(item => [item.name, item.code, item.urgency]),
    });
    yPos = doc.lastAutoTable.finalY + 10;
  }

  // ===== INVESTIGATIONS =====
  const investigations = carePlan?.investigations?.filter(i => i.accepted !== false) || [];
  if (investigations.length > 0) {
    addSectionHeader('LABORATORY INVESTIGATIONS');

    doc.autoTable({
      startY: yPos,
      margin: { left: margin, right: margin },
      theme: 'striped',
      headStyles: { fillColor: [59, 177, 156], textColor: [255, 255, 255] },
      head: [['Investigation', 'Code', 'Priority']],
      body: investigations.map(item => [item.name, item.code, item.priority]),
    });
    yPos = doc.lastAutoTable.finalY + 10;
  }

  // ===== MONITORING =====
  const monitoring = carePlan?.monitoring?.filter(m => m.accepted !== false) || [];
  if (monitoring.length > 0) {
    addSectionHeader('MONITORING & NURSING CARE');
    monitoring.forEach(item => {
      doc.setFont('helvetica', 'normal');
      doc.setFontSize(10);
      doc.text(`☐ ${item.task}`, margin, yPos);
      yPos += 5;
    });
    yPos += 5;
  }

  // ===== DISPOSITION =====
  if (carePlan?.disposition) {
    addSectionHeader('DISPOSITION & FOLLOW-UP');

    addText('Follow-up', carePlan.disposition.followUp);
    yPos += 3;

    if (carePlan.disposition.referrals?.length > 0) {
      doc.setFont('helvetica', 'bold');
      doc.text('Referrals:', margin, yPos);
      yPos += 5;
      carePlan.disposition.referrals.forEach(ref => {
        doc.setFont('helvetica', 'normal');
        doc.text(`• ${ref.specialty} (${ref.urgency}) - ${ref.reason}`, margin + 5, yPos);
        yPos += 5;
      });
      yPos += 3;
    }

    if (carePlan.disposition.patientEducation?.length > 0) {
      doc.setFont('helvetica', 'bold');
      doc.text('Patient Education:', margin, yPos);
      yPos += 5;
      carePlan.disposition.patientEducation.forEach(item => {
        doc.setFont('helvetica', 'normal');
        const lines = doc.splitTextToSize(`• ${item}`, pageWidth - 2 * margin - 5);
        doc.text(lines, margin + 5, yPos);
        yPos += 5 * lines.length;
      });
    }
  }

  // ===== FOOTER =====
  const pageCount = doc.internal.getNumberOfPages();
  for (let i = 1; i <= pageCount; i++) {
    doc.setPage(i);
    doc.setFontSize(8);
    doc.setTextColor(128, 128, 128);
    doc.text(
      `Page ${i} of ${pageCount} | MHNexus CPG LLM - AI-Generated Care Plan | ${new Date().toLocaleDateString()}`,
      pageWidth / 2,
      doc.internal.pageSize.getHeight() - 10,
      { align: 'center' }
    );

    // Disclaimer
    doc.setFontSize(7);
    doc.text(
      'This AI-generated care plan should be reviewed and approved by the treating physician before implementation.',
      pageWidth / 2,
      doc.internal.pageSize.getHeight() - 5,
      { align: 'center' }
    );
  }

  // Save the PDF
  const fileName = `CarePlan_${patient?.name?.replace(/\s+/g, '_') || 'Patient'}_${new Date().toISOString().split('T')[0]}.pdf`;
  doc.save(fileName);
}
