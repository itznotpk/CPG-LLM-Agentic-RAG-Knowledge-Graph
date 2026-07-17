import { describe, expect, it } from 'vitest';
import { aggregateLLMDegradations } from './supabase';

describe('aggregateLLMDegradations', () => {
  it('groups operation and reason while ignoring manifests', () => {
    const rows = [
      { signal_type: 'llm_degradation', severity: 'warning', payload: { operation: 'prep_brief', reason: 'empty_content' } },
      { signal_type: 'llm_degradation', severity: 'critical', payload: { operation: 'prep_brief', reason: 'empty_content' } },
      { signal_type: 'run_manifest', payload: { operations: [{ reason: 'private audit only' }] } },
    ];
    expect(aggregateLLMDegradations(rows)).toEqual([
      { operation: 'prep_brief', reason: 'empty_content', count: 2, severity: 'critical' },
    ]);
  });
});
