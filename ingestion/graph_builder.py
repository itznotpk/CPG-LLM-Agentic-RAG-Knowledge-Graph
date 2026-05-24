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
    
    # Universal clinical relationship types - apply to ANY CPG domain.
    # CONTRAINDICATED_WITH = absolute contraindication only (do not co-prescribe).
    # INTERACTS_WITH       = pharmacokinetic/pharmacodynamic interaction (carries severity).
    # CROSS_REACTS_WITH    = allergen cross-reactivity (carries risk_pct when stated).
    # REQUIRES_DOSE_ADJUSTMENT = dose modification required (carries trigger, e.g. "eGFR<30").
    CLINICAL_RELATION_TYPES = [
        "TREATS",                   # Drug/procedure treats condition
        "CONTRAINDICATED_WITH",     # Absolute contraindication (do not co-prescribe)
        "INTERACTS_WITH",           # PK/PD interaction - use severity (MAJOR/MODERATE/MINOR)
        "CROSS_REACTS_WITH",        # Allergen cross-reactivity - use risk_pct when stated
        "REQUIRES_DOSE_ADJUSTMENT", # Dose change needed - use trigger (e.g. "eGFR<30")
        "INCREASES_RISK_OF",        # Factor increases risk of condition
        "REDUCES_RISK_OF",          # Intervention reduces risk of condition
        "INDICATED_FOR",            # Drug/procedure is indicated for profile
        "ASSESSED_BY",              # Condition is assessed by tool
        "CAUSES",                   # Drug/procedure causes adverse event
        "FIRST_LINE_FOR",           # Drug/procedure is first-line
        "SECOND_LINE_FOR",          # Drug/procedure is second-line
        "REQUIRES_MONITORING",      # Drug/procedure requires monitoring
        "RECOMMENDED_FOR",          # Intervention is recommended for profile
        "HAS_DOSAGE",               # Drug has specific dosage
        "OTHER",                    # Clinical relation not covered above
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
        logger.info(" Large chunks will be truncated to avoid Graphiti token limits.")
        
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
                logger.info(f"Added episode {episode_id} to knowledge graph ({episodes_created}/{len(chunks)})")
                
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
    
    # Name normalisation is shared with the read side (agent/graph_clinical.py)
    # via agent.graph_normalise. Do not fork the logic here - update the shared
    # module instead so write-time MERGE keys stay symmetric with read-time
    # lookup keys.
    @staticmethod
    def _normalize_entity_name(name: str) -> str:
        """Return the display name (title-cased, abbreviation-expanded,
        de-pluralised). The lowercase MERGE key is `display.lower()`.
        """
        try:
            from agent.graph_normalise import canonical_form
        except ImportError:
            from ..agent.graph_normalise import canonical_form
        display, _ = canonical_form(name or "")
        return display or name

    
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
        if not use_llm:
            logger.warning(
                f"entity_extraction=disabled (use_llm=False) - {len(chunks)} chunks will receive "
                f"empty entity stubs with extraction_method='skipped'. KG triple anchors will be missing. "
                f"Check that --skip-graph was not passed unintentionally."
            )
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
                chunk_level=chunk.chunk_level,
                token_count=chunk.token_count
            )
            enriched_chunks.append(enriched_chunk)
        
        logger.info(f"Entity extraction complete for {len(enriched_chunks)} chunks")
        return enriched_chunks
    
    
    # ==========================================================================
    # LLM TRIPLE EXTRACTION - Universal CPG Relationship Extraction
    # ==========================================================================
    
    async def _extract_triples_with_llm(self, text: str, chunk_index: int, source: str, cpg_chunk_id: Optional[str] = None, before: str = "", after: str = "") -> List[Dict[str, Any]]:
        """
        Use LLM to extract (subject, relation, object) triples from a clinical text chunk.
        Works for any CPG domain - no hardcoding required.

        Args:
            text: Focus window - triples are extracted from this region only
            chunk_index: Index of the chunk in its document
            source: Source document path
            before: Up to 2 000 chars preceding the focus window (reference context only)
            after: Up to 2 000 chars following the focus window (reference context only)

        Returns:
            List of triple dicts with keys: subject, subject_type, relation, object, object_type, evidence
        """
        from pydantic_ai import Agent

        try:
            try:
                from ..agent.providers import get_ingestion_model
            except ImportError:
                from agent.providers import get_ingestion_model
            model = get_ingestion_model()
        except Exception as e:
            logger.warning(f"Could not load ingestion model for triple extraction: {e}")
            return []
        
        relation_list = "\n".join(f"  - {r}" for r in self.CLINICAL_RELATION_TYPES)

        before_block = f"\n[BEFORE - reference context, do NOT extract from here]\n{before}\n" if before else ""
        after_block = f"\n[AFTER - reference context, do NOT extract from here]\n{after}\n" if after else ""

        prompt = f"""You are a clinical knowledge graph expert. Extract medical relationships from the clinical text below.

EXTRACT relationships as JSON triples. Each triple must have:
- subject: the entity performing or being described (string)
- subject_type: one of [Drug, Condition, Procedure, DiagnosticTool, RiskFactor, AdverseEvent, PatientProfile, Organization]
- relation: one of the relation types listed below (string)
- object: the target entity (string)
- object_type: one of [Drug, Condition, Procedure, DiagnosticTool, RiskFactor, AdverseEvent, PatientProfile, Organization, Dosage]
- evidence: the exact sentence or phrase from the text that supports this triple (string)
- severity: MAJOR, MODERATE, MINOR, or null. Use ONLY when the text explicitly states a severity level or urgency (e.g. "avoid", "major risk", "monitor closely"). If not stated, return null. DO NOT infer.
- trigger: string or null. Use for REQUIRES_DOSE_ADJUSTMENT only. The specific condition triggering the adjustment (e.g. "eGFR<30", "hepatic impairment"). If not stated, return null.
- risk_pct: string or null. Use for CROSS_REACTS_WITH only. The stated cross-reactivity percentage if explicitly given. If not stated, return null.

RELATION TYPES (use exactly as written):
{relation_list}

RELATION GUIDANCE:
- CONTRAINDICATED_WITH: absolute contraindication only - the text explicitly says "do not use", "contraindicated", "avoid in all cases"
- INTERACTS_WITH: pharmacokinetic or pharmacodynamic interaction that requires attention but is not an absolute contraindication
- CROSS_REACTS_WITH: allergen cross-reactivity between two substances
- REQUIRES_DOSE_ADJUSTMENT: a dose change is needed under a specific condition (renal, hepatic, age, weight)
- severity calibration (IMPORTANT — clinical guidelines use cautious language by default; do not equate strong wording with MAJOR):
    * MAJOR    = the stated outcome is fatal or disabling (death, stroke, anaphylaxis, cardiac arrest, hepatic failure, agranulocytosis, irreversible harm).
    * MODERATE = significant clinical impact requiring action but not life-threatening. Default bucket for "avoid", "serious", "significant", "use with caution", "may worsen X", "consider alternative".
    * MINOR    = monitoring-only or clinically minor (e.g. transient LFT rise, mild GI upset, "monitor closely" without an adverse outcome stated).
    * null     = severity not stated or inferable in the source sentence.
  Strong CPG language alone ("avoid", "serious", "significant") is NOT sufficient for MAJOR — the OUTCOME must be life-threatening or disabling. Default to MODERATE when in doubt.

RULES:
- Extract ONLY relationships explicitly stated in the [FOCUS] region. Do not infer.
- The [BEFORE] and [AFTER] regions are context only - use them to resolve references
  (pronouns, abbreviations, dangling entities) but never extract a triple whose evidence
  sentence lives outside [FOCUS].
- If a relation does not fit any type, use "OTHER" and describe it in the object.
- Subject and object must be specific named entities, not vague phrases.
- severity, trigger, risk_pct: return null if not explicitly stated in the text. Never guess.
- Return a JSON array of triples. If no relationships found, return [].
- Do not include commentary - only the JSON array.
{before_block}
[FOCUS - extract triples from this region only]
{text}
{after_block}
Return format:
[
  {{"subject": "Warfarin", "subject_type": "Drug", "relation": "INTERACTS_WITH", "object": "Amiodarone", "object_type": "Drug", "evidence": "Amiodarone significantly potentiates the anticoagulant effect of warfarin, increasing risk of fatal bleeding.", "severity": "MAJOR", "trigger": null, "risk_pct": null}},
  {{"subject": "Beta-Blocker", "subject_type": "Drug", "relation": "INTERACTS_WITH", "object": "Decompensated Heart Failure", "object_type": "Condition", "evidence": "Avoid beta-blockers in decompensated heart failure; use with caution in stable HF.", "severity": "MODERATE", "trigger": null, "risk_pct": null}},
  {{"subject": "Metformin", "subject_type": "Drug", "relation": "REQUIRES_DOSE_ADJUSTMENT", "object": "Renal Impairment", "object_type": "Condition", "evidence": "Reduce metformin dose when eGFR falls below 30 mL/min/1.73m2.", "severity": null, "trigger": "eGFR<30", "risk_pct": null}},
  {{"subject": "Tamoxifen", "subject_type": "Drug", "relation": "TREATS", "object": "ER-positive Breast Cancer", "object_type": "Condition", "evidence": "Tamoxifen is recommended for ER-positive breast cancer patients.", "severity": null, "trigger": null, "risk_pct": null}},
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
            valid_severities = {"MAJOR", "MODERATE", "MINOR"}
            valid_triples = []
            for t in triples:
                if not isinstance(t, dict):
                    continue
                if not all(k in t for k in ["subject", "relation", "object"]):
                    continue
                if t.get("relation") not in self.CLINICAL_RELATION_TYPES:
                    t["relation"] = "OTHER"
                # Enforce controlled vocabulary - reject LLM hallucinations
                if t.get("severity") not in valid_severities:
                    t["severity"] = None
                # Null out trigger/risk_pct if not meaningful
                if not t.get("trigger"):
                    t["trigger"] = None
                if not t.get("risk_pct"):
                    t["risk_pct"] = None
                t["chunk_index"] = chunk_index
                t["source"] = source
                if cpg_chunk_id:
                    t["cpg_chunk_id"] = cpg_chunk_id
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
        
        Uses MERGE so re-ingestion is idempotent - duplicate triples are not created.
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
                    # Raw name from LLM extraction
                    subject_raw = triple.get("subject", "").strip()
                    obj_raw = triple.get("object", "").strip()

                    # Display name: title-cased, de-pluralised, abbreviation-expanded
                    subject_display = self._normalize_entity_name(subject_raw)
                    obj_display = self._normalize_entity_name(obj_raw)

                    # MERGE key: lowercased canonical form for deduplication
                    subject_norm = subject_display.lower()
                    obj_norm = obj_display.lower()

                    subject_type = triple.get("subject_type", "Entity").strip()
                    relation = triple.get("relation", "OTHER").strip().upper()
                    obj_type = triple.get("object_type", "Entity").strip()
                    evidence = triple.get("evidence", "")[:500]  # Cap evidence length
                    chunk_index = triple.get("chunk_index", 0)
                    cpg_chunk_id = triple.get("cpg_chunk_id")
                    source = triple.get("source", "")
                    severity = triple.get("severity")      # MAJOR/MODERATE/MINOR or None
                    trigger = triple.get("trigger")        # e.g. "eGFR<30" or None
                    risk_pct = triple.get("risk_pct")      # e.g. "10%" or None

                    if not subject_norm or not obj_norm:
                        continue

                    # Sanitize labels (Neo4j labels cannot have spaces)
                    subject_label = re.sub(r'\W+', '', subject_type) or "Entity"
                    obj_label = re.sub(r'\W+', '', obj_type) or "Entity"

                    # MERGE on name_normalised (canonical key) - guarantees
                    # "Warfarin", "warfarin", "WARFARIN" all resolve to one node.
                    # ON CREATE sets the display name; ON MATCH leaves it alone
                    # so the first-seen display form is preserved.
                    cypher = f"""
                    MERGE (s:{subject_label} {{name_normalised: $subject_norm}})
                        ON CREATE SET s.name = $subject_display
                    MERGE (o:{obj_label} {{name_normalised: $obj_norm}})
                        ON CREATE SET o.name = $obj_display
                    MERGE (s)-[r:{relation}]->(o)
                    ON CREATE SET
                        r.evidence = $evidence,
                        r.evidence_list = [$evidence],
                        r.cpg_chunk_id = $cpg_chunk_id,
                        r.cpg_chunk_ids = CASE WHEN $cpg_chunk_id IS NOT NULL THEN [$cpg_chunk_id] ELSE [] END,
                        r.source_document = $document_title,
                        r.chunk_index = $chunk_index,
                        r.source = $source,
                        r.severity = $severity,
                        r.trigger = $trigger,
                        r.risk_pct = $risk_pct,
                        r.created_at = datetime()
                    ON MATCH SET
                        r.evidence_list = CASE
                            WHEN $evidence IN coalesce(r.evidence_list, []) THEN r.evidence_list
                            ELSE coalesce(r.evidence_list, [r.evidence]) + [$evidence]
                        END,
                        r.cpg_chunk_ids = CASE
                            WHEN $cpg_chunk_id IS NULL THEN coalesce(r.cpg_chunk_ids, [])
                            WHEN $cpg_chunk_id IN coalesce(r.cpg_chunk_ids, []) THEN coalesce(r.cpg_chunk_ids, [])
                            ELSE coalesce(r.cpg_chunk_ids, []) + [$cpg_chunk_id]
                        END,
                        r.source_document = $document_title,
                        r.severity = CASE WHEN r.severity IS NULL THEN $severity ELSE r.severity END,
                        r.trigger = CASE WHEN r.trigger IS NULL THEN $trigger ELSE r.trigger END,
                        r.risk_pct = CASE WHEN r.risk_pct IS NULL THEN $risk_pct ELSE r.risk_pct END
                    """

                    await session.run(
                        cypher,
                        subject_norm=subject_norm,
                        subject_display=subject_display,
                        obj_norm=obj_norm,
                        obj_display=obj_display,
                        evidence=evidence,
                        document_title=document_title,
                        chunk_index=chunk_index,
                        cpg_chunk_id=cpg_chunk_id,
                        source=source,
                        severity=severity,
                        trigger=trigger,
                        risk_pct=risk_pct,
                    )
            
            logger.info(f"Wrote {len(triples)} triples to Neo4j for '{document_title}'")
            
        except Exception as e:
            logger.error(f"Failed to write triples to Neo4j: {e}")
            raise
    
    def _split_into_subchunks(self, text: str) -> List[Dict[str, Any]]:
        """
        Split text into non-overlapping focus windows with before/after context bands.

        Returns list of dicts:
          {
            "before": str,        # up to 2 000 chars before focus (empty for first window)
            "focus": str,         # 2 000-char focus window (extract triples from here only)
            "after": str,         # up to 2 000 chars after focus (empty for last window)
            "focus_start": int,   # byte offset of focus start inside text
            "focus_end": int,     # byte offset of focus end inside text
            "is_first": bool,
            "is_last": bool,
          }

        Band size = 2 000 chars; stride = 6 000 chars (non-overlapping focus windows).
        When text fits in one focus window, returns a single dict with empty before/after.
        """
        BAND = 2_000
        STRIDE = 6_000

        if len(text) <= STRIDE:
            return [{
                "before": "",
                "focus": text,
                "after": "",
                "focus_start": 0,
                "focus_end": len(text),
                "is_first": True,
                "is_last": True,
            }]

        windows = []
        pos = 0
        while pos < len(text):
            focus_start = pos
            focus_end = min(pos + STRIDE, len(text))
            before = text[max(0, focus_start - BAND): focus_start]
            after = text[focus_end: min(len(text), focus_end + BAND)]
            windows.append({
                "before": before,
                "focus": text[focus_start:focus_end],
                "after": after,
                "focus_start": focus_start,
                "focus_end": focus_end,
                "is_first": pos == 0,
                "is_last": focus_end >= len(text),
            })
            pos = focus_end

        return windows

    # Default category whitelist - only extract triples from chunks with
    # clinical decision-making content.  Chunks tagged as Introduction,
    # Methodology, Epidemiology, References, etc. are skipped to save LLM
    # cost and prevent noise in the graph.
    CLINICAL_CATEGORY_WHITELIST = {
        "Treatment", "Supportive Treatment", "Assessment",
        "Diagnosis", "Special Populations", "Prevention",
        "Pharmacological Treatment", "Non-Pharmacological Treatment",
        "Management", "Monitoring", "Referral",
        # Also accept chunks whose category was not set (legacy or missing
        # METADATA block) - these may still contain clinically useful content
        # and should not be silently dropped.
        None,
    }

    async def build_relationship_graph(
        self,
        chunks: List[DocumentChunk],
        document_title: str,
        category_whitelist: Optional[Set[str]] = None,
    ) -> Dict[str, Any]:
        """
        Build knowledge graph with LLM-extracted medical relationship triples.
        
        Splits oversized chunks into overlapping sub-chunks to ensure 100% coverage
        without hitting LLM context limits or truncation.

        Args:
            chunks: List of document chunks
            document_title: Title of the document
            category_whitelist: Optional set of category strings to include.
                Chunks whose metadata['category'] is not in this set are skipped.
                Defaults to CLINICAL_CATEGORY_WHITELIST.
        """
        all_triples = []
        rel_counts: Dict[str, int] = {}
        processed_triples_keys: Set[Tuple[str, str, str]] = set() # For deduping
        
        whitelist = category_whitelist if category_whitelist is not None else self.CLINICAL_CATEGORY_WHITELIST

        # Step 1: filter to embedded (h2/h3/h1_leaf) chunks
        embedded_chunks = [c for c in chunks if c.chunk_level in ("h2", "h3", "h1_leaf")]

        # Step 2: apply category whitelist
        if whitelist:
            filtered_chunks = []
            skipped_categories: Dict[str, int] = {}
            for c in embedded_chunks:
                cat = c.metadata.get("category")
                # Category may be a comma-separated string or a list
                if isinstance(cat, str):
                    cats = [x.strip() for x in cat.split(",")]
                elif isinstance(cat, list):
                    cats = cat
                else:
                    cats = [cat]  # None or missing

                # Accept chunk if ANY of its categories is in the whitelist
                if any(ct in whitelist for ct in cats):
                    filtered_chunks.append(c)
                else:
                    for ct in cats:
                        skipped_categories[ct] = skipped_categories.get(ct, 0) + 1

            skipped_count = len(embedded_chunks) - len(filtered_chunks)
            if skipped_count:
                logger.info(
                    "Category filter: kept %d of %d embedded chunks, skipped %d (categories: %s)",
                    len(filtered_chunks), len(embedded_chunks), skipped_count, skipped_categories,
                )
            embedded_chunks = filtered_chunks

        logger.info(
            "Extracting LLM triples from %d embedded chunks (h2/h3/h1_leaf), skipping %d unembedded, for '%s'",
            len(embedded_chunks), len(chunks) - len(embedded_chunks), document_title,
        )

        for chunk in embedded_chunks:
            subchunks = self._split_into_subchunks(chunk.content)

            if len(subchunks) > 1:
                logger.info("  Chunk %s is large (%d chars) - split into %d sub-chunks", chunk.index, len(chunk.content), len(subchunks))

            cpg_chunk_id: Optional[str] = chunk.metadata.get("chunk_id")

            for sub_idx, window in enumerate(subchunks):
                display_idx = f"{chunk.index}.{sub_idx+1}" if len(subchunks) > 1 else chunk.index

                triples = await self._extract_triples_with_llm(
                    text=window["focus"],
                    chunk_index=chunk.index,
                    source=chunk.metadata.get("source", ""),
                    cpg_chunk_id=cpg_chunk_id,
                    before=window["before"],
                    after=window["after"],
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
            if chunk.index < len(embedded_chunks) - 1:
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

