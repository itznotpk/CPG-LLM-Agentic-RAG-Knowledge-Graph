# -*- coding: utf-8 -*-
"""
Split the Heart Failure (5th Edition) CPG into RAG-optimized section files.
Version 3: Uses exact line positions from debug run.
"""
import re, os, sys

# Fix encoding for Windows console
sys.stdout.reconfigure(encoding='utf-8')

INPUT_FILE = r"markdown\CPG Management of Heart Failure (5th Edition).md"
OUTPUT_DIR = r"markdown\Heart-Failure(5th Edition)"
os.makedirs(OUTPUT_DIR, exist_ok=True)

with open(INPUT_FILE, "r", encoding="utf-8") as f:
    raw = f.read()

# Clean
raw = raw.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')
raw = re.sub(r'\s*<!-- image -->\s*', '\n\n', raw)
raw = re.sub(r'\n\s*\d{1,3}(?:-\d{1,3})?\s*\n', '\n', raw)
raw = re.sub(r'\n{3,}', '\n\n', raw)

lines = raw.split('\n')
total = len(lines)
print(f"Total lines: {total}")

# ── Common content blocks for overlapping ──
TABLE8 = """### Table 8: Classification Of Heart Failure According To LVEF

| Ejection Fraction Terminology | LVEF |
|---|---|
| Heart Failure with Reduced Ejection Fraction (HFrEF) | ≤ 40% |
| Heart Failure with mildly reduced LVEF (HFmrEF) | 41-49% |
| Heart Failure with Preserved Ejection Fraction (HFpEF) | ≥ 50% |
| Heart Failure with Improved Ejection Fraction (HFimpEF) | HF with a baseline LVEF of ≤ 40%, a ≥10-point increase from baseline LVEF following treatment, and a second measurement of LVEF of > 40%. |
"""

TABLE9 = """### Table 9: New York Heart Association Functional Classification

| Class | Functional Capacity | 1-Year Mortality |
|---|---|---|
| **CLASS I** | No limitation. Ordinary physical activity does not cause undue fatigue, dyspnea or palpitation. | 5-10% |
| **CLASS II** | Slight limitation of physical activity. Comfortable at rest. Ordinary physical activity results in fatigue, palpitation, dyspnea or angina. | 10-15% |
| **CLASS III** | Marked limitation of physical activity. Comfortable at rest, but less than ordinary activity will lead to symptoms. | 15-20% |
| **CLASS IV** | Inability to carry on any physical activity without discomfort. Symptoms at rest. | 20-50% |
"""

STAGES = """### Stages of Heart Failure

| Stage | Description |
|---|---|
| **A - "At Risk"** | Asymptomatic without structural cardiac disease but 'at risk' of developing HF |
| **B - "Pre HF"** | Asymptomatic but with structural and functional cardiac abnormalities that can lead to HF |
| **C - "HF"** | Symptomatic HF, either previous or current symptoms |
| **D - "Advanced HF"** | Marked symptoms interfering with daily activities of living and with recurrent hospitalizations |
"""

GRADES = """## Grades of Recommendation and Level of Evidence

*   **Class I**: Evidence and/or general agreement that a given procedure or treatment is beneficial, useful, and effective.
*   **Class IIa**: Weight of evidence/opinion is in favour of usefulness/efficacy. *Should be considered*.
*   **Class IIb**: Usefulness/efficacy is less well established. *May be considered*.
*   **Class III**: Evidence and/or general agreement that a procedure/treatment is not useful/effective and in some cases may be harmful.
*   **Level A**: Data from multiple randomized clinical trials or meta-analyses.
*   **Level B**: Data from a single randomized clinical trial or large non-randomized studies.
*   **Level C**: Consensus of opinion of experts, case studies, or standard-of-care.
"""

