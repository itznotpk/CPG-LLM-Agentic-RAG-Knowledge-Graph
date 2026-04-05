import os
import re
import shutil

INPUT_FILE = r'c:\Documents\CPG\CPG markdown\CPG-LLM-Agentic-RAG-Knowledge-Graph-main\markdown\6 Management of Hypertension (5th Edition).md'
OUTPUT_DIR = r'c:\Documents\CPG\CPG markdown\CPG-LLM-Agentic-RAG-Knowledge-Graph-main\markdown\Hypertension(5th Edition)'

def get_metadata(section_name):
    # Base metadata block
    return f"""<!--
category: "internal medicine"
use_case: "RAG"
patient_input: "null"
output: "{section_name}"
-->

# {section_name.upper()}

"""

SECTIONS = [
    (1, "Epidemiology, Definition and Classification of Hypertension", "section-1-epidemiology-definition-classification.md", r"^## Epidemiology, Definition and Classification of Hypertension"),
    (2, "Measurement of Blood Pressure", "section-2-measurement-blood-pressure.md", r"^## Measurement of Blood Pressure"),
    (3, "Diagnosis and Initial Assessment", "section-3-diagnosis-initial-assessment.md", r"^## Diagnosis and Initial Assessment"),
    (4, "Non-Pharmacological Management", "section-4-non-pharmacological-management.md", r"^## Non-pharmacological Management"), # Case insensitive match inside python
    (5, "Pharmacological Management", "section-5-pharmacological-management.md", r"^## Pharmacological Management"),
    (6, "Management of Severe Hypertension", "section-6-severe-hypertension.md", r"^## Management of Severe Hypertension"),
    (7, "Hypertension in Special Groups", "section-7-special-groups.md", r"^## Hypertension in Special Groups"),
    (8, "Economic Impact of Hypertension", "section-8-economic-impact.md", r"^## Economic Impact of Hypertension"),
    (9, "Types of Antihypertensive Agents", "section-9-types-of-agents.md", r"^## Types of Antihypertensive Agents"),
    (10, "Resistant and Refractory Hypertension", "section-10-resistant-refractory.md", r"^## Resistant and Refractory Hypertension"),
    (11, "Aspirin in Hypertension", "section-11-aspirin.md", r"^## Aspirin in Hypertension"),
    (12, "Device and Procedure Based Therapy", "section-12-device-procedure-therapy.md", r"^## Device and Procedure Based Therapy"),
    (13, "Suggested Areas of Research", "section-13-suggested-research.md", r"^## Suggested Areas of Research"),
    (14, "Appendices", "appendix.md", r"^## Appendices"),
    (15, "References", "references.md", r"^## References")
]

def main():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    current_section = 0
    file_contents = {0: []} # 0 is Introduction/Frontmatter/Key Recommendations

    for line in lines:
        matched = False
        for sec_num, sec_title, filename, regex in SECTIONS:
            if re.match(regex, line.strip(), re.IGNORECASE):
                current_section = sec_num
                file_contents[current_section] = []
                matched = True
                break
        
        file_contents[current_section].append(line)

    # Preprocess tables for overlapping
    table_of_classification = []
    risk_stratification = []
    drug_tables = []
    
    # Simple extraction of common tables based on keywords in lines across all
    full_text = "".join(lines)
    
    # Save the files
    for sec_num, content_lines in file_contents.items():
        if sec_num == 0:
            filename = "section-0-key-recommendations.md"
            title = "Key Recommendations and Intro"
        else:
            _, title, filename, _ = SECTIONS[sec_num-1]
        
        filepath = os.path.join(OUTPUT_DIR, filename)
        with open(filepath, 'w', encoding='utf-8') as sf:
            sf.write(get_metadata(title))
            sf.writelines(content_lines)

    print("Success: Files split.")

if __name__ == "__main__":
    main()
