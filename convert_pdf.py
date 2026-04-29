"""
PDF to Markdown converter using Docling

Features:
- Converts all PDFs in a directory to markdown
- Skips already converted files (use --force to re-convert)
- CLI arguments for flexibility
- Reuses converter instance for performance
- Configurable Docling pipeline options
"""
import argparse
import logging
from pathlib import Path
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.datamodel.base_models import InputFormat

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_converter(
    do_ocr: bool = True,
    do_table_structure: bool = True,
    force_full_page_ocr: bool = False,
    ocr_lang: list[str] | None = None,
) -> DocumentConverter:
    """Create a configured DocumentConverter instance."""
    from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    
    pipeline_options = PdfPipelineOptions()
    pipeline_options.do_ocr = do_ocr
    pipeline_options.do_table_structure = do_table_structure
    
    if do_ocr:
        from docling.datamodel.pipeline_options import EasyOcrOptions
        pipeline_options.ocr_options = EasyOcrOptions()
        pipeline_options.ocr_options.force_full_page_ocr = force_full_page_ocr
        if ocr_lang:
            pipeline_options.ocr_options.lang = ocr_lang
    
    converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(
                pipeline_options=pipeline_options,
                backend=PyPdfiumDocumentBackend
            )
        }
    )
    logger.info(
        "Converter initialized (OCR: %s, Table Structure: %s, Full Page OCR: %s) "
        "using PyPdfiumDocumentBackend and EasyOCR",
        do_ocr,
        do_table_structure,
        force_full_page_ocr,
    )
    return converter


def convert_pdf_to_markdown(
    converter: DocumentConverter,
    pdf_path: str,
    output_dir: str = "markdown",
    force: bool = False
) -> Path | None:
    """Convert a PDF file to markdown using Docling."""
    pdf_path = Path(pdf_path)
    
    # Create output path
    pdf_name = pdf_path.stem
    output_path = Path(output_dir) / f"{pdf_name}.md"
    
    # Skip if already exists (unless force is True)
    if output_path.exists() and not force:
        logger.info(f"Skipping (already exists): {output_path}")
        return output_path
    
    # Ensure output directory exists
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Convert PDF
    logger.info(f"Converting: {pdf_path.name}")
    try:
        result = converter.convert(str(pdf_path))
        
        # Export to markdown
        markdown_content = result.document.export_to_markdown()
        
        # Save markdown
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(markdown_content)
        
        logger.info(f"Saved to: {output_path}")
        return output_path
    except Exception as e:
        logger.error(f"Failed to convert {pdf_path.name}: {e}")
        return None


def convert_all_pdfs(
    input_dir: str = "documents",
    output_dir: str = "markdown",
    force: bool = False,
    do_ocr: bool = True,
    do_table_structure: bool = True,
    force_full_page_ocr: bool = False,
    ocr_lang: list[str] | None = None,
) -> list[Path]:
    """Convert all PDF files in the input directory to markdown."""
    input_path = Path(input_dir)
    
    if not input_path.exists():
        logger.error(f"Directory '{input_dir}' does not exist")
        return []
    
    # Find all PDF files
    pdf_files = list(input_path.glob("*.pdf"))
    
    if not pdf_files:
        logger.warning(f"No PDF files found in '{input_dir}'")
        return []
    
    logger.info(f"Found {len(pdf_files)} PDF file(s) to convert")
    
    # Create converter ONCE and reuse for all files
    converter = create_converter(
        do_ocr=do_ocr,
        do_table_structure=do_table_structure,
        force_full_page_ocr=force_full_page_ocr,
        ocr_lang=ocr_lang,
    )
    
    converted = []
    for i, pdf_file in enumerate(pdf_files, 1):
        logger.info(f"[{i}/{len(pdf_files)}] Processing: {pdf_file.name}")
        output_path = convert_pdf_to_markdown(converter, str(pdf_file), output_dir, force)
        if output_path:
            converted.append(output_path)
    
    logger.info(f"Converted {len(converted)}/{len(pdf_files)} files successfully")
    return converted


def main():
    """Main entry point with CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Convert PDF files to Markdown using Docling"
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
        "--force", "-f",
        action="store_true",
        help="Re-convert files even if markdown already exists"
    )
    parser.add_argument(
        "--no-ocr",
        action="store_true",
        help="Disable OCR (faster, but won't work on scanned PDFs)"
    )
    parser.add_argument(
        "--no-tables",
        action="store_true",
        help="Disable table structure extraction"
    )
    parser.add_argument(
        "--force-full-page-ocr",
        action="store_true",
        help="Force OCR on full page (useful when OCR returns empty results)"
    )
    parser.add_argument(
        "--ocr-lang",
        type=str,
        default="",
        help="Comma-separated OCR languages (e.g., 'en' or 'en,ms')"
    )
    parser.add_argument(
        "--single", "-s",
        type=str,
        help="Convert a single PDF file instead of a directory"
    )
    
    args = parser.parse_args()
    
    ocr_lang = [lang.strip() for lang in args.ocr_lang.split(",") if lang.strip()]

    if args.single:
        # Convert single file
        converter = create_converter(
            do_ocr=not args.no_ocr,
            do_table_structure=not args.no_tables,
            force_full_page_ocr=args.force_full_page_ocr,
            ocr_lang=ocr_lang or None,
        )
        convert_pdf_to_markdown(converter, args.single, args.output, args.force)
    else:
        # Convert all files in directory
        convert_all_pdfs(
            input_dir=args.input,
            output_dir=args.output,
            force=args.force,
            do_ocr=not args.no_ocr,
            do_table_structure=not args.no_tables,
            force_full_page_ocr=args.force_full_page_ocr,
            ocr_lang=ocr_lang or None,
        )


if __name__ == "__main__":
    main()
