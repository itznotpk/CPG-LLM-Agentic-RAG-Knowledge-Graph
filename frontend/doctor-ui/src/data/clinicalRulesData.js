// Clinical Decision Support Rules Database
// This would typically come from a backend/database

// Drug-Drug Interactions
export const drugInteractions = [
  {
    drug1: 'metformin',
    drug2: 'empagliflozin',
    severity: 'low',
    description: 'May increase risk of hypoglycemia when combined. Monitor blood glucose closely.',
    recommendation: 'Consider dose adjustment of metformin if hypoglycemia occurs.',
  },
  {
    drug1: 'metformin',
    drug2: 'lisinopril',
    severity: 'low',
    description: 'ACE inhibitors may enhance the hypoglycemic effect of antidiabetic agents.',
    recommendation: 'Monitor blood glucose levels, especially when initiating therapy.',
  },
  {
    drug1: 'amlodipine',
    drug2: 'atorvastatin',
    severity: 'medium',
    description: 'Amlodipine may increase atorvastatin levels, increasing risk of myopathy.',
    recommendation: 'Limit atorvastatin dose to 20mg when used with amlodipine.',
  },
  {
    drug1: 'glipizide',
    drug2: 'metformin',
    severity: 'medium',
    description: 'Combined use increases hypoglycemia risk.',
    recommendation: 'Monitor blood glucose frequently. Educate patient on hypoglycemia symptoms.',
  },
  {
    drug1: 'lisinopril',
    drug2: 'empagliflozin',
    severity: 'medium',
    description: 'Both agents lower blood pressure. Increased risk of hypotension.',
    recommendation: 'Monitor blood pressure closely. Consider lower initial doses.',
  },
  {
    drug1: 'aspirin',
    drug2: 'warfarin',
    severity: 'high',
    description: 'Significantly increased bleeding risk.',
    recommendation: 'Avoid combination unless clearly indicated. Monitor INR closely.',
  },
  {
    drug1: 'metformin',
    drug2: 'contrast dye',
    severity: 'high',
    description: 'Risk of lactic acidosis with iodinated contrast.',
    recommendation: 'Hold metformin 48 hours before and after contrast procedures.',
  },
];

// Drug-Allergy Cross References
export const drugAllergyAlerts = [
  {
    allergen: 'sulfa',
    drugs: ['sulfamethoxazole', 'sulfasalazine', 'glipizide', 'furosemide'],
    severity: 'high',
    description: 'Patient has documented sulfa allergy. These medications contain sulfonamide groups.',
    crossReactivity: 'Variable cross-reactivity between sulfonamide antibiotics and non-antibiotics.',
  },
  {
    allergen: 'penicillin',
    drugs: ['amoxicillin', 'ampicillin', 'piperacillin', 'cephalexin'],
    severity: 'high',
    description: 'Patient allergic to penicillin. Cross-reactivity possible with cephalosporins (~1%).',
    crossReactivity: 'True cross-reactivity with cephalosporins is low but caution advised.',
  },
  {
    allergen: 'nsaid',
    drugs: ['ibuprofen', 'naproxen', 'aspirin', 'diclofenac', 'celecoxib'],
    severity: 'medium',
    description: 'NSAID sensitivity/allergy documented.',
    crossReactivity: 'COX-2 selective inhibitors may be safer but use with caution.',
  },
  {
    allergen: 'ace inhibitor',
    drugs: ['lisinopril', 'enalapril', 'ramipril', 'captopril'],
    severity: 'high',
    description: 'History of ACE inhibitor-induced angioedema.',
    crossReactivity: 'All ACE inhibitors contraindicated. ARBs may be used with caution.',
  },
];

