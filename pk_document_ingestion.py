"""
Document Ingestion Pipeline with VLM (Vision Language Model) Support

This module uses Docling to convert PDFs to Markdown with:
- PyPdfium2 backend for PDF parsing
- TableFormer (Accurate mode) for table extraction
- Ollama VLM (Qwen3-VL) for image descriptions

Architecture:
    PDF Documents → Docling Runtime → Markdown Output
                         ↓
                   Image Extractor
                         ↓
                   Ollama VLM (Qwen3-VL)
                         ↓
                   Image Descriptions

Requirements:
    - Ollama running locally: ollama serve
    - VLM model pulled: ollama pull qwen3-vl:2b
"""
from typing import Any
from pathlib import Path
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.pipeline_options import PdfPipelineOptions, TableStructureOptions
from docling.datamodel.base_models import InputFormat
from docling_core.types.doc import ImageRefMode

# Try to import VLM-related modules (may not be available in all docling versions)
try:
    from docling.datamodel.pipeline_options import (
        PictureDescriptionApiOptions,
        TableFormerMode,
    )
    VLM_AVAILABLE = True
except ImportError:
    VLM_AVAILABLE = False
    print("Warning: VLM picture description not available in this docling version")

# Try to import PyPdfium backend
try:
    from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
    PYPDFIUM_AVAILABLE = True
except ImportError:
    PYPDFIUM_AVAILABLE = False
    print("Warning: PyPdfiumDocumentBackend not available")

# =============================================================================
# CONFIGURATION
# =============================================================================

# Ollama Configuration
OLLAMA_URL = "http://localhost:11434"  # Default Ollama URL
# VLM_MODEL = "ministral-3:3b"  # Alternative model
VLM_MODEL = "qwen3-vl:4b"  # Vision Language Model for image descriptions

# VLM Prompt for describing images (CPG/Medical context)
VLM_PROMPT = (
    "You are analyzing a clinical practice guideline (CPG) document image. "
    "Provide a DETAILED and STRUCTURED description of what you see. "
    "\n\nFor FLOWCHARTS/ALGORITHMS: "
    "1. Identify the starting point and end points "
    "2. List ALL decision nodes (diamond shapes) and their conditions "
    "3. List ALL action boxes and their contents "
    "4. Describe the flow/arrows connecting them "
    "5. Include any scoring systems, severity levels, or classifications shown "
    "\n\nFor TABLES: "
    "1. List column headers "
    "2. Summarize key data (drug names, dosages, grades, contraindications) "
    "\n\nFor DIAGRAMS: "
    "1. Identify anatomical structures or medical devices shown "
    "2. Describe labels and annotations "
    "\n\nBe comprehensive - this description will replace the image in the document."
)

# Markdown Placeholders
PAGE_BREAK_PLACEHOLDER = "<!-- page_break -->"
IMAGE_DESCRIPTION_START = "<image_description>"
IMAGE_DESCRIPTION_END = "</image_description>"

# Definition extraction patterns
DEFINITION_PATTERNS = [
    # Pattern: "TERM = definition" (e.g., "ED = erectile dysfunction")
    (r'\b([A-Z][A-Z0-9\-]{1,10})\s*=\s*([^.;\n]+[a-z])', 'abbreviation'),
    # Pattern: "Term is defined as definition"
    (r'\b([A-Z][a-zA-Z\s]{2,30})\s+is\s+defined\s+as\s+([^.]+\.)', 'formal'),
    # Pattern: "Term refers to definition"
    (r'\b([A-Z][a-zA-Z\s]{2,30})\s+refers\s+to\s+([^.]+\.)', 'reference'),
    # Pattern: "**Term**: definition" (markdown bold definitions)
    (r'\*\*([^*]{2,40})\*\*[:\s]+([^.]+\.)', 'bold'),
    # Pattern: Term (definition in parentheses)
    (r'\b([A-Z][A-Z0-9\-]{1,10})\s+\(([^)]+)\)', 'parenthetical'),
]

# Known medical abbreviations/definitions (base set for CPG)
KNOWN_DEFINITIONS = {
    "ED": "Erectile Dysfunction",
    "IIEF-5": "5-item version of International Index of Erectile Function",
    "EHS": "Erection Hardness Score",
    "PDE5i": "Phosphodiesterase-5 inhibitors",
    "ASCVD": "Atherosclerotic Cardiovascular Disease",
    "VED": "Vacuum Erection Device",
    "Li-ESWT": "Low-intensity Extracorporeal Shockwave Therapy",
    "LUTS": "Lower Urinary Tract Symptoms",
    "BPH": "Benign Prostatic Hyperplasia",
    "NPT": "Nocturnal Penile Tumescence",
    "PSA": "Prostate-Specific Antigen",
    "HbA1c": "Glycated Hemoglobin",
    "LH": "Luteinizing Hormone",
    "PHQ-9": "Patient Health Questionnaire-9",
    "GAD-7": "Generalized Anxiety Disorder 7-item scale",
    "CBT": "Cognitive Behavioral Therapy",
    "MOH": "Ministry of Health",
    "CPG": "Clinical Practice Guideline",
}


