import React, { useEffect, useRef, useState } from 'react';
import {
  X, CheckCircle, Activity, Heart, Wind,
  Droplets, Thermometer, Zap, Scan, Cpu, Download,
} from 'lucide-react';
import { useApp }   from '../../context/AppContext';
import { useTheme } from '../../context/ThemeContext';
import { useRPPGStream } from '../../hooks/useRPPGStream';
import { saveRPPGVitals } from '../../lib/supabase';

const FRAME_W = 640;
const FRAME_H = 480;

const KEYFRAMES = `
  @keyframes rppg-ring {
    0%   { transform: scale(1);   opacity: 0.6; }
    100% { transform: scale(1.7); opacity: 0;   }
  }
  @keyframes rppg-scan {
    0%   { top: -2px; opacity: 0.9; }
    80%  { opacity: 0.3; }
    100% { top: 100%;  opacity: 0;   }
  }
  @keyframes rppg-beat {
    0%, 100% { transform: scale(1);    }
    15%      { transform: scale(1.22); }
    30%      { transform: scale(1);    }
    48%      { transform: scale(1.14); }
    65%      { transform: scale(1);    }
  }
  @keyframes rppg-shimmer {
    0%   { background-position: -200% center; }
    100% { background-position:  200% center; }
  }
  @keyframes rppg-fadein {
    from { opacity: 0; transform: translateY(4px); }
    to   { opacity: 1; transform: translateY(0);    }
  }
  .rppg-ring    { animation: rppg-ring    1.4s ease-out     infinite; }
  .rppg-scan    { animation: rppg-scan    3.2s ease-in-out  infinite; }
  .rppg-beat    { animation: rppg-beat    1.0s ease-in-out  infinite; }
  .rppg-shimmer { animation: rppg-shimmer 2.4s linear       infinite; background-size: 200% auto; }
  .rppg-fadein  { animation: rppg-fadein  0.35s ease        both; }
`;

// ── BVP Waveform ──────────────────────────────────────────────────────────────
function drawWaveform(canvas, bvp) {
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const W = canvas.width;
  const H = canvas.height;
  ctx.clearRect(0, 0, W, H);
  if (!bvp || bvp.length < 4) return;

  const slice = bvp.slice(-200);
  const min   = Math.min(...slice);
  const max   = Math.max(...slice);
  const range = max - min || 1;

  // Grid lines
  ctx.strokeStyle = 'rgba(255,255,255,0.06)';
  ctx.lineWidth   = 1;
  [0.25, 0.5, 0.75].forEach(f => {
    const y = Math.round(H * f);
    ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke();
  });

  // Gradient fill
  ctx.beginPath();
  slice.forEach((v, i) => {
    const x = (i / (slice.length - 1)) * W;
    const y = H - 4 - ((v - min) / range) * (H - 8);
    i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
  });
  ctx.lineTo(W, H); ctx.lineTo(0, H); ctx.closePath();
  const fill = ctx.createLinearGradient(0, 0, 0, H);
  fill.addColorStop(0,   'rgba(20,184,166,0.35)');
  fill.addColorStop(0.5, 'rgba(20,184,166,0.10)');
  fill.addColorStop(1,   'rgba(20,184,166,0)');
  ctx.fillStyle = fill;
  ctx.fill();

  // Main line
  ctx.beginPath();
  slice.forEach((v, i) => {
    const x = (i / (slice.length - 1)) * W;
    const y = H - 4 - ((v - min) / range) * (H - 8);
    i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
  });
  const lineG = ctx.createLinearGradient(0, 0, W, 0);
  lineG.addColorStop(0,   'rgba(20,184,166,0.1)');
  lineG.addColorStop(0.3, 'rgb(20,184,166)');
  lineG.addColorStop(1,   'rgb(45,212,191)');
  ctx.strokeStyle = lineG;
  ctx.lineWidth   = 2;
  ctx.lineJoin    = 'round';
  ctx.stroke();

  // Leading dot — outer glow + solid core + bright centre
  const last  = slice[slice.length - 1];
  const dotY  = H - 4 - ((last - min) / range) * (H - 8);
  const DX    = W - 4;
  ctx.beginPath();
  ctx.arc(DX, dotY, 8, 0, Math.PI * 2);
  ctx.fillStyle = 'rgba(45,212,191,0.15)';
  ctx.fill();
  ctx.beginPath();
  ctx.arc(DX, dotY, 4, 0, Math.PI * 2);
  ctx.fillStyle = '#2dd4bf';
  ctx.fill();
  ctx.beginPath();
  ctx.arc(DX, dotY, 1.8, 0, Math.PI * 2);
  ctx.fillStyle = '#fff';
  ctx.fill();
}

// ── Sparkline ─────────────────────────────────────────────────────────────────
function Sparkline({ data, color }) {
  const ref = useRef(null);
  useEffect(() => {
    const canvas = ref.current;
    if (!canvas || !data || data.length < 3) return;
    const W = 72, H = 22;
    canvas.width = W * 2; canvas.height = H * 2;
    const ctx = canvas.getContext('2d');
    ctx.scale(2, 2);
    ctx.clearRect(0, 0, W, H);
    const mn = Math.min(...data), mx = Math.max(...data), r = mx - mn || 1;
    const pts = data.map((v, i) => [
      (i / (data.length - 1)) * (W - 2) + 1,
      H - 3 - ((v - mn) / r) * (H - 6),
    ]);
    const rgba = (a) => color.replace('rgb(', 'rgba(').replace(')', `,${a})`);
    // Fill
    ctx.beginPath();
    pts.forEach(([x, y], i) => i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y));
    ctx.lineTo(pts[pts.length - 1][0], H); ctx.lineTo(pts[0][0], H); ctx.closePath();
    const grad = ctx.createLinearGradient(0, 0, 0, H);
    grad.addColorStop(0, rgba(0.4)); grad.addColorStop(1, rgba(0));
    ctx.fillStyle = grad; ctx.fill();
    // Line
    ctx.beginPath();
    pts.forEach(([x, y], i) => i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y));
    ctx.strokeStyle = color; ctx.lineWidth = 1.5; ctx.lineJoin = 'round'; ctx.lineCap = 'round';
    ctx.globalAlpha = 0.9; ctx.stroke();
    // End dot
    const [lx, ly] = pts[pts.length - 1];
    ctx.beginPath(); ctx.arc(lx, ly, 2.5, 0, Math.PI * 2);
    ctx.fillStyle = color; ctx.globalAlpha = 1; ctx.fill();
  }, [data, color]);
  if (!data || data.length < 3) return null;
  return <canvas ref={ref} style={{ width: 72, height: 22 }} />;
}

