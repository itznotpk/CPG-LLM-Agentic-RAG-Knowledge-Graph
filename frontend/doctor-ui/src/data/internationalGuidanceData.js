// Phase-1 demonstration data for the International Guidance comparison surface.
// These records are manually curated examples, not a live guideline surveillance
// service and never alter the Malaysian CPG-grounded care plan.

const SUPPORT_MESSAGE = 'This diagnosis is not in the curated comparison demo. The care plan remains grounded in the routed Malaysian MoH CPG; live Europe PMC literature is available in the Evidence tab.';

const CURATED_GUIDANCE = [
  {
    id: 't2dm',
    match: /type\s*2\s*diabetes|\bt2dm\b|\bdiabetes mellitus\b/i,
    condition: 'Type 2 Diabetes Mellitus', reviewedOn: '2026-07-17',
    local: { publisher: 'Malaysia Ministry of Health', title: 'Clinical Practice Guidelines: Management of Type 2 Diabetes Mellitus', version: '6th Edition', year: '2020', summary: 'Active local standard used by the ClearPath plan.' },
    international: { publisher: 'American Diabetes Association', title: 'Standards of Care in Diabetes', version: 'Current curated comparison edition', year: '2026', url: 'https://diabetesjournals.org/care/issue', summary: 'International reference shown for clinician comparison; it does not replace the Malaysian CPG.' },
    difference: 'Review current international recommendations alongside Malaysian formulary, access, and referral pathways before considering any case-level variation.',
    localisation: 'Medication availability, financing, laboratory access, and local referral pathways must be considered before applying international guidance.',
    changes: [
      { section: 'Medications', local: 'Malaysian MoH CPG remains the active plan source.', international: 'International source available for comparison.', reason: 'No clinician-approved replacement has been configured in this demo.', status: 'review' },
      { section: 'Care & Monitoring', local: 'Use Malaysian monitoring and referral pathways.', international: 'International monitoring guidance may differ by setting.', reason: 'Local test access and referral capacity require clinical localisation.', status: 'review' },
    ],
  },
  {
    id: 'hypertension',
    match: /hypertension|hypertensive/i,
    condition: 'Hypertension', reviewedOn: '2026-07-17',
    local: { publisher: 'Malaysia Ministry of Health', title: 'Clinical Practice Guidelines: Management of Hypertension', version: '5th Edition', year: '2018', summary: 'Active local standard used by the ClearPath plan.' },
    international: { publisher: 'European Society of Cardiology', title: 'Guidelines for the Management of Elevated Blood Pressure and Hypertension', version: 'Current curated comparison edition', year: '2024', url: 'https://www.escardio.org/Guidelines/Clinical-Practice-Guidelines', summary: 'International reference shown for clinician comparison; it does not replace the Malaysian CPG.' },
    difference: 'Use the comparison to identify topics requiring clinical review; do not automatically substitute thresholds, targets, or treatment pathways.',
    localisation: 'Confirm local measurement practice, medicine formulary, monitoring capacity, and referral pathways before applying international guidance.',
    changes: [
      { section: 'Overview', local: 'Malaysian CPG is the active clinical baseline.', international: 'International source available for comparison.', reason: 'No clinician-approved replacement has been configured in this demo.', status: 'review' },
      { section: 'Medications', local: 'Use Malaysian formulary-aligned recommendations.', international: 'International treatment pathways may differ.', reason: 'Formulary and local monitoring requirements must be reviewed before adoption.', status: 'review' },
    ],
  },
  {
    id: 'heart-failure',
    match: /heart failure|\bhfref\b|\bhfpef\b/i,
    condition: 'Heart Failure', reviewedOn: '2026-07-17',
    local: { publisher: 'Malaysia Ministry of Health', title: 'Clinical Practice Guidelines: Management of Heart Failure', version: '5th Edition', year: '2023', summary: 'Active local standard used by the ClearPath plan.' },
    international: { publisher: 'European Society of Cardiology', title: 'Guidelines for the Diagnosis and Treatment of Acute and Chronic Heart Failure', version: 'Current curated comparison edition', year: '2023', url: 'https://www.escardio.org/Guidelines/Clinical-Practice-Guidelines', summary: 'International reference shown for clinician comparison; it does not replace the Malaysian CPG.' },
    difference: 'Compare only the relevant clinical question and retain Malaysian CPG recommendations as the active baseline.',
    localisation: 'Consider medicine access, specialist availability, diagnostic capacity, and local escalation pathways before applying international guidance.',
    changes: [
      { section: 'Medications', local: 'Malaysian CPG is the active medication-plan source.', international: 'International source available for comparison.', reason: 'No clinician-approved replacement has been configured in this demo.', status: 'review' },
      { section: 'Follow-up & Safety', local: 'Use Malaysian escalation and referral pathways.', international: 'International follow-up recommendations may differ.', reason: 'Specialist access and escalation routes must be localised.', status: 'review' },
    ],
  },
];

export function getCuratedInternationalGuidance(diagnoses = []) {
  const names = diagnoses.map((diagnosis) => diagnosis?.name || '').filter(Boolean);
  const record = CURATED_GUIDANCE.find((item) => names.some((name) => item.match.test(name)));
  return record ? { status: 'available', record } : { status: 'unavailable', message: SUPPORT_MESSAGE };
}
