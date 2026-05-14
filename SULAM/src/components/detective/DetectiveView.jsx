import { useState, useCallback } from 'react';
import { SAMPLE_CASES } from '../../data/sampleCases.js';
import { streamDetectivePlan } from '../../lib/detectiveApi.js';
import { mapDdxToDiagnosis, mapTreatmentPlanToCarePlan } from '../../lib/mappers.js';
import CaseCard from './CaseCard.jsx';
import Pipeline from './Pipeline.jsx';

const INITIAL_STEPS = { 2: null, 3: null, 4: null, 5: null };

export default function DetectiveView() {
  const [selectedCaseId, setSelectedCaseId]   = useState(null);
  const [steps, setSteps]                      = useState(INITIAL_STEPS);
  const [thinkingText, setThinkingText]        = useState('');
  const [diagnosis, setDiagnosis]              = useState(null);
  const [carePlan, setCarePlan]                = useState(null);
  const [error, setError]                      = useState(null);
  const [isStreaming, setIsStreaming]           = useState(false);

  const runCase = useCallback(async (caseData) => {
    setSelectedCaseId(caseData.id);
    setSteps(INITIAL_STEPS);
    setThinkingText('');
    setDiagnosis(null);
    setCarePlan(null);
    setError(null);
    setIsStreaming(true);

    try {
      const result = await streamDetectivePlan(
        caseData.caseBody,
        (stageUpdate) => {
          setSteps(prev => ({
            ...prev,
            [stageUpdate.stage]: {
              status: stageUpdate.status,
              detail: stageUpdate.detail || '',
            },
          }));
        },
        (thinkingDelta) => {
          setThinkingText(prev => prev + (thinkingDelta.chunk || ''));
        },
        () => {},
      );

      const mappedDiagnosis = mapDdxToDiagnosis(result.ddx || [], result.cpgs_matched || []);
      const mappedCarePlan  = mapTreatmentPlanToCarePlan(result.treatment_plan);

      setDiagnosis(mappedDiagnosis);
      setCarePlan(mappedCarePlan);
    } catch (err) {
      setError(err.message || 'Something went wrong. Is the backend running on port 8058?');
    } finally {
      setIsStreaming(false);
    }
  }, []);

  return (
    <div>
      {/* Page header */}
      <div style={{ marginBottom: 28 }}>
        <h1 className="display-heading" style={{ fontSize: 30, marginBottom: 6 }}>
          Medical Detective
        </h1>
        <p style={{ color: 'var(--ink-soft)', fontSize: 15 }}>
          Pick a patient and watch the AI figure out the diagnosis — step by step, using real clinical guidelines.
        </p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '280px 1fr', gap: 24, alignItems: 'start' }}>
        {/* Left panel — case cards */}
        <div>
          <div className="mono-label" style={{ marginBottom: 10 }}>Choose a Patient</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {SAMPLE_CASES.map(c => (
              <CaseCard
                key={c.id}
                caseData={c}
                isSelected={selectedCaseId === c.id}
                isDisabled={isStreaming && selectedCaseId !== c.id}
                onClick={runCase}
              />
            ))}
          </div>
        </div>

        {/* Right panel — pipeline */}
        <div>
          {error && (
            <div style={{
              padding: '14px 18px',
              background: 'var(--err-soft)',
              border: '1px solid rgba(192,67,63,0.25)',
              borderRadius: 'var(--r-lg)',
              color: 'var(--err)',
              fontSize: 14,
              marginBottom: 20,
            }}>
              <strong>Connection error:</strong> {error}
            </div>
          )}

          {selectedCaseId ? (
            <Pipeline
              steps={steps}
              thinkingText={thinkingText}
              diagnosis={diagnosis}
              carePlan={carePlan}
              isStreaming={isStreaming}
            />
          ) : (
            <div style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              height: 400,
              background: 'var(--surface)',
              border: '2px dashed var(--line)',
              borderRadius: 'var(--r-lg)',
              gap: 12,
            }}>
              <div style={{ fontSize: 40 }}>🔍</div>
              <div style={{ fontFamily: 'var(--font-display)', fontSize: 20, fontWeight: 700, color: 'var(--ink)' }}>
                Select a patient to begin
              </div>
              <div style={{ color: 'var(--ink-soft)', fontSize: 14 }}>
                The AI detective will investigate their case live
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