# =============================================================================
# PIPELINE OPTIONS
# =============================================================================

def create_picture_description_options():
    """Create VLM options for image description using Ollama."""
    if not VLM_AVAILABLE:
        return None
    
    return PictureDescriptionApiOptions(
        url=f"{OLLAMA_URL}/v1/chat/completions",
        params=dict[str, Any](
            model=VLM_MODEL,
            think=False,
            seed=42,
            max_completion_tokens=256,
        ),
        prompt=VLM_PROMPT,
        timeout=90,
    )


def create_pdf_pipeline_options() -> PdfPipelineOptions:
    """Create PDF pipeline options with VLM and table extraction enabled."""
    options = PdfPipelineOptions(
        enable_remote_services=True,
        do_ocr=False,  # Disable OCR (use VLM instead)
        do_table_structure=True,
        generate_picture_images=True,
        do_picture_description=True,
    )
    
    # Configure TableFormer for accurate table extraction
    if VLM_AVAILABLE:
        options.table_structure_options = TableStructureOptions(
            mode=TableFormerMode.ACCURATE,  # High-precision table model
        )
        # Configure VLM for picture descriptions
        options.picture_description_options = create_picture_description_options()
    
    return options


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def add_page_numbers(content: str) -> str:
    """
    Replace page break placeholders with numbered page headers.
    
    Args:
        content: Markdown content with page break placeholders
        
    Returns:
        Markdown content with page numbers
    """
    pages = content.split(PAGE_BREAK_PLACEHOLDER)
    
    if len(pages) <= 1:
        # No page breaks, just add Page 1 header at the start
        return f"---\n## 📄 Page 1\n---\n\n{content}"
    
    numbered_pages = []
    for i, page in enumerate(pages, 1):
        page_header = f"\n---\n## 📄 Page {i}\n---\n"
        numbered_pages.append(f"{page_header}{page.strip()}")
    
    return "\n\n".join(numbered_pages)


def extract_definitions(content: str) -> dict[str, str]:
    """
    Extract term definitions from document content.
    
    Uses regex patterns to identify common definition formats:
    - "TERM = definition" (abbreviations)
    - "Term is defined as definition"
    - "Term refers to definition"
    - "**Term**: definition" (markdown bold)
    - "TERM (definition in parentheses)"
    
    Args:
        content: Document markdown content
        
    Returns:
        Dictionary of {term: definition}
    """
    import re
    
    definitions = {}
    
    # Start with known definitions
    definitions.update(KNOWN_DEFINITIONS)
    
    # Extract definitions from content using patterns
    for pattern, pattern_type in DEFINITION_PATTERNS:
        matches = re.findall(pattern, content)
        for match in matches:
            term = match[0].strip()
            definition = match[1].strip()
            
            # Clean up definition
            definition = re.sub(r'\s+', ' ', definition)  # Normalize whitespace
            definition = definition.rstrip('.')
            
            # Only add if term looks valid (not too long, not a sentence)
            if len(term) <= 40 and len(definition) <= 200:
                # Don't overwrite existing definitions unless new one is longer/better
                if term not in definitions or len(definition) > len(definitions[term]):
                    definitions[term] = definition
    
    return definitions


def generate_glossary(definitions: dict[str, str]) -> str:
    """
    Generate a markdown glossary table from definitions.
    
    Args:
        definitions: Dictionary of {term: definition}
        
    Returns:
        Markdown formatted glossary section
    """
    if not definitions:
        return ""
    
    # Sort definitions alphabetically by term
    sorted_defs = sorted(definitions.items(), key=lambda x: x[0].lower())
    
    glossary = "## 📖 Glossary\n\n"
    glossary += "| Term | Definition |\n"
    glossary += "|------|------------|\n"
    
    for term, definition in sorted_defs:
        # Escape pipe characters in definition
        definition = definition.replace("|", "\\|")
        glossary += f"| **{term}** | {definition} |\n"
    
    glossary += "\n---\n"
    
    return glossary


def add_glossary_to_content(content: str, definitions: dict[str, str]) -> str:
    """
    Add glossary section to the beginning of markdown content.
    
    Args:
        content: Original markdown content
        definitions: Dictionary of definitions to include
        
    Returns:
        Markdown content with glossary prepended
    """
    if not definitions:
        return content
    
    glossary = generate_glossary(definitions)
    
    # Insert glossary after the first page header if it exists
    if "## 📄 Page 1" in content:
        parts = content.split("## 📄 Page 1", 1)
        return parts[0] + "## 📄 Page 1\n\n" + glossary + parts[1].lstrip('\n')
    else:
        return glossary + "\n" + content


