"""
ICD-11 DDx Search Script

Vector search for differential diagnosis suggestions.
Input: Patient symptoms text
Output: Top 5 ICD-11 code suggestions with similarity scores
"""

import asyncio
import os
import sys
from pathlib import Path

# Add parent directory to path to import from agent
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

import asyncpg
from agent.providers import get_embedding_client, get_embedding_model


async def generate_embedding(text: str) -> list[float]:
    """Generate embedding using the existing embedding model."""
    client = get_embedding_client()
    model_name = get_embedding_model()
    response = await client.embeddings.create(
        input=text,
        model=model_name
    )
    return response.data[0].embedding


def apply_tabulation_filter(
    candidates: list[dict],
    query_symptoms: str
) -> list[dict]:
    """
    Apply Morbidity Tabulation Layer filter to candidates.
    
    Rules:
    - REMOVE if query matches any Exclusion (NO list) - strict boundary
    - BOOST if query matches any Inclusion (YES list) - synonym match
    """
    filtered = []
    query_lower = query_symptoms.lower()
    query_words = set(query_lower.split())
    
    for candidate in candidates:
        # Check NO list first (strict removal)
        exclusions = candidate.get("exclusions") or []
        excluded = False
        for exc in exclusions:
            exc_lower = exc.lower()
            # Check if exclusion term appears in query
            if exc_lower in query_lower or any(word in exc_lower for word in query_words if len(word) > 3):
                excluded = True
                candidate["filter_reason"] = f"Excluded: {exc}"
                break
        
        if excluded:
            continue  # Skip this candidate
        
        # Check YES list (boost confidence if synonym matches)
        inclusions = candidate.get("inclusions") or []
        inclusion_match = False
        matched_inclusion = None
        for inc in inclusions:
            inc_lower = inc.lower()
            if inc_lower in query_lower or any(word in inc_lower for word in query_words if len(word) > 3):
                inclusion_match = True
                matched_inclusion = inc
                break
        
        candidate["inclusion_match"] = inclusion_match
        candidate["matched_term"] = matched_inclusion
        filtered.append(candidate)
    
    # Sort: inclusion matches first, then by similarity descending
    filtered.sort(
        key=lambda x: (not x.get("inclusion_match", False), -x["similarity"])
    )
    
    return filtered


