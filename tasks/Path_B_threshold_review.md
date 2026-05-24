# Path B threshold-extraction review

Sampled 25 edges per relation, gated on `confidence == "high"`.
Shown below: 49 extractions that would be MERGEd onto existing edges.

**For each row, verify the extracted threshold against the evidence text and tick one box.**
`source_document` points at the section in the CPG markdown for cross-reference.

---

## REQUIRES_DOSE_ADJUSTMENT  (9 extractions)

### REQUIRES_DOSE_ADJUSTMENT #1: `Thiazide Diuretics` → `Advanced Renal Impairment`

- **Source:** Section 14.6: HF And Chronic Kidney Disease
- **Existing trigger string:** `'eGFR<30'`
- **Evidence:** _If eGFR < 30 mls/min/1.73m², most thiazide diuretics are no longer effective and loop diuretics are preferred._
- **Extracted:** `eGFR < 30 mL/min/1.73m2`  (negated=False)
- **Rationale:** The text explicitly states eGFR < 30 mL/min/1.73m2 as the threshold where thiazides become ineffective, requiring switch to loop diuretics.
- **edge_id:** `5:94ea5408-46d3-403a-a3d2-6b09bcc86e92:6917549918362018474`

- [ ] Approve  [ ] Edit  [ ] Reject

### REQUIRES_DOSE_ADJUSTMENT #2: `Arb` → `Egfr Reduction`

- **Source:** Section 14.6: HF And Chronic Kidney Disease
- **Existing trigger string:** `'eGFR reduces ≥25%'`
- **Evidence:** _Consider reducing or discontinuing ACEi/ARB within two months from commencement (after excluding other precipitating factors) when: SCr levels remain ≥ 30% from the baseline (or eGFR reduces ≥ 25%)_
- **Extracted:** `eGFR >= 25 %`  (negated=False)
- **Rationale:** The text explicitly states eGFR reduces ≥25% as a trigger for dose adjustment.
- **edge_id:** `5:94ea5408-46d3-403a-a3d2-6b09bcc86e92:1157445994955149387`

- [ ] Approve  [ ] Edit  [ ] Reject

### REQUIRES_DOSE_ADJUSTMENT #3: `Mras` → `Hyperkalemia`

- **Source:** Section 10: Chronic Heart Failure - Heart Failure with Reduced LVEF (HFrEF)
- **Existing trigger string:** `'serum potassium >5.5mmol/l'`
- **Evidence:** _If despite these measures, hyperkalemia persists (serum potassium >5.5mmol/l), then the dose of MRA should be reduced or stopped._
- **Extracted:** `K+ > 5.5 mmol/L`  (negated=False)
- **Rationale:** Explicit numeric threshold for serum potassium triggers dose adjustment.
- **edge_id:** `5:94ea5408-46d3-403a-a3d2-6b09bcc86e92:1152942395327783322`

- [ ] Approve  [ ] Edit  [ ] Reject

### REQUIRES_DOSE_ADJUSTMENT #4: `Eptifibatide` → `Chronic Kidney Disease Stage 3`

- **Source:** Section 12: Appendices
- **Existing trigger string:** `'eGFR <50 mL/min/1.73m2'`
- **Evidence:** _No adjustment of bolus, reduce infusion rate to 1 µg/kg/min i eGFR <50 mL/min/1.73m2_
- **Extracted:** `eGFR < 50 mL/min/1.73m2`  (negated=False)
- **Rationale:** Evidence explicitly states dose adjustment for eGFR < 50 mL/min/1.73m2.
- **edge_id:** `5:94ea5408-46d3-403a-a3d2-6b09bcc86e92:6917549918362017734`

- [ ] Approve  [ ] Edit  [ ] Reject

### REQUIRES_DOSE_ADJUSTMENT #5: `Methyldopa` → `Postpartum Period`

- **Source:** Section 14: Management Of Hypertension In Pregnancy
- **Existing trigger string:** `'postpartum delivery'`
- **Evidence:** _Methyldopa should be stopped within 2 days following delivery to avoid the risk of depression._
- **Extracted:** `duration <= 2 days`  (negated=False)
- **Rationale:** The text specifies a numeric duration threshold of 2 days following delivery for stopping methyldopa.
- **edge_id:** `5:94ea5408-46d3-403a-a3d2-6b09bcc86e92:6917549918362014261`

- [ ] Approve  [ ] Edit  [ ] Reject

### REQUIRES_DOSE_ADJUSTMENT #6: `Acei/Arb` → `Hyperkalemia`

