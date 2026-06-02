# LLM-judge change list (20260602_151527, model=mimo-v2.5-pro)

rows=148 | dropped chunks=134 | regrades=61 | all-rejected rows=4 | errors=37

Rows below were changed. `all_rejected` = judge rejected every labeled chunk (row kept intact but needs NEW candidates). Spot-check these.

---

## ret_001 — STEMI  [llm_verified]
**Q:** What is the time target for primary PCI door-to-balloon in STEMI?

- ❌ drop `4270486d` — Discusses fibrinolytic therapy, not primary PCI door-to-balloon time.

## ret_002 — STEMI  [llm_verified]
**Q:** When should fibrinolysis be given instead of primary PCI in STEMI?

- ❌ drop `1a862aa2` — Overview of reperfusion strategies, not specific to fibrinolysis vs PCI.
- ❌ drop `9a7b42f4` — Describes primary PCI indications, not when to use fibrinolysis instead.
- 🔁 `4270486d` supporting→primary — Directly states fibrinolysis may be preferable in the golden hour.

## ret_003 — STEMI  [llm_verified]
**Q:** What dual antiplatelet loading doses are recommended for STEMI?

- ❌ drop `8e723094` — Discusses older STEMI patients, not loading doses.
- 🔁 `35887c88` primary→supporting — Mentions aspirin and clopidogrel loading but incomplete for dual therapy.
- 🔁 `781bda12` supporting→primary — Directly lists dual antiplatelet loading doses for STEMI.

## ret_004 — STEMI  [llm_verified]
**Q:** What anticoagulation is used during primary PCI for STEMI?

- ❌ drop `a90c8b3a` — Discusses reinfarction, not anticoagulation during primary PCI.

## ret_005 — STEMI  [llm_verified]
**Q:** What secondary prevention medications are recommended after STEMI discharge?

- ❌ drop `35887c88` — Focuses on initial acute management, not discharge prevention.

## ret_006 — NSTE-ACS  [llm_verified]
**Q:** How is GRACE score used to risk-stratify NSTE-ACS patients?

- ❌ drop `78e1aca7` — Discusses bleeding risk scores, not GRACE score for risk stratification.

## ret_007 — NSTE-ACS  [llm_verified]
**Q:** What antiplatelet therapy is recommended in NSTE-ACS?

- ❌ drop `c1825bef` — Discusses anti-ischemic drugs, not antiplatelet therapy.

## ret_008 — NSTE-ACS  [llm_verified]
**Q:** When should coronary angiography be performed in high-risk NSTE-ACS?

- ❌ drop `67925aae` — Discusses antiplatelet therapy, not angiography timing.
- ❌ drop `86b5f53a` — Covers level of care, not angiography timing.

## ret_009 — NSTE-ACS  [llm_verified]
**Q:** What anticoagulation options are used in NSTE-ACS?

- ❌ drop `0de7c444` — Discusses older persons with NSTE-ACS, not anticoagulation options.
- ❌ drop `f2201e74` — Focuses on CKD diagnosis in ACS, not anticoagulation options.

## ret_010 — NSTE-ACS  [llm_verified]
**Q:** What are the very high risk features in NSTE-ACS requiring immediate angiography?

- ❌ drop `c1825bef` — Discusses anti-ischemic therapy, not high-risk features for angiography.
- ❌ drop `9ca2718a` — Covers primary care assessment, not specific high-risk features.
- 🔁 `af970e9e` supporting→primary — Directly addresses very high risk features and immediate angiography indication.

## ret_011 — NSTEMI  [llm_verified]
**Q:** What is the TIMI risk score and how is it used in UA/NSTEMI?

- ❌ drop `10bf06c9` — General triage context, not specific to TIMI score.
- 🔁 `d5d68a9b` supporting→primary — Directly defines TIMI score and its components.

## ret_012 — NSTEMI  [llm_verified]
**Q:** What defines NSTEMI versus unstable angina?

- ❌ drop `7f16c9de` — Classifies unstable angina, not directly comparing to NSTEMI.
- 🔁 `41e119b3` primary→supporting — Discusses troponin's role in diagnosing myocardial infarction, relevant to NSTEMI.
- 🔁 `70694073` supporting→primary — Directly defines NSTEMI vs unstable angina based on biomarkers.

## ret_013 — NSTEMI  [llm_verified]
**Q:** What anticoagulation is recommended in UA/NSTEMI according to 2011 CPG?

- ❌ drop `10bf06c9` — Discusses triage and risk assessment, not anticoagulation specifics.
- ❌ drop `7cde5fc4` — Focuses on risk stratification pathways, not anticoagulation therapy.

## ret_014 — NSTEMI  [llm_verified]
**Q:** When is urgent revascularization indicated in NSTEMI?

- ❌ drop `eb318514` — Discusses conservative management, not urgent revascularization indications.
- ❌ drop `7cde5fc4` — Focuses on risk stratification pathways, not specific revascularization timing.

## ret_015 — Heart Failure  [llm_verified]
**Q:** What are the four foundational medications for HFrEF?

- ❌ drop `5686d703` — Focuses on renal dysfunction management, not HFrEF foundational meds.
- 🔁 `d76390b0` supporting→primary — Directly lists the four foundational medications for HFrEF.

## ret_016 — Heart Failure  [llm_verified]
**Q:** What is the LVEF threshold that defines HFrEF versus HFpEF?

- 🔁 `3e37689a` primary→supporting — Discusses HFmrEF range, not direct HFrEF vs HFpEF threshold.
- 🔁 `4874e108` supporting→primary — Directly defines HFrEF (≤40%) and HFpEF (>50%) thresholds.

## ret_017 — Heart Failure  [llm_verified]
**Q:** What diuretic is used in acute decompensated heart failure with congestion?

- ❌ drop `ea5df015` — Focuses on oral conversion and discharge, not initial acute treatment.

## ret_018 — Heart Failure  [llm_all_rejected]
**Q:** When is ICD indicated for primary prevention of sudden cardiac death in heart failure?


