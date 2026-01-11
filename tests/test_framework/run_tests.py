"""
Main runner for ED CPG RAG testing framework.
Generates test cases and evaluates the RAG system.
"""

import asyncio
import sys
from pathlib import Path

# Add parent dir to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tests.test_framework.generate_test_cases import generate_test_cases, save_test_cases
from tests.test_framework.evaluate_rag import run_evaluation, calculate_metrics, save_results, print_comparison


async def main():
    """Run full test suite: generate cases and evaluate."""
    print("=" * 70)
    print("🧪 ED CPG RAG TESTING FRAMEWORK")
    print("=" * 70)
    
    # Step 1: Generate test cases
    print("\n📝 STEP 1: Generating test cases with Gemini...")
    print("-" * 70)
    
    test_cases = generate_test_cases(num_cases=15)
    
    if not test_cases:
        print("❌ Failed to generate test cases. Exiting.")
        sys.exit(1)
    
    output_path = save_test_cases(test_cases)
    
    print(f"\n✅ Generated {len(test_cases)} test cases")
    print(f"   Saved to: {output_path}")
    
    # Print sample case
    if test_cases:
        sample = test_cases[0]
        print(f"\n📋 Sample Case: {sample.get('case_id', 'TC001')}")
        print(f"   Patient: {sample.get('patient_demographics', {})}")
        print(f"   Query: {sample.get('clinical_query', '')[:80]}...")
    
    # Step 2: Evaluate RAG system
    print("\n" + "=" * 70)
    print("🔬 STEP 2: Evaluating RAG System...")
    print("-" * 70)
    
    results = await run_evaluation(output_path.name)
    metrics = calculate_metrics(results)
    
    # Step 3: Print results
    print("\n" + "=" * 70)
    print("📊 EVALUATION RESULTS")
    print("=" * 70)
    
    print(f"\n📈 Overall Metrics:")
    print(f"   Total Cases:     {metrics['total_cases']}")
    print(f"   Successful:      {metrics['successful']}")
    print(f"   Failed:          {metrics['failed']}")
    print(f"   Success Rate:    {metrics['success_rate']}")
    print(f"   Avg Response:    {metrics['avg_response_time_ms']:.0f}ms")
    print(f"   Avg Sources:     {metrics['avg_sources_per_response']:.1f}")
    
    print(f"\n📊 By Difficulty:")
    for diff, stats in metrics.get("by_difficulty", {}).items():
        rate = (stats['success']/stats['total']*100) if stats['total'] else 0
        print(f"   {diff}: {stats['success']}/{stats['total']} ({rate:.0f}%)")
    
    print(f"\n🎯 By Clinical Focus:")
    for focus, stats in metrics.get("by_clinical_focus", {}).items():
        rate = (stats['success']/stats['total']*100) if stats['total'] else 0
        print(f"   {focus}: {stats['success']}/{stats['total']} ({rate:.0f}%)")
    
    # Print detailed comparison
    print_comparison(results)
    
    # Save results
    save_results(results, metrics)
    
    print("\n" + "=" * 70)
    print("✅ Testing complete!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())

