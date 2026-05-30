import React from 'react';

/**
 * TierSegmentedControl — three-state pill input for DDx Major/Minor selection.
 *
 *   value: 'off' | 'minor' | 'major'
 *   onChange(next: 'off' | 'minor' | 'major'): void
 *   disabled?: boolean
 *
 * Tapping the active segment toggles it back to 'off'. Tapping a different
 * segment switches state directly. Visual feedback uses a neutral background
 * for off, blue for minor (co-consideration), amber for major (primary).
 */
const TIER_STYLES = {
  off:   { bg: 'bg-slate-700/40',  text: 'text-slate-300',   ring: 'ring-slate-500/40' },
  minor: { bg: 'bg-sky-600',       text: 'text-white',       ring: 'ring-sky-400' },
  major: { bg: 'bg-amber-500',     text: 'text-slate-900',   ring: 'ring-amber-300' },
};

const SEGMENT_LABEL = { off: 'Off', minor: 'Minor', major: 'Major' };
const SEGMENT_ORDER = ['off', 'minor', 'major'];

export function TierSegmentedControl({ value = 'off', onChange, disabled = false, ariaLabel }) {
  const current = SEGMENT_ORDER.includes(value) ? value : 'off';

  const handle = (tier) => {
    if (disabled) return;
    if (tier === current) {
      onChange?.('off');
    } else {
      onChange?.(tier);
    }
  };

  return (
    <div
      role="radiogroup"
      aria-label={ariaLabel || 'Diagnosis tier'}
      className="inline-flex items-center rounded-full bg-slate-800/70 p-1 gap-1 text-xs font-semibold"
    >
      {SEGMENT_ORDER.map((tier) => {
        const isActive = tier === current;
        const style = TIER_STYLES[tier];
        const baseClasses = 'px-3 py-1 rounded-full transition-colors duration-150';
        const activeClasses = isActive
          ? `${style.bg} ${style.text} ring-2 ${style.ring}`
          : 'text-slate-400 hover:text-slate-200';
        return (
          <button
            key={tier}
            type="button"
            role="radio"
            aria-checked={isActive}
            disabled={disabled}
            onClick={() => handle(tier)}
            className={`${baseClasses} ${activeClasses} ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
          >
            {SEGMENT_LABEL[tier]}
          </button>
        );
      })}
    </div>
  );
}

export default TierSegmentedControl;
