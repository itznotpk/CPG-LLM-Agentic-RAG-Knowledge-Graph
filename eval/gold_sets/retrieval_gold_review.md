# Retrieval gold review worksheet (20260602_150310)

Total rows: 148 | flagged for review: 22 | chunk-level flags: 30

## How to review (3 steps per row)

1. **Read the question (Q).** Then read each chunk's preview underneath.
2. **For each chunk, ask: does this text actually answer the question?**
   - YES -> keep it. If it's THE best answer, make sure it is marked `[primary]`.
   - NO  -> delete that chunk id from `relevant_chunk_ids` in `retrieval_gold.jsonl`.
3. When the row's chunks are correct, change that row's `review_status` to `verified`.

`primary` = the chunk that directly answers. `supporting` = related/extra context. The ⚠️ tag is just a hint to look closer, not proof it is wrong.

---

## ret_010 — NSTE-ACS  (score=13.9)
**Q:** What are the very high risk features in NSTE-ACS requiring immediate angiography?

- `c1825bef` **[primary]** (sec 7)
  > ### 7.3.3: Anti-Ischemic Drug Therapy These agents may be given either for relief of ischemia (symptoms) or for improvement of prognosis. ##
- `9ca2718a` **[supporting]** (sec 6)
  > ## 6.2: Primary Care Clinics Chest pain is one of the more common presentations in primary care facilities. In less urban areas, it may be t
- `af970e9e` **[supporting]** (sec 7)  ⚠️ no_keyword_overlap
  > ## 7.4: Revascularization Strategies There is a strong rationale for early revascularization in patients with NSTE-ACS who are at intermedia

## ret_014 — NSTEMI  (score=5.55)
**Q:** When is urgent revascularization indicated in NSTEMI?

- `d65bc250` **[primary]** (sec 8)  ⚠️ no_keyword_overlap
  > ## 8.1: Routine Early Invasive Management [Grade I, Level B] Urgent (as soon as possible after hospital presentation) coronary angiography/r
- `eb318514` **[supporting]** (sec 8)  ⚠️ no_keyword_overlap
  > ## 8.2: Routine Early Conservative Management (Selective Invasive Therapy) [Grade I, Level A] The use of aggressive anticoagulant and antipl
- `7cde5fc4` **[supporting]** (sec 0)  ⚠️ no_keyword_overlap
  > ## Flowchart 1: Risk Stratification Of UA/NSTEMI **[ PATHWAY A: LOW RISK ]** 1. Clinical Profile Assessment: * no angina in the past * no on

## ret_027 — Dyslipidaemia  (score=11.567)
**Q:** Which statins are classified as high-intensity and reduce LDL by more than 50%?

- `5098d958` **[primary]** (sec 10)
  > ## 10.7: HIV * With the advent of good and improved access to effective therapy for HIV, life expectancy has increased, and CVD has become a
- `e42dbfad` **[supporting]** (sec 7)
  > ### 7.7.4: Optimizing Statin Therapy * The therapeutic doses of statins used in clinical practice should be similar between Asian and Caucas
- `2da07506` **[supporting]** (sec 9)
  > ## 9.1: Timing Of Initiation **[Grade I, Level A] Acute Coronary Syndrome (ACS)** * **Rapid Initiation**: High-dose statin therapy should be

## ret_030 — Atrial Fibrillation  (score=?)
**Q:** How is CHA2DS2-VASc score calculated and what score triggers anticoagulation in AF?

- `4a357abd` **[primary]** (sec 6)
  > # Section 6: Management: Prevention Of Thromboembolism ## 6.1: Risk Stratification For Stroke Assessment of thromboembolic risk (risk strati
- `c28f691c` **[supporting]** (sec 6)
  > ## 6.2: Strategies For Thromboembolic Prophylaxis The CHADS₂ stroke risk stratification scheme should be used as a simple initial (and easil
- `a2fb566d` **[supporting]** (sec 4)  ⚠️ no_keyword_overlap
  > ## 4.2: Thromboembolic Prophylaxis Antithrombotic therapy must be considered in all patients with AF. Strategies that may reduce thromboembo

## ret_031 — Atrial Fibrillation  (score=?)
**Q:** Which anticoagulants are preferred in non-valvular atrial fibrillation?

- `b57540a7` **[primary]** (sec 6)
  > ### 6.3.3: Anticoagulation With Direct Thrombin Inhibitors Dabigatran etexilate is an oral prodrug that is rapidly converted by a serum este
- `29da79c0` **[supporting]** (sec 6)
  > ### 6.3.4: Investigational Agents Several new anticoagulant drugs-broadly in two classes, another oral direct thrombin inhibitors (e.g. AZD0
