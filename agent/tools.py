"""
Tools for the Pydantic AI agent.
"""

import os
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import asyncio

from pydantic import BaseModel, Field
from dotenv import load_dotenv

from .db_utils import (
    vector_search,
    hybrid_search,
    get_document,
    list_documents,
    get_document_chunks
)
from .graph_utils import (
    search_knowledge_graph,
    get_entity_relationships,
    graph_client
)
from .models import ChunkResult, GraphSearchResult, DocumentMetadata
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


class DocumentInput(BaseModel):
    """Input for document retrieval."""
    document_id: str = Field(..., description="Document ID to retrieve")


class DocumentListInput(BaseModel):
    """Input for listing documents."""
    limit: int = Field(default=20, description="Maximum number of documents")
    offset: int = Field(default=0, description="Number of documents to skip")


class EntityRelationshipInput(BaseModel):
    """Input for entity relationship query."""
    entity_name: str = Field(..., description="Name of the entity")
    depth: int = Field(default=2, description="Maximum traversal depth")


class EntityTimelineInput(BaseModel):
    """Input for entity timeline query."""
    entity_name: str = Field(..., description="Name of the entity")
    start_date: Optional[str] = Field(None, description="Start date (ISO format)")
    end_date: Optional[str] = Field(None, description="End date (ISO format)")


# CPG-Specific Tool Input Models
class CPGFilteredSearchInput(BaseModel):
    """Input for CPG filtered search - search with evidence filters."""
    query: str = Field(..., description="Search query for clinical content")
    grade: Optional[str] = Field(None, description="Filter by recommendation grade: 'Grade A', 'Grade B', 'Grade C', or 'Key Recommendation'")
    population: Optional[str] = Field(None, description="Filter by target population: 'General', 'Diabetes', 'Cardiac Disease', 'Elderly', etc.")
    category: Optional[str] = Field(None, description="Filter by category: 'Diagnosis', 'Treatment', 'Referral', 'Monitoring', 'Prevention'")
    recommendations_only: bool = Field(default=False, description="Only return recommendations (graded content)")
    limit: int = Field(default=10, description="Maximum number of results")


class DrugInteractionInput(BaseModel):
    """Input for drug interaction/contraindication search."""
    drug_name: str = Field(..., description="Name of the drug to check (e.g., 'Sildenafil', 'Tadalafil')")


class TreatmentRecommendationInput(BaseModel):
    """Input for treatment recommendation search."""
    condition: str = Field(..., description="Medical condition to get recommendations for (e.g., 'Erectile Dysfunction', 'Vasculogenic ED')")
    population: Optional[str] = Field(None, description="Optional patient population filter (e.g., 'Diabetes', 'Cardiac Disease')")


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


async def get_document_tool(input_data: DocumentInput) -> Optional[Dict[str, Any]]:
    """
    Retrieve a complete document.
    
    Args:
        input_data: Document retrieval parameters
    
    Returns:
        Document data or None
    """
    try:
        document = await get_document(input_data.document_id)
        
        if document:
            # Also get all chunks for the document
            chunks = await get_document_chunks(input_data.document_id)
            document["chunks"] = chunks
        
        return document
        
    except Exception as e:
        logger.error(f"Document retrieval failed: {e}")
        return None


async def list_documents_tool(input_data: DocumentListInput) -> List[DocumentMetadata]:
    """
    List available documents.
    
    Args:
        input_data: Listing parameters
    
    Returns:
        List of document metadata
    """
    try:
        documents = await list_documents(
            limit=input_data.limit,
            offset=input_data.offset
        )
        
        # Convert to DocumentMetadata models
        return [
            DocumentMetadata(
                id=d["id"],
                title=d["title"],
                source=d["source"],
                metadata=d["metadata"],
                created_at=datetime.fromisoformat(d["created_at"]),
                updated_at=datetime.fromisoformat(d["updated_at"]),
                chunk_count=d.get("chunk_count")
            )
            for d in documents
        ]
        
    except Exception as e:
        logger.error(f"Document listing failed: {e}")
        return []