async def search_ddx(symptoms: str, top_k: int = 5) -> list[dict]:
    """
    Search for differential diagnosis suggestions based on symptoms.
    
    Uses two-stage retrieval:
    1. Vector similarity search (retrieves 10 candidates)
    2. Morbidity Tabulation Layer filter (returns top 5)
    
    Args:
        symptoms: Patient symptoms text
        top_k: Number of suggestions to return (default 5)
    
    Returns:
        List of ICD-11 code suggestions with similarity scores
    """
    database_url = os.getenv("DATABASE_URL")
    
    # Generate embedding for symptoms
    embedding = await generate_embedding(symptoms)

    if not database_url:
        print("\n⚠️  WARNING: DATABASE_URL not set. Running in MOCK/DEMO mode.")
        print("    Returning static example results.")
        
        # Simulated Database Candidates (Rich Data)
        # This allows us to test the 'apply_tabulation_filter' logic without a real DB.
        mock_candidates = [
            {
                "code": "HA00.0",
                "title": "Hypoactive sexual desire dysfunction",
                "description": "Hypoactive sexual desire dysfunction is characterized by deficiency or absence of sexual thoughts or fantasies and desire for sexual activity.",
                "inclusions": ["Frigidity in female", "Hypoactive sexual desire disorder"],
                "exclusions": ["Sexual aversion disorder"],
                "similarity": 0.9234
            },
            {
                "code": "HA02.0",
                "title": "Anorgasmia",
                "description": "Anorgasmia is characterised by the absence or marked infrequency of the orgasm experience or markedly diminished intensity of orgasmic sensations.",
                "inclusions": ["Psychogenic anorgasmy", "Inhibited orgasm"],
                "exclusions": [],
                "similarity": 0.8100 
            },
            {
                "code": "HA01",
                "title": "Sexual arousal dysfunctions",
                "description": "Sexual arousal dysfunctions are characterized by the inability to attain or maintain adequate lubrication or vasocongestion responses.",
                "inclusions": ["Female sexual arousal dysfunction"],
                "exclusions": [],
                "similarity": 0.7500
            },
            {
                "code": "HA03",
                "title": "Ejaculatory dysfunctions",
                "description": "Ejaculatory dysfunctions involve the inability to ejaculate or premature ejaculation during sexual activity.",
                "inclusions": ["Premature ejaculation", "Delayed ejaculation"],
                "exclusions": [],
                "similarity": 0.6500
            },
            {
                "code": "HA04",
                "title": "Sexual pain disorders",
                "description": "Persistent or recurrent pain associated with sexual intercourse or other sexual activities.",
                "inclusions": ["Dyspareunia", "Vaginismus"],
                "exclusions": [],
                "similarity": 0.5400
            }
        ]
        
        # Apply the ACTUAL Morbidity Tabulation Layer logic to these mock candidates
        print("    [Mock] applying tabulation filter logic...")
        filtered = apply_tabulation_filter(mock_candidates, symptoms)
        
        # Format for output (ensure description length, etc)
        suggestions = []
        for item in filtered: # return all matches from mock db
            desc = item["description"] or ""
            suggestions.append({
                "code": item["code"],
                "title": item["title"],
                "description": desc, # print_results handles wrapping
                "similarity": item["similarity"],
                "inclusion_match": item.get("inclusion_match", False),
                "matched_term": item.get("matched_term")
            })
            
        return suggestions[:top_k] # Filter to top K
    
    conn = await asyncpg.connect(database_url)
    
    try:
        # Fetch more candidates than needed for filtering
        fetch_limit = top_k * 2  # Get 10 for filtering down to 5
        
        results = await conn.fetch("""
            SELECT 
                code,
                title,
                description,
                inclusions,
                exclusions,
                1 - (embedding <=> $1::vector) AS similarity
            FROM icd11_codes
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> $1::vector
            LIMIT $2
        """, str(embedding), fetch_limit)
        
        candidates = []
        for row in results:
            candidates.append({
                "code": row["code"],
                "title": row["title"],
                "description": row["description"],
                "inclusions": row["inclusions"],
                "exclusions": row["exclusions"],
                "similarity": round(float(row["similarity"]), 4)
            })
        
        # Apply Morbidity Tabulation Layer filter
        filtered = apply_tabulation_filter(candidates, symptoms)
        
        # Prepare final suggestions (limit to top_k)
        suggestions = []
        for item in filtered[:top_k]:
            desc = item["description"] or ""
            suggestions.append({
                "code": item["code"],
                "title": item["title"],
                "description": desc[:200] + "..." if len(desc) > 200 else desc,
                "similarity": item["similarity"],
                "inclusion_match": item.get("inclusion_match", False),
                "matched_term": item.get("matched_term")
            })
        
        return suggestions
        
    finally:
        await conn.close()


def print_header():
    """Print the DDx search header."""
    print("\n" + "═" * 70)
    print("  🏥  ICD-11 DIFFERENTIAL DIAGNOSIS ENGINE  🏥")
    print("     Chapter 17: Conditions Related to Sexual Health")
    print("═" * 70)
    print("\nEnter patient symptoms/condition to get top 5 ICD-11 diagnoses.")
    print("Type 'q', 'exit' or 'quit' to exit.\n")


