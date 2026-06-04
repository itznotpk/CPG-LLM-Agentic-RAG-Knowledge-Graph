# Clinical Practice Guidelines (CPG) Test Cases

This document contains a set of clinical vignettes designed to test the capabilities of the Agentic RAG assistant against the currently chunked CPGs in the vector database. Each test case includes the user query and the expected ground truth / clinical outcome based on Malaysian CPG standards.

## 1. STEMI (4th Edition) - Acute Management & Reperfusion
**Target CPG:** Management of Acute ST Segment Elevation Myocardial Infarction (STEMI) – (4th Edition)
**Test Focus:** Time-sensitive protocols, specific pharmacological doses, decision trees for reperfusion.

**User Query:**
> "A 55-year-old male presents to the Emergency Department with severe crushing chest pain radiating to his left arm, which started 2 hours ago. His ECG shows ST elevation in leads V1-V4. He has no known allergies and no contraindications. What is the recommended initial pharmacological therapy and what is the target timeframe for reperfusion?"

**Expected Ground Truth:**
*   **Summary:** Acute anterior STEMI within the reperfusion window.
*   **Medication Changes:** 
    *   START: Aspirin 300mg stat (loading dose).
    *   START: P2Y12 inhibitor (e.g., Ticagrelor 180mg OR Clopidogrel 300-600mg loading dose).
    *   Consider Sublingual Nitroglycerin (NTG).
*   **Monitoring & Next Steps:** 
    *   Primary Percutaneous Coronary Intervention (PCI) is the preferred reperfusion strategy if it can be performed within a door-to-balloon time of **< 90 minutes**.
    *   If PCI cannot be achieved within 120 minutes of diagnosis, immediate fibrinolytic therapy (within 30 mins) is recommended.

---

## 2. Dyslipidaemia (6th Ed) & CVD in Women - Risk Stratification
**Target CPG:** Management of Dyslipidaemia 2023 (6th Edition), Prevention of Cardiovascular Disease in Women (2nd Edition)
**Test Focus:** Risk categorization and intensive statin targeting.

**User Query:**
> "A 48-year-old female patient with a 5-year history of Type 2 Diabetes and current smoking habit presents for a health checkup. Her latest LDL-C is 3.5 mmol/L. According to the guidelines, what is her cardiovascular risk category, and what specific medication and dose should be initiated to hit the target LDL-C?"

**Expected Ground Truth:**
*   **Summary:** Patient is classified as High Risk (or Very High Risk depending on target organ damage) due to Diabetes + Smoking.
*   **Medication Changes:**
    *   START: High-intensity statin therapy (e.g., Atorvastatin 40-80mg daily OR Rosuvastatin 20-40mg daily).
*   **Follow-up / Goals:** Target LDL-C should be `< 1.8 mmol/L` for High Risk or `< 1.4 mmol/L` (and >50% reduction from baseline) if classified as Very High Risk.

---

## 3. Heart Failure (5th Edition) - Foundational Therapy
**Target CPG:** Management of Heart Failure (5th Edition)
**Test Focus:** Multi-drug guideline-directed medical therapy (GDMT) initiation.

**User Query:**
> "A 65-year-old man is newly diagnosed with Heart Failure with reduced Ejection Fraction (HFrEF) with an LVEF of 30%. His blood pressure is 130/80 mmHg and heart rate is 75 bpm. He is clinically stable and not congested. What foundational medication classes should be started for this patient?"

**Expected Ground Truth:**
*   **Summary:** Stable newly diagnosed HFrEF.
*   **Medication Changes:** The four pillars of HFrEF therapy should be initiated (simultaneously or sequentially):
    1.  ACE-Inhibitor (ACEI) OR ARNI (Sacubitril/Valsartan).
    2.  Beta-blocker (e.g., Bisoprolol, Carvedilol).
    3.  Mineralocorticoid Receptor Antagonist (MRA) (e.g., Spironolactone).
    4.  SGLT2 inhibitor (e.g., Dapagliflozin, Empagliflozin).

---

## 4. Ischaemic Stroke (3rd Edition) - Thrombolysis Window
**Target CPG:** Management of Ischaemic Stroke (3rd Edition)
**Test Focus:** Strict timeline logic and drug dosages.

