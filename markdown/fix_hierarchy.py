import os
import re

folder = r'markdown\Ischaemic-Stroke(3rd Edition)'

for filename in os.listdir(folder):
    if not filename.endswith('.md'):
        continue
    if filename == 'section-1-epidemiology-definition-and-classification-of-stroke.md':
        continue
        
    path = os.path.join(folder, filename)
    with open(path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    seq1 = 0
    seq2 = 0
    current_major = None
    
    for i in range(len(lines)):
        # Skip tables or anything not a heading
        if not lines[i].startswith('##'):
            pass
            
        # Match ## 8.1. Text
        m2 = re.match(r'^(##+)\s+(\d+)\.\d+\.\s*(.*)$', lines[i].strip())
        # Match ## 8.1 Text (without trailing dot)
        m2b = re.match(r'^(##+)\s+(\d+)\.\d+\s+(.*)$', lines[i].strip())
        
        # Match ## 8. Text
        m1 = re.match(r'^(##+)\s+(\d+)\.\s*(.*)$', lines[i].strip())
        
        if m2:
            seq2 += 1
            hashes, major, text = m2.groups()
            if current_major != major:
                current_major = major
                seq1 = 1 if seq1 == 0 else seq1 # Assume parent if missing
            lines[i] = f"{hashes} {major}.{seq1}.{seq2} {text}\n"
        elif m2b:
            seq2 += 1
            hashes, major, text = m2b.groups()
            if current_major != major:
                current_major = major
                seq1 = 1 if seq1 == 0 else seq1
            lines[i] = f"{hashes} {major}.{seq1}.{seq2} {text}\n"
        elif m1:
            seq1 += 1
            seq2 = 0 # reset child counter
            hashes, major, text = m1.groups()
            if current_major != major:
                current_major = major
                seq1 = 1
            lines[i] = f"{hashes} {major}.{seq1} {text}\n"
            
    with open(path, 'w', encoding='utf-8') as f:
        f.writelines(lines)
        
print("Hierarchy numbering fixed.")
