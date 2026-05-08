import React, { useState } from 'react';
import {
  CheckCircle,
  Download,
  Eye,
  FileText,
  RefreshCw,
  Printer,
  Share2,
  ChevronDown,
  ChevronUp,
  Pill,
  Stethoscope,
  FlaskConical,
  Calendar,
  Check,
  X,
  User,
} from 'lucide-react';
import { GlassCard, Button, Badge } from '../shared';
import { useApp } from '../../context/AppContext';
import { useTheme } from '../../context/ThemeContext';
import { generateCarePlanPDF } from '../../utils/pdfGenerator';

// Summary Sidebar Component
function PlanSummary({ carePlan, patient, nextReviewDate }) {
  const [isExpanded, setIsExpanded] = useState(true);
  const { isDark } = useTheme();

  const acceptedMedsStop = carePlan.medications.stop.filter((m) => m.accepted);
  const acceptedMedsStart = carePlan.medications.start.filter((m) => m.accepted);
  const acceptedInterventions = carePlan.interventions.filter((i) => i.accepted);
  const acceptedInvestigations = carePlan.investigations.filter((i) => i.accepted);

  return (
    <GlassCard className="p-5">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between mb-4"
      >
        <div className="flex items-center gap-3">
          <div className="p-2 bg-green-500/20 rounded-xl">
            <FileText className={`w-5 h-5 ${isDark ? 'text-green-400' : 'text-green-600'}`} />
          </div>
          <h3 className={`text-lg font-semibold ${isDark ? 'text-white' : 'text-slate-800'}`}>Plan Summary</h3>
        </div>
        {isExpanded ? (
          <ChevronUp className={`w-5 h-5 ${isDark ? 'text-slate-400' : 'text-slate-600'}`} />
        ) : (
          <ChevronDown className={`w-5 h-5 ${isDark ? 'text-slate-400' : 'text-slate-600'}`} />
        )}
      </button>

      {isExpanded && (
        <div className="space-y-4 animate-fadeIn">
          {/* Patient Info */}
          <div className={`p-3 rounded-xl ${isDark ? 'bg-[var(--accent-primary)]/20' : 'bg-[var(--accent-primary)]/10'}`}>
            <div className="flex items-center gap-2 mb-1">
              <User className="w-4 h-4 text-[var(--accent-primary)]" />
              <span className={`font-medium ${isDark ? 'text-white' : 'text-slate-800'}`}>{patient.name || 'Patient'}</span>
            </div>
            <p className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
              {patient.age ? `${patient.age} years old` : ''} {patient.gender ? `• ${patient.gender}` : ''}
            </p>
          </div>

          {/* Medication Changes */}
          <div>
            <div className="flex items-center gap-2 mb-2">
              <Pill className="w-4 h-4 text-[var(--accent-primary)]" />
              <span className={`font-medium ${isDark ? 'text-white' : 'text-slate-800'}`}>Medication Changes</span>
            </div>
            <div className="space-y-1 pl-6">
              {acceptedMedsStop.map((med) => (
                <div key={med.id} className="flex items-center gap-2 text-sm">
                  <X className="w-3 h-3 text-red-500" />
                  <span className={`font-medium ${isDark ? 'text-red-400' : 'text-red-800'}`}>Stop {med.name}</span>
                </div>
              ))}
              {acceptedMedsStart.map((med) => (
                <div key={med.id} className="flex items-center gap-2 text-sm">
                  <Check className="w-3 h-3 text-green-500" />
                  <span className={`font-medium ${isDark ? 'text-green-400' : 'text-green-800'}`}>Start {med.name} {med.dose}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Interventions */}
          {acceptedInterventions.length > 0 && (
            <div>
              <div className="flex items-center gap-2 mb-2">
                <Stethoscope className="w-4 h-4 text-[var(--accent-primary)]" />
                <span className={`font-medium ${isDark ? 'text-white' : 'text-slate-800'}`}>Interventions</span>
              </div>
              <div className="space-y-1 pl-6">
                {acceptedInterventions.map((item) => (
                  <div key={item.id} className="flex items-center gap-2 text-sm">
                    <Check className="w-3 h-3 text-green-500" />
                    <span className={isDark ? 'text-slate-300' : 'text-slate-700'}>{item.name}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Investigations */}
          {acceptedInvestigations.length > 0 && (
            <div>
              <div className="flex items-center gap-2 mb-2">
                <FlaskConical className="w-4 h-4 text-[var(--accent-primary)]" />
                <span className={`font-medium ${isDark ? 'text-white' : 'text-slate-800'}`}>Investigations</span>
              </div>
              <div className="flex flex-wrap gap-1 pl-6">
                {acceptedInvestigations.map((item) => (
                  <Badge key={item.id} variant="outline" size="sm">
                    {item.name}
                  </Badge>
                ))}
              </div>
            </div>
          )}

          {/* Follow-up */}
          <div className={`p-3 rounded-xl ${isDark ? 'bg-blue-900/30' : 'bg-blue-50/50'}`}>
            <div className="flex items-center gap-2">
              <Calendar className={`w-4 h-4 ${isDark ? 'text-blue-400' : 'text-blue-600'}`} />
              <span className={`font-medium ${isDark ? 'text-blue-300' : 'text-blue-800'}`}>
                Follow-up: {nextReviewDate || carePlan.disposition.followUp}
              </span>
            </div>
          </div>
        </div>
      )}
    </GlassCard>
  );
}

// Main Output Section
export function OutputSection() {
  const { state, resetApp, goToStep } = useApp();
  const { isDark } = useTheme();
  const { patient, carePlan, diagnosis, nextReviewDate } = state;
  const [showPrintPreview, setShowPrintPreview] = useState(false);

  // Get the selected diagnoses from the differentials array (supports multiple selection)
  const selectedIds = diagnosis?.selectedDiagnosisIds?.length > 0
    ? diagnosis.selectedDiagnosisIds
    : [diagnosis?.differentials?.[0]?.id].filter(Boolean);
  const selectedDiagnoses = diagnosis?.differentials?.filter(
    (d) => selectedIds.includes(d.id)
  ) || [];

  const handleNewAssessment = () => {
    resetApp();
  };

  const handleViewChart = () => {
    goToStep(3);
  };

  const handleExportPDF = () => {
    generateCarePlanPDF({
      patient,
      diagnosis,
      carePlan,
    });
  };

  const handlePrint = () => {
    window.print();
  };

  return (
    <div className="space-y-6 animate-fadeIn">
      {/* Success Banner */}
      <GlassCard variant="success" className="p-6">
        <div className="flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className="p-4 bg-green-500/20 rounded-full">
              <CheckCircle className={`w-10 h-10 ${isDark ? 'text-green-400' : 'text-green-600'}`} />
            </div>
            <div>
              <h2 className={`text-2xl font-bold ${isDark ? 'text-green-300' : 'text-green-800'}`}>
                Care Plan Successfully Generated & Saved
              </h2>
              <p className={`mt-1 ${isDark ? 'text-green-200' : 'text-green-700'}`}>
                The evidence-based care plan has been saved to the patient's chart.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant="success" size="lg">
              Saved at {new Date().toLocaleTimeString()}
            </Badge>
          </div>
        </div>
      </GlassCard>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main Content */}
        <div className="lg:col-span-2 space-y-6">
          {/* Action Tools */}
          <GlassCard className="p-5">
            <h3 className={`text-lg font-semibold mb-4 ${isDark ? 'text-white' : 'text-slate-800'}`}>Quick Actions</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <Button
                variant="primary"
                size="md"
                icon={Download}
                onClick={handleExportPDF}
                className="w-full"
              >
                Export PDF
              </Button>
              <Button
                variant="secondary"
                size="md"
                icon={Printer}
                onClick={handlePrint}
                className="w-full"
              >
                Print
              </Button>
              <Button
                variant="secondary"
                size="md"
                icon={Eye}
                onClick={handleViewChart}
                className="w-full"
              >
                View Plan
              </Button>
              <Button
                variant="secondary"
                size="md"
                icon={Share2}
                onClick={() => { }}
                className="w-full"
              >
                Share
              </Button>
            </div>
          </GlassCard>

          {/* Diagnosis Summary */}
          <GlassCard className="p-5">
            <h3 className={`text-lg font-semibold mb-4 ${isDark ? 'text-white' : 'text-slate-800'}`}>
              Diagnosis Summary ({selectedDiagnoses.length})
            </h3>
            <div className="space-y-3">
              {selectedDiagnoses.map((diag, idx) => (
                <div key={diag.id} className={`p-4 rounded-xl ${isDark ? 'bg-white/10' : 'bg-white/50'}`}>
                  <div className="flex items-start justify-between">
                    <div>
                      <p className={`font-semibold ${isDark ? 'text-white' : 'text-slate-800'}`}>
                        {idx + 1}. {diag.name}
                      </p>
                      <p className={`text-sm mt-1 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                        ICD-11: {diag.icdCode}
                      </p>
                    </div>
                    <Badge
                      variant={diag.risk === 'high' ? 'danger' : diag.risk === 'medium' ? 'warning' : 'success'}
                      size="md"
                    >
                      {diag.risk?.charAt(0).toUpperCase() + diag.risk?.slice(1)} Risk
                    </Badge>
                  </div>
                </div>
              ))}
            </div>
          </GlassCard>

          {/* Key Recommendations */}
          <GlassCard className="p-5">
            <h3 className={`text-lg font-semibold mb-4 ${isDark ? 'text-white' : 'text-slate-800'}`}>Key Recommendations</h3>
            <div className="space-y-3">
              <div className={`p-4 rounded-xl border-l-4 border-red-500 ${isDark ? 'bg-red-900/30' : 'bg-red-50/80'}`}>
                <span className={`text-xs font-bold uppercase ${isDark ? 'text-red-400' : 'text-red-700'}`}>Stop Medication</span>
                <p className={`font-medium mt-1 ${isDark ? 'text-white' : 'text-slate-800'}`}>
                  Glipizide 5mg OD - Replacing with SGLT2i
                </p>
              </div>
              <div className={`p-4 rounded-xl border-l-4 border-green-500 ${isDark ? 'bg-green-900/30' : 'bg-green-50/80'}`}>
                <span className={`text-xs font-bold uppercase ${isDark ? 'text-green-400' : 'text-green-700'}`}>Start Medications</span>
                <p className={`font-medium mt-1 ${isDark ? 'text-white' : 'text-slate-800'}`}>
                  Empagliflozin 10mg OD, Lisinopril 5mg OD
                </p>
              </div>
              <div className={`p-4 rounded-xl border-l-4 border-blue-500 ${isDark ? 'bg-blue-900/30' : 'bg-blue-50/80'}`}>
                <span className={`text-xs font-bold uppercase ${isDark ? 'text-blue-400' : 'text-blue-700'}`}>Referral</span>
                <p className={`font-medium mt-1 ${isDark ? 'text-white' : 'text-slate-800'}`}>
                  Ophthalmology for diabetic retinopathy screening
                </p>
              </div>
            </div>
          </GlassCard>
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          <PlanSummary carePlan={carePlan} patient={patient} nextReviewDate={nextReviewDate} />

          {/* New Assessment Button */}
          <Button
            variant="outline"
            size="lg"
            icon={RefreshCw}
            onClick={handleNewAssessment}
            className="w-full"
          >
            Start New Assessment
          </Button>
        </div>
      </div>
    </div>
  );
}
