"""
Graph utilities for Neo4j/Graphiti integration.
"""

import os
import json
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone
from contextlib import asynccontextmanager
import asyncio

from graphiti_core import Graphiti
from graphiti_core.utils.maintenance.graph_data_operations import clear_data
from graphiti_core.llm_client.config import LLMConfig
from graphiti_core.llm_client.openai_client import OpenAIClient
from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig
from graphiti_core.cross_encoder.openai_reranker_client import OpenAIRerankerClient
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


# =============================================================================
# CUSTOM ENTITY TYPES FOR MEDICAL/CPG DOMAIN
# =============================================================================
# These define custom entity labels that will appear in Neo4j
# instead of generic "Entity" labels.

class Medication(BaseModel):
    """A drug or pharmaceutical used for treatment."""
    drug_class: Optional[str] = Field(None, description="Drug class (e.g., PDE5 inhibitor)")
    dosage: Optional[str] = Field(None, description="Typical dosage")
    contraindications: Optional[str] = Field(None, description="Known contraindications")

class Condition(BaseModel):
    """A medical condition, disease, or diagnosis."""
    severity: Optional[str] = Field(None, description="Severity level if applicable")
    icd_code: Optional[str] = Field(None, description="ICD code if known")

class Procedure(BaseModel):
    """A medical procedure, treatment, or intervention."""
    procedure_type: Optional[str] = Field(None, description="Type: surgical, lifestyle, mechanical")
    indication: Optional[str] = Field(None, description="Primary indication")

class DiagnosticTool(BaseModel):
    """A diagnostic test, score, or assessment tool."""
    tool_type: Optional[str] = Field(None, description="Type: questionnaire, lab test, imaging")
    normal_range: Optional[str] = Field(None, description="Normal range if applicable")

class AdverseEvent(BaseModel):
    """A side effect, complication, or adverse event."""
    severity: Optional[str] = Field(None, description="Severity: mild, moderate, severe")
    frequency: Optional[str] = Field(None, description="How common: rare, common, frequent")

class RiskFactor(BaseModel):
    """A risk factor or predisposing condition."""
    modifiable: Optional[bool] = Field(None, description="Whether the risk factor is modifiable")

class Organization(BaseModel):
    """A medical organization, hospital, or institution."""
    org_type: Optional[str] = Field(None, description="Type: hospital, association, regulatory")
    country: Optional[str] = Field(None, description="Country if applicable")


# Dictionary of custom entity types for Graphiti
CUSTOM_ENTITY_TYPES: Dict[str, type] = {
    "Medication": Medication,
    "Condition": Condition,
    "Procedure": Procedure,
    "DiagnosticTool": DiagnosticTool,
    "AdverseEvent": AdverseEvent,
    "RiskFactor": RiskFactor,
    "Organization": Organization,
}

