import React from 'react';
import { BrainCircuit, X, ChevronRight, Copy, Check } from 'lucide-react';
import { useApp } from '../../context/AppContext';
import { useTheme } from '../../context/ThemeContext';
import { PipelineProgress } from '../sections/PipelineProgress';

/**
 * TraceDrawer — persistent AI Reasoning Trace panel.
 * Pinned to the right edge of the viewport across Steps 2, 3, and 4.
 * Collapses to a 40px vertical tab when closed.
 *
 * Props:
 *   isOpen   — bool
 *   onToggle — () => void
 */
export function TraceDrawer({ isOpen, onToggle }) {
  const { state } = useApp();
  const { isDark } = useTheme();
  const [copied, setCopied] = React.useState(false);

  const { pipelineEvents, pipelineThinking, pipelineSummary } = state;
  const hasTrace = pipelineEvents?.length > 0;

  const handleCopy = () => {
    const traceText = pipelineEvents
      .map(e => `[${e.eventType}] Stage ${e.stage}: ${e.detail || ''}`)
      .join('\n');
    navigator.clipboard.writeText(traceText).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  return (
    <>
      {/* Collapsed tab — always visible */}
      {!isOpen && (
        <button
          onClick={onToggle}
          title="Open AI Reasoning Trace"
          className={`fixed right-0 top-1/2 -translate-y-1/2 z-40 flex flex-col items-center justify-center gap-1.5
            w-10 py-5 rounded-l-xl shadow-xl border-l-0 transition-all duration-200
            ${isDark
              ? 'bg-indigo-900/80 border border-indigo-500/40 text-indigo-300 hover:bg-indigo-800/90'
              : 'bg-indigo-600 border border-indigo-500 text-white hover:bg-indigo-700'
            } backdrop-blur-md`}
        >
          <BrainCircuit className="w-4 h-4 shrink-0" />
          <span
            className="text-[10px] font-bold uppercase tracking-wider"
            style={{ writingMode: 'vertical-rl', transform: 'rotate(180deg)' }}
          >
            Trace
          </span>
          {hasTrace && (
            <span className={`w-2 h-2 rounded-full ${isDark ? 'bg-indigo-400' : 'bg-white'} animate-pulse`} />
          )}
        </button>
      )}

      {/* Expanded drawer */}
      <div
        className={`fixed top-0 right-0 h-full z-40 flex flex-col transition-transform duration-300 ease-in-out
          ${isOpen ? 'translate-x-0' : 'translate-x-full'}
          w-[380px] max-w-[90vw]
          ${isDark ? 'bg-slate-900/95 border-l border-indigo-500/20' : 'bg-white/95 border-l border-indigo-200'}
          backdrop-blur-xl shadow-2xl`}
      >
        {/* Drawer header */}
        <div className={`flex items-center justify-between px-4 py-3 border-b shrink-0
          ${isDark ? 'border-indigo-500/20 bg-indigo-900/30' : 'border-indigo-100 bg-indigo-50'}`}
        >
          <div className="flex items-center gap-2">
            <BrainCircuit className={`w-4 h-4 ${isDark ? 'text-indigo-400' : 'text-indigo-600'}`} />
            <span className={`text-sm font-semibold ${isDark ? 'text-indigo-300' : 'text-indigo-700'}`}>
              AI Reasoning Trace
            </span>
            {hasTrace && (
              <span className={`text-xs px-2 py-0.5 rounded-full font-medium
                ${isDark ? 'bg-indigo-500/20 text-indigo-400' : 'bg-indigo-100 text-indigo-600'}`}>
                Live
              </span>
            )}
          </div>
          <div className="flex items-center gap-1">
            {hasTrace && (
              <button
                onClick={handleCopy}
                title="Copy trace to clipboard"
                className={`p-1.5 rounded-lg text-xs transition-colors
                  ${isDark ? 'hover:bg-white/10 text-slate-400' : 'hover:bg-slate-100 text-slate-500'}`}
              >
                {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
              </button>
            )}
            <button
              onClick={onToggle}
              title="Collapse trace"
              className={`p-1.5 rounded-lg transition-colors
                ${isDark ? 'hover:bg-white/10 text-slate-400' : 'hover:bg-slate-100 text-slate-500'}`}
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Scrollable trace body */}
        <div className="flex-1 overflow-y-auto p-3">
          {hasTrace ? (
            <PipelineProgress
              pipelineEvents={pipelineEvents}
              pipelineThinking={pipelineThinking}
              summary={pipelineSummary}
              isLive={state.isAnalyzing || state.isGeneratingPlan}
              collapsed={false}
            />
          ) : (
            <div className={`flex flex-col items-center justify-center h-full gap-3 text-center py-12
              ${isDark ? 'text-slate-500' : 'text-slate-400'}`}
            >
              <BrainCircuit className="w-10 h-10 opacity-30" />
              <p className="text-sm">No reasoning trace yet.</p>
              <p className="text-xs opacity-70">Start a clinical analysis to see the AI reasoning chain here.</p>
            </div>
          )}
        </div>

        {/* Footer */}
        {hasTrace && (
          <div className={`px-4 py-2 border-t text-[10px] shrink-0
            ${isDark ? 'border-slate-700/50 text-slate-600' : 'border-slate-200 text-slate-400'}`}
          >
            Powered by Gemini 2.5 Flash · Evidence grounded in Malaysian CPGs
          </div>
        )}
      </div>

      {/* Backdrop overlay on mobile */}
      {isOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/20 lg:hidden"
          onClick={onToggle}
        />
      )}
    </>
  );
}
