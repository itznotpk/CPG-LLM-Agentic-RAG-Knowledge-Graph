"""
Knowledge graph builder for extracting entities and relationships.
"""

import os
import logging
from typing import List, Dict, Any, Optional, Set, Tuple
from datetime import datetime, timezone
import asyncio
import re

from graphiti_core import Graphiti
from dotenv import load_dotenv
import json

from .chunker import DocumentChunk

# Import graph utilities
try:
    from ..agent.graph_utils import GraphitiClient
except ImportError:
    # For direct execution or testing
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from agent.graph_utils import GraphitiClient

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


class GraphBuilder:
    """Builds knowledge graph from document chunks."""
    
    def __init__(self):
        """Initialize graph builder."""
        self.graph_client = GraphitiClient()
        self._initialized = False
    
    async def initialize(self):
        """Initialize graph client."""
        if not self._initialized:
            await self.graph_client.initialize()
            self._initialized = True
    
    async def close(self):
        """Close graph client."""
        if self._initialized:
            await self.graph_client.close()
            self._initialized = False
    
    # ==========================================================================
    # UNIVERSAL CLINICAL RELATION TYPES (for LLM triple extraction)
    # ==========================================================================
    
    # Universal clinical relationship types â€” apply to ANY CPG domain
    CLINICAL_RELATION_TYPES = [
        "TREATS",               # Drug/procedure treats condition
        "CONTRAINDICATED_WITH", # Drug/intervention is contraindicated
        "INCREASES_RISK_OF",    # Factor increases risk of condition
        "REDUCES_RISK_OF",      # Intervention reduces risk of condition
        "INDICATED_FOR",        # Drug/procedure is indicated for profile
        "ASSESSED_BY",          # Condition is assessed by tool
        "CAUSES",               # Drug/procedure causes adverse event
        "FIRST_LINE_FOR",       # Drug/procedure is first-line
        "SECOND_LINE_FOR",      # Drug/procedure is second-line
        "REQUIRES_MONITORING",  # Drug/procedure requires monitoring
        "RECOMMENDED_FOR",      # Intervention is recommended for profile
        "HAS_DOSAGE",           # Drug has specific dosage
        "OTHER",                # Clinical relation not covered above
    ]

    # Entity categories for LLM-based entity extraction
    ENTITY_CATEGORIES = [
        "CONDITIONS",       # Diseases, disorders, syndromes
        "MEDICATIONS",      # Drugs, drug classes
        "DIAGNOSTIC_TOOLS", # Tests, scales, imaging
        "PROCEDURES",       # Surgeries, interventions
        "RISK_FACTORS",     # Lifestyle, comorbidity risks
        "ADVERSE_EVENTS",   # Side effects, complications
        "ORGANIZATIONS",    # Guideline bodies, societies
    ]
    
    async def add_document_to_graph(
        self,
        chunks: List[DocumentChunk],
        document_title: str,
        document_source: str,
        document_metadata: Optional[Dict[str, Any]] = None,
        batch_size: int = 3  # Reduced batch size for Graphiti
    ) -> Dict[str, Any]:
        """
        Add document chunks to the knowledge graph.
        
        Args:
            chunks: List of document chunks
            document_title: Title of the document
            document_source: Source of the document
            document_metadata: Additional metadata
            batch_size: Number of chunks to process in each batch
        
        Returns:
            Processing results
        """
        if not self._initialized:
            await self.initialize()
        
        if not chunks:
            return {"episodes_created": 0, "errors": []}
        
        logger.info(f"Adding {len(chunks)} chunks to knowledge graph for document: {document_title}")
        logger.info("âš ï¸ Large chunks will be truncated to avoid Graphiti token limits.")
        
        # Check for oversized chunks and warn (increased from 6000 to 10000)
        oversized_chunks = [i for i, chunk in enumerate(chunks) if len(chunk.content) > 10000]
        if oversized_chunks:
            logger.warning(f"Found {len(oversized_chunks)} chunks over 10000 chars that will be truncated: {oversized_chunks}")
        
        episodes_created = 0
        errors = []
        
        # Process chunks one by one to avoid overwhelming Graphiti
        for i, chunk in enumerate(chunks):
            try:
                # Create episode ID
                episode_id = f"{document_source}_{chunk.index}_{datetime.now().timestamp()}"
                
                # Prepare episode content with size limits
                episode_content = self._prepare_episode_content(
                    chunk,
                    document_title,
                    document_metadata
                )
                
                # Create source description (shorter)
                source_description = f"Document: {document_title} (Chunk: {chunk.index})"
                
                # Add episode to graph
                await self.graph_client.add_episode(
                    episode_id=episode_id,
                    content=episode_content,
                    source=source_description,
                    timestamp=datetime.now(timezone.utc),
                    metadata={
                        "document_title": document_title,
                        "document_source": document_source,
                        "chunk_index": chunk.index,
                        "original_length": len(chunk.content),
                        "processed_length": len(episode_content)
                    }
                )
                
                episodes_created += 1
                logger.info(f"âœ“ Added episode {episode_id} to knowledge graph ({episodes_created}/{len(chunks)})")
                
                # Small delay between each episode to reduce API pressure
                if i < len(chunks) - 1:
                    await asyncio.sleep(0.5)
                    
            except Exception as e:
                error_msg = f"Failed to add chunk {chunk.index} to graph: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)
                
                # Continue processing other chunks even if one fails
                continue
        
        result = {
            "episodes_created": episodes_created,
            "total_chunks": len(chunks),
            "errors": errors
        }
        
        logger.info(f"Graph building complete: {episodes_created} episodes created, {len(errors)} errors")
        return result
    
    def _prepare_episode_content(
        self,
        chunk: DocumentChunk,
        document_title: str,
        document_metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Prepare episode content with minimal context to avoid token limits.
        
        Args:
            chunk: Document chunk
            document_title: Title of the document
            document_metadata: Additional metadata
        
        Returns:
            Formatted episode content (optimized for Graphiti)
        """
        # Limit chunk content to avoid Graphiti's 8192 token limit
        # Estimate ~4 chars per token, keep content under 6000 chars to leave room for processing
        max_content_length = 6000
        
        content = chunk.content
        if len(content) > max_content_length:
            # Truncate content but try to end at a sentence boundary
            truncated = content[:max_content_length]
            last_sentence_end = max(
                truncated.rfind('. '),
                truncated.rfind('! '),
                truncated.rfind('? ')
            )
            
            if last_sentence_end > max_content_length * 0.7:  # If we can keep 70% and end cleanly
                content = truncated[:last_sentence_end + 1] + " [TRUNCATED]"
            else:
                content = truncated + "... [TRUNCATED]"
            
            logger.warning(f"Truncated chunk {chunk.index} from {len(chunk.content)} to {len(content)} chars for Graphiti")
        
        # Add minimal context (just document title for now)
        if document_title and len(content) < max_content_length - 100:
            episode_content = f"[Doc: {document_title[:50]}]\n\n{content}"
        else:
            episode_content = content
        
        return episode_content
    
    def _estimate_tokens(self, text: str) -> int:
        """Rough estimate of token count (4 chars per token)."""
        return len(text) // 4
    
    def _is_content_too_large(self, content: str, max_tokens: int = 7000) -> bool:
        """Check if content is too large for Graphiti processing."""
        return self._estimate_tokens(content) > max_tokens
    
    
    # ==========================================================================
    # LLM-BASED ENTITY EXTRACTION (for PostgreSQL metadata)
    # ==========================================================================
    
    async def _extract_entities_with_llm(self, text: str) -> Dict[str, List[str]]:
        """
        Use LLM to dynamically extract and classify medical entities from text.
        
        Returns:
            Dict mapping category names to lists of entity strings
        """
        from pydantic_ai import Agent
        
        try:
            from agent.providers import get_ingestion_model
            model = get_ingestion_model()
        except Exception:
            try:
                from ..agent.providers import get_ingestion_model
                model = get_ingestion_model()
            except Exception as e:
                logger.warning(f"Could not load ingestion model for entity extraction: {e}")
                return {}
        
        max_chars = 6000
        truncated = text[:max_chars] if len(text) > max_chars else text
        
        categories = "\n".join(f"  - {c}" for c in self.ENTITY_CATEGORIES)
        
        prompt = f"""Extract medical entities from the clinical text below.
Classify each entity into one of these categories:
{categories}

Return a JSON object where keys are category names and values are arrays of entity strings.
If a category has no entities, omit it.
Return ONLY the JSON object, no commentary.

TEXT:
{truncated}
"""
        
        try:
            temp_agent = Agent(model)
            response = await temp_agent.run(prompt)
            result_text = response.output.strip()
            
            json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
            if json_match:
                result_text = json_match.group()
            
            entities = json.loads(result_text)
            if not isinstance(entities, dict):
                return {}
            return entities
            
        except Exception as e:
            logger.warning(f"LLM entity extraction failed: {e}")
            return {}
    
    async def extract_entities_from_chunks(
        self,
        chunks: List[DocumentChunk],
        use_llm: bool = True
    ) -> List[DocumentChunk]:
        """
        Extract medical entities from chunks and add to metadata.
        
        Args:
            chunks: List of document chunks
            use_llm: Use LLM for dynamic entity extraction (recommended)
        
        Returns:
            Chunks with entity metadata added
        """
        logger.info(f"Extracting medical entities from {len(chunks)} chunks using {'LLM' if use_llm else 'pattern matching'}")
        
        enriched_chunks = []
        
        for i, chunk in enumerate(chunks):
            content = chunk.content
            
            if use_llm:
                llm_entities = await self._extract_entities_with_llm(content)
                
                entities = {
                    "conditions": llm_entities.get("CONDITIONS", []),
                    "medications": llm_entities.get("MEDICATIONS", []),
                    "diagnostic_tools": llm_entities.get("DIAGNOSTIC_TOOLS", []),
                    "procedures": llm_entities.get("PROCEDURES", []),
                    "risk_factors": llm_entities.get("RISK_FACTORS", []),
                    "adverse_events": llm_entities.get("ADVERSE_EVENTS", []),
                    "organizations": llm_entities.get("ORGANIZATIONS", []),
                    "extraction_method": "llm"
                }
            else:
                entities = {
                    "conditions": [],
                    "medications": [],
                    "diagnostic_tools": [],
                    "procedures": [],
                    "risk_factors": [],
                    "adverse_events": [],
                    "organizations": [],
                    "extraction_method": "skipped"
                }
            
            if (i + 1) % 5 == 0 or i == 0:
                logger.info(f"  Processed chunk {i + 1}/{len(chunks)}")
            
            enriched_chunk = DocumentChunk(
                content=chunk.content,
                index=chunk.index,
                start_char=chunk.start_char,
                end_char=chunk.end_char,
                metadata={
                    **chunk.metadata,
                    "entities": entities,
                    "entity_extraction_date": datetime.now().isoformat()
                },
                token_count=chunk.token_count
            )
            enriched_chunks.append(enriched_chunk)
        
        logger.info(f"Entity extraction complete for {len(enriched_chunks)} chunks")
        return enriched_chunks
    
    
    # ==========================================================================
    # LLM TRIPLE EXTRACTION â€” Universal CPG Relationship Extraction
    # ==========================================================================
    
    async def _extract_triples_with_llm(self, text: str, chunk_index: int, source: str) -> List[Dict[str, Any]]:
        """
        Use LLM to extract (subject, relation, object) triples from a clinical text chunk.
        Works for any CPG domain â€” no hardcoding required.
        
        Args:
            text: Chunk content
            chunk_index: Index of the chunk in its document
            source: Source document path
        
        Returns:
            List of triple dicts with keys: subject, subject_type, relation, object, object_type, evidence
        """
        from pydantic_ai import Agent
        
        try:
            from pydantic_ai.models.bedrock import BedrockConverseModel
            model_id = os.getenv("BEDROCK_MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0")
            model = BedrockConverseModel(model_id)
        except Exception as e:
            logger.warning(f"Could not load ingestion model for triple extraction: {e}")
            return []
        
        # Use provided text directly (already truncated/subchunked by caller)
        truncated = text
        
        relation_list = "\n".join(f"  - {r}" for r in self.CLINICAL_RELATION_TYPES)
        
        prompt = f"""You are a clinical knowledge graph expert. Extract medical relationships from the clinical text below.

EXTRACT relationships as JSON triples. Each triple must have:
- subject: the entity performing or being described (string)
- subject_type: one of [Drug, Condition, Procedure, DiagnosticTool, RiskFactor, AdverseEvent, PatientProfile, Organization]
- relation: one of the relation types listed below (string)
- object: the target entity (string)
- object_type: one of [Drug, Condition, Procedure, DiagnosticTool, RiskFactor, AdverseEvent, PatientProfile, Organization, Dosage]
- evidence: the exact sentence or phrase from the text that supports this triple (string)

RELATION TYPES (use exactly as written):
{relation_list}

RULES:
- Extract ONLY relationships explicitly stated in the text. Do not infer.
- If a relation does not fit any type, use "OTHER" and describe it in the object.
- Subject and object must be specific named entities, not vague phrases.
- Return a JSON array of triples. If no relationships found, return [].
- Do not include commentary â€” only the JSON array.

TEXT:
{truncated}

Return format:
[
  {{"subject": "Tamoxifen", "subject_type": "Drug", "relation": "TREATS", "object": "ER-positive breast cancer", "object_type": "Condition", "evidence": "Tamoxifen is recommended for ER-positive breast cancer patients."}},
  ...
]
"""
        
        try:
            temp_agent = Agent(model)
            response = await temp_agent.run(prompt)
            result_text = response.output.strip()
            
            # Extract JSON array from response
            json_match = re.search(r'\[.*\]', result_text, re.DOTALL)
            if json_match:
                result_text = json_match.group()
            
            triples = json.loads(result_text)
            
            if not isinstance(triples, list):
                return []
            
            # Validate and clean triples
            valid_triples = []
            for t in triples:
                if not isinstance(t, dict):
                    continue
                if not all(k in t for k in ["subject", "relation", "object"]):
                    continue
                if t.get("relation") not in self.CLINICAL_RELATION_TYPES:
                    t["relation"] = "OTHER"
                t["chunk_index"] = chunk_index
                t["source"] = source
                valid_triples.append(t)
            
            logger.debug(f"Chunk {chunk_index}: extracted {len(valid_triples)} triples")
            return valid_triples
            
        except json.JSONDecodeError as e:
            logger.warning(f"Triple extraction JSON parse failed for chunk {chunk_index}: {e}")
            return []
        except Exception as e:
            logger.warning(f"Triple extraction failed for chunk {chunk_index}: {e}")
            return []
    
    async def _write_triples_to_neo4j(self, triples: List[Dict[str, Any]], document_title: str):
        """
        Write extracted triples to Neo4j as typed edges using MERGE.
        
        Uses MERGE so re-ingestion is idempotent â€” duplicate triples are not created.
        Each node is labelled with its entity type (e.g., :Drug, :Condition).
        Each edge carries evidence text and source metadata.
        
        Args:
            triples: List of triple dicts from _extract_triples_with_llm
            document_title: Source document title (stored on each edge)
        """
        if not triples:
            return
        
        if not self._initialized:
            await self.initialize()
        
        try:
            # Get database name from the graph driver or env var
            # Pass None so the neo4j driver uses its own default (works with Aura).
            # Explicit NEO4J_DATABASE env var overrides when set.
            db_name = os.getenv("NEO4J_DATABASE") or None
            async with self.graph_client.graphiti.driver.client.session(database=db_name) as session:
                for triple in triples:
                    subject = triple.get("subject", "").strip()
                    subject_type = triple.get("subject_type", "Entity").strip()
                    relation = triple.get("relation", "OTHER").strip().upper()
                    obj = triple.get("object", "").strip()
                    obj_type = triple.get("object_type", "Entity").strip()
                    evidence = triple.get("evidence", "")[:500]  # Cap evidence length
                    chunk_index = triple.get("chunk_index", 0)
                    source = triple.get("source", "")
                    
                    if not subject or not obj:
                        continue
                    
                    # Sanitize labels (Neo4j labels cannot have spaces)
                    subject_label = re.sub(r'\W+', '', subject_type) or "Entity"
                    obj_label = re.sub(r'\W+', '', obj_type) or "Entity"
                    
                    # MERGE nodes by name+label, then MERGE relationship with evidence
                    cypher = f"""
                    MERGE (s:{subject_label} {{name: $subject}})
                    MERGE (o:{obj_label} {{name: $object}})
                    MERGE (s)-[r:{relation}]->(o)
                    ON CREATE SET
                        r.evidence = $evidence,
                        r.source_document = $document_title,
                        r.chunk_index = $chunk_index,
                        r.source = $source,
                        r.created_at = datetime()
                    ON MATCH SET
                        r.evidence = CASE WHEN r.evidence IS NULL THEN $evidence ELSE r.evidence END,
                        r.source_document = $document_title
                    """
                    
                    await session.run(
                        cypher,
                        subject=subject,
                        object=obj,
                        evidence=evidence,
                        document_title=document_title,
                        chunk_index=chunk_index,
                        source=source
                    )
            
            logger.info(f"Wrote {len(triples)} triples to Neo4j for '{document_title}'")
            
        except Exception as e:
            logger.error(f"Failed to write triples to Neo4j: {e}")
            raise
    
    def _split_into_subchunks(self, text: str, max_chars: int = 6000, overlap: int = 500) -> List[str]:
        """Split a large text into overlapping sub-chunks for LLM processing."""
        if len(text) <= max_chars:
            return [text]
        
        subchunks = []
        start = 0
        while start < len(text):
            end = start + max_chars
            chunk = text[start:end]
            
            # If not at the end, try to find a clean break (newline or period)
            if end < len(text):
                last_newline = chunk.rfind('\n')
                last_period = chunk.rfind('. ')
                
                if last_newline > max_chars * 0.7:
                    end = start + last_newline + 1
                elif last_period > max_chars * 0.7:
                    end = start + last_period + 2
                
                chunk = text[start:end]
            
            subchunks.append(chunk)
            start = end - overlap if end < len(text) else end
            
            # Safety break for very small progress
            if end <= start:
                start += max_chars // 2
                
        return subchunks

    async def build_relationship_graph(
        self,
        chunks: List[DocumentChunk],
        document_title: str
    ) -> Dict[str, Any]:
        """
        Build knowledge graph with LLM-extracted medical relationship triples.
        
        Splits oversized chunks into overlapping sub-chunks to ensure 100% coverage
        without hitting LLM context limits or truncation.
        """
        all_triples = []
        rel_counts: Dict[str, int] = {}
        processed_triples_keys: Set[Tuple[str, str, str]] = set() # For deduping
        
        logger.info(f"Extracting LLM triples from {len(chunks)} chunks for '{document_title}'")
        
        for chunk in chunks:
            # Phase A2 Fix: Split into overlapping subchunks to avoid 6000 char truncation
            subchunks = self._split_into_subchunks(chunk.content, max_chars=6000, overlap=500)
            
            if len(subchunks) > 1:
                logger.info(f"  Chunk {chunk.index} is large ({len(chunk.content)} chars) - split into {len(subchunks)} sub-chunks")
            
            for sub_idx, sub_content in enumerate(subchunks):
                # Use a fractional index for sub-chunks (e.g., 12.1, 12.2)
                display_idx = f"{chunk.index}.{sub_idx+1}" if len(subchunks) > 1 else chunk.index
                
                triples = await self._extract_triples_with_llm(
                    text=sub_content,
                    chunk_index=chunk.index,
                    source=chunk.metadata.get("source", "")
                )
                
                for t in triples:
                    # Deduplication check
                    triple_key = (
                        t.get("subject", "").lower().strip(),
                        t.get("relation", "").upper().strip(),
                        t.get("object", "").lower().strip()
                    )
                    
                    if triple_key in processed_triples_keys:
                        continue
                    
                    processed_triples_keys.add(triple_key)
                    t["source_document"] = document_title
                    t["subchunk_index"] = display_idx
                    
                    rel = t.get("relation", "OTHER")
                    rel_counts[rel] = rel_counts.get(rel, 0) + 1
                    all_triples.append(t)
                
                # Small delay between sub-chunks
                if sub_idx < len(subchunks) - 1:
                    await asyncio.sleep(0.5)
            
            # Small delay between main chunks
            if chunk.index < len(chunks) - 1:
                await asyncio.sleep(0.3)
        
        # Write all triples to Neo4j
        if all_triples:
            await self._write_triples_to_neo4j(all_triples, document_title)
        
        logger.info(f"Relationship graph built: {len(all_triples)} triples, types: {rel_counts}")
        
        return {
            "relationships": all_triples,
            "counts": rel_counts,
            "total": len(all_triples)
        }
    
    async def clear_graph(self):
        """Clear all data from the knowledge graph."""
        if not self._initialized:
            await self.initialize()
        
        logger.warning("Clearing knowledge graph...")
        await self.graph_client.clear_graph()
        logger.info("Knowledge graph cleared")


# Factory function
def create_graph_builder() -> GraphBuilder:
    """Create graph builder instance."""
    return GraphBuilder()


# Example usage with CPG document
async def main():
    """Example usage of the graph builder with CPG content."""
    from .chunker import ChunkingConfig, create_chunker
    
    # Create chunker and graph builder
    config = ChunkingConfig(chunk_size=1200, use_semantic_splitting=False)
    chunker = create_chunker(config)
    graph_builder = create_graph_builder()
    
    sample_cpg_text = """
    4.2 Pharmacological Treatment
    
    Phosphodiesterase type 5 (PDE5) inhibitors are recommended as first-line 
    pharmacological treatment for erectile dysfunction. [Grade A]
    
    Sildenafil, Tadalafil, and Vardenafil are available PDE5 inhibitors with 
    similar efficacy but different pharmacokinetic profiles.
    
    Contraindications:
    - Concurrent use of nitrates (absolute contraindication)
    - Cardiovascular conditions requiring nitrate therapy
    
    Dosage recommendations:
    - Sildenafil: 50mg on-demand, 25-100mg range
    - Tadalafil: 10mg on-demand or 5mg daily
    - Vardenafil: 10mg on-demand
    
    Adverse effects: headache, flushing, dyspepsia, nasal congestion.
    """
    
    # Chunk the document
    chunks = chunker.chunk_document(
        content=sample_cpg_text,
        title="Malaysia CPG - ED Management",
        source="cpg_ed_treatment.pdf"
    )
    
    print(f"Created {len(chunks)} chunks")
    
    # Build relationship graph using LLM triple extraction
    try:
        rel_result = await graph_builder.build_relationship_graph(
            chunks=chunks,
            document_title="Malaysia CPG - ED Management"
        )
        print(f"Triple extraction result: {rel_result['total']} triples, types: {rel_result['counts']}")
        
        # Add to Graphiti knowledge graph
        result = await graph_builder.add_document_to_graph(
            chunks=chunks,
            document_title="Malaysia CPG - ED Management",
            document_source="cpg_ed_treatment.pdf",
            document_metadata={"category": "Treatment", "evidence_level": "Grade A"}
        )
        
        print(f"Graph building result: {result}")
        
    except Exception as e:
        print(f"Graph building failed: {e}")
    
    finally:
        await graph_builder.close()


if __name__ == "__main__":
    asyncio.run(main())

