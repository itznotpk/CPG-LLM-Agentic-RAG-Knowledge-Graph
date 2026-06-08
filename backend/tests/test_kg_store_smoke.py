"""
§4.3.1 Grounding-store integrity smoke test (Neo4j knowledge graph).

The Neo4j arm of §4.3.1 has direct *unit* tests (relation-extraction guardrails,
the prescribing navigator, the avoid-arm class expansion) and *runtime* coverage
(the SAF stress suite, the INF-01 outage probe), but — like pgvector before
`test_grounding_store_smoke.py` — it had no standalone **live-graph** connectivity
-and-integrity check. This is that check: it asserts, in isolation, the schema and
node/edge invariants the Stage 4.5 inject and Stage 6 verify arms silently depend
on, so a paused Aura instance, a dropped edge type, or a node missing its match
key surfaces as a named store-level failure rather than as "the KG returned zero
flags this run" several layers up.

It deliberately does NOT assert a *high* `INTERACTS_WITH` count: the documented
DDI sparsity (~290 edges over ~1,630 drug nodes, because edges come only from CPG
prose) is a known, by-design property recorded in §4.3.1 and Figure 4.3, and is
precisely why Stage 6 runs two independent critics. Asserting abundance here would
contradict the report's own honest caveat.

LIVE GRAPH ONLY — skipped automatically when NEO4J_URI is unset (so the mocked
unit suite and DB-less CI runs are unaffected). Run explicitly with:

    cd backend; pytest tests/test_kg_store_smoke.py -m integration
"""

from __future__ import annotations

import os

import pytest
import pytest_asyncio

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.getenv("NEO4J_URI"),
        reason="KG store smoke test requires a live NEO4J_URI",
    ),
]

# Node labels the Stage 4.5 / Stage 6 Cypher reads against. Each must be present
# and non-empty or the corresponding arm has nothing to match.
REQUIRED_NODE_LABELS = ["Drug", "Condition"]

# Relationship types the pipeline depends on, grouped by the arm that reads them:
#   AVOID arm (clinical_graph_lookup / _kg_verify_plan): CONTRAINDICATED_WITH, INTERACTS_WITH
#   monitoring:                                          REQUIRES_MONITORING
#   PREFER arm (graph_navigator):                        FIRST_LINE_FOR, RECOMMENDED_FOR
#   referral arm (lookup_referrals):                     REQUIRES_REFERRAL
REQUIRED_REL_TYPES = [
    "CONTRAINDICATED_WITH",
    "INTERACTS_WITH",
    "REQUIRES_MONITORING",
    "FIRST_LINE_FOR",
    "RECOMMENDED_FOR",
    "REQUIRES_REFERRAL",
]


@pytest_asyncio.fixture
async def kg_session():
    """Per-test Neo4j session, driver config mirroring _get_neo4j_session()."""
    from neo4j import AsyncGraphDatabase

    driver = AsyncGraphDatabase.driver(
        os.environ["NEO4J_URI"],
        auth=(os.environ["NEO4J_USER"], os.environ["NEO4J_PASSWORD"]),
        max_connection_lifetime=300,
        keep_alive=True,
        liveness_check_timeout=30,
        connection_acquisition_timeout=60,
    )
    db = os.getenv("NEO4J_DATABASE") or None
    try:
        async with driver.session(database=db) as session:
            yield session
    finally:
        await driver.close()


async def _scalar(session, cypher: str, **params) -> int:
    res = await session.run(cypher, **params)
    row = await res.single()
    return row[0]


# ---------------------------------------------------------------------------
# Connectivity (Aura idle-drop / paused-instance guard)
# ---------------------------------------------------------------------------

async def test_round_trip_query(kg_session):
    """
    A trivial round-trip proves the driver can reach and query the graph. This is
    the KG analogue of the pgvector probes guard: when Aura is paused or has dropped
    an idle connection, Stage 4.5 silently returns zero flags — this names that.
    """
    ok = await _scalar(kg_session, "RETURN 1 AS ok")
    assert ok == 1


# ---------------------------------------------------------------------------
# Schema presence — required node labels and relationship types
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("label", REQUIRED_NODE_LABELS)
async def test_node_label_present_and_non_empty(kg_session, label):
    count = await _scalar(kg_session, f"MATCH (n:{label}) RETURN count(n)")
    assert count > 0, f"no :{label} nodes — its arm has nothing to match against"


@pytest.mark.parametrize("rel_type", REQUIRED_REL_TYPES)
async def test_relationship_type_present_and_non_empty(kg_session, rel_type):
    count = await _scalar(kg_session, f"MATCH ()-[r:{rel_type}]->() RETURN count(r)")
    assert count > 0, (
        f"no :{rel_type} edges — the arm reading this relationship is wired to an empty set"
    )


# ---------------------------------------------------------------------------
# Match-key integrity — name_normalised is the IN-clause key
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("label", REQUIRED_NODE_LABELS)
async def test_nodes_have_normalised_name(kg_session, label):
    """
    Every Stage 4.5 / Stage 6 Cypher matches on `name_normalised IN $...`. A node
    missing that property can never be matched, so it is silently invisible to the
    safety arms — assert full coverage on the labels those arms key off.
    """
    missing = await _scalar(
        kg_session,
        f"MATCH (n:{label}) WHERE n.name_normalised IS NULL RETURN count(n)",
    )
    assert missing == 0, (
        f"{missing} :{label} node(s) have NULL name_normalised — unmatchable by the safety Cypher"
    )


async def test_no_null_endpoint_contraindication_edges(kg_session):
    """
    Relation-extraction integrity (§3.3.1): a CONTRAINDICATED_WITH edge whose
    endpoint has no name_normalised cannot be surfaced and is a hallmark of a
    section-anchor hallucination. There should be none.
    """
    bad = await _scalar(
        kg_session,
        """
        MATCH (a)-[:CONTRAINDICATED_WITH]->(b)
        WHERE a.name_normalised IS NULL OR b.name_normalised IS NULL
        RETURN count(*)
        """,
    )
    assert bad == 0, f"{bad} CONTRAINDICATED_WITH edge(s) have an unnamed endpoint"


# ---------------------------------------------------------------------------
# Drug-safety arm is wired (NOT an abundance assertion — see module docstring)
# ---------------------------------------------------------------------------

async def test_interacts_with_arm_is_wired(kg_session):
    """
    INTERACTS_WITH must merely *exist* (>0), confirming the DDI arm is wired. We do
    NOT assert a large count: the ~290-edge sparsity over ~1,630 drug nodes is the
    documented, by-design caveat of §4.3.1 (edges extracted only from CPG prose),
    and is why Stage 6 also runs an independent LLM critic. Asserting abundance
    would contradict the report's own honest limitation.
    """
    count = await _scalar(kg_session, "MATCH ()-[r:INTERACTS_WITH]->() RETURN count(r)")
    assert count > 0, "INTERACTS_WITH arm is empty — the graph DDI source is not wired at all"
