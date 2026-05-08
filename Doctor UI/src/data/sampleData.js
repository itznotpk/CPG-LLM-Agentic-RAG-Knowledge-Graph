// Sample data for the CPG LLM demo application

export const samplePatientData = {
  name: "Wong Kin Meng ",
  dob: "1958-03-15",
  nsn: "580315-08-1234",
  gender: "Male",
  age: 68,
};

// Mock MPIS Patient Database for NRIC lookup
export const mpisPatientDatabase = {
  "580315-08-1234": {
    patient: {
      name: "Wong Kin Meng",
      dob: "1958-03-15",
      nsn: "580315-08-1234",
      gender: "Male",
      age: 68,
    },
    mpisData: {
      race: "Malay",
      ethnicity: "Malaysian",
      allergies: "None known",
      comorbidities: ["Type 2 Diabetes Mellitus", "Hypertension", "Hyperlipidemia"],
      currentMeds: [
        { name: "Metformin", dose: "1000mg", frequency: "BD" },
        { name: "Glipizide", dose: "5mg", frequency: "OD" },
        { name: "Amlodipine", dose: "5mg", frequency: "OD" },
        { name: "Atorvastatin", dose: "20mg", frequency: "ON" },
      ],
      vitalsHistory: [
        { date: "2025-02-15", bpSystolic: 158, bpDiastolic: 95, hr: 82, temp: 36.5, spo2: 97, weight: 94 },
        { date: "2025-03-20", bpSystolic: 155, bpDiastolic: 92, hr: 80, temp: 36.6, spo2: 97, weight: 93.5 },
        { date: "2025-04-18", bpSystolic: 150, bpDiastolic: 90, hr: 78, temp: 36.4, spo2: 98, weight: 93 },
        { date: "2025-05-22", bpSystolic: 148, bpDiastolic: 88, hr: 76, temp: 36.5, spo2: 97, weight: 92.5 },
        { date: "2025-06-19", bpSystolic: 152, bpDiastolic: 92, hr: 80, temp: 36.7, spo2: 96, weight: 93 },
        { date: "2025-07-17", bpSystolic: 146, bpDiastolic: 86, hr: 75, temp: 36.5, spo2: 98, weight: 92 },
        { date: "2025-08-21", bpSystolic: 144, bpDiastolic: 85, hr: 74, temp: 36.4, spo2: 98, weight: 91.5 },
        { date: "2025-09-18", bpSystolic: 148, bpDiastolic: 88, hr: 78, temp: 36.6, spo2: 97, weight: 92 },
        { date: "2025-10-16", bpSystolic: 145, bpDiastolic: 86, hr: 76, temp: 36.5, spo2: 98, weight: 91 },
        { date: "2025-11-20", bpSystolic: 143, bpDiastolic: 85, hr: 77, temp: 36.4, spo2: 98, weight: 91.5 },
        { date: "2025-12-18", bpSystolic: 140, bpDiastolic: 84, hr: 75, temp: 36.5, spo2: 98, weight: 91 },
        { date: "2026-01-08", bpSystolic: 142, bpDiastolic: 86, hr: 78, temp: 36.6, spo2: 98, weight: 92 },
      ],
    },
  },
  "750622-10-5678": {
    patient: {
      name: "Siti Aminah binti Yusof",
      dob: "1975-06-22",
      nsn: "750622-10-5678",
      gender: "Female",
      age: 51,
    },
    mpisData: {
      race: "Malay",
      ethnicity: "Malaysian",
      allergies: "Penicillin",
      comorbidities: ["Asthma", "Obesity"],
      currentMeds: [
        { name: "Salbutamol Inhaler", dose: "100mcg", frequency: "PRN" },
        { name: "Budesonide Inhaler", dose: "200mcg", frequency: "BD" },
      ],
    },
  },
  "680910-14-9012": {
    patient: {
      name: "Rajesh A/L Krishnan",
      dob: "1968-09-10",
      nsn: "680910-14-9012",
      gender: "Male",
      age: 58,
    },
    mpisData: {
      race: "Indian",
      ethnicity: "Malaysian",
      allergies: "Sulfa drugs",
      comorbidities: ["Coronary Artery Disease", "Type 2 Diabetes Mellitus", "Chronic Kidney Disease Stage 3"],
      currentMeds: [
        { name: "Aspirin", dose: "100mg", frequency: "OD" },
        { name: "Metformin", dose: "500mg", frequency: "BD" },
        { name: "Clopidogrel", dose: "75mg", frequency: "OD" },
        { name: "Bisoprolol", dose: "5mg", frequency: "OD" },
      ],
    },
  },
  "850415-07-3456": {
    patient: {
      name: "Lee Wei Ming",
      dob: "1985-04-15",
      nsn: "850415-07-3456",
      gender: "Male",
      age: 41,
    },
    mpisData: {
      race: "Chinese",
      ethnicity: "Malaysian",
      allergies: "None known",
      comorbidities: [],
      currentMeds: [],
    },
  },
};