- **Source:** Section 14.6: HF And Chronic Kidney Disease
- **Existing trigger string:** `'Serum potassium ≥5.5 mmol/L'`
- **Evidence:** _Consider reducing or discontinuing ACEi/ARB within two months from commencement (after excluding other precipitating factors) when: Serum potassium ≥ 5.5 mmol/L_
- **Extracted:** `K+ >= 5.5 mmol/L`  (negated=False)
- **Rationale:** The evidence explicitly states a specific numeric threshold of ≥5.5 mmol/L for serum potassium as the trigger for dose adjustment.
- **edge_id:** `5:94ea5408-46d3-403a-a3d2-6b09bcc86e92:1155194195141461698`

- [ ] Approve  [ ] Edit  [ ] Reject

### REQUIRES_DOSE_ADJUSTMENT #7: `Friii` → `Hypoglycemia`

- **Source:** Section 4: Management of Diabetic Metabolic Emergencies
- **Existing trigger string:** `'glucose <14 mmol/L'`
- **Evidence:** _If glucose <14 mmol/L → reduce FRIII by 50% and switch to dextrose drip_
- **Extracted:** `glucose < 14 mmol/L`  (negated=False)
- **Rationale:** Evidence explicitly states a numeric glucose threshold (<14 mmol/L) that triggers dose adjustment.
- **edge_id:** `5:94ea5408-46d3-403a-a3d2-6b09bcc86e92:1155194195141473223`

- [ ] Approve  [ ] Edit  [ ] Reject

### REQUIRES_DOSE_ADJUSTMENT #8: `Clopidogrel` → `Age Over 75 Year`

- **Source:** Section 8: Cardiac Care Unit (Ccu) Management
- **Existing trigger string:** `'age > 75 years'`
- **Evidence:** _In older patients, a loading dose of 75 mg may be adequate._
- **Extracted:** `age > 75 years`  (negated=False)
- **Rationale:** The trigger 'age > 75 years' directly specifies the numeric threshold for age, indicating dose adjustment is required for patients exceeding this age.
- **edge_id:** `5:94ea5408-46d3-403a-a3d2-6b09bcc86e92:6917549918362016910`

- [ ] Approve  [ ] Edit  [ ] Reject

### REQUIRES_DOSE_ADJUSTMENT #9: `Thiazide Diuretics` → `Egfr < 30 Mls/Min/1.73M²`

- **Source:** Section 14.6: HF And Chronic Kidney Disease
- **Existing trigger string:** `'eGFR<30'`
- **Evidence:** _If eGFR < 30 mls/min/1.73m², most thiazide diuretics are no longer effective and loop diuretics are preferred._
- **Extracted:** `eGFR < 30 mL/min/1.73m2`  (negated=False)
- **Rationale:** The text explicitly states eGFR < 30 mL/min/1.73m2 as the threshold where thiazide diuretics become ineffective.
- **edge_id:** `5:94ea5408-46d3-403a-a3d2-6b09bcc86e92:6917549918362018506`

- [ ] Approve  [ ] Edit  [ ] Reject

---

## REQUIRES_MONITORING  (10 extractions)

### REQUIRES_MONITORING #1: `Pcsk9 Inhibitor` → `Severe Chronic Kidney Disease`

- **Source:** Section 7: Management Of Dyslipidaemia
- **Existing trigger string:** `'eGFR<20'`
- **Evidence:** _It has not been studied in patients with eGFR < 20ml/min/1.73m²._
- **Extracted:** `eGFR < 20 mL/min/1.73m2`  (negated=False)
- **Rationale:** The text explicitly states a numeric eGFR threshold of 20 mL/min/1.73m².
- **edge_id:** `5:94ea5408-46d3-403a-a3d2-6b09bcc86e92:6919788524036171207`

- [ ] Approve  [ ] Edit  [ ] Reject

### REQUIRES_MONITORING #2: `Oral Oxycodone` → `Pain Specialist Or Palliative Medicine Specialist Referral`

- **Source:** Section 4: Pharmacological Intervention
- **Existing trigger string:** `'>400 mg/day'`
- **Evidence:** _When opioid doses are very high (oral morphine >600 mg/day, oral oxycodone >400 mg/day or transdermal fentanyl >200 mcg/hour), patients should be referred to a pain specialist or palliative medicine specialist._
- **Extracted:** `oxycodone_dose > 400 mg/day`  (negated=False)
- **Rationale:** The text explicitly states oral oxycodone >400 mg/day as the trigger for specialist referral.
- **edge_id:** `5:94ea5408-46d3-403a-a3d2-6b09bcc86e92:1152929201188243028`

- [ ] Approve  [ ] Edit  [ ] Reject

### REQUIRES_MONITORING #3: `Glucocorticoid` → `Plasma Glucose`

- **Source:** Section 6: T2DM in Special Populations
- **Existing trigger string:** `'Prednisolone ≥5mg/day'`
- **Evidence:** _All patients receiving glucocorticoids equivalent to Prednisolone of ≥5mg/day should have their plasma glucose monitored for 24–48 hours and insulin commenced if plasma glucose is persistently high._
- **Extracted:** `prednisolone_dose >= 5 mg/day`  (negated=False)
- **Rationale:** The text explicitly states that patients receiving a glucocorticoid dose equivalent to prednisolone >= 5 mg/day require plasma glucose monitoring.
- **edge_id:** `5:94ea5408-46d3-403a-a3d2-6b09bcc86e92:6917536724222489820`

