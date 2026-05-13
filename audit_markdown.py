import os
import re
import sys
import io

# Ensure stdout uses UTF-8 to avoid encoding errors on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def audit_markdown_files(directory, fix=False):
    """
    Audits and optionally fixes markdown files for specific header formatting.
    """
    header_pattern = re.compile(r'^(#+)\s+(.*)')
    table_figure_header_pattern = re.compile(r'^(#+)\s+((Table|Figure)\s+\d+:)', re.IGNORECASE)
    numbered_header_pattern = re.compile(r'^(\d+(\.\d+)*)(:?\s+)(.*)')

    files_found = 0
    errors_found = 0
    files_fixed = 0

    print(f"Auditing directory: {directory} (Fix mode: {'ON' if fix else 'OFF'})\n")

    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(".md"):
                files_found += 1
                file_path = os.path.join(root, file)
                with open(file_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()

                new_lines = []
                file_changed = False
                file_errors = []

                for i, line in enumerate(lines):
                    line_num = i + 1
                    stripped_line = line.strip()
                    
                    header_match = header_pattern.match(stripped_line)
                    if header_match:
                        hashes = header_match.group(1)
                        content = header_match.group(2)
                        original_content = content
                        
                        # Fix 1: No all-caps in headers
                        letters = [c for c in content if c.isalpha()]
                        if letters and all(c.isupper() for c in letters):
                            file_errors.append(f"Line {line_num}: All-caps header")
                            if fix:
                                content = content.title() # Simple title case fix
                                file_changed = True

                        # Fix 2: Table or Figure lines should not be headers
                        tf_match = table_figure_header_pattern.match(stripped_line)
                        if tf_match:
                            file_errors.append(f"Line {line_num}: Table/Figure as header")
                            if fix:
                                stripped_line = tf_match.group(2) + stripped_line[len(tf_match.group(0)):]
                                file_changed = True
                                new_lines.append(stripped_line + '\n')
                                continue

                        # Fix 3: Numbered header missing colon
                        if len(hashes) in [2, 3]:
                            numbered_match = numbered_header_pattern.match(content)
                            if numbered_match:
                                number_part = numbered_match.group(1)
                                separator = numbered_match.group(3)
                                title_part = numbered_match.group(4)
                                if ":" not in separator:
                                    file_errors.append(f"Line {line_num}: Missing colon")
                                    if fix:
                                        content = f"{number_part}: {title_part}"
                                        file_changed = True
                        
                        if fix and file_changed:
                            new_lines.append(f"{hashes} {content}\n")
                        else:
                            new_lines.append(line)
                    else:
                        new_lines.append(line)

                if file_errors:
                    print(f"Issues in {file}:")
                    for err in file_errors:
                        print(f"  - {err}")
                    errors_found += len(file_errors)
                    
                    if fix and file_changed:
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.writelines(new_lines)
                        print(f"  [FIXED] {file}")
                        files_fixed += 1

    print(f"\nTask complete.")
    print(f"Files checked: {files_found}")
    print(f"Total issues found: {errors_found}")
    if fix:
        print(f"Files modified: {files_fixed}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Audit and fix Markdown headers.")
    parser.add_argument("directory", nargs="?", default=r"c:\Users\chinp\OneDrive\Documents\Agentic RAG\CPG LLM\markdown\Anaesthesia-Medication-Safety")
    parser.add_argument("--fix", action="store_true", help="Automatically fix issues")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.directory):
        print(f"Error: Directory {args.directory} does not exist.")
        sys.exit(1)
        
    audit_markdown_files(args.directory, fix=args.fix)