## ret_019 — Heart Failure  [llm_all_rejected]
**Q:** How is BNP or NT-proBNP used to diagnose heart failure?


## ret_020 — Hypertension  [llm_verified]
**Q:** What is the first-line antihypertensive in T2DM with proteinuria?

- ❌ drop `2c7689d3` — Discusses CCBs, not first-line for T2DM with proteinuria.

## ret_021 — Hypertension  [llm_verified]
**Q:** What is the blood pressure target in hypertension?

- ❌ drop `f25b7024` — Discusses drug choices, not blood pressure targets.
- 🔁 `765dcf9c` primary→supporting — Provides treatment threshold for hypertension in diabetes.
- 🔁 `01228a38` supporting→primary — Directly states blood pressure targets for hypertension.

## ret_022 — Hypertension  [llm_verified]
**Q:** Which drug combination is avoided in hypertension?

- ❌ drop `495b6e52` — Discusses hypertension and CKD, not drug combinations to avoid.
- ❌ drop `d5eb8334` — Focuses on RAS blockers, not specific avoided combinations.
- 🔁 `f25b7024` supporting→primary — Directly addresses first-line drug choices and beta-blocker caution.

## ret_023 — Hypertension  [llm_verified]
**Q:** What defines resistant hypertension?

- 🔁 `01228a38` primary→supporting — Provides context on BP targets and initial steps before defining resistant hypertension.
- 🔁 `862ee786` supporting→primary — Directly defines resistant hypertension with specific criteria.

## ret_024 — Hypertension  [llm_verified]
**Q:** How should hypertensive emergency be managed?

- ❌ drop `964c618d` — Discusses hypertensive urgency, not emergency, with different management.
- ❌ drop `525c30f7` — Focuses on dangers of rapid BP reduction in urgencies, not emergency management.

## ret_025 — Dyslipidaemia  [llm_verified]
**Q:** What is the LDL-C target for very high cardiovascular risk?

- 🔁 `d133b78d` primary→supporting — References target dependent on CV risk, but no specific value for very high risk.
- 🔁 `2da07506` supporting→primary — Directly states LDL-C target <1.4 mmol/L for established CVD (very high risk).

## ret_026 — Dyslipidaemia  [llm_verified]
**Q:** What is the LDL-C target for high cardiovascular risk patients?

- ❌ drop `74498dc4` — Discusses CKD risk, not specific LDL-C target.
- 🔁 `d133b78d` primary→supporting — References target dependent on CV risk, but no specific value.
- 🔁 `2da07506` supporting→primary — Directly states LDL-C target <1.4 mmol/L for high-risk.

## ret_027 — Dyslipidaemia  [llm_verified]
**Q:** Which statins are classified as high-intensity and reduce LDL by more than 50%?

- ❌ drop `5098d958` — Discusses statins in HIV, not high-intensity classification.
- ❌ drop `2da07506` — Focuses on timing and targets, not statin intensity classification.
- 🔁 `e42dbfad` supporting→primary — Directly states high-intensity statins reduce LDL-C >50%.

## ret_028 — Dyslipidaemia  [llm_verified]
**Q:** When should ezetimibe be added to statin therapy?

- ❌ drop `00e4eee3` — Discusses diabetes and statins, not specific ezetimibe addition timing.

## ret_029 — Dyslipidaemia  [llm_verified]
**Q:** What are PCSK9 inhibitors used for and who qualifies?

- ❌ drop `5098d958` — Discusses HIV and dyslipidemia, not PCSK9 inhibitors.
- ❌ drop `4f74f4e5` — Covers statin safety, not PCSK9 inhibitors.

## ret_030 — Atrial Fibrillation  [llm_verified]
**Q:** How is CHA2DS2-VASc score calculated and what score triggers anticoagulation in AF?

- ❌ drop `a2fb566d` — General antithrombotic therapy, not specific to CHA2DS2-VASc.
- 🔁 `4a357abd` primary→supporting — Discusses stroke risk factors relevant to score calculation.
- 🔁 `c28f691c` supporting→primary — Directly references CHA2DS2-VASc score and anticoagulation thresholds.

## ret_032 — Atrial Fibrillation  [llm_verified]
**Q:** Which AF patients must use warfarin rather than a NOAC?

- ❌ drop `b57540a7` — Focuses on dabigatran (a NOAC) efficacy, not warfarin indications.

## ret_034 — Atrial Fibrillation  [llm_verified]
**Q:** What anticoagulation is needed before electrical cardioversion in AF?

- ❌ drop `068c280a` — Discusses pharmacological cardioversion, not anticoagulation requirements.

## ret_035 — Stable Coronary Artery Disease  [llm_verified]
**Q:** What is the first-line anti-anginal therapy in stable coronary artery disease?

- ❌ drop `40a091e5` — Describes stable CAD spectrum, not anti-anginal therapy.
- ❌ drop `cda7bff4` — Discusses natural history and prognosis, not treatment.
- 🔁 `2840d032` supporting→primary — Directly describes an anti-anginal agent, trimetazidine.

## ret_036 — Stable Coronary Artery Disease  [llm_verified]
**Q:** What are the secondary prevention medications in stable coronary artery disease?

- ❌ drop `40a091e5` — Defines stable CAD but does not list secondary prevention medications.
- 🔁 `7d18f7f5` supporting→primary — Directly lists secondary prevention medications for stable CAD.

## ret_037 — Stable Coronary Artery Disease  [llm_verified]
**Q:** When is revascularization indicated in stable CAD?

- ❌ drop `40a091e5` — Defines stable CAD spectrum, not revascularization indications.
- ❌ drop `4413da99` — Introduces CAD and stable CAD populations, not indications.
- 🔁 `668be23e` supporting→primary — Directly lists indications for revascularization in stable CAD.

## ret_038 — Percutaneous Coronary Intervention  [llm_verified]
**Q:** What is the recommended DAPT duration after a drug-eluting stent?

