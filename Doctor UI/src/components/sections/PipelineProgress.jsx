import React, { useRef, useEffect, useState } from 'react';
import {
  CheckCircle, AlertCircle, Loader2, Circle,
  BrainCircuit, ChevronDown, ChevronUp, RefreshCw,
} from 'lucide-react';
import { GlassCard } from '../shared';
import { useTheme } from '../../context/ThemeContext';

const STAGE_DEFS = [
  { stage: 2, num: '01', label: 'DDx Analysis',      hasThinking: true  },
  { stage: 3, num: '02', label: 'CPG Routing',        hasThinking: false },
  { stage: 4, num: '03', label: 'Evidence Retrieval', hasThinking: false },
  { stage: 5, num: '04', label: 'Plan Synthesis',     hasThinking: false },
];

const FRIENDLY_ERRORS = {
  429: 'API quota exhausted — check billing at AI Studio.',
  401: 'API key invalid or expired.',
  500: 'Upstream model error. Try again in a moment.',
  503: 'Service temporarily unavailable.',
};

function getFriendlyError(detail) {
  if (!detail) return 'Unexpected error. See console for details.';
  const code = Object.keys(FRIENDLY_ERRORS).find(c => String(detail).includes(c));
  return code ? FRIENDLY_ERRORS[code] : 'An error occurred during this step.';
}

const MATCH_TYPE_COLORS = {
  exact:    'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
  parent:   'bg-blue-500/20   text-blue-400    border-blue-500/30',
  range:    'bg-blue-500/20   text-blue-400    border-blue-500/30',
  semantic: 'bg-amber-500/20  text-amber-400   border-amber-500/30',
};

function StatusDot({ status, num }) {
  const base = 'w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold border-2 shrink-0 transition-all duration-300';
  if (status === 'complete') return (
    <div className={`${base} bg-emerald-500/20 border-emerald-500 text-emerald-400`}>
      <CheckCircle className="w-4 h-4" />
    </div>
  );
  if (status === 'error') return (
    <div className={`${base} bg-red-500/20 border-red-500 text-red-400`}>
      <AlertCircle className="w-4 h-4" />
    </div>
  );
  if (status === 'running') return (
    <div className={`${base} bg-[var(--accent-primary)]/20 border-[var(--accent-primary)] text-[var(--accent-primary)] animate-pulse`}>
      <Loader2 className="w-4 h-4 animate-spin" />
    </div>
  );
  return (
    <div className={`${base} bg-slate-800/50 border-slate-600 text-slate-500`}>
      {num}
    </div>
  );
}

