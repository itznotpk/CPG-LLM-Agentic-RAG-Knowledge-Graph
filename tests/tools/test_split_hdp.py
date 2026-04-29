"""Tests for the Heart Disease in Pregnancy markdown splitter."""

from tools import split_hdp


def test_slugify_basic() -> None:
    """Slugify should normalize spaces and symbols."""
    value = "Heart Disease & Pregnancy"
    assert split_hdp._slugify(value) == "heart-disease-and-pregnancy"


def test_infer_metadata_diagnosis() -> None:
    """Metadata inference should identify diagnosis sections."""
    meta = split_hdp._infer_metadata("Diagnosis and Assessment", "section")
    assert meta.category == "diagnosis"
    assert meta.output == "diagnostic_plan"


def test_split_segments_basic() -> None:
    """Segment splitting should detect numeric and backmatter headings."""
    lines = [
        "Cover Page",
        "## 1 INTRODUCTION",
        "Intro text",
        "## 2 Diagnosis",
        "Diag text",
        "## REFERENCES",
        "Ref text",
    ]

    segments = split_hdp._split_segments(lines)
    keys = [seg.key for seg in segments]

    assert keys[0] == "0.0"
    assert "1" in keys
    assert "2" in keys
    assert "references" in keys
