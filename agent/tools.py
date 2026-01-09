"""
Tools for the Pydantic AI agent.
"""

import logging
from typing import List, Dict, Any, Optional


from pydantic import BaseModel, Field
from dotenv import load_dotenv

from .db_utils import (
    vector_search,
    hybrid_search
)
from .graph_utils import (
    search_knowledge_graph,
    get_entity_relationships
)
from .models import ChunkResult, GraphSearchResult
from .providers import get_embedding_client, get_embedding_model

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

# Initialize embedding client with flexible provider
embedding_client = get_embedding_client()
EMBEDDING_MODEL = get_embedding_model()


async def generate_embedding(text: str) -> List[float]:
    """
    Generate embedding for text using OpenAI.
    
    Args:
        text: Text to embed
    
    Returns:
        Embedding vector
    """
    try:
        response = await embedding_client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=text
        )
        return response.data[0].embedding
    except Exception as e:
        logger.error(f"Failed to generate embedding: {e}")
        raise


# Tool Input Models
class VectorSearchInput(BaseModel):
    """Input for vector search tool."""
    query: str = Field(..., description="Search query")
    limit: int = Field(default=10, description="Maximum number of results")


class GraphSearchInput(BaseModel):
    """Input for graph search tool."""
    query: str = Field(..., description="Search query")


class HybridSearchInput(BaseModel):
    """Input for hybrid search tool."""
    query: str = Field(..., description="Search query")
    limit: int = Field(default=10, description="Maximum number of results")
    text_weight: float = Field(default=0.3, description="Weight for text similarity (0-1)")


class EntityRelationshipInput(BaseModel):
    """Input for entity relationship query."""
    entity_name: str = Field(..., description="Name of the entity")
    depth: int = Field(default=2, description="Maximum traversal depth")


class DrugInteractionInput(BaseModel):
    """Input for drug interaction/contraindication search."""
    drug_name: str = Field(..., description="Name of the drug to check (e.g., 'Sildenafil', 'Tadalafil')")


class TreatmentRecommendationInput(BaseModel):
    """Input for treatment recommendation search."""
    condition: str = Field(..., description="Medical condition to get recommendations for (e.g., 'Erectile Dysfunction', 'Vasculogenic ED')")


# Tool Implementation Functions
async def vector_search_tool(input_data: VectorSearchInput) -> List[ChunkResult]:
    """
    Perform vector similarity search.
    
    Args:
        input_data: Search parameters
    
    Returns:
        List of matching chunks
    """
    try:
        # Generate embedding for the query
        embedding = await generate_embedding(input_data.query)
        
        # Perform vector search
        results = await vector_search(
            embedding=embedding,
            limit=input_data.limit
        )

        # Convert to ChunkResult models
        return [
            ChunkResult(
                chunk_id=str(r["chunk_id"]),
                document_id=str(r["document_id"]),
                content=r["content"],
                score=r["similarity"],
                metadata=r["metadata"],
                document_title=r["document_title"],
                document_source=r["document_source"]
            )
            for r in results
        ]
        
    except Exception as e:
        logger.error(f"Vector search failed: {e}")
        return []


async def graph_search_tool(input_data: GraphSearchInput) -> List[GraphSearchResult]:
    """
    Search the knowledge graph.
    
    Args:
        input_data: Search parameters
    
    Returns:
        List of graph search results
    """
    try:
        results = await search_knowledge_graph(
            query=input_data.query
        )
        
        # Convert to GraphSearchResult models
        return [
            GraphSearchResult(
                fact=r["fact"],
                uuid=r["uuid"],
                valid_at=r.get("valid_at"),
                invalid_at=r.get("invalid_at"),
                source_node_uuid=r.get("source_node_uuid")
            )
            for r in results
        ]
        
    except Exception as e:
        logger.error(f"Graph search failed: {e}")
        return []