async def get_entity_relationships_tool(input_data: EntityRelationshipInput) -> Dict[str, Any]:
    """
    Get relationships for an entity.
    
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


async def get_entity_timeline_tool(input_data: EntityTimelineInput) -> List[Dict[str, Any]]:
    """
    Get timeline of facts for an entity.
    
    Args:
        input_data: Timeline query parameters
    
    Returns:
        Timeline of facts
    """
    try:
        # Parse dates if provided
        start_date = None
        end_date = None
        
        if input_data.start_date:
            start_date = datetime.fromisoformat(input_data.start_date)
        if input_data.end_date:
            end_date = datetime.fromisoformat(input_data.end_date)
        
        # Get timeline from graph
        timeline = await graph_client.get_entity_timeline(
            entity_name=input_data.entity_name,
            start_date=start_date,
            end_date=end_date
        )
        
        return timeline
        
    except Exception as e:
        logger.error(f"Entity timeline query failed: {e}")
        return []


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
# CPG-SPECIFIC SEARCH TOOLS (Clinical Practice Guidelines)
# =============================================================================

async def cpg_filtered_search_tool(input_data: CPGFilteredSearchInput) -> List[Dict[str, Any]]:
    """
    Search CPG content with metadata filters.
    
    This tool enables precise retrieval by filtering on:
    - Evidence grade (Grade A, B, C)
    - Target population (Diabetes, Cardiac Disease, etc.)
    - Category (Diagnosis, Treatment, Referral)
    
    Args:
        input_data: CPG search parameters with filters
    
    Returns:
        List of filtered CPG chunks with metadata
    """
    from .db_utils import db_pool
    
    try:
        # Generate embedding for the query
        embedding = await generate_embedding(input_data.query)
        embedding_str = '[' + ','.join(map(str, embedding)) + ']'
        
        async with db_pool.acquire() as conn:
            results = await conn.fetch(
                """
                SELECT * FROM cpg_filtered_search(
                    $1::vector,
                    $2,
                    $3,
                    $4,
                    $5,
                    $6
                )
                """,
                embedding_str,
                input_data.grade,
                input_data.population,
                input_data.category,
                input_data.recommendations_only,
                input_data.limit
            )
            
            return [
                {
                    "content": r["content"],
                    "similarity": r["similarity"],
                    "evidence_level": r["evidence_level"],
                    "grade": r["grade"],
                    "target_population": r["target_population"],
                    "category": r["category"],
                    "section_hierarchy": r["section_hierarchy"],
                    "is_recommendation": r["is_recommendation"],
                    "is_table": r["is_table"],
                    "structured_content": r["structured_content"],
                    "document_title": r["document_title"],
                    "chunk_id": str(r["chunk_id"])
                }
                for r in results
            ]
            
    except Exception as e:
        logger.error(f"CPG filtered search failed: {e}")
        # Fallback to regular vector search
        return await vector_search_tool(VectorSearchInput(
            query=input_data.query,
            limit=input_data.limit
        ))


async def get_grade_a_recommendations_tool(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Get Grade A (highest evidence) recommendations related to a query.
    
    Args:
        query: Search query
        limit: Maximum results
    
    Returns:
        List of Grade A recommendations
    """
    from .db_utils import db_pool
    
    try:
        embedding = await generate_embedding(query)
        embedding_str = '[' + ','.join(map(str, embedding)) + ']'
        
        async with db_pool.acquire() as conn:
            results = await conn.fetch(
                """
                SELECT * FROM get_grade_a_recommendations($1::vector, $2)
                """,
                embedding_str,
                limit
            )
            
            return [
                {
                    "content": r["content"],
                    "similarity": r["similarity"],
                    "section_hierarchy": r["section_hierarchy"],
                    "target_population": r["target_population"],
                    "document_title": r["document_title"],
                    "chunk_id": str(r["chunk_id"])
                }
                for r in results
            ]
            
    except Exception as e:
        logger.error(f"Grade A recommendations search failed: {e}")
        return []