ABBREV = """## Abbreviations Used in This Section

| Abbreviation | Description |
|---|---|
| ACE-I | Angiotensin Converting Enzyme Inhibitor |
| AF | Atrial Fibrillation |
| ARB | Angiotensin Receptor Blocker |
| ARNI | Angiotensin Receptor-Neprilysin Inhibitor |
| BNP | B-type Natriuretic Peptide |
| BP | Blood Pressure |
| CAD | Coronary Artery Disease |
| CKD | Chronic Kidney Disease |
| CRT | Cardiac Resynchronization Therapy |
| CV | Cardiovascular |
| CVD | Cardiovascular Disease |
| DM | Diabetes Mellitus |
| ECG | Electrocardiogram |
| eGFR | Estimated Glomerular Filtration Rate |
| HF | Heart Failure |
| HFimpEF | HF with Improved Ejection Fraction |
| HFmrEF | HF with Mildly Reduced Ejection Fraction |
| HFpEF | HF with Preserved Ejection Fraction |
| HFrEF | HF with Reduced Ejection Fraction |
| ICD | Implantable Cardioverter Defibrillator |
| IV | Intravenous |
| LV | Left Ventricular |
| LVEF | Left Ventricular Ejection Fraction |
| MACE | Major Adverse Cardiovascular Events |
| MCS | Mechanical Circulatory Support |
| MI | Myocardial Infarction |
| MRA | Mineralocorticoid Receptor Antagonist |
| NT-proBNP | N-terminal pro-B-type Natriuretic Peptide |
| NYHA | New York Heart Association |
| PPCM | Peripartum Cardiomyopathy |
| SGLT2-i | Sodium-Glucose Cotransporter-2 Inhibitor |
| VHD | Valvular Heart Disease |
"""

def extract(start, end):
    """Extract lines[start:end] as cleaned text."""
    t = '\n'.join(lines[start:end])
    t = re.sub(r'\n{3,}', '\n\n', t).strip()
    return t

def write_section(filename, title, meta, content, overlaps=None):
    """Write a formatted section file."""
    header = f"""# {title}

<!-- METADATA
category: {meta[0]}
use_case: {meta[1]}
patient_input: {meta[2]}
output: {meta[3]}
-->

"""
    overlap_text = ""
    if overlaps:
        overlap_text = "\n\n---\n\n## Contextual Anchors (Overlapping)\n\n" + "\n---\n\n".join(overlaps)
    
    full = header + content + overlap_text + "\n\n---\n\n" + ABBREV + "\n\n---\n\n" + GRADES + "\n"
    
    path = os.path.join(OUTPUT_DIR, filename)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(full)
    kb = len(full.encode('utf-8')) / 1024
    print(f"  {filename} ({kb:.1f} KB)")

# ── Now find exact positions by scanning ──
def find(pattern, start=0):
    p = re.compile(pattern, re.IGNORECASE)
    for i in range(start, total):
        if p.search(lines[i]):
            return i
    return total

