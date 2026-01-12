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
    get_entity_relationships,
    get_entity_node_with_summary
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


class AlgorithmPathwayInput(BaseModel):
    """Input for algorithm pathway navigation."""
    current_step: str = Field(..., description="Current clinical situation or step (e.g., 'PDE5i failure', 'Low cardiac risk', 'treatment failure')")
    condition: str = Field(default="ED", description="Medical condition context (e.g., 'ED', 'cardiovascular')")


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
    1. Entity node summaries (from Neo4j) - contains dosages, side effects, etc.
    2. Knowledge graph search (for related facts)
    3. Vector search on document chunks (multiple targeted searches)
    
    Args:
        input_data: Drug name to look up
    
    Returns:
        Drug information with contraindications, dosages, side effects from the knowledge base
    """
    drug = input_data.drug_name
    logger.info(f"Getting drug information for: {drug}")
    
    result = {
        "drug_name": drug,
        "entity_summary": None,  # NEW: Direct from Neo4j node
        "contraindications": [],
        "dosages": [],
        "adverse_events": [],
        "related_facts": [],
        "related_content": []
    }
    
    # ==========================================================================
    # STEP 0: Get entity node directly from Neo4j (contains rich summary info!)
    # This is the most important step - the summary has dosages, side effects, etc.
    # ==========================================================================
    try:
        entity_nodes = await get_entity_node_with_summary(drug, fuzzy_match=True)
        
        if entity_nodes:
            logger.info(f"Found {len(entity_nodes)} entity nodes for '{drug}'")
            
            for node in entity_nodes:
                name = node.get("name", "")
                summary = node.get("summary", "")
                
                if summary:
                    # Store the best matching summary
                    if drug.lower() in name.lower():
                        result["entity_summary"] = {
                            "name": name,
                            "summary": summary,
                            "source": "neo4j_entity_node"
                        }
                    
                    # Parse the summary for specific info
                    summary_lower = summary.lower()
                    
                    # Extract dosage info from summary
                    if any(kw in summary_lower for kw in ['mg', 'dose', 'initial', 'daily', 'on-demand']):
                        result["dosages"].append(f"[From {name}]: {summary}")
                    
                    # Extract contraindication info
                    if any(kw in summary_lower for kw in ['contraindicated', 'avoid', 'nitrate', 'must not']):
                        result["contraindications"].append(f"[From {name}]: {summary}")
                    
                    # Extract adverse events
                    if any(kw in summary_lower for kw in ['headache', 'flushing', 'side effect', 'adverse', 'myalgia']):
                        result["adverse_events"].append(f"[From {name}]: {summary}")
        else:
            logger.info(f"No entity nodes found for '{drug}'")
            
    except Exception as e:
        logger.warning(f"Entity node lookup failed for {drug}: {e}")
    
    # ==========================================================================
    # STEP 1: Search knowledge graph for related facts
    # ==========================================================================
    try:
        graph_results = await graph_search_tool(GraphSearchInput(
            query=f"{drug} contraindication dosage adverse effect side effect"
        ))
        
        for fact_result in graph_results:
            fact = fact_result.fact.lower() if hasattr(fact_result, 'fact') else str(fact_result).lower()
            result["related_facts"].append(fact_result.fact if hasattr(fact_result, 'fact') else str(fact_result))
            
            # Categorize facts based on content
            if 'contraindicated' in fact or 'avoid' in fact or 'must not' in fact or 'nitrate' in fact:
                result["contraindications"].append(fact_result.fact if hasattr(fact_result, 'fact') else str(fact_result))
            elif 'dosage' in fact or 'dose' in fact or 'mg' in fact or 'initial' in fact:
                result["dosages"].append(fact_result.fact if hasattr(fact_result, 'fact') else str(fact_result))
            elif 'adverse' in fact or 'side effect' in fact or 'cause' in fact or 'headache' in fact or 'flushing' in fact:
                result["adverse_events"].append(fact_result.fact if hasattr(fact_result, 'fact') else str(fact_result))
        
        logger.info(f"Graph search found {len(graph_results)} results for {drug}")
                
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
    
    # ==========================================================================
    # STEP 3: Dynamic vector search - query built from entity summary keywords
    # This adapts automatically to new documents without manual updates!
    # ==========================================================================
    
    # Extract keywords dynamically from entity summary (if available)
    dynamic_keywords = set()
    
    # Base keywords (minimal fallback)
    base_keywords = {"dose", "mg", "contraindication", "side effect", "adverse"}
    
    if result.get("entity_summary") and result["entity_summary"].get("summary"):
        summary = result["entity_summary"]["summary"]
        
        # Extract important terms from the summary
        summary_lower = summary.lower()
        
        # Add drug-specific terms found in summary
        keyword_patterns = [
            "mg", "dose", "initial", "max", "daily", "on-demand",
            "onset", "duration", "hours", "minutes", 
            "headache", "flushing", "myalgia", "back pain",
            "contraindicated", "avoid", "nitrate", "riociguat",
            "effective", "improved", "side effect", "adverse"
        ]
        
        for kw in keyword_patterns:
            if kw in summary_lower:
                dynamic_keywords.add(kw)
        
        logger.info(f"Extracted {len(dynamic_keywords)} keywords from entity summary for '{drug}'")
    
    # Combine with base keywords if we didn't find many dynamic ones
    all_keywords = dynamic_keywords if len(dynamic_keywords) >= 3 else dynamic_keywords.union(base_keywords)
    
    # Build dynamic query
    dynamic_query = f"{drug} " + " ".join(all_keywords)
    logger.info(f"Dynamic vector search query: {dynamic_query[:100]}...")
    
    try:
        search_results = await vector_search_tool(VectorSearchInput(
            query=dynamic_query,
            limit=10
        ))
        for r in search_results:
            result["related_content"].append({
                "content": r.content[:2000],
                "document": r.document_title, 
                "score": r.score,
                "search_type": "dynamic"
            })
        logger.info(f"Dynamic vector search found {len(search_results)} results for {drug}")
    except Exception as e:
        logger.warning(f"Dynamic vector search failed for {drug}: {e}")
    
    # ==========================================================================
    # STEP 4: Fallback search - only if Steps 0-3 didn't find enough info
    # ==========================================================================
    if not result["related_content"] and not result.get("entity_summary"):
        logger.info(f"No results from primary searches, running comprehensive fallback for {drug}")
        try:
            # Comprehensive fallback with all possible keywords
            fallback_query = f"""
            {drug} onset duration hours initial dose max dose mg 
            contraindication adverse effect side effect 
            nitrate washout period caution warning
            """.strip().replace('\n', ' ')
            
            fallback_results = await vector_search_tool(VectorSearchInput(
                query=fallback_query,
                limit=10
            ))
            for r in fallback_results:
                result["related_content"].append({
                    "content": r.content[:2000],
                    "document": r.document_title,
                    "score": r.score,
                    "search_type": "fallback"
                })
            logger.info(f"Fallback search found {len(fallback_results)} results for {drug}")
        except Exception as e:
            logger.warning(f"Fallback search failed for {drug}: {e}")
    
    # Remove duplicates
    result["contraindications"] = list(set(result["contraindications"]))
    result["dosages"] = list(set(result["dosages"]))
    result["adverse_events"] = list(set(result["adverse_events"]))
    
    # Deduplicate related_content by content hash
    seen_content = set()
    unique_content = []
    for item in result["related_content"]:
        content_hash = hash(item["content"][:200])  # Use first 200 chars as hash
        if content_hash not in seen_content:
            seen_content.add(content_hash)
            unique_content.append(item)
    result["related_content"] = unique_content
    
    logger.info(f"Drug info for {drug}: {len(result['contraindications'])} contraindications, "
                f"{len(result['dosages'])} dosages, {len(result['adverse_events'])} adverse events, "
                f"{len(result['related_content'])} content chunks")
    
    return result



async def get_algorithm_pathway_tool(input_data: AlgorithmPathwayInput) -> Dict[str, Any]:
    """
    Navigate CPG algorithms step-by-step and find next steps in treatment pathway.
    
    Use this when:
    - Following a clinical algorithm (e.g., Algorithm 1, Algorithm 2)
    - Determining what to do when current treatment fails
    - Finding next steps after a certain clinical event
    
    Args:
        input_data: Current step/situation and condition context
    
    Returns:
        Next steps in the algorithm pathway with alternatives
    """
    current_step = input_data.current_step
    condition = input_data.condition
    
    logger.info(f"Algorithm pathway search for: {current_step} in context of {condition}")
    
    try:
        # Search for algorithm/pathway content with multiple targeted queries
        queries = [
            f"algorithm {current_step} {condition} next step",
            f"if {current_step} then {condition}",
            f"{current_step} failure alternative {condition}",
            f"after {current_step} {condition} management"
        ]
        
        all_results = []
        
        # Search vector DB for pathway content
        for q in queries[:2]:  # Limit to avoid too many calls
            results = await vector_search_tool(VectorSearchInput(query=q, limit=5))
            all_results.extend(results)
        
        # Search knowledge graph for related pathway facts
        graph_results = await graph_search_tool(GraphSearchInput(
            query=f"{current_step} {condition} pathway next"
        ))
        
        # Deduplicate and structure results
        seen_content = set()
        pathway_steps = []
        
        for r in all_results:
            content_key = r.content[:100]
            if content_key not in seen_content:
                seen_content.add(content_key)
                pathway_steps.append({
                    "content": r.content[:600],
                    "document": r.document_title,
                    "score": r.score
                })
        
        # Extract pathway facts from graph
        pathway_facts = []
        if graph_results:
            for r in graph_results[:5]:
                if hasattr(r, 'fact'):
                    pathway_facts.append(r.fact)
        
        return {
            "current_step": current_step,
            "condition": condition,
            "next_steps": pathway_steps[:8],  # Top 8 most relevant
            "pathway_facts": pathway_facts,
            "alternatives": [p for p in pathway_steps if 'alternative' in p['content'].lower() or 'fail' in p['content'].lower()][:3],
            "total_found": len(pathway_steps)
        }
        
    except Exception as e:
        logger.error(f"Algorithm pathway search failed: {e}")
        return {
            "current_step": current_step,
            "condition": condition,
            "next_steps": [],
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