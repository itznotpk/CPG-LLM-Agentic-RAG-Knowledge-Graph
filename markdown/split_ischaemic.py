import os
import re

cpg_file = r'markdown\CPG Management of Ischaemic Stroke 3rd Edition 2020 v20230403.md'
out_dir = r'markdown\Ischaemic-Stroke(3rd Edition)'

with open(cpg_file, 'r', encoding='utf-8') as f:
    lines = f.read().split('\n')

os.makedirs(out_dir, exist_ok=True)

# Indices based on previous search
boundaries = [
    (0, 'summary-and-preamble', 0),
    (1, 'epidemiology-definition-and-classification-of-stroke', 1066),
    (2, 'causes-and-pathophysiology', 1150),
    (3, 'diagnosis-and-initial-assessment', 1232),
    (4, 'prognosis', 1287),
    (5, 'prevention-of-stroke', 1344),
    (6, 'investigations', 1910),
    (7, 'emergency-medicine-services', 1980),
    (8, 'acute-general-management', 2182),
    (9, 'reperfusion-of-ischaemic-brain', 2438),
    (10, 'endovascular-thrombectomy', 2693),
    (11, 'stroke-unit', 2832),
    (12, 'stroke-in-the-older-person', 2913),
    (13, 'stroke-and-cardioembolism', 3178),
    (14, 'stroke-in-special-circumstances', 3274),
    (15, 'management-of-stroke-in-pregnancy', 3507),
    (16, 'stroke-therapies-with-limited-evidence', 3591),
    (17, 'quality-assurance', 3620),
    (18, 'appendices', 3633),
    (19, 'references', 3700)
]

# Extract overlap sections block from preamble
# Grades (Lines 423-443)
grades_str = "\n".join(lines[423:444])
# Abbreviations (Lines 445-625)
abbr_str = "\n".join(lines[445:625])

overlap_grades = f"""
<!-- ============================================================ -->
<!-- OVERLAP CONTENT FROM: GRADES OF RECOMMENDATION & EVIDENCE    -->
<!-- Purpose: Defines clinical evidence codes used in this CPG    -->
<!-- ============================================================ -->

{grades_str}

<!-- END OVERLAP FROM: GRADES OF RECOMMENDATION & EVIDENCE -->
"""

overlap_abbr = f"""
<!-- ============================================================ -->
<!-- OVERLAP CONTENT FROM: ABBREVIATIONS                          -->
<!-- Purpose: Localized list of clinical abbreviations used in Section -->
<!-- ============================================================ -->

{abbr_str}

<!-- END OVERLAP FROM: ABBREVIATIONS -->
"""

for i in range(len(boundaries)):
    ch_num = boundaries[i][0]
    ch_slug = boundaries[i][1]
    start_idx = boundaries[i][2]
    end_idx = boundaries[i+1][2] if i + 1 < len(boundaries) else len(lines)
    
    file_name = f'section-{ch_num}-{ch_slug}.md'
    file_path = os.path.join(out_dir, file_name)
    
    # Extract lines
    chunk_lines = lines[start_idx:end_idx]
    
    # Format h1
    if chunk_lines and not chunk_lines[0].startswith('# SECTION'):
        # Just ensure the first meaningful line has # H1 if it's a chapter
        if ch_num > 0:
            chunk_lines.insert(0, f'# SECTION {ch_num}: {ch_slug.upper().replace("-", " ")}')
        else:
            chunk_lines.insert(0, '# SECTION 0: SUMMARY AND PREAMBLE')

    # Add Golden Metadata
    metadata_block = f"""
<!-- METADATA
category: clinical_guidelines
use_case: stroke_management
patient_input: 
output: 
-->
"""
    chunk_lines.insert(1, metadata_block)
    
    # Add overlap at the bottom (except for section 0 which already has them natively)
    if ch_num != 0 and ch_num != 18 and ch_num != 19:
        chunk_lines.append(overlap_grades)
        chunk_lines.append(overlap_abbr)
        
    with open(file_path, 'w', encoding='utf-8') as out:
        out.write('\n'.join(chunk_lines))
        
print("Splitting and Overlap generation complete!")
