import React, { useMemo, useState } from 'react';
import { Sparkles, Star, AlertCircle } from 'lucide-react';
import { GlassCard, Button, Badge, TierSegmentedControl } from '../shared';

/**
 * DDxSelectionPanel — clinician picks 1–5 DDx codes and tags exactly one as Major.
 *
 * Props:
 *   candidates: [{ rank, code, title, probability, reasoning, suggested_tier }]
 *   headlessDefault: { major, minors } — system's headless-mode pick (used for hint badges only)
 *   onConfirm({ selected_codes, major_code }): void   — fires when clinician hits Confirm
 *   disabled?: boolean
 *
 * Default state: all rows Off — clinician must actively engage with each suggestion.
 * Major exclusivity enforced silently: setting Major on a new card auto-demotes the
 * previous Major to Minor. Confirm disabled until exactly one Major is set.
 * The UI deliberately does NOT show the CPG allocation math (3/3+2/3+1+1/…) —
 * that lives in the backend.
 */
export function DDxSelectionPanel({
  candidates = [],
  headlessDefault = {},
  onConfirm,
  disabled = false,
}) {
  const initialTiers = useMemo(
    () => Object.fromEntries(candidates.map((c) => [c.code, 'off'])),
    [candidates],
  );
  const [tiers, setTiers] = useState(initialTiers);
  const [hintsDismissed, setHintsDismissed] = useState(false);

  React.useEffect(() => {
    setTiers(initialTiers);
    setHintsDismissed(false);
  }, [initialTiers]);

  const selectedCodes = Object.entries(tiers)
    .filter(([, t]) => t !== 'off')
    .map(([code]) => code);
  const majorCode = Object.entries(tiers).find(([, t]) => t === 'major')?.[0] || null;
  const canConfirm = !!majorCode && !disabled;

  const setTier = (code, nextTier) => {
    setTiers((prev) => {
      const updated = { ...prev };
      if (nextTier === 'major') {
        // Demote any other major to minor (silent exclusivity)
        for (const [k, v] of Object.entries(updated)) {
          if (k !== code && v === 'major') {
            updated[k] = 'minor';
          }
        }
      }
      updated[code] = nextTier;
      return updated;
    });
  };

  const applyHint = (code, tier) => {
    setTier(code, tier);
  };

  const restoreHints = () => setHintsDismissed(false);

  const handleConfirm = () => {
    if (!canConfirm) return;
    onConfirm?.({
      selected_codes: selectedCodes,
      major_code: majorCode,
    });
  };

  if (!candidates.length) return null;

  return (
    <GlassCard className="space-y-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-amber-400" />
            Tag your differentials
          </h3>
          <p className="text-sm text-slate-300 mt-1">
            Tap to mark each suggestion as <span className="text-amber-300 font-semibold">Major</span>{' '}
            (primary diagnosis) or <span className="text-sky-300 font-semibold">Minor</span>{' '}
            (co-consideration). One Major is required.
          </p>
        </div>
        {hintsDismissed && (
          <button
            type="button"
            onClick={restoreHints}
            className="text-xs text-slate-300 underline hover:text-slate-100"
          >
            Restore suggestions
          </button>
        )}
      </div>

      <ul className="space-y-2">
        {candidates.map((c) => {
          const tier = tiers[c.code] || 'off';
          const probabilityPct = Math.round((c.probability ?? 0) * 100);
          const showMajorHint =
            !hintsDismissed
            && tier === 'off'
            && c.code === headlessDefault.major;
          const showMinorHint =
            !hintsDismissed
            && tier === 'off'
            && (headlessDefault.minors || []).includes(c.code);
          return (
            <li
              key={c.code}
              className="flex flex-col gap-2 rounded-xl border border-slate-700/60 bg-slate-900/40 p-3 sm:flex-row sm:items-center sm:justify-between"
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <Badge variant="default" className="text-xs">#{c.rank}</Badge>
                  <span className="font-sans text-sm text-slate-200">{c.code}</span>
                  <span className="text-sm text-slate-100 truncate" title={c.title}>
                    {c.title}
                  </span>
                </div>
                <div className="mt-1.5 flex items-center gap-2">
                  <div className="flex-1 h-1.5 bg-slate-700/60 rounded overflow-hidden max-w-[200px]">
                    <div
                      className="h-full bg-emerald-500"
                      style={{ width: `${Math.min(100, Math.max(0, probabilityPct))}%` }}
                    />
                  </div>
                  <span className="text-xs text-slate-300 font-sans">{probabilityPct}%</span>
                </div>
                {(showMajorHint || showMinorHint) && (
                  <div className="mt-2 flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => applyHint(c.code, showMajorHint ? 'major' : 'minor')}
                      className={`inline-flex items-center gap-1 text-xs px-2 py-1 rounded-full border transition-colors ${
                        showMajorHint
                          ? 'border-amber-400/60 text-amber-200 hover:bg-amber-500/10'
                          : 'border-sky-400/60 text-sky-200 hover:bg-sky-500/10'
                      }`}
                    >
                      <Star className="w-3 h-3" />
                      {showMajorHint
                        ? 'System suggests as Major — tap to apply'
                        : 'System suggests as Minor — tap to apply'}
                    </button>
                    <button
                      type="button"
                      onClick={() => setHintsDismissed(true)}
                      className="text-[10px] text-slate-400 hover:text-slate-200"
                      aria-label="Dismiss all suggestion hints"
                    >
                      dismiss
                    </button>
                  </div>
                )}
              </div>
              <TierSegmentedControl
                value={tier}
                onChange={(next) => setTier(c.code, next)}
                disabled={disabled}
                ariaLabel={`Tier for ${c.code} ${c.title}`}
              />
            </li>
          );
        })}
      </ul>

      <div className="flex items-center justify-end gap-3 pt-2 border-t border-slate-700/40">
        {!majorCode && (
          <span className="inline-flex items-center gap-1 text-xs text-slate-400">
            <AlertCircle className="w-3.5 h-3.5" />
            Mark one diagnosis as Major to continue
          </span>
        )}
        <Button
          variant="primary"
          disabled={!canConfirm}
          onClick={handleConfirm}
          title={canConfirm ? undefined : 'Set exactly one Major to enable'}
        >
          Confirm selection
        </Button>
      </div>
    </GlassCard>
  );
}

export default DDxSelectionPanel;
