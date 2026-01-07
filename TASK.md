# Task List - CPG Agentic RAG with Knowledge Graph

## Overview
This document tracks all tasks for building the CPG (Clinical Practice Guidelines) Agentic RAG system with knowledge graph capabilities for the Malaysia ED Treatment Guidelines.

---

## Phase 1: Foundation & Setup ✅

### Database Setup
- [x] Create Neon PostgreSQL database with pgvector
- [x] Create Neo4j Aura instance
- [x] Set up database schema with CPG columns
- [x] Create connection utilities

### Environment Configuration
- [x] Configure OpenRouter for LLM (Gemini)
- [x] Configure Gemini for embeddings (768 dimensions)
- [x] Set up environment variables
- [x] Test connectivity to all services

---

## Phase 2: CPG Enhancement ✅

### Step 1: Structural PDF Parsing
- [x] Create `cpg_parser.py` with hierarchical parsing
- [x] Detect headers by font size and boldness
- [x] Maintain section hierarchy (Section → Subsection → Content)
- [x] Add `parent_chunk_id` for chunk relationships

### Step 2: Metadata Extraction
- [x] Create `CPGMetadataExtractor` class
- [x] Extract evidence levels (Level I, II, III)
- [x] Extract grades (Grade A, B, C)
- [x] Identify target populations (Diabetes, Cardiac, Elderly)
- [x] Classify categories (Diagnosis, Treatment, Referral)
- [x] Flag recommendations, tables, algorithms

### Step 3: Table & Algorithm Handling
- [x] Table extraction with bounding boxes
- [x] Convert tables to structured JSON
- [x] Vision LLM integration for flowchart description
- [x] Preserve table headers and rows

### Step 4: Knowledge Graph Relationships
- [x] Define 7 medical entity categories in `graph_builder.py`
- [x] Implement relationship extraction (TREATS, CONTRAINDICATED_WITH, etc.)
- [x] Add keyword-based entity detection
- [x] Integrate with Graphiti for graph storage

### Step 5: Database Schema Updates
- [x] Add CPG columns to `chunks` table in `schema.sql`
- [x] Create `cpg_filtered_search()` function
- [x] Create `get_chunk_with_parent_context()` function
- [x] Create `get_grade_a_recommendations()` function

---

## Phase 3: Agent Tools ✅

### Core Search Tools
- [x] `vector_search` - Semantic similarity search
- [x] `graph_search` - Knowledge graph facts
- [x] `hybrid_search` - Vector + keyword combined

### CPG-Specific Tools
- [x] `cpg_filtered_search` - Filter by grade/population/category
- [x] `get_grade_a_recommendations` - Highest evidence only
- [x] `get_drug_information` - Contraindications, dosages, side effects
- [x] `get_treatment_recommendations` - Treatments by condition
- [x] `get_chunk_with_parent_context` - Hierarchical context

### Entity Tools
- [x] `get_entity_relationships` - Entity connections in graph
- [x] `get_entity_timeline` - Temporal facts

### Document Tools
- [x] `get_document` - Full document retrieval
- [x] `list_documents` - Available documents

---

## Phase 4: System Prompt ✅

### Clinical Decision Support Prompt
- [x] Define role as CPG clinical assistant
- [x] List medical entity types
- [x] Document tool usage guidance
- [x] Add example clinical queries
- [x] Include evidence grade citation instructions
- [x] Add disclaimer for clinical use

---

## Phase 5: Ingestion Pipeline ✅

### Pipeline Integration
- [x] Add `use_cpg_parser` flag to ingest.py
- [x] Create `_ingest_cpg_pdf()` method
- [x] Create `_save_cpg_to_postgres()` with CPG columns
- [x] Add entity extraction to chunks
- [x] Integrate with graph builder

### Debug Output
- [x] Add `save_processed` flag
- [x] Save markdown to `documents/_processed/{name}.md`
- [x] Save chunks JSON to `documents/_processed/{name}_chunks.json`
- [x] Save structure summary to `documents/_processed/{name}_structure.json`

