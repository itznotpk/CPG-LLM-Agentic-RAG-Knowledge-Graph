import React, { useState } from 'react';
import { Letterhead, PatientBanner, SoapSection, VitalsTable, AssessmentList, MedTable, PlanTable, PlanSub, fcpIcons } from './FinalCarePlanPieces';
/* Final Care Plan — Stage 4 app */

const EDIT_INPUT = {
  background: 'rgba(16,185,129,0.06)',
  border: '1px solid rgba(16,185,129,0.35)',
  borderRadius: 6, padding: '4px 8px',
  fontSize: 13, fontFamily: 'inherit', outline: 'none', width: '100%',
};

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

/* ── Editable plain text / textarea ── */
function EditableText({ value, onChange, editing, multiline = false, className = '', style = {} }) {
  if (!editing) {
    return multiline
      ? <p className={`narrative ${className}`} style={style}>{value}</p>
      : <span className={className} style={style}>{value}</span>;
  }
  const base = { ...EDIT_INPUT, lineHeight: 1.6, ...style };
  return multiline
    ? <textarea rows={4} value={value} onChange={e => onChange(e.target.value)}
        style={{ ...base, resize: 'vertical', display: 'block' }} className={className} />
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
              ? <><strong style={{ marginRight: 6 }}>{l.category}:</strong>{l.goal}</>
              : l}
            </span>
          </div>
        ))}
      </div>
    );
  }
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      {items.map((l, i) => {
        const text = typeof l === 'object' ? `${l.category}: ${l.goal}` : l;
        return (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ color: 'var(--accent-primary)', fontWeight: 700, flexShrink: 0 }}>•</span>
            <input type="text" value={text}
              onChange={e => {
                const next = [...items];
                if (typeof l === 'object') {
                  const ci = e.target.value.indexOf(': ');
                  next[i] = ci > -1
                    ? { ...l, category: e.target.value.slice(0, ci), goal: e.target.value.slice(ci + 2) }
                    : { ...l, goal: e.target.value };
                } else { next[i] = e.target.value; }
                onChange(next);
              }}
              style={EDIT_INPUT}
            />
            <button onClick={() => onChange(items.filter((_, j) => j !== i))} style={REMOVE_BTN}>×</button>
          </div>
        );
      })}
      <button onClick={() => onChange([...items, typeof items[0] === 'object' ? { category: 'New', goal: '' } : ''])}
        style={ADD_BTN}>+ Add item</button>
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
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {rows.map((row, i) => (
        <div key={i} style={{
          display: 'grid', gap: 6, padding: '8px 10px',
          background: 'rgba(16,185,129,0.04)', borderRadius: 8,
          border: '1px solid rgba(16,185,129,0.2)',
          gridTemplateColumns: headers.map(h => h.width ? `${h.width}px` : '1fr').join(' ') + ' 24px',
        }}>
          {headers.map((h, j) => (
            <div key={j}>
              <div style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: '#6b7280', marginBottom: 3 }}>{h.label}</div>
              <input type="text" value={row[h.field] ?? ''} onChange={e => {
                const next = rows.map((r, ri) => ri === i ? { ...r, [h.field]: e.target.value } : r);
                onChange(next);
              }} style={EDIT_INPUT} />
            </div>
          ))}
          <div style={{ display: 'flex', alignItems: 'center', paddingTop: 18 }}>
            <button onClick={() => onChange(rows.filter((_, ri) => ri !== i))} style={REMOVE_BTN}>×</button>
          </div>
        </div>
      ))}
      <button onClick={() => onChange([...rows, buildEmpty()])} style={ADD_BTN}>+ Add row</button>
    </div>
  );
}

