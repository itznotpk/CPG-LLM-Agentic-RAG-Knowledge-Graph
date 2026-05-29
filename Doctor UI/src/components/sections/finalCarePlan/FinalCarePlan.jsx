import React, { useState, useRef, useImperativeHandle, forwardRef } from 'react';
import { useTheme } from '../../../context/ThemeContext';
import { Letterhead, PatientBanner, SoapSection, VitalsTable, AssessmentList, MedTable, PlanTable, PlanSub, fcpIcons } from './FinalCarePlanPieces';
/* Final Care Plan — Stage 4 app */

const REMOVE_BTN = {
  background: 'none', border: 'none', cursor: 'pointer',
  color: '#ef4444', fontSize: 16, lineHeight: 1, padding: '0 4px', flexShrink: 0,
};

const ADD_BTN = {
  marginTop: 6, fontSize: 12, fontWeight: 600,
  color: 'var(--accent-primary)', background: 'rgba(16,185,129,0.08)',
  border: '1px solid rgba(16,185,129,0.3)', borderRadius: 6,
  padding: '3px 10px', cursor: 'pointer',
};

const INLINE_EDIT = {
  background: 'transparent', border: 'none', borderBottom: '1px dashed #cbd5e1',
  borderRadius: 0, padding: '2px 0', fontSize: 13, fontFamily: 'inherit',
  outline: 'none', width: '100%',
};

/* ── Editable plain text / textarea ── */
function EditableText({ value, onChange, editing, multiline = false, className = '', style = {} }) {
  if (!editing) {
    return multiline
      ? <p className={`narrative ${className}`} style={style}>{value}</p>
      : <span className={className} style={style}>{value}</span>;
  }
  const base = { ...INLINE_EDIT, lineHeight: 1.6, ...style };
  return multiline
    ? <textarea rows={4} value={value} onChange={e => onChange(e.target.value)}
        style={{ ...base, resize: 'vertical', display: 'block', borderBottom: 'none', border: '1px dashed #cbd5e1', borderRadius: 6, padding: '8px' }} className={className} />
    : <input type="text" value={value} onChange={e => onChange(e.target.value)}
        style={{ ...base, display: 'inline-block' }} className={className} />;
}

/* ── Editable bullet list (strings or {category,goal} objects) ── */
function EditableBullets({ items, onChange, editing }) {
  if (!editing) {
    return (
      <div className="bullets">
        {items.map((l, i) => (
          <div key={i} className="bullet">
            <span className="marker">•</span>
            <span>{typeof l === 'object'
              ? (l.category
                ? <><span className="item-title">{l.category}</span><span className="item-subtitle">{l.goal}</span></>
                : <SplitPlanText text={l.goal} />)
              : <SplitPlanText text={l} />}
            </span>
          </div>
        ))}
      </div>
    );
  }
  const INLINE_TITLE = {
    background: 'transparent', border: 'none', borderBottom: '1px dashed #cbd5e1',
    borderRadius: 0, padding: '2px 0', fontSize: 13, fontWeight: 600, fontFamily: 'inherit',
    outline: 'none', width: '100%', color: '#1e293b',
  };
  const INLINE_SUB = {
    background: 'transparent', border: 'none', borderBottom: '1px dashed #e2e8f0',
    borderRadius: 0, padding: '2px 0', fontSize: 12, fontFamily: 'inherit',
    outline: 'none', width: '100%', color: '#64748b',
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      {items.map((l, i) => {
        const raw = typeof l === 'object' ? `${l.category}: ${l.goal}` : l;
        const dashMatch = raw.match(/\s+(?:—|-|–)\s+/);
        const title = dashMatch ? raw.slice(0, dashMatch.index).trim() : raw;
        const subtitle = dashMatch ? raw.slice(dashMatch.index + dashMatch[0].length).trim() : '';

        return (
          <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 8, padding: '4px 0', borderBottom: '1px solid #f1f5f9' }}>
            <span style={{ color: 'var(--accent-primary)', fontWeight: 700, flexShrink: 0, marginTop: 2 }}>•</span>
            <div style={{ flex: 1, minWidth: 0 }}>
              <input type="text" value={title}
                onChange={e => {
                  const next = [...items];
                  const newVal = subtitle ? `${e.target.value} — ${subtitle}` : e.target.value;
                  if (typeof l === 'object') {
                    const ci = newVal.indexOf(': ');
                    next[i] = ci > -1
                      ? { ...l, category: newVal.slice(0, ci), goal: newVal.slice(ci + 2) }
                      : { ...l, goal: newVal };
                  } else { next[i] = newVal; }
                  onChange(next);
                }}
                style={INLINE_TITLE}
                placeholder="Title"
              />
              <input type="text" value={subtitle}
                onChange={e => {
                  const next = [...items];
                  const newVal = e.target.value ? `${title} — ${e.target.value}` : title;
                  if (typeof l === 'object') {
                    const ci = newVal.indexOf(': ');
                    next[i] = ci > -1
                      ? { ...l, category: newVal.slice(0, ci), goal: newVal.slice(ci + 2) }
                      : { ...l, goal: newVal };
                  } else { next[i] = newVal; }
                  onChange(next);
                }}
                style={INLINE_SUB}
                placeholder="Description"
              />
            </div>
            <button onClick={() => onChange(items.filter((_, j) => j !== i))} style={{ ...REMOVE_BTN, marginTop: 4 }}>×</button>
          </div>
        );
      })}
      <button onClick={() => onChange([...items, typeof items[0] === 'object' ? { category: 'New', goal: '' } : ''])}
        style={{ ...ADD_BTN, alignSelf: 'flex-start' }}>+ Add item</button>
    </div>
  );
}

