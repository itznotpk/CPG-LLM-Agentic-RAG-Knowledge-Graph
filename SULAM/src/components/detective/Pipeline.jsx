import StepCard from './StepCard.jsx';
import ThinkingBox from './ThinkingBox.jsx';
import DiagnosisList from './DiagnosisList.jsx';
import CarePlanCard from './CarePlanCard.jsx';

const STEPS = [
  { stage: 2, stepNumber: 1, title: 'Reading the clues',            caption: 'AI generates differential diagnoses' },
  { stage: 3, stepNumber: 2, title: 'Choosing the right guidebooks', caption: '⚡ The Agentic step — AI decides what to look up' },
  { stage: 4, stepNumber: 3, title: 'Reading the real guidelines',   caption: '📚 The RAG step — grounding in real documents' },
  { stage: 5, stepNumber: 4, title: 'Writing the care plan',         caption: 'Every recommendation cites a CPG source' },
];

function FlowLine({ filled }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'center', height: 28 }}>
      <div style={{ width: 2, position: 'relative', background: 'var(--line)', borderRadius: 1 }}>
        <div style={{
          position: 'absolute', top: 0, left: 0, width: '100%',
          height: filled ? '100%' : '0%',
          background: 'var(--primary)',
          borderRadius: 1,
          transition: 'height 0.5s ease',
        }} />
      </div>
    </div>
  );
}

export default function Pipeline({ steps, thinkingText, diagnosis, carePlan, isStreaming }) {
  const getStatus = (stage) => steps[stage]?.status || 'pending';
  const getDetail = (stage) => steps[stage]?.detail || '';

  const stageComplete = (stage) => getStatus(stage) === 'complete';

  return (
    <div>
      {STEPS.map((step, i) => (
        <div key={step.stage}>
          <StepCard
            stepNumber={step.stepNumber}
            title={step.title}
            caption={step.caption}
            status={getStatus(step.stage)}
            detail={getDetail(step.stage)}
          >
            {/* Step 1 — DDx: show thinking box then diagnosis list */}
            {step.stage === 2 && (
              <>
                <ThinkingBox
                  text={thinkingText}
                  isActive={getStatus(2) === 'running'}
                />
                {stageComplete(2) && diagnosis && (
                  <DiagnosisList
                    differentials={diagnosis.differentials}
                    cpgsMatched={diagnosis.cpgsMatched}
                  />
                )}
              </>
            )}

            {/* Step 2 — CPG routing: show matched guideline chips */}
            {step.stage === 3 && stageComplete(3) && diagnosis?.cpgsMatched?.length > 0 && (
              <div style={{ marginTop: 8 }}>
                <div style={{ fontSize: 13, color: 'var(--ink-soft)', marginBottom: 6 }}>
                  Matched guidelines for top ICD code:
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                  {diagnosis.cpgsMatched.map((cpg, j) => (
                    <span key={j} className="chip chip-primary" style={{
                      animation: `fadeSlideIn 0.3s ease both`,
                      animationDelay: `${j * 80}ms`,
                    }}>
                      📖 {cpg}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Step 4 — Care plan */}
            {step.stage === 5 && stageComplete(5) && carePlan && (
              <CarePlanCard carePlan={carePlan} />
            )}
          </StepCard>

          {/* Animated flow line between steps */}
          {i < STEPS.length - 1 && (
            <FlowLine filled={stageComplete(step.stage)} />
          )}
        </div>
      ))}

      <style>{`
        @keyframes fadeSlideIn {
          from { opacity: 0; transform: translateY(4px); }
          to   { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </div>
  );
}