/* ── Editable medications table ── */
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
    const newRow = { id: Date.now(), name: '', dose: '', reason: '', cpgRef: '', action: 'start' };
    onChange({ ...meds, start: [...(meds.start || []), newRow] });
  };

  if (!editing) return <MedTable meds={meds} />;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {rows.map((row, i) => (
        <div key={i} style={{
          display: 'grid', gap: 6, padding: '10px 12px',
          background: 'rgba(16,185,129,0.04)', borderRadius: 8,
          border: '1px solid rgba(16,185,129,0.2)',
          gridTemplateColumns: '90px 1fr 1fr 120px 24px',
        }}>
          {/* Action */}
          <div>
            <div style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: '#6b7280', marginBottom: 3 }}>Action</div>
            <select value={row.action} onChange={e => updateRow(i, 'action', e.target.value)}
              style={{ ...EDIT_INPUT, padding: '4px 6px' }}>
              {['start','stop','change','continue'].map(a => <option key={a} value={a}>{a}</option>)}
            </select>
          </div>
          {/* Medication */}
          <div>
            <div style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: '#6b7280', marginBottom: 3 }}>Medication</div>
            <input type="text" value={row.name || ''} onChange={e => updateRow(i, 'name', e.target.value)}
              style={{ ...EDIT_INPUT, marginBottom: 4 }} placeholder="Drug name" />
            <input type="text" value={row.dose || row.newDose || ''} onChange={e => updateRow(i, row.action === 'change' ? 'newDose' : 'dose', e.target.value)}
              style={EDIT_INPUT} placeholder="Dose / frequency" />
          </div>
          {/* Reason */}
          <div>
            <div style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: '#6b7280', marginBottom: 3 }}>Reason / Instructions</div>
            <input type="text" value={row.reason || ''} onChange={e => updateRow(i, 'reason', e.target.value)}
              style={{ ...EDIT_INPUT, marginBottom: 4 }} placeholder="Reason" />
            <input type="text" value={row.instructions || ''} onChange={e => updateRow(i, 'instructions', e.target.value)}
              style={EDIT_INPUT} placeholder="Instructions (optional)" />
          </div>
          {/* CPG ref */}
          <div>
            <div style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: '#6b7280', marginBottom: 3 }}>Reference</div>
            <input type="text" value={row.cpgRef || ''} onChange={e => updateRow(i, 'cpgRef', e.target.value)}
              style={EDIT_INPUT} placeholder="CPG ref" />
          </div>
          <div style={{ display: 'flex', alignItems: 'center', paddingTop: 18 }}>
            <button onClick={() => removeRow(i)} style={REMOVE_BTN}>×</button>
          </div>
        </div>
      ))}
      <button onClick={addRow} style={ADD_BTN}>+ Add medication</button>
    </div>
  );
}

