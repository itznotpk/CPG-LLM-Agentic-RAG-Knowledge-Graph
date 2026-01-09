# Malaysia CPG: Erectile Dysfunction - RAG Optimized
> **Source**: Clinical Practice Guidelines on Management of Erectile Dysfunction (2024)
> **Publisher**: Malaysian Health Technology Assessment Section (MaHTAS), Ministry of Health Malaysia
> **Optimized for**: RAG-based care plan generation

---

# SECTION 1: CLINICAL DECISION ALGORITHMS

## ALGORITHM 1: DIAGNOSIS AND TREATMENT OF ED

<!-- METADATA
category: algorithm
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



# SECTION 2: KEY RECOMMENDATIONS (Evidence-Based)

<!-- METADATA
category: recommendations
evidence_grade: high
use_case: care_plan_generation
-->

## Diagnosis & Assessment

| Recommendation | Grade |
|----------------|-------|
| Comprehensive medical, psychosocial, and sexual history in EVERY ED patient | **Strong** |
| Use validated questionnaire (IIEF-5) to assess all sexual function domains | **Strong** |
| Focused physical examination to identify underlying conditions | **Strong** |
| Routine laboratory tests to identify modifiable risk factors | **Strong** |
| Cardiac risk assessment in ALL ED patients (and vice versa) | **Strong** |

## Treatment

| Recommendation | Grade |
|----------------|-------|
| Advise ALL ED patients on lifestyle and risk factor modifications | **Strong** |
| Offer PDE5i to ALL patients unless contraindicated | **Strong** |
| Mechanical devices (VED, shockwave) may be offered | Conditional |
| Li-ESWT should be performed by urologists only (mild-moderate ED) | **Strong** |
| Penile prosthesis for patients who failed other interventions | Conditional |
| Integrated psychological interventions should be considered | Conditional |

---

# SECTION 3: PHARMACOLOGICAL TREATMENT

<!-- METADATA
category: treatment
treatment_type: pharmacological
use_case: medication_selection
-->

## PDE5 Inhibitors - Comparison Table

| Drug | Onset | Duration | Initial Dose | Max Dose | Best For |
|------|-------|----------|--------------|----------|----------|
| **Sildenafil** | 30-60 min | Up to 12h | 50 mg | 100 mg | On-demand use |
| **Tadalafil** | 30 min | Up to 36h | 10 mg (on-demand) or 2.5 mg (daily) | 20 mg (on-demand) or 5 mg (daily) | Frequent intercourse, BPH+ED |
| **Avanafil** | 15 min | 6+ hours | 100 mg | 200 mg | Rapid onset needed |
| **Vardenafil** | 30 min | 4-5h | 10 mg | 20 mg | *Not registered in Malaysia* |

## CONTRAINDICATIONS (Critical Safety)

<!-- METADATA
category: contraindication
critical: true
use_case: medication_safety_check
-->

### Absolute Contraindications for PDE5i

| Contraindication | Reason | Alternative |
|------------------|--------|-------------|
| **Nitrates** (any form) | Severe hypotension risk | ICI, VED, or surgical |
| **Riociguat** | Severe hypotension risk | ICI, VED, or surgical |
| **Hypersensitivity** to PDE5i | Allergic reaction | Different PDE5i or alternative class |

### Cautions (Use with Care)

| Condition | Precaution |
|-----------|------------|
| Alpha-blockers | Start sildenafil at 25 mg |
| CYP3A4 inhibitors | Reduce PDE5i dose |
| Severe renal impairment (CrCl <30) | Start sildenafil at 25 mg |
| Hepatic impairment | Start at lowest dose |
| History of NAION | Use with caution, discuss risks |
| Predisposition to priapism | Monitor closely |

### Drug-Nitrate Washout Periods

| PDE5i | Time before nitrate can be given |
|-------|----------------------------------|
| Sildenafil | 24 hours |
| Tadalafil | 48 hours |
| Avanafil | 12 hours |

## Common Adverse Events

| AE | Sildenafil | Tadalafil | Avanafil |
|----|------------|-----------|----------|
| Headache | ✓ | ✓ | ✓ |
| Flushing | ✓ | ✓ (less) | ✓ |
| Dyspepsia | ✓ | ✓ | ✓ |
| Nasal congestion | ✓ | ✓ | ✓ |
| Back pain/Myalgia | Less | ✓ (more) | Less |
| Visual disturbances | ✓ | Less | Less |

---

# SECTION 4: SPECIAL POPULATIONS

<!-- METADATA
category: special_population
use_case: patient_specific_guidance
-->

## Cardiac Disease Patients

| Condition | PDE5i Use | Notes |
|-----------|-----------|-------|
| Stable angina (mild) | Safe | Low cardiac risk |
| Post-MI (>6 weeks) | Safe | If no complications |
| Post-MI (2-6 weeks) | Stress test first | Intermediate risk |
| Post-MI (<2 weeks) | Defer | High risk |
| NYHA Class I-II | Safe | Low cardiac risk |
| NYHA Class III | Evaluate | Intermediate risk |
| NYHA Class IV | Defer | High risk |
| On nitrates | Contraindicated | Use alternative |