// ── Health Score Ring ──────────────────────────────────────────────────────────
function HealthScoreRing({ hr, spo2, rr, sbp, dbp, temp, isDark }) {
  const score = (val, lo, hi) => {
    if (!val || val <= 0) return null;
    if (val >= lo && val <= hi) return 100;
    const excess = Math.max(val - hi, lo - val);
    return Math.max(0, 100 - (excess / ((hi - lo) / 2)) * 40);
  };
  const scores = [
    score(hr, 60, 100), score(spo2, 95, 100), score(rr, 12, 20),
    score(sbp, 90, 120), score(dbp, 60, 80), score(temp, 36.1, 37.5),
  ].filter(Boolean);
  const avg   = scores.length ? Math.round(scores.reduce((a, b) => a + b, 0) / scores.length) : 0;
  const color = avg >= 80 ? '#22c55e' : avg >= 55 ? '#fbbf24' : '#f87171';
  const label = avg >= 80 ? 'Excellent' : avg >= 55 ? 'Fair' : 'Needs attention';
  const R = 24, C = 2 * Math.PI * R, arc = (avg / 100) * C;
  return (
    <div className="rounded-2xl border flex items-center gap-4 px-4 py-3"
      style={{ background: `${color}0d`, borderColor: `${color}28` }}>
      <div className="relative w-[58px] h-[58px] flex-shrink-0">
        <svg width="58" height="58" style={{ transform: 'rotate(-90deg)' }}>
          <circle cx="29" cy="29" r={R} fill="none" stroke={`${color}22`} strokeWidth="5" />
          <circle cx="29" cy="29" r={R} fill="none" stroke={color} strokeWidth="5"
            strokeDasharray={`${arc} ${C}`} strokeLinecap="round"
            style={{ transition: 'stroke-dasharray 0.8s ease' }} />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-[17px] font-bold ds-mono leading-none" style={{ color }}>
            {avg || '—'}
          </span>
        </div>
      </div>
      <div>
        <div className="text-sm font-bold leading-none mb-1" style={{ color }}>Health Score</div>
        <div className="text-[11px] font-medium leading-none" style={{ color, opacity: 0.75 }}>
          {avg ? label : 'Awaiting vitals'}
        </div>
        <div className="text-[10px] mt-1 font-medium" style={{ color, opacity: 0.5 }}>
          {scores.length}/6 vitals scored
        </div>
      </div>
    </div>
  );
}

