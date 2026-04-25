import os
import re

def fix_format(text):
    # Rule 1: Spaces before commas, periods, closing parens
    text = re.sub(r' +([,\.\)])', r'\1', text)
    # Spaces after opening parens
    text = re.sub(r'(\() +', r'\1', text)
    
    # Rule 2: Decimals and numbers (e.g. 25 . 7 -> 25.7)
    # The first pass of Rule 1 turns "25 . 7" into "25. 7".
    # Let's fix digits with dots
    text = re.sub(r'(\d)\s*\.\s*(\d)', r'\1.\2', text)
    text = re.sub(r'(\d)\s*\.\s*(\d)', r'\1.\2', text) # run twice for overlapping like 1 . 2 . 3 -> 1.2.3
    
    # Rule 3: Headings (e.g. ## 1 . Head -> ## 1. Head)
    text = re.sub(r'(#+\s+\d+)\s*\.\s+', r'\1. ', text)
    
    # Rule 4: Roman/Alpha lists (e.g. - I . -> - I.)
    text = re.sub(r'^(\s*-\s+[a-zA-ZIVXLCDM]+)\s*\.\s+', r'\1. ', text, flags=re.MULTILINE)
    
    # Rule 5: i.e. and e.g. and et al.
    text = re.sub(r'\b[iI]\s*\.\s*[eE]\s*\.', 'i.e.', text)
    text = re.sub(r'\b[eE]\s*\.\s*[gG]\s*\.', 'e.g.', text)
    text = re.sub(r'\bet\s+al\s*\.', 'et al.', text)

    # Rule 6: Fix broken paragraphs (if a line ends with a word/comma, and double newline follows, then lowercase letter)
    # Specifically: newline, optional spaces/newlines, lowercase letter
    text = re.sub(r'([a-zA-Z,])\n\n+([a-z])', r'\1 \2', text)
    text = re.sub(r'([a-zA-Z,])\n([a-z])', r'\1 \2', text)
    
    # Also "word ." -> "word." is handled by Rule 1.
    
    # Now let's handle the "Key Recommendations:" bullet points
    lines = text.split('\n')
    in_key_rec = False
    for i, line in enumerate(lines):
        if 'Key Recommendations:' in line or 'Key Recommendation:' in line:
            in_key_rec = True
        elif line.startswith('## ') and 'Key Recommendations' not in line:
            in_key_rec = False
            
        if in_key_rec and re.match(r'^-\s*\d+\s*\.\s*', line):
            lines[i] = re.sub(r'^-\s*\d+\s*\.\s*', '- ', line)
            
    text = '\n'.join(lines)
    
    return text

def main():
    folder = r'markdown\Ischaemic-Stroke(3rd Edition)'
    for file in os.listdir(folder):
        if not file.endswith('.md'):
            continue
        # Skip section-1 as it was manually formatted by user and already perfect
        if file == 'section-1-epidemiology-definition-and-classification-of-stroke.md':
            continue
            
        path = os.path.join(folder, file)
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        new_content = fix_format(content)
        
        if new_content != content:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(new_content)
                
    print("Formatting applied successfully.")

if __name__ == '__main__':
    main()
