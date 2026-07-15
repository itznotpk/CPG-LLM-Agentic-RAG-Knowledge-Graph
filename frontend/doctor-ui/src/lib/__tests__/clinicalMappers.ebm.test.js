import { describe, it, expect } from 'vitest';
import { mapEbmEvidence } from '../clinicalMappers';

describe('mapEbmEvidence', () => {
  it('maps and sorts by tier high->low', () => {
    const plan = { ebm_evidence: [
      { title: 'B', journal: 'J', year: 2022, evidence_tier: 'low', url: 'u2', cpg_gap: false },
      { title: 'A', journal: 'Cochrane', year: 2024, evidence_tier: 'high', url: 'u1', cpg_gap: true },
    ]};
    const out = mapEbmEvidence(plan);
    expect(out).toHaveLength(2);
    expect(out[0].tier).toBe('high');
    expect(out[0].cpgGap).toBe(true);
  });
  it('handles missing field', () => {
    expect(mapEbmEvidence({})).toEqual([]);
    expect(mapEbmEvidence(null)).toEqual([]);
  });
});