# Find key positions
pos = {}
pos['table8'] = find(r'Table 8.*Classification|Classification Of Heart Failure According To LVEF')
pos['s1'] = find(r'^## 1\. INTRODUCTION')
pos['s2'] = pos['table8'] - 10  # approximate boundary
pos['s3'] = pos['table8']
pos['s4'] = find(r'^## 4\. PATHOPHYSIOLOGY')
pos['s5'] = find(r'^## 5\. ETIOLOGY')
pos['s6'] = find(r'^## 6\. DIAGNOSIS')
pos['s7'] = find(r'^## 7\. PREVENTION')
pos['s8'] = find(r'^## 8\. NON-PHARMACOLOGICAL')
pos['s9'] = find(r'^## 9\. ACUTE HEART FAILURE')
pos['s10'] = find(r'^## 10\. CHRONIC HEART FAILURE')
pos['s10_1'] = find(r'^## 10\.1\s', pos.get('s10', 0))
pos['s10_2'] = find(r'^## 10\.2\s', pos.get('s10', 0))
pos['s11'] = find(r'MILDLY REDUCED.*EJECTION.*HFmrEF', pos.get('s10', 0) + 100)
pos['s12'] = find(r'IMPROVED.*EJECTION.*HFimpEF', pos.get('s11', 0) + 10)
pos['s13'] = find(r'PRESERVED.*SYSTOLIC|HFpEF.*LVEF.*50', pos.get('s12', 0) + 10)
pos['s14'] = find(r'^## 14\.\s|SPECIAL GROUPS', pos.get('s13', 0) + 10)
pos['s14_4'] = find(r'ARRHYTHMIAS.*CONDUCTION|14\.4', pos.get('s14', 0) + 100)
pos['s14_5'] = find(r'CARDIO-ONCOLOGY|14\.5', pos.get('s14_4', 0) + 10)
pos['s14_6'] = find(r'CHRONIC KIDNEY DISEASE|14\.6', pos.get('s14_5', 0) + 10)
pos['s14_7'] = find(r'^## 14\.7', pos.get('s14_6', 0) + 10)
pos['s14_8'] = find(r'^## 14\.8', pos.get('s14_7', 0) + 10)
pos['s14_9'] = find(r'^## 14\.9', pos.get('s14_8', 0) + 10)
pos['s15'] = find(r'^## 15\.\s|ADVANCED HEART FAILURE', pos.get('s14_9', 0) + 10)
pos['s16'] = find(r'^## 16\.\s|REHABILITATION', pos.get('s15', 0) + 10)
pos['s17'] = find(r'ORGANISATION OF CARE|^## 17', pos.get('s16', 0) + 10)
pos['s18'] = find(r'^## 18\.\s|OTHER THERAPIES', pos.get('s17', 0) + 10)
pos['s19'] = find(r'^## 19\.\s|PERFORMANCE MEASURES', pos.get('s18', 0) + 10)
pos['appendix'] = find(r'Appendix\s+I', pos.get('s19', 0) + 10)
pos['refs'] = find(r'^## REFERENCES', pos.get('appendix', 0))

print("\nSection positions found:")
for k, v in pos.items():
    snippet = lines[v][:80] if v < total else "END"
    print(f"  {k}: line {v} -> {snippet}")

# ── Extract & Write Sections ──
print("\nWriting sections...")

# Section 1: Introduction
content = extract(pos['s1'], pos['s2'])
write_section("section-1-introduction.md",
    "SECTION 1: INTRODUCTION & EPIDEMIOLOGY",
    ("Introduction", "Background Information", "", "HF epidemiology, socioeconomic burden"),
    content)

# Section 2: Definition
content = extract(pos['s2'], pos['s3'])
write_section("section-2-definition.md",
    "SECTION 2: DEFINITION",
    ("Introduction", "Definition", "", "Definition of Heart Failure"),
    content)

# Section 3: Classification
content = extract(pos['s3'], pos['s4'])
write_section("section-3-classification.md",
    "SECTION 3: CLASSIFICATION",
    ("Classification", "Staging and Classification", "LVEF, Symptoms", "Classification, NYHA staging, Stages of HF"),
    content, [TABLE8, TABLE9, STAGES])

# Section 4: Pathophysiology
content = extract(pos['s4'], pos['s5'])
write_section("section-4-pathophysiology.md",
    "SECTION 4: PATHOPHYSIOLOGY",
    ("Pathophysiology", "Disease Mechanism", "", "HFrEF, HFpEF, HFmrEF, HFimpEF pathophysiology"),
    content, [TABLE8])

# Section 5: Etiology
content = extract(pos['s5'], pos['s6'])
write_section("section-5-etiology.md",
    "SECTION 5: ETIOLOGY",
    ("Etiology", "Cause Identification", "Patient history, risk factors", "Causes of HF, decompensation factors (CHAMPION mnemonic)"),
    content)

