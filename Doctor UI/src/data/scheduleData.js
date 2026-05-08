// Sample schedule and patient registry data

export const todaySchedule = [
  {
    id: 'apt-001',
    time: '09:00 AM',
    patient: {
      id: 'p-001',
      name: 'Wong Kin Meng',
      age: 68,
      gender: 'Male',
      nsn: '600521-04-1834',
      photo: null
    },
    status: 'waiting', // waiting, in-progress, done
    isEmergency: false,
    isHighRisk: true,
    triage: {
      vitals: {
        bp: '150/90',
        bpStatus: 'high', // normal, high, critical
        hr: 88,
        temp: 37.2,
        spo2: 96
      },
      chiefComplaint: 'Follow-up for Type 2 Diabetes, numbness in feet',
      notes: 'Patient reports increased thirst and frequent urination'
    }
  },
  {
    id: 'apt-002',
    time: '09:30 AM',
    patient: {
      id: 'p-002',
      name: 'Siti Nurhaliza binti Hassan',
      age: 45,
      gender: 'Female',
      nsn: '810520-10-5678',
      photo: null
    },
    status: 'waiting',
    isEmergency: false,
    isHighRisk: false,
    triage: {
      vitals: {
        bp: '120/80',
        bpStatus: 'normal',
        hr: 72,
        temp: 36.8,
        spo2: 98
      },
      chiefComplaint: 'Routine health screening',
      notes: 'Annual check-up, no acute complaints'
    }
  },
  {
    id: 'apt-003',
    time: '10:00 AM',
    patient: {
      id: 'p-003',
      name: 'Raj Kumar A/L Muthu',
      age: 52,
      gender: 'Male',
      nsn: '740812-14-9012',
      photo: null
    },
    status: 'waiting',
    isEmergency: true,
    isHighRisk: true,
    triage: {
      vitals: {
        bp: '180/110',
        bpStatus: 'critical',
        hr: 102,
        temp: 37.0,
        spo2: 94
      },
      chiefComplaint: 'Severe headache, blurred vision',
      notes: 'Hypertensive urgency suspected, known HTN non-compliant with meds'
    }
  },
  {
    id: 'apt-004',
    time: '10:30 AM',
    patient: {
      id: 'p-004',
      name: 'Lee Mei Ling',
      age: 35,
      gender: 'Female',
      nsn: '910605-07-3456',
      photo: null
    },
    status: 'waiting',
    isEmergency: false,
    isHighRisk: false,
    triage: {
      vitals: {
        bp: '118/75',
        bpStatus: 'normal',
        hr: 68,
        temp: 36.5,
        spo2: 99
      },
      chiefComplaint: 'Prenatal check-up (20 weeks)',
      notes: 'Second pregnancy, no complications so far'
    }
  },
  {
    id: 'apt-005',
    time: '11:00 AM',
    patient: {
      id: 'p-005',
      name: 'Mohammad Faiz bin Yusof',
      age: 72,
      gender: 'Male',
      nsn: '540118-02-7890',
      photo: null
    },
    status: 'waiting',
    isEmergency: false,
    isHighRisk: true,
    triage: {
      vitals: {
        bp: '145/88',
        bpStatus: 'high',
        hr: 78,
        temp: 37.1,
        spo2: 95
      },
      chiefComplaint: 'Chest discomfort on exertion',
      notes: 'History of CAD, post-CABG 2019, on dual antiplatelet therapy'
    }
  },
  {
    id: 'apt-006',
    time: '11:30 AM',
    patient: {
      id: 'p-006',
      name: 'Aminah binti Osman',
      age: 58,
      gender: 'Female',
      nsn: '680923-06-4567',
      photo: null
    },
    status: 'waiting',
    isEmergency: false,
    isHighRisk: false,
    triage: {
      vitals: {
        bp: '130/82',
        bpStatus: 'normal',
        hr: 74,
        temp: 36.7,
        spo2: 97
      },
      chiefComplaint: 'Joint pain, difficulty climbing stairs',
      notes: 'Suspected osteoarthritis, BMI 28'
    }
  }
];