# Help from this PR for setting up the custom clients: https://github.com/getzep/graphiti/pull/601/files
class GraphitiClient:
    """Manages Graphiti knowledge graph operations."""
    
    def __init__(
        self,
        neo4j_uri: Optional[str] = None,
        neo4j_user: Optional[str] = None,
        neo4j_password: Optional[str] = None
    ):
        """
        Initialize Graphiti client.
        
        Args:
            neo4j_uri: Neo4j connection URI
            neo4j_user: Neo4j username
            neo4j_password: Neo4j password
        """
        # Neo4j configuration
        self.neo4j_uri = neo4j_uri or os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.neo4j_user = neo4j_user or os.getenv("NEO4J_USER", "neo4j")
        self.neo4j_password = neo4j_password or os.getenv("NEO4J_PASSWORD")
        self.neo4j_database = os.getenv("NEO4J_DATABASE", "neo4j")
        
        if not self.neo4j_password:
            raise ValueError("NEO4J_PASSWORD environment variable not set")
        
        # LLM configuration
        self.llm_provider = os.getenv("GRAPHITI_LLM_PROVIDER", os.getenv("INGESTION_LLM_PROVIDER", os.getenv("LLM_PROVIDER", "openai"))).lower()
        self.llm_base_url = os.getenv("GRAPHITI_LLM_BASE_URL", os.getenv("INGESTION_LLM_BASE_URL", os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")))
        self.llm_api_key = os.getenv("GRAPHITI_LLM_API_KEY", os.getenv("INGESTION_LLM_API_KEY", os.getenv("LLM_API_KEY")))
        self.llm_choice = os.getenv("GRAPHITI_LLM_CHOICE", os.getenv("INGESTION_LLM_CHOICE", os.getenv("LLM_CHOICE", "gpt-4.1-mini")))
        
        if not self.llm_api_key and self.llm_provider != "bedrock":
            raise ValueError("LLM_API_KEY environment variable not set")
        
        # Embedding configuration
        self.embedding_base_url = os.getenv("EMBEDDING_BASE_URL", "https://api.openai.com/v1")
        self.embedding_api_key = os.getenv("EMBEDDING_API_KEY")
        self.embedding_model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
        self.embedding_dimensions = int(os.getenv("VECTOR_DIMENSION", "1536"))
        
        self.embedding_provider = os.getenv("EMBEDDING_PROVIDER", "openai").lower()
        if self.embedding_provider != "bedrock" and not self.embedding_api_key:
            raise ValueError("EMBEDDING_API_KEY environment variable not set")
        
        self.graphiti: Optional[Graphiti] = None
        self._initialized = False
    
    async def initialize(self):
        """Initialize Graphiti client."""
        if self._initialized:
            return
        
        try:
            # Create LLMConfig
            llm_config = LLMConfig(
                api_key=self.llm_api_key,
                model=self.llm_choice,
                small_model=self.llm_choice,  # Can be the same as main model
                base_url=self.llm_base_url
            )
            llm_provider = self.llm_provider
            
            if llm_provider == "bedrock":
                import boto3
                from graphiti_core.llm_client.client import LLMClient
                
                class BedrockLlamaClient(LLMClient):
                    def __init__(self, config):
                        super().__init__(config)
                        self.client = boto3.client('bedrock-runtime', region_name=os.getenv('AWS_REGION', 'us-east-1'))
                        self.model_id = config.model
                        
                    async def _generate_response(self, messages, response_model, max_tokens, model_size):
                        boto_messages = []
                        system_prompts = []
                        
                        for msg in messages:
                            msg_dict = msg.model_dump() if hasattr(msg, 'model_dump') else msg
                            role = msg_dict.get('role')
                            content = msg_dict.get('content')
                            
                            if role == 'system':
                                system_prompts.append({"text": content})
                            else:
                                boto_messages.append({"role": role, "content": [{"text": content}]})
                        
                        if response_model:
                            schema_str = json.dumps(response_model.model_json_schema(), indent=2)
                            sys_prompt = f"You MUST output raw valid JSON that adheres exactly to this JSON schema. Do NOT wrap it in markdown block or any text. ONLY return JSON.\n{schema_str}"
                            system_prompts.append({"text": sys_prompt})
                            
                        def _invoke():
                            logger.debug(f"Boto3 Converse Call -> modelId: {self.model_id}")
                            return self.client.converse(
                                modelId=self.model_id,
                                messages=boto_messages,
                                system=system_prompts,
                                inferenceConfig={"maxTokens": min(max_tokens, 8192), "temperature": 0.0}
                            )
                            
                        response = await asyncio.to_thread(_invoke)
                        output_text = response['output']['message']['content'][0]['text']
                        
                        if response_model:
                            # Strip markdown fences if present
                            if "```json" in output_text:
                                output_text = output_text.split("```json")[1].split("```")[0].strip()
                            elif "```" in output_text:
                                output_text = output_text.split("```")[1].split("```")[0].strip()
                            # MUST return dict — base class handles Pydantic validation
                            return json.loads(output_text)
                        # When no response_model, return raw text wrapped in dict
                        return {"content": output_text}

                llm_client = BedrockLlamaClient(config=llm_config)
            else:
                # Create OpenAI LLM client
                llm_client = OpenAIClient(config=llm_config)
            
            # Check embedding provider
            embedding_provider = os.getenv("EMBEDDING_PROVIDER", "openai").lower()
            
            if embedding_provider == "bedrock":
                from graphiti_core.embedder.client import EmbedderClient
                import boto3
                
                class BedrockEmbedder(EmbedderClient):
                    def __init__(self, model_id, dimension):
                        self.model_id = model_id
                        self.dimension = dimension
                        self.client = boto3.client('bedrock-runtime', region_name=os.getenv('AWS_REGION', 'us-east-1'))
                        
                    def _invoke_bedrock_sync(self, text: str) -> list[float]:
                        if "titan" in self.model_id:
                            body = json.dumps({"inputText": text})
                            response = self.client.invoke_model(
                                modelId=self.model_id,
                                body=body,
                                contentType='application/json',
                                accept='application/json'
                            )
                            result = json.loads(response.get('body').read())
                            return result.get('embedding')[:self.dimension]
                        elif "cohere" in self.model_id:
                            body = json.dumps({"texts": [text], "input_type": "search_document"})
                            response = self.client.invoke_model(
                                modelId=self.model_id,
                                body=body,
                                contentType='application/json',
                                accept='application/json'
                            )
                            result = json.loads(response.get('body').read())
                            return result.get('embeddings')[0][:self.dimension]
                        else:
                            raise ValueError(f"Unsupported Bedrock model: {self.model_id}")
                            
                    async def create(self, input_data: str | list[str] | Any) -> list[float]:
                        text = input_data[0] if isinstance(input_data, list) else str(input_data)
                        return await asyncio.to_thread(self._invoke_bedrock_sync, text)
                        
                    async def create_batch(self, input_data_list: list[str]) -> list[list[float]]:
                        tasks = [self.create(txt) for txt in input_data_list]
                        return await asyncio.gather(*tasks)

                embedder = BedrockEmbedder(
                    model_id=self.embedding_model,
                    dimension=self.embedding_dimensions
                )
            else:
                if not self.embedding_api_key:
                    raise ValueError("EMBEDDING_API_KEY environment variable not set")
                    
                # Create OpenAI embedder
                embedder = OpenAIEmbedder(
                    config=OpenAIEmbedderConfig(
                        api_key=self.embedding_api_key,
                        embedding_model=self.embedding_model,
                        embedding_dim=self.embedding_dimensions,
                        base_url=self.embedding_base_url
                    )
                )
            
            cross_encoder_client = None
            if llm_provider != "bedrock":
                cross_encoder_client = OpenAIRerankerClient(client=llm_client, config=llm_config)
            else:
                from graphiti_core.cross_encoder.client import CrossEncoderClient
                
                class BedrockCohereRerankerClient(CrossEncoderClient):
                    """Reranker using Cohere Rerank v3.5 on AWS Bedrock."""
                    def __init__(self):
                        self.client = boto3.client('bedrock-runtime', region_name=os.getenv('AWS_REGION', 'us-east-1'))
                        self.model_id = os.getenv('RERANKER_MODEL', 'cohere.rerank-v3-5:0')
                    
                    async def rank(self, query: str, passages: list[str]) -> list[tuple[str, float]]:
                        if not passages:
                            return []
                        
                        try:
                            body = json.dumps({
                                "query": query,
                                "documents": passages,
                                "top_n": len(passages)
                            })
                            
                            def _invoke():
                                return self.client.invoke_model(
                                    modelId=self.model_id,
                                    body=body,
                                    contentType='application/json',
                                    accept='application/json'
                                )
                            
                            response = await asyncio.to_thread(_invoke)
                            result = json.loads(response['body'].read())
                            
                            ranked = []
                            for item in result.get('results', []):
                                idx = item['index']
                                score = item['relevance_score']
                                ranked.append((passages[idx], score))
                            
                            # Sort descending by relevance score
                            ranked.sort(key=lambda x: x[1], reverse=True)
                            return ranked
                            
                        except Exception as e:
                            logger.warning(f"Bedrock Cohere reranker failed, falling back to passthrough: {e}")
                            # Graceful fallback: return passages with equal scores
                            return [(p, 1.0) for p in passages]
                
                cross_encoder_client = BedrockCohereRerankerClient()
            
            # Initialize Graphiti with custom clients
            # Create Neo4jDriver with correct database name (Aura uses a generated ID, not 'neo4j')
            from graphiti_core.driver.neo4j_driver import Neo4jDriver
            neo4j_driver = Neo4jDriver(
                uri=self.neo4j_uri,
                user=self.neo4j_user,
                password=self.neo4j_password,
                database=self.neo4j_database,
            )
            
            self.graphiti = Graphiti(
                self.neo4j_uri,
                self.neo4j_user,
                self.neo4j_password,
                llm_client=llm_client,
                embedder=embedder,
                cross_encoder=cross_encoder_client,
                graph_driver=neo4j_driver
            )
            
            # Build indices and constraints
            await self.graphiti.build_indices_and_constraints()
            
            self._initialized = True
            logger.info(f"Graphiti client initialized successfully with LLM: {self.llm_choice} and embedder: {self.embedding_model}")
            
        except Exception as e:
            logger.error(f"Failed to initialize Graphiti: {e}")
            raise
    
    async def close(self):
        """Close Graphiti connection."""
        if self.graphiti:
            await self.graphiti.close()
            self.graphiti = None
            self._initialized = False
            logger.info("Graphiti client closed")
    
    async def add_episode(
        self,
        episode_id: str,
        content: str,
        source: str,
        timestamp: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None,
        use_custom_entity_types: bool = True
    ):
        """
        Add an episode to the knowledge graph with custom medical entity types.
        
        Args:
            episode_id: Unique episode identifier
            content: Episode content
            source: Source of the content
            timestamp: Episode timestamp
            metadata: Additional metadata
            use_custom_entity_types: Whether to use custom medical entity types
        """
        if not self._initialized:
            await self.initialize()
        
        episode_timestamp = timestamp or datetime.now(timezone.utc)
        
        # Import EpisodeType for proper source handling
        from graphiti_core.nodes import EpisodeType
        
        # Use custom entity types for medical domain
        entity_types = CUSTOM_ENTITY_TYPES if use_custom_entity_types else None
        
        await self.graphiti.add_episode(
            name=episode_id,
            episode_body=content,
            source=EpisodeType.text,  # Always use text type for our content
            source_description=source,
            reference_time=episode_timestamp
            # Note: entity_types removed - using Graphiti's default entity extraction
        )
        
        if use_custom_entity_types:
            logger.info(f"Added episode {episode_id} with custom entity types: {list(CUSTOM_ENTITY_TYPES.keys())}")
        else:
            logger.info(f"Added episode {episode_id} to knowledge graph")
    
    async def search(
        self,
        query: str,
        center_node_distance: int = 2,
        use_hybrid_search: bool = True,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Search the knowledge graph for clinical facts.

        Ingestion populates typed edges (CAUSES, INDICATED_FOR, ...) directly via Cypher
        rather than via graphiti.add_episode, so Graphiti's RELATES_TO / Episodic index is
        empty and graphiti.search() returns nothing. This implementation does a keyword
        Cypher search over the typed edges instead, ranked by how many query keywords hit
        the subject or object names.
        """
        if not self._initialized:
            await self.initialize()

        import re
        keywords = [w.lower() for w in re.findall(r"\w+", query) if len(w) >= 3]
        if not keywords:
            return []

        try:
            async with self.graphiti.driver.session() as session:
                cypher = """
                UNWIND $keywords AS kw
                MATCH (a)-[r]->(b)
                WHERE r.evidence IS NOT NULL
                  AND (toLower(a.name) CONTAINS kw OR toLower(b.name) CONTAINS kw)
                WITH a, r, b, count(DISTINCT kw) AS hits
                ORDER BY hits DESC
                LIMIT $limit
                RETURN
                    a.name              AS subj,
                    type(r)             AS rel,
                    b.name              AS obj,
                    r.severity          AS sev,
                    r.evidence          AS evidence,
                    r.cpg_chunk_id      AS source_chunk,
                    toString(elementId(r)) AS uuid,
                    toString(elementId(a)) AS subj_uuid
                """
                result = await session.run(cypher, keywords=keywords, limit=limit)
                facts: List[Dict[str, Any]] = []
                async for rec in result:
                    sev = f"[{rec['sev']}]" if rec["sev"] else ""
                    fact_str = (
                        f"({rec['subj']}) -[{rec['rel']}]{sev}-> ({rec['obj']})"
                    )
                    if rec["evidence"]:
                        fact_str += f": {rec['evidence']}"
                    facts.append({
                        "fact": fact_str,
                        "uuid": rec["uuid"],
                        "valid_at": None,
                        "invalid_at": None,
                        "source_node_uuid": rec["subj_uuid"],
                    })
                return facts

        except Exception as e:
            logger.error(f"Graph search failed: {e}")
            return []
    
    async def get_related_entities(
        self,
        entity_name: str,
        relationship_types: Optional[List[str]] = None,
        depth: int = 1
    ) -> Dict[str, Any]:
        """
        Get entities related to a given entity using Graphiti search.
        
        Args:
            entity_name: Name of the entity
            relationship_types: Types of relationships to follow (not used with Graphiti)
            depth: Maximum depth to traverse (not used with Graphiti)
        
        Returns:
            Related entities and relationships
        """
        if not self._initialized:
            await self.initialize()
        
        # Use Graphiti search to find related information about the entity
        results = await self.graphiti.search(f"relationships involving {entity_name}")
        
        # Extract entity information from the search results
        related_entities = set()
        facts = []
        
        for result in results:
            facts.append({
                "fact": result.fact,
                "uuid": str(result.uuid),
                "valid_at": str(result.valid_at) if hasattr(result, 'valid_at') and result.valid_at else None
            })
            
            # Simple entity extraction from fact text (could be enhanced)
            if entity_name.lower() in result.fact.lower():
                related_entities.add(entity_name)
        
        return {
            "central_entity": entity_name,
            "related_facts": facts,
            "search_method": "graphiti_semantic_search"
        }
    
    async def get_entity_timeline(
        self,
        entity_name: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Get timeline of facts for an entity using Graphiti.
        
        Args:
            entity_name: Name of the entity
            start_date: Start of time range (not currently used)
            end_date: End of time range (not currently used)
        
        Returns:
            Timeline of facts
        """
        if not self._initialized:
            await self.initialize()
        
        # Search for temporal information about the entity
        results = await self.graphiti.search(f"timeline history of {entity_name}")
        
        timeline = []
        for result in results:
            timeline.append({
                "fact": result.fact,
                "uuid": str(result.uuid),
                "valid_at": str(result.valid_at) if hasattr(result, 'valid_at') and result.valid_at else None,
                "invalid_at": str(result.invalid_at) if hasattr(result, 'invalid_at') and result.invalid_at else None
            })
        
        # Sort by valid_at if available
        timeline.sort(key=lambda x: x.get('valid_at') or '', reverse=True)
        
        return timeline
    
    async def get_graph_statistics(self) -> Dict[str, Any]:
        """
        Get basic statistics about the knowledge graph.
        
        Returns:
            Graph statistics
        """
        if not self._initialized:
            await self.initialize()
        
        # For now, return a simple search to verify the graph is working
        # More detailed statistics would require direct Neo4j access
        try:
            test_results = await self.graphiti.search("test")
            return {
                "graphiti_initialized": True,
                "sample_search_results": len(test_results),
                "note": "Detailed statistics require direct Neo4j access"
            }
        except Exception as e:
            return {
                "graphiti_initialized": False,
                "error": str(e)
            }
    
    async def clear_graph(self):
        """Clear all data from the graph (USE WITH CAUTION)."""
        if not self._initialized:
            await self.initialize()
        
        try:
            # Use Graphiti's proper clear_data function with the driver
            await clear_data(self.graphiti.driver)
            logger.warning("Cleared all data from knowledge graph")
        except Exception as e:
            logger.error(f"Failed to clear graph using clear_data: {e}")
            # Fallback: Close and reinitialize (this will create fresh indices)
            if self.graphiti:
                await self.graphiti.close()
            
            self._initialized = False
            await self.initialize()
            
            logger.warning("Reinitialized Graphiti client (fresh indices created)")
    
    async def get_entity_node_by_name(
        self,
        entity_name: str,
        fuzzy_match: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Get an entity node directly from Neo4j by name, including its summary.
        
        This is useful for getting structured info like dosages, contraindications
        that are stored in the node's summary field.
        
        Args:
            entity_name: Name of the entity to find (e.g., "Sildenafil")
            fuzzy_match: If True, use case-insensitive contains matching
        
        Returns:
            Entity node data including name, summary, labels, or None if not found
        """
        if not self._initialized:
            await self.initialize()
        
        try:
            async with self.graphiti.driver.session() as session:
                if fuzzy_match:
                    # Case-insensitive fuzzy match
                    query = """
                    MATCH (n:Entity)
                    WHERE toLower(n.name) CONTAINS toLower($name)
                    RETURN n.name as name, n.summary as summary, labels(n) as labels, 
                           n.uuid as uuid, n.created_at as created_at
                    LIMIT 5
                    """
                else:
                    # Exact match
                    query = """
                    MATCH (n:Entity {name: $name})
                    RETURN n.name as name, n.summary as summary, labels(n) as labels,
                           n.uuid as uuid, n.created_at as created_at
                    LIMIT 1
                    """
                
                result = await session.run(query, name=entity_name)
                records = await result.data()
                
                if records:
                    return records if fuzzy_match else records[0]
                return None
                
        except Exception as e:
            logger.error(f"Failed to get entity node for '{entity_name}': {e}")
            return None
    
    async def search_entities_by_type(
        self,
        entity_type: str,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Search for entities by a keyword in their name or summary.
        
        Args:
            entity_type: Type keyword to search for (e.g., "PDE5", "medication", "dose")
            limit: Maximum results to return
        
        Returns:
            List of matching entity nodes with summaries
        """
        if not self._initialized:
            await self.initialize()
        
        try:
            async with self.graphiti.driver.session() as session:
                query = """
                MATCH (n:Entity)
                WHERE toLower(n.name) CONTAINS toLower($type)
                   OR toLower(n.summary) CONTAINS toLower($type)
                RETURN n.name as name, n.summary as summary, labels(n) as labels
                LIMIT $limit
                """
                
                result = await session.run(query, type=entity_type, limit=limit)
                records = await result.data()
                return records
                
        except Exception as e:
            logger.error(f"Failed to search entities by type '{entity_type}': {e}")
            return []


# Global Graphiti client instance
graph_client = GraphitiClient()


async def initialize_graph():
    """Initialize graph client."""
    await graph_client.initialize()


async def close_graph():
    """Close graph client."""
    await graph_client.close()


# Convenience functions for common operations
async def add_to_knowledge_graph(
    content: str,
    source: str,
    episode_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> str:
    """
    Add content to the knowledge graph.
    
    Args:
        content: Content to add
        source: Source of the content
        episode_id: Optional episode ID
        metadata: Optional metadata
    
    Returns:
        Episode ID
    """
    if not episode_id:
        episode_id = f"episode_{datetime.now(timezone.utc).isoformat()}"
    
    await graph_client.add_episode(
        episode_id=episode_id,
        content=content,
        source=source,
        metadata=metadata
    )
    
    return episode_id


async def search_knowledge_graph(
    query: str
) -> List[Dict[str, Any]]:
    """
    Search the knowledge graph.
    
    Args:
        query: Search query
    
    Returns:
        Search results
    """
    return await graph_client.search(query)


async def get_entity_relationships(
    entity: str,
    depth: int = 2
) -> Dict[str, Any]:
    """
    Get relationships for an entity.
    
    Args:
        entity: Entity name
        depth: Maximum traversal depth
    
    Returns:
        Entity relationships
    """
    return await graph_client.get_related_entities(entity, depth=depth)


async def test_graph_connection() -> bool:
    """
    Test graph database connection.
    
    Returns:
        True if connection successful
    """
    try:
        await graph_client.initialize()
        stats = await graph_client.get_graph_statistics()
        logger.info(f"Graph connection successful. Stats: {stats}")
        return True
    except Exception as e:
        logger.error(f"Graph connection test failed: {e}")
        return False


async def get_entity_node_with_summary(
    entity_name: str,
    fuzzy_match: bool = True
) -> Optional[Dict[str, Any]]:
    """
    Get an entity node from Neo4j with its summary.
    
    The summary contains rich information like dosages, contraindications,
    side effects that the LLM extracted during graph building.
    
    Args:
        entity_name: Name of the entity (e.g., "Sildenafil")
        fuzzy_match: If True, use case-insensitive contains matching
    
    Returns:
        Entity node data with name, summary, labels, or None
    """
    return await graph_client.get_entity_node_by_name(entity_name, fuzzy_match)


async def search_entities_by_keyword(
    keyword: str,
    limit: int = 20
) -> List[Dict[str, Any]]:
    """
    Search for entities by keyword in their name or summary.
    
    Args:
        keyword: Search keyword (e.g., "dose", "PDE5", "contraindication")
        limit: Maximum results
    
    Returns:
        List of matching entity nodes with summaries
    """
    return await graph_client.search_entities_by_type(keyword, limit)