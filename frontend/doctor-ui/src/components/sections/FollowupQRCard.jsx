import { useEffect, useRef, useState } from 'react';
import { QRCodeSVG } from 'qrcode.react';
import { MessageCircle, CheckCircle2 } from 'lucide-react';
import { GlassCard } from '../shared';
import { enrollFollowup, getFollowupStatus } from '../../lib/clinicalApi';

/**
 * Post-visit follow-up enrollment card. Enrolls once on mount, shows the
 * t.me deep-link QR, then polls status every 3 s until the patient scans
 * (status flips to 'active') and shows "Connected".
 */
export default function FollowupQRCard({ consultationId, patientNric, isDark }) {
  const [deepLink, setDeepLink] = useState(null);
  const [status, setStatus] = useState('none');
  const [error, setError] = useState(null);
  const enrolled = useRef(false);

  useEffect(() => {
    if (!consultationId || !patientNric || enrolled.current) return;
    enrolled.current = true;
    enrollFollowup(consultationId, patientNric)
      .then((r) => { setDeepLink(r.deep_link); setStatus('issued'); })
      .catch((e) => setError(String(e.message || e)));
  }, [consultationId, patientNric]);

  useEffect(() => {
    if (status !== 'issued') return undefined;
    const t = setInterval(async () => {
      const s = await getFollowupStatus(consultationId);
      if (s?.status === 'active') setStatus('active');
    }, 3000);
    return () => clearInterval(t);
  }, [status, consultationId]);

  if (error) return null; // follow-up is optional — never block the output step

  return (
    <GlassCard className="p-5">
      <div className="flex items-center gap-2 mb-3">
        <MessageCircle size={18} className="text-teal-500" />
        <h3 className={`font-semibold ${isDark ? 'text-white' : 'text-gray-900'}`}>Patient Follow-up</h3>
      </div>
      {status === 'active' ? (
        <div className="flex items-center gap-2 text-teal-500">
          <CheckCircle2 size={18} />
          <span className="text-sm font-medium">Connected — first check-in sent</span>
        </div>
      ) : deepLink ? (
        <div className="flex items-center gap-4">
          <div className="bg-white p-2 rounded-lg">
            <QRCodeSVG value={deepLink} size={120} />
          </div>
          <p className={`text-sm ${isDark ? 'text-gray-300' : 'text-gray-600'}`}>
            Ask the patient to scan this with their phone to receive follow-up
            check-ins on Telegram. Link expires in 48 hours.
          </p>
        </div>
      ) : (
        <p className={`text-sm ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>Preparing follow-up link…</p>
      )}
    </GlassCard>
  );
}
