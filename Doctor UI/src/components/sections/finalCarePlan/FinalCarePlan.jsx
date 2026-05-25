import React from 'react';
import { Letterhead, PatientBanner, SoapSection, VitalsTable, AssessmentList, MedTable, PlanTable, PlanSub, fcpIcons } from './FinalCarePlanPieces';
/* Final Care Plan — Stage 4 app */

export function FinalCarePlan({
  patient, diagnoses, carePlan: plan, allergies, vitals,
  clinicalNotes, provider, encounter, nextReviewDate,
  onExportPDF, onPrint, onBack, onNewAssessment,
}) {


  // Plan totals for the right-rail KPI mini
  const totalMeds =
  (plan.medications.stop?.length || 0) + (
  plan.medications.start?.length || 0) + (
  plan.medications.change?.length || 0) + (
  plan.medications.continue?.length || 0);

  return (
    <div className="fcp-shell">
      <div>
        <div className="fcp-eyebrow">
          <span className="step">Step 4 of 4 · Final Care Plan</span>
          <span className="status"><span className="dot"></span>Ready to approve</span>
          <span className="doc-id">DOC-{encounter.id}</span>
        </div>

        {/* THE PAPER */}
        <div className="paper">
          <Letterhead provider={provider} encounter={encounter} />
          <PatientBanner patient={patient} encounter={encounter} allergies={allergies} />

          <div className="doc-body">
            <SoapSection letter="S" title="Subjective" desc="Patient-reported history" id="soap-s">
              <p className="narrative">{clinicalNotes}</p>
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
                <p className="narrative" style={{ fontSize: 13 }}>{plan.clinicalSummary}</p>
              </PlanSub>

              <PlanSub num="P2" title="Medications" count={`${totalMeds} items`}>
                <MedTable meds={plan.medications} />
              </PlanSub>

              <PlanSub num="P3" title="Procedures & Interventions" count={`${plan.interventions.length} items`}>
                <PlanTable
                  headers={[
                  { label: 'Procedure' },
                  { label: 'Rationale' },
                  { label: 'Urgency', width: 140 }]
                  }
                  rows={plan.interventions.map((i) => [
                  <div><div className="name">{i.name}</div></div>,
                  <div className="desc">{i.rationale}</div>,
                  <span className={`atag ${i.urgency === 'Today' ? 'stop' : 'change'}`}>{i.urgency}</span>]
                  )} />
                
              </PlanSub>

              <PlanSub num="P4" title="Monitoring & Investigations" count={`${plan.monitoring.length} items`}>
                <PlanTable
                  headers={[
                  { label: 'Parameter' },
                  { label: 'Target' },
                  { label: 'Schedule', width: 140 }]
                  }
                  rows={plan.monitoring.map((m) => [
                  <div className="name">{m.parameter}</div>,
                  <div className="desc">{m.target || '—'}</div>,
                  <span className="atag continue">{m.schedule}</span>]
                  )} />
                
              </PlanSub>

              <PlanSub num="P5" title="Lifestyle & Self-Management" count={`${plan.lifestyle.length} goals`}>
                <div className="bullets">
                  {plan.lifestyle.map((l, i) =>
                  <div key={i} className="bullet">
                      <span className="marker">•</span>
                      <span><strong style={{ marginRight: 6 }}>{l.category}:</strong>{l.goal}</span>
                    </div>
                  )}
                </div>
              </PlanSub>

              <PlanSub num="P6" title="Referrals" count={`${plan.referrals.length} sent`}>
                <PlanTable
                  headers={[
                  { label: 'Specialty' },
                  { label: 'Reason for referral' },
                  { label: 'Urgency', width: 140 }]
                  }
                  rows={plan.referrals.map((r) => [
                  <div className="name">{r.specialty}</div>,
                  <div className="desc">{r.reason}</div>,
                  <span className="atag change">{r.urgency}</span>]
                  )} />
                
              </PlanSub>

              <PlanSub num="P7" title="Patient Education">
                <div className="bullets">
                  <div className="bullet"><span className="marker">•</span><span>Diabetes self-management — understanding HbA1c targets, hypoglycaemia recognition and management</span></div>
                  <div className="bullet"><span className="marker">•</span><span>SGLT2 inhibitor sick-day rules — hold medication if ill, report symptoms early</span></div>
                  <div className="bullet"><span className="marker">•</span><span>Daily foot inspection — check for wounds, blisters, skin changes</span></div>
                  <div className="bullet"><span className="marker">•</span><span>Signs of DKA — nausea, vomiting, abdominal pain (rare but important with SGLT2i)</span></div>
                  <div className="bullet"><span className="marker">•</span><span>Carry glucose tablets — for hypoglycaemic episodes</span></div>
                  <div className="bullet"><span className="marker">•</span><span>Importance of regular follow-up and lab monitoring</span></div>
                </div>
              </PlanSub>

              <PlanSub num="P8" title="Safety Netting — Red Flags">
                <div className="redflags">
                  <h5>{fcpIcons.alert({ stroke: '#991b1b' })} Return to clinic / call emergency for any of the following</h5>
                  <ul>{plan.redFlags.map((f, i) => <li key={i}>{f}</li>)}</ul>
                </div>
              </PlanSub>

              <PlanSub num="P9" title="Follow-up Plan">
                <div className="tca-row">
                  <div className="tca-list">
                    {plan.followUp.map((f, i) => {
                      const idx = f.indexOf(':');
                      const when = idx > -1 ? f.slice(0, idx).trim() : '—';
                      const what = idx > -1 ? f.slice(idx + 1).trim() : f;
                      return (
                        <div key={i} className="tca-li">
                          <span className="when">{when}</span>
                          <span className="what">{what}</span>
                        </div>);

                    })}
                  </div>
                  <div className="tca-summary">
                    <div className="label">Next Review (TCA)</div>
                    <div className="date">{nextReviewDate || "—"}</div>
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
          <p style={{ margin: '0 0 12px', fontSize: 13, color: 'var(--fg-secondary)', fontWeight: "700" }}>
            Ready for Final Approval
          </p>
          <button className="action-btn primary" onClick={onNewAssessment}>
            <span className="icon-box">{fcpIcons.check({})}</span>
            <span>Approve Care Plan</span>
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

      
    </div>);

}
