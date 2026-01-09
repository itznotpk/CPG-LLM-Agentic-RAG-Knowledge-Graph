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
    # LLM-BASED DYNAMIC ENTITY EXTRACTION
    # ==========================================================================
    
    # Entity categories (structure only, values are extracted dynamically)
    ENTITY_CATEGORIES = [
        "MEDICATIONS",       # Drug names, pharmaceuticals, drug classes
        "CONDITIONS",        # Diseases, diagnoses, symptoms
        "PROCEDURES",        # Treatments, surgeries, therapies
        "DIAGNOSTIC_TOOLS",  # Tests, scores, questionnaires, imaging
        "RISK_FACTORS",      # Lifestyle factors, comorbidities
        "ADVERSE_EVENTS",    # Side effects, complications
        "ORGANIZATIONS",     # Medical organizations, hospitals
    ]
    
    async def _extract_entities_with_llm(self, text: str) -> Dict[str, List[str]]:
        """
        Use LLM to dynamically extract and classify medical entities from text.
        
        This is fully dynamic - no hardcoded entity values. The LLM identifies
        and categorizes all medical entities based on context.
        
        Args:
            text: Content to extract entities from
            
        Returns:
            Dictionary with entity categories as keys and lists of entities as values
        """
        from pydantic_ai import Agent
        
        try:
            # Import the ingestion model
            from agent.providers import get_ingestion_model
            model = get_ingestion_model()
            
            # Truncate text if too long (LLM context limit)
            max_chars = 4000
            truncated_text = text[:max_chars] if len(text) > max_chars else text
            
            prompt = f"""Analyze this medical text and extract entities into categories.

CATEGORIES:
- MEDICATIONS: Drug names, drug classes (e.g., "Sildenafil", "PDE5 inhibitors", "Nitrates")
- CONDITIONS: Diseases, diagnoses, symptoms (e.g., "Erectile Dysfunction", "Diabetes", "Hypertension")
- PROCEDURES: Treatments, surgeries, therapies (e.g., "Penile prosthesis", "Lifestyle modification")
- DIAGNOSTIC_TOOLS: Tests, scores, questionnaires (e.g., "IIEF-5", "HbA1c", "PSA")
- RISK_FACTORS: Lifestyle factors, comorbidities (e.g., "Smoking", "Obesity", "Advanced age")
- ADVERSE_EVENTS: Side effects, complications (e.g., "Headache", "Flushing", "Priapism")
- ORGANIZATIONS: Medical organizations, hospitals (e.g., "MOH", "WHO", "Malaysian Urological Association")

TEXT:
{truncated_text}

Return ONLY a valid JSON object with the categories as keys and arrays of extracted entity strings as values.
If no entities found for a category, use an empty array [].
Do not include explanations, only the JSON.

Example format:
{{"MEDICATIONS": ["Sildenafil", "Tadalafil"], "CONDITIONS": ["ED", "Diabetes"], "PROCEDURES": [], ...}}
"""
            
            # Create temporary agent for entity extraction
            temp_agent = Agent(model)
            response = await temp_agent.run(prompt)
            result_text = response.output
            
            # Parse JSON response
            # Try to extract JSON from response (may have extra text)
            json_match = re.search(r'\{[^{}]*\}', result_text, re.DOTALL)
            if json_match:
                result_text = json_match.group()
            
            entities = json.loads(result_text)
            
            # Ensure all categories exist
            for category in self.ENTITY_CATEGORIES:
                if category not in entities:
                    entities[category] = []
                # Convert to list if not already
                if not isinstance(entities[category], list):
                    entities[category] = [entities[category]]
            
            logger.debug(f"LLM extracted entities: {entities}")
            return entities
            
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse LLM response as JSON: {e}")
            return {cat: [] for cat in self.ENTITY_CATEGORIES}
        except Exception as e:
            logger.warning(f"LLM entity extraction failed: {e}")
            return {cat: [] for cat in self.ENTITY_CATEGORIES}

    
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
        logger.info("⚠️ Large chunks will be truncated to avoid Graphiti token limits.")
        
        # Check for oversized chunks and warn
        oversized_chunks = [i for i, chunk in enumerate(chunks) if len(chunk.content) > 6000]
        if oversized_chunks:
            logger.warning(f"Found {len(oversized_chunks)} chunks over 6000 chars that will be truncated: {oversized_chunks}")
        
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
                logger.info(f"✓ Added episode {episode_id} to knowledge graph ({episodes_created}/{len(chunks)})")
                
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
    
    async def extract_entities_from_chunks(
        self,
        chunks: List[DocumentChunk],
        use_llm: bool = True
    ) -> List[DocumentChunk]:
        """
        Extract medical entities from chunks and add to metadata.
        
        Uses LLM-based dynamic extraction to identify and categorize entities.
        No hardcoded entity lists - all entities are discovered from the text.
        
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
                # Dynamic LLM-based entity extraction
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
                # Fallback to legacy pattern matching (deprecated)
                entities = {
                    "conditions": self._extract_conditions(content),
                    "medications": self._extract_medications(content),
                    "diagnostic_tools": self._extract_technologies(content),
                    "procedures": [],
                    "risk_factors": self._extract_risk_factors(content),
                    "adverse_events": self._extract_adverse_events(content),
                    "organizations": self._extract_companies(content),
                    "extraction_method": "pattern"
                }
            
            # Log progress
            if (i + 1) % 5 == 0 or i == 0:
                logger.info(f"  Processed chunk {i + 1}/{len(chunks)}")
            
            # Create enriched chunk
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
            
            # Preserve embedding if it exists
            if hasattr(chunk, 'embedding'):
                enriched_chunk.embedding = chunk.embedding
            
            enriched_chunks.append(enriched_chunk)
        
        # Log summary
        total_entities = sum(
            len(c.metadata.get("entities", {}).get(cat, []))
            for c in enriched_chunks
            for cat in ["conditions", "medications", "procedures", "diagnostic_tools"]
        )
        logger.info(f"Entity extraction complete: {total_entities} entities across {len(enriched_chunks)} chunks")
        
        return enriched_chunks
    
    # ==========================================================================
    # LEGACY FALLBACK: Pattern-Based Entity Extraction (DEPRECATED)
    # ==========================================================================
    # NOTE: These hardcoded sets are DEPRECATED and only used as fallback
    # when use_llm=False in extract_entities_from_chunks().
    # 
    # PRIMARY METHOD: LLM-based extraction via _extract_entities_with_llm()
    # which dynamically identifies ALL entities from text without limitation.
    # ==========================================================================
    
    # 1. DIAGNOSIS & CONDITIONS (For "Risk Assessment" & "Clinical Summary")
    CONDITIONS = {
        "Erectile Dysfunction", "Psychogenic ED", "Organic ED", "Mixed ED",
        "Vasculogenic ED", "Neurogenic ED", "Arteriogenic ED", "Veno-occlusive dysfunction",
        "Peyronie's disease", "Hypogonadism", "Testicular atrophy",
        "Diabetes Mellitus", "Type 2 Diabetes", "Hypertension", "Dyslipidemia",
        "Cardiovascular Disease", "Ischaemic Heart Disease", "Coronary Artery Disease",
        "Heart Failure", "Atrial Fibrillation", "Stroke", "Depression", "Anxiety",
        "Benign Prostatic Hyperplasia", "LUTS", "Prostate Cancer", "Spinal Cord Injury",
        "Premature Ejaculation", "Obesity", "Metabolic Syndrome"
    }

    # 2. PHARMACOLOGICAL AGENTS (For "Pharmacological Management")
    MEDICATIONS = {
        # Drug Classes
        "Phosphodiesterase-5 inhibitors", "PDE5i", "Alpha-blockers", "Antihypertensives",
        "Nitrates", "Androgens", "Antidepressants", "SSRI",
        # Specific Agents (ED Treatment)
        "Sildenafil", "Tadalafil", "Vardenafil", "Avanafil", "Udenafil",
        "Alprostadil", "Papaverine", "Phentolamine", "Yohimbine",
        # Contraindicated/Interacting Agents
        "Glyceryl trinitrate", "Isosorbide mononitrate", "Riociguat", "Doxazosin",
        # Traditional/Complementary (mentioned in CPG)
        "Tongkat Ali", "Ginseng", "L-arginine", "Propionyl-L-carnitine"
    }

    # 3. DIAGNOSTIC TOOLS & SCORES (For "Investigations" & "Assessment")
    DIAGNOSTIC_TOOLS = {
        # Scores/Questionnaires
        "IIEF-5", "International Index of Erectile Function", 
        "EHS", "Erection Hardness Score", 
        "Framingham Risk Score", "Princeton Consensus", "PHQ-9", "GAD-7",
        # Lab/Imaging
        "Fasting Blood Glucose", "HbA1c", "Lipid Profile", "Total Testosterone",
        "Prolactin", "LH", "PSA", "Serum Creatinine", "Urinalysis",
        "Nocturnal Penile Tumescence", "NPTR", 
        "Penile Duplex Doppler Ultrasound", "Pudendal Arteriography"
    }

    # 4. INTERVENTIONS & PROCEDURES (For "Interventions" & "Disposition")
    PROCEDURES = {
        # Lifestyle
        "Lifestyle modification", "Weight loss", "Smoking cessation", 
        "Pelvic floor muscle training", "Physical activity",
        # Mechanical/Surgical
        "Vacuum Erection Device", "VED", 
        "Low-intensity Extracorporeal Shockwave Therapy", "Li-ESWT",
        "Penile Prosthesis", "Inflatable Penile Prosthesis", "Malleable Prosthesis",
        "Penile Revascularization", "Angioplasty",
        # Psych
        "Psychosexual therapy", "CBT", "Couples therapy", "Sex therapy"
    }

    # 5. RISK FACTORS & SYMPTOMS (For "Clinical Summary")
    RISK_FACTORS = {
        "Smoking", "Sedentary lifestyle", "Alcohol consumption", "Recreational drug use",
        "Advanced age", "Pelvic surgery", "Radiotherapy", "Trauma",
        "Morning erection loss", "Low libido", "Performance anxiety"
    }

    # 6. ADVERSE EVENTS (For "Monitoring & Nursing")
    ADVERSE_EVENTS = {
        "Priapism", "Hypotension", "Headache", "Flushing", "Dyspepsia", 
        "Nasal congestion", "Visual abnormalities", "Myalgia", "Back pain",
        "NAION", "Hearing loss"
    }
    
    # 7. MEDICAL ORGANIZATIONS (Malaysia Healthcare)
    MEDICAL_ORGANIZATIONS = {
        "MOH", "Ministry of Health", "KKM", "Kementerian Kesihatan Malaysia",
        "Malaysian Urological Association", "Academy of Medicine Malaysia",
        "Malaysian Medical Association", "WHO", "AUA", "EAU"
    }
    
    # 8. DEFINITIONS (Abbreviations and term definitions)
    DEFINITIONS = {
        "ED": "Erectile Dysfunction",
        "IIEF-5": "5-item version of International Index of Erectile Function",
        "EHS": "Erection Hardness Score",
        "PDE5i": "Phosphodiesterase-5 inhibitors",
        "ASCVD": "Atherosclerotic Cardiovascular Disease",
        "VED": "Vacuum Erection Device",
        "Li-ESWT": "Low-intensity Extracorporeal Shockwave Therapy",
        "LUTS": "Lower Urinary Tract Symptoms",
        "BPH": "Benign Prostatic Hyperplasia",
        "NPT": "Nocturnal Penile Tumescence",
        "PSA": "Prostate-Specific Antigen",
        "HbA1c": "Glycated Hemoglobin",
        "LH": "Luteinizing Hormone",
        "PHQ-9": "Patient Health Questionnaire-9",
        "GAD-7": "Generalized Anxiety Disorder 7-item scale",
        "CBT": "Cognitive Behavioral Therapy",
        "MOH": "Ministry of Health",
        "CPG": "Clinical Practice Guideline",
        "Exercise Ability": "Walking 1.6 km in 20 min or climbing 2 flights of stairs in 10 sec",
    }
    
    def _extract_companies(self, text: str) -> List[str]:
        """Extract organization/institution names from text."""
        # Healthcare organizations and institutions
        organizations = self.MEDICAL_ORGANIZATIONS | {
            # Pharmaceutical companies
            "Pfizer", "Eli Lilly", "Bayer", "GSK", "Novartis", "Roche",
            # Hospitals (add Malaysian hospitals as needed)
            "Hospital Kuala Lumpur", "HKL", "UMMC", "IJN"
        }
        
        found = set()
        text_lower = text.lower()
        
        for org in organizations:
            pattern = r'\b' + re.escape(org.lower()) + r'\b'
            if re.search(pattern, text_lower):
                found.add(org)
        
        return list(found)
    
    def _extract_technologies(self, text: str) -> List[str]:
        """Extract medical terms, diagnostic tools, and procedures from text."""
        # Combine diagnostic tools and procedures
        medical_terms = self.DIAGNOSTIC_TOOLS | self.PROCEDURES | {
            "AI", "machine learning", "telemedicine", "telehealth",
            "electronic health record", "EHR", "clinical decision support"
        }
        
        found = set()
        text_lower = text.lower()
        
        for term in medical_terms:
            if term.lower() in text_lower:
                found.add(term)
        
        return list(found)
    
    def _extract_conditions(self, text: str) -> List[str]:
        """Extract medical conditions and diagnoses from text."""
        found = set()
        text_lower = text.lower()
        
        for condition in self.CONDITIONS:
            pattern = r'\b' + re.escape(condition.lower()) + r'\b'
            if re.search(pattern, text_lower):
                found.add(condition)
        
        return list(found)
    
    def _extract_medications(self, text: str) -> List[str]:
        """Extract medication and drug names from text."""
        found = set()
        text_lower = text.lower()
        
        for med in self.MEDICATIONS:
            pattern = r'\b' + re.escape(med.lower()) + r'\b'
            if re.search(pattern, text_lower):
                found.add(med)
        
        return list(found)
    
    def _extract_risk_factors(self, text: str) -> List[str]:
        """Extract risk factors and symptoms from text."""
        found = set()
        text_lower = text.lower()
        
        for rf in self.RISK_FACTORS:
            if rf.lower() in text_lower:
                found.add(rf)
        
        return list(found)
    
    def _extract_adverse_events(self, text: str) -> List[str]:
        """Extract adverse events and side effects from text."""
        found = set()
        text_lower = text.lower()
        
        for ae in self.ADVERSE_EVENTS:
            pattern = r'\b' + re.escape(ae.lower()) + r'\b'
            if re.search(pattern, text_lower):
                found.add(ae)
        
        return list(found)
    
    def _extract_people(self, text: str) -> List[str]:
        """Extract person names from text (medical authors, experts)."""
        # Add Malaysian medical experts or CPG authors as needed
        medical_experts = {
            # Add CPG authors here if known
        }
        
        found = set()
        for person in medical_experts:
            if person in text:
                found.add(person)
        
        return list(found)
    
    def _extract_locations(self, text: str) -> List[str]:
        """Extract location names from text."""
        locations = {
            # Malaysian states and cities
            "Malaysia", "Kuala Lumpur", "Selangor", "Penang", "Johor",
            "Sabah", "Sarawak", "Perak", "Kedah", "Kelantan", "Terengganu",
            "Pahang", "Negeri Sembilan", "Melaka", "Perlis", "Putrajaya",
            # Healthcare facilities
            "Hospital", "Klinik", "Pusat Kesihatan"
        }
        
        found = set()
        for location in locations:
            if location in text:
                found.add(location)
        
        return list(found)
    
    def _extract_definitions(self, text: str) -> List[Dict[str, str]]:
        """
        Extract term definitions from text.
        
        Looks for abbreviations and terms that have known definitions,
        and extracts any new definition patterns from the text.
        
        Args:
            text: Content to extract definitions from
            
        Returns:
            List of dicts with 'term' and 'definition' keys
        """
        found_definitions = []
        text_lower = text.lower()
        
        # Check for known definitions mentioned in text
        for term, definition in self.DEFINITIONS.items():
            if term.lower() in text_lower:
                found_definitions.append({
                    "term": term,
                    "definition": definition,
                    "source": "known"
                })
        
        # Extract new definitions using patterns
        definition_patterns = [
            # "TERM = definition"
            r'\b([A-Z][A-Z0-9\-]{1,10})\s*=\s*([^.;\n]+[a-z])',
            # "TERM (definition)"
            r'\b([A-Z][A-Z0-9\-]{1,10})\s+\(([^)]+)\)',
        ]
        
        for pattern in definition_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                term = match[0].strip()
                definition = match[1].strip()
                
                # Skip if already in known definitions
                if term not in self.DEFINITIONS and len(definition) <= 100:
                    found_definitions.append({
                        "term": term,
                        "definition": definition,
                        "source": "extracted"
                    })
        
        return found_definitions
    
    # ==========================================================================
    # MEDICAL RELATIONSHIP EXTRACTION (Neo4j Knowledge Graph)
    # ==========================================================================
    
    # Relationship definitions for CPG
    MEDICAL_RELATIONSHIPS = {
        'TREATS': 'Drug/Intervention treats a condition',
        'CONTRAINDICATED_WITH': 'Drug is contraindicated with another drug or condition',
        'HAS_DOSAGE': 'Drug has specific dosage information',
        'REQUIRES_MONITORING': 'Drug/Intervention requires monitoring of labs/symptoms',
        'RECOMMENDED_FOR': 'Intervention is recommended for specific patient profile',
        'CAUSES': 'Drug causes adverse event',
        'ALTERNATIVE_TO': 'Drug is alternative to another drug',
        'FIRST_LINE_FOR': 'Drug is first-line treatment for condition',
        'SECOND_LINE_FOR': 'Drug is second-line treatment for condition',
        'ASSESSED_BY': 'Condition is assessed by diagnostic tool',
        'HAS_DEFINITION': 'Term has a definition/explanation',
    }
    
    # Knowledge base for relationship extraction (Malaysia CPG ED)
    DRUG_CONDITION_TREATMENTS = {
        # PDE5 Inhibitors treat ED
        "Sildenafil": ["Erectile Dysfunction", "Vasculogenic ED", "Psychogenic ED"],
        "Tadalafil": ["Erectile Dysfunction", "Vasculogenic ED", "Benign Prostatic Hyperplasia", "LUTS"],
        "Vardenafil": ["Erectile Dysfunction"],
        "Avanafil": ["Erectile Dysfunction"],
        "Alprostadil": ["Erectile Dysfunction", "Neurogenic ED"],
        "Testosterone": ["Hypogonadism", "Low libido"],
        # Procedures
        "Vacuum Erection Device": ["Erectile Dysfunction", "Post-prostatectomy ED"],
        "Li-ESWT": ["Vasculogenic ED", "Mild ED"],
        "Penile Prosthesis": ["Refractory ED", "Severe ED"],
        "Psychosexual therapy": ["Psychogenic ED", "Performance anxiety"],
    }
    
    DRUG_CONTRAINDICATIONS = {
        # PDE5i contraindications
        "Sildenafil": ["Nitrates", "Glyceryl trinitrate", "Isosorbide mononitrate", "Riociguat", "Severe Heart Failure"],
        "Tadalafil": ["Nitrates", "Glyceryl trinitrate", "Isosorbide mononitrate", "Riociguat", "Severe Heart Failure"],
        "Vardenafil": ["Nitrates", "Glyceryl trinitrate", "Isosorbide mononitrate", "Riociguat"],
        "Avanafil": ["Nitrates", "Riociguat"],
        # Alpha-blocker interactions
        "PDE5i": ["Alpha-blockers", "Doxazosin"],
    }
    
    DRUG_DOSAGES = {
        "Sildenafil": ["50mg on-demand", "25-100mg", "Start 50mg, adjust based on response"],
        "Tadalafil": ["10mg on-demand", "5mg daily", "2.5-20mg", "10-20mg on-demand"],
        "Vardenafil": ["10mg on-demand", "5-20mg"],
        "Avanafil": ["100mg on-demand", "50-200mg"],
        "Alprostadil": ["10-20mcg intracavernosal", "125-1000mcg intraurethral"],
    }
    
    DRUG_MONITORING = {
        "Testosterone": ["PSA", "Hematocrit", "Lipid Profile", "Liver function tests"],
        "Alprostadil": ["Priapism monitoring", "Blood pressure"],
        "PDE5i": ["Blood pressure", "Visual symptoms", "Hearing changes"],
    }
    
    DRUG_ADVERSE_EVENTS = {
        "Sildenafil": ["Headache", "Flushing", "Dyspepsia", "Nasal congestion", "Visual abnormalities", "NAION"],
        "Tadalafil": ["Headache", "Back pain", "Myalgia", "Dyspepsia", "Flushing"],
        "Vardenafil": ["Headache", "Flushing", "Dyspepsia"],
        "Alprostadil": ["Priapism", "Penile pain", "Fibrosis"],
    }
    
    CONDITION_ASSESSMENTS = {
        "Erectile Dysfunction": ["IIEF-5", "EHS", "Nocturnal Penile Tumescence", "Penile Duplex Doppler Ultrasound"],
        "Cardiovascular Disease": ["Framingham Risk Score", "Princeton Consensus", "ECG"],
        "Hypogonadism": ["Total Testosterone", "LH", "Prolactin"],
        "Diabetes Mellitus": ["HbA1c", "Fasting Blood Glucose"],
        "Depression": ["PHQ-9"],
        "Anxiety": ["GAD-7"],
    }
    
    PATIENT_PROFILE_RECOMMENDATIONS = {
        "Li-ESWT": ["Mild vasculogenic ED", "PDE5i responders wanting drug-free option"],
        "Penile Prosthesis": ["Refractory ED", "PDE5i non-responders", "Post-radical prostatectomy"],
        "Psychosexual therapy": ["Psychogenic ED", "Performance anxiety", "Relationship issues"],
        "Tadalafil daily": ["Frequent sexual activity", "Concurrent BPH/LUTS"],
        "Vacuum Erection Device": ["Elderly patients", "Post-prostatectomy", "Contraindication to PDE5i"],
    }
    
    def extract_medical_relationships(
        self,
        text: str,
        entities: Dict[str, List[str]]
    ) -> List[Dict[str, Any]]:
        """
        Extract medical relationships from text based on extracted entities.
        
        Args:
            text: Chunk text content
            entities: Previously extracted entities
            
        Returns:
            List of relationship dictionaries with source, target, type, and evidence
        """
        relationships = []
        text_lower = text.lower()
        
        medications = entities.get("medications", [])
        conditions = entities.get("conditions", [])
        procedures = entities.get("procedures", []) + entities.get("diagnostic_tools", [])
        adverse_events = entities.get("adverse_events", [])
        
        # 1. TREATS relationships
        for med in medications:
            if med in self.DRUG_CONDITION_TREATMENTS:
                for condition in self.DRUG_CONDITION_TREATMENTS[med]:
                    if condition.lower() in text_lower or any(c.lower() == condition.lower() for c in conditions):
                        relationships.append({
                            "source": med,
                            "source_type": "Drug",
                            "target": condition,
                            "target_type": "Condition",
                            "relationship": "TREATS",
                            "evidence": self._extract_evidence_snippet(text, med, condition)
                        })
        
        # 2. CONTRAINDICATED_WITH relationships
        for med in medications:
            if med in self.DRUG_CONTRAINDICATIONS:
                for contra in self.DRUG_CONTRAINDICATIONS[med]:
                    if contra.lower() in text_lower:
                        relationships.append({
                            "source": med,
                            "source_type": "Drug",
                            "target": contra,
                            "target_type": "Drug" if contra in self.MEDICATIONS else "Condition",
                            "relationship": "CONTRAINDICATED_WITH",
                            "evidence": self._extract_evidence_snippet(text, med, contra)
                        })
        
        # 3. HAS_DOSAGE relationships
        for med in medications:
            if med in self.DRUG_DOSAGES:
                # Look for dosage patterns in text
                dosage_pattern = r'\b(\d+(?:\.\d+)?)\s*(?:mg|mcg|ml)\b'
                if re.search(dosage_pattern, text, re.IGNORECASE):
                    for dosage in self.DRUG_DOSAGES[med]:
                        if any(d in text_lower for d in dosage.lower().split()):
                            relationships.append({
                                "source": med,
                                "source_type": "Drug",
                                "target": dosage,
                                "target_type": "Dosage",
                                "relationship": "HAS_DOSAGE",
                                "evidence": self._extract_evidence_snippet(text, med, dosage.split()[0])
                            })
                            break
        
        # 4. REQUIRES_MONITORING relationships
        for med in medications:
            if med in self.DRUG_MONITORING:
                for monitor in self.DRUG_MONITORING[med]:
                    if monitor.lower() in text_lower:
                        relationships.append({
                            "source": med,
                            "source_type": "Drug",
                            "target": monitor,
                            "target_type": "LabTest",
                            "relationship": "REQUIRES_MONITORING",
                            "evidence": self._extract_evidence_snippet(text, med, monitor)
                        })
        
        # 5. CAUSES (adverse events)
        for med in medications:
            if med in self.DRUG_ADVERSE_EVENTS:
                for ae in self.DRUG_ADVERSE_EVENTS[med]:
                    if ae.lower() in text_lower:
                        relationships.append({
                            "source": med,
                            "source_type": "Drug",
                            "target": ae,
                            "target_type": "AdverseEvent",
                            "relationship": "CAUSES",
                            "evidence": self._extract_evidence_snippet(text, med, ae)
                        })
        
        # 6. ASSESSED_BY relationships
        for condition in conditions:
            if condition in self.CONDITION_ASSESSMENTS:
                for tool in self.CONDITION_ASSESSMENTS[condition]:
                    if tool.lower() in text_lower:
                        relationships.append({
                            "source": condition,
                            "source_type": "Condition",
                            "target": tool,
                            "target_type": "DiagnosticTool",
                            "relationship": "ASSESSED_BY",
                            "evidence": self._extract_evidence_snippet(text, condition, tool)
                        })
        
        # 7. RECOMMENDED_FOR relationships (procedures -> patient profiles)
        for proc in procedures:
            if proc in self.PATIENT_PROFILE_RECOMMENDATIONS:
                for profile in self.PATIENT_PROFILE_RECOMMENDATIONS[proc]:
                    if profile.lower() in text_lower:
                        relationships.append({
                            "source": proc,
                            "source_type": "Intervention",
                            "target": profile,
                            "target_type": "PatientProfile",
                            "relationship": "RECOMMENDED_FOR",
                            "evidence": self._extract_evidence_snippet(text, proc, profile)
                        })
        
        # 8. Detect FIRST_LINE_FOR / SECOND_LINE_FOR from text patterns
        first_line_patterns = [
            r'first[- ]line\s+(?:treatment|therapy|option)',
            r'recommended\s+as\s+first',
            r'initial\s+treatment',
        ]
        second_line_patterns = [
            r'second[- ]line\s+(?:treatment|therapy|option)',
            r'alternative\s+(?:treatment|therapy)',
            r'if\s+.*\s+fails',
        ]
        
        for med in medications:
            if med.lower() in text_lower:
                for pattern in first_line_patterns:
                    if re.search(pattern, text_lower):
                        for condition in conditions:
                            relationships.append({
                                "source": med,
                                "source_type": "Drug",
                                "target": condition,
                                "target_type": "Condition",
                                "relationship": "FIRST_LINE_FOR",
                                "evidence": self._extract_sentence_containing(text, med)
                            })
                        break
                
                for pattern in second_line_patterns:
                    if re.search(pattern, text_lower):
                        for condition in conditions:
                            relationships.append({
                                "source": med,
                                "source_type": "Drug",
                                "target": condition,
                                "target_type": "Condition",
                                "relationship": "SECOND_LINE_FOR",
                                "evidence": self._extract_sentence_containing(text, med)
                            })
                        break
        
        return relationships
    
    def _extract_evidence_snippet(self, text: str, term1: str, term2: str, context_chars: int = 150) -> str:
        """Extract a text snippet containing both terms as evidence."""
        text_lower = text.lower()
        term1_lower = term1.lower()
        term2_lower = term2.lower()
        
        # Find positions
        pos1 = text_lower.find(term1_lower)
        pos2 = text_lower.find(term2_lower)
        
        if pos1 == -1 or pos2 == -1:
            return ""
        
        # Get range containing both terms
        start = max(0, min(pos1, pos2) - context_chars // 2)
        end = min(len(text), max(pos1 + len(term1), pos2 + len(term2)) + context_chars // 2)
        
        snippet = text[start:end].strip()
        
        # Add ellipsis if truncated
        if start > 0:
            snippet = "..." + snippet
        if end < len(text):
            snippet = snippet + "..."
        
        return snippet
    
    def _extract_sentence_containing(self, text: str, term: str) -> str:
        """Extract the sentence containing a term."""
        sentences = re.split(r'[.!?]\s+', text)
        for sentence in sentences:
            if term.lower() in sentence.lower():
                return sentence.strip()[:200]
        return ""
    
    async def build_relationship_graph(
        self,
        chunks: List[DocumentChunk],
        document_title: str
    ) -> Dict[str, Any]:
        """
        Build knowledge graph with medical relationships.
        
        Args:
            chunks: List of chunks with entities extracted
            document_title: Title of the source document
            
        Returns:
            Summary of relationships created
        """
        all_relationships = []
        
        for chunk in chunks:
            entities = chunk.metadata.get("entities", {})
            relationships = self.extract_medical_relationships(chunk.content, entities)
            
            for rel in relationships:
                rel["source_document"] = document_title
                rel["chunk_index"] = chunk.index
            
            all_relationships.extend(relationships)
        
        # Log relationship summary
        rel_counts = {}
        for rel in all_relationships:
            rel_type = rel["relationship"]
            rel_counts[rel_type] = rel_counts.get(rel_type, 0) + 1
        
        logger.info(f"Extracted {len(all_relationships)} relationships: {rel_counts}")
        
        return {
            "relationships": all_relationships,
            "counts": rel_counts,
            "total": len(all_relationships)
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
    
    # Extract medical entities
    enriched_chunks = await graph_builder.extract_entities_from_chunks(chunks)
    
    for i, chunk in enumerate(enriched_chunks):
        entities = chunk.metadata.get('entities', {})
        print(f"Chunk {i}:")
        print(f"  Medications: {entities.get('medications', [])}")
        print(f"  Conditions: {entities.get('conditions', [])}")
        print(f"  Adverse Events: {entities.get('adverse_events', [])}")
    
    # Add to knowledge graph
    try:
        result = await graph_builder.add_document_to_graph(
            chunks=enriched_chunks,
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