- `c28f691c` **[supporting]** (sec 6)  ⚠️ no_keyword_overlap
  > ## 6.2: Strategies For Thromboembolic Prophylaxis The CHADS₂ stroke risk stratification scheme should be used as a simple initial (and easil

## ret_032 — Atrial Fibrillation  (score=?)
**Q:** Which AF patients must use warfarin rather than a NOAC?

- `c002a270` **[primary]** (sec 9)  ⚠️ no_keyword_overlap
  > ## 9.10: Valvular Heart Disease AF frequently accompanies valvular heart disease. LA distension is an early manifestation of progressive mit
- `459eb0c5` **[supporting]** (sec 6)
  > ### 6.3.1: Anticoagulation With Vitamin K Antagonists (Vka) There were 6 large randomized trials, both primary and secondary prevention, tha
- `b57540a7` **[supporting]** (sec 6)
  > ### 6.3.3: Anticoagulation With Direct Thrombin Inhibitors Dabigatran etexilate is an oral prodrug that is rapidly converted by a serum este

## ret_039 — Percutaneous Coronary Intervention  (score=11.8)
**Q:** What is the preferred arterial access route for PCI?

- `90e568f7` **[primary]** (sec 2)
  > ### 2.1.4: Technical Considerations During Primary PCI For a favourable outcome, it is important to obtain good TIMI 3 epicardial flow and o
- `be945c7a` **[supporting]** (sec 7)  ⚠️ no_keyword_overlap
  > ## 7.1: Vascular Access Complications ### 7.1.1: Retro-Peritoneal Hematoma This is more common after a 'high' groin puncture. It may not be 
- `024ca2cc` **[supporting]** (sec 4)
  > ## 4.4: Elderly The elderly tend to have a higher rate of complications following both PCI and CABG. This includes death, MI, strokes, renal

## ret_040 — Percutaneous Coronary Intervention  (score=25.9)
**Q:** When should CABG be preferred over PCI in multivessel CAD?

- `c6ab1301` **[primary]** (sec 2)
  > ## 2.3: Stable Coronary Artery Disease (Cad) Stable CAD refers to stable angina, asymptomatic myocardial ischaemia and coronary atherosclero
- `f46642a5` **[supporting]** (sec 6)
  > ## 6.2: Multi-Vessel Disease An important factor determining treatment strategies in a patient with multi-vessel disease is the clinical sta
- `7d109c00` **[supporting]** (sec 1)  ⚠️ boilerplate_weak
  > # Section 1: Introduction > **Context:** 2009 Malaysian CPG on PCI. CVD caused 24.2% of Malaysian hospital deaths (2006); CAD and cerebrovas

## ret_065 — Cancer Pain  (score=?)
**Q:** How should breakthrough cancer pain be dosed?

- `3dab2948` **[primary]** (sec 4)
  > ### 4.4.4: Breakthrough Pain Management - Breakthrough pain in cancer refers to an exacerbation of pain in the setting of chronic pain manag
- `152dfa30` **[supporting]** (sec 4)
  > ### 4.4.3: Opioid Initiation, Titration And Maintenance - **Initiation** Strong opioids should be initiated at the lowest effective dose. Fo
- `e48a1e6a` **[supporting]** (sec ?)  ⚠️ no_keyword_overlap
  > ## Algorithm 2: Titration Of Morphine For Rapid Pain Relief In Adults With Severe Pain And Distress **Step 1: Initial Presentation** **Adult

## ret_067 — Cancer Pain  (score=?)
**Q:** How should constipation from opioids be prevented and treated?

- `b5a6f792` **[primary]** (sec 4)
  > ### 4.4.8: Opioid Side Effects Opioids are generally well-tolerated and safe in cancer pain management. [Level I] In a large systematic revi
- `6af3d586` **[supporting]** (sec ?)
  > ### Appendix 5A: Suggested Medication Dosages And Adverse Effects In Adults | Drug | Recommended Dosages | Side Effects | Remarks | |---|---
- `58dc7be3` **[supporting]** (sec ?)  ⚠️ no_keyword_overlap
  > ## Algorithm 1: Management Of Cancer Pain In Adults **Step 1: Initial Assessment** **Cancer patient presents with pain** ↓ **Assessment** * 

## ret_072 — Patient Safety Minimal Monitoring  (score=?)
**Q:** What are the minimum monitoring standards required during anaesthesia?

- `eb606127` **[primary]** (sec 3)  ⚠️ no_keyword_overlap
  > ## 3.1: General Monitoring Principles a. The anaesthesiologist should ensure proper functioning of anaesthetic equipment, monitor the depth 