## Diabetic Patients

- **Prevalence**: 59.1% of diabetic men have ED
- **Management**: Optimize glycaemic control first
- **PDE5i efficacy**: Slightly lower than non-diabetics, may need higher doses
- **Consider**: Combination therapy

## Post-Prostatectomy

- **ED prevalence**: 25-100% post-radical prostatectomy
- **Recovery time**: Up to 48 months for erectile function recovery
- **Treatment**: PDE5i effective post nerve-sparing surgery
- **Recommendation**: Start penile rehabilitation early

## Spinal Cord Injury

| Treatment | Efficacy | Caution |
|-----------|----------|---------|
| PDE5i | Effective | May trigger autonomic dysreflexia |
| ICI | 82-100% | High AE rate (priapism, pain) |
| VED | 70-93% success | Cold penis sensation |
| Penile prosthesis | Up to 79% satisfaction | Avoid malleable (erosion risk) |

> ⚠️ **All treatments may trigger autonomic dysreflexia in SCI patients**

---

# SECTION 5: LIFESTYLE MODIFICATIONS

<!-- METADATA
category: treatment
treatment_type: lifestyle
use_case: non_pharmacological_intervention
-->

## Evidence-Based Lifestyle Interventions

| Intervention | Benefit | Evidence |
|--------------|---------|----------|
| **Aerobic exercise** (≥3x/week, ≥30 min) | Improves IIEF scores | Level I |
| **Weight loss** (BMI reduction) | Improves erectile function | Level I |
| **Mediterranean diet** | Reduces ED risk | Level II-2 |
| **Smoking cessation** | Improves ED regardless of pack-years | Level II-3 |
| **Alcohol abstinence** | Improves IIEF-5 after 3 months | Level II-2 |
| **Pelvic floor exercises** | 35-47% cure rate | Level II-3 |

---

# SECTION 6: REFERRAL CRITERIA

<!-- METADATA
category: referral
use_case: care_escalation
-->

## When to Refer

| Refer to | When |
|----------|------|
| **Urologist** | Severe ED (IIEF-5: 5-7), Treatment failure, Need for mechanical/surgical intervention, Young patient with trauma history |
| **Cardiologist** | High cardiac risk, Intermediate risk needing stress test, Unstable cardiac condition |
| **Endocrinologist** | Complex hormonal disorders, Hypogonadism |
| **Psychiatrist/Psychologist** | Psychogenic ED, Significant psychological factors, Depression/anxiety as primary cause |
| **Multidisciplinary** | Mixed ED with multiple comorbidities |

---

# SECTION 7: ASSESSMENT TOOLS

<!-- METADATA
category: assessment
use_case: severity_classification
-->

## IIEF-5 (International Index of Erectile Function - 5 item)

| Score | Interpretation |
|-------|----------------|
| 22-25 | No ED |
| 17-21 | Mild ED |
| 12-16 | Mild-Moderate ED |
| 8-11 | Moderate ED |
| 5-7 | Severe ED |

## Erection Hardness Score (EHS)

| Score | Description |
|-------|-------------|
| 0 | Penis does not enlarge |
| 1 | Penis is larger but not hard |
| 2 | Penis is hard but not enough for penetration |
| 3 | Penis is hard enough for penetration but not completely hard |
| 4 | Penis is completely hard and fully rigid |

---

# SECTION 8: MONITORING & FOLLOW-UP

<!-- METADATA
category: follow_up
use_case: care_plan_timeline
-->

## Follow-up Schedule

| Phase | Timing | Purpose |
|-------|--------|---------|
| **Initial** | 2-4 weeks | Assess response, tolerability |
| **Titration** | 4-8 weeks | Dose adjustment if needed |
| **Maintenance** | Every 3-6 months | Ongoing effectiveness, AE monitoring |
| **As needed** | Variable | For lifestyle modifications |

## What to Monitor

- IIEF-5 score changes
- Treatment adherence
- Adverse events
- Cardiovascular status
- Psychosocial impact
- Partner satisfaction

---

# APPENDIX: QUICK REFERENCE TABLES

## PDE5i Dose Adjustments

| Scenario | Sildenafil | Tadalafil |
|----------|------------|-----------|
| With alpha-blocker | Start 25 mg | Start 5 mg |
| With CYP3A4 inhibitor | Start 25 mg | Max 10 mg |
| CrCl <30 ml/min | Start 25 mg | Start 5 mg |
| Hepatic impairment | Start 25 mg | Max 10 mg |
| Elderly (>65 years) | Start 25 mg | No adjustment needed |

## Treatment Failure Algorithm

```
PDE5i FAILURE (after 4 attempts at max dose)
         ↓
    REASSESS
    • Correct usage? (timing, stimulation)
    • Correct dose?
    • Try different PDE5i
         ↓
    STILL FAILING?
         ↓
    ┌─────────────┐
    │             │
    ↓             ↓
 ADD VED    REFER TO
            UROLOGIST
              │
              ↓
         ┌────────────┐
         │            │
        ICI     PENILE PROSTHESIS
```

---

*Document optimized for RAG chunking and care plan generation*
*Last updated: January 2026*