# Section 6: Diagnosis
content = extract(pos['s6'], pos['s7'])
write_section("section-6-diagnosis.md",
    "SECTION 6: DIAGNOSIS",
    ("Diagnosis", "Clinical Assessment", "Symptoms, signs, ECG, BNP/NT-proBNP, echocardiogram", "Diagnostic criteria, Framingham criteria, investigations"),
    content, [TABLE8, TABLE9, STAGES])

# Section 7: Prevention
content = extract(pos['s7'], pos['s8'])
write_section("section-7-prevention.md",
    "SECTION 7: PREVENTION",
    ("Prevention", "Risk Factor Management", "HTN, DM, obesity, smoking, family history", "Stage A & B prevention strategies"),
    content, [STAGES])

# Section 8: Non-Pharmacological
content = extract(pos['s8'], pos['s9'])
write_section("section-8-non-pharmacological.md",
    "SECTION 8: NON-PHARMACOLOGICAL MEASURES",
    ("Management", "Lifestyle Intervention", "Lifestyle, diet, fluid intake, exercise capacity", "Education, exercise, diet, fluid restriction, weight monitoring"),
    content, [TABLE9])

# Section 9: Acute HF
content = extract(pos['s9'], pos['s10'])
write_section("section-9-acute-heart-failure.md",
    "SECTION 9: ACUTE HEART FAILURE",
    ("Management", "Acute Management", "Acute presentation, hemodynamics, congestion status", "Acute HF phases, diuretics, vasodilators, inotropes, discharge planning"),
    content, [TABLE8, TABLE9])

# Section 10: Chronic HFrEF
content = extract(pos['s10'], pos['s11'])
write_section("section-10-chronic-hfref.md",
    "SECTION 10: CHRONIC HF - HFrEF (LVEF <40%)",
    ("Management", "Pharmacological Treatment HFrEF", "LVEF <40%, BP, HR, renal function, potassium", "Foundational HF medications: ACEi/ARB/ARNI, beta-blockers, MRA, SGLT2i, device therapy"),
    content, [TABLE8, TABLE9])

# Section 11: HFmrEF
content = extract(pos['s11'], pos['s12'])
write_section("section-11-hfmref.md",
    "SECTION 11: HFmrEF (LVEF 41-49%)",
    ("Management", "HFmrEF Management", "LVEF 41-49%", "Management approach for mildly reduced EF"),
    content, [TABLE8])

# Section 12: HFimpEF
content = extract(pos['s12'], pos['s13'])
write_section("section-12-hfimpef.md",
    "SECTION 12: HFimpEF (Improved Ejection Fraction)",
    ("Management", "HFimpEF Management", "Baseline LVEF <40% improved to >40%", "Continuation of therapy, monitoring, relapse risk"),
    content, [TABLE8])

# Section 13: HFpEF
content = extract(pos['s13'], pos['s14'])
write_section("section-13-chronic-hfpef.md",
    "SECTION 13: CHRONIC HF - HFpEF (LVEF >50%)",
    ("Management", "Pharmacological Treatment HFpEF", "LVEF >50%, comorbidities", "HFpEF management, diuretics, SGLT2i, comorbidity management"),
    content, [TABLE8, TABLE9])

# Section 14.1-14.3: Diabetes, VHD, Cardiomyopathy
content = extract(pos['s14'], pos['s14_4'])
write_section("section-14-1-diabetes-vhd-cardiomyopathy.md",
    "SECTION 14.1-14.3: HF AND DIABETES, VALVULAR HEART DISEASE, CARDIOMYOPATHY",
    ("Special Groups", "Comorbidity Management", "Diabetes, VHD type, cardiomyopathy type", "SGLT2i in diabetes, valve intervention criteria, DCM/HCM/RCM management"),
    content, [TABLE8])

# Section 14.4-14.5: Arrhythmias, Cardio-Oncology
content = extract(pos['s14_4'], pos['s14_6'])
write_section("section-14-2-arrhythmias-oncology.md",
    "SECTION 14.4-14.5: HF AND ARRHYTHMIAS, CARDIO-ONCOLOGY",
    ("Special Groups", "Arrhythmia and Oncology", "Arrhythmia type, cancer treatment history", "Arrhythmia-induced cardiomyopathy, AF management, cardiotoxicity protocols"),
    content)

