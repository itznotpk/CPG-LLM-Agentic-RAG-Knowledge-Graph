// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, waitFor, fireEvent, cleanup } from '@testing-library/react';
import { ThemeProvider } from '../../../context/ThemeContext';

const ALERT = vi.hoisted(() => ({
  id: 1, patient_nric: '900101-14-5555', severity: 'critical',
  summary: 'tripwire: breathless', patient_reply: 'woke up breathless',
  status: 'open', created_at: '2026-07-16T10:00:00Z',
}));

vi.mock('../../../lib/supabase', async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    getPatientAlerts: vi.fn().mockResolvedValue([ALERT]),
    ackPatientAlert: vi.fn().mockResolvedValue(undefined),
    supabase: { channel: () => ({ on: vi.fn().mockReturnThis(), subscribe: vi.fn().mockReturnThis() }), removeChannel: vi.fn() },
  };
});

import PatientAlertsPanel from '../PatientAlertsPanel';
import { ackPatientAlert } from '../../../lib/supabase';

// GlassCard/Badge (used inside PatientAlertsPanel) require a ThemeProvider
// ancestor — mirrors the pattern in FollowupQRCard.test.jsx / SafetyReviewBanner.test.jsx.
// This project has no @testing-library/jest-dom, so assertions use plain
// truthy checks rather than toBeInTheDocument (same precedent).
const renderPanel = (props) =>
  render(
    <ThemeProvider>
      <PatientAlertsPanel {...props} />
    </ThemeProvider>,
  );

afterEach(() => cleanup());

describe('PatientAlertsPanel', () => {
  it('renders open alerts with masked NRIC and verbatim reply', async () => {
    renderPanel({ isDark: false });
    await waitFor(() => expect(screen.getByText(/woke up breathless/i)).toBeTruthy());
    expect(screen.queryByText('900101-14-5555')).toBeNull();  // full NRIC never shown
    expect(screen.getByText(/5555/)).toBeTruthy();             // masked tail shown
  });

  it('acknowledge button calls ackPatientAlert', async () => {
    renderPanel({ isDark: false });
    await waitFor(() => screen.getByRole('button', { name: /acknowledge/i }));
    fireEvent.click(screen.getByRole('button', { name: /acknowledge/i }));
    await waitFor(() => expect(ackPatientAlert).toHaveBeenCalledWith(1, expect.anything()));
  });
});