# =============================================================================
# DOCUMENT PROCESSING
# =============================================================================

def process_document(pdf_path: str) -> str:
    """
    Process a PDF document and convert to markdown with VLM image descriptions.
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        Markdown content with image descriptions
    """
    # Build format options
    format_options = {
        InputFormat.PDF: PdfFormatOption(
            pipeline_options=create_pdf_pipeline_options(),
        )
    }
    
    # Add PyPdfium backend if available
    if PYPDFIUM_AVAILABLE:
        format_options[InputFormat.PDF] = PdfFormatOption(
            pipeline_options=create_pdf_pipeline_options(),
            backend=PyPdfiumDocumentBackend,
        )
    
    # Create converter
    converter = DocumentConverter(format_options=format_options)
    
    # Convert document
    result = converter.convert(pdf_path)
    doc = result.document
    
    # Export to markdown with image placeholders
    content = doc.export_to_markdown(
        image_mode=ImageRefMode.PLACEHOLDER,
        image_placeholder="",
        page_break_placeholder=PAGE_BREAK_PLACEHOLDER,
        include_annotations=True,
        mark_annotations=True,
    )
    
    # Replace annotation markers with our custom tags
    content = content.replace(
        '<!--<annotation kind="description">-->', IMAGE_DESCRIPTION_START
    )
    content = content.replace(
        "<!--<annotation/>-->", IMAGE_DESCRIPTION_END
    )
    
    # Add page numbers to the markdown
    content = add_page_numbers(content)
    
    # Extract definitions and add glossary
    definitions = extract_definitions(content)
    if definitions:
        content = add_glossary_to_content(content, definitions)
    
    return content


def process_all_documents(
    input_dir: str = "documents",
    output_dir: str = "markdown",
    force: bool = False
) -> list[Path]:
    """
    Process all PDF documents in a directory.
    
    Args:
        input_dir: Directory containing PDF files
        output_dir: Directory to save markdown files
        force: If True, re-process even if markdown already exists
        
    Returns:
        List of output file paths
    """
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    if not input_path.exists():
        print(f"Error: Directory '{input_dir}' does not exist")
        return []
    
    pdf_files = list(input_path.glob("*.pdf"))
    
    if not pdf_files:
        print(f"No PDF files found in '{input_dir}'")
        return []
    
    # Filter out already processed files (unless force=True)
    if not force:
        files_to_process = []
        skipped = 0
        for pdf_file in pdf_files:
            output_file = output_path / f"{pdf_file.stem}.md"
            if output_file.exists():
                skipped += 1
            else:
                files_to_process.append(pdf_file)
        
        if skipped > 0:
            print(f"Skipping {skipped} already processed file(s) (use --force to re-process)")
        pdf_files = files_to_process
    
    if not pdf_files:
        print("No new PDF files to process")
        return []
    
    print(f"Processing {len(pdf_files)} PDF file(s)...")
    
    converted = []
    for i, pdf_file in enumerate(pdf_files, 1):
        print(f"\n[{i}/{len(pdf_files)}] Processing: {pdf_file.name}")
        try:
            md_content = process_document(str(pdf_file))
            
            # Save markdown
            output_file = output_path / f"{pdf_file.stem}.md"
            output_file.write_text(md_content, encoding="utf-8")
            
            print(f"Saved to: {output_file}")
            converted.append(output_file)
        except Exception as e:
            print(f"Error processing {pdf_file.name}: {e}")
    
    print(f"\nProcessed {len(converted)}/{len(pdf_files)} files successfully")
    return converted


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Main entry point with CLI arguments."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Convert PDF files to Markdown with VLM image descriptions using Docling"
    )
    parser.add_argument(
        "--input", "-i",
        default="documents",
        help="Input directory containing PDF files (default: documents)"
    )
    parser.add_argument(
        "--output", "-o",
        default="markdown",
        help="Output directory for markdown files (default: markdown)"
    )
    parser.add_argument(
        "--single", "-s",
        type=str,
        help="Process a single PDF file instead of a directory"
    )
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Re-process files even if markdown already exists"
    )
    
    args = parser.parse_args()
    
    if args.single:
        # Process single file
        pdf_path = Path(args.single)
        if not pdf_path.exists():
            print(f"Error: File '{args.single}' does not exist")
            return
        
        print(f"Processing: {pdf_path.name}")
        md_content = process_document(str(pdf_path))
        
        # Save to output directory
        output_path = Path(args.output)
        output_path.mkdir(parents=True, exist_ok=True)
        output_file = output_path / f"{pdf_path.stem}.md"
        output_file.write_text(md_content, encoding="utf-8")
        print(f"Saved to: {output_file}")
    else:
        # Process all documents in directory
        process_all_documents(args.input, args.output, force=args.force)


if __name__ == "__main__":
    main()

