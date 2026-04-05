import os
import re

INPUT_FILE = r'c:\Documents\CPG\CPG markdown\CPG-LLM-Agentic-RAG-Knowledge-Graph-main\markdown\8 Primary & Secondary Prevention of CVD 2017.md'
OUTPUT_DIR = r'c:\Documents\CPG\CPG markdown\CPG-LLM-Agentic-RAG-Knowledge-Graph-main\markdown\Primary-and-Secondary-Prevention-of-CVD'

def get_metadata(section_name):
    return f"""<!--
category: "internal medicine"
use_case: "RAG"
patient_input: "null"
output: "{section_name}"
-->

# {section_name.upper()}

"""

# Define sections with their regex markers
SECTIONS = [
    (0, "Summary and Table of Contents", "section-0-summary.md", r"^## CONTENTS|^SUMMARY"),
    (1, "Introduction", "section-1-introduction.md", r"^## 1\. Introduction"),
    (2, "Prevention of CVD", "section-2-prevention.md", r"^## 2\. PREVENTION OF CVD"),
    (3, "Estimation of Global Cardiovascular Risk", "section-3-risk-estimation.md", r"^## 3\. ESTIMATION OF GLOBAL"),
    (4, "Types of CVD", "section-4-types-of-cvd.md", r"^## 4\. TYPES OF CVD"),
    (5, "Risk Factors for CVD", "section-5-risk-factors.md", r"^## 5\. RISK FACTORS"),
    (6, "Other Conditions Associated with Increased CV Risk", "section-6-other-conditions.md", r"^## 6\. OTHER CONDITIONS"),
    (7, "Other Risk Markers of CVD", "section-7-risk-markers.md", r"^## 7\. OTHER RISK MARKERS"),
    (8, "Interventions to Prevent CVD", "section-8-interventions.md", r"^## 8\. INTERVENTIONS TO PREVENT"),
    (9, "Management of Individual Risk Factors", "section-9-management-risk-factors.md", r"^## 9\. MANAGEMENT OF INDIVIDUAL"),
    (10, "Adherence to Therapy", "section-10-adherence.md", r"^## 10\. ADHERENCE TO THERAPY"),
    (11, "Community, Population and Governmental Level", "section-11-community-governmental.md", r"^## 11\. COMMUNITY"),
    (12, "Traditional and Complementary Medicine", "section-12-tcm.md", r"^## 12\. TRADITIONAL"),
    (13, "Miscellaneous FAQ and Myths", "section-13-faq-myths.md", r"^## 13\. MISCELLANEOUS"),
    (14, "Monitoring and Quality Assurance", "section-14-monitoring.md", r"^## 14\. MONITORING"),
    (15, "References", "references.md", r"^## REFERENCES"),
    (16, "Acknowledgments and Disclosure", "appendix.md", r"^## ACKNOWLEDGMENTS")
]

def main():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    full_doc = "".join(lines)
    
    # 1. Extract Universal Context (Precise Extraction)
    def extract_block(pattern):
        match = re.search(pattern, full_doc, re.DOTALL | re.IGNORECASE)
        if match:
            # Clean up consecutive images or page numbers if needed
            return match.group(0).strip()
        return ""

    # Table 3: Risk Stratification
    table3_match = re.search(r'## Table 3: Risk Stratification of Cardiovascular.*?\n(.*?)(?=\n\n|\n## |\nTable 4|\Z)', full_doc, re.DOTALL | re.IGNORECASE)
    table3 = table3_match.group(0).strip() if table3_match else "Risk Stratification Table not found."
    
    # Table 4: Targets
    table4_match = re.search(r'Table 4: Targets of Individual Risk Factors.*?\n(.*?)(?=\n\n|\n## |\nTable 5|\Z)', full_doc, re.DOTALL | re.IGNORECASE)
    table4 = table4_match.group(0).strip() if table4_match else "Targets Table not found."
    
    # Abbreviations
    abbr_match = re.search(r'## ABBREVIATIONS.*?\n(.*?)(?=\n\n## RATIONALE|\n## 1\.|\Z)', full_doc, re.DOTALL | re.IGNORECASE)
    abbreviations = abbr_match.group(0).strip() if abbr_match else ""

    print(f"DEBUG: Table 3 found: {len(table3)} chars")
    print(f"DEBUG: Table 4 found: {len(table4)} chars")
    print(f"DEBUG: Abbr found: {len(abbreviations)} chars")

    universal_context = f"\n\n--- \n\n> **OVERLAPPING UNIVERSAL CONTEXT FOR RAG:**\n\n{abbreviations}\n\n{table3}\n\n{table4}\n"

    # 2. Split Sections
    file_contents = {val[0]: [] for val in SECTIONS}
    current_section = 0
    seen_sections = set()

    for line in lines:
        stripped = line.strip()
        matched = False
        for sec_num, sec_title, filename, regex in SECTIONS:
            if re.match(regex, stripped, re.IGNORECASE):
                # Ensure it's a real header match
                if (stripped.startswith("##") or "CONTENTS" in stripped or "SUMMARY" in stripped) and sec_num not in seen_sections:
                    current_section = sec_num
                    seen_sections.add(sec_num)
                    matched = True
                    break
        
        file_contents[current_section].append(line)

    # 3. Save Files
    for sec_num, sec_title, filename, regex in SECTIONS:
        content = "".join(file_contents[sec_num])
        if not content:
            continue

        # Add metadata
        filepath = os.path.join(OUTPUT_DIR, filename)
        
        # Append Overlapping Context to management and intervention sections (8-14)
        # Plus section 3 and 5 as they are foundational
        if sec_num in [3, 5, 8, 9, 10, 11, 12, 13, 14]:
            final_content = get_metadata(sec_title) + content + universal_context
        else:
            final_content = get_metadata(sec_title) + content

        with open(filepath, 'w', encoding='utf-8') as sf:
            sf.write(final_content)

    print(f"Successfully split and overlapped {len(seen_sections)} sections.")

if __name__ == "__main__":
    main()
