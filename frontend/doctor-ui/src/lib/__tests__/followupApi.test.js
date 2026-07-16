import { describe, it, expect, vi, beforeEach } from 'vitest';
import { enrollFollowup, getFollowupStatus } from '../clinicalApi';

describe('followup clinical API', () => {
  beforeEach(() => { global.fetch = vi.fn(); });

  it('enrollFollowup POSTs consultation_id + patient_nric', async () => {
    fetch.mockResolvedValue({ ok: true, json: async () => ({ deep_link: 'https://t.me/B?start=t' }) });
    const out = await enrollFollowup(101, '900101-14-5555');
    expect(out.deep_link).toContain('t.me');
    const [url, opts] = fetch.mock.calls[0];
    expect(url).toContain('/followup/enroll');
    expect(JSON.parse(opts.body)).toEqual({ consultation_id: 101, patient_nric: '900101-14-5555' });
  });

  it('getFollowupStatus returns null on non-2xx', async () => {
    fetch.mockResolvedValue({ ok: false });
    expect(await getFollowupStatus(101)).toBeNull();
  });
});