- ❌ drop `b9af44d4` — Describes stent types, not DAPT duration.
- 🔁 `f02f0faa` supporting→primary — Directly addresses antiplatelet therapy duration after PCI.

## ret_039 — Percutaneous Coronary Intervention  [llm_verified]
**Q:** What is the preferred arterial access route for PCI?

- ❌ drop `be945c7a` — Discusses vascular access complications, not preferred route.
- ❌ drop `024ca2cc` — Focuses on elderly PCI considerations, not arterial access.

## ret_040 — Percutaneous Coronary Intervention  [llm_verified]
**Q:** When should CABG be preferred over PCI in multivessel CAD?

- ❌ drop `c6ab1301` — General stable CAD definition, not specific to CABG vs PCI in multivessel.
- ❌ drop `7d109c00` — Introduction context, no specific guidance on CABG vs PCI choice.
- 🔁 `f46642a5` supporting→primary — Directly lists factors favoring CABG over PCI in multivessel disease.

## ret_041 — Pulmonary Arterial Hypertension  [llm_verified]
**Q:** What defines pulmonary arterial hypertension at right heart catheterization?

- ❌ drop `2272e4bb` — Discusses PAH evaluation, not the hemodynamic definition.
- ❌ drop `053695e9` — Covers screening, not the hemodynamic definition.
- 🔁 `288e5c14` supporting→primary — Directly defines PAH by resting mPAP >25 mmHg at catheterization.

## ret_042 — Pulmonary Arterial Hypertension  [llm_verified]
**Q:** Which PAH patients should undergo vasoreactivity testing?

- ❌ drop `aa9ececd` — Discusses treatment algorithm, not vasoreactivity testing criteria.
- ❌ drop `2272e4bb` — Describes general PAH evaluation, not specific to vasoreactivity testing.
- 🔁 `ae8323fe` supporting→primary — Directly states vasoreactivity testing should be done in all PAH cases except pulmonary venous obstruction.

## ret_043 — Pulmonary Arterial Hypertension  [llm_verified]
**Q:** What are the first-line targeted therapies for non-vasoreactive PAH?

- ❌ drop `aa9ececd` — Discusses supportive therapy, not targeted first-line therapies.

## ret_045 — Heart Disease in Pregnancy  [llm_verified]
**Q:** Which anticoagulant is preferred during pregnancy?

- ❌ drop `6d911a6f` — Lists drug safety data but does not address anticoagulant preference.
- 🔁 `e90de8ba` primary→supporting — Discusses anticoagulation for mechanical heart valves in pregnancy, not general preference.
- 🔁 `358ee888` supporting→primary — Directly compares warfarin vs LMWH regimens for anticoagulation in pregnancy.

## ret_046 — Infective Endocarditis  [llm_verified]
**Q:** What are the major Duke criteria for infective endocarditis?

- ❌ drop `e148af71` — Focuses on IE in transcatheter valves, not the Duke criteria.
- ❌ drop `0e97ca29` — Discusses complications of IE, not diagnostic criteria.

## ret_047 — Infective Endocarditis  [llm_verified]
**Q:** What empirical antibiotic regimen is used for suspected native valve IE?

- ❌ drop `6e01515e` — Focuses on pediatric renal dosing, not empirical IE regimen.

## ret_049 — Infective Endocarditis  [llm_verified]
**Q:** What antibiotic prophylaxis is recommended for dental procedures in high-risk cardiac patients?

- ❌ drop `e148af71` — Discusses transcatheter valve IE, not dental prophylaxis.
- 🔁 `68f9b1e5` supporting→primary — Directly lists antibiotic regimens for dental procedures.

## ret_050 — Ischaemic Stroke  [llm_verified]
**Q:** What is the time window for IV thrombolysis in acute ischaemic stroke?

- ❌ drop `bd4e59bd` — Discusses endovascular thrombectomy, not IV thrombolysis time window.
- 🔁 `e1350385` supporting→primary — Directly states IV thrombolysis time window: onset within 4.5 hours.

## ret_051 — Ischaemic Stroke  [llm_verified]
**Q:** What blood pressure must be achieved before IV thrombolysis in stroke?

- ❌ drop `6d22d42a` — Discusses general hypertension management, not pre-thrombolysis BP target.
- ❌ drop `f7fb7c9e` — Focuses on secondary prevention, not acute thrombolysis BP criteria.

## ret_052 — Ischaemic Stroke  [llm_verified]
**Q:** What is the time window for mechanical thrombectomy in large vessel occlusion stroke?

- ❌ drop `59e01d03` — Discusses IVT time window and general reperfusion, not specific to LVO thrombectomy window.

## ret_062 — Colorectal Carcinoma  [llm_verified]
**Q:** When is Lynch syndrome testing indicated in colorectal cancer?

- ❌ drop `2a9066ca` — Focuses on histopathology, not genetic testing indications.

## ret_068 — Nasopharyngeal Carcinoma  [llm_verified]
**Q:** What is the primary treatment for nasopharyngeal carcinoma?

- ❌ drop `079951bc` — Discusses follow-up after treatment, not the primary treatment itself.
- ❌ drop `b548cd4f` — Focuses on implementation and audit, not treatment specifics.

## ret_070 — Nasopharyngeal Carcinoma  [llm_verified]
**Q:** What is the role of EBV DNA in NPC?

- ❌ drop `079951bc` — Discusses follow-up radiotherapy, not EBV DNA role.
- ❌ drop `ef4d26ad` — Focuses on prognosis and staging, not EBV DNA.
- 🔁 `684fdcbd` supporting→primary — Directly mentions EBV serology test for NPC screening.

## ret_071 — Nasopharyngeal Carcinoma  [llm_verified]
**Q:** What presenting symptoms should raise suspicion for nasopharyngeal carcinoma?

- ❌ drop `32b9ec5d` — Discusses recurrent cancer, not initial presenting symptoms.

## ret_073 — Patient Safety Minimal Monitoring  [llm_verified]
**Q:** When is temperature monitoring required during anaesthesia?