**User Query:**
> "A 68-year-old female is brought to the emergency department with sudden onset right-sided weakness and aphasia that started exactly 2.5 hours ago. A CT scan of the brain shows no hemorrhage. Her blood pressure is 160/90 mmHg. Is she a candidate for intravenous thrombolysis, and if so, what is the recommended drug and dosage protocol?"

**Expected Ground Truth:**
*   **Summary:** Acute Ischaemic Stroke within the therapeutic window.
*   **Monitoring & Next Steps:** Yes, she is a candidate for IV thrombolysis as she is within the 4.5-hour window and has no hemorrhage.
*   **Medication Changes:** 
    *   START: IV Alteplase (rt-PA) at a dose of **0.9 mg/kg** (maximum dose 90 mg).
    *   Administration protocol: 10% of the dose given as an initial bolus over 1 minute, and the remaining 90% given as an infusion over 60 minutes.

---

## 5. Anaesthesia Monitoring - Safety Standards
**Target CPG:** Recommendations For Patient Safety And Minimal Monitoring Standards During Anaesthesia And Recovery
**Test Focus:** Protocol retrieval and mandatory hardware/monitoring checks.

**User Query:**
> "A 50-year-old patient is scheduled for an elective laparoscopic cholecystectomy under general anaesthesia. According to the national safety standards, what are the mandatory, minimal monitoring modalities that must be attached and running during the maintenance of general anaesthesia?"

**Expected Ground Truth:**
*   **Summary:** Standard general anaesthesia monitoring requirements.
*   **Monitoring & Next Steps:** Mandatory minimum monitoring must include:
    1.  Continuous ECG
    2.  Non-Invasive Blood Pressure (NIBP) measured at least every 5 minutes
    3.  Continuous Pulse Oximetry (SpO2)
    4.  Continuous Capnography (EtCO2)
    5.  Temperature monitoring (or available to be measured)

---

## 6. Atrial Fibrillation - Anticoagulation Strategy
**Target CPG:** Management of Atrial Fibrillation
**Test Focus:** Scoring systems (CHA2DS2-VASc) and comparative drug recommendations.

**User Query:**
> "A 72-year-old male with non-valvular Atrial Fibrillation and a history of hypertension presents for stroke prevention assessment. His CHA2DS2-VASc score is calculated to be 3. Should he be prescribed an antiplatelet or an oral anticoagulant? Furthermore, are Direct Oral Anticoagulants (DOACs) preferred over Warfarin for this patient?"

**Expected Ground Truth:**
*   **Summary:** Non-valvular AF with high stroke risk (CHA2DS2-VASc >= 2).
*   **Medication Changes:**
    *   An oral anticoagulant (OAC) is strongly indicated. Antiplatelet therapy alone is NOT recommended for stroke prevention in this risk category.
    *   DOACs (e.g., Dabigatran, Rivaroxaban, Apixaban) are generally recommended as **first-line therapy** over Vitamin K Antagonists (Warfarin) for non-valvular AF, due to a lower risk of intracranial hemorrhage and better convenience, assuming no contraindications (e.g., severe renal impairment).

---

## 7. Infective Endocarditis - Dental Prophylaxis
**Target CPG:** Prevention, Diagnosis and Management of Infective Endocarditis 2017
**Test Focus:** Procedural prophylaxis and specific conditional logic (allergy vs no allergy).

**User Query:**
> "A 35-year-old patient with a prosthetic mechanical heart valve is scheduled for a routine dental extraction. Does this patient require infective endocarditis antibiotic prophylaxis? If yes, what is the recommended standard antibiotic regimen for a patient with no known penicillin allergy?"

**Expected Ground Truth:**
*   **Summary:** Highest-risk cardiac condition undergoing a high-risk dental procedure (manipulation of gingival tissue/periapical region).
*   **Monitoring & Next Steps:** Yes, antibiotic prophylaxis is strictly recommended.
*   **Medication Changes:**
    *   START: Amoxicillin **2 grams** orally, administered 30 to 60 minutes before the dental procedure.
