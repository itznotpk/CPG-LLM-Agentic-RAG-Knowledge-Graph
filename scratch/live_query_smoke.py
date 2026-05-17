"""
Live agent-tool smoke test for the 5 recently-ingested CPGs.

Calls vector_search_tool and graph_search_tool directly (bypassing the FastAPI
layer) with one realistic clinical query per CPG. For each query we print:
  - top-3 vector results: similarity, document title, content preview
  - top-5 graph facts: relation triples from the KG

This exercises the same retrieval path the agent uses at runtime.
"""

import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")
from dotenv import load_dotenv

load_dotenv()

from agent.db_utils import initialize_database, close_database
from agent.graph_utils import initialize_graph, close_graph
from agent.tools import (
    vector_search_tool,
    graph_search_tool,
    VectorSearchInput,
    GraphSearchInput,
)

QUERIES = [
    ("Safe Use of Medication in Anaesthesia",
     "What are best practices to prevent medication errors during anaesthesia?"),
    ("Pre-Anaesthetic Assessment",
     "What investigations should be performed before anaesthesia for a patient with diabetes?"),
    ("Patient Safety & Minimal Monitoring",
     "What are the minimum monitoring standards required during general anaesthesia?"),
    ("Cancer Pain (2nd Edition)",
     "What is the first-line opioid for moderate to severe cancer pain in adults?"),
    ("Atrial Fibrillation",
     "When is anticoagulation indicated for stroke prevention in atrial fibrillation?"),
]


async def run_one(label: str, query: str):
    print("\n" + "=" * 78)
    print(f"CPG: {label}")
    print(f"Q  : {query}")
    print("=" * 78)

    print("\n[VECTOR SEARCH — top 3]")
    try:
        vs = await vector_search_tool(VectorSearchInput(query=query, limit=3))
        if not vs:
            print("  (no results)")
        for r in vs:
            title = r.document_title or "(no title)"
            preview = r.content.replace("\n", " ")[:120]
            print(f"  sim={r.score:.4f} | {title[:55]}")
            print(f"    {preview}...")
    except Exception as e:
        print(f"  ! vector_search_tool error: {e}")

    print("\n[GRAPH SEARCH — top 5 facts]")
    try:
        gs = await graph_search_tool(GraphSearchInput(query=query))
        if not gs:
            print("  (no facts)")
        for r in gs[:5]:
            print(f"  - {r.fact}")
    except Exception as e:
        print(f"  ! graph_search_tool error: {e}")


async def main():
    print("Initializing DB + graph clients...")
    await initialize_database()
    await initialize_graph()
    try:
        for label, q in QUERIES:
            await run_one(label, q)
    finally:
        await close_database()
        await close_graph()
    print("\n" + "=" * 78)
    print("DONE")
    print("=" * 78)


if __name__ == "__main__":
    asyncio.run(main())