/* ── Editable table: generic rows of field arrays ── */
function EditableTable({ headers, rows, onChange, editing, buildEmpty, renderView }) {
  if (!editing) {
    return (
      <table className="tbl">
        <thead><tr>{headers.map((h, i) => <th key={i} style={h.width ? { width: h.width } : undefined}>{h.label}</th>)}</tr></thead>
        <tbody>{rows.map((r, i) => <tr key={i}>{renderView(r, i).map((cell, j) => <td key={j}>{cell}</td>)}</tr>)}</tbody>
      </table>
    );
  }
  const INLINE = {
    background: 'transparent', border: 'none', borderBottom: '1px dashed #cbd5e1',
    borderRadius: 0, padding: '2px 0', fontSize: 13, fontFamily: 'inherit',
    outline: 'none', width: '100%',
  };
  return (
    <div>
      <table className="tbl">
        <thead>
          <tr>
            {headers.map((h, i) => <th key={i} style={h.width ? { width: h.width } : undefined}>{h.label}</th>)}
            <th style={{ width: 30 }}></th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i}>
              {headers.map((h, j) => (
                <td key={j} style={{ verticalAlign: 'top' }}>
                  <input type="text" value={row[h.field] ?? ''} onChange={e => {
                    const next = rows.map((r, ri) => ri === i ? { ...r, [h.field]: e.target.value } : r);
                    onChange(next);
                  }} style={INLINE} />
                </td>
              ))}
              <td style={{ verticalAlign: 'top', paddingTop: 6 }}>
                <button onClick={() => onChange(rows.filter((_, ri) => ri !== i))} style={REMOVE_BTN} title="Remove row">×</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <button onClick={() => onChange([...rows, buildEmpty()])} style={{ ...ADD_BTN, marginTop: 8 }}>+ Add row</button>
    </div>
  );
}

function SplitTitleSubtitle({ text }) {
  const source = text || '';
  const dashIdx = source.indexOf('—');
  if (dashIdx === -1) return <div className="name">{source}</div>;

  const title = source.slice(0, dashIdx).trim();
  const subtitle = source.slice(dashIdx + 1).trim();
  return (
    <div>
      <div className="name">{title}</div>
      {subtitle && <div className="desc" style={{ maxWidth: 'none', width: '100%' }}>{subtitle}</div>}
    </div>
  );
}

function ReferralTitleSubtitle({ text }) {
  const source = String(text || '')
    .replace(/\s*\((routine|urgent|consider|today|semi-urgent|prompt)\)/gi, '')
    .replace(/\s+/g, ' ')
    .trim();
  const title = source
    .replace(/â€”|Ã¢â‚¬â€|\u2014|\u2013/g, ' - ')
    .split(/\s+-\s+|:/)[0]
    .trim();

  return <div className="name">{title}</div>;
}

/* ── Editable medications table ── */
function SplitPlanText({ text }) {
  const planText = String(text || '').replace(/\s+/g, ' ').trim();
  const splitMatch = planText.match(/\s+(?:-|—|–|â€”|Ã¢â‚¬â€|ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â)\s+/);
  if (splitMatch?.index != null) {
    const title = planText.slice(0, splitMatch.index).trim();
    const subtitle = planText.slice(splitMatch.index + splitMatch[0].length).trim();
    return (
      <>
        <span className="item-title">{title}</span>
        {subtitle && <span className="item-subtitle">{subtitle}</span>}
      </>
    );
  }
  if (!planText) return <span></span>;
  const cleanText = String(text || '').replace(/â€”|Ã¢â‚¬â€/g, ' - ');
  const normalised = cleanText.replace(/\u2014|\u2013/g, ' - ');
  const idx = normalised.indexOf(' - ');
  if (idx !== -1) {
    const title = normalised.slice(0, idx).trim();
    const subtitle = normalised.slice(idx + 3).trim();
    return (
      <>
        <span className="item-title">{title}</span>
        {subtitle && <span className="item-subtitle">{subtitle}</span>}
      </>
    );
  }
  const source = text || '';
  const dashIdx = source.indexOf('â€”');
  if (dashIdx === -1) return <span>{source}</span>;

  const title = source.slice(0, dashIdx).trim();
  const subtitle = source.slice(dashIdx + 1).trim();
  return (
    <>
      <span className="item-title">{title}</span>
      {subtitle && <span className="item-subtitle">{subtitle}</span>}
    </>
  );
}

