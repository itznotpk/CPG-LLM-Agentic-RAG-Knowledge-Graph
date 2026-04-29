"""
Convert Heart Disease in Pregnancy PDF using OCR fallback chain:
1. RapidOCR with force_full_page_ocr=True
2. EasyOCR with force_full_page_ocr=True  
3. EasyOCR with force_full_page_ocr=True (retry)
"""
import logging
from pathlib import Path
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.datamodel.base_models import InputFormat
from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

PDF_PATH = Path(r"CPG Heart Disease in Pregnancy.pdf")
OUTPUT_PATH = Path(r"markdown/CPG Heart Disease in Pregnancy.md")

def try_convert(ocr_engine_name, ocr_options_class, force_full_page_ocr=True):
    """Try converting with a specific OCR engine."""
    logger.info(f"=== Attempting conversion with {ocr_engine_name} (force_full_page_ocr={force_full_page_ocr}) ===")
    
    pipeline_options = PdfPipelineOptions()
    pipeline_options.do_ocr = True
    pipeline_options.do_table_structure = True
    pipeline_options.ocr_options = ocr_options_class()
    pipeline_options.ocr_options.force_full_page_ocr = force_full_page_ocr
    
    converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(
                pipeline_options=pipeline_options,
                backend=PyPdfiumDocumentBackend
            )
        }
    )
    
    result = converter.convert(str(PDF_PATH))
    markdown_content = result.document.export_to_markdown()
    
    # Check if result is meaningful (not just image placeholders)
    lines = [l.strip() for l in markdown_content.split('\n') if l.strip()]
    non_image_lines = [l for l in lines if l != '<!-- image -->']
    
    logger.info(f"Total lines: {len(lines)}, Non-image lines: {len(non_image_lines)}")
    
    if len(non_image_lines) > 50:  # Meaningful content threshold
        logger.info(f"SUCCESS with {ocr_engine_name}: {len(non_image_lines)} content lines extracted")
        return markdown_content
    else:
        logger.warning(f"INSUFFICIENT content with {ocr_engine_name}: only {len(non_image_lines)} content lines")
        return None

def main():
    if not PDF_PATH.exists():
        logger.error(f"PDF not found: {PDF_PATH}")
        return
    
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    # Attempt 1: RapidOCR
    try:
        from docling.datamodel.pipeline_options import RapidOcrOptions
        result = try_convert("RapidOCR", RapidOcrOptions, force_full_page_ocr=True)
        if result:
            with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
                f.write(result)
            logger.info(f"Saved to {OUTPUT_PATH} using RapidOCR")
            return
    except Exception as e:
        logger.error(f"RapidOCR failed: {e}")
    
    # Attempt 2: EasyOCR
    try:
        from docling.datamodel.pipeline_options import EasyOcrOptions
        result = try_convert("EasyOCR", EasyOcrOptions, force_full_page_ocr=True)
        if result:
            with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
                f.write(result)
            logger.info(f"Saved to {OUTPUT_PATH} using EasyOCR")
            return
    except Exception as e:
        logger.error(f"EasyOCR failed: {e}")
    
    # Attempt 3: EasyOCR retry with force_full_page_ocr  
    try:
        from docling.datamodel.pipeline_options import EasyOcrOptions
        logger.info("Retrying EasyOCR with force_full_page_ocr=True (final attempt)...")
        result = try_convert("EasyOCR (retry)", EasyOcrOptions, force_full_page_ocr=True)
        if result:
            with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
                f.write(result)
            logger.info(f"Saved to {OUTPUT_PATH} using EasyOCR (retry)")
            return
    except Exception as e:
        logger.error(f"EasyOCR retry failed: {e}")
    
    logger.error("ALL OCR attempts failed to produce meaningful content!")

if __name__ == "__main__":
    main()
