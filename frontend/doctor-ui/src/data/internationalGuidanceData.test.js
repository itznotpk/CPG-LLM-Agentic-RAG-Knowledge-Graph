import { describe, expect, it } from 'vitest';
import { getCuratedInternationalGuidance } from './internationalGuidanceData';

describe('getCuratedInternationalGuidance', () => {
  it('returns the curated diabetes comparison for a supported diagnosis', () => {
    const result = getCuratedInternationalGuidance([{ name: 'Type 2 Diabetes Mellitus - uncontrolled' }]);
    expect(result.status).toBe('available');
    expect(result.record.id).toBe('t2dm');
    expect(result.record.local.publisher).toBe('Malaysia Ministry of Health');
  });

  it('returns an honest unavailable state for diagnoses outside the demo scope', () => {
    const result = getCuratedInternationalGuidance([{ name: 'Acute appendicitis' }]);
    expect(result.status).toBe('unavailable');
    expect(result.message).toMatch(/not in the curated comparison demo/i);
  });
});
