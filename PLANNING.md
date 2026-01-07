# CPG Agentic RAG with Knowledge Graph - Project Plan

## Project Overview

This project builds an AI-powered **Clinical Practice Guidelines (CPG) Assistant** that combines Agentic RAG (Retrieval Augmented Generation) with knowledge graph capabilities to provide evidence-based clinical decision support for the **Malaysia CPG on Erectile Dysfunction Management**. The system uses PostgreSQL with pgvector for vector search and Neo4j (via Graphiti) for knowledge graph operations.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    API Layer                             │
│  ┌─────────────────┐        ┌────────────────────┐     │
│  │   FastAPI       │        │   Streaming SSE    │     │
│  │   Endpoints     │        │   Responses        │     │
│  └────────┬────────┘        └────────────────────┘     │
│           │                                              │
├───────────┴──────────────────────────────────────────────┤
│                    Agent Layer                           │
│  ┌─────────────────┐        ┌────────────────────┐     │
│  │  Pydantic AI    │        │   12 Agent Tools   │     │
│  │    Agent        │◄──────►│  - CPG Search      │     │
│  └────────┬────────┘        │  - Drug Info       │     │
│           │                 │  - Graph Search    │     │
│           │                 └────────────────────┘     │
├───────────┴──────────────────────────────────────────────┤
│                  Storage Layer                           │
│  ┌─────────────────┐        ┌────────────────────┐     │
│  │   PostgreSQL    │        │      Neo4j         │     │
│  │   + pgvector    │        │   (via Graphiti)   │     │
│  │  CPG Metadata   │        │  Medical Entities  │     │
│  └─────────────────┘        └────────────────────┘     │
└─────────────────────────────────────────────────────────┘
```

## Core Components

### 1. Agent System (`/agent`)
- **agent.py**: Pydantic AI agent with 12 registered tools for clinical decision support
- **tools.py**: Tool implementations for CPG search, drug info, treatment recommendations
- **prompts.py**: System prompts for clinical reasoning and evidence-based responses
- **api.py**: FastAPI endpoints with streaming support
- **db_utils.py**: PostgreSQL database utilities
- **graph_utils.py**: Neo4j/Graphiti utilities for medical knowledge graph
- **models.py**: Pydantic models for CPG data validation
- **providers.py**: LLM provider abstraction (OpenRouter, Gemini)

### 2. Ingestion System (`/ingestion`)
- **ingest.py**: Main ingestion pipeline with CPG-specific processing
- **cpg_parser.py**: Hierarchical PDF parser for CPG documents
- **chunker.py**: Semantic chunking with 1200 character size
- **embedder.py**: Document embedding generation (768 dimensions)
- **graph_builder.py**: Medical entity and relationship extraction
- **cleaner.py**: Database cleanup utilities

### 3. Database Schema (`/sql`)
- **schema.sql**: PostgreSQL schema with CPG-specific columns

### 4. CLI Interface (`/cli.py`)
- Interactive command-line interface for clinical queries
- Real-time streaming with tool usage visibility
- Evidence grade citations in responses

## CPG-Specific Features

### Medical Entity Categories
| Category | Examples |
|----------|----------|
| CONDITIONS | Erectile Dysfunction, Diabetes, Cardiovascular Disease |
| MEDICATIONS | Sildenafil, Tadalafil, Vardenafil, Avanafil |
| PROCEDURES | Penile Prosthesis, Intracavernosal Injection, Li-ESWT |
| DIAGNOSTIC_TOOLS | IIEF-5, EHS, Penile Doppler Ultrasound |
| RISK_FACTORS | Smoking, Obesity, Hypertension |
| ADVERSE_EVENTS | Headache, Flushing, Priapism |
| MEDICAL_ORGANIZATIONS | MOH Malaysia, AUA, EAU |

### Knowledge Graph Relationships
| Relationship | Description |
|--------------|-------------|
| TREATS | Medication → Condition |
| CONTRAINDICATED_WITH | Medication → Drug/Condition |
| HAS_DOSAGE | Medication → Dosage Info |
| REQUIRES_MONITORING | Medication → Parameter |
| CAUSES | Medication → Adverse Event |
| ASSESSED_BY | Condition → Diagnostic Tool |
| RECOMMENDED_FOR | Treatment → Patient Population |

### CPG Metadata Fields
| Field | Values |
|-------|--------|
| evidence_level | Level I, Level II, Level III |
| grade | Grade A, Grade B, Grade C, Key Recommendation |
| target_population | General, Diabetes, Cardiac Disease, Elderly |
| category | Diagnosis, Treatment, Referral, Monitoring |
| is_recommendation | true/false |
| is_table | true/false |
| is_algorithm | true/false |

## Technical Stack

### Core Technologies
- **Python 3.11+**: Primary language
- **Pydantic AI**: Agent framework
- **FastAPI**: API framework
- **PostgreSQL + pgvector**: Vector database (Neon)
- **Neo4j + Graphiti**: Knowledge graph (Neo4j Aura)
- **Gemini**: LLM (via OpenRouter) and Embeddings

### Key Libraries
- **PyMuPDF (fitz)**: PDF parsing
- **pymupdf4llm**: PDF to markdown conversion
- **asyncpg**: PostgreSQL async driver
- **httpx**: Async HTTP client

## Agent Tools (12 Total)

### Search Tools
1. `vector_search` - Semantic similarity search
2. `graph_search` - Knowledge graph facts
3. `hybrid_search` - Vector + keyword combined

### CPG-Specific Tools
4. `cpg_filtered_search` - Filter by grade/population/category
5. `get_grade_a_recommendations` - Highest evidence only
6. `get_drug_information` - Contraindications, dosages, side effects
7. `get_treatment_recommendations` - Treatments by condition
8. `get_chunk_with_parent_context` - Hierarchical context

### Entity Tools
9. `get_entity_relationships` - Entity connections in graph
10. `get_entity_timeline` - Temporal facts

### Document Tools
11. `get_document` - Full document retrieval
12. `list_documents` - Available documents

## Implementation Phases

### Phase 1: Foundation ✅
- PostgreSQL with pgvector on Neon
- Neo4j on Neo4j Aura
- Base Pydantic AI agent

### Phase 2: CPG Enhancement ✅
- Hierarchical PDF parsing (cpg_parser.py)
- Medical entity extraction
- CPG metadata columns
- 12 agent tools

### Phase 3: Knowledge Graph ✅
- Medical relationship extraction
- Graphiti integration
- Entity-relationship queries

### Phase 4: Clinical Decision Support ✅
- Evidence-based system prompt
- Grade/population filtering
- Drug information tools

### Phase 5: Testing & Optimization
- Full CPG ingestion
- Response validation
- Performance tuning

## Configuration

### Environment Variables
```bash
# PostgreSQL (Neon)
DATABASE_URL=postgresql://user:pass@host/dbname?sslmode=require

# Neo4j Aura
NEO4J_URI=neo4j+s://xxxxx.databases.neo4j.io
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password

# LLM (OpenRouter)
OPENROUTER_API_KEY=sk-or-v1-xxxxx
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL=google/gemini-2.0-flash-001

# Embeddings (Gemini)
GEMINI_API_KEY=AIzaxxxxx
EMBEDDING_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
EMBEDDING_MODEL=text-embedding-004
VECTOR_DIMENSION=768
CHUNK_SIZE=1200
```

## Example Clinical Queries

### Treatment Recommendations
- "What is the first-line treatment for erectile dysfunction?"
- "Give me Grade A recommendations for PDE5 inhibitors"
- "How should ED be treated in diabetic patients?"

### Drug Information
- "What are the contraindications for Sildenafil?"
- "What is the recommended dosage for Tadalafil?"
- "What side effects should I monitor for with PDE5 inhibitors?"

### Diagnosis
- "How is erectile dysfunction diagnosed?"
- "What diagnostic tools are used for ED assessment?"
- "What does IIEF-5 measure?"

## Disclaimer

This system provides clinical decision support based on Malaysia's CPG for ED Management. It is intended as a reference tool and should not replace professional medical judgment. Always consult qualified healthcare providers for patient care decisions.