- ❌ drop `eb606127` — General monitoring principles, not specific to temperature.
- ❌ drop `717ad6db` — Standards of care, not specific to temperature monitoring.

## ret_075 — Pre-Anaesthetic Assessment  [llm_verified]
**Q:** What does ASA physical status classification describe?

- ❌ drop `d95ac0af` — Discusses physical examination, not ASA classification.
- ❌ drop `959c2791` — Covers pre-anaesthetic investigations, not ASA classification.

## ret_078 — Pre-Anaesthetic Assessment  [llm_verified]
**Q:** Which medications should be continued on the morning of surgery?

- ❌ drop `e3d94e8a` — Discusses premedication purpose and selection, not continuation of chronic meds.
- ❌ drop `b5808984` — Covers preoperative fasting, not medication continuation.

## ret_079 — Anaesthesia Medication Safety  [llm_verified]
**Q:** What are high-alert medications in the anaesthesia setting?

- ❌ drop `8909e0b9` — Discusses storage, not identification of high-alert medications.
- ❌ drop `ad251779` — General background on medication safety, not specific high-alert list.

## ret_080 — Anaesthesia Medication Safety  [llm_verified]
**Q:** How should neuromuscular blockade be monitored and reversed?

- ❌ drop `834cede3` — Discusses drug dosing in extreme weight, not NMB monitoring/reversal.
- ❌ drop `b29dc24f` — Covers volatile agent handling, unrelated to neuromuscular blockade.

## ret_081 — Anaesthesia Medication Safety  [llm_verified]
**Q:** What are the guidelines for safe labelling of drug syringes in the operating theatre?

- ❌ drop `95c35397` — Focuses on IV delivery and infusion lines, not syringe labelling.

## ret_082 — Anaesthesia Medication Safety  [llm_verified]
**Q:** How should anaphylaxis during anaesthesia be managed?

- ❌ drop `cea71eb0` — Provides background on anaphylaxis, not management steps.
- ❌ drop `5f8a77a3` — Focuses on post-reaction investigation, not acute management.
- 🔁 `174c2427` supporting→primary — Directly outlines key management steps for anaphylaxis.

## ret_083 — Erectile Dysfunction  [llm_verified]
**Q:** What is the first-line treatment for erectile dysfunction?

- ❌ drop `3fd8e19f` — Only shows search strategy, not treatment recommendations.

## ret_084 — Erectile Dysfunction  [llm_verified]
**Q:** When are PDE5 inhibitors contraindicated in ED?

- ❌ drop `585b62b2` — Lists mechanical and pharmacological treatments but not specific contraindications.

## ret_085 — Erectile Dysfunction  [llm_verified]
**Q:** How is erectile dysfunction severity assessed using the IIEF-5?

- ❌ drop `9fa37c3a` — Discusses ED prevalence in comorbidities, not IIEF-5 severity assessment.
- 🔁 `68b8c329` primary→supporting — Provides the IIEF-5 questionnaire items but not the severity scoring.
- 🔁 `649a7260` supporting→primary — Directly defines IIEF-5 score ranges and clinical severity classifications.

## ret_086 — Erectile Dysfunction  [llm_verified]
**Q:** What cardiovascular risk evaluation is needed before PDE5 inhibitor therapy?

- ❌ drop `4743ca03` — Only lists abbreviations, no clinical guidance on CV risk evaluation.

## ret_087 — Erectile Dysfunction  [llm_verified]
**Q:** What is the second-line treatment for ED when PDE5 inhibitors fail?

- ❌ drop `4743ca03` — Only a list of abbreviations, no treatment information.
- 🔁 `f97faa29` supporting→primary — Directly describes intracavernosal injections as a second-line treatment.

## ret_097 — Nasopharyngeal Carcinoma  [llm_verified]
**Q:** What induction chemotherapy is used for locoregionally advanced NPC?

- ❌ drop `f0d6828f` — Only covers TNM staging, not chemotherapy specifics.

## ret_101 — Heart Failure  [llm_verified]
**Q:** What are the indications for CRT (cardiac resynchronisation therapy) in heart failure?

- ❌ drop `9794b9c8` — Lists drug therapy indications, not CRT.
- ❌ drop `d7e88cba` — Discusses arrhythmia-induced cardiomyopathy, not CRT.
- 🔁 `c4ab7f24` supporting→primary — Directly lists CRT indications and criteria.

## ret_102 — Heart Failure  [llm_verified]
**Q:** What is the ARNI (sacubitril/valsartan) indication in HFrEF?

- ❌ drop `ea5df015` — Discusses diuretic conversion, not ARNI indication.

## ret_103 — Colorectal Carcinoma  [llm_verified]
**Q:** What is the neoadjuvant treatment for locally advanced rectal cancer?

- ❌ drop `50bdec0a` — Discusses colon carcinoma surgery, not rectal neoadjuvant treatment.
- ❌ drop `ddf3dce8` — Histopathology form, not treatment information.
- 🔁 `4dfd6403` supporting→primary — Directly addresses neoadjuvant radiotherapy for rectal carcinoma.

## ret_104 — Cancer Pain  [llm_verified]
**Q:** What opioid rotation is recommended for uncontrolled pain or intolerable side effects?

- ❌ drop `152dfa30` — Discusses opioid initiation and titration, not rotation for uncontrolled pain or side effects.

## ret_105 — NSTE-ACS  [llm_verified]
**Q:** What is the DAPT duration in NSTE-ACS managed with PCI?

- ❌ drop `67925aae` — Focuses on aspirin loading/maintenance, not DAPT duration.
- ❌ drop `c1825bef` — Discusses anti-ischemic therapy, not DAPT duration.
- 🔁 `5d0f1035` supporting→primary — Directly states DAPT duration for at least 1 year.

## ret_106 — Ischaemic Stroke  [llm_verified]
**Q:** What are the absolute contraindications to IV thrombolysis in stroke?