async def get_drug_info_tool(input_data: DrugInteractionInput) -> Dict[str, Any]:
    """
    Get comprehensive information about a drug including contraindications,
    dosages, and adverse events.
    
    Args:
        input_data: Drug name to look up
    
    Returns:
        Drug information with contraindications, dosages, side effects
    """
    from .db_utils import db_pool
    
    # Knowledge base from graph_builder (should match)
    DRUG_CONTRAINDICATIONS = {
        "Sildenafil": ["Nitrates", "Glyceryl trinitrate", "Isosorbide mononitrate", "Riociguat", "Severe Heart Failure"],
        "Tadalafil": ["Nitrates", "Glyceryl trinitrate", "Isosorbide mononitrate", "Riociguat", "Severe Heart Failure"],
        "Vardenafil": ["Nitrates", "Glyceryl trinitrate", "Isosorbide mononitrate", "Riociguat"],
        "Avanafil": ["Nitrates", "Riociguat"],
    }
    
    DRUG_DOSAGES = {
        "Sildenafil": ["50mg on-demand", "25-100mg range", "Start 50mg, adjust based on response"],
        "Tadalafil": ["10mg on-demand", "5mg daily for regular use", "10-20mg on-demand"],
        "Vardenafil": ["10mg on-demand", "5-20mg range"],
        "Avanafil": ["100mg on-demand", "50-200mg range"],
    }
    
    DRUG_ADVERSE_EVENTS = {
        "Sildenafil": ["Headache", "Flushing", "Dyspepsia", "Nasal congestion", "Visual abnormalities"],
        "Tadalafil": ["Headache", "Back pain", "Myalgia", "Dyspepsia"],
        "Vardenafil": ["Headache", "Flushing", "Dyspepsia"],
        "Avanafil": ["Headache", "Flushing", "Nasal congestion"],
    }
    
    drug = input_data.drug_name
    
    result = {
        "drug_name": drug,
        "contraindications": DRUG_CONTRAINDICATIONS.get(drug, []),
        "dosages": DRUG_DOSAGES.get(drug, []),
        "adverse_events": DRUG_ADVERSE_EVENTS.get(drug, []),
        "related_content": []
    }
    
    # Also search for relevant content from the vector DB
    try:
        search_results = await vector_search_tool(VectorSearchInput(
            query=f"{drug} dosage contraindication adverse effects",
            limit=3
        ))
        result["related_content"] = [
            {"content": r.content[:500], "document": r.document_title}
            for r in search_results
        ]
    except Exception as e:
        logger.warning(f"Could not fetch related content for {drug}: {e}")
    
    return result


async def get_treatment_recommendations_tool(input_data: TreatmentRecommendationInput) -> Dict[str, Any]:
    """
    Get treatment recommendations for a specific condition, optionally filtered by patient population.
    
    Args:
        input_data: Condition and optional population filter
    
    Returns:
        Treatment recommendations with evidence grades
    """
    # First, search for relevant content
    query = f"treatment recommendation {input_data.condition}"
    if input_data.population:
        query += f" {input_data.population}"
    
    # Use CPG filtered search if possible
    try:
        cpg_results = await cpg_filtered_search_tool(CPGFilteredSearchInput(
            query=query,
            population=input_data.population,
            category="Treatment",
            recommendations_only=True,
            limit=10
        ))
        
        # Organize by grade
        by_grade = {"Grade A": [], "Grade B": [], "Grade C": [], "Other": []}
        
        for r in cpg_results:
            grade = r.get("grade", "Other")
            if grade in by_grade:
                by_grade[grade].append({
                    "content": r["content"][:500],
                    "section": " > ".join(r.get("section_hierarchy", [])),
                    "population": r.get("target_population")
                })
            else:
                by_grade["Other"].append({
                    "content": r["content"][:500],
                    "section": " > ".join(r.get("section_hierarchy", []))
                })
        
        return {
            "condition": input_data.condition,
            "population_filter": input_data.population,
            "recommendations_by_grade": by_grade,
            "total_found": len(cpg_results)
        }
        
    except Exception as e:
        logger.error(f"Treatment recommendations search failed: {e}")
        # Fallback to regular search
        vector_results = await vector_search_tool(VectorSearchInput(query=query, limit=5))
        return {
            "condition": input_data.condition,
            "population_filter": input_data.population,
            "results": [{"content": r.content[:500]} for r in vector_results],
            "note": "Using fallback search (CPG metadata not available)"
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