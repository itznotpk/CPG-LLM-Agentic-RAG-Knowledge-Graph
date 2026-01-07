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

---

## Phase 8: Full Deployment (TODO)

### Full CPG Ingestion
- [ ] Ingest complete Malaysia ED CPG PDF
- [ ] Verify all sections are parsed
- [ ] Validate metadata extraction accuracy
- [ ] Test all 12 agent tools with real queries

### Performance Optimization
- [ ] Index optimization for CPG searches
- [ ] Batch processing for large PDFs
- [ ] Caching for frequent queries

### Validation
- [ ] Verify Grade A recommendations are correct
- [ ] Validate drug contraindication accuracy
- [ ] Test population-specific filtering
- [ ] Cross-reference with original CPG document

---

## Current Status

**Completed:** Phases 1-7 (Foundation, CPG Enhancement, Agent Tools, System Prompt, Pipeline, Testing, Cleanup)

**Next:** Phase 8 - Full CPG ingestion and validation

---

## Quick Reference

### CLI Commands
```bash
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