function StageBadge({ text, colorClass }) {
  if (!text) return null;
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${colorClass || 'bg-slate-700/50 text-slate-400 border-slate-600/50'}`}>
      {text}
    </span>
  );
}

function ThinkingDropdown({ text, isStreaming }) {
  const scrollRef = useRef(null);
  useEffect(() => {
    if (isStreaming && scrollRef.current)
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [text, isStreaming]);

  if (!text) return null;
  return (
    <div
      ref={scrollRef}
      className="mt-2 max-h-44 overflow-y-auto rounded-lg p-3 text-xs font-mono leading-relaxed
        bg-[var(--accent-primary)]/5 text-slate-300 border border-[var(--accent-primary)]/20"
    >
      {text}
      {isStreaming && (
        <span className="inline-block w-1.5 h-3 ml-0.5 bg-[var(--accent-primary)] animate-pulse align-middle" />
      )}
    </div>
  );
}

/**
 * Props:
 *   pipelineEvents:  ordered array of { eventType, stage, name?, status, detail, badge? }
 *   pipelineThinking: { [nodeName]: string }
 *   summary:          { elapsed_ms, ddxCount, cpgCount } | null
 *   isLive:           bool — true while analysis is running
 *   collapsed:        bool — when true, show only the summary header (DiagnosisSection)
 *   onToggle:         () => void — toggle collapsed state
 */
export function PipelineProgress({
  pipelineEvents = [],
  pipelineThinking = {},
  summary = null,
  isLive = false,
  collapsed = false,
  onToggle,
  resynthOverride = null,
}) {
  const { isDark } = useTheme();
  const [thinkingOpen, setThinkingOpen] = useState(false);

  const stageData = STAGE_DEFS.map((def) => {
    const stageEvents = pipelineEvents.filter((e) => e.stage === def.stage);
    const stageUpdate = [...stageEvents].reverse().find((e) => e.eventType === 'stage_update');
    const subSteps = stageEvents.filter((e) => e.eventType === 'sub_step');
    const status = stageUpdate?.status || 'pending';
    const detail = stageUpdate?.detail || '';
    const badge  = stageUpdate?.badge || null;
    return { ...def, status, detail, badge, subSteps };
  });

  const thinkingText = pipelineThinking['DDx Re-rank'] || '';
  const isThinkingStreaming = isLive && stageData[0]?.status === 'running' && thinkingText.length > 0;

  const summaryText = summary
    ? `${(summary.elapsed_ms / 1000).toFixed(1)}s · ${summary.ddxCount} ICD codes · ${summary.cpgCount} CPGs`
    : isLive ? 'Analysing…' : '';

  return (
    <div className={`overflow-hidden rounded-xl border-2 ${isLive ? 'border-[var(--accent-primary)] shadow-lg shadow-[var(--accent-primary)]/10' : isDark ? 'border-indigo-500/30 bg-slate-800/80' : 'border-indigo-200 bg-white'} transition-all duration-300`}>
      {/* Header */}
      <div
        className={`flex items-center justify-between px-5 py-3 border-b ${isDark ? 'bg-indigo-900/20 border-indigo-500/20' : 'bg-indigo-50 border-indigo-100'} ${onToggle ? 'cursor-pointer select-none' : ''}`}
        onClick={onToggle}
      >
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5">
            {isLive ? (
              <span className="w-2.5 h-2.5 rounded-full bg-[var(--accent-primary)] animate-pulse" />
            ) : (
              <BrainCircuit className={`w-4 h-4 ${isDark ? 'text-indigo-400' : 'text-indigo-600'}`} />
            )}
            <span className={`text-base font-semibold ${isDark ? 'text-indigo-300' : 'text-indigo-700'}`}>
              AI Reasoning Trace
            </span>
          </div>
          {summaryText && (
            <span className={`text-xs ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
              {summaryText}
            </span>
          )}
        </div>
        {onToggle && (
          collapsed
            ? <ChevronDown className="w-4 h-4 text-slate-500" />
            : <ChevronUp   className="w-4 h-4 text-slate-500" />
        )}
      </div>

      {/* Timeline body */}
      {!collapsed && (
        <div className="px-5 pb-5">
          <div className="space-y-0">
            {stageData.map((stage, stageIdx) => {
              const isLast = stageIdx === stageData.length - 1;
              const isActive = stage.status === 'running';

              return (
                <React.Fragment key={stage.stage}>
                {/* Clinician override marker — inserted between Stage 2 and Stage 3 */}
                {stage.stage === 3 && resynthOverride && (
                  <div className="flex gap-4">
                    <div className="flex flex-col items-center">
                      <div className="w-8 h-8 flex items-center justify-center rounded-full
                        bg-amber-500/20 border-2 border-amber-500/50 text-amber-400 text-xs">
                        ✎
                      </div>
                      <div className="w-0.5 flex-1 my-1 min-h-4 bg-amber-500/30" />
                    </div>
                    <div className="flex-1 pb-4 pt-1">
                      <p className={`text-xs font-medium ${isDark ? 'text-amber-300' : 'text-amber-700'}`}>
                        Clinician override
                      </p>
                      <p className={`text-xs mt-0.5 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                        {resynthOverride.codes.join(' · ')}
                      </p>
                    </div>
                  </div>
                )}
                <div className="flex gap-4">
                  {/* Left: dot + vertical line */}
                  <div className="flex flex-col items-center">
                    <StatusDot status={stage.status} num={stage.num} />
                    {!isLast && (
                      <div className={`w-0.5 flex-1 my-1 min-h-4 transition-colors duration-500
                        ${stage.status === 'complete' ? 'bg-emerald-500/40' : 'bg-slate-700/50'}`}
                      />
                    )}
                  </div>

                  {/* Right: content */}
                  <div className="flex-1 pb-4 min-w-0">
                    {/* Stage header row */}
                    <div className="flex items-center justify-between pt-1 mb-1">
                      <span className={`text-sm font-semibold ${
                        isActive                    ? (isDark ? 'text-white'       : 'text-slate-800') :
                        stage.status === 'complete' ? (isDark ? 'text-slate-200'  : 'text-slate-700') :
                        stage.status === 'error'    ? 'text-red-400' :
                        (isDark ? 'text-slate-500' : 'text-slate-400')
                      }`}>
                        {stage.label}
                      </span>
                      <div className="flex items-center gap-2 ml-3 shrink-0">
                        {stage.badge && (
                          <StageBadge text={stage.badge}
                            colorClass="bg-emerald-500/15 text-emerald-400 border-emerald-500/30"
                          />
                        )}
                        {stage.status === 'complete' && !stage.badge && stage.detail && (
                          <span className="text-xs text-slate-500">{stage.detail.split('·').pop()?.trim()}</span>
                        )}
                      </div>
                    </div>

                    {/* Detail text or Error card */}
                    {stage.status === 'error' ? (
                      <div className="mt-1 mb-2 p-3 rounded-lg bg-red-500/10 border border-red-500/30">
                        <p className={`text-xs font-semibold flex items-center gap-1.5 ${isDark ? 'text-red-400' : 'text-red-600'}`}>
                          <AlertCircle className="w-3.5 h-3.5 shrink-0" />
                          {stage.label} failed
                        </p>
                        <p className={`text-xs mt-1 ${isDark ? 'text-red-300/80' : 'text-red-700/80'}`}>
                          {getFriendlyError(stage.detail)}
                        </p>
                        <button className={`mt-2 flex items-center gap-1 text-[10px] font-bold uppercase tracking-wider ${isDark ? 'text-red-300' : 'text-red-700'} hover:underline`}>
                          <RefreshCw className="w-3 h-3" /> Retry Stage
                        </button>
                      </div>
                    ) : stage.detail && stage.status !== 'pending' && (
                      <p className={`text-xs mb-1 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                        {stage.detail}
                      </p>
                    )}

                    {/* Sub-steps */}
                    {stage.subSteps.length > 0 && (
                      <div className="mt-1.5 space-y-1 pl-3 border-l border-slate-700/50">
                        {stage.subSteps.map((sub, i) => {
                          const isLastSub = i === stage.subSteps.length - 1;
                          const connector = isLastSub ? '└' : '├';
                          const matchColor = sub.badge ? (MATCH_TYPE_COLORS[sub.badge] || MATCH_TYPE_COLORS.semantic) : null;
                          return (
                            <div key={i} className="flex items-center gap-2">
                              <span className="text-slate-600 font-mono text-xs shrink-0">{connector}</span>
                              <span className={`text-xs truncate ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                                {sub.detail}
                              </span>
                              {sub.badge && (
                                <StageBadge text={sub.badge} colorClass={matchColor} />
                              )}
                            </div>
                          );
                        })}
                      </div>
                    )}

                    {/* Thinking dropdown — DDx stage only */}
                    {stage.hasThinking && thinkingText && (
                      <div className="mt-2">
                        <button
                          onClick={() => setThinkingOpen((o) => !o)}
                          className="flex items-center gap-1.5 text-xs text-[var(--accent-primary)] hover:opacity-80 transition-opacity"
                        >
                          <BrainCircuit className="w-3.5 h-3.5" />
                          {thinkingOpen ? 'Hide reasoning' : 'View reasoning'}
                          {thinkingOpen ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                        </button>
                        {thinkingOpen && (
                          <ThinkingDropdown text={thinkingText} isStreaming={isThinkingStreaming} />
                        )}
                      </div>
                    )}
                  </div>
                </div>
                </React.Fragment>
              );
            })}
          </div>

          {/* Footer */}
          <div className={`mt-2 pt-3 border-t text-xs ${isDark ? 'border-slate-700/50 text-slate-600' : 'border-slate-200 text-slate-400'}`}>
            Powered by Gemini 2.5 Flash · Evidence grounded in Malaysian CPGs
          </div>
        </div>
      )}
    </div>
  );
}