---

## Phase 6: Testing ✅

### Trial Ingestion
- [x] Test with 10-page trial PDF (pages 1-10)
- [x] Verify chunks are created in PostgreSQL
- [x] Verify entities are extracted
- [x] Verify graph nodes are created in Neo4j
- [x] Test CLI with sample queries

---

## Phase 7: Cleanup ✅

### Remove Old Tech References
- [x] Update README.md to CPG focus
- [x] Update PLANNING.md to CPG focus
- [x] Update TASK.md to CPG focus
- [x] Remove `SimpleEntityExtractor` with old tech patterns
- [x] Update `main()` example in graph_builder.py
- [x] Update requirements.txt with organized dependencies (2026-01-07)

---

## Phase 8: Validation & Testing (IN PROGRESS)

### Full CPG Ingestion
- [ ] Ingest complete Malaysia ED CPG PDF (full document, not just 10 pages)
- [ ] Verify all sections are parsed correctly
- [ ] Validate metadata extraction accuracy (evidence levels, grades)
- [ ] Test with documents containing complex tables and algorithms

### Tool Validation
- [ ] Test `vector_search` with various clinical queries
- [ ] Test `graph_search` for entity relationships
- [ ] Test `hybrid_search` combined results
- [ ] Test `cpg_filtered_search` with grade/population filters
- [ ] Test `get_grade_a_recommendations` returns correct recommendations
- [ ] Test `get_drug_information` for all PDE5 inhibitors
- [ ] Test `get_treatment_recommendations` by condition
- [ ] Test `get_chunk_with_parent_context` hierarchical retrieval
- [ ] Test `get_entity_relationships` in Neo4j
- [ ] Test `get_entity_timeline` temporal facts
- [ ] Test `get_document` and `list_documents`

### Data Structure Validation
- [ ] Verify vector DB embeddings are correct (768 dimensions)
- [ ] Verify knowledge graph entities are properly linked
- [ ] Verify CPG metadata columns are populated

---

## Phase 9: Local LLM Support (TODO)

### Ollama Integration
- [ ] Add Ollama provider to `providers.py`
- [ ] Configure local model selection (llama3, mistral, etc.)
- [ ] Test with local embeddings (nomic-embed-text)
- [ ] Update .env.example with Ollama configuration
- [ ] Document offline usage in README

---

## Phase 10: Reflector Agent (TODO)

### Self-Critique Implementation
- [ ] Design reflection prompt for clinical accuracy
- [ ] Implement reflection loop after initial response
- [ ] Add evidence grade verification check
- [ ] Add contraindication cross-reference check
- [ ] Implement retry mechanism for incomplete answers
- [ ] Test reflection quality improvement

---

## Phase 11: UI Integration (TODO)

### Replace CLI with Web UI
- [ ] Choose framework (Streamlit, Gradio, or custom React)
- [ ] Design clinical query interface
- [ ] Implement streaming response display
- [ ] Add tool usage visualization
- [ ] Add source/evidence citation display
- [ ] Deploy to cloud (optional)

---

## Current Status

**Completed:** Phases 1-7 (Foundation, CPG Enhancement, Agent Tools, System Prompt, Pipeline, Testing, Cleanup)

**In Progress:** Phase 8 - Validation & Testing

**Next:** Phase 9 (Ollama) → Phase 10 (Reflector) → Phase 11 (UI)

---

## Discovered During Work (2026-01-07)
- requirements.txt was missing `pymupdf` and `pymupdf4llm` packages
- Old requirements had many unnecessary transitive dependencies
- Cleaned up and organized requirements.txt with categories

---

## Quick Reference

### CLI Commands
```bash
# Install dependencies
pip install -r requirements.txt

# Ingest CPG documents
python -m ingestion.ingest --clean -v

# Run CLI agent
python cli.py

# Run API server
python api.py
```

### Example Queries
```
What is the first-line treatment for ED?
Give me Grade A recommendations
What are contraindications for Sildenafil?
How is ED diagnosed in diabetic patients?
```
