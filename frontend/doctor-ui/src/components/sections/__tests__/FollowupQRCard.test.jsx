// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import { ThemeProvider } from '../../../context/ThemeContext';

vi.mock('../../../lib/clinicalApi', () => ({
  enrollFollowup: vi.fn().mockResolvedValue({ deep_link: 'https://t.me/B?start=tok', expires_at: 'x' }),
  getFollowupStatus: vi.fn().mockResolvedValue({ status: 'issued' }),
}));

import FollowupQRCard from '../FollowupQRCard';
import { getFollowupStatus } from '../../../lib/clinicalApi';

// GlassCard (used inside FollowupQRCard) requires a ThemeProvider ancestor —
// mirrors the pattern in SafetyReviewBanner.test.jsx (defaults to light, no matchMedia needed).
// This project has no @testing-library/jest-dom, so assertions use plain
// truthy checks rather than toBeInTheDocument (SafetyReviewBanner.test.jsx does the same).
const renderCard = (props) =>
  render(
    <ThemeProvider>
      <FollowupQRCard {...props} />
    </ThemeProvider>,
  );

afterEach(() => cleanup());

describe('FollowupQRCard', () => {
  it('renders QR after enrolling', async () => {
    renderCard({ consultationId: 101, patientNric: 'X', isDark: false });
    await waitFor(() => expect(document.querySelector('svg, canvas')).toBeTruthy());
    expect(screen.getByText(/scan/i)).toBeTruthy();
  });

  it('flips to connected when status becomes active', async () => {
    getFollowupStatus.mockResolvedValue({ status: 'active' });
    renderCard({ consultationId: 101, patientNric: 'X', isDark: false });
    // Real 3s poll interval — give waitFor enough headroom to observe it fire.
    await waitFor(() => expect(screen.getByText(/connected/i)).toBeTruthy(), { timeout: 4000 });
  });
});