- ❌ drop `0f4f0382` — Discusses cardioembolism, not contraindications to thrombolysis.
- ❌ drop `8590c0c8` — Covers eligibility and requirements, not contraindications.

## ret_107 — Nasopharyngeal Carcinoma  [llm_verified]
**Q:** What is the staging system used for NPC and what are the treatment implications?

- 🔁 `cd7a7a89` primary→supporting — Discusses treatment modalities but not staging system.
- 🔁 `1d056230` supporting→primary — Directly addresses radiological staging for NPC.

## ret_108 — Heart Failure  [llm_verified]
**Q:** What monitoring parameters guide titration of foundational HF medications?

- ❌ drop `5686d703` — Focuses on renal dysfunction management, not specific HF medication titration.
- 🔁 `84623d8c` supporting→primary — Directly lists monitoring parameters (BP, HR, renal function, K+) for titration.

## ret_109 — Dyslipidaemia  [llm_verified]
**Q:** What non-HDL-C target applies when TG >4.5 mmol/L?

- ❌ drop `00e4eee3` — Discusses diabetes dyslipidemia, not non-HDL-C target for high TG.
- 🔁 `3eac1a90` supporting→primary — Directly states non-HDL-C is primary target when TG>4.5 mmol/L.

## ret_110 — NSTE-ACS  [llm_all_rejected]
**Q:** What is the target HbA1c for DAPT de-escalation after ACS?


## ret_111 — Ischaemic Stroke  [llm_verified]
**Q:** What are the discharge criteria after IVT in acute ischaemic stroke?

- ❌ drop `15f60ec3` — Discusses long-term risk factor management, not discharge criteria post-IVT.
- ❌ drop `f7fb7c9e` — Focuses on long-term secondary prevention, not acute discharge criteria.
- 🔁 `e1350385` supporting→primary — Directly outlines post-IVT monitoring and care, implying discharge readiness.

## ret_112 — Stable Coronary Artery Disease  [llm_verified]
**Q:** What second-line anti-anginal medications are used if beta-blockers are insufficient?

- ❌ drop `40a091e5` — Describes stable CAD spectrum, not specific second-line medications.

## ret_113 — Atrial Fibrillation  [llm_verified]
**Q:** How should a patient on warfarin for AF be bridged perioperatively?

- ❌ drop `48eda19f` — Addresses elevated INR/bleeding, not perioperative bridging.
- 🔁 `74f4a084` primary→supporting — Provides context on interruption but lacks specific bridging details.
- 🔁 `e8d5508f` supporting→primary — Directly answers bridging based on thromboembolism risk.

## ret_114 — Hypertension  [llm_verified]
**Q:** What special considerations apply to patients with chronic kidney disease and hypertension?

- ❌ drop `d5eb8334` — Focuses on RAS blockers generally, not specific to CKD considerations.
- ❌ drop `765dcf9c` — Discusses hypertension in diabetes, not specifically CKD.

## ret_115 — Erectile Dysfunction  [llm_verified]
**Q:** What is the risk stratification used before prescribing PDE5 inhibitors in ED?

- ❌ drop `4743ca03` — Only lists abbreviations, not risk stratification details.

## ret_116 — Breast Cancer  [llm_verified]
**Q:** What systemic therapy is recommended for HER2-positive metastatic breast cancer?

- ❌ drop `0200add3` — Discusses adjuvant therapy, not metastatic HER2-positive treatment.
- ❌ drop `16102754` — Focuses on neoadjuvant therapy, not metastatic HER2-positive treatment.

## ret_117 — STEMI  [llm_verified]
**Q:** What is the fibrinolysis door-to-needle time target in STEMI?

- ❌ drop `a9005e0e` — Discusses epidemiology and importance of time, not DNT target.
- ❌ drop `1a862aa2` — General reperfusion strategy overview, no specific DNT target.

## ret_118 — Percutaneous Coronary Intervention  [llm_verified]
**Q:** What post-PCI follow-up is needed for patients with acute MI?

- ❌ drop `c6ab1301` — Discusses stable CAD management, not post-MI PCI follow-up.
- ❌ drop `3dc2cd3e` — Focuses on cardiogenic shock treatment, not routine follow-up.

## ret_119 — Breast Cancer  [llm_verified]
**Q:** What are adjuvant radiotherapy indications in breast cancer after mastectomy?

- ❌ drop `02aa085b` — Discusses radiotherapy after breast-conserving surgery, not mastectomy.
- ❌ drop `6e5b32d5` — Focuses on margins after breast-conserving surgery, not mastectomy indications.
- 🔁 `cf4dc6cc` supporting→primary — Lists adjuvant radiotherapy as an option after mastectomy.

## ret_131 — T2 Diabetes Mellitus  [llm_verified]
**Q:** What is first-line pharmacological therapy for newly diagnosed type 2 diabetes?

- ❌ drop `087715fc` — Focuses on DKD management, not first-line T2DM therapy.

## ret_133 — Thyroid Disorders  [llm_verified]
**Q:** How is subclinical hypothyroidism diagnosed and when should it be treated?

- ❌ drop `bc1a0bbf` — Focuses on pregnancy, not general diagnosis/treatment.
- 🔁 `a58f4615` primary→supporting — Lists causes, not diagnosis or treatment criteria.
- 🔁 `c81a20a6` supporting→primary — Directly answers diagnosis and treatment criteria by age/TSH.

## ret_134 — Thyroid Disorders  [llm_verified]
**Q:** What is the first-line treatment for Graves disease or hyperthyroidism?

- ❌ drop `8abc46ea` — Focuses on subclinical hyperthyroidism, not Graves' disease first-line.

## ret_135 — Thyroid Disorders  [llm_verified]
**Q:** How should thyroid dysfunction be managed in pregnancy?

- ❌ drop `cf7bbb49` — General hypothyroidism treatment, not pregnancy-specific management.
- 🔁 `a9d1220c` primary→supporting — Details LT4 dose adjustments during pregnancy, supporting management.
- 🔁 `d4d37a58` supporting→primary — Directly answers TSH goals for managing hypothyroidism in pregnancy.

