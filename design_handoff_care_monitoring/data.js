/* Shared mock data for the Care & Monitoring redesign.
   Cardiac case from the reference screenshots: 23-y-o female, NSTEMI post-PCI,
   warfarin + fluconazole + amiodarone triple therapy. */
window.CM_DATA = {
  procedures: [
    {
      id: 'p1',
      name: 'ECG',
      detail: 'Baseline assessment post-PCI; assess rhythm, ischaemic changes, and QT prolongation risk from amiodarone.',
      note: '23-year-old female on amiodarone post-PCI — ECG needed to assess QT interval and detect any new ischaemic changes before continuing antiarrhythmic therapy.',
      urgency: 'Today',
    },
    {
      id: 'p2',
      name: 'Echocardiography',
      detail: 'Assess LVEF and cardiac function post-NSTEMI to guide ACE-I and beta-blocker therapy duration.',
      note: 'Post-NSTEMI LVEF determines eligibility and duration of ACE-I and beta-blocker therapy; a reduced EF would also change prognosis and follow-up intensity.',
      urgency: 'This admission',
    },
    {
      id: 'p3',
      name: 'Lipid profile',
      detail: 'TC, LDL-C, HDL-C, TG — baseline assessment; target LDL-C <1.8 mmol/L post-ACS.',
      note: 'Baseline lipids anchor high-intensity statin titration toward the post-ACS LDL-C <1.8 mmol/L target and provide a reference for the 6-week recheck.',
      urgency: 'Baseline',
    },
    {
      id: 'p4',
      name: 'Renal function',
      detail: 'eGFR, creatinine — baseline to guide ACE-I, metformin, and sitagliptin dosing.',
      note: 'eGFR is required before initiating ACE-I and to dose-adjust metformin and sitagliptin; contrast load from PCI also warrants a baseline for comparison.',
      urgency: 'Baseline',
    },
    {
      id: 'p5',
      name: 'LFTs',
      detail: 'Baseline given concurrent fluconazole and amiodarone use; both agents associated with hepatotoxicity.',
      note: 'Both fluconazole and amiodarone carry hepatotoxicity risk; a baseline allows early detection of drug-induced liver injury during co-administration.',
      urgency: 'Baseline',
    },
    {
      id: 'p6',
      name: 'INR monitoring',
      detail: 'Intensified frequency during fluconazole overlap (5 days remaining) and amiodarone co-administration.',
      note: 'Fluconazole and amiodarone both potentiate warfarin; intensified INR checks during the overlap window mitigate a significant bleeding risk.',
      urgency: 'Today',
    },
  ],

  monitoring: [
    { id: 'm1', test: 'INR',                    schedule: 'Daily during fluconazole course, then twice weekly', target: '2.0–2.5',  priority: 'high' },
    { id: 'm2', test: 'LFTs',                   schedule: 'Baseline, then weekly for 4 weeks',                  target: 'Within normal range', priority: 'high' },
    { id: 'm3', test: 'Renal function',         schedule: 'Baseline + q3 months', sub: 'eGFR / creatinine',     target: null,        priority: 'routine' },
    { id: 'm4', test: 'Lipid profile',          schedule: 'Baseline + 6 weeks post-statin initiation', sub: 'LDL-C', target: 'LDL-C <1.8 mmol/L', priority: 'routine' },
    { id: 'm5', test: 'HbA1c',                  schedule: 'q3 months',            target: 'Individualised to hypoglycaemia risk', priority: 'routine' },
    { id: 'm6', test: 'ECG',                    schedule: 'Baseline + q6 months', target: null,                 priority: 'routine' },
  ],

  lifestyle: [
    { id: 'l1', goal: 'Cardiac rehabilitation referral — structured exercise and secondary prevention', category: 'Exercise' },
    { id: 'l2', goal: 'Smoking cessation counselling and pharmacotherapy if applicable',                category: 'Lifestyle' },
    { id: 'l3', goal: 'Mediterranean-style diet; limit sodium to <2 g/day',                            category: 'Diet' },
    { id: 'l4', goal: 'Medication adherence support — triple therapy bleeding-risk education',         category: 'Adherence' },
  ],
};
