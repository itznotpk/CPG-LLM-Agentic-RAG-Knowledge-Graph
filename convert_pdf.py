"""
PDF to Markdown converter using Docling
"""
from docling.document_converter import DocumentConverter
from pathlib import Path

def convert_pdf_to_markdown(pdf_path: str, output_dir: str = "markdown"):
    """Convert a PDF file to markdown using Docling."""
    
    # Initialize converter
    converter = DocumentConverter()
    
    # Convert PDF
    print(f"Converting: {pdf_path}")
    result = converter.convert(pdf_path)
    
    # Export to markdown
    markdown_content = result.document.export_to_markdown()
    
    # Create output path
    pdf_name = Path(pdf_path).stem
    output_path = Path(output_dir) / f"{pdf_name}.md"
    
    # Ensure output directory exists
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Save markdown
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(markdown_content)
    
    print(f"Saved to: {output_path}")
    return output_path

if __name__ == "__main__":
    # Convert the e-CPG Management PDF
    pdf_file = "documents/e-CPG Management of Erectile Dysfunction.pdf"
    convert_pdf_to_markdown(pdf_file, "markdown")
