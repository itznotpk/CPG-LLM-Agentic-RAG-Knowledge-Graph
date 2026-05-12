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
];

export const patientRegistry = [
  {
    id: 'p-001',
    name: 'Wong Kin Meng',
    age: 68,
    gender: 'Male',
    nsn: '600521-04-1834',
    status: 'active',
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
  totalAppointments: 2,
  patientsWaiting: 2,
  patientsInProgress: 0,
  patientsDone: 0,
};

export const recentActivity = [
  { id: 1, action: 'Care plan generated', patient: 'Tan Wei Ming', time: '2 days ago', type: 'plan' },
  { id: 2, action: 'Follow-up scheduled', patient: 'Fatimah binti Ismail', time: '2 days ago', type: 'schedule' },
];
