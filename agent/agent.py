"""
Main Pydantic AI agent for agentic RAG with knowledge graph.
"""

import os
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from pydantic_ai import Agent, RunContext
from dotenv import load_dotenv

from .prompts import SYSTEM_PROMPT
from .providers import get_llm_model
from .tools import (
    vector_search_tool,
    graph_search_tool,
    hybrid_search_tool,
    get_document_tool,
    list_documents_tool,
    get_entity_relationships_tool,
    get_entity_timeline_tool,
    cpg_filtered_search_tool,
    get_grade_a_recommendations_tool,
    get_drug_info_tool,
    get_treatment_recommendations_tool,
    get_chunk_with_context_tool,
    VectorSearchInput,
    GraphSearchInput,
    HybridSearchInput,
    DocumentInput,
    DocumentListInput,
    EntityRelationshipInput,
    EntityTimelineInput,
    CPGFilteredSearchInput,
    DrugInteractionInput,
    TreatmentRecommendationInput
)

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


@dataclass
class AgentDependencies:
    """Dependencies for the agent."""
    session_id: str
    user_id: Optional[str] = None
    search_preferences: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.search_preferences is None:
            self.search_preferences = {
                "use_vector": True,
                "use_graph": True,
                "default_limit": 10
            }


# Initialize the agent with flexible model configuration
rag_agent = Agent(
    get_llm_model(),
    deps_type=AgentDependencies,
    system_prompt=SYSTEM_PROMPT
)


# Register tools with proper docstrings (no description parameter)
@rag_agent.tool
async def vector_search(
    ctx: RunContext[AgentDependencies],
    query: str,
    limit: int = 10
) -> List[Dict[str, Any]]:
    """
    Search for relevant information using semantic similarity.
    
    This tool performs vector similarity search across document chunks
    to find semantically related content. Returns the most relevant results
    regardless of similarity score.
    
    Args:
        query: Search query to find similar content
        limit: Maximum number of results to return (1-50)
    
    Returns:
        List of matching chunks ordered by similarity (best first)
    """
    input_data = VectorSearchInput(
        query=query,
        limit=limit
    )
    
    results = await vector_search_tool(input_data)
    
    # Convert results to dict for agent
    return [
        {
            "content": r.content,
            "score": r.score,
            "document_title": r.document_title,
            "document_source": r.document_source,
            "chunk_id": r.chunk_id
        }
        for r in results
    ]


@rag_agent.tool
async def graph_search(
    ctx: RunContext[AgentDependencies],
    query: str
) -> List[Dict[str, Any]]:
    """
    Search the knowledge graph for facts and relationships.
    
    This tool queries the knowledge graph to find specific facts, relationships 
    between entities, and temporal information. Best for finding specific facts,
    relationships between companies/people/technologies, and time-based information.
    
    Args:
        query: Search query to find facts and relationships
    
    Returns:
        List of facts with associated episodes and temporal data
    """
    input_data = GraphSearchInput(query=query)
    
    results = await graph_search_tool(input_data)
    
    # Convert results to dict for agent
    return [
        {
            "fact": r.fact,
            "uuid": r.uuid,
            "valid_at": r.valid_at,
            "invalid_at": r.invalid_at,
            "source_node_uuid": r.source_node_uuid
        }
        for r in results
    ]


@rag_agent.tool
async def hybrid_search(
    ctx: RunContext[AgentDependencies],
    query: str,
    limit: int = 10,
    text_weight: float = 0.3
) -> List[Dict[str, Any]]:
    """
    Perform both vector and keyword search for comprehensive results.
    
    This tool combines semantic similarity search with keyword matching
    for the best coverage. It ranks results using both vector similarity
    and text matching scores. Best for combining semantic and exact matching.
    
    Args:
        query: Search query for hybrid search
        limit: Maximum number of results to return (1-50)
        text_weight: Weight for text similarity vs vector similarity (0.0-1.0)
    
    Returns:
        List of chunks ranked by combined relevance score
    """
    input_data = HybridSearchInput(
        query=query,
        limit=limit,
        text_weight=text_weight
    )
    
    results = await hybrid_search_tool(input_data)
    
    # Convert results to dict for agent
    return [
        {
            "content": r.content,
            "score": r.score,
            "document_title": r.document_title,
            "document_source": r.document_source,
            "chunk_id": r.chunk_id
        }
        for r in results
    ]