async def hybrid_search_tool(input_data: HybridSearchInput) -> List[ChunkResult]:
    """
    Perform hybrid search (vector + keyword).
    
    Args:
        input_data: Search parameters
    
    Returns:
        List of matching chunks
    """
    try:
        # Generate embedding for the query
        embedding = await generate_embedding(input_data.query)
        
        # Perform hybrid search
        results = await hybrid_search(
            embedding=embedding,
            query_text=input_data.query,
            limit=input_data.limit,
            text_weight=input_data.text_weight
        )
        
        # Convert to ChunkResult models
        return [
            ChunkResult(
                chunk_id=str(r["chunk_id"]),
                document_id=str(r["document_id"]),
                content=r["content"],
                score=r["combined_score"],
                metadata=r["metadata"],
                document_title=r["document_title"],
                document_source=r["document_source"]
            )
            for r in results
        ]
        
    except Exception as e:
        logger.error(f"Hybrid search failed: {e}")
        return []


async def get_entity_relationships_tool(input_data: EntityRelationshipInput) -> Dict[str, Any]:
    """
    Get relationships for an entity from the knowledge graph.
    
    Args:
        input_data: Entity relationship parameters
    
    Returns:
        Entity relationships
    """
    try:
        return await get_entity_relationships(
            entity=input_data.entity_name,
            depth=input_data.depth
        )
        
    except Exception as e:
        logger.error(f"Entity relationship query failed: {e}")
        return {
            "central_entity": input_data.entity_name,
            "related_entities": [],
            "relationships": [],
            "depth": input_data.depth,
            "error": str(e)
        }


# Combined search function for agent use
async def perform_comprehensive_search(
    query: str,
    use_vector: bool = True,
    use_graph: bool = True,
    limit: int = 10
) -> Dict[str, Any]:
    """
    Perform a comprehensive search using multiple methods.
    
    Args:
        query: Search query
        use_vector: Whether to use vector search
        use_graph: Whether to use graph search
        limit: Maximum results per search type (only applies to vector search)
    
    Returns:
        Combined search results
    """
    results = {
        "query": query,
        "vector_results": [],
        "graph_results": [],
        "total_results": 0
    }
    
    tasks = []
    
    if use_vector:
        tasks.append(vector_search_tool(VectorSearchInput(query=query, limit=limit)))
    
    if use_graph:
        tasks.append(graph_search_tool(GraphSearchInput(query=query)))
    
    if tasks:
        search_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        if use_vector and not isinstance(search_results[0], Exception):
            results["vector_results"] = search_results[0]
        
        if use_graph:
            graph_idx = 1 if use_vector else 0
            if not isinstance(search_results[graph_idx], Exception):
                results["graph_results"] = search_results[graph_idx]
    
    results["total_results"] = len(results["vector_results"]) + len(results["graph_results"])
    
    return results


# =============================================================================
# DRUG AND TREATMENT TOOLS
# =============================================================================