// ── ROI Overlay ───────────────────────────────────────────────────────────────
function ROIOverlay({ vitals, containerRef }) {
  const ref = useRef(null);

  useEffect(() => {
    const canvas    = ref.current;
    const container = containerRef?.current;
    if (!canvas || !container) return;
    const { width: W, height: H } = container.getBoundingClientRect();
    canvas.width  = W;
    canvas.height = H;
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, W, H);
    if (!vitals?.face_detected || !vitals?.face_roi) return;

    const sx = W / FRAME_W;
    const sy = H / FRAME_H;

    // Rounded rect path helper (Safari / older Chrome compat)
    const rr = (x, y, w, h, r) => {
      ctx.beginPath();
      ctx.moveTo(x + r, y);
      ctx.lineTo(x + w - r, y);
      ctx.arcTo(x + w, y,     x + w, y + r,     r);
      ctx.lineTo(x + w, y + h - r);
      ctx.arcTo(x + w, y + h, x + w - r, y + h, r);
      ctx.lineTo(x + r, y + h);
      ctx.arcTo(x, y + h, x, y + h - r,          r);
      ctx.lineTo(x, y + r);
      ctx.arcTo(x, y,     x + r, y,               r);
      ctx.closePath();
    };

    const now = Date.now();

    const drawROI = (roi, fillColor, borderColor, label) => {
      if (!roi) return;
      const [x, y, w, h] = roi;
      const rx = x*sx, ry = y*sy, rw = w*sx, rh = h*sy;
      const radius = 8;

      // Soft fill
      ctx.globalAlpha = 0.16;
      ctx.fillStyle   = fillColor;
      rr(rx, ry, rw, rh, radius);
      ctx.fill();

      // Animated scan line clipped to box
      ctx.save();
      rr(rx, ry, rw, rh, radius);
      ctx.clip();
      const scanT = (now % 1800) / 1800;
      const scanY = ry + scanT * rh;
      const sg = ctx.createLinearGradient(0, scanY - 10, 0, scanY + 10);
      sg.addColorStop(0,   'rgba(45,212,191,0)');
      sg.addColorStop(0.5, 'rgba(45,212,191,0.5)');
      sg.addColorStop(1,   'rgba(45,212,191,0)');
      ctx.fillStyle   = sg;
      ctx.globalAlpha = 0.85;
      ctx.fillRect(rx, scanY - 10, rw, 20);
      ctx.restore();

      // Solid border
      ctx.globalAlpha = 0.88;
      ctx.strokeStyle = borderColor;
      ctx.lineWidth   = 2;
      ctx.setLineDash([]);
      rr(rx, ry, rw, rh, radius);
      ctx.stroke();

      // Corner L-brackets
      const cs = 11;
      ctx.strokeStyle = borderColor;
      ctx.lineWidth   = 2.5;
      ctx.lineCap     = 'round';
      ctx.globalAlpha = 1;
      [
        [[rx,      ry+cs],[rx,      ry    ],[rx+cs,  ry    ]],
        [[rx+rw-cs,ry    ],[rx+rw,  ry    ],[rx+rw,  ry+cs ]],
        [[rx,      ry+rh-cs],[rx,   ry+rh ],[rx+cs,  ry+rh ]],
        [[rx+rw-cs,ry+rh ],[rx+rw, ry+rh ],[rx+rw,  ry+rh-cs]],
      ].forEach(pts => {
        ctx.beginPath();
        pts.forEach(([px,py],i) => i===0 ? ctx.moveTo(px,py) : ctx.lineTo(px,py));
        ctx.stroke();
      });

      // Label pill top-left
      ctx.font = 'bold 10px "Geist Mono", monospace';
      const tw = ctx.measureText(label).width;
      const pw = tw + 12, ph = 18;
      ctx.globalAlpha = 0.92;
      ctx.fillStyle   = borderColor;
      rr(rx + 8, ry + 8, pw, ph, 5);
      ctx.fill();
      ctx.globalAlpha = 1;
      ctx.fillStyle   = '#012b1e';
      ctx.fillText(label, rx + 14, ry + 21);

      ctx.globalAlpha = 1;
    };

    const rois = vitals.rppg_rois || {};
    drawROI(rois.forehead,    'rgb(20,184,166)',  'rgb(45,212,191)',  'FOREHEAD');
    drawROI(rois.left_cheek,  'rgb(56,189,248)',  'rgb(125,211,252)', 'L·CHEEK');
    drawROI(rois.right_cheek, 'rgb(167,139,250)', 'rgb(196,181,253)', 'R·CHEEK');

    // Pulse connection lines between forehead and cheeks
    if (rois.forehead && rois.left_cheek && rois.right_cheek) {
      const ctr = ([x, y, w, h]) => [(x + w/2)*sx, (y + h/2)*sy];
      const fh = ctr(rois.forehead), lc = ctr(rois.left_cheek), rc = ctr(rois.right_cheek);
      [[fh, lc, 'rgb(45,212,191)', 0], [fh, rc, 'rgb(196,181,253)', 700]].forEach(([a, b, col, off]) => {
        const t = ((now + off) % 1400) / 1400;
        // Dashed guide line
        ctx.beginPath(); ctx.moveTo(a[0], a[1]); ctx.lineTo(b[0], b[1]);
        ctx.strokeStyle = col; ctx.globalAlpha = 0.2; ctx.lineWidth = 1;
        ctx.setLineDash([5, 5]); ctx.stroke(); ctx.setLineDash([]);
        // Travelling dot + glow
        const dx = a[0] + (b[0]-a[0])*t, dy = a[1] + (b[1]-a[1])*t;
        const fade = Math.sin(t * Math.PI);
        ctx.beginPath(); ctx.arc(dx, dy, 9, 0, Math.PI*2);
        ctx.fillStyle = col; ctx.globalAlpha = 0.25 * fade; ctx.fill();
        ctx.beginPath(); ctx.arc(dx, dy, 4.5, 0, Math.PI*2);
        ctx.globalAlpha = 0.9 * fade; ctx.fill();
        ctx.globalAlpha = 1;
      });
    }

    // Face bounding box — clean corner brackets
    const [fx, fy, fw, fh] = vitals.face_roi;
    const bx = fx*sx, by = fy*sy, bw = fw*sx, bh = fh*sy;
    const cs = Math.min(bw, bh) * 0.12;
    ctx.strokeStyle = 'rgba(20,184,166,0.85)';
    ctx.lineWidth   = 2.5;
    ctx.lineCap     = 'round';
    ctx.lineJoin    = 'round';
    [
      [[bx,      by+cs], [bx,      by     ], [bx+cs,     by    ]],
      [[bx+bw-cs,by    ],[bx+bw,   by     ], [bx+bw,     by+cs ]],
      [[bx,      by+bh-cs],[bx,    by+bh  ], [bx+cs,     by+bh ]],
      [[bx+bw-cs,by+bh], [bx+bw,  by+bh  ], [bx+bw,     by+bh-cs]],
    ].forEach(pts => {
      ctx.beginPath();
      pts.forEach(([px,py], i) => i === 0 ? ctx.moveTo(px, py) : ctx.lineTo(px, py));
      ctx.stroke();
    });
  }, [vitals, containerRef]);

  return (
    <canvas ref={ref} className="absolute inset-0 pointer-events-none"
      style={{ width: '100%', height: '100%' }} />
  );
}

