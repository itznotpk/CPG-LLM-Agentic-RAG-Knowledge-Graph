import React from 'react';
import { FileText, CheckCircle2, Edit3, Zap } from 'lucide-react';
import { GlassCard, TextArea, Button, VoiceInputButton, VoiceStatusIndicator } from '../shared';
import { useApp } from '../../context/AppContext';
import { useTheme } from '../../context/ThemeContext';

export function ClinicalNotes({ isConfirmed, onConfirm }) {
  const { state, dispatch } = useApp();
  const { isDark } = useTheme();
  const { clinicalNotes, patient } = state;
  const [isListening, setIsListening] = React.useState(false);

  const handleChange = (value) => {
    dispatch({ type: 'SET_CLINICAL_NOTES', payload: value });
    // If notes change after confirmation, reset confirmation
    if (isConfirmed && onConfirm) {
      onConfirm(false);
    }
  };

  const handleVoiceTranscript = (transcript) => {
    // Append the transcript to existing notes
    const newValue = clinicalNotes
      ? clinicalNotes + ' ' + transcript
      : transcript;
    handleChange(newValue);
  };

  const handleConfirm = () => {
    // Just confirm the notes locally - actual save happens when "Analyze Clinical Assessment" is pressed
    // This creates a new consultation row in the database with the clinical notes
    if (onConfirm) onConfirm(true);
  };

  const handleEdit = () => {
    if (onConfirm) onConfirm(false);
  };

  const handleDemoFill = () => {
    const demoNotes = `Chest pain and tends to vomit`;
    handleChange(demoNotes);
  };

  return (
    <GlassCard className={`p-5 ${isConfirmed ? 'border-2 border-green-500/30' : ''}`}>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className={`p-2 rounded-xl ${isConfirmed ? 'bg-green-500/20' : 'bg-[var(--accent-primary)]/20'}`}>
            {isConfirmed
              ? <CheckCircle2 className="w-5 h-5 text-green-500" />
              : <FileText className="w-5 h-5 text-[var(--accent-primary)]" />
            }
          </div>
          <div>
            <h3 className={`text-lg font-semibold ${isDark ? 'text-white' : 'text-slate-800'}`}>Clinical Notes</h3>
            {isConfirmed && (
              <p className="text-xs text-green-500">Notes confirmed ✓</p>
            )}
          </div>
          <VoiceStatusIndicator isListening={isListening} />
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleDemoFill}
            disabled={isConfirmed}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-all
              ${isConfirmed
                ? 'opacity-50 cursor-not-allowed'
                : isDark
                  ? 'bg-amber-500/20 text-amber-400 hover:bg-amber-500/30'
                  : 'bg-amber-100 text-amber-700 hover:bg-amber-200'
              }`}
            title="Fill with demo data"
          >
            <Zap className="w-4 h-4" />
            Demo Fill
          </button>
          <VoiceInputButton
            onTranscript={handleVoiceTranscript}
          />
        </div>
      </div>

      <TextArea
        id="clinical-notes"
        label="History & Physical Examination"
        rows={6}
        placeholder="Enter clinical history, presenting complaints, physical examination findings... or use voice input"
        value={clinicalNotes}
        onChange={(e) => handleChange(e.target.value)}
        helper="Include relevant symptoms, duration, and examination findings. Voice dictation supported."
        disabled={isConfirmed}
      />

      {/* Confirm/Edit Button */}
      <div className="mt-4 flex justify-end">
        {isConfirmed ? (
          <Button
            variant="secondary"
            size="sm"
            icon={Edit3}
            onClick={handleEdit}
          >
            Edit Notes
          </Button>
        ) : (
          <Button
            variant="success"
            size="md"
            icon={CheckCircle2}
            onClick={handleConfirm}
            disabled={!clinicalNotes?.trim()}
          >
            Confirm Clinical Notes
          </Button>
        )}
      </div>
    </GlassCard>
  );
}