@rag_agent.tool
async def get_document(
    ctx: RunContext[AgentDependencies],
    document_id: str
) -> Optional[Dict[str, Any]]:
    """
    Retrieve the complete content of a specific document.
    
    This tool fetches the full document content along with all its chunks
    and metadata. Best for getting comprehensive information from a specific
    source when you need the complete context.
    
    Args:
        document_id: UUID of the document to retrieve
    
    Returns:
        Complete document data with content and metadata, or None if not found
    """
    input_data = DocumentInput(document_id=document_id)
    
    document = await get_document_tool(input_data)
    
    if document:
        # Format for agent consumption
        return {
            "id": document["id"],
            "title": document["title"],
            "source": document["source"],
            "content": document["content"],
            "chunk_count": len(document.get("chunks", [])),
            "created_at": document["created_at"]
        }
    
    return None


@rag_agent.tool
async def list_documents(
    ctx: RunContext[AgentDependencies],
    limit: int = 20,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """
    List available documents with their metadata.
    
    This tool provides an overview of all documents in the knowledge base,
    including titles, sources, and chunk counts. Best for understanding
    what information sources are available.
    
    Args:
        limit: Maximum number of documents to return (1-100)
        offset: Number of documents to skip for pagination
    
    Returns:
        List of documents with metadata and chunk counts
    """
    input_data = DocumentListInput(limit=limit, offset=offset)
    
    documents = await list_documents_tool(input_data)
    
    # Convert to dict for agent
    return [
        {
            "id": d.id,
            "title": d.title,
            "source": d.source,
            "chunk_count": d.chunk_count,
            "created_at": d.created_at.isoformat()
        }
        for d in documents
    ]


@rag_agent.tool
async def get_entity_relationships(
    ctx: RunContext[AgentDependencies],
    entity_name: str,
    depth: int = 2
) -> Dict[str, Any]:
    """
    Get all relationships for a specific entity in the knowledge graph.
    
    This tool explores the knowledge graph to find how a specific entity
    (company, person, technology) relates to other entities. Best for
    understanding how companies or technologies relate to each other.
    
    Args:
        entity_name: Name of the entity to explore (e.g., "Google", "OpenAI")
        depth: Maximum traversal depth for relationships (1-5)
    
    Returns:
        Entity relationships and connected entities with relationship types
    """
    input_data = EntityRelationshipInput(
        entity_name=entity_name,
        depth=depth
    )
    
    return await get_entity_relationships_tool(input_data)


@rag_agent.tool
async def get_entity_timeline(
    ctx: RunContext[AgentDependencies],
    entity_name: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Get the timeline of facts for a specific entity.
    
    This tool retrieves chronological information about an entity,
    showing how information has evolved over time. Best for understanding
    how information about an entity has developed or changed.
    
    Args:
        entity_name: Name of the entity (e.g., "Microsoft", "AI")
        start_date: Start date in ISO format (YYYY-MM-DD), optional
        end_date: End date in ISO format (YYYY-MM-DD), optional
    
    Returns:
        Chronological list of facts about the entity with timestamps
    """
    input_data = EntityTimelineInput(
        entity_name=entity_name,
        start_date=start_date,
        end_date=end_date
    )
    
    return await get_entity_timeline_tool(input_data)


# =============================================================================
# CPG-SPECIFIC TOOLS (Clinical Practice Guidelines)
# =============================================================================

@rag_agent.tool
async def cpg_filtered_search(
    ctx: RunContext[AgentDependencies],
    query: str,
    grade: Optional[str] = None,
    population: Optional[str] = None,
    category: Optional[str] = None,
    recommendations_only: bool = False,
    limit: int = 10
) -> List[Dict[str, Any]]:
    """
    Search Clinical Practice Guidelines with evidence-based filters.
    
    This tool provides precise retrieval of clinical recommendations by filtering:
    - By evidence grade (Grade A = highest, Grade B, Grade C)
    - By target population (Diabetes, Cardiac Disease, Elderly, etc.)
    - By category (Diagnosis, Treatment, Referral, Monitoring)
    
    Best for: "Give me Grade A recommendations for diabetic patients"
    
    Args:
        query: Search query for clinical content
        grade: Filter by grade - 'Grade A', 'Grade B', 'Grade C', or 'Key Recommendation'
        population: Filter by population - 'General', 'Diabetes', 'Cardiac Disease', 'Elderly', etc.
        category: Filter by category - 'Diagnosis', 'Treatment', 'Referral', 'Monitoring', 'Prevention'
        recommendations_only: If True, only return graded recommendations
        limit: Maximum results (default 10)
    
    Returns:
        List of filtered CPG content with evidence metadata
    """
    input_data = CPGFilteredSearchInput(
        query=query,
        grade=grade,
        population=population,
        category=category,
        recommendations_only=recommendations_only,
        limit=limit
    )
    
    return await cpg_filtered_search_tool(input_data)


@rag_agent.tool
async def get_grade_a_recommendations(
    ctx: RunContext[AgentDependencies],
    query: str,
    limit: int = 10
) -> List[Dict[str, Any]]:
    """
    Get only Grade A (highest evidence) recommendations for a query.
    
    Grade A recommendations have the strongest evidence base and should be
    followed in most clinical situations. Use this when you need the most
    authoritative guidance.
    
    Args:
        query: Search query (e.g., "PDE5 inhibitor treatment", "ED diagnosis")
        limit: Maximum results (default 10)
    
    Returns:
        List of Grade A recommendations with section context
    """
    return await get_grade_a_recommendations_tool(query, limit)


@rag_agent.tool
async def get_drug_information(
    ctx: RunContext[AgentDependencies],
    drug_name: str
) -> Dict[str, Any]:
    """
    Get comprehensive drug information including contraindications and dosages.
    
    This tool provides essential prescribing information:
    - Contraindications (drugs/conditions to avoid)
    - Standard dosages
    - Common adverse events
    - Related guideline content
    
    Args:
        drug_name: Name of the drug (e.g., 'Sildenafil', 'Tadalafil', 'Vardenafil')
    
    Returns:
        Drug information dictionary with contraindications, dosages, side effects
    """
    input_data = DrugInteractionInput(drug_name=drug_name)
    return await get_drug_info_tool(input_data)


@rag_agent.tool
async def get_treatment_recommendations(
    ctx: RunContext[AgentDependencies],
    condition: str,
    population: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get treatment recommendations for a condition, organized by evidence grade.
    
    This tool retrieves all treatment recommendations for a specific condition,
    organized by evidence strength (Grade A > B > C). Optionally filter by
    patient population for more specific guidance.
    
    Args:
        condition: Medical condition (e.g., 'Erectile Dysfunction', 'Vasculogenic ED')
        population: Optional patient population (e.g., 'Diabetes', 'Cardiac Disease', 'Elderly')
    
    Returns:
        Treatment recommendations organized by evidence grade
    """
    input_data = TreatmentRecommendationInput(
        condition=condition,
        population=population
    )
    return await get_treatment_recommendations_tool(input_data)


@rag_agent.tool
async def get_chunk_with_parent_context(
    ctx: RunContext[AgentDependencies],
    chunk_id: str
) -> Dict[str, Any]:
    """
    Get a chunk with its parent section for full context.
    
    When vector search returns a chunk, use this to get the parent section
    context. This helps understand what the recommendation belongs to
    (e.g., the subsection it's under).
    
    Args:
        chunk_id: UUID of the chunk from a previous search result
    
    Returns:
        Chunk with parent content and full hierarchical context
    """
    return await get_chunk_with_context_tool(chunk_id)