# SECTION 1: CLINICAL DECISION ALGORITHMS

## ALGORITHM 1: DIAGNOSIS AND TREATMENT OF ED

<!-- METADATA
category: algorithm
icd11_primary: HA01.1
icd11_related: HA00, HA00.0, HA00.1, HA00.2, HA00.3, HA00.Z, HA01, HA01.0, HA01.00, HA01.01, HA01.02, HA01.03, HA01.0Z, HA01.1, HA01.10, HA01.11, HA01.12, HA01.13, HA01.1Z, HA01.Y, HA01.Z, HA02, HA02.0, HA02.00, HA02.01, HA02.02, HA02.03, HA02.0Z, HA02.Y, HA02.Z, HA03, HA03.0, HA03.00, HA03.01, HA03.02, HA03.03, HA03.0Z, HA03.1, HA03.10, HA03.11, HA03.12, HA03.13, HA03.1Z, HA03.Y, HA03.Z, HA0Y, HA0Z
use_case: treatment_decision
patient_input: symptoms, IIEF-5_score
output: treatment_pathway
-->

### Overview
This algorithm outlines the clinical decision pathway for diagnosing and treating Erectile Dysfunction (ED).

---

### 📖 Glossary

| Term | Definition |
|------|------------|
| **ASCVD** | Atherosclerotic Cardiovascular Disease |
| **ED** | Erectile Dysfunction |
| **IIEF-5** | 5-item version of International Index of Erectile Function |
| **PDE5i** | Phosphodiesterase-5 inhibitors |
| **VED** | Vacuum Erection Device |

---

### Step 1: Initial Assessment

**Patient presents with symptoms of ED**

↓

#### History Taking & Examination
- **Medical history** (cardiovascular, diabetes, neurological)
- **Psychological history** (depression, anxiety, relationship issues)
- **Sexual history** (with partner involvement preferred)
- **Assessment using IIEF-5** (International Index of Erectile Function)
- **Focused physical examination**
- ± Laboratory investigation
- ± Imaging

↓

### Step 2: Diagnosis of ED

After assessment, classify the **Type of ED**:

| Type | Description |
|------|-------------|
| **Organic ED** | Physical/medical cause (vascular, hormonal, neurogenic) |
| **Psychogenic ED** | Psychological cause (anxiety, depression, relationship) |
| **Mixed ED** | Combination of organic and psychogenic factors |

> *Some cases may present with mixed ED. Categorize severity according to IIEF-5.

---

### Step 3: Severity Assessment (for Organic ED)

**Based on IIEF-5 Score:**

| Score | Severity |
|-------|----------|
| 22-25 | Normal |
| 17-21 | Mild |
| 12-16 | Mild-moderate |
| 8-11 | Moderate |
| 5-7 | Severe |

---

### Step 4: Treatment Pathways

#### Pathway A: Mild/Moderate ED (Score 8-21)
- Lifestyle modification
- ± Pharmacotherapy
- **If no improvement:** → Refer to urologist

#### Pathway B: Severe ED (Score 5-7)
**Refer to urologist:**
- Lifestyle modification + Pharmacotherapy
- ± Mechanical devices / Surgical intervention

#### Pathway C: Psychogenic ED
- Lifestyle modification
- ± Pharmacotherapy
- → Refer to mental health professionals

---

## ALGORITHM 2: CLASSIFICATION FOR ED PATIENTS WITH CARDIOVASCULAR DISEASE

<!-- METADATA
category: algorithm
icd11_primary: HA01.1
icd11_related: HA00, HA00.0, HA00.1, HA00.2, HA00.3, HA00.Z, HA01, HA01.0, HA01.00, HA01.01, HA01.02, HA01.03, HA01.0Z, HA01.1, HA01.10, HA01.11, HA01.12, HA01.13, HA01.1Z, HA01.Y, HA01.Z, HA02, HA02.0, HA02.00, HA02.01, HA02.02, HA02.03, HA02.0Z, HA02.Y, HA02.Z, HA03, HA03.0, HA03.00, HA03.01, HA03.02, HA03.03, HA03.0Z, HA03.1, HA03.10, HA03.11, HA03.12, HA03.13, HA03.1Z, HA03.Y, HA03.Z, HA0Y, HA0Z
use_case: cardiac_risk_stratification
patient_input: cardiac_history, exercise_ability, medications
output: treatment_safety_classification
critical: true
-->

### Overview

This algorithm classifies ED patients with cardiovascular disease for safe treatment selection.

> **Note:** If vasculogenic ED, perform ASCVD risk score assessment.

---

### Step 1: Starting Point

**Patients with confirmed ED**

↓

### Step 2: Exercise Ability Assessment<sup>a</sup>

Assess the patient's exercise ability to estimate cardiovascular risk.

↓

### Step 3: Cardiac Risk Stratification

**Cardiac risk stratification according to Princeton Consensus***

> *Refer to Table 1 for cardiac risk stratification for patients with ED based on 2nd and 3rd Princeton Consensus.

↓

Classify into one of three risk categories:

---

### Step 4: Risk-Based Pathways

#### Low Risk Pathway

**Low Risk** → Elective risk assessment (optional)

↓ (or optionally → **Stress test<sup>b</sup>** → if Pass → proceed below)

**For advice and treatment by primary team**

↓

Continue to Step 5 (Nitrate Assessment)

---

#### Intermediate Risk Pathway

**Intermediate Risk** → **Stress test<sup>b</sup>**

↓

| Test Result | Next Step |
|-------------|-----------|
| **Pass** | Reclassify as **Low Risk** → For advice and treatment by primary team |
| **Fail** | Reclassify as **High Risk** → For further cardiac assessment |

---

#### High Risk Pathway

**High Risk** → **For further cardiac assessment**

(Treatment deferred until cardiac condition stabilized)

---

### Step 5: Nitrate Assessment (After Risk Classification)

For patients cleared for treatment (Low Risk):

#### Decision: Is the patient prescribed nitrate/riociguat?

| Patient Status | Treatment Path |
|----------------|----------------|
| **No** (not on nitrates) | → **PDE5i** (phosphodiesterase-5 inhibitors) |
| **Yes** (on nitrates) | → Check: Is nitrate necessary? |

#### If on nitrates, is nitrate necessary?

| Answer | Treatment Path |
|--------|----------------|
| **Yes** (nitrate essential) | → **Non-PDE5i treatment** |
| **No** (nitrate can be stopped) | → **Consider stopping nitrate, then PDE5i** |

---

### Key Abbreviations

| Abbreviation | Meaning |
|--------------|---------|
| ASCVD | Atherosclerotic Cardiovascular Disease |
| ED | Erectile Dysfunction |
| PDE5i | Phosphodiesterase-5 Inhibitors |

---

### Footnotes

<sup>a</sup> **Exercise ability** is used to guide physician estimating cardiovascular risk associated with sexual activity and should be established before the initiation of ED treatment. Sexual activity is equivalent to:
- Walking 1.6 km (1 mile) on the flat in 20 minutes
- Briskly climbing two flights of stairs in 10 seconds

<sup>b</sup> **Stress test:** Sexual activity is equivalent to 4 minutes of the Bruce treadmill protocol. **Pass** is defined as completion of the test without symptoms, arrhythmias, or a fall in systolic blood pressure.

---