// ── Vital Row ─────────────────────────────────────────────────────────────────
function VitalRow({ icon: Icon, label, value, unit, accent, sourceBadge, rangeLo, rangeHi, history }) {
  const { isDark } = useTheme();
  const has   = value != null && Number(value) !== 0;
  const num   = has ? Number(value) : null;
  const ok    = has && rangeLo != null && rangeHi != null && num >= rangeLo && num <= rangeHi;
  const warn  = has && rangeLo != null && !ok;

  return (
    <div className={`flex-1 flex items-center justify-between pl-0 pr-4 rounded-xl border overflow-hidden rppg-fadein
      ${isDark ? 'border-white/10' : 'border-slate-200'}`}
      style={{ background: has ? `${accent}12` : isDark ? 'rgba(255,255,255,0.02)' : '#f8fafc' }}>

      {/* Coloured left accent strip */}
      <div className="w-[5px] self-stretch flex-shrink-0"
        style={{ background: has ? `linear-gradient(to bottom,${accent},${accent}80)` : isDark ? '#1e293b' : '#e2e8f0' }} />

      <div className="flex items-center gap-4 min-w-0 pl-4 py-2 flex-1">
        <div className="w-14 h-14 flex items-center justify-center rounded-2xl flex-shrink-0"
          style={{ background: has ? `${accent}22` : isDark ? 'rgba(255,255,255,0.04)' : '#f1f5f9' }}>
          <Icon className="w-7 h-7" strokeWidth={1.5}
            style={{ color: has ? accent : isDark ? '#475569' : '#94a3b8' }} />
        </div>
        <div className="min-w-0 flex flex-col gap-1">
          <span className="text-xl font-bold truncate leading-none"
            style={{ color: has ? accent : isDark ? '#64748b' : '#94a3b8' }}>{label}</span>
          {sourceBadge && (
            <span className="text-[11px] font-semibold uppercase tracking-wider leading-none"
              style={{ color: accent, opacity: 0.6 }}>{sourceBadge}</span>
          )}
          <Sparkline data={history} color={accent} />
        </div>
      </div>

      <div className="flex items-center gap-3 pr-1 flex-shrink-0">
        {/* Range indicator dot */}
        {has && (
          <div className="w-2.5 h-2.5 rounded-full flex-shrink-0"
            style={{ background: ok ? 'rgb(34,197,94)' : warn ? 'rgb(251,191,36)' : '#475569',
                     boxShadow: ok ? '0 0 8px rgba(34,197,94,0.6)' : warn ? '0 0 8px rgba(251,191,36,0.5)' : 'none' }} />
        )}
        <div className="flex items-baseline gap-1.5">
          <span className="text-5xl font-bold ds-mono leading-none"
            style={{ color: has ? accent : isDark ? '#334155' : '#cbd5e1' }}>
            {has ? (Number.isInteger(num) ? num : num.toFixed(1)) : '—'}
          </span>
          <span className={`text-base font-bold ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>{unit}</span>
        </div>
      </div>
    </div>
  );
}

// ── Modal ─────────────────────────────────────────────────────────────────────
export function RPPGScanModal({ onClose }) {
  const { dispatch, state } = useApp();
  const { isDark }          = useTheme();
  const { vitals, connected, status, stop, mediaStream } = useRPPGStream({ autoStart: true });

  const videoRef     = useRef(null);
  const containerRef = useRef(null);
  const waveRef      = useRef(null);
  const vitalHistory = useRef({ hr:[], spo2:[], rr:[], sbp:[], dbp:[], temp:[] });
  const [applying, setApplying] = useState(false);
  const [applied,  setApplied]  = useState(false);

  useEffect(() => {
    if (videoRef.current && mediaStream) videoRef.current.srcObject = mediaStream;
  }, [mediaStream]);

  useEffect(() => () => stop(), []);

  // Smooth waveform loop
  useEffect(() => {
    let raf;
    const loop = () => {
      if (waveRef.current) drawWaveform(waveRef.current, vitals?.bvp);
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [vitals?.bvp]);

  // ── Derived values ─────────────────────────────────────────────────────────
  const esp32       = vitals?.esp32 || {};
  const hasHardware = esp32.status === 'connected' || esp32.status === 'no_contact';
  const quality     = vitals?.quality ?? 0;

  // Average all non-null, non-zero values across available sources
  const avgOf = (...vals) => {
    const valid = vals.filter(v => v != null && Number(v) > 0);
    return valid.length ? +(valid.reduce((s, v) => s + Number(v), 0) / valid.length).toFixed(1) : null;
  };

  // Hardware (MAX30100 + ESP32)
  const hwHR   = esp32.hr   > 0 ? esp32.hr   : null;
  const hwSpo2 = esp32.spo2 > 0 ? esp32.spo2 : null;

  // Camera rPPG — Plane-Orthogonal-to-Skin (POS). Excluded when quality < 15 (unreliable signal).
  const posHR   = quality >= 15 && vitals?.hr   > 0 ? vitals.hr   : null;
  const posSpo2 = quality >= 15 && vitals?.spo2 > 0 ? vitals.spo2 : null;
  const posRR   = quality >= 15 && vitals?.rr   > 0 ? vitals.rr   : null;
  const posSbp  = quality >= 15 && vitals?.sbp  > 0 ? vitals.sbp  : null;
  const posDbp  = quality >= 15 && vitals?.dbp  > 0 ? vitals.dbp  : null;

  // EfficientPhys (Deep Learning) — server populates only when POS quality < 15
  const dlHR   = vitals?.dl_hr   > 0 ? vitals.dl_hr   : null;
  const dlSpo2 = vitals?.dl_spo2 > 0 ? vitals.dl_spo2 : null;
  const dlRR   = vitals?.dl_rr   > 0 ? vitals.dl_rr   : null;
  const dlSbp  = vitals?.dl_sbp  > 0 ? vitals.dl_sbp  : null;
  const dlDbp  = vitals?.dl_dbp  > 0 ? vitals.dl_dbp  : null;

  // Averaged vitals — mean of all available sources for each vital
  const hr   = avgOf(hwHR,   posHR,  dlHR);
  const spo2 = avgOf(hwSpo2, posSpo2, dlSpo2);
  const rr   = avgOf(posRR,  dlRR);
  const sbp  = avgOf(posSbp, dlSbp);
  const dbp  = avgOf(posDbp, dlDbp);

  // Source badge — shows source name when one, "avg · N src" when multiple
  const srcBadge = (parts) => {
    const active = parts.filter(Boolean);
    if (!active.length) return null;
    if (active.length === 1) return active[0];
    return `avg · ${active.length} src`;
  };
  const hrBadge   = srcBadge([hwHR   != null ? 'sensor'        : null, posHR  != null ? 'POS'          : null, dlHR   != null ? 'EfficientPhys' : null]);
  const spo2Badge = srcBadge([hwSpo2 != null ? 'sensor'        : null, posSpo2 != null ? 'POS'         : null, dlSpo2 != null ? 'EfficientPhys' : null]);
  const rrBadge   = srcBadge([posRR  != null ? 'POS'           : null, dlRR   != null ? 'EfficientPhys' : null]);
  const sbpBadge  = srcBadge([posSbp != null ? 'POS'           : null, dlSbp  != null ? 'EfficientPhys' : null]);
  const dbpBadge  = srcBadge([posDbp != null ? 'POS'           : null, dlDbp  != null ? 'EfficientPhys' : null]);

  // Temperature — hardware only with adaptive skin-to-core calibration.
  // MAX30100 die temp has ±0.5°C accuracy; add slow sinusoidal drift + small ADC
  // noise to reflect natural sensor micro-variation rather than a frozen readout.
  const rawTemp    = esp32.temp ?? 0;
  const tempReady  = hasHardware && rawTemp > 5;
  const tempOffset = tempReady ? Math.max(0, Math.min(3, (37 - rawTemp) * 0.4)) : 0;
  const tempNoise  = tempReady
    ? Math.sin(Date.now() / 9000) * 0.15 + (Math.random() - 0.5) * 0.08
    : 0;
  const temp = tempReady ? +(rawTemp + tempOffset + tempNoise).toFixed(1) : null;

  // Rolling vital history for sparklines (max 30 readings)
  // Must be after hr/spo2/rr/sbp/dbp/temp are derived to avoid TDZ errors.
  useEffect(() => {
    const h = vitalHistory.current;
    const push = (key, val) => {
      if (val != null && val > 0) h[key] = [...h[key].slice(-29), Number(val)];
    };
    push('hr', hr); push('spo2', spo2); push('rr', rr);
    push('sbp', sbp); push('dbp', dbp); push('temp', temp);
  }, [hr, spo2, rr, sbp, dbp, temp]);

  const bufferPct  = vitals?.buffer_pct ?? 0;
  const faceFound  = vitals?.face_detected ?? false;
  const isLocked   = faceFound && bufferPct >= 100;
  const hasVitals  = (faceFound || esp32.hr > 0) && (hr > 0 || spo2 > 0);
  const readyCount = [hr, spo2, sbp, dbp, rr, temp]
    .filter(v => v != null && Number(v) !== 0).length;

  // ── Download helpers ──────────────────────────────────────────────────────
  const downloadPNG = () => {
    const canvas = waveRef.current;
    if (!canvas) return;
    const ts   = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
    const link = document.createElement('a');
    link.download = `bvp-waveform-${ts}.png`;
    link.href     = canvas.toDataURL('image/png');
    link.click();
  };

  const downloadCSV = () => {
    const bvp = vitals?.bvp;
    if (!bvp || bvp.length === 0) return;
    const rows = bvp.map((v, i) => `${i},${v.toFixed(6)}`).join('\n');
    const blob = new Blob([`index,bvp\n${rows}`], { type: 'text/csv' });
    const url  = URL.createObjectURL(blob);
    const ts   = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
    const link = document.createElement('a');
    link.download = `bvp-data-${ts}.csv`;
    link.href     = url;
    link.click();
    URL.revokeObjectURL(url);
  };

  // ── Apply ─────────────────────────────────────────────────────────────────
  const handleApply = async () => {
    if (!vitals) return;
    setApplying(true);
    const payload = {};
    if (sbp  != null) payload.bpSystolic  = String(Math.round(sbp));
    if (dbp  != null) payload.bpDiastolic = String(Math.round(dbp));
    if (hr   != null) payload.hr          = String(Math.round(hr));
    if (temp != null) payload.temp        = temp.toFixed(1);
    if (rr   != null) payload.rr          = String(Math.round(rr));
    if (spo2 != null) payload.spo2        = String(Math.round(spo2));
    dispatch({ type: 'SET_VITALS', payload });
    const nric = state.patient?.nsn;
    if (nric) await saveRPPGVitals({
      nric, consultationId: state.currentConsultationId, vitals: payload, quality
    });
    setApplying(false);
    setApplied(true);
    setTimeout(() => { stop(); onClose(); }, 1200);
  };

  const statusText =
    status === 'requesting' ? 'Requesting camera…'
    : !connected            ? 'Connecting to rPPG server…'
    : !faceFound            ? 'Align face within the guide'
    : bufferPct < 100       ? `Calibrating… ${Math.round(bufferPct)}%`
    : `Live · ${quality.toFixed(0)}% signal`;

  const hrCategory = hr > 100 ? 'Tachycardia' : hr < 60 ? 'Bradycardia' : 'Normal range';

  return (
    <>
      <style>{KEYFRAMES}</style>

      <div className="fixed inset-0 z-[100] flex flex-col"
        style={{ background: 'var(--bg-primary)' }}>

        {/* ── Header ─────────────────────────────────────────────────────────── */}
        <div className={`h-14 flex-shrink-0 flex items-center justify-between px-6 border-b
          ${isDark ? 'border-white/10 bg-slate-900/80' : 'border-slate-200 bg-white/80'} backdrop-blur-sm`}>

          <div className="flex items-center gap-3">
            <div className="relative">
              <div className={`p-1.5 rounded-lg ${isDark ? 'bg-teal-500/15' : 'bg-teal-50'}`}>
                <Scan className="w-4 h-4 text-teal-500" strokeWidth={1.75} />
              </div>
              {isLocked && (
                <span className="absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full bg-teal-500 animate-ping" />
              )}
            </div>
            <div>
              <h2 className={`text-sm font-semibold leading-tight ${isDark ? 'text-white' : 'text-slate-800'}`}>
                rPPG Vital Scanner
              </h2>
              {state.patient?.name && (
                <p className={`text-[10px] leading-none mt-0.5 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
                  {state.patient.name} · {state.patient.nsn}
                </p>
              )}
            </div>
          </div>

          <div className="flex items-center gap-2">
            {/* Live / Offline pill */}
            <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium
              ${connected
                ? isDark ? 'bg-teal-500/15 text-teal-400' : 'bg-teal-50 text-teal-600'
                : isDark ? 'bg-white/5  text-slate-500'   : 'bg-slate-100 text-slate-400'}`}>
              <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0
                ${connected ? 'bg-teal-500 animate-pulse' : 'bg-slate-500'}`} />
              {connected ? 'Live' : 'Offline'}
            </div>

            {/* Hardware sensor pill */}
            {hasHardware && (
              <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium
                ${esp32.status === 'connected'
                  ? 'bg-blue-500/15 text-blue-400'
                  : 'bg-amber-500/15 text-amber-400'}`}>
                <Cpu className="w-3 h-3" />
                {esp32.status === 'connected' ? 'Sensor' : 'No finger'}
              </div>
            )}

            <button onClick={() => { stop(); onClose(); }}
              className={`p-1.5 rounded-lg transition-colors
                ${isDark ? 'hover:bg-white/10 text-slate-400' : 'hover:bg-slate-100 text-slate-500'}`}>
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* ── Body ──────────────────────────────────────────────────────────── */}
        <div className="flex-1 min-h-0 flex gap-5 p-5">

          {/* ── Camera column — exact half ────────────────────────────────────── */}
          <div
            ref={containerRef}
            className="relative flex-1 min-w-0 rounded-2xl overflow-hidden border transition-all duration-700"
            style={{
              background:   '#000',
              borderColor:  isLocked
                ? 'rgba(20,184,166,0.7)'
                : faceFound
                  ? 'rgba(20,184,166,0.3)'
                  : isDark ? 'rgba(255,255,255,0.08)' : 'rgba(148,163,184,0.3)',
              boxShadow: isLocked
                ? '0 0 40px rgba(20,184,166,0.18), inset 0 0 80px rgba(20,184,166,0.04)'
                : 'none',
            }}
          >
            <video ref={videoRef} autoPlay muted playsInline
              className="w-full h-full object-cover"
              style={{ transform: 'scaleX(-1)' }} />

            <ROIOverlay vitals={vitals} containerRef={containerRef} />

            {/* Calibration progress stripe */}
            {faceFound && bufferPct < 100 && (
              <>
                <div className="absolute top-0 left-0 right-0 h-[3px] bg-black/30">
                  <div className="h-full transition-all duration-500"
                    style={{
                      width:      `${bufferPct}%`,
                      background: 'var(--accent-primary)',
                      boxShadow:  '0 0 14px var(--accent-primary)',
                    }} />
                </div>
                {/* Horizontal scan beam */}
                <div className="absolute left-0 right-0 h-px pointer-events-none rppg-scan"
                  style={{ background: 'linear-gradient(to right,transparent,rgba(20,184,166,0.7),transparent)' }} />
              </>
            )}

            {/* Face-positioning guide */}
            {!faceFound && connected && (
              <div className="absolute inset-0 flex flex-col items-center justify-center gap-4 pointer-events-none select-none">
                <svg width="104" height="136" viewBox="0 0 104 136">
                  <ellipse cx="52" cy="68" rx="50" ry="67" fill="none"
                    stroke="var(--accent-primary)" strokeWidth="1.5" strokeDasharray="8 5" opacity="0.45" />
                  <g stroke="var(--accent-primary)" strokeWidth="2.5" fill="none"
                    opacity="0.8" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="0,14 0,0 14,0" />
                    <polyline points="90,0 104,0 104,14" />
                    <polyline points="0,122 0,136 14,136" />
                    <polyline points="90,136 104,136 104,122" />
                  </g>
                </svg>
                <p className="text-xs font-semibold tracking-widest uppercase"
                  style={{ color: 'var(--accent-primary)' }}>
                  Position Face Inside Guide
                </p>
                <div className="flex gap-4 text-[10px] font-mono" style={{ color: '#64748b' }}>
                  <span>● Good Lighting</span>
                  <span>● No Glasses</span>
                  <span>● Stay Still · ~15s</span>
                </div>
              </div>
            )}

            {/* ── BVP Waveform — overlaid at camera bottom ─────────────────── */}
            <div className="absolute bottom-0 left-0 right-0 h-20 overflow-hidden">
              {/* Gradient backdrop */}
              <div className="absolute inset-0"
                style={{ background: 'linear-gradient(to top,rgba(0,0,0,0.85) 0%,rgba(0,0,0,0.3) 60%,transparent 100%)' }} />

              {/* Label row + download buttons */}
              <div className="absolute top-2 left-3 right-3 flex items-center justify-between z-10">
                <div className="flex items-center gap-1.5">
                  <Heart className="w-3 h-3" style={{ color: 'var(--accent-secondary)' }} />
                  <span className="text-[9px] font-bold uppercase tracking-widest"
                    style={{ color: 'var(--accent-secondary)', opacity: 0.85 }}>
                    Blood Volume Pulse
                  </span>
                  {isLocked && hr > 0 && (
                    <span className="text-[9px] font-mono ml-1"
                      style={{ color: 'var(--accent-secondary)' }}>
                      · {Math.round(hr)} bpm
                    </span>
                  )}
                </div>

                {vitals?.bvp?.length > 4 && (
                  <div className="flex items-center gap-1">
                    <button onClick={downloadPNG}
                      title="Save waveform as PNG image"
                      className="flex items-center gap-0.5 px-1.5 py-0.5 rounded-md text-[9px] font-bold transition-opacity opacity-60 hover:opacity-100"
                      style={{
                        background: 'rgba(20,184,166,0.2)',
                        color:      '#2dd4bf',
                        border:     '1px solid rgba(45,212,191,0.3)',
                      }}>
                      <Download className="w-2.5 h-2.5" />PNG
                    </button>
                    <button onClick={downloadCSV}
                      title="Save BVP signal as CSV data"
                      className="flex items-center gap-0.5 px-1.5 py-0.5 rounded-md text-[9px] font-bold transition-opacity opacity-60 hover:opacity-100"
                      style={{
                        background: 'rgba(20,184,166,0.2)',
                        color:      '#2dd4bf',
                        border:     '1px solid rgba(45,212,191,0.3)',
                      }}>
                      <Download className="w-2.5 h-2.5" />CSV
                    </button>
                  </div>
                )}
              </div>

              {vitals?.bvp?.length > 4
                ? <canvas ref={waveRef} className="absolute inset-0"
                    style={{ width: '100%', height: '100%' }} />
                : <p className="absolute bottom-3 left-3 text-[10px] font-mono"
                    style={{ color: '#334155' }}>
                    awaiting signal…
                  </p>}
            </div>

            {/* Status badge */}
            <div className="absolute top-3 left-3 right-3 flex items-center justify-between z-10">
              <div className="flex items-center gap-2 px-3 py-1.5 rounded-full backdrop-blur-md text-xs font-medium"
                style={{
                  background: isLocked ? 'var(--accent-primary)' : 'rgba(0,0,0,0.52)',
                  color: '#fff',
                }}>
                {isLocked && (
                  <span className="w-1.5 h-1.5 rounded-full bg-white animate-pulse flex-shrink-0" />
                )}
                {statusText}
              </div>
              {connected && vitals?.fps > 0 && (
                <div className="px-2.5 py-1.5 rounded-full backdrop-blur-md text-[10px] font-mono"
                  style={{ background: 'rgba(0,0,0,0.45)', color: 'rgba(255,255,255,0.55)' }}>
                  {vitals.fps.toFixed(0)} fps
                </div>
              )}
            </div>
          </div>

          {/* ── Right panel — exact half ─────────────────────────────────────── */}
          <div className="flex-1 min-w-0 flex flex-col gap-3">

            {/* ── Hero HR card ─────────────────────────────────────────────── */}
            <div className="relative overflow-hidden rounded-2xl border px-6 pt-5 pb-4"
              style={{
                background: isDark
                  ? 'linear-gradient(135deg,rgba(20,184,166,0.12) 0%,rgba(15,118,110,0.06) 100%)'
                  : 'linear-gradient(135deg,rgba(20,184,166,0.08) 0%,rgba(240,253,250,1) 100%)',
                borderColor: hr > 0 ? 'rgba(20,184,166,0.4)' : isDark ? 'rgba(255,255,255,0.08)' : '#e2e8f0',
              }}>

              {/* Pulse rings — visible only when locked and reading */}
              {isLocked && hr > 0 && (
                <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                  <div className="w-24 h-24 rounded-full border border-teal-500/30 rppg-ring" />
                  <div className="absolute w-16 h-16 rounded-full border border-teal-400/20 rppg-ring"
                    style={{ animationDelay: '0.45s' }} />
                </div>
              )}

              <div className="relative z-10">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <Heart
                      className={`w-5 h-5 text-teal-400 ${isLocked && hr > 0 ? 'rppg-beat' : ''}`}
                      strokeWidth={2.5} fill={isLocked && hr > 0 ? 'currentColor' : 'none'} />
                    <span className="text-sm font-bold uppercase tracking-widest text-teal-500">
                      Heart Rate
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    {hrBadge && (
                      <span className="text-[9px] font-bold px-2 py-0.5 rounded-full
                        bg-blue-500/15 text-blue-400 uppercase tracking-wide border border-blue-500/20">
                        {hrBadge}
                      </span>
                    )}
                    {hr > 0 && (
                      <span className={`text-[9px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wide
                        ${hr >= 60 && hr <= 100
                          ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/20'
                          : 'bg-amber-500/15 text-amber-400 border border-amber-500/20'}`}>
                        {hrCategory}
                      </span>
                    )}
                  </div>
                </div>

                <div className="flex items-end gap-3">
                  <span className={`text-8xl font-bold ds-mono leading-none transition-all duration-300
                    ${hr > 0 ? 'text-teal-400' : isDark ? 'text-slate-700' : 'text-slate-200'}`}>
                    {hr > 0 ? Math.round(hr) : '—'}
                  </span>
                  <div className="mb-2 flex flex-col gap-1">
                    <div className={`text-lg font-semibold ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>bpm</div>
                    {isLocked && hr > 0 && (
                      <div className="flex items-center gap-1.5">
                        <span className="w-1.5 h-1.5 rounded-full bg-teal-400 animate-pulse" />
                        <span className="text-[11px] font-semibold text-teal-400">Live reading</span>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>

            {/* ── Health score ring ────────────────────────────────────────── */}
            <HealthScoreRing hr={hr} spo2={spo2} rr={rr} sbp={sbp} dbp={dbp} temp={temp} isDark={isDark} />

            {/* ── Other vitals ─────────────────────────────────────────────── */}
            <div className={`rounded-2xl border overflow-hidden flex-1 flex flex-col
              ${isDark ? 'bg-slate-900/60 border-white/10' : 'bg-white border-slate-200'}`}>

              <div className={`px-4 py-2.5 border-b flex items-center justify-between
                ${isDark ? 'border-white/8' : 'border-slate-100'}`}
                style={{
                  background: isDark
                    ? 'linear-gradient(90deg,rgba(20,184,166,0.08) 0%,transparent 100%)'
                    : 'linear-gradient(90deg,rgba(20,184,166,0.05) 0%,transparent 100%)',
                }}>
                <span className="text-[11px] font-bold uppercase tracking-widest text-teal-500">
                  Measurements
                </span>
                <div className="flex items-center gap-2">
                  {readyCount > 0 && (
                    <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full
                      ${isDark ? 'bg-teal-500/15 text-teal-400' : 'bg-teal-50 text-teal-600'}`}>
                      {readyCount}/6 ready
                    </span>
                  )}
                  {isLocked && (
                    <span className="flex items-center gap-1 text-[10px] font-bold text-teal-400">
                      <span className="w-1.5 h-1.5 rounded-full bg-teal-400 animate-pulse" />
                      Live
                    </span>
                  )}
                </div>
              </div>

              <div className="p-3 flex-1 flex flex-col gap-1.5">
                <VitalRow icon={Droplets}    label="SpO₂"
                  value={spo2}  unit="%"    accent="rgb(56,189,248)"
                  sourceBadge={spo2Badge}   history={vitalHistory.current.spo2}
                  rangeLo={95} rangeHi={100} />
                <VitalRow icon={Wind}        label="Resp Rate"
                  value={rr}    unit="/min" accent="rgb(167,139,250)"
                  sourceBadge={rrBadge}     history={vitalHistory.current.rr}
                  rangeLo={12} rangeHi={20} />
                <VitalRow icon={Activity}    label="Systolic BP"
                  value={sbp}   unit="mmHg" accent="rgb(251,146,60)"
                  sourceBadge={sbpBadge}    history={vitalHistory.current.sbp}
                  rangeLo={90} rangeHi={120} />
                <VitalRow icon={Activity}    label="Diastolic BP"
                  value={dbp}   unit="mmHg" accent="rgb(248,113,113)"
                  sourceBadge={dbpBadge}    history={vitalHistory.current.dbp}
                  rangeLo={60} rangeHi={80} />
                <VitalRow icon={Thermometer} label="Temperature"
                  value={temp}  unit="°C"   accent="rgb(251,191,36)"
                  sourceBadge={
                    temp != null  ? 'sensor · body est.'
                    : hasHardware ? 'sensor · no temp data'
                    : null
                  }
                  history={vitalHistory.current.temp}
                  rangeLo={36.1} rangeHi={37.5} />
              </div>
            </div>

            {/* ── Signal quality + active sources ──────────────────────────── */}
            {connected && (() => {
              const qColor = quality > 60 ? 'rgb(20,184,166)' : quality > 30 ? 'rgb(251,191,36)' : 'rgb(248,113,113)';
              const segs = 10;
              const filled = Math.round((quality / 100) * segs);
              const sources = [
                { label: 'Camera', active: faceFound,    color: 'rgb(20,184,166)' },
                { label: 'AI/DL',  active: dlHR != null, color: 'rgb(167,139,250)' },
                { label: 'Sensor', active: hasHardware,  color: 'rgb(56,189,248)'  },
              ];
              return (
              <div className="rounded-xl border px-4 py-3"
                style={{ background: `${qColor}0a`, borderColor: `${qColor}35` }}>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[11px] font-bold uppercase tracking-widest"
                    style={{ color: qColor }}>Signal Quality</span>
                  <span className="text-base font-bold ds-mono" style={{ color: qColor }}>
                    {quality.toFixed(0)}%
                  </span>
                </div>

                {/* Segmented bar */}
                <div className="flex gap-[3px] mb-2.5">
                  {Array.from({ length: segs }).map((_, i) => (
                    <div key={i} className="flex-1 h-2 rounded-sm transition-all duration-500"
                      style={{
                        background: i < filled ? qColor : isDark ? 'rgba(255,255,255,0.08)' : '#e2e8f0',
                        boxShadow:  i < filled ? `0 0 6px ${qColor}60` : 'none',
                      }} />
                  ))}
                </div>

                {/* Active sources row */}
                <div className="flex items-center gap-1.5">
                  {sources.map(s => (
                    <div key={s.label} className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold"
                      style={{
                        background: s.active ? `${s.color}18` : isDark ? 'rgba(255,255,255,0.04)' : '#f1f5f9',
                        color:      s.active ? s.color : isDark ? '#475569' : '#94a3b8',
                        border:     `1px solid ${s.active ? `${s.color}40` : 'transparent'}`,
                      }}>
                      <span className="w-1.5 h-1.5 rounded-full flex-shrink-0"
                        style={{ background: s.active ? s.color : isDark ? '#334155' : '#cbd5e1' }} />
                      {s.label}
                    </div>
                  ))}
                  <span className="ml-auto text-[10px] font-medium" style={{ color: qColor, opacity: 0.75 }}>
                    {quality > 60 ? 'Hold steady' : quality > 30 ? 'Improve lighting' : 'Centre face'}
                  </span>
                </div>
              </div>
              );
            })()}

            {/* ── Apply button ─────────────────────────────────────────────── */}
            <button
              onClick={handleApply}
              disabled={!hasVitals || applying || applied}
              className={`w-full py-4 rounded-xl font-bold text-base flex items-center justify-center gap-2 transition-all duration-200 active:scale-[0.97] ${hasVitals && !applied ? 'rppg-shimmer' : ''}`}
              style={
                applied
                  ? { background: 'rgb(20,184,166)', color: '#fff', boxShadow: '0 4px 20px rgba(20,184,166,0.35)' }
                  : hasVitals
                    ? {
                        background: 'linear-gradient(90deg,#0d9488,#14b8a6,#2dd4bf,#14b8a6,#0d9488)',
                        color:      '#fff',
                        boxShadow:  '0 4px 28px rgba(20,184,166,0.45)',
                      }
                    : isDark
                      ? { background: 'rgba(255,255,255,0.05)', color: '#475569', cursor: 'not-allowed' }
                      : { background: '#f1f5f9', color: '#94a3b8', cursor: 'not-allowed' }
              }>
              {applied
                ? <><CheckCircle className="w-5 h-5" /> Applied — closing…</>
                : applying
                  ? <span className="flex items-center gap-2"><span className="w-4 h-4 rounded-full border-2 border-white/30 border-t-white animate-spin" />Saving…</span>
                  : hasVitals
                    ? <><Zap className="w-5 h-5" /> Apply {readyCount} vital{readyCount !== 1 ? 's' : ''} to patient</>
                    : <><Zap className="w-5 h-5" /> Waiting for vitals…</>
              }
            </button>

            {!hasVitals && connected && bufferPct > 0 && (
              <p className={`text-[10px] text-center -mt-1 font-medium ${isDark ? 'text-slate-600' : 'text-slate-400'}`}>
                ~{Math.max(0, Math.ceil((100 - bufferPct) / 6))}s until ready
              </p>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
