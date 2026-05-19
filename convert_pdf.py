"""
PDF to Markdown converter using Docling.

This is step 1 of the CPG ingestion pipeline: it produces ONE monolithic
markdown file per PDF into `markdown/raw_monolithic/` (the established
convention in this repo). Section splitting is a separate downstream step.

Features:
- Converts all PDFs in a directory, or a single file (--single)
- Skips already-converted files (use --force to re-convert)
- Reuses one converter instance across files for performance
- Configurable Docling pipeline (OCR, table structure/mode)
- Per-file timing and a final summary with full tracebacks on failure
"""
import argparse
import logging
import time
import traceback
from pathlib import Path

from docling.datamodel.base_models import InputFormat
from docling.document_converter import DocumentConverter, PdfFormatOption

# Output directory convention used across this repo for raw, unsplit markdown.
DEFAULT_OUTPUT_DIR = "markdown/raw_monolithic"
DEFAULT_INPUT_DIR = "documents"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def create_converter(
    do_ocr: bool = True,
    do_table_structure: bool = True,
    force_full_page_ocr: bool = False,
    ocr_lang: list[str] | None = None,
    accurate_tables: bool = True,
) -> DocumentConverter:
    """Create a configured DocumentConverter instance."""
    from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
    from docling.datamodel.pipeline_options import PdfPipelineOptions

    pipeline_options = PdfPipelineOptions()
    pipeline_options.do_ocr = do_ocr
    pipeline_options.do_table_structure = do_table_structure

    if do_table_structure and accurate_tables:
        try:
            from docling.datamodel.pipeline_options import TableFormerMode

            pipeline_options.table_structure_options.mode = TableFormerMode.ACCURATE
            pipeline_options.table_structure_options.do_cell_matching = True
        except (ImportError, AttributeError):
            logger.warning("ACCURATE table mode unavailable; using default mode")

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
                backend=PyPdfiumDocumentBackend,
            )
        }
    )
    logger.info(
        "Converter ready (OCR=%s, tables=%s, accurate_tables=%s, "
        "full_page_ocr=%s, backend=PyPdfium2, ocr=EasyOCR)",
        do_ocr,
        do_table_structure,
        do_table_structure and accurate_tables,
        force_full_page_ocr,
    )
    return converter


def convert_pdf_to_markdown(
    converter: DocumentConverter,
    pdf_path: str,
    output_dir: str = DEFAULT_OUTPUT_DIR,
    force: bool = False,
) -> Path | None:
    """Convert a single PDF to a monolithic markdown file.

    Output filename preserves the PDF stem (e.g. "Foo.pdf" -> "Foo.md")
    to match the existing raw_monolithic naming convention.
    """
    pdf_path = Path(pdf_path)

    if not pdf_path.is_file():
        logger.error("Not a file: %s", pdf_path)
        return None

    output_path = Path(output_dir) / f"{pdf_path.stem}.md"

    if output_path.exists() and not force:
        logger.info("Skipping (already exists, use --force): %s", output_path)
        return output_path

    Path(output_dir).mkdir(parents=True, exist_ok=True)

    logger.info("Converting: %s", pdf_path.name)
    start = time.perf_counter()
    try:
        result = converter.convert(str(pdf_path))
        markdown_content = result.document.export_to_markdown()

        # Atomic-ish write: write to temp then replace, so a crash mid-write
        # never leaves a half-written .md that --force-skip would trust.
        tmp_path = output_path.with_suffix(".md.tmp")
        tmp_path.write_text(markdown_content, encoding="utf-8")
        tmp_path.replace(output_path)

        elapsed = time.perf_counter() - start
        logger.info(
            "Saved %s (%.0f KB, %.1fs)",
            output_path,
            len(markdown_content) / 1024,
            elapsed,
        )
        return output_path
    except Exception as e:
        logger.error("Failed to convert %s: %s", pdf_path.name, e)
        logger.debug("%s", traceback.format_exc())
        return None


def convert_all_pdfs(
    input_dir: str = DEFAULT_INPUT_DIR,
    output_dir: str = DEFAULT_OUTPUT_DIR,
    force: bool = False,
    do_ocr: bool = True,
    do_table_structure: bool = True,
    force_full_page_ocr: bool = False,
    ocr_lang: list[str] | None = None,
    accurate_tables: bool = True,
) -> list[Path]:
    """Convert every PDF in the input directory to markdown."""
    input_path = Path(input_dir)

    if not input_path.exists():
        logger.error("Input directory does not exist: %s", input_dir)
        return []

    pdf_files = sorted(input_path.glob("*.pdf"))
    if not pdf_files:
        logger.warning("No PDF files found in: %s", input_dir)
        return []

    logger.info("Found %d PDF file(s)", len(pdf_files))

    converter = create_converter(
        do_ocr=do_ocr,
        do_table_structure=do_table_structure,
        force_full_page_ocr=force_full_page_ocr,
        ocr_lang=ocr_lang,
        accurate_tables=accurate_tables,
    )

    converted: list[Path] = []
    failed: list[str] = []
    for i, pdf_file in enumerate(pdf_files, 1):
        logger.info("[%d/%d] %s", i, len(pdf_files), pdf_file.name)
        output_path = convert_pdf_to_markdown(
            converter, str(pdf_file), output_dir, force
        )
        if output_path:
            converted.append(output_path)
        else:
            failed.append(pdf_file.name)

    logger.info("Done: %d/%d succeeded", len(converted), len(pdf_files))
    if failed:
        logger.warning("Failed: %s", ", ".join(failed))
    return converted


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Convert PDF(s) to monolithic Markdown using Docling"
    )
    parser.add_argument(
        "--input", "-i",
        default=DEFAULT_INPUT_DIR,
        help=f"Input directory of PDFs (default: {DEFAULT_INPUT_DIR})",
    )
    parser.add_argument(
        "--output", "-o",
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output directory (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--single", "-s",
        type=str,
        help="Convert a single PDF file instead of scanning a directory",
    )
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Re-convert even if the markdown already exists",
    )
    parser.add_argument(
        "--no-ocr",
        action="store_true",
        help="Disable OCR (faster; fails on scanned PDFs)",
    )
    parser.add_argument(
        "--no-tables",
        action="store_true",
        help="Disable table structure extraction",
    )
    parser.add_argument(
        "--fast-tables",
        action="store_true",
        help="Use FAST table mode instead of the default ACCURATE",
    )
    parser.add_argument(
        "--force-full-page-ocr",
        action="store_true",
        help="OCR the full page (use when normal OCR returns empty)",
    )
    parser.add_argument(
        "--ocr-lang",
        type=str,
        default="",
        help="Comma-separated OCR languages, e.g. 'en' or 'en,ms'",
    )

    args = parser.parse_args()
    ocr_lang = [s.strip() for s in args.ocr_lang.split(",") if s.strip()]

    if args.single:
        converter = create_converter(
            do_ocr=not args.no_ocr,
            do_table_structure=not args.no_tables,
            force_full_page_ocr=args.force_full_page_ocr,
            ocr_lang=ocr_lang or None,
            accurate_tables=not args.fast_tables,
        )
        convert_pdf_to_markdown(converter, args.single, args.output, args.force)
    else:
        convert_all_pdfs(
            input_dir=args.input,
            output_dir=args.output,
            force=args.force,
            do_ocr=not args.no_ocr,
            do_table_structure=not args.no_tables,
            force_full_page_ocr=args.force_full_page_ocr,
            ocr_lang=ocr_lang or None,
            accurate_tables=not args.fast_tables,
        )


if __name__ == "__main__":
    main()