function ShortColonText({ text }) {
  const source = String(text || '')
    .replace(/\s*\[[^\]]+\]/g, '')
    .replace(/â€”|Ã¢â‚¬â€|\u2014|\u2013/g, ' - ')
    .replace(/\s+/g, ' ')
    .trim();
  const colonIdx = source.indexOf(':');
  const dashIdx = source.indexOf(' - ');
  const separatorIdx = colonIdx !== -1 ? colonIdx : dashIdx;

  if (separatorIdx === -1) return <span className="item-title">{source}</span>;

  const title = source.slice(0, separatorIdx).trim();
  const descriptionStart = separatorIdx + (colonIdx !== -1 ? 1 : 3);
  const description = source
    .slice(descriptionStart)
    .split(/\s+-\s+|;\s+|,\s*urgent\b|,\s*emergency\b|\.\s+/i)[0]
    .trim();

  return (
    <>
      <span className="item-title">{title}</span>
      {description && <span className="item-subtitle">{description}</span>}
    </>
  );
}

function EducationList({ items }) {
  return (
    <div className="education-grid">
      {items.map((item, i) => (
        <div key={i} className="education-item">
            <span className="marker"></span>
          <div><SplitPlanText text={item} /></div>
        </div>
      ))}
    </div>
  );
}

function RedFlagList({ items }) {
  return (
    <div className="redflags redflags-compact">
      <h5>{fcpIcons.alert({ stroke: '#991b1b' })} Return immediately if:</h5>
      <div className="redflag-list">
        {items.map((item, i) => (
          <div key={i} className="redflag-item">
            <ShortColonText text={item} />
          </div>
        ))}
      </div>
    </div>
  );
}

function normaliseReferralDepartment(value = '') {
  const text = String(value)
    .replace(/\s*\((routine|urgent|consider|today|semi-urgent|prompt)\)/gi, '')
    .replace(/â€”|Ã¢â‚¬â€|\u2014|\u2013/g, ' - ')
    .replace(/\s+/g, ' ')
    .trim();
  const title = text.split(/\s+-\s+|:/)[0].replace(/^refer(?:ral)?\s+to\s+/i, '').trim();
  const lower = title.toLowerCase();
  const departments = [
    ['cardiologist', 'Cardiology'],
    ['cardiology', 'Cardiology'],
    ['multidisciplinary team', 'Multidisciplinary Team'],
    ['physiotherapy', 'Physiotherapy'],
    ['nephrology', 'Nephrology'],
    ['ophthalmology', 'Ophthalmology'],
    ['dietetics', 'Dietetics'],
    ['psychiatry', 'Psychiatry'],
    ['dentistry', 'Dentistry'],
    ['oral health professional', 'Oral Health Professional'],
    ['bariatric surgery', 'Bariatric Surgery'],
    ['geriatrics', 'Geriatrics'],
    ['endocrinology', 'Endocrinology'],
  ];
  const match = departments.find(([needle]) => lower.includes(needle));
  return match ? match[1] : title;
}

function collapseReferrals(referrals = []) {
  const urgencyRank = { Routine: 1, 'Semi-Urgent': 2, Urgent: 3 };
  const byDepartment = new Map();

  referrals.forEach((ref) => {
    const department = normaliseReferralDepartment(ref.specialty);
    const specialty = `Refer to ${department}`;
    const existing = byDepartment.get(department.toLowerCase());
    if (existing && urgencyRank[existing.urgency] >= urgencyRank[ref.urgency]) return;
    byDepartment.set(department.toLowerCase(), { ...ref, specialty });
  });

  return [...byDepartment.values()]
    .sort((a, b) => (urgencyRank[b.urgency] || 0) - (urgencyRank[a.urgency] || 0))
    .map((ref, i) => ({ ...ref, id: ref.id ?? i + 1 }));
}

function urgencyTagClass(urgency = '') {
  if (String(urgency).toLowerCase().includes('urgent')) return 'stop';
  if (String(urgency).toLowerCase().includes('semi')) return 'change';
  return 'change';
}

function compactSchedule(value = '') {
  const source = String(value || '').trim();
  const text = source.toLowerCase();
  if (!source) return '';

  if (text.includes('weekly until stable')) return 'Weekly -> monthly';
  if (text.includes('every 6 months') && text.includes('amiodarone')) return 'q6 months';
  if (text.includes('each clinic visit')) return 'Each visit';
  if (text.includes('every 3 months') && text.includes('every 6 months')) return 'q3 months -> q6 months';
  if (text.includes('self-monitoring')) return 'Self-monitoring';
  if (text.includes('baseline') && text.includes('annually')) return 'Baseline -> annually';
  if (text.includes('next clinic visit')) return 'Next visit';
  if (text.includes('annually')) return 'Annually';
  if (text.includes('every 6 months')) return 'q6 months';
  if (text.includes('every 3 months')) return 'q3 months';
  if (text.includes('monthly')) return 'Monthly';

  return source.length > 36 ? source.split(/;|, then|, or|, more/i)[0].trim() : source;
}

