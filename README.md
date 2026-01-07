# Malaysia CPG Agentic RAG with Knowledge Graph

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Pydantic AI](https://img.shields.io/badge/Pydantic_AI-Agent_Framework-E92063?style=for-the-badge&logo=pydantic&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-pgvector-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)
![Neo4j](https://img.shields.io/badge/Neo4j-Knowledge_Graph-4581C3?style=for-the-badge&logo=neo4j&logoColor=white)
![Gemini](https://img.shields.io/badge/Google_Gemini-LLM_&_Embeddings-4285F4?style=for-the-badge&logo=google&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-API-009688?style=for-the-badge&logo=fastapi&logoColor=white)

An intelligent **Clinical Practice Guidelines (CPG) Assistant** that combines **Agentic RAG** (Retrieval-Augmented Generation) with a **Knowledge Graph** to provide evidence-based clinical decision support for the Malaysia CPG on Erectile Dysfunction Management.

---

## 📑 Content Overview

| Section | Description |
|---------|-------------|
| [What This System Does](#-what-this-system-does) | Core capabilities overview |
| [Tech Stack](#-tech-stack) | Technologies and frameworks used |
| [Features](#-features) | Document ingestion, knowledge graph, agent tools |
| [Quick Start](#-quick-start) | Installation and setup guide |
| [Example Queries](#-example-queries) | Sample clinical queries |
| [Project Structure](#-project-structure) | Folder and file organization |
| [Architecture](#-architecture) | System design diagram |
| [Next Steps](#-next-steps) | Development roadmap |
| [Disclaimer](#️-disclaimer) | Clinical usage disclaimer |

---

## 🏥 What This System Does

- **Ingests CPG PDF documents** with hierarchical structure parsing (Section → Subsection → Recommendation)
- **Extracts medical entities**: Conditions, Medications, Procedures, Diagnostic Tools, Risk Factors, Adverse Events
- **Builds a knowledge graph** with medical relationships (TREATS, CONTRAINDICATED_WITH, HAS_DOSAGE, etc.)
- **Enables evidence-filtered search**: Find Grade A recommendations, filter by patient population (Diabetes, Cardiac, Elderly)
- **Provides clinical decision support** via conversational AI agent

## 🛠 Tech Stack

### Core Framework
| Component | Technology | Badge |
|-----------|------------|-------|
| **Agent Framework** | Pydantic AI | ![Pydantic](https://img.shields.io/badge/Pydantic_AI-E92063?style=flat-square&logo=pydantic) |
| **LLM Provider** | OpenRouter → Gemini | ![OpenRouter](https://img.shields.io/badge/OpenRouter-000000?style=flat-square) |
| **LLM Model** | `google/gemini-2.0-flash-001` | ![Gemini](https://img.shields.io/badge/Gemini_2.0-4285F4?style=flat-square&logo=google) |

### Data Layer
| Component | Technology | Badge |
|-----------|------------|-------|
| **Vector Database** | PostgreSQL + pgvector (Neon) | ![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?style=flat-square&logo=postgresql&logoColor=white) |
| **Knowledge Graph** | Neo4j Aura + Graphiti | ![Neo4j](https://img.shields.io/badge/Neo4j-4581C3?style=flat-square&logo=neo4j&logoColor=white) |
| **Embeddings** | Gemini `text-embedding-004` (768d) | ![Embeddings](https://img.shields.io/badge/768_dim-Embeddings-green?style=flat-square) |

### Document Processing
| Component | Technology | Badge |
|-----------|------------|-------|
| **PDF Parsing** | PyMuPDF (fitz) | ![PyMuPDF](https://img.shields.io/badge/PyMuPDF-PDF_Parser-red?style=flat-square) |
| **PDF → Markdown** | pymupdf4llm | ![Markdown](https://img.shields.io/badge/Markdown-Converter-blue?style=flat-square) |
| **Chunking** | Semantic (1200 chars) | ![Chunks](https://img.shields.io/badge/1200_char-Chunks-orange?style=flat-square) |

### API & Interface
| Component | Technology | Badge |
|-----------|------------|-------|
| **API Framework** | FastAPI + SSE Streaming | ![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white) |
| **CLI** | Interactive Python CLI | ![CLI](https://img.shields.io/badge/CLI-Terminal-black?style=flat-square) |

## 📋 Features

### Document Ingestion
- **Hierarchical PDF parsing** - Detects sections by font size/boldness
- **Table extraction** - Converts tables to structured JSON
- **Algorithm/flowchart handling** - Vision LLM describes flowcharts as text
- **Metadata extraction** - Evidence levels (Grade A/B/C), target populations, categories
- **Processed file output** - Saves markdown and JSON to `documents/_processed/`

### Knowledge Graph Relationships
| Relationship | Example |
|--------------|---------|
| `TREATS` | (Sildenafil) → (Erectile Dysfunction) |
| `CONTRAINDICATED_WITH` | (Sildenafil) → (Nitrates) |
| `HAS_DOSAGE` | (Tadalafil) → ("10mg on-demand") |
| `REQUIRES_MONITORING` | (Testosterone) → (PSA) |
| `CAUSES` | (Sildenafil) → (Headache) |
| `ASSESSED_BY` | (Erectile Dysfunction) → (IIEF-5) |
| `RECOMMENDED_FOR` | (Li-ESWT) → ("Mild vasculogenic ED") |

### Agent Tools (12 Total)
| Tool | Purpose |
|------|---------|
| `vector_search` | Semantic similarity search |
| `graph_search` | Knowledge graph facts |
| `hybrid_search` | Vector + keyword combined |
| `cpg_filtered_search` | Filter by grade/population/category |
| `get_grade_a_recommendations` | Highest evidence only |
| `get_drug_information` | Contraindications, dosages, side effects |
| `get_treatment_recommendations` | Treatments by condition |
| `get_entity_relationships` | Entity connections in graph |
| `get_entity_timeline` | Temporal facts |
| `get_document` | Full document retrieval |
| `list_documents` | Available documents |
| `get_chunk_with_parent_context` | Hierarchical context |

## 🚀 Quick Start

### 1. Prerequisites

- Python 3.11+
- PostgreSQL with pgvector (recommend [Neon](https://neon.tech))
- Neo4j database (recommend [Neo4j Aura](https://neo4j.com/cloud/aura/))
- API keys for OpenRouter and Gemini

### 2. Installation

```bash
# Enter directory
cd agentic-rag-knowledge-graph

# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt
pip install pymupdf pymupdf4llm
```

### 3. Environment Setup

Create `.env` file:

```env
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

# Embeddings (Gemini - Free!)
GEMINI_API_KEY=AIzaxxxxx
EMBEDDING_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
EMBEDDING_MODEL=text-embedding-004

# Settings
VECTOR_DIMENSION=768
CHUNK_SIZE=1200
```

### 4. Database Setup

Run the SQL in `sql/schema.sql` in your Neon database console. This creates tables with CPG-specific columns:
- `evidence_level`, `grade`, `target_population`, `category`
- `section_hierarchy`, `is_recommendation`, `is_table`, `is_algorithm`
- `parent_chunk_id` for hierarchical relationships

### 5. Ingest CPG Documents

```bash
# Place your CPG PDF in documents/ folder
python -m ingestion.ingest --clean -v
```

**Output files saved to `documents/_processed/`:**
- `{name}.md` - Full markdown content
- `{name}_chunks.json` - Chunks with metadata  
- `{name}_structure.json` - Document structure summary

### 6. Run the CLI Agent

```bash
python cli.py
```

## 💬 Example Queries

### Treatment Recommendations
```
What is the first-line treatment for erectile dysfunction?
Give me Grade A recommendations for PDE5 inhibitors
How should ED be treated in diabetic patients?
```

### Drug Information
```
What are the contraindications for Sildenafil?
What is the recommended dosage for Tadalafil?
What side effects should I monitor for with PDE5 inhibitors?
```

### Diagnosis
```
How is erectile dysfunction diagnosed?
What diagnostic tools are used for ED assessment?
What does IIEF-5 measure?
```

### Knowledge Graph Queries
```
Search the knowledge graph for erectile dysfunction facts
What entities are related to Sildenafil?
Show me the relationships for cardiovascular disease
```

## 📁 Project Structure

```
agentic-rag-knowledge-graph/
├── agent/
│   ├── agent.py          # Pydantic AI agent with 12 tools
│   ├── tools.py          # Tool implementations
│   ├── prompts.py        # System prompt for CPG assistant
│   ├── providers.py      # LLM/embedding provider config
│   ├── db_utils.py       # PostgreSQL utilities
│   └── graph_utils.py    # Neo4j/Graphiti utilities
├── ingestion/
│   ├── ingest.py         # Main ingestion pipeline
│   ├── cpg_parser.py     # Hierarchical PDF parser
│   ├── graph_builder.py  # Entity & relationship extraction
│   ├── chunker.py        # Semantic chunking
│   └── embedder.py       # Embedding generation
├── sql/
│   └── schema.sql        # Database schema with CPG columns
├── documents/            # Place CPG PDFs here
│   └── _processed/       # Auto-generated markdown/JSON
├── cli.py                # Command-line interface
├── api.py                # FastAPI server
└── .env                  # Configuration
```

## 🔧 CLI Options

```bash
python -m ingestion.ingest [OPTIONS]

Options:
  --clean, -c        Clean databases before ingestion
  --chunk-size N     Chunk size (default: 1200)
  --no-cpg           Disable CPG-specific parsing
  --fast, -f         Skip knowledge graph building
  --verbose, -v      Enable debug logging
```

## 📊 CPG Metadata Schema

Each chunk is enriched with:

| Field | Example Values |
|-------|----------------|
| `evidence_level` | Level I, Level II, Level III |
| `grade` | Grade A, Grade B, Grade C, Key Recommendation |
| `target_population` | General, Diabetes, Cardiac Disease, Elderly, Spinal Cord Injury |
| `category` | Diagnosis, Treatment, Referral, Monitoring, Prevention |
| `section_hierarchy` | ["4. TREATMENT", "4.2 Pharmacological Treatment"] |
| `is_recommendation` | true/false |
| `is_table` | true/false |
| `is_algorithm` | true/false |

## 🏗 Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              USER QUERY                                      │
│                    "What are PDE5 inhibitor contraindications?"              │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PYDANTIC AI AGENT                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                        SYSTEM PROMPT                                 │    │
│  │  "You are a clinical decision support assistant for Malaysia CPG.   │    │
│  │   Use cpg_filtered_search for evidence-based queries..."            │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                    │                                         │
│                                    ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    LLM (Gemini via OpenRouter)                       │    │
│  │                                                                      │    │
│  │   REASONING: "User asks about contraindications for a drug.         │    │
│  │   I should use get_drug_information tool for Sildenafil/Tadalafil"  │    │
│  │                                                                      │    │
│  │   DECISION: Call get_drug_information("Sildenafil")                 │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                    │                                         │
│                                    ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                         TOOL REGISTRY                                │    │
│  │                    (12 Tools Available)                              │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
    ┌───────────────────┐ ┌─────────────────┐ ┌──────────────────┐
    │   VECTOR DB       │ │ KNOWLEDGE GRAPH │ │   STATIC RULES   │
    │   (PostgreSQL +   │ │    (Neo4j +     │ │  (Hardcoded in   │
    │    pgvector)      │ │    Graphiti)    │ │   graph_builder) │
    └───────────────────┘ └─────────────────┘ └──────────────────┘
            │                     │                    │
            ▼                     ▼                    ▼
    ┌───────────────────┐ ┌─────────────────┐ ┌──────────────────┐
    │ • Chunk embeddings│ │ • Entity nodes  │ │ • Contraindications│
    │ • Full text search│ │ • Relationships │ │ • Dosages         │
    │ • CPG metadata    │ │ • Temporal facts│ │ • Drug-condition  │
    │   (grade, pop.)   │ │                 │ │   mappings        │
    └───────────────────┘ └─────────────────┘ └──────────────────┘
                    │               │               │
                    └───────────────┼───────────────┘
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          TOOL RESULTS                                        │
│   {contraindications: ["Nitrates", "Riociguat"], dosages: ["50mg"], ...}    │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     LLM SYNTHESIZES RESPONSE                                 │
│  "Sildenafil is contraindicated with Nitrates (Grade A). The standard       │
│   dose is 50mg on-demand. Common side effects include headache..."          │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 🚧 Next Steps

| Priority | Task | Description |
|----------|------|-------------|
| 🔴 High | **Validate Embeddings** | Test with more documents containing tables, algorithms, and complex structures to verify vector DB and knowledge graph are structured correctly |
| 🔴 High | **Validate All Tools** | Comprehensive testing of all 12 agent tools with various query types |
| 🟡 Medium | **Implement Ollama** | Add local LLM support via Ollama for offline prototyping and development |
| 🟡 Medium | **Reflector Agent** | Integrate a reflection/self-critique agent for improved response quality |
| 🟢 Future | **UI Integration** | Replace CLI with web UI or other user interface (Streamlit, Gradio, or custom frontend) |

---

## ⚠️ Disclaimer

This system provides clinical decision support based on Malaysia's CPG for ED Management. It is intended as a reference tool and should not replace professional medical judgment. Always consult qualified healthcare providers for patient care decisions.

---

## 🙏 Acknowledgments

- Malaysia Ministry of Health for CPG development
- Original agentic-rag-knowledge-graph framework by Cole Medin
- Graphiti by Zep for temporal knowledge graphs
