import React, { useState } from 'react';
import { getTodayUTC8 } from '../../utils/timezone';
import {
  ClipboardList,
  Stethoscope,
  Pill,
  Activity,
  Calendar,
  BookOpen,
  Check,
  ChevronDown,
  ChevronUp,
  FileText,
  AlertCircle,
  Plus,
  Minus,
  ArrowRight,
  ArrowLeft,
  Shield,
  Heart,
} from 'lucide-react';
import {
  GlassCard,
  Button,
  Badge,
  WorkflowActions,
  WORKFLOW_STATES,
  TextToSpeechButton,
} from '../shared';
import { useApp } from '../../context/AppContext';
import { useTheme } from '../../context/ThemeContext';


// Accordion Section Component
function AccordionSection({ title, icon: Icon, children, defaultOpen = true, rightAction }) {
  const [isOpen, setIsOpen] = useState(defaultOpen);
  const { isDark } = useTheme();

  return (
    <GlassCard className="overflow-hidden">
      <div className={`flex items-center justify-between p-4 ${isDark ? 'hover:bg-white/5' : 'hover:bg-white/10'}`}>
        <button
          onClick={() => setIsOpen(!isOpen)}
          className="flex items-center gap-3 flex-1"
        >
          <div className="p-2 bg-[var(--accent-primary)]/20 rounded-xl">
            <Icon className="w-5 h-5 text-[var(--accent-primary)]" />
          </div>
          <h3 className={`text-lg font-semibold ${isDark ? 'text-white' : 'text-slate-800'}`}>{title}</h3>
        </button>
        <div className="flex items-center gap-2">
          {rightAction}
          <button onClick={() => setIsOpen(!isOpen)}>
            {isOpen ? (
              <ChevronUp className={`w-5 h-5 ${isDark ? 'text-slate-400' : 'text-slate-600'}`} />
            ) : (
              <ChevronDown className={`w-5 h-5 ${isDark ? 'text-slate-400' : 'text-slate-600'}`} />
            )}
          </button>
        </div>
      </div>
      {isOpen && <div className="px-4 pb-4">{children}</div>}
    </GlassCard>
  );
}

// Clinical Summary Section
function ClinicalSummary({ summary, readSummaryButton }) {
  const { isDark } = useTheme();

  return (
    <AccordionSection title="Summary" icon={FileText} rightAction={readSummaryButton}>
      <div className={`p-4 rounded-xl ${isDark ? 'bg-white/10' : 'bg-white/50'}`}>
        <p className={`leading-relaxed ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>{summary}</p>
      </div>
    </AccordionSection>
  );
}

// Interventions Section (Simplified)
function InterventionsSection({ interventions }) {
  const { isDark } = useTheme();

  if (!interventions || interventions.length === 0) return null;

  return (
    <AccordionSection title="Interventions & Procedures" icon={Stethoscope}>
      <div className="space-y-2">
        {interventions.map((item) => (
          <div
            key={item.id}
            className={`flex items-start gap-3 p-3 rounded-lg ${isDark ? 'bg-white/5' : 'bg-white/40'}`}
          >
            <Check className={`w-4 h-4 mt-0.5 flex-shrink-0 ${isDark ? 'text-green-400' : 'text-green-600'}`} />
            <div className="flex-1">
              <div className="flex items-center gap-2 flex-wrap">
                <span className={`font-medium ${isDark ? 'text-white' : 'text-slate-800'}`}>{item.name}</span>
                <Badge variant="info" size="sm">{item.urgency}</Badge>
              </div>
              <p className={`text-sm mt-1 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>{item.rationale}</p>
            </div>
          </div>
        ))}
      </div>
    </AccordionSection>
  );
}