## ret_136 — Thyroid Disorders  [llm_verified]
**Q:** How should a thyroid nodule be evaluated for malignancy?

- ❌ drop `3179a6c0` — Focuses on Hashimoto's thyroiditis diagnosis, not general nodule evaluation.

## ret_137 — Diabetes in Pregnancy  [llm_verified]
**Q:** How is gestational diabetes screened and diagnosed using the OGTT?

- 🔁 `fe1b20a3` primary→supporting — Discusses screening strategies but not OGTT specifics.
- 🔁 `818ebb43` supporting→primary — Directly details OGTT use for screening and diagnosis.

## ret_138 — Diabetes in Pregnancy  [llm_verified]
**Q:** What are the glycaemic targets during pregnancy in diabetes?

- ❌ drop `84724c82` — Focuses on screening and preconception, not glycaemic targets.
- 🔁 `f771aa79` primary→supporting — Discusses monitoring for glycaemic control but not specific targets.
- 🔁 `22fec27b` supporting→primary — Directly states HbA1c targets for pregnancy planning.

## ret_139 — Diabetes in Pregnancy  [llm_all_rejected]
**Q:** When is insulin indicated in gestational diabetes mellitus?


## ret_140 — Diabetes in Pregnancy  [llm_verified]
**Q:** What postpartum follow-up is recommended after gestational diabetes?

- ❌ drop `84724c82` — Focuses on screening and antenatal management, not postpartum follow-up.
- ❌ drop `fe1b20a3` — Discusses screening and diagnosis, not postpartum care.

## ret_141 — Type 1 Diabetes Mellitus  [llm_verified]
**Q:** What insulin regimen is recommended for children and adolescents with type 1 diabetes?

- ❌ drop `fa5cef1a` — Discusses growth/puberty impact, not regimen recommendations.
- ❌ drop `26dcc98c` — Covers surgical management, not insulin regimen selection.

## ret_142 — Type 1 Diabetes Mellitus  [llm_verified]
**Q:** How is diabetic ketoacidosis managed in children with type 1 diabetes?

- ❌ drop `7665ed36` — Discusses sick day management, not acute DKA treatment.

## ret_143 — Type 1 Diabetes Mellitus  [llm_verified]
**Q:** How should hypoglycaemia be treated in children with type 1 diabetes?

- ❌ drop `fa5cef1a` — Discusses growth and puberty, not hypoglycaemia treatment.
- ❌ drop `564a0a84` — Focuses on self-monitoring blood glucose, not acute treatment.

## ret_144 — Type 1 Diabetes Mellitus  [llm_verified]
**Q:** What are the HbA1c targets and glucose monitoring recommendations for paediatric type 1 diabetes?

- ❌ drop `fa5cef1a` — Discusses growth/puberty, not HbA1c targets or glucose monitoring.
- ❌ drop `fcf79e72` — Focuses on Ramadan fasting, not general HbA1c targets or monitoring.
- 🔁 `564a0a84` supporting→primary — Directly addresses SMBG frequency and aims for glycaemic targets.

## ret_145 — Growth Hormone  [llm_verified]
**Q:** What are the criteria for diagnosing growth hormone deficiency in children?

- ❌ drop `47577ae9` — Lists search terms, not diagnostic criteria.
- 🔁 `ce50d746` primary→supporting — Provides clinical criteria for suspecting GHD, not full diagnostic criteria.
- 🔁 `639f02c9` supporting→primary — Directly states biochemical diagnostic criteria for GHD in children.

## ret_146 — Growth Hormone  [llm_verified]
**Q:** What is the recommended dosage for growth hormone therapy in children?

- ❌ drop `a020ff76` — Discusses benefits and indications for adult GH deficiency, not pediatric dosage.
- ❌ drop `12d36ecd` — Focuses on athletic performance in adults, not pediatric growth hormone therapy dosage.

## ret_147 — Growth Hormone  [llm_verified]
**Q:** When should growth hormone therapy be reassessed or transitioned in adolescents?

- ❌ drop `ac109410` — Discusses outcomes in Turner syndrome, not transition reassessment.

## ret_148 — Growth Hormone  [llm_verified]
**Q:** How are adults with growth hormone deficiency screened and diagnosed?

- ❌ drop `47577ae9` — Lists search terms, not diagnostic criteria or methods.
- ❌ drop `b5fbe3bb` — Focuses on transition period, not general adult diagnosis.
- 🔁 `f4b8fd1a` supporting→primary — Directly outlines screening and diagnostic algorithm for adults.



---
# RE-JUDGE pass (20260602_152214) — targeted 41 rows
ok=41 dropped=48 regraded=27 still_all_rejected=4 still_errored=0

## ret_018 - Heart Failure [llm_all_rejected] (re-judge)
**Q:** When is ICD indicated for primary prevention of sudden cardiac death in heart failure?


## ret_019 - Heart Failure [llm_verified] (re-judge)
**Q:** How is BNP or NT-proBNP used to diagnose heart failure?
- drop 3fe695aa - Lists investigations but does not mention BNP/NT-proBNP.
- drop 4484faee - Discusses symptoms and signs, not natriuretic peptide use.
- drop ffd0fdd3 - Focuses on ACHD investigations, not BNP/NT-proBNP use.


## ret_053 - Ischaemic Stroke [llm_verified] (re-judge)
**Q:** What antiplatelet therapy is given after ischaemic stroke?
- drop 0362c8d3 - Focuses on other risk factors like diabetes and smoking, not antiplatelet therapy.
- drop 66b08619 - Discusses angioplasty/stenting, not antiplatelet therapy.


## ret_054 - Ischaemic Stroke [llm_verified] (re-judge)
**Q:** When should anticoagulation be started after AF-related ischaemic stroke?
- drop a75495a9 - Discusses cerebral venous thrombosis, not AF-related ischaemic stroke timing.
- drop 4a6a31c8 - Focuses on DOAC reversal in bleeding, not anticoagulation timing post-stroke.
- regrade 0f4f0382 supporting->primary - Directly addresses AF-related ischaemic stroke and management principles.