- [ ] Approve  [ ] Edit  [ ] Reject

### REQUIRES_MONITORING #4: `Ace Inhibitor` → `Renal Function`

- **Source:** Section 14.6: HF And Chronic Kidney Disease
- **Existing trigger string:** `'creatinine rise >30% over 2 months'`
- **Evidence:** _A persistent rise in creatinine of >30% over 2 months warrants cessation of ACEI/ARB drug therapy._
- **Extracted:** `creatinine > 30 %`  (negated=False)
- **Rationale:** The text specifies a >30% rise in creatinine as a trigger for cessation of therapy.
- **edge_id:** `5:94ea5408-46d3-403a-a3d2-6b09bcc86e92:1152929201188242085`

- [ ] Approve  [ ] Edit  [ ] Reject

### REQUIRES_MONITORING #5: `Orlistat` → `Multivitamin Level`

- **Source:** Section 3.9: Management of Co-morbidities in T2DM
- **Existing trigger string:** `'use >12 months'`
- **Evidence:** _MVT replacements if used >12 months._
- **Extracted:** `duration > 12 months`  (negated=False)
- **Rationale:** Text explicitly states a numeric duration threshold of >12 months triggering multivitamin monitoring.
- **edge_id:** `5:94ea5408-46d3-403a-a3d2-6b09bcc86e92:6917536724222489414`

- [ ] Approve  [ ] Edit  [ ] Reject

### REQUIRES_MONITORING #6: `Transdermal Fentanyl` → `Pain Specialist Or Palliative Medicine Specialist Referral`

- **Source:** Section 4: Pharmacological Intervention
- **Existing trigger string:** `'>200 mcg/hour'`
- **Evidence:** _When opioid doses are very high (oral morphine >600 mg/day, oral oxycodone >400 mg/day or transdermal fentanyl >200 mcg/hour), patients should be referred to a pain specialist or palliative medicine specialist._
- **Extracted:** `transdermal_fentanyl_dose > 200 mcg/hour`  (negated=False)
- **Rationale:** The text explicitly states transdermal fentanyl >200 mcg/hour as the threshold for specialist referral.
- **edge_id:** `5:94ea5408-46d3-403a-a3d2-6b09bcc86e92:1152929201188242695`

- [ ] Approve  [ ] Edit  [ ] Reject

### REQUIRES_MONITORING #7: `Rehabilitative Surgery` → `Graves' Ophthalmopathy Inactivity`

- **Source:** Section 9: Graves' Ophthalmopathy
- **Existing trigger string:** `'6 months of inactivity'`
- **Evidence:** _Rehabilitative surgery should be done after the disease has been inactive for 6 months._
- **Extracted:** `duration >= 6 months`  (negated=False)
- **Rationale:** The text explicitly requires a 6-month period of inactivity before surgery.
- **edge_id:** `5:94ea5408-46d3-403a-a3d2-6b09bcc86e92:6917536724222488383`

- [ ] Approve  [ ] Edit  [ ] Reject

### REQUIRES_MONITORING #8: `Angiotensin Receptor Blocker` → `Renal Function`

- **Source:** Section 7: Hypertension In Special Groups
- **Existing trigger string:** `'creatinine rise >30% over 2 months'`
- **Evidence:** _A persistent rise in creatinine of >30% over 2 months warrants cessation of ACEI/ARB drug therapy._
- **Extracted:** `creatinine > 30 %`  (negated=False)
- **Rationale:** Text specifies a creatinine rise >30% as the threshold for action.
- **edge_id:** `5:94ea5408-46d3-403a-a3d2-6b09bcc86e92:1152929201188241775`

- [ ] Approve  [ ] Edit  [ ] Reject

### REQUIRES_MONITORING #9: `Insulin` → `All-Cause Mortality And Hospitalization For Heart Failure`

- **Source:** Section 14.1: Diabetes And Heart Failure
- **Existing trigger string:** `'HbA1c < 7%'`
- **Evidence:** _Insulin -This has been associated with increased all-cause mortality and hospitalization for HF especially in patients with low HbA1c < 7%._
- **Extracted:** `HbA1c < 7 %`  (negated=False)
- **Rationale:** The evidence explicitly states 'low HbA1c < 7%' as the condition associated with increased risk.
- **edge_id:** `5:94ea5408-46d3-403a-a3d2-6b09bcc86e92:6917536724222485024`

- [ ] Approve  [ ] Edit  [ ] Reject

### REQUIRES_MONITORING #10: `Oral Morphine` → `Pain Specialist Or Palliative Medicine Specialist Referral`

