"""
Generate test cases for ED CPG RAG system using Gemini.
Reads the CPG document and generates realistic clinical scenarios with ground truth answers.
"""

import os
import json
import asyncio
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# Use Gemini via OpenRouter or direct
GEMINI_BASE_URL = os.getenv("LLM_BASE_URL", "https://openrouter.ai/api/v1")
GEMINI_API_KEY = os.getenv("LLM_API_KEY")
GEMINI_MODEL = "google/gemini-2.0-flash-001"

# Output directory
OUTPUT_DIR = Path(__file__).parent / "generated_cases"
OUTPUT_DIR.mkdir(exist_ok=True)


def load_cpg_content() -> str:
    """Load the full CPG document content."""
    cpg_path = Path(__file__).parent.parent.parent / "e-CPG-ED-RAG-Optimized.md"
    
    if not cpg_path.exists():
        # Try loading all markdown sections
        markdown_dir = Path(__file__).parent.parent.parent / "markdown"
        content = ""
        for md_file in sorted(markdown_dir.glob("*.md")):
            content += f"\n\n{'='*50}\n{md_file.name}\n{'='*50}\n"
            content += md_file.read_text(encoding="utf-8")
        return content
    
    return cpg_path.read_text(encoding="utf-8")


GENERATION_PROMPT = """You are a clinical expert creating test cases for an ED (Erectile Dysfunction) CPG RAG system.

Based on the Malaysian ED Clinical Practice Guidelines provided below, generate {num_cases} realistic clinical scenarios.

For EACH scenario, provide:

1. **case_id**: Unique identifier (e.g., "TC001")
2. **patient_demographics**: Age, gender
3. **chief_complaint**: Why the patient is presenting
4. **medical_history**: Relevant conditions (diabetes, hypertension, cardiac, etc.)
5. **current_medications**: List of current medications
6. **vital_signs**: BP, heart rate, BMI
7. **ed_symptoms**: Duration, severity, IIEF-5 score if applicable
8. **clinical_query**: The natural language query a doctor might ask the system

9. **ground_truth**: The expected correct answer based on the CPG, structured as:
   - **summary**: Brief clinical assessment
   - **followup_care_plan**: Recommended follow-up actions
   - **medications**: Drug recommendations with dosages
   - **next_steps**: Immediate clinical actions

10. **key_cpg_references**: Which CPG sections/algorithms apply
11. **difficulty**: "easy", "medium", or "hard"
12. **clinical_focus**: Main topic (e.g., "cardiac_risk", "pde5i_selection", "lifestyle", etc.)

IMPORTANT GUIDELINES:
- Make cases clinically realistic and diverse
- Include cases covering: cardiovascular risk stratification, PDE5i contraindications, lifestyle modifications, treatment failures, special populations (diabetes, post-prostatectomy, etc.)
- Ground truth must be STRICTLY based on the CPG content provided
- Include at least 2-3 "hard" cases with complex comorbidities or contraindications

Return the response as a valid JSON array of test case objects.

---

CPG CONTENT:
{cpg_content}

---

Generate {num_cases} test cases now. Return ONLY valid JSON array, no other text.
"""


def generate_test_cases(num_cases: int = 15) -> List[Dict[str, Any]]:
    """Generate test cases using Gemini."""
    
    print(f"Loading CPG content...")
    cpg_content = load_cpg_content()
    
    # Truncate if too long (Gemini has context limits)
    max_chars = 100000
    if len(cpg_content) > max_chars:
        print(f"Truncating CPG content from {len(cpg_content)} to {max_chars} chars")
        cpg_content = cpg_content[:max_chars]
    
    print(f"CPG content loaded: {len(cpg_content)} characters")
    
    client = OpenAI(
        base_url=GEMINI_BASE_URL,
        api_key=GEMINI_API_KEY
    )
    
    prompt = GENERATION_PROMPT.format(
        num_cases=num_cases,
        cpg_content=cpg_content
    )
    
    print(f"Generating {num_cases} test cases with Gemini...")
    print("This may take 1-2 minutes...")
    
    response = client.chat.completions.create(
        model=GEMINI_MODEL,
        messages=[
            {"role": "system", "content": "You are a clinical expert. Return only valid JSON."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
        max_tokens=8000
    )
    
    response_text = response.choices[0].message.content
    
    # Clean up response (remove markdown code blocks if present)
    if response_text.startswith("```"):
        response_text = response_text.split("```")[1]
        if response_text.startswith("json"):
            response_text = response_text[4:]
    if response_text.endswith("```"):
        response_text = response_text[:-3]
    
    try:
        test_cases = json.loads(response_text.strip())
        print(f"Successfully generated {len(test_cases)} test cases")
        return test_cases
    except json.JSONDecodeError as e:
        print(f"Failed to parse JSON: {e}")
        # Save raw response for debugging
        debug_path = OUTPUT_DIR / "debug_response.txt"
        debug_path.write_text(response_text)
        print(f"Raw response saved to {debug_path}")
        return []


def save_test_cases(test_cases: List[Dict[str, Any]], filename: str = None) -> Path:
    """Save generated test cases to JSON file."""
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"test_cases_{timestamp}.json"
    
    output_path = OUTPUT_DIR / filename
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "generated_at": datetime.now().isoformat(),
            "num_cases": len(test_cases),
            "test_cases": test_cases
        }, f, indent=2, ensure_ascii=False)
    
    print(f"Test cases saved to: {output_path}")
    return output_path


def main():
    """Main function to generate and save test cases."""
    print("=" * 60)
    print("ED CPG RAG Test Case Generator")
    print("=" * 60)
    
    # Generate test cases
    test_cases = generate_test_cases(num_cases=15)
    
    if test_cases:
        # Save to file
        output_path = save_test_cases(test_cases)
        
        # Print summary
        print("\n" + "=" * 60)
        print("GENERATION SUMMARY")
        print("=" * 60)
        print(f"Total cases generated: {len(test_cases)}")
        
        # Count by difficulty
        difficulties = {}
        focuses = {}
        for tc in test_cases:
            diff = tc.get("difficulty", "unknown")
            focus = tc.get("clinical_focus", "unknown")
            difficulties[diff] = difficulties.get(diff, 0) + 1
            focuses[focus] = focuses.get(focus, 0) + 1
        
        print(f"\nBy difficulty: {difficulties}")
        print(f"By clinical focus: {focuses}")
        print(f"\nOutput file: {output_path}")
    else:
        print("No test cases generated. Check the debug output.")


if __name__ == "__main__":
    main()

