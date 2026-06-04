"""
Shared name normalisation for the KG write side (ingestion/graph_builder.py)
and read side (agent/graph_clinical.py).

The MERGE key in Neo4j is `name_normalised`. Both sides MUST produce the same
string for the same logical entity, or read queries miss nodes that were
correctly written. Keep the pipeline here, import it from both sides.
"""

import re
from typing import Tuple

# Known clinical abbreviation -> canonical full form mapping.
# When the LLM extracts "DCCV" in one chunk and "Direct Current Cardioversion"
# in another, both resolve to the same canonical name so MERGE creates one node.
_ABBREV_MAP = {
    "af": "Atrial Fibrillation",
    "afl": "Atrial Flutter",
    "hf": "Heart Failure",
    "vka": "Vitamin K Antagonist",
    "oac": "Oral Anticoagulant",
    "dccv": "Direct Current Cardioversion",
    "inr": "International Normalized Ratio",
    "tia": "Transient Ischaemic Attack",
    "lmwh": "Low Molecular Weight Heparin",
    "ecg": "Electrocardiography",
    "toe": "Transoesophageal Echocardiography",
    "laa": "Left Atrial Appendage",
    "tte": "Transthoracic Echocardiography",
    "ufh": "Unfractionated Heparin",
    "pci": "Percutaneous Coronary Intervention",
    "bms": "Bare Metal Stent",
    "acs": "Acute Coronary Syndrome",
    "nstemi": "Non-ST Elevation Myocardial Infarction",
    "lvef": "Left Ventricular Ejection Fraction",
    "la": "Left Atrium",
    "lv": "Left Ventricle",
}

_PROTECTED_PLURAL_SUFFIXES = ("ss", "us", "is", "sis", "ics", "ies")


def canonical_form(name: str) -> Tuple[str, str]:
    """Apply the shared canonical pipeline.

    Returns (display_name, name_normalised) where name_normalised is the
    Neo4j MERGE key. The pipeline:
      1. strip whitespace
      2. expand abbreviation if lowered name is in _ABBREV_MAP
      3. title-case
      4. de-pluralise trailing 's' (only for simple cases, len > 4, suffix
         not in {ss, us, is, sis, ics, ies})
      5. name_normalised = display_name.lower()
    """
    if not name:
        return "", ""

    s = name.strip()
    lowered = s.lower()

    if lowered in _ABBREV_MAP:
        display = _ABBREV_MAP[lowered]
    else:
        display = s.title()
        if (
            len(display) > 4
            and display.endswith("s")
            and not display.lower().endswith(_PROTECTED_PLURAL_SUFFIXES)
        ):
            display = display[:-1]

    return display, display.lower()


def clean_user_input(name: str) -> str:
    """Defensive cleaning for clinician-supplied names before canonicalising.

    LLM-extracted triple subjects/objects are already clean entity names, so
    the write side does NOT run this. Read-side inputs (patient meds,
    comorbidities, allergies) may contain dose strings or brand parentheticals
    that the graph never stored, so we strip those before canonical_form().

      "Sildenafil (Viagra)" -> "Sildenafil"
      "warfarin 5 mg daily" -> "warfarin"
    """
    if not name:
        return ""
    s = name.strip()
    s = re.sub(r"\s*\([^)]*\)", "", s)
    s = re.sub(r"\s+\d+\s*mg.*$", "", s, flags=re.IGNORECASE)
    return s.strip()


def normalise_for_lookup(name: str) -> str:
    """Read-side: clean user input then return the name_normalised MERGE key."""
    cleaned = clean_user_input(name)
    _, key = canonical_form(cleaned)
    return key