- **Source:** Section 4: Pharmacological Intervention
- **Existing trigger string:** `'>600 mg/day'`
- **Evidence:** _When opioid doses are very high (oral morphine >600 mg/day, oral oxycodone >400 mg/day or transdermal fentanyl >200 mcg/hour), patients should be referred to a pain specialist or palliative medicine specialist._
- **Extracted:** `morphine_dose > 600 mg/day`  (negated=False)
- **Rationale:** Text specifies a numeric dose threshold for referral (>600 mg/day oral morphine).
- **edge_id:** `5:94ea5408-46d3-403a-a3d2-6b09bcc86e92:6917536724222477907`

- [ ] Approve  [ ] Edit  [ ] Reject

---

## CONTRAINDICATED_WITH  (18 extractions)

### CONTRAINDICATED_WITH #1: `Dulaglutide` → `Severe Chronic Kidney Disease`

- **Source:** Appendix: Drug Dosage Adjustments in Chronic Kidney Disease (CKD) and Cardiovascular Outcome Trials (CVOTs)
- **Existing trigger string:** `'eGFR <15'`
- **Evidence:** _<15: Avoid_
- **Extracted:** `eGFR < 15 mL/min/1.73m2`  (negated=False)
- **Rationale:** The text explicitly states 'eGFR <15' as the threshold for avoiding dulaglutide.
- **edge_id:** `5:94ea5408-46d3-403a-a3d2-6b09bcc86e92:1152925902653370684`

- [ ] Approve  [ ] Edit  [ ] Reject

### CONTRAINDICATED_WITH #2: `Exenatide Er` → `Severe Chronic Kidney Disease`

- **Source:** Appendix: Drug Dosage Adjustments in Chronic Kidney Disease (CKD) and Cardiovascular Outcome Trials (CVOTs)
- **Existing trigger string:** `'GFR <30'`
- **Evidence:** _Avoid_
- **Extracted:** `eGFR < 30 mL/min/1.73m2`  (negated=False)
- **Rationale:** The trigger explicitly states 'GFR <30' as the condition for avoidance, indicating a specific numeric threshold for contraindication.
- **edge_id:** `5:94ea5408-46d3-403a-a3d2-6b09bcc86e92:1152925902653370682`

- [ ] Approve  [ ] Edit  [ ] Reject

### CONTRAINDICATED_WITH #3: `Fibrate` → `Statin`

- **Source:** Section 10: Management Of Dyslipidemia In Specific Conditions
- **Existing trigger string:** `'eGFR<60'`
- **Evidence:** _In patients with CKD (eGFR <60 mL/min/1.73 m2), the combination of statins and fibrates and ezetimibe monotherapy is not recommended due to risk of drug toxicity._
- **Extracted:** `eGFR < 60 mL/min/1.73m2`  (negated=False)
- **Rationale:** The text explicitly states eGFR <60 mL/min/1.73 m2 as the condition for the contraindication.
- **edge_id:** `5:94ea5408-46d3-403a-a3d2-6b09bcc86e92:78`

- [ ] Approve  [ ] Edit  [ ] Reject

### CONTRAINDICATED_WITH #4: `Glibenclamide` → `Severe Chronic Kidney Disease`

- **Source:** Appendix: Drug Dosage Adjustments in Chronic Kidney Disease (CKD) and Cardiovascular Outcome Trials (CVOTs)
- **Existing trigger string:** `'GFR <30'`
- **Evidence:** _Avoid_
- **Extracted:** `eGFR < 30 mL/min/1.73m2`  (negated=False)
- **Rationale:** The trigger explicitly states GFR <30 as the threshold for severe chronic kidney disease.
- **edge_id:** `5:94ea5408-46d3-403a-a3d2-6b09bcc86e92:1152925902653365015`

- [ ] Approve  [ ] Edit  [ ] Reject

### CONTRAINDICATED_WITH #5: `Gtn` → `Hypotension`

- **Source:** Section 7: In-Hospital Management
- **Existing trigger string:** `'SBP < 90 mmHg'`
- **Evidence:** _One dose of sublingual GTN by tablet or spray if chest pain persists (avoid if SBP < 90 mmHg)._
- **Extracted:** `SBP < 90 mmHg`  (negated=False)
- **Rationale:** The evidence explicitly states to avoid GTN if systolic blood pressure is less than 90 mmHg.
- **edge_id:** `5:94ea5408-46d3-403a-a3d2-6b09bcc86e92:1152925902653362270`

- [ ] Approve  [ ] Edit  [ ] Reject

### CONTRAINDICATED_WITH #6: `Metformin` → `Diabetic Kidney Disease`