- `fb0bceca` **[supporting]** (sec 3)
  > ## 3.2: Oxygenation a. Oxygenation may be monitored by noting the colour of the patient's mucous membranes and the colour of the operative s
- `75376fad` **[supporting]** (sec 3)
  > ## 3.3: Circulation a. The circulation must be monitored by observation of the pulse, heart rate, and blood pressure. b. The blood pressure 

## ret_073 — Patient Safety Minimal Monitoring  (score=?)
**Q:** When is temperature monitoring required during anaesthesia?

- `5faa2c3d` **[primary]** (sec 3)
  > ## 3.5: Temperature a. The means to measure body temperature should be readily available. b. Body temperature must be monitored in situation
- `eb606127` **[supporting]** (sec 3)  ⚠️ no_keyword_overlap
  > ## 3.1: General Monitoring Principles a. The anaesthesiologist should ensure proper functioning of anaesthetic equipment, monitor the depth 
- `717ad6db` **[supporting]** (sec 5)  ⚠️ no_keyword_overlap
  > ## 5.2: Standards Of Care And Monitoring Patients are entitled to receive the equivalent standard of care of monitoring during anaesthesia a

## ret_074 — Patient Safety Minimal Monitoring  (score=?)
**Q:** What monitoring is required in the post-anaesthesia care unit (PACU)?

- `8abf42d7` **[primary]** (sec 4)  ⚠️ no_keyword_overlap
  > ## 4.3: Monitoring In Recovery All patients in the recovery area / bay must be appropriately monitored according to the patient's condition.
- `90adec0f` **[supporting]** (sec 4)  ⚠️ no_keyword_overlap
  > ## 4.2: Minimum Facilities For Recovery Area | Facility Type | Description | |---------------|-------------| | Beds / Trolleys | Suitable be
- `fe7f208d` **[supporting]** (sec 4)  ⚠️ no_keyword_overlap
  > ## 4.4: Handover And Discharge a. Proper Handover: There should be a proper handover for the transfer of the patient's care: - From operatin

## ret_075 — Pre-Anaesthetic Assessment  (score=?)
**Q:** What does ASA physical status classification describe?

- `7634c215` **[primary]** (sec 4)
  > # Section 4: Risk Assessment, Stratification And Disclosure > **Context:** This section covers risk assessment, stratification, and disclosu
- `d95ac0af` **[supporting]** (sec 3)  ⚠️ no_keyword_overlap
  > ## 3.2: Physical Examination 3.2.1 Examination of the patient is an essential part of the pre-anaesthetic assessment. 3.2.2 Although the car
- `959c2791` **[supporting]** (sec ?)  ⚠️ no_keyword_overlap
  > # Appendix: Recommended Pre-Anaesthetic Investigations > **Context:** This appendix contains the recommended pre-anaesthetic investigations 

## ret_077 — Pre-Anaesthetic Assessment  (score=?)
**Q:** How is cardiac risk assessed before non-cardiac surgery?

- `7634c215` **[primary]** (sec 4)  ⚠️ no_keyword_overlap,boilerplate_weak
  > # Section 4: Risk Assessment, Stratification And Disclosure > **Context:** This section covers risk assessment, stratification, and disclosu
- `959c2791` **[supporting]** (sec ?)  ⚠️ no_keyword_overlap
  > # Appendix: Recommended Pre-Anaesthetic Investigations > **Context:** This appendix contains the recommended pre-anaesthetic investigations 
- `d95ac0af` **[supporting]** (sec 3)  ⚠️ no_keyword_overlap
  > ## 3.2: Physical Examination 3.2.1 Examination of the patient is an essential part of the pre-anaesthetic assessment. 3.2.2 Although the car

## ret_078 — Pre-Anaesthetic Assessment  (score=?)
**Q:** Which medications should be continued on the morning of surgery?

- `96bb3ca9` **[primary]** (sec 6)  ⚠️ no_keyword_overlap
  > # Section 6: Pre-Operative Medication > **Context:** This section covers pre-operative medication management, including review of current me
- `e3d94e8a` **[supporting]** (sec 8)  ⚠️ no_keyword_overlap
  > ## 8.4: Premedication 8.4.1 Purpose of premedication is to relieve patient's anxiety and provide tranquility before the operation. 8.4.2 Pre
- `b5808984` **[supporting]** (sec 8)
  > ## 8.3: Pre-Operative Fasting 8.3.1 It has been shown that drinking clear fluid up to 2 hours before surgery does not increase residual gast

## ret_079 — Anaesthesia Medication Safety  (score=?)
**Q:** What are high-alert medications in the anaesthesia setting?

