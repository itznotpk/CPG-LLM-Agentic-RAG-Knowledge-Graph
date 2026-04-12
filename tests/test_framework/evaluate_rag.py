"""
Evaluate the ED CPG RAG system against generated test cases.
Compares RAG system output with ground truth answers.
"""

import os
import json
import asyncio
import httpx
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from dotenv import load_dotenv

load_dotenv()

RAG_API_URL = os.getenv("RAG_API_URL", "http://localhost:8058")
TEST_DIR = Path(__file__).parent / "generated_cases"
RESULTS_DIR = Path(__file__).parent / "evaluation_results"
RESULTS_DIR.mkdir(exist_ok=True)


@dataclass
class EvaluationResult:
    """Result of evaluating a single test case."""
    case_id: str
    query: str
    difficulty: str
    clinical_focus: str
    ground_truth: Dict[str, str]
    rag_response: Dict[str, str]
    sources_used: List[Dict[str, Any]]
    response_time_ms: float
    success: bool
    error: Optional[str] = None


async def call_rag_api(query: str) -> Dict[str, Any]:
    """Call the RAG API with a clinical query."""
    async with httpx.AsyncClient(timeout=120.0) as client:
        start = datetime.now()
        response = await client.post(f"{RAG_API_URL}/chat", json={"message": query})
        elapsed = (datetime.now() - start).total_seconds() * 1000
        if response.status_code != 200:
            raise Exception(f"API error: {response.status_code}")
        data = response.json()
        data["response_time_ms"] = elapsed
        return data


def parse_rag_response(message: str) -> Dict[str, str]:
    """Parse RAG response into sections."""
    sections = {"summary": "", "followup_care_plan": "", "medications": "", "next_steps": ""}
    parts = message.split("##")
    for part in parts:
        lower = part.lower().strip()
        if lower.startswith("summary"):
            sections["summary"] = part.replace("Summary", "", 1).strip()
        elif "follow" in lower and "plan" in lower:
            sections["followup_care_plan"] = part.split("\n", 1)[-1].strip()
        elif lower.startswith("medication"):
            sections["medications"] = part.split("\n", 1)[-1].strip()
        elif "next" in lower and "step" in lower:
            sections["next_steps"] = part.split("\n", 1)[-1].strip()
    if not any(sections.values()):
        sections["summary"] = message
    return sections


async def evaluate_test_case(test_case: Dict[str, Any]) -> EvaluationResult:
    """Evaluate a single test case."""
    case_id = test_case.get("case_id", "unknown")
    query = test_case.get("clinical_query", "")
    print(f"  Evaluating {case_id}: {query[:50]}...")
    try:
        response = await call_rag_api(query)
        rag_sections = parse_rag_response(response.get("message", ""))
        return EvaluationResult(
            case_id=case_id, query=query,
            difficulty=test_case.get("difficulty", "unknown"),
            clinical_focus=test_case.get("clinical_focus", "unknown"),
            ground_truth=test_case.get("ground_truth", {}),
            rag_response=rag_sections,
            sources_used=response.get("sources", []),
            response_time_ms=response.get("response_time_ms", 0),
            success=True
        )
    except Exception as e:
        return EvaluationResult(
            case_id=case_id, query=query,
            difficulty=test_case.get("difficulty", "unknown"),
            clinical_focus=test_case.get("clinical_focus", "unknown"),
            ground_truth=test_case.get("ground_truth", {}),
            rag_response={}, sources_used=[], response_time_ms=0,
            success=False, error=str(e)
        )


async def run_evaluation(test_cases_file: str) -> List[EvaluationResult]:
    """Run evaluation on all test cases."""
    test_path = TEST_DIR / test_cases_file
    with open(test_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    test_cases = data.get("test_cases", [])
    print(f"Loaded {len(test_cases)} test cases")
    
    results = []
    for i, tc in enumerate(test_cases, 1):
        print(f"\n[{i}/{len(test_cases)}]", end="")
        result = await evaluate_test_case(tc)
        results.append(result)
        await asyncio.sleep(1)
    return results


def calculate_metrics(results: List[EvaluationResult]) -> Dict[str, Any]:
    """Calculate evaluation metrics."""
    total = len(results)
    successful = sum(1 for r in results if r.success)
    response_times = [r.response_time_ms for r in results if r.success]
    avg_time = sum(response_times) / len(response_times) if response_times else 0
    
    by_difficulty = {}
    for r in results:
        d = r.difficulty
        by_difficulty.setdefault(d, {"total": 0, "success": 0})
        by_difficulty[d]["total"] += 1
        if r.success:
            by_difficulty[d]["success"] += 1
    
    by_focus = {}
    for r in results:
        f = r.clinical_focus
        by_focus.setdefault(f, {"total": 0, "success": 0})
        by_focus[f]["total"] += 1
        if r.success:
            by_focus[f]["success"] += 1
    
    total_sources = sum(len(r.sources_used) for r in results if r.success)
    
    return {
        "total_cases": total, "successful": successful, "failed": total - successful,
        "success_rate": f"{(successful/total)*100:.1f}%" if total else "0%",
        "avg_response_time_ms": round(avg_time, 2),
        "avg_sources_per_response": round(total_sources / successful, 2) if successful else 0,
        "by_difficulty": by_difficulty, "by_clinical_focus": by_focus
    }


def save_results(results: List[EvaluationResult], metrics: Dict[str, Any]) -> Path:
    """Save evaluation results to JSON."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = RESULTS_DIR / f"evaluation_{ts}.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({"evaluated_at": datetime.now().isoformat(), "metrics": metrics,
                   "results": [asdict(r) for r in results]}, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to: {output_path}")
    return output_path


def print_comparison(results: List[EvaluationResult]):
    """Print detailed comparison."""
    print("\n" + "=" * 80)
    print("DETAILED COMPARISON: Ground Truth vs RAG Response")
    print("=" * 80)
    for r in results:
        if not r.success:
            print(f"\n❌ {r.case_id}: FAILED - {r.error}")
            continue
        print(f"\n{'─' * 80}")
        print(f"📋 {r.case_id} | {r.difficulty} | {r.clinical_focus}")
        print(f"🔍 Query: {r.query[:80]}...")
        print(f"⏱️  {r.response_time_ms:.0f}ms | {len(r.sources_used)} sources")
        for sec in ["summary", "medications", "next_steps"]:
            gt = str(r.ground_truth.get(sec, "N/A"))[:150]
            rag = str(r.rag_response.get(sec, "N/A"))[:150]
            print(f"\n  📌 {sec.upper()}:")
            print(f"     GT:  {gt}...")
            print(f"     RAG: {rag}...")


async def main():
    """Main evaluation function."""
    import sys
    print("=" * 60)
    print("ED CPG RAG System Evaluation")
    print("=" * 60)

    test_files = list(TEST_DIR.glob("test_cases_*.json"))
    if not test_files:
        print("No test cases found! Run generate_test_cases.py first.")
        sys.exit(1)

    latest = max(test_files, key=lambda p: p.stat().st_mtime)
    print(f"Using: {latest.name}")

    results = await run_evaluation(latest.name)
    metrics = calculate_metrics(results)

    print("\n" + "=" * 60)
    print("EVALUATION SUMMARY")
    print("=" * 60)
    print(f"Total: {metrics['total_cases']} | Success: {metrics['successful']} | Failed: {metrics['failed']}")
    print(f"Rate: {metrics['success_rate']} | Avg time: {metrics['avg_response_time_ms']:.0f}ms")

    print_comparison(results)
    save_results(results, metrics)


if __name__ == "__main__":
    asyncio.run(main())