- **Source:** Section 3.7: Treatment algorithms for the management of T2DM
- **Existing trigger string:** `'eGFR<30'`
- **Evidence:** _Avoid* if eGFR < 30ml/min/1.73m²_
- **Extracted:** `eGFR < 30 mL/min/1.73m2`  (negated=False)
- **Rationale:** Evidence explicitly states contraindication if eGFR < 30 mL/min/1.73m².
- **edge_id:** `5:94ea5408-46d3-403a-a3d2-6b09bcc86e92:6917533425687599606`

- [ ] Approve  [ ] Edit  [ ] Reject

### CONTRAINDICATED_WITH #7: `Lixisenatide` → `Severe Chronic Kidney Disease`

- **Source:** Appendix: Drug Dosage Adjustments in Chronic Kidney Disease (CKD) and Cardiovascular Outcome Trials (CVOTs)
- **Existing trigger string:** `'GFR <30'`
- **Evidence:** _Avoid_
- **Extracted:** `eGFR < 30 mL/min/1.73m2`  (negated=False)
- **Rationale:** The trigger 'GFR <30' explicitly defines a numeric threshold for severe chronic kidney disease as contraindication.
- **edge_id:** `5:94ea5408-46d3-403a-a3d2-6b09bcc86e92:1152925902653370683`

- [ ] Approve  [ ] Edit  [ ] Reject

### CONTRAINDICATED_WITH #8: `Prasugrel` → `Stage 5 Chronic Kidney Disease`

- **Source:** Section 12: Appendices
- **Existing trigger string:** `'eGFR<15'`
- **Evidence:** _Stage 5 (eGFR <15 mL/min/1.73m2): Not recommended_
- **Extracted:** `eGFR < 15 mL/min/1.73m2`  (negated=False)
- **Rationale:** The evidence explicitly states eGFR <15 mL/min/1.73m2 for Stage 5 CKD as contraindicated.
- **edge_id:** `5:94ea5408-46d3-403a-a3d2-6b09bcc86e92:6917533425687601090`

- [ ] Approve  [ ] Edit  [ ] Reject

### CONTRAINDICATED_WITH #9: `Ertugliflozin` → `Severe Chronic Kidney Disease`

- **Source:** Appendix: Drug Dosage Adjustments in Chronic Kidney Disease (CKD) and Cardiovascular Outcome Trials (CVOTs)
- **Existing trigger string:** `'GFR <30'`
- **Evidence:** _Avoid_
- **Extracted:** `eGFR < 30 mL/min/1.73m2`  (negated=False)
- **Rationale:** The trigger 'GFR <30' directly encodes a numeric eGFR threshold of 30 mL/min/1.73m2 that contraindicates Ertugliflozin.
- **edge_id:** `5:94ea5408-46d3-403a-a3d2-6b09bcc86e92:1152925902653370685`

- [ ] Approve  [ ] Edit  [ ] Reject

### CONTRAINDICATED_WITH #10: `Ezetimibe Monotherapy` → `Chronic Kidney Disease Stage 3A-5`

- **Source:** Section 10: Management Of Dyslipidemia In Specific Conditions
- **Existing trigger string:** `'eGFR<60'`
- **Evidence:** _In patients with CKD (eGFR <60 mL/min/1.73 m2), the combination of statins and fibrates and ezetimibe monotherapy is not recommended due to risk of drug toxicity._
- **Extracted:** `eGFR < 60 mL/min/1.73m2`  (negated=False)
- **Rationale:** The text explicitly states eGFR <60 mL/min/1.73m2 as the threshold for contraindication.
- **edge_id:** `5:94ea5408-46d3-403a-a3d2-6b09bcc86e92:1155177702467053121`

- [ ] Approve  [ ] Edit  [ ] Reject

### CONTRAINDICATED_WITH #11: `Fondaparinux` → `Severe Renal Failure`

- **Source:** Section 8: NSTE-ACS In Special Groups
- **Existing trigger string:** `'CrCl <20 mL/min'`
- **Evidence:** _Fondaparinux is contraindicated in severe renal failure (CrCl <20 mL/min)._
- **Extracted:** `CrCl < 20 mL/min`  (negated=False)
- **Rationale:** Evidence explicitly states a numeric CrCl threshold for severe renal failure.
- **edge_id:** `5:94ea5408-46d3-403a-a3d2-6b09bcc86e92:6917533425687601480`

- [ ] Approve  [ ] Edit  [ ] Reject

### CONTRAINDICATED_WITH #12: `Acarbose` → `Severe Chronic Kidney Disease`

- **Source:** Appendix: Drug Dosage Adjustments in Chronic Kidney Disease (CKD) and Cardiovascular Outcome Trials (CVOTs)
- **Existing trigger string:** `'eGFR <25'`
- **Evidence:** _<25: Avoid_
- **Extracted:** `eGFR < 25 mL/min/1.73m2`  (negated=False)
- **Rationale:** The text explicitly states a threshold of eGFR <25 for avoidance, indicating a contraindication trigger.
- **edge_id:** `5:94ea5408-46d3-403a-a3d2-6b09bcc86e92:1152925902653364388`

