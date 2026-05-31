"""Seed curated drug-safety edges for the T2DM + HFrEF (metabolic heart failure) case.

Case 8's showcase is dual-source safety flags (source="llm" + source="graph"). The KG
shipped with no edges linking the diabetes meds to heart failure, so `clinical_graph_lookup`
returned 0 graph flags and only the LLM side fired. This seeds the curated rules the
Malaysian CPGs support, in the exact node/edge shape the Stage-6 queries match:

  - drug×comorbidity (graph_clinical._query_comorbidity_flags):
      (:Drug)-[:CONTRAINDICATED_WITH|REQUIRES_MONITORING {severity, evidence, source_document}]->(:Condition)
      matched on d.name_normalised IN candidates  AND  c.name_normalised IN comorbidities
  - drug×drug (graph_clinical._query_drug_interactions):
      (:Drug)-[:INTERACTS_WITH {...}]-(:Drug)  matched on name_normalised

Matching is exact-equality on `name_normalised` (plain lowercase), so the Condition node
must carry name_normalised='heart failure with reduced ef' to match the case comorbidity
"Heart failure with reduced EF". Idempotent — safe to re-run.

Usage:  python scripts/seed_metabolic_hf_safety_edges.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.graph_clinical import _get_neo4j_session  # noqa: E402

T2DM_CPG = "CPG Management of Type 2 Diabetes Mellitus (6th Edition)"
HF_CPG = "CPG Management of Heart Failure (5th Edition)"

# (cypher, params) tuples — each MERGE is idempotent.
STATEMENTS: list[tuple[str, dict]] = [
    # --- Condition node the case comorbidity normalises onto ---
    (
        """
        MERGE (c:Condition {name_normalised: 'heart failure with reduced ef'})
        ON CREATE SET c.name = 'Heart Failure with Reduced Ejection Fraction',
                      c.seeded = true
        RETURN c.name AS name
        """,
        {},
    ),
    # --- Sulfonylurea class node (gliclazide expands to this in _DRUG_CLASS_EXPANSION) ---
    (
        """
        MERGE (d:Drug {name_normalised: 'sulfonylurea'})
        ON CREATE SET d.name = 'Sulfonylurea', d.seeded = true
        RETURN d.name AS name
        """,
        {},
    ),
    # --- gliclazide × HFrEF : sulfonylureas associated with excess HF morbidity ---
    (
        """
        MATCH (d:Drug {name_normalised: 'gliclazide'})
        MATCH (c:Condition {name_normalised: 'heart failure with reduced ef'})
        MERGE (d)-[r:CONTRAINDICATED_WITH]->(c)
        SET r.severity = 'MODERATE',
            r.evidence = $ev,
            r.evidence_list = [$ev],
            r.source_document = $src,
            r.seeded = true
        RETURN d.name AS d, c.name AS c
        """,
        {
            "ev": "Sulfonylureas (e.g. gliclazide) are associated with increased heart-failure "
                  "morbidity and hypoglycaemia; prefer agents with proven cardiovascular benefit "
                  "(SGLT2 inhibitor) in HFrEF and review for de-escalation.",
            "src": T2DM_CPG,
        },
    ),
    # --- sulfonylurea (class) × HFrEF : same rule at class level ---
    (
        """
        MATCH (d:Drug {name_normalised: 'sulfonylurea'})
        MATCH (c:Condition {name_normalised: 'heart failure with reduced ef'})
        MERGE (d)-[r:CONTRAINDICATED_WITH]->(c)
        SET r.severity = 'MODERATE',
            r.evidence = $ev,
            r.evidence_list = [$ev],
            r.source_document = $src,
            r.seeded = true
        RETURN d.name AS d, c.name AS c
        """,
        {
            "ev": "Sulfonylureas are associated with increased heart-failure risk; prefer SGLT2 "
                  "inhibitors with proven HFrEF benefit.",
            "src": T2DM_CPG,
        },
    ),
    # --- metformin × HFrEF : permitted at eGFR >=30, monitor renal function (downgraded caution) ---
    (
        """
        MATCH (d:Drug {name_normalised: 'metformin'})
        MATCH (c:Condition {name_normalised: 'heart failure with reduced ef'})
        MERGE (d)-[r:REQUIRES_MONITORING]->(c)
        SET r.severity = 'MINOR',
            r.evidence = $ev,
            r.evidence_list = [$ev],
            r.source_document = $src,
            r.seeded = true
        RETURN d.name AS d, c.name AS c
        """,
        {
            "ev": "Metformin is permitted in stable heart failure at eGFR >=30 mL/min/1.73m2; "
                  "monitor renal function and withhold during acute decompensation or AKI risk "
                  "(historical HF contraindication now downgraded).",
            "src": HF_CPG,
        },
    ),
    # --- gliclazide × dapagliflozin : additive hypoglycaemia risk (drug-drug) ---
    (
        """
        MATCH (a:Drug {name_normalised: 'gliclazide'})
        MATCH (b:Drug {name_normalised: 'dapagliflozin'})
        MERGE (a)-[r:INTERACTS_WITH]->(b)
        SET r.severity = 'MODERATE',
            r.evidence = $ev,
            r.evidence_list = [$ev],
            r.source_document = $src,
            r.seeded = true
        RETURN a.name AS a, b.name AS b
        """,
        {
            "ev": "Adding an SGLT2 inhibitor (dapagliflozin) to a sulfonylurea (gliclazide) "
                  "increases hypoglycaemia risk; consider sulfonylurea dose reduction.",
            "src": T2DM_CPG,
        },
    ),
]


async def main() -> int:
    ctx = await _get_neo4j_session()
    async with ctx as session:
        for cypher, params in STATEMENTS:
            result = await session.run(cypher, **params)
            rows = [rec.data() async for rec in result]
            label = " ".join(cypher.split())[:70]
            print(f"OK  {rows if rows else '(no rows)'}   <- {label}...")
    print("\nSeed complete (idempotent).")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
