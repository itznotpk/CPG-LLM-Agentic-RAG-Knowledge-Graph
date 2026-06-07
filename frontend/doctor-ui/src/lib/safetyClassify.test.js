/**
 * Unit tests for the Stage-6 safety-banner pure logic.
 *
 * Guards two documented invariants (see CLAUDE.md "Stage 6 safety banner contract"):
 *  1. The severity filter drops MODERATE flags as LLM noise EXCEPT source==='graph'.
 *     KG flags default to MODERATE, so without the exemption every graph-verified
 *     flag collapses into reviewer_notes and the dual-source story disappears.
 *  2. classifyFlag triages each flag into plan / current_only / class_or_noise.
 *     Only `plan` flags require a per-flag decision; the matchedMed enables the
 *     deep-link to the med row.
 */
import { describe, it, expect } from 'vitest';
import { isFlagVisible, classifyFlag } from './safetyClassify';

describe('isFlagVisible — severity filter with graph exemption', () => {
  it('keeps CRITICAL and MAJOR regardless of source', () => {
    expect(isFlagVisible({ severity: 'CRITICAL', source: 'llm' })).toBe(true);
    expect(isFlagVisible({ severity: 'MAJOR', source: 'llm' })).toBe(true);
  });

  it('drops MODERATE LLM flags as noise', () => {
    expect(isFlagVisible({ severity: 'MODERATE', source: 'llm' })).toBe(false);
  });

  it('KEEPS MODERATE flags when source === "graph" (the dual-source exemption)', () => {
    expect(isFlagVisible({ severity: 'MODERATE', source: 'graph' })).toBe(true);
  });

  it('the filter preserves at least one KG flag in a mixed batch', () => {
    const flags = [
      { severity: 'MODERATE', source: 'llm' },     // dropped
      { severity: 'MODERATE', source: 'graph' },   // kept
      { severity: 'CRITICAL', source: 'llm' },     // kept
    ];
    const kept = flags.filter(isFlagVisible);
    expect(kept).toHaveLength(2);
    expect(kept.some((f) => f.source === 'graph')).toBe(true);
  });
});

describe('classifyFlag — plan / current_only / class_or_noise triage', () => {
  const plannedMeds = [
    { id: 7, name: 'Enalapril 5mg', section: 'start' },
    { id: 9, name: 'Losartan 50mg', section: 'contraindicated' },
  ];
  const currentMeds = ['Atenolol 25mg', 'Metformin 1g'];

  it('classifies a flag whose drug is in the plan as "plan" and returns the matched med (for deep-link)', () => {
    const flag = { title: 'Losartan - teratogen caution', detail: 'ARB in pregnancy', severity: 'CRITICAL' };
    const c = classifyFlag(flag, plannedMeds, currentMeds);
    expect(c.kind).toBe('plan');
    expect(c.matchedMed.id).toBe(9);
    expect(c.matchedMed.section).toBe('contraindicated');
  });

  it('classifies a current-med-only flag as "current_only"', () => {
    const flag = { title: 'Atenolol caution', detail: 'beta-blocker', severity: 'MAJOR' };
    const c = classifyFlag(flag, plannedMeds, currentMeds);
    expect(c.kind).toBe('current_only');
    expect(c.matchedMed.name).toBe('Atenolol 25mg');
  });

  it('classifies a class-level flag matching neither plan nor current as "class_or_noise"', () => {
    const flag = { title: 'ARB class caution', detail: 'class-level advisory', severity: 'MODERATE', source: 'graph' };
    const c = classifyFlag(flag, plannedMeds, currentMeds);
    expect(c.kind).toBe('class_or_noise');
    expect(c.matchedMed).toBeUndefined();
  });

  it('matches on a token, not just the full string (token-hit path)', () => {
    const flag = { title: 'Enalapril + spironolactone - hyperkalemia', detail: '', severity: 'MAJOR' };
    const c = classifyFlag(flag, plannedMeds, currentMeds);
    expect(c.kind).toBe('plan');
    expect(c.matchedMed.id).toBe(7);
  });

  it('falls back to detail when the flag has no title', () => {
    const flag = { detail: 'metformin lactic-acidosis risk', severity: 'MAJOR' };
    const c = classifyFlag(flag, plannedMeds, currentMeds);
    expect(c.kind).toBe('current_only');
  });

  it('ignores short (<3 char) med names to avoid spurious substring hits', () => {
    const flag = { title: 'caution about iron', detail: '', severity: 'MAJOR' };
    const c = classifyFlag(flag, [{ id: 1, name: 'K', section: 'start' }], []);
    expect(c.kind).toBe('class_or_noise');
  });
});
