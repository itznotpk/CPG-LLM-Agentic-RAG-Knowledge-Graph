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
import re


# Clinical abbreviation → ICD-11 full-form expansion.
# Applied BEFORE embedding so short comorbidity strings ("CKD Stage 3", "T2DM")
# match the ICD-11 title vectors which use full clinical terminology.
# Patterns are word-boundary regex; replacements are lowercase.
_CLINICAL_SYNONYMS: list[tuple[str, str]] = [
    (r"\bckd\b",         "chronic kidney disease"),
    (r"\bt2dm\b",        "type 2 diabetes mellitus"),
    (r"\bt1dm\b",        "type 1 diabetes mellitus"),
    (r"\bdm\b",          "diabetes mellitus"),
    (r"\bhfpef\b",       "heart failure with preserved ejection fraction"),
    (r"\bhfref\b",       "heart failure with reduced ejection fraction"),
    (r"\bhfmref\b",      "heart failure with mildly reduced ejection fraction"),
    (r"\bhf\b",          "heart failure"),
    (r"\bchf\b",         "congestive heart failure"),
    (r"\bcad\b",         "coronary artery disease"),
    (r"\bihd\b",         "ischaemic heart disease"),
    (r"\bacs\b",         "acute coronary syndrome"),
    (r"\bmi\b",          "myocardial infarction"),
    (r"\bstemi\b",       "st elevation myocardial infarction"),
    (r"\bnstemi\b",      "non st elevation myocardial infarction"),
    (r"\bafib\b",        "atrial fibrillation"),
    (r"\baf\b",          "atrial fibrillation"),
    (r"\bcopd\b",        "chronic obstructive pulmonary disease"),
    (r"\bpah\b",         "pulmonary arterial hypertension"),
    (r"\bhtn\b",         "hypertension"),
    (r"\bdvt\b",         "deep vein thrombosis"),
    (r"\bpe\b",          "pulmonary embolism"),
    (r"\bcva\b",         "cerebrovascular accident"),
    (r"\btia\b",         "transient ischaemic attack"),
    (r"\bckd\s*stage\s*\d+\b", "chronic kidney disease"),  # strip stage qualifier — ICD encodes stage separately
]


def _expand_clinical_synonyms(text: str) -> str:
    """Expand common clinical abbreviations to ICD-11 full-form terminology."""
    for pattern, replacement in _CLINICAL_SYNONYMS:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text


def normalize_query(query: str) -> str:
    """
    Normalize user query for consistent embedding results.

    Preprocessing:
    - Strip leading/trailing whitespace
    - Remove trailing punctuation (.,!?;:)
    - Collapse multiple spaces to single space
    - Convert to lowercase
    - Remove special characters except hyphens and apostrophes
    - Expand clinical abbreviations (CKD → chronic kidney disease, T2DM → type 2 diabetes mellitus)
    """
    if not query:
        return ""

    # Strip whitespace
    query = query.strip()

    # Remove trailing punctuation
    query = query.rstrip('.,!?;:')

    # Collapse multiple spaces
    query = re.sub(r'\s+', ' ', query)

    # Remove special characters (keep alphanumeric, spaces, hyphens, apostrophes)
    query = re.sub(r"[^\w\s\-']", '', query)

    # Lowercase
    query = query.lower()

    # Expand clinical abbreviations BEFORE embedding so vector search matches full ICD-11 titles
    query = _expand_clinical_synonyms(query)

    # Collapse any whitespace introduced by multi-word expansions
    query = re.sub(r'\s+', ' ', query).strip()

    return query


def validate_query(query: str) -> tuple[bool, str]:
    """
    Validate query before processing.
    
    Returns:
        (is_valid, error_message)
    """
    if not query:
        return False, "Query cannot be empty"
    
    if len(query) < 3:
        return False, "Query too short (minimum 3 characters)"
    
    if len(query) > 500:
        return False, "Query too long (maximum 500 characters)"
    
    # Check if query has meaningful content (at least one letter)
    if not re.search(r'[a-zA-Z]', query):
        return False, "Query must contain at least one letter"
    
    return True, ""