- [ ] Approve  [ ] Edit  [ ] Reject

### CONTRAINDICATED_WITH #13: `Luseogliflozin` → `Severe Chronic Kidney Disease`

- **Source:** Appendix: Drug Dosage Adjustments in Chronic Kidney Disease (CKD) and Cardiovascular Outcome Trials (CVOTs)
- **Existing trigger string:** `'GFR <30'`
- **Evidence:** _Avoid_
- **Extracted:** `eGFR < 30 mL/min/1.73m2`  (negated=False)
- **Rationale:** The trigger 'GFR <30' directly indicates a numeric threshold for contraindication.
- **edge_id:** `5:94ea5408-46d3-403a-a3d2-6b09bcc86e92:1152925902653370686`

- [ ] Approve  [ ] Edit  [ ] Reject

### CONTRAINDICATED_WITH #14: `Sglt2 Inhibitor` → `Severe Renal Impairment`

- **Source:** Section 3.6: Glucose Lowering Drugs and Insulin Therapy
- **Existing trigger string:** `'eGFR<30'`
- **Evidence:** _Do not initiate at eGFR <30 ml/min/1.73 m² but, may continue if already initiated._
- **Extracted:** `eGFR < 30 mL/min/1.73m2`  (negated=False)
- **Rationale:** Text explicitly states not to initiate at eGFR <30 mL/min/1.73m2, which is a specific numeric threshold for contraindication.
- **edge_id:** `5:94ea5408-46d3-403a-a3d2-6b09bcc86e92:1157429502280735231`

- [ ] Approve  [ ] Edit  [ ] Reject

### CONTRAINDICATED_WITH #15: `Semaglutide` → `Severe Chronic Kidney Disease`

- **Source:** Appendix: Drug Dosage Adjustments in Chronic Kidney Disease (CKD) and Cardiovascular Outcome Trials (CVOTs)
- **Existing trigger string:** `'eGFR <15'`
- **Evidence:** _<15: Avoid_
- **Extracted:** `eGFR < 15 mL/min/1.73m2`  (negated=False)
- **Rationale:** The text explicitly states an eGFR threshold of <15 to avoid the drug, which is a specific numeric threshold for a contraindication.
- **edge_id:** `5:94ea5408-46d3-403a-a3d2-6b09bcc86e92:1159681302094420149`

- [ ] Approve  [ ] Edit  [ ] Reject

### CONTRAINDICATED_WITH #16: `Glp1 Receptor Agonist` → `Diabetic Kidney Disease`

- **Source:** Section 3.7: Treatment algorithms for the management of T2DM
- **Existing trigger string:** `'eGFR<15'`
- **Evidence:** _avoid if eGFR < 15 ml/min/1.73m²_
- **Extracted:** `eGFR < 15 mL/min/1.73m2`  (negated=False)
- **Rationale:** The text explicitly states to avoid the drug if eGFR is below 15 mL/min/1.73m², defining a numeric contraindication threshold.
- **edge_id:** `5:94ea5408-46d3-403a-a3d2-6b09bcc86e92:1152925902653371101`

- [ ] Approve  [ ] Edit  [ ] Reject

### CONTRAINDICATED_WITH #17: `Bupropion` → `Mao Inhibitor`

- **Source:** Section 12: Appendices
- **Existing trigger string:** `'within past 14 days'`
- **Evidence:** _Contraindicated in individuals with a history of seizure disorder, a history of an eating disorder, who are using another form of bupropion (Wellbutrin SR) or who have used an MAO inhibitor in the past 14 days._
- **Extracted:** `duration < 14 days`  (negated=True)
- **Rationale:** The text specifies a numeric time window (14 days) for contraindication after MAO inhibitor use.
- **edge_id:** `5:94ea5408-46d3-403a-a3d2-6b09bcc86e92:6917533425687601163`

- [ ] Approve  [ ] Edit  [ ] Reject

### CONTRAINDICATED_WITH #18: `Thiazide Diuretics` → `Severe Renal Insufficiency`

- **Source:** Section 7: Hypertension In Special Groups
- **Existing trigger string:** `'GFR<30'`
- **Evidence:** _In patients with GFR <30 ml/min/1.73m², thiazide diuretics may not be effective antihypertensive agents and therefore loop diuretics are preferred._
- **Extracted:** `eGFR < 30 mL/min/1.73m2`  (negated=False)
- **Rationale:** The evidence directly states GFR <30 ml/min/1.73m² as the threshold for contraindication.
- **edge_id:** `5:94ea5408-46d3-403a-a3d2-6b09bcc86e92:1155177702467047980`

- [ ] Approve  [ ] Edit  [ ] Reject

---

## HAS_DOSAGE  (12 extractions)

### HAS_DOSAGE #1: `Warfarin` → `Inr 1.5 To 2.5`