## ret_055 - Breast Cancer [llm_verified] (re-judge)
**Q:** What is the recommended mammography screening interval for average-risk women?
- drop 7dd15b2a - Focuses on high-risk women with personal history, not average-risk.
- drop cce0ccd4 - Discusses intensive screening for high-risk individuals, not average-risk.
- regrade 80bda005 supporting->primary - Directly states average-risk women aged 50-74 should be screened every two years.


## ret_056 - Breast Cancer [llm_verified] (re-judge)
**Q:** What is the preferred biopsy technique for breast lesions?
- drop 31682a57 - Discusses imaging, not biopsy technique.
- regrade da760404 supporting->primary - Directly states core needle biopsy is preferred for breast lesions.


## ret_057 - Breast Cancer [llm_verified] (re-judge)
**Q:** Which breast cancer patients should receive trastuzumab?
- drop 16102754 - Discusses neoadjuvant chemotherapy, not trastuzumab eligibility.
- regrade 0200add3 supporting->primary - Directly links HER2 status to adjuvant targeted therapy selection.


## ret_058 - Breast Cancer [llm_verified] (re-judge)
**Q:** When is neoadjuvant chemotherapy indicated in breast cancer?
- regrade 16102754 primary->supporting - Discusses NACT in early breast cancer but not specific indications.
- regrade 939d0544 supporting->primary - Directly shows neoadjuvant chemotherapy indications for locally advanced breast cancer.


## ret_059 - Breast Cancer [llm_verified] (re-judge)
**Q:** When should BRCA carriers have annual MRI screening?
- drop 80bda005 - Discusses average risk screening, not BRCA-specific MRI timing.
- regrade 7dd15b2a supporting->primary - Directly states annual MRI for BRCA carriers aged 30-49.


## ret_060 - Colorectal Carcinoma [llm_verified] (re-judge)
**Q:** What is the recommended colonoscopy screening schedule for colorectal cancer?
- drop 172c8135 - Discusses family history risk, not screening schedule.
- drop 2d35dd37 - Covers post-polypectomy surveillance, not initial screening.
- regrade 48180ca0 supporting->primary - Directly provides screening intervals for average-risk population.


## ret_061 - Colorectal Carcinoma [llm_all_rejected] (re-judge)
**Q:** What adjuvant chemotherapy regimen is used after surgery for stage III colon cancer?


## ret_063 - Colorectal Carcinoma [llm_verified] (re-judge)
**Q:** What is the role of CEA in colorectal cancer monitoring?
- drop 5efb976c - Discusses diagnostic investigations, not CEA monitoring role.
- drop 355dd175 - Focuses on screening modalities, not CEA monitoring.
- regrade dcdc80b1 supporting->primary - Directly states CEA monitoring is part of post-treatment surveillance.


## ret_064 - Cancer Pain [llm_verified] (re-judge)
**Q:** What are the three steps of the WHO analgesic ladder for cancer pain?
- drop 45174b74 - Discusses non-opioids for pain, not the ladder's three steps.


## ret_065 - Cancer Pain [llm_verified] (re-judge)
**Q:** How should breakthrough cancer pain be dosed?
- drop e48a1e6a - Focuses on severe pain titration algorithm, not specifically breakthrough cancer pain dosing.
- regrade 3dab2948 primary->supporting - Defines breakthrough pain and rescue analgesia need, but not dosing specifics.
- regrade 152dfa30 supporting->primary - Directly states breakthrough pain dosing: similar doses up to every hour as needed.


## ret_067 - Cancer Pain [llm_verified] (re-judge)
**Q:** How should constipation from opioids be prevented and treated?
- drop 6af3d586 - Lists general drug dosages and side effects, not specific to opioid constipation.
- drop 58dc7be3 - Describes cancer pain management algorithm, not opioid side effect management.


## ret_088 - Primary Secondary Prevention of CVD [llm_verified] (re-judge)
**Q:** What Framingham Risk Score threshold defines high CVD risk for primary prevention?
- drop b9b22d83 - Discusses screening age, not FRS threshold for high risk.
- drop d35350dd - Focuses on diabetes-specific prevention, not general FRS threshold.
- regrade 8fe69a1c supporting->primary - Directly references FRS and risk stratification table for thresholds.


## ret_089 - Primary Secondary Prevention of CVD [llm_verified] (re-judge)
**Q:** Is aspirin recommended for primary prevention of CVD?
- drop f59341f0 - Discusses anticoagulation for atrial fibrillation, not aspirin for primary prevention.
- drop 6f5983e4 - Focuses on erectile dysfunction and CVD risk, not aspirin therapy.


## ret_090 - CVD Prevention in Women [llm_verified] (re-judge)
**Q:** What unique risk factors increase CVD risk specifically in women?
- drop 54cfbcf6 - Lists general CVD risk categories, not women-specific factors.
- regrade b635360f supporting->primary - Directly details sex-specific risk factor: combined oral contraceptives.


## ret_091 - CVD Prevention in Women [llm_all_rejected] (re-judge)
**Q:** Is hormone replacement therapy recommended for CVD prevention in women?


## ret_092 - Pulmonary Arterial Hypertension [llm_verified] (re-judge)
**Q:** What combination targeted therapy is recommended for high-risk PAH?
- regrade 801010da primary->supporting - Mentions sequential combination therapy but not specific high-risk recommendation.
- regrade e874cd1f supporting->primary - Directly recommends combination therapy for WHO Class IV (high-risk) patients.


## ret_093 - NSTEMI [llm_verified] (re-judge)
**Q:** How is the NSTEMI (2011) early discharge strategy applied?
- drop 10bf06c9 - Focuses on triage and risk categorization, not early discharge strategy.