async def generate_embedding(text: str) -> list[float]:
    """Generate embedding using the configured embedding provider."""
    embedding_provider = os.getenv("EMBEDDING_PROVIDER", "openai").lower()

    if embedding_provider == "bedrock":
        import boto3
        import json
        import asyncio

        client = boto3.client("bedrock-runtime", region_name=os.getenv("AWS_REGION", "us-east-1"))
        model_id = os.getenv("EMBEDDING_MODEL", "amazon.titan-embed-text-v1")
        dimension = int(os.getenv("VECTOR_DIMENSION", "1536"))

        def _invoke():
            if "titan" in model_id:
                body = json.dumps({"inputText": text})
            elif "cohere" in model_id:
                body = json.dumps({"texts": [text], "input_type": "search_query"})
            else:
                raise ValueError(f"Unsupported Bedrock embedding model: {model_id}")

            response = client.invoke_model(
                modelId=model_id,
                body=body,
                contentType="application/json",
                accept="application/json",
            )
            result = json.loads(response["body"].read())

            if "titan" in model_id:
                return result.get("embedding")[:dimension]
            if "cohere" in model_id:
                return result.get("embeddings")[0][:dimension]

        return await asyncio.to_thread(_invoke)

    client = get_embedding_client()
    model_name = get_embedding_model()
    response = await client.embeddings.create(
        input=text,
        model=model_name,
    )
    return response.data[0].embedding


import numpy as np

def cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    """Calculate cosine similarity between two vectors."""
    a = np.array(vec1)
    b = np.array(vec2)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def _tokenize(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) > 3}


def _lexical_overlap(query_text: str, title: str, inclusions: list[str] | None, description: str | None = None) -> list[str]:
    query_tokens = _tokenize(query_text)
    if not query_tokens:
        return []

    candidate_text = title or ""
    if description:
        candidate_text += " " + description
    if inclusions:
        candidate_text += " " + " ".join(inclusions)

    candidate_tokens = _tokenize(candidate_text)
    overlap = sorted(query_tokens & candidate_tokens)
    return overlap


def build_reasoning(candidate: dict, query_text: str) -> list[str]:
    reasons: list[str] = []

    sim = candidate.get("similarity")
    if sim is not None:
        reasons.append(f"Vector similarity {sim:.3f}")

    if candidate.get("inclusion_match"):
        matched = candidate.get("matched_term")
        inc_sim = candidate.get("inclusion_similarity")
        if matched:
            if inc_sim:
                reasons.append(f"Inclusion match: {matched} ({inc_sim:.3f})")
            else:
                reasons.append(f"Inclusion match: {matched}")

    overlap = _lexical_overlap(
        query_text,
        candidate.get("title", ""),
        candidate.get("inclusions") or [],
        description=candidate.get("description"),
    )
    if overlap:
        reasons.append("Keyword overlap: " + ", ".join(overlap[:5]))

    # Better labeling for special matches
    if candidate.get("matched_term") == "[DESCRIPTION]":
        # Rename the matched term for the UI reasoning list
        for i, r in enumerate(reasons):
            if "Inclusion match: [DESCRIPTION]" in r:
                reasons[i] = r.replace("Inclusion match: [DESCRIPTION]", "Exact description match")

    return reasons


