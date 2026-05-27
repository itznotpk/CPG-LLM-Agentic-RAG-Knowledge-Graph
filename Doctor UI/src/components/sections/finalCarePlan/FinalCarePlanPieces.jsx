import React from 'react';
/* Final Care Plan — Stage 4 clinical document */





/* ---------- Icons (SVG inline) ---------- */
export const fcpIcons = {
  check: (p) => <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" {...p}><polyline points="20 6 9 17 4 12" /></svg>,
  download: (p) => <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="7 10 12 15 17 10" /><line x1="12" y1="15" x2="12" y2="3" /></svg>,
  print: (p) => <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" {...p}><polyline points="6 9 6 2 18 2 18 9" /><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2" /><rect x="6" y="14" width="12" height="8" /></svg>,
  send: (p) => <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" {...p}><line x1="22" y1="2" x2="11" y2="13" /><polygon points="22 2 15 22 11 13 2 9 22 2" /></svg>,
  edit: (p) => <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="M12 20h9" /><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4z" /></svg>,
  mail: (p) => <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" /><polyline points="22 6 12 13 2 6" /></svg>,
  share: (p) => <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" {...p}><circle cx="18" cy="5" r="3" /><circle cx="6" cy="12" r="3" /><circle cx="18" cy="19" r="3" /><line x1="8.59" y1="13.51" x2="15.42" y2="17.49" /><line x1="15.41" y1="6.51" x2="8.59" y2="10.49" /></svg>,
  alert: (p) => <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" /><path d="M12 9v4" /><path d="M12 17h.01" /></svg>
};

/* ============================================================
   LETTERHEAD
   ============================================================ */
export function Letterhead({ provider, encounter }) {
  return (
    <div className="letterhead">
      <div className="crest">M</div>
      <div>
        <div className="font-display italic text-teal-700 text-2xl leading-none tracking-tight mb-1">ClearPath.</div>
        <div className="hospital-tagline">{provider.clinic} · No.12 Jalan Bukit Damansara, KL</div>
      </div>
      <div className="doc-meta">
        <div>{encounter.id}</div>
        <div>{encounter.date} · {encounter.time}</div>
      </div>
    </div>);

}

/* ============================================================
   PATIENT BANNER + ALLERGY STRIP
   ============================================================ */
export function PatientBanner({ patient, encounter, allergies, provider }) {
  const patientSubParts = [
    patient.age ? `${patient.age} y` : null,
    patient.sex || patient.gender,
    patient.ethnicity
  ].filter(Boolean);
  const patientSub = patientSubParts.join(' · ');

  const nsnLast4 = patient.nsn ? patient.nsn.slice(-4) : '5821';
  const displayMrn = patient.mrn || `MRN-${nsnLast4}`;

  return (
    <>
      <div className="patient-banner">
        <div className="field">
          <div className="field-label">Patient</div>
          <div className="field-value">{patient.name}</div>
          {patientSub && <div className="field-sub">{patientSub}</div>}
        </div>
        <div className="field">
          <div className="field-label">MRN</div>
          <div className="field-value">{displayMrn}</div>
          <div className="field-sub">NRIC last 4: ····{nsnLast4}</div>
        </div>
        <div className="field">
          <div className="field-label">Encounter</div>
          <div className="field-value">{encounter.type}</div>
          {encounter.duration && encounter.duration !== '—' && (
            <div className="field-sub">{encounter.duration}</div>
          )}
        </div>
        <div className="field">
          <div className="field-label">Provider</div>
          <div className="field-value">{provider?.name || 'Dr. Aiman Halim'}</div>
          <div className="field-sub">{provider?.mmcNo ? `MMC-${provider.mmcNo.replace(/^MMC-/i, '')}` : 'MMC-48921'}</div>
        </div>
      </div>
      {allergies && allergies.length > 0 &&
      <div className="allergy-strip">
          {fcpIcons.alert({ stroke: '#b91c1c' })}
          <span className="allergy-label">Known Allergies</span>
          <div className="allergy-chips">
            {allergies.map((a, i) => <span key={i} className="allergy-chip">{a}</span>)}
          </div>
        </div>
      }
    </>);

}

/* ============================================================
   SOAP SECTION SHELL
   ============================================================ */
export function SoapSection({ letter, title, desc, children, id }) {
  return (
    <section className="soap-section" id={id}>
      <div className="soap-header">
        <div className="soap-letter">{letter}</div>
        <h3>{title}</h3>
        {desc && <span className="section-desc">{desc}</span>}
      </div>
      <div className="soap-rule" />
      <div className="soap-content">{children}</div>
    </section>);

}

/* ============================================================
   VITALS GRID
   ============================================================ */