// Contraindications based on conditions
export const contraindications = [
  {
    condition: 'chronic kidney disease',
    conditionCodes: ['N18', 'N18.3', 'N18.4', 'N18.5'],
    drugs: [
      { name: 'metformin', severity: 'high', note: 'Contraindicated if eGFR <30. Reduce dose if eGFR 30-45.' },
      { name: 'nsaids', severity: 'high', note: 'Can worsen renal function and cause fluid retention.' },
      { name: 'gadolinium', severity: 'medium', note: 'Risk of nephrogenic systemic fibrosis.' },
    ],
  },
  {
    condition: 'heart failure',
    conditionCodes: ['I50', 'I50.9'],
    drugs: [
      { name: 'pioglitazone', severity: 'high', note: 'Can cause fluid retention and worsen heart failure.' },
      { name: 'nsaids', severity: 'high', note: 'Can worsen heart failure and cause fluid retention.' },
      { name: 'verapamil', severity: 'high', note: 'Negative inotropic effect may worsen heart failure.' },
    ],
  },
  {
    condition: 'liver disease',
    conditionCodes: ['K70', 'K71', 'K72', 'K74'],
    drugs: [
      { name: 'metformin', severity: 'medium', note: 'Use with caution. Risk of lactic acidosis in severe liver disease.' },
      { name: 'atorvastatin', severity: 'medium', note: 'Monitor LFTs. Reduce dose in moderate impairment.' },
      { name: 'acetaminophen', severity: 'medium', note: 'Limit to 2g/day in liver disease.' },
    ],
  },
  {
    condition: 'pregnancy',
    conditionCodes: ['Z33'],
    drugs: [
      { name: 'lisinopril', severity: 'high', note: 'ACE inhibitors are teratogenic. Contraindicated in pregnancy.' },
      { name: 'atorvastatin', severity: 'high', note: 'Statins are contraindicated in pregnancy.' },
      { name: 'warfarin', severity: 'high', note: 'Teratogenic. Use LMWH instead.' },
      { name: 'empagliflozin', severity: 'medium', note: 'Limited data. Not recommended in pregnancy.' },
    ],
  },
];

// Dosage adjustment rules
export const dosageRules = [
  {
    drug: 'metformin',
    adjustments: [
      { condition: 'eGFR >= 60', dose: 'Standard dosing up to 2000mg/day', adjustment: 'none' },
      { condition: 'eGFR 45-59', dose: 'Max 2000mg/day', adjustment: 'monitor' },
      { condition: 'eGFR 30-44', dose: 'Max 1000mg/day', adjustment: 'reduce' },
      { condition: 'eGFR < 30', dose: 'Contraindicated', adjustment: 'stop' },
    ],
    ageAdjustment: 'Use with caution in elderly (>80 years). Consider lower doses.',
    weightAdjustment: null,
  },
  {
    drug: 'empagliflozin',
    adjustments: [
      { condition: 'eGFR >= 45', dose: '10-25mg once daily', adjustment: 'none' },
      { condition: 'eGFR 30-44', dose: '10mg once daily (for CV/renal benefit)', adjustment: 'reduce' },
      { condition: 'eGFR < 30', dose: 'Not recommended for glycemic control', adjustment: 'caution' },
    ],
    ageAdjustment: 'No specific adjustment. Monitor for volume depletion in elderly.',
    weightAdjustment: null,
  },
  {
    drug: 'lisinopril',
    adjustments: [
      { condition: 'eGFR >= 30', dose: 'Start 5-10mg, titrate to 20-40mg daily', adjustment: 'none' },
      { condition: 'eGFR 10-29', dose: 'Start 2.5-5mg, max 40mg', adjustment: 'reduce' },
      { condition: 'eGFR < 10', dose: 'Start 2.5mg, titrate carefully', adjustment: 'reduce' },
    ],
    ageAdjustment: 'Start at lower dose in elderly. More sensitive to hypotensive effects.',
    weightAdjustment: null,
  },
  {
    drug: 'atorvastatin',
    adjustments: [
      { condition: 'Normal renal function', dose: '10-80mg once daily', adjustment: 'none' },
      { condition: 'CKD', dose: 'No dose adjustment required', adjustment: 'none' },
    ],
    ageAdjustment: 'Consider lower starting dose in elderly due to increased myopathy risk.',
    weightAdjustment: null,
  },
];

// Helper function to check drug interactions
export function checkDrugInteractions(currentMeds, newMeds) {
  const allMeds = [...currentMeds, ...newMeds].map(m => m.name?.toLowerCase() || m.toLowerCase());
  const interactions = [];

  for (let i = 0; i < allMeds.length; i++) {
    for (let j = i + 1; j < allMeds.length; j++) {
      const drug1 = allMeds[i];
      const drug2 = allMeds[j];
      
      const interaction = drugInteractions.find(
        int => (int.drug1 === drug1 && int.drug2 === drug2) ||
               (int.drug1 === drug2 && int.drug2 === drug1)
      );
      
      if (interaction) {
        interactions.push({
          ...interaction,
          drugs: [drug1, drug2],
        });
      }
    }
  }
  
  return interactions;
}