// Medications Section (Simplified with CHANGE category)
function MedicationsSection({ medications }) {
  const { isDark } = useTheme();

  return (
    <AccordionSection title="Medication Recommendations" icon={Pill}>
      <div className="space-y-4">
        {/* STOP Medications */}
        {medications.stop && medications.stop.length > 0 && (
          <div>
            <div className="flex items-center gap-2 mb-2">
              <div className={`p-1 rounded ${isDark ? 'bg-red-500/20' : 'bg-red-100'}`}>
                <Minus className={`w-4 h-4 ${isDark ? 'text-red-400' : 'text-red-600'}`} />
              </div>
              <span className={`font-semibold text-sm uppercase ${isDark ? 'text-red-400' : 'text-red-700'}`}>Stop</span>
            </div>
            <div className="space-y-2">
              {medications.stop.map((med) => (
                <div key={med.id} className={`p-3 rounded-lg border-l-4 border-red-500 ${isDark ? 'bg-red-900/20' : 'bg-red-50'}`}>
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className={`font-medium ${isDark ? 'text-white' : 'text-slate-800'}`}>{med.name}</span>
                    <span className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>{med.dose}</span>
                  </div>
                  <p className={`text-sm mt-1 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>{med.reason}</p>
                  {med.cpgRef && <p className={`text-xs mt-1 italic ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>[{med.cpgRef}]</p>}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* START Medications */}
        {medications.start && medications.start.length > 0 && (
          <div>
            <div className="flex items-center gap-2 mb-2">
              <div className={`p-1 rounded ${isDark ? 'bg-green-500/20' : 'bg-green-100'}`}>
                <Plus className={`w-4 h-4 ${isDark ? 'text-green-400' : 'text-green-600'}`} />
              </div>
              <span className={`font-semibold text-sm uppercase ${isDark ? 'text-green-400' : 'text-green-700'}`}>Start</span>
            </div>
            <div className="space-y-2">
              {medications.start.map((med) => (
                <div key={med.id} className={`p-3 rounded-lg border-l-4 border-green-500 ${isDark ? 'bg-green-900/20' : 'bg-green-50'}`}>
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className={`font-medium ${isDark ? 'text-white' : 'text-slate-800'}`}>{med.name}</span>
                    <span className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>{med.dose}</span>
                  </div>
                  <p className={`text-sm mt-1 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>{med.reason}</p>
                  {med.instructions && (
                    <p className={`text-xs mt-1 flex items-center gap-1 ${isDark ? 'text-amber-400' : 'text-amber-700'}`}>
                      <AlertCircle className="w-3 h-3" />
                      {med.instructions}
                    </p>
                  )}
                  {med.cpgRef && <p className={`text-xs mt-1 italic ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>[{med.cpgRef}]</p>}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* CHANGE Medications */}
        {medications.change && medications.change.length > 0 && (
          <div>
            <div className="flex items-center gap-2 mb-2">
              <div className={`p-1 rounded ${isDark ? 'bg-amber-500/20' : 'bg-amber-100'}`}>
                <ArrowRight className={`w-4 h-4 ${isDark ? 'text-amber-400' : 'text-amber-600'}`} />
              </div>
              <span className={`font-semibold text-sm uppercase ${isDark ? 'text-amber-400' : 'text-amber-700'}`}>Change</span>
            </div>
            <div className="space-y-2">
              {medications.change.map((med) => (
                <div key={med.id} className={`p-3 rounded-lg border-l-4 border-amber-500 ${isDark ? 'bg-amber-900/20' : 'bg-amber-50'}`}>
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className={`font-medium ${isDark ? 'text-white' : 'text-slate-800'}`}>{med.name}</span>
                    <span className={`text-sm line-through ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>{med.previousDose}</span>
                    <ArrowRight className={`w-3 h-3 ${isDark ? 'text-slate-400' : 'text-slate-500'}`} />
                    <span className={`text-sm font-medium ${isDark ? 'text-amber-400' : 'text-amber-700'}`}>{med.newDose}</span>
                  </div>
                  <p className={`text-sm mt-1 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>{med.reason}</p>
                  {med.kiv && (
                    <p className={`text-xs mt-1 flex items-center gap-1 ${isDark ? 'text-blue-400' : 'text-blue-700'}`}>
                      <AlertCircle className="w-3 h-3" />
                      {med.kiv}
                    </p>
                  )}
                  {med.cpgRef && <p className={`text-xs mt-1 italic ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>[{med.cpgRef}]</p>}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* CONTINUE Medications */}
        {medications.continue && medications.continue.length > 0 && (
          <div>
            <div className="flex items-center gap-2 mb-2">
              <div className={`p-1 rounded ${isDark ? 'bg-blue-500/20' : 'bg-blue-100'}`}>
                <Check className={`w-4 h-4 ${isDark ? 'text-blue-400' : 'text-blue-600'}`} />
              </div>
              <span className={`font-semibold text-sm uppercase ${isDark ? 'text-blue-400' : 'text-blue-700'}`}>Continue</span>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
              {medications.continue.map((med) => (
                <div key={med.id} className={`p-3 rounded-lg border-l-4 border-blue-400 ${isDark ? 'bg-blue-900/20' : 'bg-blue-50'}`}>
                  <div className="flex items-center justify-between">
                    <div>
                      <span className={`font-medium ${isDark ? 'text-white' : 'text-slate-800'}`}>{med.name}</span>
                      <span className={`text-sm ml-2 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>{med.dose}</span>
                    </div>
                    <Check className={`w-4 h-4 ${isDark ? 'text-blue-400' : 'text-blue-600'}`} />
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </AccordionSection>
  );
}

// Monitoring Section (Simplified with schedules)
function MonitoringSection({ monitoring }) {
  const { isDark } = useTheme();

  if (!monitoring || monitoring.length === 0) return null;

  return (
    <AccordionSection title="Monitoring & Testing" icon={Activity}>
      <div className="space-y-2">
        {monitoring.map((item) => (
          <div
            key={item.id}
            className={`flex items-center justify-between p-3 rounded-lg ${isDark ? 'bg-white/5' : 'bg-white/40'}`}
          >
            <div className="flex items-center gap-3">
              <Check className={`w-4 h-4 flex-shrink-0 ${isDark ? 'text-green-400' : 'text-green-600'}`} />
              <span className={`${isDark ? 'text-slate-200' : 'text-slate-700'}`}>{item.task}</span>
            </div>
            {item.schedule && (
              <Badge variant="info" size="sm">{item.schedule}</Badge>
            )}
          </div>
        ))}
      </div>
    </AccordionSection>
  );
}

// Follow-Up Section with Patient Status and TCA Date Picker
function FollowUpSection({ followUp }) {
  const { isDark } = useTheme();
  const { state, dispatch } = useApp();
  const currentStatus = state.patientStatus || 'active';
  const nextReviewDate = state.nextReviewDate || '';

  if (!followUp) return null;

  const statusOptions = [
    { value: 'active', label: 'Active', color: 'emerald', icon: Check },
    { value: 'follow-up', label: 'Follow-up', color: 'amber', icon: Calendar },
    { value: 'discharged', label: 'Discharged', color: 'slate', icon: Shield },
  ];

  const handleStatusChange = (status) => {
    dispatch({ type: 'SET_PATIENT_STATUS', payload: status });
  };

  const handleTCAChange = (date) => {
    dispatch({ type: 'SET_NEXT_REVIEW_DATE', payload: date });
  };

  return (
    <AccordionSection title="Follow-up" icon={Calendar}>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Next Review Date (TCA) Picker */}
        <div className={`p-4 rounded-xl ${isDark ? 'bg-[var(--accent-primary)]/20' : 'bg-[var(--accent-primary)]/10'}`}>
          <div className="flex items-center gap-2 mb-3">
            <Calendar className="w-5 h-5 text-[var(--accent-primary)]" />
            <span className={`font-semibold ${isDark ? 'text-white' : 'text-slate-800'}`}>Next Review Date (TCA)</span>
          </div>
          <input
            type="date"
            value={nextReviewDate}
            onChange={(e) => handleTCAChange(e.target.value)}
            min={getTodayUTC8()}
            className={`w-full px-4 py-2.5 rounded-xl border transition-all
              focus:outline-none focus:ring-2 focus:ring-[var(--accent-primary)]/50
              ${isDark
                ? 'bg-white/10 border-white/20 text-white'
                : 'bg-white border-slate-200 text-slate-800'}`}
          />
          <p className={`text-xs mt-2 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
            Set the patient's next follow-up appointment
          </p>
        </div>

        {/* Patient Status Selection */}
        <div className={`p-4 rounded-xl ${isDark ? 'bg-white/5' : 'bg-slate-50'}`}>
          <div className="flex items-center gap-2 mb-3">
            <Shield className="w-5 h-5 text-[var(--accent-primary)]" />
            <span className={`font-semibold ${isDark ? 'text-white' : 'text-slate-800'}`}>Patient Status</span>
          </div>
          <div className="flex flex-wrap gap-2">
            {statusOptions.map((option) => {
              const isSelected = currentStatus === option.value;
              const Icon = option.icon;
              const colorClasses = {
                emerald: isSelected
                  ? 'bg-emerald-500 text-white border-emerald-500'
                  : `${isDark ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30 hover:bg-emerald-500/30' : 'bg-emerald-100 text-emerald-700 border-emerald-300 hover:bg-emerald-200'}`,
                amber: isSelected
                  ? 'bg-amber-500 text-white border-amber-500'
                  : `${isDark ? 'bg-amber-500/20 text-amber-400 border-amber-500/30 hover:bg-amber-500/30' : 'bg-amber-100 text-amber-700 border-amber-300 hover:bg-amber-200'}`,
                slate: isSelected
                  ? 'bg-slate-500 text-white border-slate-500'
                  : `${isDark ? 'bg-slate-500/20 text-slate-400 border-slate-500/30 hover:bg-slate-500/30' : 'bg-slate-200 text-slate-700 border-slate-300 hover:bg-slate-300'}`,
              };
              return (
                <button
                  key={option.value}
                  onClick={() => handleStatusChange(option.value)}
                  className={`flex items-center gap-2 px-4 py-2 rounded-lg border font-medium transition-all ${colorClasses[option.color]}`}
                >
                  <Icon className="w-4 h-4" />
                  {option.label}
                </button>
              );
            })}
          </div>
          <p className={`text-xs mt-2 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
            Status and TCA will be synced when care plan is finalized
          </p>
        </div>
      </div>
    </AccordionSection>
  );
}

// Referrals Section
function ReferralsSection({ referrals }) {
  const { isDark } = useTheme();

  if (!referrals || referrals.length === 0) return null;

  return (
    <AccordionSection title="Referrals" icon={ClipboardList}>
      <div className="space-y-2">
        {referrals.map((ref, idx) => (
          <div key={idx} className={`p-3 rounded-xl ${isDark ? 'bg-white/10' : 'bg-white/30'}`}>
            <div className="flex items-center justify-between">
              <span className={`font-semibold ${isDark ? 'text-white' : 'text-slate-800'}`}>{ref.specialty}</span>
              <Badge variant="info" size="sm">{ref.urgency}</Badge>
            </div>
            <p className={`text-sm mt-1 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>{ref.reason}</p>
          </div>
        ))}
      </div>
    </AccordionSection>
  );
}

// Patient Education Section (Enhanced with categories)
function PatientEducationSection({ education }) {
  const { isDark } = useTheme();

  if (!education || education.length === 0) return null;

  // Handle both old string format and new object format
  const items = education.map((item, idx) => {
    if (typeof item === 'string') {
      return { text: item, category: 'General' };
    }
    return item;
  });

  return (
    <AccordionSection title="Patient Education & Counseling" icon={BookOpen}>
      <div className="space-y-2">
        {items.map((item, idx) => (
          <div
            key={idx}
            className={`flex items-start gap-3 p-3 rounded-lg ${isDark ? 'bg-white/5' : 'bg-white/40'}`}
          >
            <Check className={`w-4 h-4 mt-0.5 flex-shrink-0 ${isDark ? 'text-green-400' : 'text-green-600'}`} />
            <div className="flex-1">
              <span className={`text-sm ${isDark ? 'text-slate-200' : 'text-slate-700'}`}>{item.text}</span>
              {item.category && (
                <Badge variant="info" size="sm" className="ml-2">{item.category}</Badge>
              )}
            </div>
          </div>
        ))}
      </div>
    </AccordionSection>
  );
}

// Lifestyle & Self-Management Section (NEW)
function LifestyleSection({ lifestyle }) {
  const { isDark } = useTheme();

  if (!lifestyle || lifestyle.length === 0) return null;

  const categoryIcons = {
    Exercise: Activity,
    Diet: Pill,
    Weight: Activity,
    Lifestyle: BookOpen,
  };

  return (
    <AccordionSection title="Lifestyle & Self-Management Goals" icon={Activity}>
      <div className="space-y-2">
        {lifestyle.map((item) => {
          const CategoryIcon = categoryIcons[item.category] || Check;
          return (
            <div
              key={item.id}
              className={`flex items-start gap-3 p-3 rounded-lg ${isDark ? 'bg-white/5' : 'bg-white/40'}`}
            >
              <div className={`p-1 rounded ${isDark ? 'bg-emerald-500/20' : 'bg-emerald-100'}`}>
                <CategoryIcon className={`w-4 h-4 ${isDark ? 'text-emerald-400' : 'text-emerald-600'}`} />
              </div>
              <div className="flex-1">
                <span className={`text-sm ${isDark ? 'text-slate-200' : 'text-slate-700'}`}>{item.goal}</span>
                <Badge variant="success" size="sm" className="ml-2">{item.category}</Badge>
              </div>
            </div>
          );
        })}
      </div>
    </AccordionSection>
  );
}

// CPG References Section
function CPGReferencesSection({ references }) {
  const { isDark } = useTheme();

  return (
    <AccordionSection title="CPG References" icon={BookOpen} defaultOpen={false}>
      <div className="flex flex-wrap gap-2">
        {references.map((ref, idx) => (
          <button
            key={idx}
            className={`px-3 py-2 rounded-xl text-sm transition-colors text-left ${isDark
              ? 'bg-[var(--accent-primary)]/20 hover:bg-[var(--accent-primary)]/30 text-slate-200'
              : 'bg-[var(--accent-primary)]/10 hover:bg-[var(--accent-primary)]/20 text-slate-700'
              }`}
          >
            <span className={`font-medium ${isDark ? 'text-white' : 'text-slate-800'}`}>{ref.title}</span>
            <span className={`ml-1 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
              ({ref.edition}, Pg {ref.page})
            </span>
          </button>
        ))}
      </div>
    </AccordionSection>
  );
}

// Main Care Plan Section
export function CarePlanSection() {
  const { state, updateCarePlanItem, updateMedication, finalizePlan, goToStep } = useApp();
  const { isDark, accent } = useTheme();
  const { carePlan, patientData, diagnosis } = state;

  // Get selected diagnoses (supports multiple selection)
  const selectedIds = diagnosis?.selectedDiagnosisIds?.length > 0
    ? diagnosis.selectedDiagnosisIds
    : [diagnosis?.differentials?.[0]?.id].filter(Boolean);
  const selectedDiagnoses = diagnosis?.differentials?.filter(
    (d) => selectedIds.includes(d.id)
  ) || [];

  // Local state for workflow and notes
  const [workflowStatus, setWorkflowStatus] = useState(WORKFLOW_STATES.DRAFT);
  const [workflowHistory, setWorkflowHistory] = useState([]);
  const [notes, setNotes] = useState([]);

  if (!carePlan) return null;

  const handleBack = () => {
    goToStep(2);
  };

  const handleStatusChange = (newStatus, comment) => {
    setWorkflowStatus(newStatus);
    setWorkflowHistory(prev => [
      {
        status: newStatus,
        action: newStatus === WORKFLOW_STATES.REVIEWED ? 'Marked as Reviewed' : 'Approved',
        user: 'Dr. Current User',
        timestamp: new Date().toLocaleString(),
        comment
      },
      ...prev
    ]);
  };

  const handleReject = (comment) => {
    setWorkflowStatus(WORKFLOW_STATES.DRAFT);
    setWorkflowHistory(prev => [
      {
        status: WORKFLOW_STATES.DRAFT,
        action: 'Sent back for revision',
        user: 'Dr. Current User',
        timestamp: new Date().toLocaleString(),
        comment
      },
      ...prev
    ]);
  };

  const handleRegenerate = async (feedback) => {
    // Mock regeneration - in production this would call the AI backend
    console.log('Regenerating with feedback:', feedback);
    // Simulate API delay
    await new Promise(resolve => setTimeout(resolve, 1500));
    // In production, this would update the carePlan with new recommendations
  };

  const handleFeedback = (itemId, feedbackType) => {
    console.log('Feedback for item:', itemId, feedbackType);
    // In production, this would send feedback to the RAG system
  };

  // Generate summary text for TTS
  const generateCarePlanSummary = () => {
    let summary = `Care Plan for ${patientData?.patientName || 'Patient'}. `;
    const diagnosisNames = selectedDiagnoses.map(d => d.name).join(', ') || 'Not specified';
    summary += `${selectedDiagnoses.length > 1 ? 'Diagnoses' : 'Primary Diagnosis'}: ${diagnosisNames}. `;
    summary += `Clinical Summary: ${carePlan.clinicalSummary}. `;

    if (carePlan.medications.start.length > 0) {
      summary += `New Medications to Start: ${carePlan.medications.start.map(m => m.name).join(', ')}. `;
    }
    if (carePlan.medications.stop.length > 0) {
      summary += `Medications to Stop: ${carePlan.medications.stop.map(m => m.name).join(', ')}. `;
    }

    summary += `Follow-up: ${carePlan.disposition.followUp}.`;
    return summary;
  };

  return (
    <div className="space-y-4 animate-fadeIn">
      <div className="text-center mb-6">
        <h2 className={`text-2xl font-bold mb-2 ${isDark ? 'text-white' : 'text-slate-800'}`}>
          Recommended Care Plan
        </h2>
      </div>

      {/* Summary */}
      <ClinicalSummary
        summary={carePlan.clinicalSummary}
        readSummaryButton={
          <TextToSpeechButton
            text={generateCarePlanSummary()}
            label="Read"
          />
        }
      />



      {/* Medication Recommendations - Stop/Start/Change/Continue */}
      <MedicationsSection medications={carePlan.medications} />

      {/* Interventions & Procedures */}
      <InterventionsSection interventions={carePlan.interventions} />

      {/* Monitoring & Testing */}
      <MonitoringSection monitoring={carePlan.monitoring} />

      {/* Patient Education & Counseling */}
      <PatientEducationSection education={carePlan.disposition?.patientEducation} />

      {/* Referrals */}
      <ReferralsSection referrals={carePlan.disposition?.referrals} />

      {/* Lifestyle & Self-Management Goals */}
      <LifestyleSection lifestyle={carePlan.lifestyle} />

      {/* Follow-up */}
      <FollowUpSection followUp={carePlan.disposition?.followUp} />

      {/* CPG References */}
      <CPGReferencesSection references={carePlan.cpgReferences} />

      {/* Approval Workflow */}
      <div className="mt-6">
        <WorkflowActions
          currentStatus={workflowStatus}
          onStatusChange={handleStatusChange}
          onReject={handleReject}
          onRegenerate={handleRegenerate}
          history={workflowHistory}
        />
      </div>

      {/* Action Buttons */}
      <div className="flex flex-col sm:flex-row items-center justify-center gap-4 pt-6">
        <Button
          variant="secondary"
          size="lg"
          icon={ArrowLeft}
          onClick={handleBack}
        >
          Back
        </Button>
        <Button
          variant="primary"
          size="lg"
          icon={Check}
          onClick={finalizePlan}
          disabled={workflowStatus !== WORKFLOW_STATES.APPROVED}
          glow={workflowStatus === WORKFLOW_STATES.APPROVED}
          className="min-w-[250px]"
        >
          {workflowStatus === WORKFLOW_STATES.APPROVED
            ? 'Generate Report'
            : 'Approval Required'}
        </Button>
      </div>

      {workflowStatus !== WORKFLOW_STATES.APPROVED && (
        <p className="text-center text-sm text-slate-500">
          Approve the care plan above to generate report
        </p>
      )}
    </div>
  );
}
