export const GRAPH_NODES = [
  // CPG nodes
  { id: 'cpg-htn',    type: 'cpg',     label: 'CPG Hypertension' },
  { id: 'cpg-hf',     type: 'cpg',     label: 'CPG Heart Failure' },
  { id: 'cpg-af',     type: 'cpg',     label: 'CPG Atrial Fibrillation' },
  { id: 'cpg-stroke', type: 'cpg',     label: 'CPG Stroke' },
  { id: 'cpg-lipid',  type: 'cpg',     label: 'CPG Dyslipidaemia' },

  // ICD nodes
  { id: 'icd-ba00',   type: 'icd',     label: 'BA00 Essential HTN' },
  { id: 'icd-ba81',   type: 'icd',     label: 'BA81 Heart Failure' },
  { id: 'icd-bc80',   type: 'icd',     label: 'BC80 Atrial Fibrillation' },
  { id: 'icd-8b20',   type: 'icd',     label: '8B20 Ischaemic Stroke' },
  { id: 'icd-5c80',   type: 'icd',     label: '5C80 Dyslipidaemia' },
  { id: 'icd-ba80',   type: 'icd',     label: 'BA80 Secondary HTN' },

  // Drug nodes
  { id: 'drug-amlod',  type: 'drug',   label: 'Amlodipine' },
  { id: 'drug-rami',   type: 'drug',   label: 'Ramipril' },
  { id: 'drug-furo',   type: 'drug',   label: 'Furosemide' },
  { id: 'drug-warf',   type: 'drug',   label: 'Warfarin' },
  { id: 'drug-aspirin',type: 'drug',   label: 'Aspirin' },
  { id: 'drug-statin', type: 'drug',   label: 'Atorvastatin' },
  { id: 'drug-metop',  type: 'drug',   label: 'Metoprolol' },

  // Symptom nodes
  { id: 'sym-headache',type: 'symptom',label: 'Headache' },
  { id: 'sym-dyspnea', type: 'symptom',label: 'Dyspnoea' },
  { id: 'sym-oedema',  type: 'symptom',label: 'Ankle Oedema' },
  { id: 'sym-palpita', type: 'symptom',label: 'Palpitations' },
  { id: 'sym-weakness',type: 'symptom',label: 'Limb Weakness' },
  { id: 'sym-chol',    type: 'symptom',label: 'Hypercholesterolaemia' },
];

export const GRAPH_EDGES = [
  // ICD ↔ CPG
  { source: 'icd-ba00',  target: 'cpg-htn',    label: 'coded_in' },
  { source: 'icd-ba81',  target: 'cpg-hf',     label: 'coded_in' },
  { source: 'icd-bc80',  target: 'cpg-af',     label: 'coded_in' },
  { source: 'icd-8b20',  target: 'cpg-stroke', label: 'coded_in' },
  { source: 'icd-5c80',  target: 'cpg-lipid',  label: 'coded_in' },
  { source: 'icd-ba80',  target: 'cpg-htn',    label: 'coded_in' },

  // Drug ↔ ICD (treats)
  { source: 'drug-amlod',  target: 'icd-ba00',  label: 'treats' },
  { source: 'drug-rami',   target: 'icd-ba00',  label: 'treats' },
  { source: 'drug-rami',   target: 'icd-ba81',  label: 'treats' },
  { source: 'drug-furo',   target: 'icd-ba81',  label: 'treats' },
  { source: 'drug-warf',   target: 'icd-bc80',  label: 'indicated_for' },
  { source: 'drug-aspirin',target: 'icd-8b20',  label: 'indicated_for' },
  { source: 'drug-statin', target: 'icd-5c80',  label: 'treats' },
  { source: 'drug-metop',  target: 'icd-ba81',  label: 'treats' },
  { source: 'drug-metop',  target: 'icd-bc80',  label: 'treats' },

  // Symptom ↔ ICD (presents_with)
  { source: 'sym-headache', target: 'icd-ba00',  label: 'presents_with' },
  { source: 'sym-dyspnea',  target: 'icd-ba81',  label: 'presents_with' },
  { source: 'sym-oedema',   target: 'icd-ba81',  label: 'presents_with' },
  { source: 'sym-palpita',  target: 'icd-bc80',  label: 'presents_with' },
  { source: 'sym-weakness', target: 'icd-8b20',  label: 'presents_with' },
  { source: 'sym-chol',     target: 'icd-5c80',  label: 'presents_with' },
];

export const NODE_COLORS = {
  cpg:     '#2f5fd0',
  icd:     '#8b86a8',
  drug:    '#2a9d6c',
  symptom: '#b4843a',
};
