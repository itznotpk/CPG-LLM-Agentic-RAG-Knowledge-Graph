"""
ICD-11 DDx Ingestion Script

Parses markdown file with ICD-11 codes and inserts into Neon vector DB.
ONLY operates on icd11_codes table - does NOT modify any other tables.
"""

import asyncio
import re
import os
import sys
from pathlib import Path

# Add parent directory to path to import from agent
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

import asyncpg
from agent.providers import get_embedding_client, get_embedding_model


async def parse_icd11_markdown(filepath: str) -> list[dict]:
    """Parse markdown file to extract ICD-11 codes."""
    codes = []
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Split by ## headers (each code entry)
    entries = re.split(r'\n## ', content)
    
    for entry in entries[1:]:  # Skip the first split (header)
        lines = entry.strip().split('\n')
        if not lines:
            continue
            
        # First line is "HA01.0 Title"
        first_line = lines[0]
        match = re.match(r'^(HA[\w.]+)\s+(.+)$', first_line)
        if not match:
            continue
            
        code = match.group(1)
        title = match.group(2)
        
        # Parse remaining fields
        description = ""
        inclusions = []
        exclusions = []
        parent = ""
        chapter = ""
        
        for line in lines[1:]:
            line = line.strip()
            if line.startswith("Description:"):
                description = line.replace("Description:", "").strip()
            elif line.startswith("Inclusions:"):
                inc_text = line.replace("Inclusions:", "").strip()
                inclusions = [i.strip() for i in inc_text.split(",")]
            elif line.startswith("Exclusions:"):
                exc_text = line.replace("Exclusions:", "").strip()
                exclusions = [e.strip() for e in exc_text.split(",")]
            elif line.startswith("Parent:"):
                parent = line.replace("Parent:", "").strip()
            elif line.startswith("Chapter:"):
                chapter = line.replace("Chapter:", "").strip()
        
        codes.append({
            "code": code,
            "title": title,
            "description": description,
            "inclusions": inclusions,
            "exclusions": exclusions,
            "parent_code": parent,
            "chapter": chapter
        })
    
    return codes


def create_embedding_text(code_data: dict) -> str:
    """Create text for embedding from code data."""
    parts = [code_data["title"]]
    
    if code_data["description"]:
        parts.append(code_data["description"])
    
    if code_data["inclusions"]:
        parts.append("Also known as: " + ", ".join(code_data["inclusions"]))
    
    return ". ".join(parts)


async def generate_embedding(text: str) -> list[float]:
    """Generate embedding using the existing embedding model."""
    client = get_embedding_client()
    model_name = get_embedding_model()
    response = await client.embeddings.create(
        input=text,
        model=model_name
    )
    return response.data[0].embedding


async def insert_codes(codes: list[dict]):
    """Insert ICD-11 codes into Neon database."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL not set in environment")
    
    conn = await asyncpg.connect(database_url)
    
    try:
        total = len(codes)
        print(f"\n{'='*60}")
        print(f"📥 Inserting {total} ICD-11 codes into icd11_codes table")
        print(f"{'='*60}\n")
        
        for idx, code_data in enumerate(codes, 1):
            # Generate embedding
            embed_text = create_embedding_text(code_data)
            print(f"[{idx:02d}/{total}] {code_data['code']:12} {code_data['title'][:45]:<45}", end="", flush=True)
            embedding = await generate_embedding(embed_text)
            
            # Insert into database (upsert on code)
            await conn.execute("""
                INSERT INTO icd11_codes (code, title, description, inclusions, exclusions, parent_code, chapter, embedding)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                ON CONFLICT (code) DO UPDATE SET
                    title = EXCLUDED.title,
                    description = EXCLUDED.description,
                    inclusions = EXCLUDED.inclusions,
                    exclusions = EXCLUDED.exclusions,
                    parent_code = EXCLUDED.parent_code,
                    chapter = EXCLUDED.chapter,
                    embedding = EXCLUDED.embedding
            """, 
                code_data["code"],
                code_data["title"],
                code_data["description"],
                code_data["inclusions"],
                code_data["exclusions"],
                code_data["parent_code"],
                code_data["chapter"],
                str(embedding)
            )
            print(" ✓")
        
        print(f"\n{'='*60}")
        print(f"✅ Successfully ingested {total} ICD-11 codes")
        print(f"{'='*60}\n")
        
    finally:
        await conn.close()


async def main():
    # Get markdown file path
    data_dir = Path(__file__).parent / "data"
    md_file = data_dir / "ha00_sexual_dysfunctions.md"
    
    if not md_file.exists():
        print(f"❌ File not found: {md_file}")
        return
    
    print(f"📖 Parsing {md_file}...")
    codes = await parse_icd11_markdown(str(md_file))
    print(f"   Found {len(codes)} ICD-11 codes")
    
    if codes:
        await insert_codes(codes)


if __name__ == "__main__":
    asyncio.run(main())
