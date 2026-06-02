import React from 'react';
import { useTheme } from '../../context/ThemeContext';

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
const SEGMENT_LABEL = { off: 'Off', minor: 'Minor', major: 'Major' };
const SEGMENT_ORDER = ['off', 'minor', 'major'];

export function TierSegmentedControl({ value = 'off', onChange, disabled = false, ariaLabel }) {
  const { isDark } = useTheme();
  const current = SEGMENT_ORDER.includes(value) ? value : 'off';

  const handle = (tier) => {
    if (disabled) return;
    if (tier === current) {
      onChange?.('off');
    } else {
      onChange?.(tier);
    }
  };

  const getSegmentClasses = (tier) => {
    const isActive = tier === current;
    const base = 'px-3.5 py-1.5 rounded-full transition-all duration-200 text-xs font-semibold';

    if (isActive) {
      if (tier === 'off') {
        return isDark
          ? `${base} bg-slate-600 text-white shadow-sm`
          : `${base} bg-slate-600 text-white shadow-sm`;
      }
      if (tier === 'minor') {
        return isDark
          ? `${base} bg-teal-500 text-white shadow-sm`
          : `${base} bg-teal-500 text-white shadow-sm`;
      }
      if (tier === 'major') {
        return isDark
          ? `${base} bg-amber-500 text-white shadow-sm`
          : `${base} bg-amber-500 text-white shadow-sm`;
      }
    }

    return isDark
      ? `${base} text-slate-400 hover:text-slate-200`
      : `${base} text-slate-500 hover:text-slate-700`;
  };

  return (
    <div
      role="radiogroup"
      aria-label={ariaLabel || 'Diagnosis tier'}
      className={`inline-flex items-center rounded-full p-0.5 gap-0.5 ${
        isDark ? 'bg-slate-700/60' : 'bg-slate-100'
      }`}
    >
      {SEGMENT_ORDER.map((tier) => (
        <button
          key={tier}
          type="button"
          role="radio"
          aria-checked={tier === current}
          disabled={disabled}
          onClick={() => handle(tier)}
          className={`${getSegmentClasses(tier)} ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
        >
          {SEGMENT_LABEL[tier]}
        </button>
      ))}
    </div>
  );
}

export default TierSegmentedControl;