export const sampleClinicalNotes = {
  history: `Patient reports persistently high home glucose readings (fasting 12-15, postprandial >15) over 3 months a/w polydipsia and polyuria. Admits non-compliance to meds. Exam: BP 142/86, diminished light touch sensation on bilateral big toes. No wounds.`,
};

export const sampleVitals = {
  bpSystolic: 142,
  bpDiastolic: 86,
  hr: 78,
  temp: 36.6,
  rr: 16,
  spo2: 98,
  weight: 92,
  height: 170,
};

export const sampleMPISData = {
  race: "Malay",
  ethnicity: "Malaysian",
  allergies: "None known",
  comorbidities: ["Type 2 Diabetes Mellitus", "Hypertension", "Hyperlipidemia"],
  currentMeds: [
    { name: "Metformin", dose: "1000mg", frequency: "BD" },
    { name: "Glipizide", dose: "5mg", frequency: "OD" },
    { name: "Amlodipine", dose: "5mg", frequency: "OD" },
    { name: "Atorvastatin", dose: "20mg", frequency: "ON" },
  ],
};

export const sampleDiagnosis = {
  differentials: [
    { id: 1, name: "Type 2 Diabetes Mellitus - Uncontrolled with Peripheral Neuropathy", icdCode: "E11.65", probability: 85, risk: "high" },
    { id: 2, name: "Diabetic Peripheral Neuropathy", icdCode: "E11.42", probability: 70, risk: "medium" },
    { id: 3, name: "Metabolic Syndrome", icdCode: "E88.81", probability: 65, risk: "medium" },
    { id: 4, name: "Chronic Kidney Disease Stage 2-3", icdCode: "N18.3", probability: 25, risk: "medium" },
    { id: 5, name: "Hypertensive Heart Disease", icdCode: "I11.9", probability: 15, risk: "low" },
  ],
  selectedDiagnosisIds: [1],
};

