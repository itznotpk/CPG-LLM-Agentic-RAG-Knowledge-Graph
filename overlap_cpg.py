import os
import re

OUTPUT_DIR = r'c:\Documents\CPG\CPG markdown\CPG-LLM-Agentic-RAG-Knowledge-Graph-main\markdown\Hypertension(5th Edition)'

def get_file_content(filename):
    with open(os.path.join(OUTPUT_DIR, filename), 'r', encoding='utf-8') as f:
        return f.read()

def append_to_file(filename, content):
    with open(os.path.join(OUTPUT_DIR, filename), 'a', encoding='utf-8') as f:
        f.write("\n\n" + content)

def main():
    sec1 = get_file_content("section-1-epidemiology-definition-classification.md")
    sec3 = get_file_content("section-3-diagnosis-initial-assessment.md")
    sec9 = get_file_content("section-9-types-of-agents.md")
    appendix = get_file_content("appendix.md")
    
    # Extract Table 1-A and 1-B
    t1_match = re.search(r'(TABLE 1-A Classification.*?)(?=## 1\.1)', sec1, re.DOTALL)
    table_1 = t1_match.group(1).strip() if t1_match else ""
    
    # Extract Table 3-C and 3-D
    t3_match = re.search(r'(TABLE 3-C Co-existing Cardiovascular Risk.*?)(?=## 3\.E|TABLE 3-E)', sec3, re.DOTALL)
    table_3 = t3_match.group(1).strip() if t3_match else ""
    if not table_3:
        # Fallback to general block
        t3_match = re.search(r'(TABLE 3-C Co-existing Cardiovascular Risk.*?)(?=## RECOMMENDATIONS|## SUMMARY)', sec3, re.DOTALL)
        table_3 = t3_match.group(1).strip() if t3_match else ""
        
    common_diagnostic_context = f"--- \n\n> **OVERLAPPING DIAGNOSTIC & RISK CONTEXT FOR RAG:**\n\n{table_1}\n\n{table_3}\n"
    
    # Medication sections
    # We will just append the entire section 9 contents (Types of Antihypertensive agents) 
    # to the pharmacological sections, minus its header, to give full drug data.
    sec9_cleaned = re.sub(r'^.*?# TYPES OF ANTIHYPERTENSIVE AGENTS', '', sec9, flags=re.DOTALL)
    common_med_context = f"--- \n\n> **OVERLAPPING PHARMACOLOGICAL CONTEXT (DOSAGES & DRUGS) FOR RAG:**\n\n{sec9_cleaned.strip()}\n"

    # Define where these contexts go
    diagnostic_files = [
        "section-2-measurement-blood-pressure.md",
        "section-3-diagnosis-initial-assessment.md",
        "section-4-non-pharmacological-management.md",
        "section-5-pharmacological-management.md",
        "section-6-severe-hypertension.md",
        "section-7-special-groups.md",
        "section-10-resistant-refractory.md"
    ]
    
    medication_files = [
        "section-5-pharmacological-management.md",
        "section-6-severe-hypertension.md",
        "section-7-special-groups.md",
        "section-10-resistant-refractory.md"
    ]

    for filename in diagnostic_files:
        append_to_file(filename, common_diagnostic_context)
        print(f"Added diagnostic context to {filename}")
        
    for filename in medication_files:
        append_to_file(filename, common_med_context)
        print(f"Added medication context to {filename}")
        
    print("Overlap contexts added successfully.")

if __name__ == "__main__":
    main()