# Section 14.6: CKD
content = extract(pos['s14_6'], pos['s14_7'])
write_section("section-14-6-ckd.md",
    "SECTION 14.6: HF AND CHRONIC KIDNEY DISEASE",
    ("Special Groups", "CKD Management", "eGFR, creatinine, potassium, dialysis status", "Cardio-renal syndrome, drug dosing in CKD, dialysis considerations"),
    content)

# Section 14.7: Pregnancy
content = extract(pos['s14_7'], pos['s14_8'])
write_section("section-14-7-pregnancy.md",
    "SECTION 14.7: HF AND PREGNANCY",
    ("Special Groups", "Pregnancy Management", "Pregnancy status, cardiac condition, NYHA class", "Risk stratification, safe medications, PPCM management"),
    content)

# Section 14.8: COVID-19
content = extract(pos['s14_8'], pos['s14_9'])
write_section("section-14-8-covid.md",
    "SECTION 14.8: CORONAVIRUS 2019 (COVID 19) AND HEART FAILURE",
    ("Special Groups", "COVID-19 Management", "COVID history, vaccination", "COVID-19 cardiac effects, myocarditis"),
    content)

# Section 14.9: ACHD
content = extract(pos['s14_9'], pos['s15'])
write_section("section-14-9-achd.md",
    "SECTION 14.9: HEART FAILURE IN ADULT CONGENITAL HEART DISEASE (ACHD)",
    ("Special Groups", "ACHD Management", "congenital heart disease type", "ACHD-HF management, diagnosis, pathophysiology"),
    content)

# Section 15: Advanced HF
content = extract(pos['s15'], pos['s16'])
write_section("section-15-advanced-hf.md",
    "SECTION 15: ADVANCED HEART FAILURE",
    ("Management", "Advanced/End-Stage HF", "Refractory symptoms, NYHA III-IV, recurrent hospitalizations", "Heart transplant, MCS, palliative care, end-of-life planning"),
    content, [TABLE9])

# Section 16: Rehabilitation
content = extract(pos['s16'], pos['s17'])
write_section("section-16-rehabilitation.md",
    "SECTION 16: HF REHABILITATION",
    ("Rehabilitation", "Exercise and Rehabilitation", "Functional capacity, exercise tolerance", "Cardiac rehabilitation, exercise prescription, special populations"),
    content, [TABLE9])

# Section 17: Organisation
content = extract(pos['s17'], pos['s18'])
write_section("section-17-organisation-of-care.md",
    "SECTION 17: ORGANISATION OF CARE",
    ("Organisation", "Care Coordination", "", "HF clinics, follow-up schedules, referral criteria, telemedicine"),
    content)

# Section 18-19: Other Therapies & Performance
content = extract(pos['s18'], pos['appendix'])
write_section("section-18-other-therapies-performance.md",
    "SECTION 18-19: OTHER THERAPIES & PERFORMANCE MEASURES",
    ("Other", "Complementary Therapies and Quality Indicators", "", "EECP, stem cell therapy, supplements, performance measures"),
    content)

# Appendix
content = extract(pos['appendix'], pos['refs'])
write_section("appendix.md",
    "APPENDICES",
    ("Appendix", "Reference Tables and Flowcharts", "", "Drug dosing tables, flowcharts, WHO risk classification, NYHA classification"),
    content, [TABLE8, TABLE9, STAGES])

print(f"\nDone! All files written to: {OUTPUT_DIR}")

# List output
for f in sorted(os.listdir(OUTPUT_DIR)):
    fp = os.path.join(OUTPUT_DIR, f)
    sz = os.path.getsize(fp)
    print(f"  {f} ({sz/1024:.1f} KB)")
