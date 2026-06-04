"""One-off cleanup: delete the false `Metformin -[:CONTRAINDICATED_WITH]-> Gestational Diabetes Mellitus` edge.

Root cause (see CLAUDE.md "Gap G"): the extractor mis-attributed the clause
"metformin is contraindicated or unacceptable" — which is a *trigger for
starting insulin* inside an `Insulin should be initiated when:` bullet list —
as a contraindication of metformin against the chunk's section topic (GDM).
The same CPG carries the correct RECOMMENDED_FOR / INDICATED_FOR edges for
the same pair, so this single edge is the lone false-positive.

Targeted: keyed on chunk_id so we don't touch any other edge.
"""
import asyncio
from dotenv import load_dotenv
load_dotenv()
from agent.graph_clinical import _get_neo4j_session

BAD_CHUNK = "fb30fe79-7d90-4a0d-9290-12cda5e5559a"

async def main():
    ctx = await _get_neo4j_session()
    async with ctx as s:
        # First, show what we're about to delete (audit trail in stdout).
        peek = await s.run(
            """MATCH (d)-[r:CONTRAINDICATED_WITH]->(c)
               WHERE d.name_normalised = 'metformin'
                 AND c.name_normalised = 'gestational diabetes mellitus'
                 AND (r.cpg_chunk_id = $cid OR $cid IN coalesce(r.cpg_chunk_ids, []))
               RETURN d.name AS d, c.name AS c, r.cpg_chunk_id AS chunk_id,
                      r.cpg_chunk_ids AS chunk_ids, r.evidence AS evidence,
                      r.source_document AS src""",
            cid=BAD_CHUNK,
        )
        rows = [rec async for rec in peek]
        if not rows:
            print("Nothing to delete — edge already absent.")
            return
        for r in rows:
            print(f"DELETE TARGET: {r['d']} -[:CONTRAINDICATED_WITH]-> {r['c']}")
            print(f"  src     = {r['src']}")
            print(f"  chunk   = {r['chunk_id']}")
            print(f"  chunks  = {r['chunk_ids']}")
            print(f"  evidence= {r['evidence']!r}")
        # Delete by chunk_id match (covers both single chunk_id and chunk_ids list cases).
        result = await s.run(
            """MATCH (d)-[r:CONTRAINDICATED_WITH]->(c)
               WHERE d.name_normalised = 'metformin'
                 AND c.name_normalised = 'gestational diabetes mellitus'
                 AND (r.cpg_chunk_id = $cid OR $cid IN coalesce(r.cpg_chunk_ids, []))
               DELETE r
               RETURN count(*) AS deleted""",
            cid=BAD_CHUNK,
        )
        rec = await result.single()
        print(f"\nDeleted {rec['deleted']} edge(s).")

asyncio.run(main())
