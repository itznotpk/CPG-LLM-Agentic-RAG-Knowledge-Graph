import os
import re

INPUT_FILE = r'c:\Documents\CPG\CPG markdown\CPG-LLM-Agentic-RAG-Knowledge-Graph-main\markdown\7 Stable Coronary Artery Disease (2nd Edition).md'
OUTPUT_DIR = r'c:\Documents\CPG\CPG markdown\CPG-LLM-Agentic-RAG-Knowledge-Graph-main\markdown\Stable-Coronary-Artery-Disease(2nd Edition)'

def get_metadata(section_name):
    return f"""<!--
category: "internal medicine"
use_case: "RAG"
patient_input: "null"
output: "{section_name}"
-->

# {section_name.upper()}

"""

SECTIONS = [
    (1, "Introduction", "section-1-introduction.md", r"^## 1\.\s+INTRODUCTION"),
    (2, "Clinical Spectrum of Stable CAD", "section-2-clinical-spectrum.md", r"^## 2\.\s+CLINICAL SPECTRUM"),
    (3, "Pathophysiology", "section-3-pathophysiology.md", r"^## 3\.\s+PATHOPHYSIOLOGY"),
    (4, "Natural History and Prognosis", "section-4-natural-history.md", r"^## 4\.\s+NATURAL HISTORY"),
    (5, "Diagnosis of CAD - Basic Assessment", "section-5-diagnosis-basic.md", r"^## 5\.\s+DIAGNOSIS OF CAD"),
    (6, "Other Non-Invasive Investigations", "section-6-diagnosis-non-invasive.md", r"^## 6\.\s+OTHER NON-INVASIVE"),
    (7, "Risk Stratification", "section-7-risk-stratification.md", r"^## 7\.\s+RISK STRATIFICATION"),
    (8, "Management", "section-8-management.md", r"^## 8\.\s+MANAGEMENT"),
    (9, "Chronic Refractory Angina", "section-9-chronic-refractory-angina.md", r"^## 9\.\s+CHRONIC REFRACTORY"),
    (10, "Special Groups", "section-10-special-groups.md", r"^## 10\.\s+SPECIAL GROUPS"),
    (11, "Follow-Up", "section-11-follow-up.md", r"^## 11\.\s+FOLLOW-UP"),
    (12, "Pre-Operative Assessment", "section-12-pre-operative.md", r"^## 12\.\s+PRE-OPERATIVE"),
    (13, "Monitoring and Quality Assurance", "section-13-monitoring.md", r"^## 13\.\s+MONITORING"),
    (14, "References", "references.md", r"^## REFERENCES"),
    (15, "Acknowledgments and Appendices", "appendix.md", r"^## ACKNOWLEDGMENTS|^## MEMBERS OF THE EXPERT PANEL")
]

def main():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    current_section = 0
    file_contents = {0: []}  
    seen_sections = set()
    
    for line in lines:
        for sec_num, sec_title, filename, regex in SECTIONS:
            if re.match(regex, line.strip(), re.IGNORECASE):
                if line.strip().startswith("##") and sec_num not in seen_sections: 
                    current_section = sec_num
                    seen_sections.add(sec_num)
                    if current_section not in file_contents:
                        file_contents[current_section] = []
                    break
        
        file_contents[current_section].append(line)

    sec_strings = {k: "".join(v) for k, v in file_contents.items()}
    full_doc = "".join(lines)
    
    # Extract EXACT Tables
    def get_table(tbl_regex):
        m = re.search(tbl_regex, full_doc, re.DOTALL | re.IGNORECASE)
        # return a small chunk (say 2000 chars) near the match to avoid matching till the end of doc
        if m:
            text = m.group(1)
            # Find probable end of table
            end_match = re.search(r'(?:\n\n[^\n|]+\n\n|Table \d+:)', text[100:])
            if end_match:
                return text[:100+end_match.start()].strip()
            return text[:3000].strip()
        return ""

    table1 = get_table(r'(Table 1: Pre-Test Probability.*?)(?=Table 2:|## |\Z)')
    table4 = get_table(r'(Table 4: Canadian Cardiovascular Society.*?)(?=Table 5:|## |\Z)')
    table6 = get_table(r'(Table 6: Sensitivity and Specificity.*?)(?=Table 7:|## |\Z)')
    
    diagnostic_context = f"\n\n--- \n\n> **OVERLAPPING DIAGNOSTIC & RISK CONTEXT FOR RAG:**\n\n{table1}\n\n{table4}\n\n{table6}\n"

    # Extract Medication Context tightly
    pharm_match = re.search(r'(8\.2 Pharmacological therapy.*?)(?=8\.3 Myocardial revascularization|## 8\.3)', full_doc, re.DOTALL | re.IGNORECASE)
    pharm_context = pharm_match.group(1).strip() if pharm_match else "Pharmacological Guidelines missing."
    med_context = f"\n\n--- \n\n> **OVERLAPPING PHARMACOLOGICAL CONTEXT FOR RAG:**\n\n{pharm_context}\n"
    
    diagnostic_files = [2, 8, 9, 10, 11, 12]  
    medication_files = [5, 6, 7, 9, 10, 11]  

    for sec_num, content_str in sec_strings.items():
        if sec_num == 0:
            filename = "section-0-summary.md"
            title = "Summary and Table of Contents"
        else:
            match = next((item for item in SECTIONS if item[0] == sec_num), None)
            if match:
                _, title, filename, _ = match
            else:
                title = f"Section {sec_num}"
                filename = f"section-{sec_num}.md"
                
        if sec_num in diagnostic_files:
            content_str += diagnostic_context
        if sec_num in medication_files:
            content_str += med_context
            
        filepath = os.path.join(OUTPUT_DIR, filename)
        with open(filepath, 'w', encoding='utf-8') as sf:
            sf.write(get_metadata(title))
            sf.write(content_str)
            
    print("Files cleanly split with precise overlaps applied.")

if __name__ == "__main__":
    main()