export const patientRegistry = [
  {
    id: 'p-001',
    name: 'Wong Kin Meng',
    age: 68,
    gender: 'Male',
    nsn: '600521-04-1834',
    status: 'active', // active, discharged, follow-up
    lastVisit: '2026-01-07',
    nextReview: '2026-01-10',
    tcaDays: 3,
    diagnoses: ['Type 2 Diabetes Mellitus', 'Diabetic Peripheral Neuropathy', 'Hypertension'],
    riskLevel: 'high',
    phone: '+60 12-345 6789',
    email: 'wongkinmeng@email.com',
    medicalHistory: {
      conditions: [
        { name: 'Type 2 Diabetes Mellitus', diagnosedDate: '2015-03-15', status: 'Active' },
        { name: 'Hypertension', diagnosedDate: '2012-08-20', status: 'Active' },
        { name: 'Diabetic Peripheral Neuropathy', diagnosedDate: '2023-06-10', status: 'Active' },
        { name: 'Hyperlipidemia', diagnosedDate: '2016-01-05', status: 'Active' }
      ],
      medications: [
        { name: 'Metformin 500mg', dosage: 'BD', startDate: '2015-03-20', status: 'Current' },
        { name: 'Amlodipine 5mg', dosage: 'OD', startDate: '2012-09-01', status: 'Current' },
        { name: 'Atorvastatin 20mg', dosage: 'ON', startDate: '2016-02-01', status: 'Current' },
        { name: 'Gabapentin 300mg', dosage: 'TDS', startDate: '2023-06-15', status: 'Current' },
        { name: 'Gliclazide 80mg', dosage: 'BD', startDate: '2018-04-10', endDate: '2022-01-15', status: 'Stopped' }
      ],
      labResults: [
        { test: 'HbA1c', value: '8.5%', date: '2026-01-05', status: 'High' },
        { test: 'Fasting Blood Glucose', value: '9.2 mmol/L', date: '2026-01-05', status: 'High' },
        { test: 'eGFR', value: '65 mL/min', date: '2026-01-05', status: 'Normal' },
        { test: 'Total Cholesterol', value: '4.8 mmol/L', date: '2025-10-15', status: 'Normal' },
        { test: 'LDL', value: '2.5 mmol/L', date: '2025-10-15', status: 'Normal' }
      ],
      procedures: [
        { name: 'Fundoscopy', date: '2025-06-20', result: 'Mild NPDR' },
        { name: 'ECG', date: '2025-01-10', result: 'Normal sinus rhythm' }
      ],
      allergies: ['Sulfa drugs', 'Penicillin']
    }
  },
  {
    id: 'p-002',
    name: 'Siti Nurhaliza binti Hassan',
    age: 45,
    gender: 'Female',
    nsn: '810520-10-5678',
    status: 'active',
    lastVisit: '2026-01-07',
    nextReview: null,
    tcaDays: null,
    diagnoses: ['Annual Health Screening'],
    riskLevel: 'low',
    phone: '+60 13-456 7890',
    email: 'siti.nurhaliza@email.com'
  },
  {
    id: 'p-003',
    name: 'Raj Kumar A/L Muthu',
    age: 52,
    gender: 'Male',
    nsn: '740812-14-9012',
    status: 'follow-up',
    lastVisit: '2026-01-07',
    nextReview: '2026-01-08',
    tcaDays: 1,
    diagnoses: ['Hypertensive Urgency', 'Essential Hypertension', 'Medication Non-compliance'],
    riskLevel: 'critical',
    phone: '+60 14-567 8901',
    email: 'raj.kumar@email.com'
  },
  {
    id: 'p-004',
    name: 'Lee Mei Ling',
    age: 35,
    gender: 'Female',
    nsn: '910605-07-3456',
    status: 'active',
    lastVisit: '2026-01-07',
    nextReview: '2026-02-07',
    tcaDays: 31,
    diagnoses: ['Pregnancy (G2P1, 20 weeks)'],
    riskLevel: 'moderate',
    phone: '+60 15-678 9012',
    email: 'mei.ling@email.com'
  },
  {
    id: 'p-005',
    name: 'Mohammad Faiz bin Yusof',
    age: 72,
    gender: 'Male',
    nsn: '540118-02-7890',
    status: 'follow-up',
    lastVisit: '2026-01-07',
    nextReview: '2026-01-14',
    tcaDays: 7,
    diagnoses: ['Coronary Artery Disease', 'Post-CABG', 'Stable Angina'],
    riskLevel: 'high',
    phone: '+60 16-789 0123',
    email: 'faiz.yusof@email.com'
  },
  {
    id: 'p-006',
    name: 'Aminah binti Osman',
    age: 58,
    gender: 'Female',
    nsn: '680923-06-4567',
    status: 'active',
    lastVisit: '2026-01-07',
    nextReview: '2026-01-21',
    tcaDays: 14,
    diagnoses: ['Osteoarthritis', 'Overweight'],
    riskLevel: 'low',
    phone: '+60 17-890 1234',
    email: 'aminah.osman@email.com'
  },
  {
    id: 'p-007',
    name: 'Tan Wei Ming',
    age: 28,
    gender: 'Male',
    nsn: '980310-14-2345',
    status: 'discharged',
    lastVisit: '2025-12-20',
    nextReview: null,
    tcaDays: null,
    diagnoses: ['Acute Upper Respiratory Infection (Resolved)'],
    riskLevel: 'low',
    phone: '+60 18-901 2345',
    email: 'wei.ming@email.com'
  },
  {
    id: 'p-008',
    name: 'Fatimah binti Ismail',
    age: 65,
    gender: 'Female',
    nsn: '610715-01-6789',
    status: 'follow-up',
    lastVisit: '2026-01-05',
    nextReview: '2026-01-12',
    tcaDays: 5,
    diagnoses: ['Chronic Kidney Disease Stage 3', 'Type 2 Diabetes Mellitus'],
    riskLevel: 'high',
    phone: '+60 19-012 3456',
    email: 'fatimah.ismail@email.com'
  }
];

export const dashboardStats = {
  totalAppointments: 6,
  patientsWaiting: 6,
  patientsInProgress: 0,
  patientsDone: 0,
  emergencyCases: 1,
  highRiskCases: 3
};

export const recentActivity = [
  { id: 1, action: 'Care plan generated', patient: 'Tan Wei Ming', time: '2 days ago', type: 'plan' },
  { id: 2, action: 'Follow-up scheduled', patient: 'Fatimah binti Ismail', time: '2 days ago', type: 'schedule' },
  { id: 3, action: 'Lab results reviewed', patient: 'Mohammad Faiz', time: '3 days ago', type: 'lab' },
  { id: 4, action: 'Prescription renewed', patient: 'Ahmad bin Abdullah', time: '1 week ago', type: 'prescription' },
];
