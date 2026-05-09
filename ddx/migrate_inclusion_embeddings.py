"""
Migration Script: Add Inclusion Embeddings to icd11_codes table

Run this ONCE to update existing records with pre-computed embeddings
for each inclusion term.
"""

import asyncio
import os
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

import asyncpg
from agent.providers import get_embedding_client, get_embedding_model


async def generate_embedding(text: str) -> list[float]:
    """Generate embedding using the configured provider.

    Provider-aware: branches on EMBEDDING_PROVIDER. Inlined here (rather than
    importing from agent.tools) to avoid agent.graph_utils -> graphiti_core,
    a heavy dependency this script doesn't need.
    """
    embedding_provider = os.getenv("EMBEDDING_PROVIDER", "openai").lower()

    if embedding_provider == "bedrock":
        import boto3

        bedrock_client = boto3.client(
            "bedrock-runtime",
            region_name=os.getenv("AWS_REGION", "us-east-1"),
        )
        model_id = os.getenv("EMBEDDING_MODEL", "amazon.titan-embed-text-v1")
        dimension = int(os.getenv("VECTOR_DIMENSION", "1536"))

        def _invoke():
            if "titan" in model_id:
                body = json.dumps({"inputText": text})
            elif "cohere" in model_id:
                body = json.dumps({"texts": [text], "input_type": "search_query"})
            else:
                raise ValueError(f"Unsupported Bedrock embedding model: {model_id}")

            response = bedrock_client.invoke_model(
                modelId=model_id,
                body=body,
                contentType="application/json",
                accept="application/json",
            )
            result = json.loads(response["body"].read())

            if "titan" in model_id:
                return result["embedding"][:dimension]
            return result["embeddings"][0][:dimension]

        return await asyncio.to_thread(_invoke)

    # OpenAI-compatible fallback
    client = get_embedding_client()
    model_name = get_embedding_model()
    response = await client.embeddings.create(input=text, model=model_name)
    return response.data[0].embedding


async def migrate():
    """Add inclusion_embeddings column and populate it."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL not set in environment")
    
    conn = await asyncpg.connect(database_url)
    
    try:
        # Step 1: Add column if not exists
        print("📋 Step 1: Adding inclusion_embeddings column...")
        try:
            await conn.execute("""
                ALTER TABLE icd11_codes 
                ADD COLUMN IF NOT EXISTS inclusion_embeddings JSONB DEFAULT '{}'
            """)
            print("   ✅ Column added (or already exists)")
        except Exception as e:
            print(f"   ⚠️ Column may already exist: {e}")
        
        # Step 2: Get all codes with inclusions
        print("\n📋 Step 2: Fetching codes with inclusions...")
        rows = await conn.fetch("""
            SELECT code, title, inclusions 
            FROM icd11_codes 
            WHERE inclusions IS NOT NULL AND array_length(inclusions, 1) > 0
        """)
        print(f"   Found {len(rows)} codes with inclusions")
        
        # Step 3: Generate embeddings for each inclusion term
        print("\n📋 Step 3: Generating inclusion embeddings...")
        updated = 0
        
        for row in rows:
            code = row["code"]
            inclusions = row["inclusions"]
            
            inclusion_embeddings = {}
            for inc_text in inclusions:
                if inc_text.strip():
                    print(f"   🔄 {code}: Embedding '{inc_text[:40]}...'")
                    emb = await generate_embedding(inc_text)
                    inclusion_embeddings[inc_text] = emb
            
            # Update the row
            if inclusion_embeddings:
                await conn.execute("""
                    UPDATE icd11_codes 
                    SET inclusion_embeddings = $1
                    WHERE code = $2
                """, json.dumps(inclusion_embeddings), code)
                updated += 1
        
        print(f"\n✅ Migration complete! Updated {updated} codes with inclusion embeddings.")
        
    finally:
        await conn.close()


if __name__ == "__main__":
    print("=" * 60)
    print("  ICD-11 Inclusion Embeddings Migration")
    print("=" * 60)
    asyncio.run(migrate())
