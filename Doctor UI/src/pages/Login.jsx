import { useEffect, useRef, useState } from 'react';
import styles from './Login.module.css';
import '../styles/colors_and_type.css';
import { useAuth } from '../context/AuthContext';

export default function Login() {
  const cardRef = useRef(null);
  const wrapRef = useRef(null);

  const { signIn } = useAuth();
  const [email, setEmail]               = useState('');
  const [password, setPassword]         = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [keepSignedIn, setKeepSignedIn] = useState(true);
  const [loading, setLoading]           = useState(false);
  const [errorMsg, setErrorMsg]         = useState('');

  // Request access modal
  const [showAccess, setShowAccess]     = useState(false);
  const [accessDone, setAccessDone]     = useState(false);
  const [reqName, setReqName]           = useState('');
  const [reqEmail, setReqEmail]         = useState('');
  const [reqRole, setReqRole]           = useState('Doctor');
  const [reqFacility, setReqFacility]   = useState('');

  const handleRequestAccess = (e) => {
    e.preventDefault();
    const subject = encodeURIComponent('ClearPath Access Request');
    const body = encodeURIComponent(
      `Name: ${reqName}\nEmail: ${reqEmail}\nRole: ${reqRole}\nFacility: ${reqFacility}`
    );
    window.location.href = `mailto:access@mhnexus.com?subject=${subject}&body=${body}`;
    setAccessDone(true);
  };

  const closeAccess = () => { setShowAccess(false); setAccessDone(false); setReqName(''); setReqEmail(''); setReqRole('Doctor'); setReqFacility(''); };

  // 3D mouse-tilt — matches Landing Page.html script exactly
  useEffect(() => {
    if (matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const wrap = wrapRef.current;
    const card = cardRef.current;
    if (!wrap || !card) return;

    const MAX_TILT = 8;
    const LIFT = 6;
    let raf = 0;

    const setTilt = (rx, ry, lift) => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => {
        card.style.transform = `rotateX(${rx.toFixed(2)}deg) rotateY(${ry.toFixed(2)}deg) translateZ(${lift}px)`;
      });
    };

    const onMove = (e) => {
      const r = card.getBoundingClientRect();
      const cx = e.clientX - r.left - r.width  / 2;
      const cy = e.clientY - r.top  - r.height / 2;
      setTilt((cy / (r.height / 2)) * -MAX_TILT, (cx / (r.width / 2)) * MAX_TILT, LIFT);
    };
    const onLeave = () => setTilt(0, 0, 0);

    wrap.addEventListener('mousemove', onMove);
    wrap.addEventListener('mouseleave', onLeave);
    return () => {
      cancelAnimationFrame(raf);
      wrap.removeEventListener('mousemove', onMove);
      wrap.removeEventListener('mouseleave', onLeave);
    };
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErrorMsg('');
    setLoading(true);
    try {
      await signIn(email, password);
      // Gate in App.jsx flips automatically on session change
    } catch (err) {
      setErrorMsg(err.message || 'Sign in failed. Check your credentials.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={styles.page}>

      {/* ====== LEFT — BRAND PANEL ====== */}
      <section className={styles.left} aria-label="MHNexus product brand panel">
        <div className={styles.orb + ' ' + styles.orbA} />
        <div className={styles.orb + ' ' + styles.orbB} />

        {/* Topbar */}
        <header className={styles.topbar}>
          <div className={styles.brand}>
            <img
              className={styles.logo}
              src="/UniMalaya.png"
              alt="University of Malaya"
            />
            <span className={styles.sep} aria-hidden="true" />
            <img
              className={`${styles.logo} ${styles.logoMh}`}
              src="/MHNexus.png"
              alt="MHNexus"
            />
          </div>
        </header>

        {/* Hero */}
        <div className={styles.hero}>
          <div className={styles.wordmark}>
            ClearPath<span className={styles.dotEnd}>.</span>
          </div>
          <span className={styles.eyebrow}>
            Evidence-Based Clinical Practice Guidance System
          </span>
          <h1 className={styles.heroH1}>
            Clinician's <em>second opinion</em>, at the speed of a glance.
          </h1>

          {/* Animated ECG strip */}
          <div className={styles.ecg} aria-hidden="true">
            <span className={styles.ecgLabel}>LIVE · ECG II</span>
            <svg viewBox="0 0 700 88" preserveAspectRatio="none">
              <path
                className={styles.ecgPath}
                d="
                  M 0 44 L 60 44 L 80 44 L 95 40 L 110 48 L 125 44 L 160 44
                  L 180 44 L 195 28 L 205 64 L 215 8  L 225 78 L 235 44
                  L 280 44 L 310 44 L 325 38 L 340 50 L 355 44 L 400 44
                  L 420 44 L 435 28 L 445 64 L 455 8  L 465 78 L 475 44
                  L 520 44 L 555 44 L 570 40 L 585 48 L 600 44 L 700 44
                "
              />
            </svg>
            <div className={styles.scan} />
            <div className={styles.ecgVal}>
              HR <b>72</b> bpm &nbsp;·&nbsp; SpO<sub>2</sub> <b>98</b>%
            </div>
          </div>

          {/* Feature badges */}
          <div className={styles.badgeRow}>
            <span className={styles.badge}>
              <span className={styles.badgeDot} />
              Clinical Practice Guidelines
            </span>
            <span className={styles.badge}>
              <span className={styles.badgeDot} />
              Agentic Pipeline
            </span>
            <span className={styles.badge}>
              <span className={styles.badgeDot} />
              Transparent Reasoning
            </span>
          </div>
        </div>
      </section>

      {/* ====== RIGHT — LOGIN PANEL ====== */}
      <section className={styles.right} aria-label="Sign in">
        {/* Perspective wrapper for 3D tilt */}
        <div className={styles.cardWrap} ref={wrapRef}>
          <div className={styles.card} ref={cardRef}>

            {/* Breathing halo */}
            <span className={styles.halo} aria-hidden="true" />

            {/* Traveling beams + corner pulses */}
            <div className={styles.beams} aria-hidden="true">
              <span className={`${styles.beam} ${styles.beamTop}`} />
              <span className={`${styles.beam} ${styles.beamRgt}`} />
              <span className={`${styles.beam} ${styles.beamBot}`} />
              <span className={`${styles.beam} ${styles.beamLft}`} />
              <span className={`${styles.corner} ${styles.cornerTl}`} />
              <span className={`${styles.corner} ${styles.cornerTr}`} />
              <span className={`${styles.corner} ${styles.cornerBr}`} />
              <span className={`${styles.corner} ${styles.cornerBl}`} />
            </div>

            {/* Form */}
            <form className={styles.auth} onSubmit={handleSubmit} autoComplete="off">
              <h2 className={styles.authH2}>Welcome Back</h2>
              <p className={styles.authSub}>
                Sign in to access your{' '}
                <span className={styles.authSubBrand}>ClearPath</span>{' '}
                workspace
              </p>

              {/* Email */}
              <div className={styles.field}>
                <label className={styles.fieldLabel} htmlFor="lp-email">
                  Email
                </label>
                <div className={styles.inputWrap}>
                  <svg className={styles.leadIcon} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                    <rect x="3" y="5" width="18" height="14" rx="2" />
                    <path d="M3 7l9 6 9-6" />
                  </svg>
                  <input
                    id="lp-email"
                    type="email"
                    inputMode="email"
                    placeholder="dr.tay@mhnexus.com"
                    autoComplete="username"
                    required
                    className={styles.inputField}
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                  />
                </div>
              </div>

              {/* Password */}
              <div className={styles.field}>
                <label className={styles.fieldLabel} htmlFor="lp-password">
                  <span>Password</span>
                  <a href="#" className={styles.forgot}>Forgot password?</a>
                </label>
                <div className={styles.inputWrap}>
                  <svg className={styles.leadIcon} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                    <rect x="3" y="11" width="18" height="11" rx="2" />
                    <path d="M7 11V7a5 5 0 0 1 10 0v4" />
                  </svg>
                  <input
                    id="lp-password"
                    type={showPassword ? 'text' : 'password'}
                    placeholder="••••••••••"
                    autoComplete="current-password"
                    required
                    className={styles.inputField}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                  />
                  <button
                    type="button"
                    className={styles.toggleEye}
                    aria-label={showPassword ? 'Hide password' : 'Show password'}
                    onClick={() => setShowPassword((v) => !v)}
                  >
                    {showPassword ? (
                      /* eye-off */
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94" />
                        <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19" />
                        <line x1="1" y1="1" x2="23" y2="23" />
                      </svg>
                    ) : (
                      /* eye */
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8S1 12 1 12z" />
                        <circle cx="12" cy="12" r="3" />
                      </svg>
                    )}
                  </button>
                </div>
              </div>

              {/* Keep signed in */}
              <div className={styles.rowBetween}>
                <label className={styles.checkLabel}>
                  <span
                    className={`${styles.checkBox} ${keepSignedIn ? styles.checkBoxChecked : ''}`}
                    onClick={() => setKeepSignedIn((v) => !v)}
                    role="checkbox"
                    aria-checked={keepSignedIn}
                    tabIndex={0}
                    onKeyDown={(e) => e.key === ' ' && setKeepSignedIn((v) => !v)}
                  >
                    {keepSignedIn && (
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M5 12l5 5L20 7" />
                      </svg>
                    )}
                  </span>
                  Keep me signed in for 8 hours
                </label>
              </div>

              {/* Inline error */}
              {errorMsg && (
                <p style={{ color: 'var(--danger, #ef4444)', fontSize: 13, marginBottom: 12 }}>
                  {errorMsg}
                </p>
              )}

              {/* Submit */}
              <button
                type="submit"
                className={styles.btnPrimary}
                disabled={loading}
              >
                {loading ? 'Signing in…' : 'Sign in'}
                {!loading && (
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                    <path d="M5 12h14" />
                    <path d="M12 5l7 7-7 7" />
                  </svg>
                )}
              </button>
            </form>
          </div>
        </div>

        {/* Footer */}
        <div className={styles.rightFoot}>
          <button
            className={styles.rightFootLink}
            onClick={() => setShowAccess(true)}
            style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}
          >
            New here? <b style={{ color: 'var(--primary-700)' }}>Request access</b>
          </button>
        </div>
      </section>

      {/* ====== REQUEST ACCESS MODAL ====== */}
      {showAccess && (
        <div
          onClick={(e) => e.target === e.currentTarget && closeAccess()}
          style={{
            position: 'fixed', inset: 0, zIndex: 200,
            display: 'flex', alignItems: 'flex-end', justifyContent: 'center',
            background: 'rgba(15,23,42,0.45)', backdropFilter: 'blur(4px)',
          }}
        >
          <style>{`@keyframes slideUp { from { transform: translateY(100%); opacity: 0; } to { transform: none; opacity: 1; } }`}</style>
          <div style={{
            width: '100%', maxWidth: 480,
            background: 'var(--surface, #fff)',
            borderRadius: '20px 20px 0 0',
            padding: '32px 32px 40px',
            boxShadow: '0 -8px 40px rgba(0,0,0,.18)',
            animation: 'slideUp .28s cubic-bezier(.22,.68,0,1.2) both',
          }}>
            {accessDone ? (
              <div style={{ textAlign: 'center', padding: '24px 0' }}>
                <div style={{ fontSize: 40, marginBottom: 12 }}>✅</div>
                <h3 style={{ fontSize: 20, fontWeight: 700, margin: '0 0 8px', color: 'var(--fg-primary)' }}>Request sent!</h3>
                <p style={{ fontSize: 14, color: 'var(--fg-secondary)', margin: '0 0 24px' }}>
                  Your mail client should have opened. We'll review your request and be in touch within 1–2 business days.
                </p>
                <button onClick={closeAccess} className={styles.btnPrimary}>Close</button>
              </div>
            ) : (
              <>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 24 }}>
                  <div>
                    <h3 style={{ fontSize: 22, fontWeight: 700, margin: '0 0 4px', color: 'var(--fg-primary)', letterSpacing: '-.02em' }}>
                      Apply for Access
                    </h3>
                    <p style={{ fontSize: 13, color: 'var(--fg-secondary)', margin: 0 }}>
                      We'll review and onboard you within 1–2 business days.
                    </p>
                  </div>
                  <button
                    onClick={closeAccess}
                    aria-label="Close"
                    style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 20, color: 'var(--fg-muted, #94a3b8)', lineHeight: 1, padding: '2px 4px' }}
                  >✕</button>
                </div>

                <form onSubmit={handleRequestAccess} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                  <div className={styles.field} style={{ marginBottom: 0 }}>
                    <label className={styles.fieldLabel}>Full name</label>
                    <div className={styles.inputWrap}>
                      <input className={styles.inputField} type="text" placeholder="Dr. Wong Kin Meng" required
                        value={reqName} onChange={(e) => setReqName(e.target.value)} />
                    </div>
                  </div>

                  <div className={styles.field} style={{ marginBottom: 0 }}>
                    <label className={styles.fieldLabel}>Work email</label>
                    <div className={styles.inputWrap}>
                      <input className={styles.inputField} type="email" placeholder="dr.wong@hospital.gov.my" required
                        value={reqEmail} onChange={(e) => setReqEmail(e.target.value)} />
                    </div>
                  </div>

                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                    <div className={styles.field} style={{ marginBottom: 0 }}>
                      <label className={styles.fieldLabel}>Role</label>
                      <div className={styles.inputWrap}>
                        <select className={styles.inputField} value={reqRole} onChange={(e) => setReqRole(e.target.value)} style={{ cursor: 'pointer' }}>
                          <option>Doctor</option>
                          <option>Specialist</option>
                          <option>Nurse</option>
                          <option>Medical Officer</option>
                          <option>Administrator</option>
                        </select>
                      </div>
                    </div>
                    <div className={styles.field} style={{ marginBottom: 0 }}>
                      <label className={styles.fieldLabel}>Facility</label>
                      <div className={styles.inputWrap}>
                        <input className={styles.inputField} type="text" placeholder="Hospital / Clinic"
                          value={reqFacility} onChange={(e) => setReqFacility(e.target.value)} />
                      </div>
                    </div>
                  </div>

                  <button type="submit" className={styles.btnPrimary} style={{ marginTop: 4 }}>
                    Send request
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                      <path d="M5 12h14" /><path d="M12 5l7 7-7 7" />
                    </svg>
                  </button>
                </form>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