// Helper function to check allergy alerts
export function checkAllergyAlerts(allergies, medications) {
  const alerts = [];
  const allergyList = allergies.toLowerCase().split(',').map(a => a.trim());
  
  allergyList.forEach(allergy => {
    const allergyRule = drugAllergyAlerts.find(
      rule => allergy.includes(rule.allergen.toLowerCase())
    );
    
    if (allergyRule) {
      medications.forEach(med => {
        const medName = (med.name || med).toLowerCase();
        if (allergyRule.drugs.some(d => medName.includes(d))) {
          alerts.push({
            allergen: allergyRule.allergen,
            drug: med.name || med,
            severity: allergyRule.severity,
            description: allergyRule.description,
            crossReactivity: allergyRule.crossReactivity,
          });
        }
      });
    }
  });
  
  return alerts;
}

// Helper function to check contraindications
export function checkContraindications(conditions, medications) {
  const alerts = [];
  
  conditions.forEach(condition => {
    const conditionLower = condition.toLowerCase();
    
    const rule = contraindications.find(
      c => conditionLower.includes(c.condition.toLowerCase())
    );
    
    if (rule) {
      medications.forEach(med => {
        const medName = (med.name || med).toLowerCase();
        const contraindicated = rule.drugs.find(d => medName.includes(d.name));
        
        if (contraindicated) {
          alerts.push({
            condition: rule.condition,
            drug: med.name || med,
            severity: contraindicated.severity,
            note: contraindicated.note,
          });
        }
      });
    }
  });
  
  return alerts;
}

// Calculate eGFR using CKD-EPI equation
export function calculateEGFR(creatinine, age, isFemale, isBlack = false) {
  if (!creatinine || !age) return null;
  
  let kappa = isFemale ? 0.7 : 0.9;
  let alpha = isFemale ? -0.329 : -0.411;
  let multiplier = isFemale ? 1.018 : 1.0;
  
  if (isBlack) multiplier *= 1.159;
  
  const creatRatio = creatinine / kappa;
  const minRatio = Math.min(creatRatio, 1);
  const maxRatio = Math.max(creatRatio, 1);
  
  const eGFR = 141 * Math.pow(minRatio, alpha) * Math.pow(maxRatio, -1.209) * 
               Math.pow(0.993, age) * multiplier;
  
  return Math.round(eGFR);
}

// Get dosage recommendation
export function getDosageRecommendation(drugName, eGFR, age, weight) {
  const rule = dosageRules.find(r => 
    drugName.toLowerCase().includes(r.drug.toLowerCase())
  );
  
  if (!rule) return null;
  
  let recommendation = {
    drug: drugName,
    eGFR,
    age,
    weight,
    adjustments: [],
  };
  
  // Check eGFR-based adjustments
  if (eGFR !== null) {
    for (const adj of rule.adjustments) {
      // Parse the condition (simplified)
      if (adj.condition.includes('>=') && eGFR >= parseInt(adj.condition.match(/\d+/)[0])) {
        recommendation.renalDose = adj.dose;
        recommendation.renalAdjustment = adj.adjustment;
        break;
      } else if (adj.condition.includes('<') && !adj.condition.includes('=') && 
                 eGFR < parseInt(adj.condition.match(/\d+/)[0])) {
        recommendation.renalDose = adj.dose;
        recommendation.renalAdjustment = adj.adjustment;
        break;
      } else if (adj.condition.includes('-')) {
        const [min, max] = adj.condition.match(/\d+/g).map(Number);
        if (eGFR >= min && eGFR <= max) {
          recommendation.renalDose = adj.dose;
          recommendation.renalAdjustment = adj.adjustment;
          break;
        }
      }
    }
  }
  
  // Age adjustment
  if (age && age > 65 && rule.ageAdjustment) {
    recommendation.ageNote = rule.ageAdjustment;
    recommendation.adjustments.push('elderly');
  }
  
  return recommendation;
}