def print_results(symptoms: str, suggestions: list[dict]):
    """Print formatted DDx results."""
    print("\n" + "━" * 80)
    print(f"  📋 QUERY: {symptoms}")
    print("━" * 80)
    
    if not suggestions:
        print("  ⚠️  No matching diagnoses found.\n")
        return
    
    print()
    
    for i, s in enumerate(suggestions, 1):
        similarity_pct = s['similarity'] * 100
        
        # Color-code similarity
        if similarity_pct >= 85: indicator = "🟢"
        elif similarity_pct >= 70: indicator = "🟡"
        else: indicator = "🟠"

        # --- GRID CONSTANTS ---
        # Total Inner Width: 76 (8 + 1 + 12 + 1 + 54 = 76)
        W_LEFT = 8
        W_MID = 12
        W_RIGHT = 54
        TOTAL_W = W_LEFT + 1 + W_MID + 1 + W_RIGHT # = 76
        
        # 1. Left Column (8 chars visual)
        # Content: " 🟢 #1"
        idx_str = f"#{i}"
        left_content = f" {indicator} {idx_str}"
        # Visual width calculation:
        # space(1) + emoji(2) + space(1) + idx(len)
        vis_w = 1 + 2 + 1 + len(idx_str)
        pad = W_LEFT - vis_w
        left_str = left_content + (" " * max(0, pad))

        # 2. Middle Column (12 chars)
        # Content: " HA00.0" (space prefix)
        code_raw = f" {s['code']}"
        pad = W_MID - len(code_raw)
        mid_str = code_raw + (" " * max(0, pad))
        
        # 3. Right Column (54 chars)
        # Content: " Title...   [MATCH] "
        match_badge = "[MATCH] " if s.get('inclusion_match') else ""
        if match_badge:
            match_badge = " " + match_badge # ensure space before badge
            
        # Available space for title = 54 - len(badge) - 1 (left space)
        avail_title = W_RIGHT - len(match_badge) - 1
        
        title = s['title']
        if len(title) > avail_title:
             title = title[:avail_title-3] + "..."
        
        right_content_start = f" {title}"
        # Pad effectively
        current_len = 1 + len(title) + len(match_badge)
        pad = W_RIGHT - current_len
        right_str = right_content_start + (" " * max(0, pad)) + match_badge

        # --- PRINT HEADER ---
        # Note: No spaces inside f-string around separators!
        print(f"  ┌{'─'*W_LEFT}┬{'─'*W_MID}┬{'─'*W_RIGHT}┐")
        print(f"  │{left_str}│{mid_str}│{right_str}│")
        print(f"  ├{'─'*TOTAL_W}┤")
        
        # --- PRINT BODY ---
        
        # 1. Confidence Line
        conf_raw = f"Confidence: {similarity_pct:5.1f}%"
        pad = TOTAL_W - len(conf_raw)
        print(f"  │{conf_raw}{' ' * max(0, pad)}│")
        
        # 2. Matched Term
        if s.get('matched_term'):
             term_raw = f" ↳ Term found: \"{s['matched_term']}\""
             pad = TOTAL_W - len(term_raw)
             print(f"  │{term_raw}{' ' * max(0, pad)}│")

        # 3. Description
        desc = s['description'] or "No description available."
        # Indent description by 1 space
        
        words = desc.split()
        current_line = " " # Start with space
        lines = []
        for word in words:
            # Check length against TOTAL_W
            if len(current_line) + len(word) + 1 <= TOTAL_W:
                current_line += (word + " ")
            else:
                lines.append(current_line)
                current_line = " " + word + " "
        lines.append(current_line)
        
        for line in lines[:2]: # Show max 2 lines
             line = line.strip() 
             pad = TOTAL_W - len(line)
             print(f"  │{line}{' ' * max(0, pad)}│")
             
        # Bottom Border
        print(f"  └{'─'*TOTAL_W}┘")
    
    print()


async def interactive_cli():
    """Run interactive CLI for DDx search."""
    print_header()
    
    while True:
        try:
            symptoms = input("🩺 Patient condition: ").strip()
            
            if not symptoms:
                continue
            
            if symptoms.lower() in ['exit', 'quit', 'q']:
                print("\n👋 Goodbye!\n")
                break
            
            print(f"\n🔍 Searching ICD-11 database...")
            suggestions = await search_ddx(symptoms, top_k=5)
            print_results(symptoms, suggestions)
            
        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!\n")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}\n")


async def main():
    # If command line args provided, run single query
    if len(sys.argv) > 1:
        symptoms = " ".join(sys.argv[1:])
        print(f"\n🔍 Searching ICD-11 database for: {symptoms}")
        suggestions = await search_ddx(symptoms, top_k=5)
        print_results(symptoms, suggestions)
    else:
        # Run interactive CLI
        await interactive_cli()


if __name__ == "__main__":
    asyncio.run(main())