export function FinalCarePlan({
  patient, diagnoses, carePlan: plan, allergies, vitals,
  clinicalNotes, provider, encounter, nextReviewDate,
  onExportPDF, onPrint, onBack, onNewAssessment,
}) {
  const [editing, setEditing] = useState(false);

  const initialDraft = () => ({
    clinicalNotes,
    clinicalSummary: plan.clinicalSummary,
    medications: plan.medications,
    interventions: plan.interventions,
    monitoring: plan.monitoring,
    referrals: plan.referrals,
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
  const set = (key) => (val) => setDraft(d => ({ ...d, [key]: val }));

  const totalMeds =
    (draft.medications.stop?.length || 0) +
    (draft.medications.start?.length || 0) +
    (draft.medications.change?.length || 0) +
    (draft.medications.continue?.length || 0);

  return (
    <div className="fcp-shell">
      <div>
        <div className="fcp-eyebrow">
          <span className="step">Step 4 of 4 · Final Care Plan</span>
          <span className="status"><span className="dot"></span>Ready to approve</span>
          <span className="doc-id">DOC-{encounter.id}</span>
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

        <div className="paper">
          <Letterhead provider={provider} encounter={encounter} />
          <PatientBanner patient={patient} encounter={encounter} allergies={allergies} />

          <div className="doc-body">
            <SoapSection letter="S" title="Subjective" desc="Patient-reported history" id="soap-s">
              <EditableText multiline editing={editing} value={draft.clinicalNotes}
                onChange={set('clinicalNotes')} className="narrative" />
            </SoapSection>

            <SoapSection letter="O" title="Objective" desc="Vital signs & exam findings" id="soap-o">
              <VitalsTable vitals={vitals} />
              <p style={{ marginTop: 14, fontSize: 13, lineHeight: 1.6 }}>
                <strong>Physical exam:</strong> Reduced sensation to monofilament test bilateral plantar surfaces.
                Pedal pulses present and symmetric. Skin intact. No active foot lesions or fungal infection.
                Fundoscopy deferred — referral made for dilated exam.
              </p>
            </SoapSection>

            <SoapSection letter="A" title="Assessment" desc="Clinical impression" id="soap-a">
              <AssessmentList diagnoses={diagnoses} cpgReferences={plan.cpgReferences.slice(0, 2)} />
            </SoapSection>

            <SoapSection letter="P" title="Plan" desc="Recommended interventions" id="soap-p">
              <PlanSub num="P1" title="Clinical Summary">
                <EditableText multiline editing={editing} value={draft.clinicalSummary}
                  onChange={set('clinicalSummary')} className="narrative" style={{ fontSize: 13 }} />
              </PlanSub>

              <PlanSub num="P2" title="Medications" count={`${totalMeds} items`}>
                <EditableMedTable meds={draft.medications} onChange={set('medications')} editing={editing} />
              </PlanSub>

              <PlanSub num="P3" title="Procedures & Interventions" count={`${draft.interventions.length} items`}>
                <EditableTable
                  editing={editing}
                  headers={[
                    { label: 'Procedure', field: 'name' },
                    { label: 'Rationale', field: 'rationale' },
                    { label: 'Urgency', field: 'urgency', width: 140 },
                  ]}
                  rows={draft.interventions}
                  onChange={set('interventions')}
                  buildEmpty={() => ({ id: Date.now(), name: '', rationale: '', urgency: 'Routine' })}
                  renderView={(r) => [
                    <div><div className="name">{r.name}</div></div>,
                    <div className="desc">{r.rationale}</div>,
                    <span className={`atag ${r.urgency === 'Today' ? 'stop' : 'change'}`}>{r.urgency}</span>,
                  ]}
                />
              </PlanSub>

              <PlanSub num="P4" title="Monitoring & Investigations" count={`${draft.monitoring.length} items`}>
                <EditableTable
                  editing={editing}
                  headers={[
                    { label: 'Parameter', field: 'parameter' },
                    { label: 'Target', field: 'target' },
                    { label: 'Schedule', field: 'schedule', width: 140 },
                  ]}
                  rows={draft.monitoring}
                  onChange={set('monitoring')}
                  buildEmpty={() => ({ id: Date.now(), parameter: '', target: '', schedule: '' })}
                  renderView={(r) => [
                    <div className="name">{r.parameter}</div>,
                    <div className="desc">{r.target || '—'}</div>,
                    <span className="atag continue">{r.schedule}</span>,
                  ]}
                />
              </PlanSub>

              <PlanSub num="P5" title="Lifestyle & Self-Management" count={`${draft.lifestyle.length} goals`}>
                <EditableBullets items={draft.lifestyle} onChange={set('lifestyle')} editing={editing} />
              </PlanSub>

              <PlanSub num="P6" title="Referrals" count={`${draft.referrals.length} sent`}>
                <EditableTable
                  editing={editing}
                  headers={[
                    { label: 'Specialty', field: 'specialty' },
                    { label: 'Reason for referral', field: 'reason' },
                    { label: 'Urgency', field: 'urgency', width: 140 },
                  ]}
                  rows={draft.referrals}
                  onChange={set('referrals')}
                  buildEmpty={() => ({ id: Date.now(), specialty: '', reason: '', urgency: 'Routine' })}
                  renderView={(r) => [
                    <div className="name">{r.specialty}</div>,
                    <div className="desc">{r.reason}</div>,
                    <span className="atag change">{r.urgency}</span>,
                  ]}
                />
              </PlanSub>

              <PlanSub num="P7" title="Patient Education">
                <EditableBullets items={draft.patientEducation} onChange={set('patientEducation')} editing={editing} />
              </PlanSub>

              <PlanSub num="P8" title="Safety Netting — Red Flags">
                {editing ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                    {draft.redFlags.map((f, i) => (
                      <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <input type="text" value={f}
                          onChange={e => { const next = [...draft.redFlags]; next[i] = e.target.value; set('redFlags')(next); }}
                          style={{ ...EDIT_INPUT, background: 'rgba(239,68,68,0.06)', border: '1px solid rgba(239,68,68,0.3)' }} />
                        <button onClick={() => set('redFlags')(draft.redFlags.filter((_, j) => j !== i))} style={REMOVE_BTN}>×</button>
                      </div>
                    ))}
                    <button onClick={() => set('redFlags')([...draft.redFlags, ''])}
                      style={{ ...ADD_BTN, color: '#b91c1c', background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.3)' }}>
                      + Add red flag
                    </button>
                  </div>
                ) : (
                  <div className="redflags">
                    <h5>{fcpIcons.alert({ stroke: '#991b1b' })} Return to clinic / call emergency for any of the following</h5>
                    <ul>{draft.redFlags.map((f, i) => <li key={i}>{f}</li>)}</ul>
                  </div>
                )}
              </PlanSub>

              <PlanSub num="P9" title="Follow-up Plan">
                <div className="tca-row">
                  <div className="tca-list">
                    {draft.followUp.map((f, i) => {
                      const idx = f.indexOf(':');
                      const when = idx > -1 ? f.slice(0, idx).trim() : '—';
                      const what = idx > -1 ? f.slice(idx + 1).trim() : f;
                      return editing ? (
                        <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                          <input type="text" value={f}
                            onChange={e => { const next = [...draft.followUp]; next[i] = e.target.value; set('followUp')(next); }}
                            style={EDIT_INPUT} />
                          <button onClick={() => set('followUp')(draft.followUp.filter((_, j) => j !== i))} style={REMOVE_BTN}>×</button>
                        </div>
                      ) : (
                        <div key={i} className="tca-li">
                          <span className="when">{when}</span>
                          <span className="what">{what}</span>
                        </div>
                      );
                    })}
                    {editing && (
                      <button onClick={() => set('followUp')([...draft.followUp, 'When: What'])} style={ADD_BTN}>
                        + Add item
                      </button>
                    )}
                  </div>
                  <div className="tca-summary">
                    <div className="label">Next Review (TCA)</div>
                    {editing ? (
                      <input type="text" value={draft.nextReviewDate} onChange={e => set('nextReviewDate')(e.target.value)}
                        style={{ ...EDIT_INPUT, fontSize: 18, fontWeight: 700 }} />
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
          <button className="action-btn" disabled>
            <span className="icon-box">{fcpIcons.mail({})}</span>
            <span>Email to patient</span>
          </button>
          <button className="action-btn" disabled>
            <span className="icon-box">{fcpIcons.share({})}</span>
            <span>Share with team</span>
          </button>
        </div>
      </aside>
    </div>
  );
}
