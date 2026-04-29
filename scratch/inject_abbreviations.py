import os
import re

abbrev_map = {
    "APR": "Abdominoperineal resection",
    "ASA": "Acetylsalicylic acid",
    "AUC": "Area under the curve",
    "BE": "Barium enema",
    "CC": "Conventional colonoscopy",
    "CCE": "Colon capsule endoscopy",
    "CCRT": "Concurrent chemoradiotherapy",
    "CEA": "Carcinoembryonic antigen",
    "CI": "Confidence interval",
    "CPG": "Clinical practice guidelines",
    "CRC": "Colorectal carcinoma",
    "CRM": "Circumferential resection margins",
    "CRLMs": "Colorectal liver metastases",
    "CT": "Computed tomography",
    "CTC": "Computed tomographic colonography",
    "DFS": "Disease-free survival",
    "DG": "Development Group",
    "DRM": "Distal resection margin",
    "DW-MRI": "Diffusion-weighted MRI",
    "EGFR": "Epidermal growth factor receptor",
    "FAP": "Familial adenomatous polyposis",
    "FDG PET/CT": "18F-fluorodeoxyglucose Positron Emission Tomography CT",
    "FDR": "First-degree relatives",
    "FOLFIRI": "5-FU/LV + irinotecan",
    "FOLFOX": "5-FU/LV + oxaliplatin",
    "FRR": "Familial relative risk",
    "5-FU": "Fluorouracil",
    "Gd-EOB-DTPA": "Gadolinium-ethoxybenzyl-diethylenetriaminepentaacetic acid",
    "Gy": "Gray (radiation unit)",
    "HNPCC": "Hereditary non-polyposis colorectal cancer",
    "HPE": "Histopathological examination",
    "HR": "Hazard ratio",
    "IBD": "Inflammatory bowel disease",
    "iFOBT": "Immunofaecal occult blood test",
    "IFOBT": "Immunofaecal occult blood test",
    "IHC": "Immunohistochemistry",
    "KRAS": "Kirsten rat sarcoma viral oncogene homolog",
    "LPLN": "Lateral pelvic lymph node",
    "LV": "Leucovorin",
    "MaHTAS": "Malaysian Health Technology Assessment Section",
    "MAP": "MUTYH-associated polyposis",
    "mCRC": "Metastatic colorectal carcinoma",
    "MDT": "Multidisciplinary team",
    "MMR": "Mismatch repair",
    "MoH": "Ministry of Health",
    "MRF": "Mesorectal fascia",
    "MRI": "Magnetic resonance imaging",
    "NICE": "National Institute for Health and Clinical Excellence",
    "NSAIDs": "Non-steroidal anti-inflammatory drugs",
    "OR": "Odds ratio",
    "OS": "Overall survival",
    "PFS": "Progression-free survival",
    "RC": "Review Committee",
    "RCT": "Randomised controlled trial",
    "RFA": "Radiofrequency ablation",
    "RR": "Relative risk",
    "RRR": "Relative risk ratio",
    "RT": "Radiotherapy",
    "SDR": "Second-degree relatives",
    "SIGN": "Scottish Intercollegiate Guidelines Network",
    "SIRT": "Selective internal radiation therapy",
    "TDR": "Third-degree relatives",
    "TME": "Total mesorectal excision",
    "TNM": "Tumour-Node-Metastasis",
    "TTP": "Time to progression",
    "UC": "Ulcerative colitis",
    "VC": "Virtual colonoscopy",
    "VTE": "Venous thromboembolism",
    "WHO": "World Health Organization"
}

target_dir = r"c:\Users\zhchua\Documents\Project (Comp)\CPG-LLM-Agentic-RAG-Knowledge-Graph\markdown\Colorectal-Carcinoma(2017)"
files = [f for f in os.listdir(target_dir) if f.endswith(".md") and f != "appendix-references-abbreviations.md"]

for filename in files:
    filepath = os.path.join(target_dir, filename)
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Identify used abbreviations
    # Use word boundaries to avoid matching parts of words
    found = []
    for abbrev, full in abbrev_map.items():
        if re.search(r'\b' + re.escape(abbrev) + r'\b', content):
            found.append((abbrev, full))
    
    if not found:
        continue
        
    found.sort()
    
    # Prepare the abbreviation section
    abbrev_text = "\n### Abbreviations\n\n"
    for abbrev, full in found:
        abbrev_text += f"* **{abbrev}** = {full}\n"
    abbrev_text += "\n"
    
    # Insert before the overlap section or at the end
    if "<!-- ============================================================ -->" in content:
        parts = content.split("<!-- ============================================================ -->")
        new_content = parts[0].rstrip() + "\n" + abbrev_text + "<!-- ============================================================ -->" + parts[1]
    else:
        new_content = content.rstrip() + "\n" + abbrev_text
        
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print(f"Updated {filename} with {len(found)} abbreviations.")