- `c992f582` **[primary]** (sec 2)
  > ## 2.10: Administration of Highly Concentrated Drugs, Electrolytes, Glucose, and Insulin 1) Potent drugs like vasopressors (e.g., epinephrin
- `8909e0b9` **[supporting]** (sec 2)
  > ## 2.6: Anaesthesia Medication Storage 1) Storage of anaesthesia medications must adhere to regulations specific to institutional practice. 
- `ad251779` **[supporting]** (sec 1)  ⚠️ boilerplate_weak
  > # Section 1: Introduction ## 1.1: Background Safe and effective use of medications is of paramount importance in anaesthesiology and critica

## ret_080 — Anaesthesia Medication Safety  (score=?)
**Q:** How should neuromuscular blockade be monitored and reversed?

- `37df16cc` **[primary]** (sec 3)  ⚠️ too_short_weak
  > ### 3.1.5: Use of Neuromuscular Blocking Agent a. A neuromuscular monitoring should be available whenever a neuromuscular blocking agent (NM
- `834cede3` **[supporting]** (sec 4)
  > ## 4.4: Extreme Body Weight Patients ### 4.4.1: General Principles a. Extreme body weight, either obese or underweight, is associated with p
- `b29dc24f` **[supporting]** (sec 3)  ⚠️ no_keyword_overlap
  > # Section 3: Safe Use of Medication in Specific Areas ## 3.1: General Anaesthesia ### 3.1.1: Handling of Inhalational Agents/ Volatile Agent

## ret_081 — Anaesthesia Medication Safety  (score=?)
**Q:** What are the guidelines for safe labelling of drug syringes in the operating theatre?

- `195b0526` **[primary]** (sec 2)
  > ## 2.8: Medication Labelling 1) Label syringes according to the national standard; Guideline on Syringe Labelling in Critical Care Areas. 2)
- `12b5bfcf` **[supporting]** (sec 2)
  > ## 2.7: Medication Preparation and Verification 1) Prescriptions must specify the generic drug name, dose, route, frequency, and any special
- `95c35397` **[supporting]** (sec 2)  ⚠️ no_keyword_overlap
  > ## 2.11: Intravenous Medication Delivery 1) Standardise the use of intravenous infusion pumps and syringe drivers within each facility to im

## ret_082 — Anaesthesia Medication Safety  (score=?)
**Q:** How should anaphylaxis during anaesthesia be managed?

- `cea71eb0` **[primary]** (sec 5)
  > # Section 5: Safe Medication Practice ## 5.1: Perioperative Hypersensitivity and Anaphylaxis ### 5.1.1: Introduction a. Perioperative hypers
- `174c2427` **[supporting]** (sec 5)
  > ### 5.1.2: Management of Perioperative Hypersensitivity Reactions a. Management of suspected perioperative allergic (POA) reactions involves
- `5f8a77a3` **[supporting]** (sec 5)  ⚠️ no_keyword_overlap
  > ### 5.1.5: Managing Suspected Perioperative Hypersensitivity Reaction Cases a. A history of a previously uninvestigated perioperative immedi

## ret_086 — Erectile Dysfunction  (score=24.25)
**Q:** What cardiovascular risk evaluation is needed before PDE5 inhibitor therapy?

- `ec5f6e09` **[primary]** (sec ?)
  > ## Algorithm 2: Classification For ED Patients With Cardiovascular Disease Overview: This algorithm classifies patients with confirmed ED an
- `6a9e5287` **[supporting]** (sec 3)
  > ## 3.2: Cardiovascular Risk Assessment ED could be the initial manifestation of a spectrum of clinical conditions that eventually lead to co
- `4743ca03` **[supporting]** (sec ?)  ⚠️ boilerplate_weak
  > ## List Of Abbreviations | Abbreviation | Meaning | |--------------|---------| | AE | adverse event | | AGREE | Appraisal of Guidelines for 

## ret_103 — Colorectal Carcinoma  (score=11.1)
**Q:** What is the neoadjuvant treatment for locally advanced rectal cancer?

- `50bdec0a` **[primary]** (sec 5)
  > ## 5.2: Techniques In Colorectal Surgery Surgery in CRC involves en-bloc removal of the cancer with clear margins and its associated regiona
- `4dfd6403` **[supporting]** (sec 6)
  > ## 6.2: Rectal Carcinoma Adjuvant treatment for low risk rectal cancer (T1-T2 N0) is not indicated unless surgical margin is compromised. Lo
- `ddf3dce8` **[supporting]** (sec ?)
  > ## Appendix 5: Histopathology Proforma For Colorectal Carcinoma **PERKHIDMATAN PATOLOGI** **HOSPITAL** ________________________________ **CO

