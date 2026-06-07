// @vitest-environment jsdom
/**
 * L3 — SafetyReviewBanner component / interaction tests.
 *
 * The banner is the Stage-6 safety surface. Its pure classification/filter logic
 * is unit-tested under L1 (safetyClassify); this suite covers the *rendered
 * behaviour* documented in CLAUDE.md "Stage 6 safety banner contract":
 *   - the graph-MODERATE exemption is actually VISIBLE (LLM MODERATE noise is
 *     dropped, but source==='graph' MODERATE is shown);
 *   - plan flags get a per-flag decision UI, while current-only and class/noise
 *     flags render as informational panels;
 *   - the acknowledge button is gated until every plan flag has a decision, then
 *     fires onAcknowledge with the decisions;
 *   - the jumpToMed deep-link calls back with the matched med id.
 *
 * Rendered in a real ThemeProvider (defaults to light → no matchMedia needed).
 */
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import { ThemeProvider } from '../../context/ThemeContext';
import { SafetyReviewBanner } from './SafetyReviewBanner';

afterEach(() => cleanup());

const renderBanner = (props) =>
  render(
    <ThemeProvider>
      <SafetyReviewBanner {...props} />
    </ThemeProvider>,
  );

describe('empty / null states', () => {
  it('renders nothing when report is null', () => {
    const { container } = renderBanner({ report: null });
    expect(container.firstChild).toBeNull();
  });

  it('shows the pass message when there are no flags', () => {
    renderBanner({ report: { safe_to_proceed: true, flags: [] } });
    expect(screen.getByText(/Safety review passed/i)).toBeTruthy();
  });
});

describe('graph-MODERATE exemption (the dual-source story)', () => {
  it('shows a graph MODERATE flag but drops an LLM MODERATE flag', () => {
    renderBanner({
      report: {
        safe_to_proceed: true,
        flags: [
          { severity: 'MODERATE', source: 'graph', flag_type: 'contraindication', title: 'Losartan - pregnancy contraindication', detail: 'ARB teratogenic per KG edge' },
          { severity: 'MODERATE', source: 'llm', flag_type: 'interaction', title: 'Losartan - minor LLM note', detail: 'low-value LLM noise' },
        ],
      },
      plannedMeds: [{ id: 9, name: 'Losartan 50mg', section: 'contraindicated' }],
    });
    expect(screen.getByText(/pregnancy contraindication/i)).toBeTruthy();   // graph kept
    expect(screen.queryByText(/minor LLM note/i)).toBeNull();               // llm dropped
    expect(screen.getByText(/1 Moderate/i)).toBeTruthy();                   // counted in header
  });
});

describe('flag triage rendering', () => {
  it('routes a non-prescribed class flag to the "class-level notices" panel', () => {
    renderBanner({
      report: {
        safe_to_proceed: true,
        flags: [{ severity: 'MAJOR', source: 'llm', flag_type: 'contraindication', title: 'Amiodarone - QT prolongation', detail: 'class advisory' }],
      },
      plannedMeds: [{ id: 1, name: 'Enalapril 5mg', section: 'start' }],
      currentMeds: [],
    });
    expect(screen.getByText(/Class-level notices not matched to a prescribed drug \(1\)/i)).toBeTruthy();
  });

  it('routes a current-meds-only flag to the "review existing prescription" panel', () => {
    renderBanner({
      report: {
        safe_to_proceed: true,
        flags: [{ severity: 'MAJOR', source: 'llm', flag_type: 'interaction', title: 'Atenolol - bradycardia', detail: 'beta-blocker' }],
      },
      plannedMeds: [],
      currentMeds: ['Atenolol 25mg'],
    });
    expect(screen.getByText(/Review existing prescription/i)).toBeTruthy();
  });
});

describe('acknowledge gating (blocked plan)', () => {
  const blockedProps = (onAcknowledge) => ({
    report: {
      safe_to_proceed: false,
      flags: [
        { severity: 'CRITICAL', source: 'llm', flag_type: 'interaction', title: 'Enalapril + Spironolactone - hyperkalemia', detail: 'risk', recommendation_index: 0 },
        { severity: 'MAJOR', source: 'llm', flag_type: 'contraindication', title: 'Amiodarone - QT prolongation', detail: 'class note' },
      ],
    },
    plannedMeds: [{ id: 1, name: 'Enalapril 5mg', section: 'start' }],
    currentMeds: [],
    acknowledged: false,
    onAcknowledge,
  });

  it('keeps acknowledge disabled until every plan flag is decided, then fires onAcknowledge', () => {
    const onAcknowledge = vi.fn();
    renderBanner(blockedProps(onAcknowledge));

    const ackBtn = screen.getByRole('button', { name: /accept clinical responsibility/i });
    expect(ackBtn.disabled).toBe(true);                          // gated initially

    // The only plan flag is Enalapril (Amiodarone is class/noise) — decide it.
    fireEvent.click(screen.getByRole('button', { name: /Remove from plan/i }));

    expect(ackBtn.disabled).toBe(false);                         // gate satisfied
    fireEvent.click(ackBtn);
    expect(onAcknowledge).toHaveBeenCalledTimes(1);
    const decisions = onAcknowledge.mock.calls[0][0];
    expect(Object.values(decisions)[0].decision).toBe('remove');
  });
});

describe('jumpToMed deep-link', () => {
  it('renders the deep-link for a plan flag and calls onJumpToMed with the matched id', () => {
    const onJumpToMed = vi.fn();
    renderBanner({
      report: {
        safe_to_proceed: true,
        flags: [{ severity: 'CRITICAL', source: 'llm', flag_type: 'contraindication', title: 'Losartan - teratogen', detail: 'ARB in pregnancy' }],
      },
      plannedMeds: [{ id: 42, name: 'Losartan 50mg', section: 'contraindicated' }],
      onJumpToMed,
    });
    const link = screen.getByRole('button', { name: /in contraindicated list/i });
    fireEvent.click(link);
    expect(onJumpToMed).toHaveBeenCalledWith(42);
  });
});
