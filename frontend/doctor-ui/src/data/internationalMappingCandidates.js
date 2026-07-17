// DEMO ONLY. Replace with a clinician-signed, versioned mapping before production use.
const HFrEF = /heart failure|hfref/i;
const CANDIDATES = [
  { id: 'demo-hf-overview', section: 'overview', match: HFrEF, local: 'Malaysia CPG-directed HFrEF care plan.', international: 'International guidance review is available for the same care question.' },
  { id: 'demo-hf-furosemide', section: 'meds', match: HFrEF, local: 'Furosemide 20–40 mg orally once daily — Malaysia CPG plan.', international: 'Furosemide 20 mg orally once daily — international comparison candidate.', reason: 'Demo dose-comparison candidate; not an approved prescribing change.' },
  { id: 'demo-hf-monitoring', section: 'care', match: HFrEF, local: 'Use local monitoring and referral pathways.', international: 'Review volume status, renal function and electrolytes during diuretic optimisation.', reason: 'Demo monitoring comparison candidate; local capacity must be considered.' },
  { id: 'demo-hf-followup', section: 'followup', match: HFrEF, local: 'Use Malaysian CPG follow-up and escalation pathways.', international: 'Review early post-optimisation reassessment against the international pathway.', reason: 'Demo follow-up comparison candidate; not an automatic referral change.' },
  { id: 'demo-hf-references', section: 'refs', match: HFrEF, local: 'Malaysia CPG remains the active reference.', international: 'International source is attached as a comparison reference.' },
  { id: 'demo-hf-evidence', section: 'evidence', match: HFrEF, local: 'Local CPG evidence underpins the plan.', international: 'Europe PMC evidence is supplementary international evidence.' },
];
export function getInternationalMappingCandidates(diagnoses = []) {
  const names = diagnoses.map((item) => item?.name || '').join(' ');
  return CANDIDATES.filter((item) => item.match.test(names));
}