export const sampleCarePlan = {
  clinicalSummary: `68-year-old Malay male with poorly controlled Type 2 Diabetes Mellitus (suspected HbA1c >9%), presenting with classic hyperglycemic symptoms (polydipsia, polyuria) and evidence of early peripheral neuropathy. Current glycemic control inadequate on Metformin and Glipizide. Cardiovascular risk factors include hypertension (BP 142/86) and obesity (BMI 31.8). Requires medication optimization and intensification of diabetes management.`,

  interventions: [
    {
      id: 1,
      name: "Dilated Retinal Examination",
      code: "ICHI: PZX.DB.AC",
      rationale: "Annual screening for diabetic retinopathy - overdue",
      urgency: "Within 2 weeks",
      accepted: true,
    },
    {
      id: 2,
      name: "Comprehensive Foot Examination",
      code: "ICHI: PZX.BD.AE",
      rationale: "Evidence of peripheral neuropathy on exam",
      urgency: "Today",
      accepted: true,
    },
    {
      id: 3,
      name: "Diabetes Self-Management Education",
      code: "ICHI: PZX.HA.ZZ",
      rationale: "Non-compliance reported, reinforce education",
      urgency: "This visit",
      accepted: true,
    },
  ],

  medications: {
    stop: [
      {
        id: 1,
        name: "Glipizide",
        dose: "5mg OD",
        reason: "Replacing with SGLT2i for better cardiovascular and renal protection",
        cpgRef: "CPG-DM-2020, Pg 26",
      },
    ],
    start: [
      {
        id: 2,
        name: "Empagliflozin",
        dose: "10mg OD",
        reason: "SGLT2 inhibitor - provides glycemic control with cardiovascular and renal benefits",
        instructions: "Take in the morning. Review sick day rules.",
        cpgRef: "CPG-DM-2020, Pg 28",
      },
      {
        id: 3,
        name: "Lisinopril",
        dose: "5mg OD",
        reason: "ACE inhibitor for renal protection and improved BP control",
        instructions: "Monitor potassium and creatinine in 2 weeks",
        cpgRef: "CPG-HTN-2018, Pg 42",
      },
    ],
    change: [
      {
        id: 7,
        name: "Metformin XR",
        previousDose: "1000mg OD",
        newDose: "1000mg BD",
        reason: "Uptitrate for better glycemic control",
        kiv: "KIV increase to 2000mg BD if tolerated",
        cpgRef: "CPG-DM-2020, Pg 25",
      },
    ],
    continue: [
      {
        id: 5,
        name: "Amlodipine",
        dose: "5mg OD",
        reason: "Ongoing BP management",
        cpgRef: "CPG-HTN-2018, Pg 35",
      },
      {
        id: 6,
        name: "Atorvastatin",
        dose: "20mg ON",
        reason: "Lipid management - consider uptitration",
        cpgRef: "CPG-DM-2020, Pg 32",
      },
    ],
  },

  monitoring: [
    { id: 1, task: "Daily home blood glucose monitoring (fasting + 2-hour post-prandial)", schedule: "Daily", accepted: true },
    { id: 2, task: "Re-check BP at nearest clinic", schedule: "1 week", accepted: true },
    { id: 3, task: "Repeat HbA1c", schedule: "3 months", accepted: true },
    { id: 4, task: "Urine microalbumin/creatinine ratio", schedule: "3 months", accepted: true },
    { id: 5, task: "Renal function panel (eGFR, Cr, K+)", schedule: "2 weeks", accepted: true },
    { id: 6, task: "Weekly weight monitoring", schedule: "Weekly", accepted: true },
  ],

  lifestyle: [
    { id: 1, goal: "Initiate walking program - 30 minutes, 5 days per week", category: "Exercise" },
    { id: 2, goal: "Reduce carbohydrate intake, follow diabetic diet plan", category: "Diet" },
    { id: 3, goal: "Target weight loss of 5-7% body weight over 6 months", category: "Weight" },
    { id: 4, goal: "Limit sodium intake to <2g/day for blood pressure control", category: "Diet" },
    { id: 5, goal: "Smoking cessation counseling if applicable", category: "Lifestyle" },
  ],

  investigations: [
    { id: 1, name: "HbA1c", code: "LOINC: 4548-4", priority: "Urgent", accepted: true },
    { id: 2, name: "Fasting Lipid Profile", code: "LOINC: 57698-3", priority: "Routine", accepted: true },
    { id: 3, name: "Urine Microalbumin/Creatinine Ratio", code: "LOINC: 14959-1", priority: "Urgent", accepted: true },
    { id: 4, name: "Renal Function Panel (eGFR, Cr, K+)", code: "LOINC: 24362-6", priority: "Urgent", accepted: true },
    { id: 5, name: "Liver Function Test", code: "LOINC: 24325-3", priority: "Routine", accepted: true },
  ],

  disposition: {
    followUp: "4 weeks",
    referrals: [
      { specialty: "Ophthalmology", reason: "Dilated retinal exam for diabetic retinopathy screening", urgency: "2 weeks" },
      { specialty: "Dietitian", reason: "Medical nutrition therapy for diabetes and weight management", urgency: "2 weeks" },
    ],
    patientEducation: [
      { text: "Reinforce compliance and explain complications of uncontrolled diabetes", category: "Compliance" },
      { text: "SGLT2 inhibitor sick day rules - hold medication if ill, report symptoms immediately", category: "Medication" },
      { text: "Regular foot check - daily inspection for wounds, blisters, or skin changes", category: "Self-Care" },
      { text: "Hypoglycemia recognition and management - carry glucose tablets", category: "Safety" },
      { text: "Signs of diabetic ketoacidosis (rare but important with SGLT2i) - nausea, vomiting, abdominal pain", category: "Safety" },
      { text: "Importance of regular follow-up visits and lab monitoring", category: "Compliance" },
    ],
  },

  cpgReferences: [
    { title: "MoH CPG Management of Type 2 Diabetes Mellitus", edition: "6th Edition", page: "25-28", year: "2020" },
    { title: "MoH CPG Management of Hypertension", edition: "5th Edition", page: "42", year: "2018" },
    { title: "ADA Standards of Medical Care in Diabetes", edition: "2024", page: "S140-S156", year: "2024" },
    { title: "KDIGO Clinical Practice Guideline for Diabetes in CKD", edition: "2022", page: "18-22", year: "2022" },
  ],
};
