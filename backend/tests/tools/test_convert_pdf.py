"""Tests for PDF conversion options."""

from docling.datamodel.base_models import InputFormat

import convert_pdf


def test_create_converter_sets_ocr_lang() -> None:
    """OCR language list should be applied to EasyOCR options."""
    converter = convert_pdf.create_converter(ocr_lang=["en"])
    pdf_options = converter.format_to_options[InputFormat.PDF]
    ocr_options = pdf_options.pipeline_options.ocr_options

    assert ocr_options is not None
    assert ocr_options.lang == ["en"]