function EditableMedTable({ meds, onChange, editing }) {
  const rows = [
    ...(meds.stop || []).map(m => ({ ...m, action: 'stop' })),
    ...(meds.start || []).map(m => ({ ...m, action: 'start' })),
    ...(meds.change || []).map(m => ({ ...m, action: 'change' })),
    ...(meds.continue || []).map(m => ({ ...m, action: 'continue' })),
  ];

  const updateRow = (i, field, val) => {
    const next = rows.map((r, ri) => ri === i ? { ...r, [field]: val } : r);
    // re-split back into action buckets
    const buckets = { stop: [], start: [], change: [], continue: [] };
    next.forEach(r => { const { action, ...rest } = r; buckets[action] = [...(buckets[action] || []), rest]; });
    onChange(buckets);
  };

  const removeRow = (i) => {
    const next = rows.filter((_, ri) => ri !== i);
    const buckets = { stop: [], start: [], change: [], continue: [] };
    next.forEach(r => { const { action, ...rest } = r; buckets[action] = [...(buckets[action] || []), rest]; });
    onChange(buckets);
  };

  const addRow = () => {
    const newRow = { id: Date.now(), name: '', dose: '', action: 'start' };
    onChange({ ...meds, start: [...(meds.start || []), newRow] });
  };

  if (!editing) return <MedTable meds={meds} />;

  const EDIT_INLINE = {
    background: 'transparent', border: 'none', borderBottom: '1px dashed #cbd5e1',
    borderRadius: 0, padding: '2px 0', fontSize: 13, fontFamily: 'inherit',
    outline: 'none', width: '100%',
  };

  const ACTION_COLORS = {
    start: { bg: '#dcfce7', color: '#166534', border: '#86efac' },
    stop: { bg: '#fee2e2', color: '#991b1b', border: '#fca5a5' },
    change: { bg: '#fef9c3', color: '#854d0e', border: '#fde047' },
    continue: { bg: '#e0f2fe', color: '#075985', border: '#7dd3fc' },
  };

  return (
    <div>
      <table className="tbl" style={{ tableLayout: 'fixed' }}>
        <thead>
          <tr>
            <th style={{ width: 100 }}>Action</th>
            <th>Medication</th>
            <th style={{ width: 30 }}></th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => {
            const ac = ACTION_COLORS[row.action] || ACTION_COLORS.start;
            return (
              <tr key={i}>
                <td style={{ verticalAlign: 'top', paddingTop: 10 }}>
                  <select value={row.action} onChange={e => updateRow(i, 'action', e.target.value)}
                    style={{
                      appearance: 'none', WebkitAppearance: 'none',
                      background: ac.bg, color: ac.color, border: `1px solid ${ac.border}`,
                      borderRadius: 4, padding: '3px 8px', fontSize: 11,
                      fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em',
                      cursor: 'pointer', outline: 'none', width: '100%',
                    }}>
                    {['start','stop','change','continue'].map(a => <option key={a} value={a}>{a}</option>)}
                  </select>
                </td>
                <td style={{ verticalAlign: 'top', padding: '6px 8px' }}>
                  <input type="text" value={row.name || ''} onChange={e => updateRow(i, 'name', e.target.value)}
                    style={{ ...EDIT_INLINE, fontWeight: 600, fontSize: 14 }} placeholder="Drug name" />
                  <input type="text" value={row.dose || row.newDose || ''} onChange={e => updateRow(i, row.action === 'change' ? 'newDose' : 'dose', e.target.value)}
                    style={{ ...EDIT_INLINE, fontSize: 12, color: '#64748b', marginTop: 2 }} placeholder="Dose / frequency / details" />
                </td>
                <td style={{ verticalAlign: 'top', paddingTop: 10, textAlign: 'center' }}>
                  <button onClick={() => removeRow(i)} style={REMOVE_BTN} title="Remove medication">×</button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <button onClick={addRow} style={{ ...ADD_BTN, marginTop: 8 }}>+ Add medication</button>
    </div>
  );
}

/* ── Parse clinical notes into structured sections ── */
function parseClinicalNotes(notes) {
  if (!notes) return [];
  const regex = /(CC:|Chief Complaint:|HPI:|History of Present Illness:|PE:|Physical Exam:|Physical Examination:|Labs:|Laboratory:|PMH:|Past Medical History:|\[Severity\/Staging\]|Severity\/Staging:)/gi;
  const parts = notes.split(regex);
  const sections = [];
  
  // If there's content before any key, treat it as general/unlabeled
  let firstPart = parts[0]?.trim();
  if (firstPart) {
    sections.push({ key: '', label: '', content: firstPart });
  }
  
  for (let i = 1; i < parts.length; i += 2) {
    const rawKey = parts[i];
    const rawValue = parts[i + 1] || '';
    
    // Normalize rawKey into a nice label
    let label = rawKey.trim();
    if (label.endsWith(':')) label = label.slice(0, -1).trim();
    
    // Clean up label names
    const lowerLabel = label.toLowerCase();
    if (lowerLabel === 'cc') label = 'Chief Complaint';
    else if (lowerLabel === 'hpi') label = 'History of Present Illness';
    else if (lowerLabel === 'pe') label = 'Physical Exam';
    else if (lowerLabel === 'pmh') label = 'Past Medical History';
    else if (lowerLabel === '[severity/staging]') label = 'Severity / Staging';
    
    const content = rawValue.trim();
    if (content) {
      sections.push({ key: rawKey.trim().toLowerCase(), label, content });
    }
  }
  return sections;
}

/* ── Render Subjective Sections ── */
function renderSubjectiveNotes(notes) {
  const sections = parseClinicalNotes(notes);
  const subjectiveSections = sections.filter(s => 
    !s.key.includes('pe') && 
    !s.key.includes('physical') && 
    !s.key.includes('lab')
  );
  
  // Rearrange: move Severity/Staging to the bottom
  const severityIndex = subjectiveSections.findIndex(s => s.key.includes('severity') || s.key.includes('staging'));
  if (severityIndex !== -1) {
    const severitySection = subjectiveSections.splice(severityIndex, 1)[0];
    subjectiveSections.push(severitySection);
  }
  
  if (subjectiveSections.length === 0) {
    return <p style={{ margin: 0, color: 'var(--fg-muted)', fontStyle: 'italic' }}>{notes || 'No subjective history documented.'}</p>;
  }
  
  return (
    <div className="narrative-blocks" style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
      {subjectiveSections.map((s, idx) => (
        <div key={idx} style={{ lineHeight: '1.6' }}>
          {s.label ? (
            <div style={{ fontSize: '11px', fontWeight: '700', textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--accent-primary)', marginBottom: '2px' }}>
              {s.label}
            </div>
          ) : null}
          <div style={{ fontSize: '13.5px', color: 'var(--fg-primary)' }}>
            {s.content}
          </div>
        </div>
      ))}
    </div>
  );
}

/* ── Render Objective Sections (PE / Labs) ── */
function renderObjectiveNotes(notes) {
  const sections = parseClinicalNotes(notes);
  const peLabsSections = sections.filter(s => 
    s.key.includes('pe') || 
    s.key.includes('physical') || 
    s.key.includes('lab')
  );
  
  if (peLabsSections.length === 0) {
    return (
      <div style={{ marginTop: 14, lineHeight: '1.6' }}>
        <div style={{ fontSize: '11px', fontWeight: '700', textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--accent-primary)', marginBottom: '2px' }}>
          Physical Exam
        </div>
        <div style={{ fontSize: '13.5px', color: 'var(--fg-primary)' }}>
          Reduced sensation to monofilament test bilateral plantar surfaces.
          Pedal pulses present and symmetric. Skin intact. No active foot lesions or fungal infection.
          Fundoscopy deferred — referral made for dilated exam.
        </div>
      </div>
    );
  }
  
  return (
    <div style={{ marginTop: 14, display: 'flex', flexDirection: 'column', gap: '12px' }}>
      {peLabsSections.map((s, idx) => (
        <div key={idx} style={{ lineHeight: '1.6' }}>
          <div style={{ fontSize: '11px', fontWeight: '700', textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--accent-primary)', marginBottom: '2px' }}>
            {s.label}
          </div>
          <div style={{ fontSize: '13.5px', color: 'var(--fg-primary)' }}>
            {s.content}
          </div>
        </div>
      ))}
    </div>
  );
}

export const FinalCarePlan = forwardRef(function FinalCarePlan({
  patient, diagnoses, carePlan: plan, allergies, vitals,
  clinicalNotes, provider, encounter, nextReviewDate,
  onExportPDF, onPrint, onBack, onNewAssessment,
  pdfUploaded, pdfUploading,
  onSendToPatient, deliveryStatus, canSendToPatient,
}, ref) {
  const [editing, setEditing] = useState(false);
  const { isDark } = useTheme();
  const paperRef = useRef(null);

  // Expose the paper DOM element to the parent via ref
  useImperativeHandle(ref, () => ({
    getPaperElement: () => paperRef.current,
  }));

  const initialDraft = () => ({
    clinicalNotes,
    medications: plan.medications,
    interventions: plan.interventions,
    monitoring: plan.monitoring,
    referrals: collapseReferrals(plan.referrals),
    lifestyle: plan.lifestyle,
    patientEducation: [
      'Diabetes self-management — understanding HbA1c targets, hypoglycaemia recognition and management',
      'SGLT2 inhibitor sick-day rules — hold medication if ill, report symptoms early',
      'Daily foot inspection — check for wounds, blisters, skin changes',
      'Signs of DKA — nausea, vomiting, abdominal pain (rare but important with SGLT2i)',
      'Carry glucose tablets — for hypoglycaemic episodes',
      'Importance of regular follow-up and lab monitoring',
    ],
    redFlags: plan.redFlags,
    followUp: plan.followUp,
    nextReviewDate: nextReviewDate || '',
  });

  const [draft, setDraft] = useState(initialDraft);

  React.useEffect(() => {
    setDraft(initialDraft());
  }, [clinicalNotes, plan, patient, nextReviewDate]);

  const set = (key) => (val) => setDraft(d => ({ ...d, [key]: val }));

  const totalMeds =
    (draft.medications.stop?.length || 0) +
    (draft.medications.start?.length || 0) +
    (draft.medications.change?.length || 0) +
    (draft.medications.continue?.length || 0);

  return (
    <div className="fcp-shell">
      <div>
        <div className="mb-6">
          <span className="ds-eyebrow">STEP 4 OF 4</span>
          <h2 className={`text-2xl font-semibold tracking-tight mb-1 ${isDark ? 'text-white' : 'text-slate-800'}`}>
            Final Care Plan
          </h2>
          <p className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
            Review, print, or export the finalized care plan document.
          </p>
        </div>

        {editing && (
          <div style={{
            display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12,
            padding: '8px 14px', borderRadius: 8, fontSize: 13, fontWeight: 500,
            background: 'rgba(16,185,129,0.08)', border: '1px solid rgba(16,185,129,0.3)',
            color: '#065f46',
          }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4z"/></svg>
            Editing mode — click <strong style={{ margin: '0 4px' }}>Save edits</strong> in the sidebar when done.
          </div>
        )}

        <div className="paper" ref={paperRef}>
          <Letterhead provider={provider} encounter={encounter} />
          <PatientBanner patient={patient} encounter={encounter} allergies={allergies} provider={provider} />

          <div className="doc-body">
            <SoapSection letter="S" title="Subjective" desc="Patient-reported history" id="soap-s">
              {editing ? (
                <EditableText multiline editing={editing} value={draft.clinicalNotes}
                  onChange={set('clinicalNotes')} className="narrative" />
              ) : (
                <div className="narrative">
                  {renderSubjectiveNotes(draft.clinicalNotes)}
                </div>
              )}
            </SoapSection>

            <SoapSection letter="O" title="Objective" desc="Vital signs & exam findings" id="soap-o">
              <VitalsTable vitals={vitals} />
              {renderObjectiveNotes(draft.clinicalNotes)}
            </SoapSection>

            <SoapSection letter="A" title="Assessment" desc="Clinical impression" id="soap-a">
              <AssessmentList diagnoses={diagnoses} />
            </SoapSection>

            <SoapSection letter="P" title="Plan" desc="Recommended interventions" id="soap-p">
              <PlanSub num="P1" title="Medications" count={`${totalMeds} items`}>
                <EditableMedTable meds={draft.medications} onChange={set('medications')} editing={editing} />
              </PlanSub>

              <PlanSub num="P2" title="Procedures & Interventions" count={`${draft.interventions.length} items`}>
                <EditableTable
                  editing={editing}
                  headers={[
                    { label: 'Procedure', field: 'name' },
                    { label: 'Urgency', field: 'urgency', width: 140 },
                  ]}
                  rows={draft.interventions}
                  onChange={set('interventions')}
                  buildEmpty={() => ({ id: Date.now(), name: '', urgency: 'Routine' })}
                  renderView={(r) => [
                    <SplitTitleSubtitle text={r.name} />,
                    <span className={`atag ${r.urgency === 'Today' ? 'stop' : 'change'}`}>{r.urgency}</span>,
                  ]}
                />
              </PlanSub>

              <PlanSub num="P3" title="Monitoring & Investigations" count={`${draft.monitoring.length} items`}>
                <EditableTable
                  editing={editing}
                  headers={[
                    { label: 'Parameter', field: 'parameter', width: 220 },
                    { label: 'Target', field: 'target' },
                    { label: 'Schedule', field: 'schedule', width: 280 },
                  ]}
                  rows={draft.monitoring}
                  onChange={set('monitoring')}
                  buildEmpty={() => ({ id: Date.now(), parameter: '', target: '', schedule: '' })}
                  renderView={(r) => [
                    <div className="name">{r.parameter}</div>,
                    <div className="desc">{r.target || '—'}</div>,
                    <span className="atag continue">{compactSchedule(r.schedule)}</span>,
                  ]}
                />
              </PlanSub>

              <PlanSub num="P4" title="Lifestyle & Self-Management" count={`${draft.lifestyle.length} goals`}>
                <EditableBullets items={draft.lifestyle} onChange={set('lifestyle')} editing={editing} />
              </PlanSub>

              <PlanSub num="P5" title="Referrals" count={`${draft.referrals.length} sent`}>
                <EditableTable
                  editing={editing}
                  headers={[
                    { label: 'Specialty', field: 'specialty' },
                    { label: 'Urgency', field: 'urgency', width: 140 },
                  ]}
                  rows={draft.referrals}
                  onChange={set('referrals')}
                  buildEmpty={() => ({ id: Date.now(), specialty: '', reason: '', urgency: 'Routine' })}
                  renderView={(r) => [
                    <ReferralTitleSubtitle text={r.specialty} />,
                    <span className={`atag ${urgencyTagClass(r.urgency)}`}>{r.urgency}</span>,
                  ]}
                />
              </PlanSub>

              <PlanSub num="P6" title="Patient Education">
                {editing
                  ? <EditableBullets items={draft.patientEducation} onChange={set('patientEducation')} editing={editing} />
                  : <EducationList items={draft.patientEducation} />}
              </PlanSub>

              <PlanSub num="P7" title="Safety Netting — Red Flags">
                {editing ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                    {draft.redFlags.map((f, i) => {
                      const colonIdx = f.indexOf(':');
                      const rfTitle = colonIdx > -1 ? f.slice(0, colonIdx).trim() : f;
                      const rfDesc = colonIdx > -1 ? f.slice(colonIdx + 1).trim() : '';
                      return (
                        <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 8, padding: '4px 0', borderBottom: '1px solid #fef2f2' }}>
                          <div style={{ flex: 1, minWidth: 0 }}>
                            <input type="text" value={rfTitle}
                              onChange={e => { const next = [...draft.redFlags]; next[i] = rfDesc ? `${e.target.value}: ${rfDesc}` : e.target.value; set('redFlags')(next); }}
                              style={{ background: 'transparent', border: 'none', borderBottom: '1px dashed #fca5a5', borderRadius: 0, padding: '2px 0', fontSize: 13, fontWeight: 600, fontFamily: 'inherit', outline: 'none', width: '100%', color: '#991b1b' }}
                              placeholder="Red flag title" />
                            <input type="text" value={rfDesc}
                              onChange={e => { const next = [...draft.redFlags]; next[i] = e.target.value ? `${rfTitle}: ${e.target.value}` : rfTitle; set('redFlags')(next); }}
                              style={{ background: 'transparent', border: 'none', borderBottom: '1px dashed #fecaca', borderRadius: 0, padding: '2px 0', fontSize: 12, fontFamily: 'inherit', outline: 'none', width: '100%', color: '#64748b' }}
                              placeholder="Description" />
                          </div>
                          <button onClick={() => set('redFlags')(draft.redFlags.filter((_, j) => j !== i))} style={{ ...REMOVE_BTN, marginTop: 4 }}>×</button>
                        </div>
                      );
                    })}
                    <button onClick={() => set('redFlags')([...draft.redFlags, ''])}
                      style={{ ...ADD_BTN, color: '#b91c1c', background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.3)', alignSelf: 'flex-start' }}>
                      + Add red flag
                    </button>
                  </div>
                ) : (
                  <RedFlagList items={draft.redFlags} />
                )}
              </PlanSub>

              <PlanSub num="P8" title="Follow-up Plan">
                <div className="tca-row">
                  <div className="tca-list">
                    {draft.followUp.map((f, i) => {
                      const splitMatch = f.match(/\s*(?::|—|-|–)\s+/);
                      const when = splitMatch ? f.slice(0, splitMatch.index).trim() : '—';
                      const what = splitMatch ? f.slice(splitMatch.index + splitMatch[0].length).trim() : f;
                      return editing ? (
                        <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 8, padding: '4px 0', borderBottom: '1px solid #f1f5f9' }}>
                          <div style={{ flex: 1, minWidth: 0 }}>
                            <input type="text" value={when}
                              onChange={e => { const next = [...draft.followUp]; next[i] = `${e.target.value}: ${what}`; set('followUp')(next); }}
                              style={{ background: 'transparent', border: 'none', borderBottom: '1px dashed #cbd5e1', borderRadius: 0, padding: '2px 0', fontSize: 13, fontWeight: 600, fontFamily: 'inherit', outline: 'none', width: '100%', color: '#1e293b' }}
                              placeholder="When" />
                            <input type="text" value={what}
                              onChange={e => { const next = [...draft.followUp]; next[i] = `${when}: ${e.target.value}`; set('followUp')(next); }}
                              style={{ background: 'transparent', border: 'none', borderBottom: '1px dashed #e2e8f0', borderRadius: 0, padding: '2px 0', fontSize: 12, fontFamily: 'inherit', outline: 'none', width: '100%', color: '#64748b' }}
                              placeholder="Description" />
                          </div>
                          <button onClick={() => set('followUp')(draft.followUp.filter((_, j) => j !== i))} style={{ ...REMOVE_BTN, marginTop: 4 }}>×</button>
                        </div>
                      ) : (
                        <div key={i} className="tca-li">
                          <span className="when">{when}</span>
                          <span className="what"><SplitPlanText text={what} /></span>
                        </div>
                      );
                    })}
                    {editing && (
                      <button onClick={() => set('followUp')([...draft.followUp, 'When: What'])} style={{ ...ADD_BTN, alignSelf: 'flex-start' }}>
                        + Add item
                      </button>
                    )}
                  </div>
                  <div className="tca-summary">
                    <div className="label">Next Review (TCA)</div>
                    {editing ? (
                      <input type="text" value={draft.nextReviewDate} onChange={e => set('nextReviewDate')(e.target.value)}
                        style={{ background: 'transparent', border: 'none', borderBottom: '2px dashed #10b981', borderRadius: 0, padding: '2px 0', fontSize: 18, fontWeight: 700, fontFamily: 'inherit', outline: 'none', width: '100%', color: '#065f46' }} />
                    ) : (
                      <div className="date">{draft.nextReviewDate || '—'}</div>
                    )}
                    <div className="rel">Auto-suggested from CPG. Adjust as needed.</div>
                  </div>
                </div>
              </PlanSub>
            </SoapSection>
          </div>
        </div>
      </div>

      {/* ============ RIGHT ACTION RAIL ============ */}
      <aside className="action-rail">
        <div className="rail-card">
          <h5>Status</h5>
          <p style={{ margin: '0 0 12px', fontSize: 13, color: 'var(--fg-secondary)', fontWeight: '700' }}>
            Ready for Final Approval
          </p>
          <button className="action-btn primary" onClick={onNewAssessment}>
            <span className="icon-box">{fcpIcons.check({})}</span>
            <span>Approve Care Plan</span>
          </button>
        </div>

        <div className="rail-card">
          <h5>Edit</h5>
          {editing ? (
            <>
              <button className="action-btn primary" onClick={() => setEditing(false)}>
                <span className="icon-box">{fcpIcons.check({})}</span>
                <span>Save edits</span>
              </button>
              <button className="action-btn" onClick={() => { setDraft(initialDraft()); setEditing(false); }}>
                <span className="icon-box">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6"/></svg>
                </span>
                <span>Discard changes</span>
              </button>
            </>
          ) : (
            <button className="action-btn" onClick={() => setEditing(true)}>
              <span className="icon-box">{fcpIcons.edit({})}</span>
              <span>Edit document</span>
            </button>
          )}
          <button className="action-btn" style={{ marginTop: 6 }} onClick={onBack}>
            <span className="icon-box">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="15 18 9 12 15 6"/></svg>
            </span>
            <span>Back to Care Plan</span>
          </button>
        </div>

        <div className="rail-card">
          <h5>Distribute</h5>
          <button className="action-btn" onClick={onExportPDF}>
            <span className="icon-box">{fcpIcons.download({})}</span>
            <span>Export PDF</span>
          </button>
          <button className="action-btn" onClick={onPrint}>
            <span className="icon-box">{fcpIcons.print({})}</span>
            <span>Print copy</span>
          </button>
          <button className="action-btn" disabled>
            <span className="icon-box">{fcpIcons.send({})}</span>
            <span>Send to EMR</span>
            <span className="meta">HL7 FHIR</span>
          </button>
          {/* ── Supabase upload status ── */}
          <div style={{
            display: 'flex', alignItems: 'center', gap: 8,
            padding: '8px 12px', borderRadius: 8, fontSize: 12,
            marginTop: 4,
            background: pdfUploaded
              ? 'rgba(16,185,129,0.08)'
              : pdfUploading
                ? 'rgba(59,130,246,0.08)'
                : 'rgba(100,116,139,0.06)',
            border: `1px solid ${pdfUploaded
              ? 'rgba(16,185,129,0.25)'
              : pdfUploading
                ? 'rgba(59,130,246,0.25)'
                : 'rgba(100,116,139,0.15)'}`,
            color: pdfUploaded
              ? '#065f46'
              : pdfUploading
                ? '#1e40af'
                : '#64748b',
          }}>
            {pdfUploading ? (
              <>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ animation: 'spin 1s linear infinite' }}><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>
                <span style={{ fontWeight: 500 }}>Saving to records…</span>
              </>
            ) : pdfUploaded ? (
              <>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
                <span style={{ fontWeight: 500 }}>Saved to patient records</span>
              </>
            ) : (
              <>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
                <span style={{ fontWeight: 500 }}>Pending upload</span>
              </>
            )}
          </div>
          <button
            className="action-btn"
            onClick={onSendToPatient}
            disabled={!canSendToPatient || deliveryStatus?.status === 'sending' || deliveryStatus?.status === 'sent'}
            title={!canSendToPatient ? 'Patient has not consented to email delivery' : undefined}
          >
            <span className="icon-box">{fcpIcons.mail({})}</span>
            <span>
              {deliveryStatus?.status === 'sending' ? 'Sending…'
                : deliveryStatus?.status === 'sent' ? 'Sent'
                : 'Send to patient'}
            </span>
          </button>
          {deliveryStatus && (
            <div style={{
              display: 'flex', alignItems: 'center', gap: 8,
              padding: '6px 12px', borderRadius: 8, fontSize: 12, marginTop: 4,
              background: deliveryStatus.status === 'sent'
                ? 'rgba(16,185,129,0.08)'
                : deliveryStatus.status === 'failed'
                  ? 'rgba(239,68,68,0.08)'
                  : 'rgba(59,130,246,0.08)',
              border: `1px solid ${deliveryStatus.status === 'sent'
                ? 'rgba(16,185,129,0.25)'
                : deliveryStatus.status === 'failed'
                  ? 'rgba(239,68,68,0.25)'
                  : 'rgba(59,130,246,0.25)'}`,
              color: deliveryStatus.status === 'sent' ? '#065f46'
                : deliveryStatus.status === 'failed' ? '#991b1b'
                : '#1e40af',
            }}>
              <span style={{ fontWeight: 500 }}>
                {deliveryStatus.status === 'sent' ? 'Email delivered'
                  : deliveryStatus.status === 'failed' ? `Failed: ${deliveryStatus.error || 'error'}`
                  : 'Queued for delivery'}
              </span>
            </div>
          )}
          <button className="action-btn" disabled>
            <span className="icon-box">{fcpIcons.share({})}</span>
            <span>Share with team</span>
          </button>
        </div>
      </aside>
    </div>
  );
});