async def get_drug_info_tool(input_data: DrugInteractionInput) -> Dict[str, Any]:
    """
    Get comprehensive information about a drug by dynamically searching
    the knowledge graph and document chunks.
    
    This is fully dynamic - no hardcoded drug data. All information comes from:
    1. Knowledge graph relationships (CONTRAINDICATED_WITH, HAS_DOSAGE, CAUSES)
    2. Vector search on document chunks
    
    Args:
        input_data: Drug name to look up
    
    Returns:
        Drug information with contraindications, dosages, side effects from the knowledge base
    """
    drug = input_data.drug_name
    
    result = {
        "drug_name": drug,
        "contraindications": [],
        "dosages": [],
        "adverse_events": [],
        "related_facts": [],
        "related_content": []
    }
    
    # 1. Search knowledge graph for drug relationships
    try:
        graph_results = await graph_search_tool(GraphSearchInput(
            query=f"{drug} contraindication dosage adverse effect side effect"
        ))
        
        for fact_result in graph_results:
            fact = fact_result.fact.lower() if hasattr(fact_result, 'fact') else str(fact_result).lower()
            result["related_facts"].append(fact_result.fact if hasattr(fact_result, 'fact') else str(fact_result))
            
            # Categorize facts based on content
            if 'contraindicated' in fact or 'avoid' in fact or 'must not' in fact:
                result["contraindications"].append(fact_result.fact if hasattr(fact_result, 'fact') else str(fact_result))
            elif 'dosage' in fact or 'dose' in fact or 'mg' in fact:
                result["dosages"].append(fact_result.fact if hasattr(fact_result, 'fact') else str(fact_result))
            elif 'adverse' in fact or 'side effect' in fact or 'cause' in fact or 'headache' in fact:
                result["adverse_events"].append(fact_result.fact if hasattr(fact_result, 'fact') else str(fact_result))
                
    except Exception as e:
        logger.warning(f"Graph search failed for {drug}: {e}")
    
    # 2. Get entity relationships from graph
    try:
        relationships = await get_entity_relationships_tool(EntityRelationshipInput(
            entity_name=drug,
            depth=2
        ))
        
        for rel in relationships.get("relationships", []):
            rel_type = rel.get("type", "")
            target = rel.get("target", "")
            
            if rel_type == "CONTRAINDICATED_WITH":
                result["contraindications"].append(f"Contraindicated with {target}")
            elif rel_type == "HAS_DOSAGE":
                result["dosages"].append(target)
            elif rel_type == "CAUSES":
                result["adverse_events"].append(target)
                
    except Exception as e:
        logger.warning(f"Entity relationship query failed for {drug}: {e}")
    
    # 3. Search vector DB for related content
    try:
        search_results = await vector_search_tool(VectorSearchInput(
            query=f"{drug} dosage contraindication adverse effect side effect",
            limit=5
        ))
        result["related_content"] = [
            {"content": r.content[:500], "document": r.document_title, "score": r.score}
            for r in search_results
        ]
    except Exception as e:
        logger.warning(f"Vector search failed for {drug}: {e}")
    
    # Remove duplicates
    result["contraindications"] = list(set(result["contraindications"]))
    result["dosages"] = list(set(result["dosages"]))
    result["adverse_events"] = list(set(result["adverse_events"]))
    
    return result



async def get_treatment_recommendations_tool(input_data: TreatmentRecommendationInput) -> Dict[str, Any]:
    """
    Get treatment recommendations for a specific condition.
    
    Args:
        input_data: Condition to search for
    
    Returns:
        Treatment recommendations from CPG content
    """
    # Search for treatment content
    query = f"treatment recommendation {input_data.condition}"
    
    try:
        # Use vector search to find relevant treatment content
        vector_results = await vector_search_tool(VectorSearchInput(
            query=query,
            limit=10
        ))
        
        # Also search knowledge graph for related facts
        graph_results = await graph_search_tool(GraphSearchInput(
            query=f"{input_data.condition} treatment"
        ))
        
        recommendations = []
        for r in vector_results:
            recommendations.append({
                "content": r.content[:500],
                "document": r.document_title,
                "score": r.score
            })
        
        return {
            "condition": input_data.condition,
            "recommendations": recommendations,
            "related_facts": [r.fact for r in graph_results[:5]] if graph_results else [],
            "total_found": len(vector_results)
        }
        
    except Exception as e:
        logger.error(f"Treatment recommendations search failed: {e}")
        return {
            "condition": input_data.condition,
            "recommendations": [],
            "error": str(e)
        }


async def get_chunk_with_context_tool(chunk_id: str) -> Dict[str, Any]:
    """
    Get a chunk with its parent section context for better understanding.
    
    Args:
        chunk_id: UUID of the chunk
    
    Returns:
        Chunk content with parent context
    """
    from .db_utils import db_pool
    
    try:
        async with db_pool.acquire() as conn:
            result = await conn.fetchrow(
                """
                SELECT * FROM get_chunk_with_parent_context($1::uuid)
                """,
                chunk_id
            )
            
            if result:
                return {
                    "chunk_id": str(result["chunk_id"]),
                    "content": result["content"],
                    "parent_content": result["parent_content"],
                    "section_hierarchy": result["section_hierarchy"],
                    "full_context": result["full_context"]
                }
            
            return {"error": "Chunk not found"}
            
    except Exception as e:
        logger.error(f"Failed to get chunk with context: {e}")
        return {"error": str(e)}