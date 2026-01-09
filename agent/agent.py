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
    get_entity_relationships_tool,
    get_drug_info_tool,
    get_treatment_recommendations_tool,
    get_chunk_with_context_tool,
    VectorSearchInput,
    GraphSearchInput,
    HybridSearchInput,
    EntityRelationshipInput,
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


# =============================================================================
# DRUG AND TREATMENT TOOLS
# =============================================================================


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
    condition: str
) -> Dict[str, Any]:
    """
    Get treatment recommendations for a medical condition.
    
    This tool retrieves treatment recommendations for a specific condition
    from the CPG content using vector search and knowledge graph.
    
    Args:
        condition: Medical condition (e.g., 'Erectile Dysfunction', 'Vasculogenic ED')
    
    Returns:
        Treatment recommendations from CPG content
    """
    input_data = TreatmentRecommendationInput(condition=condition)
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