- **Source:** Section 7: Treatment Of PAH In Adults
- **Existing trigger string:** `'higher risk of bleeding'`
- **Evidence:** _for IPAH patients with a higher risk of bleeding, the target INR should be 1.5 to 2.5._
- **Extracted:** `INR between 1.5..2.5 `  (negated=False)
- **Rationale:** The text explicitly states the target INR range of 1.5 to 2.5 for IPAH patients with higher bleeding risk.
- **edge_id:** `5:94ea5408-46d3-403a-a3d2-6b09bcc86e92:6917535624710852593`

- [ ] Approve  [ ] Edit  [ ] Reject

### HAS_DOSAGE #2: `Insulin` → `<0.5 Iu/Kg/Day`

- **Source:** Section 7: Insulin Therapy
- **Existing trigger string:** `'partial remission phase'`
- **Evidence:** _during partial remission phase, the TDD is often <0.5 IU/kg/day_
- **Extracted:** `TDD < 0.5 IU/kg/day`  (negated=False)
- **Rationale:** Text states TDD is often <0.5 IU/kg/day during partial remission phase, which is a specific numeric dosage threshold.
- **edge_id:** `5:94ea5408-46d3-403a-a3d2-6b09bcc86e92:6917535624710859067`

- [ ] Approve  [ ] Edit  [ ] Reject

### HAS_DOSAGE #3: `Simvastatin` → `40 Mg/Day`

- **Source:** Section 10: Management Of Dyslipidemia In Specific Conditions
- **Existing trigger string:** `'CKD Stage 3a-5'`
- **Evidence:** _Table 15: Dosing Modifications For Lipid-Lowering Drugs In CKD (Stage 3a - 5): Simvastatin Max Dose (mg/day) 40_
- **Extracted:** `simvastatin_dose <= 40 mg/day`  (negated=False)
- **Rationale:** Text explicitly states a maximum dose of 40 mg/day for CKD stages 3a-5.
- **edge_id:** `5:94ea5408-46d3-403a-a3d2-6b09bcc86e92:1161935300931359017`

- [ ] Approve  [ ] Edit  [ ] Reject

### HAS_DOSAGE #4: `Clopidogrel` → `150 Mg/Day`

- **Source:** Section 6: Lesion / Device Specific Conditions
- **Existing trigger string:** `'platelet aggregation inhibition <50%'`
- **Evidence:** _If platelet aggregation studies reveal insufficient (<50%) inhibition of platelet aggregation with standard dual antiplatelet therapy, a higher dose clopidogrel - 150 mg/day - should be considered._
- **Extracted:** `platelet_aggregation_inhibition < 50 %`  (negated=False)
- **Rationale:** Text explicitly states a numeric threshold (<50%) for insufficient platelet aggregation inhibition that triggers consideration of a higher clopidogrel dose.
- **edge_id:** `5:94ea5408-46d3-403a-a3d2-6b09bcc86e92:6917535624710850523`

- [ ] Approve  [ ] Edit  [ ] Reject

### HAS_DOSAGE #5: `Insulin` → `1.2 - 2 Iu/Kg/Day`

- **Source:** Section 7: Insulin Therapy
- **Existing trigger string:** `'puberty'`
- **Evidence:** _during puberty, higher requirements may be needed, 1.2 - 2 IU/kg/day_
- **Extracted:** `insulin_dose between 1.2..2.0 IU/kg/day`  (negated=False)
- **Rationale:** Text specifies a dose range of 1.2-2 IU/kg/day during puberty.
- **edge_id:** `5:94ea5408-46d3-403a-a3d2-6b09bcc86e92:6917535624710859069`

- [ ] Approve  [ ] Edit  [ ] Reject

### HAS_DOSAGE #6: `Insulin` → `0.7 - 1.0 Iu/Kg/Day`

- **Source:** Section 7: Insulin Therapy
- **Existing trigger string:** `'pre-pubertal'`
- **Evidence:** _pre-pubertal children usually require 0.7 - 1.0 IU/kg/day_
- **Extracted:** `insulin_dose between 0.7..1.0 IU/kg/day`  (negated=False)
- **Rationale:** The text explicitly states a numeric dosage range for insulin in pre-pubertal children.
- **edge_id:** `5:94ea5408-46d3-403a-a3d2-6b09bcc86e92:6917535624710859068`

- [ ] Approve  [ ] Edit  [ ] Reject

### HAS_DOSAGE #7: `8.4% Nahco₃` → `1 Ampoule (50 Ml) Added To 200 Ml D5% Over 1 Hr, Repeated Every 1-2 Hour`