async def apply_tabulation_filter(
    candidates: list[dict],
    query_symptoms: str,
    query_embedding: list[float],
    inclusion_threshold: float = 0.70
) -> list[dict]:
    """
    Apply Morbidity Tabulation Layer filter to candidates.
    
    Rules:
    - REMOVE if query matches any Exclusion (NO list) - substring match (strict)
    - BOOST if query embedding is similar to Inclusion embedding (semantic match)
    
    Args:
        candidates: List of ICD-11 code candidates from vector search
        query_symptoms: Original query text (for exclusion check)
        query_embedding: Pre-computed embedding of query (for inclusion check)
        inclusion_threshold: Minimum similarity for inclusion match (default 0.70)
    """
    filtered = []
    query_lower = query_symptoms.lower()
    query_words = set(query_lower.split())
    
    for candidate in candidates:
        # Check NO list first (strict removal - substring match)
        exclusions = candidate.get("exclusions") or []
        excluded = False
        for exc in exclusions:
            exc_lower = exc.lower()
            if exc_lower in query_lower or any(word in exc_lower for word in query_words if len(word) > 3):
                excluded = True
                candidate["filter_reason"] = f"Excluded: {exc}"
                break
        
        if excluded:
            continue  # Skip this candidate
        
        # Check YES list using SEMANTIC SIMILARITY
        inclusion_embeddings = candidate.get("inclusion_embeddings") or {}
        inclusion_match = False
        matched_inclusion = None
        match_similarity = 0.0
        
        if inclusion_embeddings and query_embedding:
            for inc_text, inc_emb in inclusion_embeddings.items():
                if inc_emb:
                    sim = cosine_similarity(query_embedding, inc_emb)
                    if sim > inclusion_threshold and sim > match_similarity:
                        inclusion_match = True
                        matched_inclusion = inc_text
                        match_similarity = sim
        
        # Fallback to substring matching if no embeddings available
        if not inclusion_match and not inclusion_embeddings:
            inclusions = candidate.get("inclusions") or []
            for inc in inclusions:
                inc_lower = inc.lower()
                if inc_lower in query_lower or any(word in inc_lower for word in query_words if len(word) > 3):
                    inclusion_match = True
                    matched_inclusion = inc
                    match_similarity = 0.5  # Lower confidence for substring match
                    break
        
        candidate["inclusion_match"] = inclusion_match
        candidate["matched_term"] = matched_inclusion
        candidate["inclusion_similarity"] = round(match_similarity, 3) if match_similarity else None
        filtered.append(candidate)
    
    # Sort: inclusion matches first (by inclusion similarity), then by vector similarity
    filtered.sort(
        key=lambda x: (
            not x.get("inclusion_match", False),
            -(x.get("inclusion_similarity") or 0),
            -x["similarity"]
        )
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
    
    Raises:
        ValueError: If query is invalid
    """
    # Validate query
    is_valid, error_msg = validate_query(symptoms)
    if not is_valid:
        raise ValueError(f"Invalid query: {error_msg}")
    
    # Normalize query for consistent embeddings
    normalized_symptoms = normalize_query(symptoms)
    
    database_url = os.getenv("DATABASE_URL")
    
    # Generate embedding for normalized symptoms
    try:
        embedding = await generate_embedding(normalized_symptoms)
    except Exception as e:
        raise RuntimeError(f"Failed to generate embedding: {e}")

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
        filtered = await apply_tabulation_filter(mock_candidates, normalized_symptoms, embedding)
        
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
                "matched_term": item.get("matched_term"),
                "reasoning": build_reasoning(item, normalized_symptoms)
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
                inclusion_embeddings,
                1 - (embedding <=> $1::vector) AS similarity
            FROM icd11_codes
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> $1::vector
            LIMIT $2
        """, str(embedding), fetch_limit)
        
        candidates = []
        for row in results:
            # Parse inclusion_embeddings from JSONB
            inc_emb_raw = row["inclusion_embeddings"]
            inc_emb = {}
            if inc_emb_raw:
                import json
                inc_emb = json.loads(inc_emb_raw) if isinstance(inc_emb_raw, str) else inc_emb_raw
            
            candidates.append({
                "code": row["code"],
                "title": row["title"],
                "description": row["description"],
                "inclusions": row["inclusions"],
                "exclusions": row["exclusions"],
                "inclusion_embeddings": inc_emb,
                "similarity": round(float(row["similarity"]), 4)
            })
        
        # Apply Morbidity Tabulation Layer filter with semantic matching
        filtered = await apply_tabulation_filter(candidates, normalized_symptoms, embedding)
        
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
                "matched_term": item.get("matched_term"),
                "inclusion_similarity": item.get("inclusion_similarity"),
                "reasoning": build_reasoning(item, normalized_symptoms)
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
             inc_sim = s.get('inclusion_similarity')
             if inc_sim:
                 term_raw = f" ↳ Semantic match: \"{s['matched_term']}\" ({inc_sim*100:.1f}%)"
             else:
                 term_raw = f" ↳ Substring match: \"{s['matched_term']}\""
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
