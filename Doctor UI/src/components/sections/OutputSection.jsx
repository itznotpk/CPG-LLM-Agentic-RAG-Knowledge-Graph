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
  const { patient, carePlan, diagnosis, nextReviewDate, clinicalNotes, vitals } = state;

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
    <div className="space-y-6 animate-fadeIn pb-8 relative">
      {/* Success Banner */}
      <GlassCard variant="success" className="p-6 max-w-5xl mx-auto">
        <div className="flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className="p-4 bg-green-500/20 rounded-full">
              <CheckCircle className={`w-10 h-10 ${isDark ? 'text-green-400' : 'text-green-600'}`} />
            </div>
            <div>
              <h2 className={`text-2xl font-bold ${isDark ? 'text-green-300' : 'text-green-800'}`}>
                Care Plan Successfully Generated
              </h2>
              <p className={`mt-1 ${isDark ? 'text-green-200' : 'text-green-700'}`}>
                Review the clinical encounter note below before signing.
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

      {/* SOAP NOTE VIEW */}
      <GlassCard className="p-8 max-w-5xl mx-auto border-t-8 border-t-[var(--accent-primary)] shadow-lg bg-white dark:bg-slate-900">
        <h3 className={`text-2xl font-bold mb-6 text-center border-b pb-4 ${isDark ? 'text-white border-white/10' : 'text-slate-800 border-slate-200'}`}>
          Clinical Encounter Note
        </h3>
         
        <div className="space-y-8">
          {/* Subjective */}
          <section>
            <h4 className={`text-base font-semibold mb-3 flex items-center gap-2 ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>
              <User className="w-4 h-4" /> Subjective
            </h4>
            <p className={`whitespace-pre-wrap pl-6 border-l-2 ${isDark ? 'border-slate-700 text-slate-300' : 'border-slate-200 text-slate-700'}`}>
              {clinicalNotes || 'No clinical notes provided.'}
            </p>
          </section>

          {/* Objective */}
          <section>
            <h4 className={`text-base font-semibold mb-3 flex items-center gap-2 ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>
              <Activity className="w-4 h-4" /> Objective (Vitals)
            </h4>
            <div className={`grid grid-cols-2 md:grid-cols-4 gap-4 p-4 rounded-xl ml-6 ${isDark ? 'bg-slate-800/50' : 'bg-slate-50'}`}>
              <div><span className="text-xs text-slate-500 block mb-1">Blood Pressure</span> <span className="font-medium font-variant-numeric: tabular-nums">{vitals?.bpSystolic}/{vitals?.bpDiastolic} mmHg</span></div>
              <div><span className="text-xs text-slate-500 block mb-1">Heart Rate</span> <span className="font-medium font-variant-numeric: tabular-nums">{vitals?.hr} bpm</span></div>
              <div><span className="text-xs text-slate-500 block mb-1">Temperature</span> <span className="font-medium font-variant-numeric: tabular-nums">{vitals?.temp} °C</span></div>
              <div><span className="text-xs text-slate-500 block mb-1">SpO2</span> <span className="font-medium font-variant-numeric: tabular-nums">{vitals?.spo2} %</span></div>
              <div><span className="text-xs text-slate-500 block mb-1">Weight</span> <span className="font-medium font-variant-numeric: tabular-nums">{vitals?.weight} kg</span></div>
              <div><span className="text-xs text-slate-500 block mb-1">Height</span> <span className="font-medium font-variant-numeric: tabular-nums">{vitals?.height} cm</span></div>
            </div>
          </section>

          {/* Assessment */}
          <section>
            <h4 className={`text-base font-semibold mb-3 flex items-center gap-2 ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>
              <Stethoscope className="w-4 h-4" /> Assessment
            </h4>
            <div className="ml-6 space-y-2">
              {selectedDiagnoses.map(d => (
                <div key={d.id} className={`p-3 rounded-lg border ${isDark ? 'border-slate-700 bg-slate-800/30' : 'border-slate-200 bg-white'}`}>
                  <span className={`font-semibold ${isDark ? 'text-white' : 'text-slate-800'}`}>{d.name}</span>
                  {d.icdCode && <span className="text-xs bg-[var(--accent-primary)]/10 text-[var(--accent-primary)] px-2 py-0.5 rounded ml-3">ICD-11: {d.icdCode}</span>}
                </div>
              ))}
              {selectedDiagnoses.length === 0 && <p className="text-slate-500">No diagnoses selected.</p>}
              {/* CPG Evidence source */}
              {carePlan?.cpgReferences?.length > 0 && (
                <div className={`mt-2 p-2.5 rounded-lg text-xs flex items-start gap-2 ${isDark ? 'bg-indigo-900/20 text-indigo-300 border border-indigo-500/20' : 'bg-indigo-50 text-indigo-700 border border-indigo-100'}`}>
                  <span className="font-semibold shrink-0">CPG Evidence:</span>
                  <span>{carePlan.cpgReferences.map(r => r.title || r).join(' · ')}</span>
                </div>
              )}
            </div>
          </section>

          {/* Plan */}
          <section>
            <h4 className={`text-base font-semibold mb-3 flex items-center gap-2 ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>
              <ClipboardList className="w-4 h-4" /> Plan
            </h4>
            <div className={`ml-6 space-y-4 ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
              <p className="leading-relaxed">{carePlan?.clinicalSummary}</p>
              
              {carePlan?.medications?.start?.length > 0 && (
                <div className={`p-3 rounded-lg border-l-4 border-green-500 ${isDark ? 'bg-green-900/10' : 'bg-green-50'}`}>
                  <strong className={`text-sm block mb-2 ${isDark ? 'text-green-400' : 'text-green-700'}`}>Start Medications:</strong>
                  <ul className="list-disc pl-5 space-y-1">
                    {carePlan.medications.start.filter(m => m.accepted !== false).map(m => <li key={m.id}><span className="font-medium">{m.name} {m.dose}</span> — {m.reason}</li>)}
                  </ul>
                </div>
              )}
              {carePlan?.medications?.stop?.length > 0 && (
                <div className={`p-3 rounded-lg border-l-4 border-red-500 ${isDark ? 'bg-red-900/10' : 'bg-red-50'}`}>
                  <strong className={`text-sm block mb-2 ${isDark ? 'text-red-400' : 'text-red-700'}`}>Stop Medications:</strong>
                  <ul className="list-disc pl-5 space-y-1">
                    {carePlan.medications.stop.filter(m => m.accepted !== false).map(m => <li key={m.id}><span className="font-medium">{m.name}</span> — {m.reason}</li>)}
                  </ul>
                </div>
              )}
              {carePlan?.investigations?.filter(i => i.accepted !== false)?.length > 0 && (
                <div className={`p-3 rounded-lg border-l-4 border-blue-400 ${isDark ? 'bg-blue-900/10' : 'bg-blue-50'}`}>
                  <strong className={`text-sm block mb-2 ${isDark ? 'text-blue-400' : 'text-blue-700'}`}>Investigations:</strong>
                  <ul className="list-disc pl-5 space-y-1">
                    {carePlan.investigations.filter(i => i.accepted !== false).map(i => <li key={i.id}>{i.name}</li>)}
                  </ul>
                </div>
              )}
              <div className={`p-3 rounded-lg border ${isDark ? 'border-slate-700' : 'border-slate-200'}`}>
                <strong className="text-sm font-medium">Follow-up:</strong>
                <span className="ml-2">{nextReviewDate || carePlan?.disposition?.followUp || 'As needed'}</span>
              </div>
              {carePlan?.unresolvedQuestions?.length > 0 && (
                <div className={`p-3 rounded-lg border ${isDark ? 'border-amber-500/30 bg-amber-900/10' : 'border-amber-200 bg-amber-50'}`}>
                  <strong className={`text-sm block mb-2 ${isDark ? 'text-amber-400' : 'text-amber-700'}`}>⚠ Unresolved:</strong>
                  <ul className={`list-disc pl-5 space-y-1 text-sm ${isDark ? 'text-amber-300/80' : 'text-amber-800'}`}>
                    {carePlan.unresolvedQuestions.map((q, i) => <li key={i}>{q}</li>)}
                  </ul>
                </div>
              )}
            </div>
          </section>
        </div>
      </GlassCard>

      {/* Floating Action Bar */}
      <div className="sticky bottom-4 mx-auto max-w-5xl mt-8">
        <GlassCard className="p-4 shadow-xl border border-[var(--accent-primary)]/20 flex flex-wrap justify-center gap-4 bg-white/90 dark:bg-slate-900/90 backdrop-blur-xl">
          <Button variant="outline" size="lg" icon={Download} onClick={handleExportPDF}>
            Export to EMR
          </Button>
          <Button variant="secondary" size="lg" icon={Printer} onClick={handlePrint}>
            Print Instructions
          </Button>
          <Button variant="primary" size="lg" icon={CheckCircle} onClick={handleNewAssessment} className="min-w-[200px]">
            Sign Note & Close
          </Button>
        </GlassCard>
      </div>
    </div>
  );
}
