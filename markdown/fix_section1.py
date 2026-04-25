import re

def filter_abbreviations(text):
    overlap_start = text.find('<!-- OVERLAP CONTENT FROM: ABBREVIATIONS')
    if overlap_start == -1: return text
    
    main_body = text[:overlap_start]
    abbr_block = text[overlap_start:]
    
    lines = abbr_block.split('\n')
    filtered_lines = []
    
    for line in lines:
        if line.startswith('|') and 'Abbreviations' not in line and '---' not in line:
            parts = [p.strip() for p in line.split('|')]
            if len(parts) > 2:
                abbr = parts[1]
                escaped_abbr = re.escape(abbr)
                if re.search(r'\b' + escaped_abbr + r'\b', main_body):
                    filtered_lines.append(line)
        else:
            filtered_lines.append(line)
            
    return main_body + '\n'.join(filtered_lines)

f_path = r'markdown\Ischaemic-Stroke(3rd Edition)\section-1-epidemiology-definition-and-classification-of-stroke.md'
with open(f_path, 'r', encoding='utf-8') as f:
    orig = f.read()

cleaned = orig
cleaned = cleaned.replace('new cases of stroke . 1 The high burden', 'new cases of stroke . The high burden')
cleaned = cleaned.replace('unclassified stroke (0 . 4%) . 2', 'unclassified stroke (0 . 4%) .')
cleaned = cleaned.replace('and smoking (31%) . 3 Hypertension', 'and smoking (31%) . Hypertension')
cleaned = cleaned.replace('obesity were more prevalent among women . 4', 'obesity were more prevalent among women .')
cleaned = cleaned.replace('as compared to men . 5', 'as compared to men .')
cleaned = cleaned.replace('greater than 24 hours . \" 6', 'greater than 24 hours . \"')
cleaned = cleaned.replace('timed as: 7', 'timed as:')
cleaned = cleaned.replace('without acute infarction . 8', 'without acute infarction .')
cleaned = cleaned.replace('neurological symptoms . 9', 'neurological symptoms .')
cleaned = cleaned.replace('algorithms . 10', 'algorithms .')
cleaned = cleaned.replace('technology . 11', 'technology .')
cleaned = cleaned.replace('ASCO classification . 12', 'ASCO classification .')
cleaned = cleaned.replace('Asian population . 13', 'Asian population .')

cleaned = filter_abbreviations(cleaned)

with open(f_path, 'w', encoding='utf-8') as f:
    f.write(cleaned)

print('Section 1 fixed.')