## ret_094 - Ischaemic Stroke [llm_verified] (re-judge)
**Q:** What dose of alteplase is used for IV thrombolysis in acute ischaemic stroke?
- drop 78a97955 - Focuses on blood pressure control, not alteplase dose.


## ret_095 - Heart Disease in Pregnancy [llm_verified] (re-judge)
**Q:** When should peripartum cardiomyopathy be suspected?
- drop 9784e4bd - Discusses hypertrophic cardiomyopathy, not peripartum cardiomyopathy suspicion.
- drop cc0e32d3 - General pregnancy care planning, not specific to PPCM suspicion.


## ret_096 - Breast Cancer [llm_verified] (re-judge)
**Q:** What systemic therapy is first-line in hormone receptor-positive metastatic breast cancer?
- drop 0200add3 - Discusses adjuvant therapy, not first-line systemic therapy for metastatic disease.
- drop 053a01a3 - Lists clinical questions, not treatment recommendations for metastatic breast cancer.


## ret_098 - Hypertension [llm_all_rejected] (re-judge)
**Q:** What is the HbA1c target for elderly frail patients with T2DM and hypertension?


## ret_099 - Pulmonary Arterial Hypertension [llm_verified] (re-judge)
**Q:** What cardiac monitoring is required after initiation of targeted PAH therapy?
- drop 3c1216aa - Focuses on RCT results, not monitoring requirements.


## ret_100 - Pulmonary Arterial Hypertension [llm_verified] (re-judge)
**Q:** What are the WHO functional classes in PAH and what treatment escalation is recommended?
- drop aa9ececd - Focuses on recommendation grading codes, not WHO classes or escalation.


## ret_110 - NSTE-ACS [llm_verified] (re-judge)
**Q:** How long should dual antiplatelet therapy be continued after ACS and when can it be de-escalated?
- drop c1825bef - Discusses beta-blockers, not DAPT duration or de-escalation.
- drop c778eb00 - Provides bleeding risk score, not DAPT duration guidance.


## ret_120 - Colorectal Carcinoma [llm_verified] (re-judge)
**Q:** What role does BRCA mutation testing play in colorectal cancer management?
- drop aea8ede1 - Discusses genetic testing generally, not BRCA's specific role in CRC.
- drop 172c8135 - Focuses on family history risk, not BRCA mutation testing.
- regrade faad2c4d supporting->primary - Lists hereditary syndromes including MAP, which involves BRCA-related genes.


## ret_121 - Cervical Cancer [llm_verified] (re-judge)
**Q:** What is the recommended treatment for early-stage (FIGO IA-IB) cervical cancer?
- drop 11f6fe71 - Focuses on cervical cancer in pregnancy, not general early-stage treatment.
- regrade ea797d06 primary->supporting - Discusses fertility-preserving surgery options for early-stage cervical cancer.
- regrade 28f447dd supporting->primary - Directly specifies recommended surgical treatments for FIGO IA-IB cervical cancer.


## ret_122 - Cervical Cancer [llm_verified] (re-judge)
**Q:** When is concurrent chemoradiotherapy indicated in locally advanced cervical cancer?
- drop bcef5cdd - Discusses neuroendocrine cancers, not general LACC indications.
- drop 11f6fe71 - Covers pregnancy, not the primary question on CCRT indications.


## ret_123 - Cervical Cancer [llm_verified] (re-judge)
**Q:** How should recurrent cervical cancer be managed?
- drop 929377d1 - Lists clinical questions, not management of recurrence.
- regrade ec27dc02 supporting->primary - Directly discusses management of recurrent cervical cancer.


## ret_124 - Cervical Cancer [llm_verified] (re-judge)
**Q:** What follow-up and surveillance is recommended after cervical cancer treatment?
- drop 11f6fe71 - Discusses pregnancy management, not post-treatment follow-up.
- drop bcef5cdd - Focuses on neuroendocrine cancer specifics, not general follow-up.


## ret_125 - Obesity Management [llm_verified] (re-judge)
**Q:** What BMI and waist circumference thresholds define obesity in Asian adults?
- drop 9c1c4d23 - Focuses on children, not Asian adult thresholds.
- regrade c60c7cb3 primary->supporting - Discusses lower BMI thresholds for Asians but no specific numbers.
- regrade 7eeb9a4b supporting->primary - Directly provides BMI cut-offs for Asian adults.


## ret_126 - Obesity Management [llm_verified] (re-judge)
**Q:** When is anti-obesity pharmacotherapy indicated for weight management?
- regrade 8e278114 primary->supporting - Describes semaglutide for obesity but not general indications.
- regrade 7eeb9a4b supporting->primary - Key recommendations include screening and diagnosis criteria for obesity.


## ret_127 - Obesity Management [llm_verified] (re-judge)
**Q:** What are the referral criteria for bariatric or metabolic surgery in obesity?
- drop 849d5e3c - Describes general paediatric obesity management, not surgical referral criteria.
- regrade 1e766731 primary->supporting - Provides criteria for adolescent bariatric surgery referral, not general adult criteria.
- regrade 5aa22e31 supporting->primary - Directly lists BMI and comorbidity indications for bariatric surgery.


## ret_128 - Obesity Management [llm_verified] (re-judge)
**Q:** How should childhood and adolescent obesity be assessed and managed?
- regrade 1e766731 primary->supporting - Addresses surgical management for severe adolescent obesity, a specific aspect.
- regrade 98db85cd supporting->primary - Directly outlines first-line lifestyle management for childhood obesity.


## ret_130 - T2 Diabetes Mellitus [llm_verified] (re-judge)
**Q:** What is the recommended HbA1c target for most adults with type 2 diabetes?
- drop 7b687a38 - Discusses HbA1c assay standardization, not target values.
- drop 9eddae0d - Focuses on insulin regimen, not HbA1c targets.


## ret_139 - Diabetes in Pregnancy [llm_verified] (re-judge)
**Q:** When is insulin indicated in gestational diabetes mellitus?
- drop 84724c82 - Focuses on screening and preconception, not insulin indication.