export function VitalsTable({ vitals }) {
  const cells = [
  { name: 'BP', val: `${vitals.bpSystolic}/${vitals.bpDiastolic}`, unit: 'mmHg', abn: vitals.bpSystolic > 140 || vitals.bpDiastolic > 90 },
  { name: 'HR', val: vitals.hr, unit: 'bpm' },
  { name: 'SpO₂', val: vitals.spo2, unit: '%' },
  { name: 'Temp', val: vitals.temp, unit: '°C' },
  { name: 'Weight', val: vitals.weight, unit: 'kg' },
  { name: 'BMI', val: vitals.bmi, unit: 'kg/m²', abn: vitals.bmi > 25 }];

  return (
    <div className="vitals">
      {cells.map((c, i) =>
      <div key={i} className={`v ${c.abn ? 'abnormal' : ''}`}>
          <div className="v-name">{c.name}</div>
          <div className="v-val">{c.val}<span style={{ fontSize: 10, fontWeight: 400, color: 'var(--fg-muted)', marginLeft: 4 }}>{c.unit}</span></div>
          {c.abn && <div className="v-trend" style={{ color: '#b91c1c' }}>Above range</div>}
        </div>
      )}
    </div>);

}

/* ============================================================
   ASSESSMENT — diagnoses
   ============================================================ */
export function AssessmentList({ diagnoses }) {
  return (
    <>
      <div className="dx-list">
        {diagnoses.map((d, i) =>
        <div key={i} className="dx-item">
            <div className="dx-num">{i + 1}</div>
            <div>
              <div className="dx-name">{d.name}</div>
              {d.note && <div style={{ fontSize: 12, color: 'var(--fg-muted)', marginTop: 2 }}>{d.note}</div>}
            </div>
            <span className="dx-icd">{d.icdCode}</span>
          </div>
        )}
      </div>
    </>);

}

/* ============================================================
   MEDICATION TABLE (PLAN > 1)
   ============================================================ */
export function MedTable({ meds }) {
  const rows = [
  ...(meds.stop || []).map((m) => ({ ...m, action: 'stop' })),
  ...(meds.start || []).map((m) => ({ ...m, action: 'start' })),
  ...(meds.change || []).map((m) => ({ ...m, action: 'change' })),
  ...(meds.continue || []).map((m) => ({ ...m, action: 'continue' }))];

  return (
    <table className="tbl">
      <thead>
        <tr>
          <th style={{ width: 80 }}>Action</th>
          <th>Medication</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((m) =>
        <tr key={m.action + m.id}>
            <td><span className={`atag ${m.action}`}>{m.action}</span></td>
            <td>
              <div className="name">{m.name}</div>
              <div className="meta">
                {m.action === 'change' ?
              <><span className="strike">{m.previousDose}</span><span className="arrow">→</span><span className="new">{m.newDose}</span></> :
              m.dose}
              </div>
            </td>
          </tr>
        )}
      </tbody>
    </table>);

}

/* ============================================================
   GENERIC PLAN TABLE (Investigations, Monitoring, Referrals)
   ============================================================ */
export function PlanTable({ headers, rows }) {
  return (
    <table className="tbl">
      <thead>
        <tr>{headers.map((h, i) => <th key={i} style={h.width ? { width: h.width } : undefined}>{h.label}</th>)}</tr>
      </thead>
      <tbody>
        {rows.map((r, i) =>
        <tr key={i}>{r.map((c, j) => <td key={j}>{c}</td>)}</tr>
        )}
      </tbody>
    </table>);

}

/* ============================================================
   SUBSECTION WRAPPER
   ============================================================ */
export function PlanSub({ num, title, count, children }) {
  return (
    <div className="plan-subsection">
      <div className="plan-h4">
        <span className="plan-num">{num}</span>
        <h4>{title}</h4>
        {count != null && <span className="count">{count}</span>}
      </div>
      {children}
    </div>);

}

/* ============================================================
   SIGNATURE BLOCK
   ============================================================ */
export function SignatureBlock({ provider, signed }) {
  return (
    <div className="signature">
      <div className="sig-block">
        <div className="sig-title">Provider Signature</div>
        <div className="sig-line">{signed ? 'A. Halim' : ''}</div>
        <dl className="sig-info">
          <dt>Name</dt><dd>{provider.name}</dd>
          <dt>Role</dt><dd>{provider.role}</dd>
          <dt>MMC No.</dt><dd className="mono">{provider.mmcNo}</dd>
          <dt>Date</dt><dd className="mono">{signed ? '25 May 2026 · 10:42' : '—'}</dd>
        </dl>
      </div>
      <div className="sig-block">
        <div className="sig-title">Patient Acknowledgement</div>
        <div className="sig-line"></div>
        <dl className="sig-info">
          <dt>Name</dt><dd>Mohd Faizal bin Hassan</dd>
          <dt>NRIC</dt><dd className="mono">·······5821</dd>
          <dt>Witnessed by</dt><dd>—</dd>
          <dt>Date</dt><dd className="mono">—</dd>
        </dl>
      </div>
    </div>);

}