- **Source:** Section 4: Management of Diabetic Metabolic Emergencies
- **Existing trigger string:** `'pH <6.9'`
- **Evidence:** _E.g. 1 ampoule (50 ml) 8.4% NaHCO₃ added to 200 ml D5% over 1 hr, repeated every 1-2 hours, until pH is ≥7.0._
- **Extracted:** `pH >= 7.0 `  (negated=True)
- **Rationale:** The text states the dosing regimen continues until pH reaches ≥7.0, defining the safe threshold.
- **edge_id:** `5:94ea5408-46d3-403a-a3d2-6b09bcc86e92:1152928101676626880`

- [ ] Approve  [ ] Edit  [ ] Reject

### HAS_DOSAGE #8: `Unfractionated Heparin` → `Iv Bolus 60 Iu/Kg (Max 4000 Iu), Infusion 12Iu/Kg/Hour (Max 1000 Iu/Hour) Adjusted To Maintain Aptt 1.5 - 2.0X Normal`

- **Source:** Section 12: Appendices
- **Existing trigger string:** `None`
- **Evidence:** _IV bolus 60 IU/kg (max 4000 IU), infusion 12IU/kg/hour (max 1000 IU/hour) adjusted to maintain aPTT 1.5 - 2.0x normal_
- **Extracted:** `aPTT between 1.5..2.0 x normal`  (negated=False)
- **Rationale:** The dosage is adjusted to maintain aPTT within a specific numeric range (1.5-2.0x normal).
- **edge_id:** `5:94ea5408-46d3-403a-a3d2-6b09bcc86e92:6917535624710856654`

- [ ] Approve  [ ] Edit  [ ] Reject

### HAS_DOSAGE #9: `Aspirin` → `75Mg To 325Mg Daily`

- **Source:** Section 5: Prevention Of Stroke
- **Existing trigger string:** `None`
- **Evidence:** _The recommended dose of oral Aspirin post-stroke is 75mg to 325mg daily._
- **Extracted:** `aspirin_dose between 75..325 mg/day`  (negated=False)
- **Rationale:** The text explicitly states a recommended dosage range of 75-325 mg daily.
- **edge_id:** `5:94ea5408-46d3-403a-a3d2-6b09bcc86e92:6919787424524541501`

- [ ] Approve  [ ] Edit  [ ] Reject

### HAS_DOSAGE #10: `Ertugliflozin` → `15 Mg Od Maximum`

- **Source:** Section 3.6: Glucose Lowering Drugs and Insulin Therapy
- **Existing trigger string:** `None`
- **Evidence:** _Maximum dose: 15 mg OD_
- **Extracted:** `ertugliflozin_dose <= 15 mg/day`  (negated=False)
- **Rationale:** The text explicitly states a maximum dose of 15 mg OD, which is a numeric threshold for the drug's dosing.
- **edge_id:** `5:94ea5408-46d3-403a-a3d2-6b09bcc86e92:6917535624710861395`

- [ ] Approve  [ ] Edit  [ ] Reject

### HAS_DOSAGE #11: `Nicotine Lozenge` → `2 Mg And 4 Mg; Week 1-6: 1 Lozenge 1-2 Hourly Minimum 9 Per Day; Week 7-9: 1 Lozenge 2-4 Hourly; Week 10-12: 1 Lozenge 4-8 Hourly; Maximum 15 Per Day, Maximum Duration 24 Week`

- **Source:** Section 12: Appendices
- **Existing trigger string:** `None`
- **Evidence:** _NiQuitin®: 4mg: suitable for smokers who have their time to first cigarette is < 30 minutes after waking up. 2mg: suitable for smokers who have their time to first cigarette is > 30 minutes after waking up. Week 1-6: 1 lozenge 1-2 hourly. Min: 9 lozenge/day. Week 7-9: 1 lozenge 2-4 hourly. Week 10-12: 1 lozenge 4-8 hourly. Max: 15 lozenge/day. Max duration: 24 wk_
- **Extracted:** `time to first cigarette < 30 minutes`  (negated=False)
- **Rationale:** The text specifies a threshold of < 30 minutes for smokers to be suitable for the 4mg lozenge.
- **edge_id:** `5:94ea5408-46d3-403a-a3d2-6b09bcc86e92:1152928101676621823`

- [ ] Approve  [ ] Edit  [ ] Reject

### HAS_DOSAGE #12: `Isotonic Saline` → `10 - 20 Ml/Kg Over 1 - 2 Hour`

- **Source:** Section 6: Diabetic Ketoacidosis
- **Existing trigger string:** `None`
- **Evidence:** _Infuse 10 - 20 ml/kg of isotonic saline over 1 - 2 hours._
- **Extracted:** `dose between 10..20 ml/kg`  (negated=False)
- **Rationale:** Text specifies a numeric dosage range for isotonic saline infusion.
- **edge_id:** `5:94ea5408-46d3-403a-a3d2-6b09bcc86e92:6917535624710858970`

- [ ] Approve  [ ] Edit  [ ] Reject

---

## Summary

- WRITE (would be merged): 49
- Gated by confidence:     14
- Skipped (no threshold):  37
- Errors:                  0