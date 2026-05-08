"""Parse unstructured patient text into structured fields for DDx queries.

Heuristic parser for:
- age, sex
- BMI, BP, heart rate
- symptoms
- comorbidities
- medications

Outputs both structured JSON and a normalized query string for DDx embedding.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, asdict
from typing import List, Optional


AGE_RE = re.compile(r"\b(\d{1,3})\s*(?:yo|y/o|yrs?|years?|year)\s*(?:-?\s*old)?\b", re.IGNORECASE)
BMI_RE = re.compile(r"\b(?:BMI|body\s*mass\s*index)\s*(?:is|=|:)?\s*(\d{1,2}(?:\.\d+)?)\b", re.IGNORECASE)
BP_LABEL_RE = re.compile(r"\b(?:BP|blood\s*pressure)\b", re.IGNORECASE)
BP_RE = re.compile(
    r"\b(?:BP|blood\s*pressure)\s*[:=]?\s*(\d{2,3})\s*(?:/|over|-)\s*(\d{2,3})\b",
    re.IGNORECASE,
)
BP_RATIO_RE = re.compile(r"\b(\d{2,3})\s*/\s*(\d{2,3})\b")
HR_RE = re.compile(r"\b(?:HR|heart\s*rate|pulse)\s*[:=]?\s*(\d{2,3})(?:\s*bpm)?\b", re.IGNORECASE)

SEX_RE = re.compile(r"\b(male|female|man|woman|boy|girl)\b", re.IGNORECASE)

SYMPTOM_PATTERNS = [
    r"symptoms?\s*[:=]\s*([^.;\n]+)",
    r"symptoms?\s+include\s+([^.;\n]+)",
    r"sx\s*[:=]\s*([^.;\n]+)",
    r"complains\s+of\s+([^.;\n]+)",
    r"c/o\s+([^.;\n]+)",
    r"presenting\s+with\s+([^.;\n]+)",
    r"pt\s+(?:with|has)\s+([^.;\n]+)",
    r"reports\s+([^.;\n]+)",
]

COMORBIDITY_PATTERNS = [
    r"history\s+of\s+([^.;\n]+)",
    r"past\s+medical\s+history\s*[:=]\s*([^.;\n]+)",
    r"PMH\s*[:=]\s*([^.;\n]+)",
    r"hx\s*[:=]\s*([^.;\n]+)",
    r"known\s+([^.;\n]+)",
    r"diagnosed\s+with\s+([^.;\n]+)",
    r"comorbidit(?:y|ies)\s*[:=]\s*([^.;\n]+)",
]

MEDICATION_PATTERNS = [
    r"current\s+medications?\s*[:=]\s*([^.;\n]+)",
    r"medications?\s*[:=]\s*([^.;\n]+)",
    r"meds\s*[:=]\s*([^.;\n]+)",
    r"takes\s+([^.;\n]+)",
    r"on\s+([^.;\n]+)\b",  # fallback: very loose
]


COMORBIDITY_MAP = {
    "htn": "hypertension",
    "dm": "diabetes mellitus",
    "t2dm": "type 2 diabetes mellitus",
    "t1dm": "type 1 diabetes mellitus",
    "cad": "coronary artery disease",
    "ihd": "ischaemic heart disease",
    "hld": "hyperlipidaemia",
    "copd": "chronic obstructive pulmonary disease",
    "ckd": "chronic kidney disease",
}


@dataclass
class PatientInfo:
    age: Optional[int] = None
    sex: Optional[str] = None
    bmi: Optional[float] = None
    bp: Optional[str] = None
    heart_rate: Optional[int] = None
    symptoms: List[str] = None
    comorbidities: List[str] = None
    medications: List[str] = None

    def __post_init__(self):
        self.symptoms = self.symptoms or []
        self.comorbidities = self.comorbidities or []
        self.medications = self.medications or []


def _normalize_list(text: str) -> List[str]:
    if not text:
        return []
    parts = re.split(r"[,;/]\s*|\band\b\s*", text, flags=re.IGNORECASE)
    cleaned = []
    for p in parts:
        v = p.strip(" .;:\t\n")
        if v:
            cleaned.append(v)
    return cleaned


def _normalize_comorbidities(items: List[str]) -> List[str]:
    normalized = []
    for item in items:
        key = item.strip().lower()
        normalized.append(COMORBIDITY_MAP.get(key, item))
    return normalized


def _first_match(patterns: List[str], text: str) -> Optional[str]:
    for pat in patterns:
        m = re.search(pat, text, flags=re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return None


def parse_patient_text(text: str) -> PatientInfo:
    info = PatientInfo()

    m = AGE_RE.search(text)
    if m:
        info.age = int(m.group(1))

    sex_match = SEX_RE.search(text)
    if sex_match:
        s = sex_match.group(1).lower()
        info.sex = "male" if s in {"male", "man", "boy"} else "female"

    m = BMI_RE.search(text)
    if m:
        info.bmi = float(m.group(1))

    m = BP_RE.search(text)
    if m:
        info.bp = f"{m.group(1)}/{m.group(2)}"
    else:
        # If BP label missing but ratio exists, assume first ratio is BP
        if BP_LABEL_RE.search(text):
            ratio = BP_RATIO_RE.search(text)
            if ratio:
                info.bp = f"{ratio.group(1)}/{ratio.group(2)}"

    m = HR_RE.search(text)
    if m:
        info.heart_rate = int(m.group(1))

    symptoms_raw = _first_match(SYMPTOM_PATTERNS, text)
    if symptoms_raw:
        info.symptoms = _normalize_list(symptoms_raw)

    comorb_raw = _first_match(COMORBIDITY_PATTERNS, text)
    if comorb_raw:
        info.comorbidities = _normalize_comorbidities(_normalize_list(comorb_raw))

    meds_raw = _first_match(MEDICATION_PATTERNS, text)
    if meds_raw:
        info.medications = _normalize_list(meds_raw)

    return info


def format_patient_query(info: PatientInfo) -> str:
    parts: List[str] = []
    if info.age:
        parts.append(f"{info.age} year old")
    if info.sex:
        parts.append(info.sex)
    if info.bmi is not None:
        parts.append(f"BMI {info.bmi}")
    if info.bp:
        parts.append(f"BP {info.bp}")
    if info.heart_rate:
        parts.append(f"heart rate {info.heart_rate}")
    if info.symptoms:
        parts.append("symptoms: " + ", ".join(info.symptoms))
    if info.comorbidities:
        parts.append("comorbidities: " + ", ".join(info.comorbidities))
    if info.medications:
        parts.append("medications: " + ", ".join(info.medications))
    return " ".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(description="Parse unstructured patient text into structured DDx input")
    parser.add_argument("text", nargs="*", help="Unstructured patient text")
    args = parser.parse_args()

    if not args.text:
        print("Enter patient text (empty line to quit):")
        while True:
            raw_text = input("> ").strip()
            if not raw_text:
                return 0
            info = parse_patient_text(raw_text)
            output = {
                "structured": asdict(info),
                "formatted_query": format_patient_query(info),
            }
            print(json.dumps(output, indent=2))
        return 0

    raw_text = " ".join(args.text)
    info = parse_patient_text(raw_text)

    output = {
        "structured": asdict(info),
        "formatted_query": format_patient_query(info),
    }
    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
