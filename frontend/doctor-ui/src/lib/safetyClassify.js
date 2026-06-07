// Pure safety-flag classification — no React, no side-effects, importable anywhere.
// Extracted from SafetyReviewBanner.jsx so the two load-bearing rules documented
// in CLAUDE.md (the graph-exemption severity filter and the plan/current/noise
// triage) can be unit-tested without the JSX render chain.

/**
 * Severity filter with the graph exemption.
 *
 * Stage 6 KG-sourced flags default to MODERATE (`_kg_severity_to_safety` never
 * emits CRITICAL and floors missing/MINOR to MODERATE). Dropping all MODERATE
 * flags as LLM noise would therefore silently discard every graph-verified flag
 * and collapse the dual-source (LLM ‖ KG) story. Keep MODERATE when
 * `source === 'graph'`.
 */
export const isFlagVisible = (f) => f.severity !== 'MODERATE' || f.source === 'graph';

/**
 * Classify a flag against the current plan and the patient's existing meds.
 * Returns { kind, matchedMed? } where:
 *   `plan`           — drug appears in the active care plan → real decision required;
 *                       matchedMed = { id, name, section } enables deep-linking
 *   `current_only`   — drug is in the patient's current med list but NOT in the
 *                       new plan → informational, no plan mutation possible
 *   `class_or_noise` — neither → collapsed informational pile
 */
export function classifyFlag(flag, plannedMeds, currentMeds) {
  const drugs = (flag.title || flag.detail || '').toLowerCase();

  const findMatch = (meds, nameKey = 'name') => {
    for (const med of meds) {
      const rawName = typeof med === 'string' ? med : med?.[nameKey] || med?.drug || '';
      if (!rawName) continue;
      const low = String(rawName).toLowerCase();
      if (low.length < 3) continue;
      const tokenHit = low.split(/[\s,()]+/).some((tok) => tok.length >= 4 && /^[a-z]/.test(tok) && drugs.includes(tok));
      if (drugs.includes(low) || tokenHit) return med;
    }
    return null;
  };

  const planned = findMatch(plannedMeds);
  if (planned) return { kind: 'plan', matchedMed: planned };
  const current = findMatch(currentMeds);
  if (current) return { kind: 'current_only', matchedMed: typeof current === 'string' ? { name: current } : current };
  return { kind: 'class_or_noise' };
}
