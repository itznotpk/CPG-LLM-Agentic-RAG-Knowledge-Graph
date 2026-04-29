# Malaysia CPG Agentic RAG with Knowledge Graph

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Pydantic AI](https://img.shields.io/badge/Pydantic_AI-Agent_Framework-E92063?style=for-the-badge&logo=pydantic&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-pgvector-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)
![Neo4j](https://img.shields.io/badge/Neo4j-Knowledge_Graph-4581C3?style=for-the-badge&logo=neo4j&logoColor=white)
![Gemini](https://img.shields.io/badge/Google_Gemini-LLM_&_Embeddings-4285F4?style=for-the-badge&logo=google&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-API-009688?style=for-the-badge&logo=fastapi&logoColor=white)

An intelligent **Clinical Practice Guidelines (CPG) Assistant** that combines **Agentic RAG** (Retrieval-Augmented Generation) with a **Knowledge Graph** to provide evidence-based clinical decision support for Malaysia CPGs, including **Erectile Dysfunction**, **Heart Failure (5th Edition)**, **Dyslipidaemia (6th Edition)**, **Ischaemic Stroke (3rd Edition)**, **STEMI (4th Edition)**, and **NSTE-ACS (3rd Edition)**.

> **Last Updated:** April 2026

---

## 📑 Content Overview

| Section | Description |
|---------|-------------|
| [What This System Does](#-what-this-system-does) | Core capabilities overview |
| [Architecture](#-architecture) | System design and flow |
| [Tech Stack](#-tech-stack) | Technologies and frameworks |
| [Features](#-features) | Document ingestion, knowledge graph, agent tools |
| [Quick Start](#-quick-start) | Installation and setup guide |
| [Running the System](#-running-the-system) | API, CLI, and Frontend |
| [Example Queries](#-example-queries) | Sample clinical queries |
| [Project Structure](#-project-structure) | Folder and file organization |
| [Configuration](#-configuration) | Environment variables |
| [Next Steps](#-next-steps) | Development roadmap |

---

## 🏥 What This System Does

```
┌─────────────────────────────────────────────────────────────────┐
│  USER: "What is the recommended initial dose for Sildenafil     │
│         and how long does its effect persist?"                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    AGENTIC RAG SYSTEM                           │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │ Agent decides│→ │ Queries Neo4j│→ │ Queries      │           │
│  │ which tools  │  │ entity nodes │  │ Vector DB    │           │
│  └──────────────┘  └──────────────┘  └──────────────┘           │
│                              │                                  │
│                              ▼                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ Synthesizes answer from all sources                      │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  RESPONSE: "The recommended initial dose for Sildenafil is      │
│  50 mg, up to 100 mg. Sildenafil's effects can last up to       │
│  12 hours."                                                     │
└─────────────────────────────────────────────────────────────────┘
```

### Core Capabilities

- **Ingests CPG markdown documents** with hierarchical structure parsing
- **Dynamic LLM entity extraction** with 10 medical entity categories
- **Builds a knowledge graph** in Neo4j with entity summaries
- **Enables semantic search** via Vector DB (PostgreSQL + pgvector)
- **Provides clinical decision support** via conversational AI agent
- **Web Frontend** for clinical case analysis
- **RAG-optimized markdown** with localized glossaries, contextual anchors, and evidence keys per section

---

## 🏗 Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                           USER INTERFACES                            │
├────────────────┬────────────────┬────────────────────────────────────┤
│   Web Frontend │    CLI (cli.py)│        Direct API                  │
│   (port 8080)  │                │      (port 8058)                   │
└────────────────┴────────────────┴────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────────┐
│                      FASTAPI BACKEND                                 │
│                      (agent/api.py)                                  │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │                    PYDANTIC AI AGENT                           │  │
│  │  • LLM: Gemini 2.0 Flash via OpenRouter                        │  │
│  │  • System Prompt: Clinical ED Assistant                        │  │
│  │  • Autonomous Tool Selection                                   │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                              │                                       │
│  ┌───────────────────────────┼───────────────────────────┐           │
│  ▼                           ▼                           ▼           │
│ ┌────────────┐   ┌────────────────────┐   ┌────────────────────┐     │
│ │vector_search│  │get_drug_information│   │   graph_search     │     │
│ │hybrid_search│  │get_algorithm_path  │   │entity_relationships│     │
│ └────────────┘   └────────────────────┘   └────────────────────┘     │
└──────────────────────────────────────────────────────────────────────┘
          │                    │                        │
          ▼                    ▼                        ▼
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────┐
│   PostgreSQL     │  │     Neo4j        │  │   Entity Summaries   │
│   + pgvector     │  │  Knowledge Graph │  │   (from graph nodes) │
│                  │  │                  │  │                      │
│ • Document chunks│  │ • Entity nodes   │  │ "Sildenafil (50 mg   │
│ • Embeddings     │  │ • RELATES_TO     │  │  initial dose, up to │
│ • CPG metadata   │  │ • MENTIONS       │  │  100 mg) is a PDE5i" │
└──────────────────┘  └──────────────────┘  └──────────────────────┘
```

---

## 🛠 Tech Stack

### Core Framework
| Component | Technology |
|-----------|------------|
| **Agent Framework** | Pydantic AI |
| **LLM Provider** | OpenRouter → Gemini 2.0 Flash |
| **Embeddings** | Google Gemini `text-embedding-004` (768d) |

### Data Layer
| Component | Technology |
|-----------|------------|
| **Vector Database** | PostgreSQL + pgvector (Neon) |
| **Knowledge Graph** | Neo4j Aura + Graphiti |

### Interfaces
| Component | Port |
|-----------|------|
| **Backend API** | `http://localhost:8058` |
| **Web Frontend** | `http://localhost:8080` |
| **CLI** | Terminal |

---

## 📋 Features

### Agent Tools (5 Specialized Retrieval Tools)

| Tool | Purpose | Data Source |
|------|---------|-------------|
| `vector_search` | Semantic similarity search (definitions, protocols) | PostgreSQL |
| `graph_search` | Knowledge graph relationships (classifications, pathways) | Neo4j |
| `hybrid_search` | Vector + keyword combined (specific drug+dose) | PostgreSQL |
| `get_drug_information` | Multi-step drug info with entity summaries | Neo4j + PostgreSQL |
| `get_algorithm_pathway` | Step-by-step algorithm navigation, next steps | Neo4j + PostgreSQL |

### Dynamic `get_drug_information` Tool

The drug information tool uses a **4-step dynamic retrieval**:

```
STEP 0: Query Neo4j entity nodes directly
        → Gets summaries like "Sildenafil (50 mg initial dose...)"

STEP 1: Graph search for related facts
        → Gets relationships and edges

STEP 2: Entity relationships
        → Gets connected entities

STEP 3: Dynamic vector search
        → Extracts keywords FROM entity summary
        → Builds targeted search query automatically
        → Falls back to comprehensive search if no summary

STEP 4: Fallback search (if prior steps return nothing)
```

### `get_algorithm_pathway` Tool (NEW)

Navigate CPG algorithms step-by-step and find next treatment steps:

```
get_algorithm_pathway(
    current_step="PDE5i failure",    # Current clinical situation
    condition="ED"                    # Medical context
)

Returns:
  - next_steps: What to do next in the pathway
  - pathway_facts: Related graph facts
  - alternatives: Options when treatment fails
```

**Use When:**
- Following CPG algorithms (Algorithm 1, Algorithm 2)
- Treatment has failed, need next steps
- Patient passed/failed a test

### Agent Output Format

The agent responds in a structured **6-section care plan** format:

| Section | Content | Primary Tool |
|---------|---------|-------------|
| **1) Summary** | Diagnosis classification, risk factors | `graph_search` |
| **2) Medication Changes** | START/STOP/CHANGE with doses | `get_drug_information` + `hybrid_search` |
| **3) Patient Education** | Lifestyle, drug instructions, warnings | `vector_search` |
| **4) Monitoring & Next Steps** | Tests, side effects, red flags | `vector_search` + `get_algorithm_pathway` |
| **5) Referrals** | When/which specialist, urgency | `graph_search` + `vector_search` |
| **6) Follow-up** | Timeline, reassessment criteria | `vector_search` + `get_algorithm_pathway` |

### Entity Extraction (LLM-Based)

10 entity categories extracted during ingestion:

| Category | Examples |
|----------|----------|
| `MEDICATIONS` | Sildenafil, Tadalafil, PDE5 inhibitors |
| `CONDITIONS` | Erectile Dysfunction, Diabetes, Hypertension |
| `PROCEDURES` | Penile prosthesis, Stress test, Lifestyle modification |
| `DIAGNOSTIC_TOOLS` | IIEF-5, HbA1c, PSA, Bruce Protocol |
| `RISK_FACTORS` | Smoking, Obesity, Advanced age |
| `ADVERSE_EVENTS` | Headache, Flushing, Priapism, Hypotension |
| `ORGANIZATIONS` | MOH, WHO, EAU, ACC/AHA |
| `CONTRAINDICATIONS` | Nitrates contraindicated with PDE5i |
| `DOSAGES` | 50 mg initial, 24 hour washout, once daily |
| `RISK_CATEGORIES` | Low Risk, Intermediate Risk, High Risk |

### Web Frontend

Modern web UI for clinical case analysis:

- 🎨 Dark theme with Tailwind CSS
- 📝 Sample clinical cases
- ⏳ Animated progress indicators
- 📚 Collapsible sources section
- ⚠️ Clinical disclaimer

---

## 🚀 Quick Start

### 1. Prerequisites

- Python 3.11+
- PostgreSQL with pgvector (recommend [Neon](https://neon.tech))
- Neo4j database (recommend [Neo4j Aura](https://neo4j.com/cloud/aura/))
- API keys: OpenRouter, Google Gemini

### 2. Installation

```bash
# Clone repository
git clone https://github.com/itznotpk/CPG-LLM-Agentic-RAG-Knowledge-Graph.git
cd CPG-LLM-Agentic-RAG-Knowledge-Graph

# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt
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

# Ingestion LLM (can be same or different)
INGESTION_LLM=gpt-4.1-nano

# Embeddings (Gemini - Free!)
GEMINI_API_KEY=AIzaxxxxx
EMBEDDING_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
EMBEDDING_MODEL=text-embedding-004

# Settings
VECTOR_DIMENSION=768
CHUNK_SIZE=1200
```

### 4. Database Setup

Run the SQL in `sql/schema.sql` in your Neon database console.

### 5. Ingest Documents

```bash
# Ingest markdown files into vector DB and knowledge graph
python -m ingestion.ingest -d markdown -v

# Clean databases and re-ingest
python -m ingestion.ingest -d markdown -v --clean
```

---

## 🖥 Running the System

### Terminal 1: Backend API

```bash
python -m agent.api
# Runs on http://localhost:8058
```

### Terminal 2: CLI Agent

```bash
python cli.py
# Or specify port: python cli.py --port 8058
```

### Terminal 3: Web Frontend

```bash
cd frontend
python run.py
# Runs on http://localhost:8080
```

Open browser to `http://localhost:8080` for the web interface.

### ICD-11 DDx Engine (Prototype)

```bash
# Ingest ICD-11 codes
python ddx/ingest_icd11.py

# Migrate inclusion embeddings (one-time, for semantic matching)
python ddx/migrate_inclusion_embeddings.py

# Interactive differential diagnosis search
python ddx/search_ddx.py
```

The DDx Engine features:
- **Two-stage retrieval**: Vector search + Morbidity Tabulation Layer
- **Semantic inclusion matching**: Compares query to inclusion synonyms
- **Query normalization**: Handles typos, punctuation, casing

See [ddx/README.md](ddx/README.md) for details.

---

## 💬 Example Queries

### Drug Information
```
What is the recommended initial dose for Sildenafil?
What are the contraindications for PDE5 inhibitors?
How long does Tadalafil's effect last?
```

### Clinical Decision Support
```
45-year-old male with ED, hypertension, and diabetes. Currently on metformin and amlodipine.
Patient classified as 'Intermediate Risk' for cardiac issues - what is the next step?
```

### Diagnosis
```
How is erectile dysfunction diagnosed?
What does IIEF-5 measure?
What score ranges indicate severe ED?
```

---

## 📁 Project Structure

```
CPG-LLM-Agentic-RAG-Knowledge-Graph/
├── agent/
│   ├── agent.py          # Pydantic AI agent with tools
│   ├── tools.py          # Tool implementations (dynamic)
│   ├── prompts.py        # System prompt for CPG assistant
│   ├── providers.py      # LLM/embedding provider config
│   ├── api.py            # FastAPI backend server
│   ├── db_utils.py       # PostgreSQL utilities
│   └── graph_utils.py    # Neo4j/Graphiti utilities + entity queries
├── ingestion/
│   ├── ingest.py         # Main ingestion pipeline
│   ├── graph_builder.py  # Entity extraction (10 categories)
│   ├── chunker.py        # Semantic chunking
│   └── embedder.py       # Embedding generation
├── frontend/
│   └── run.py            # FastAPI frontend server
├── documents/            # Source PDF files (not tracked in git)
├── markdown/             # CPG markdown files (RAG-optimized)
│   ├── Erectile-Dysfunction/
│   ├── Heart-Failure(5th Edition)/
│   ├── Dyslipidaemia(6th-Edition)/
│   ├── Ischaemic-Stroke(3rd Edition)/  # 18 sections
│   ├── STEMI(4th Edition)/             # 20 sections
│   ├── NSTE-ACS(3rd Edition)/          # 12 sections
│   └── ...               # Additional CPGs (20+ guidelines)
├── ddx/                  # ICD-11 Differential Diagnosis Engine
│   ├── data/             # ICD-11 code markdown files
│   ├── ingest_icd11.py   # ICD-11 ingestion script
│   ├── search_ddx.py     # DDx search with semantic matching
│   ├── migrate_inclusion_embeddings.py  # Inclusion embeddings migration
│   └── README.md         # DDx module documentation
├── sql/
│   └── schema.sql        # Database schema
├── convert_pdf.py        # PDF to Markdown converter (Docling)
├── cli.py                # Command-line interface
├── CPG-RAG-Standardization-Guide.md  # Formatting standards for CPG ingestion
└── .env                  # Configuration (not in repo)
```

---

## ⚙️ Configuration

### Graph Builder Limits

| Setting | Value | Purpose |
|---------|-------|---------|
| `max_chars` for LLM extraction | 8000 | Captures more tables |
| Chunk warning threshold | 10000 | Logs oversized chunks |
| Entity categories | 10 | Comprehensive extraction |

### Tool Settings

| Setting | Value |
|---------|-------|
| Vector search results | 10 |
| Content per result | 2000 chars |
| Dynamic keyword extraction | From entity summaries |

---

## 📄 Ingested CPGs

| CPG Document | Edition | Sections | Status |
|---|---|---|---|
| Erectile Dysfunction | - | 12 | ✅ Complete |
| Heart Failure | 5th Edition | 14 | ✅ Complete |
| Dyslipidaemia | 6th Edition | 14 | ✅ Complete |
| Ischaemic Stroke | 3rd Edition | 18 | ✅ Complete |
| STEMI | 4th Edition | 20 | ✅ Complete |
| **NSTE-ACS** | **3rd Edition** | **12** | **✅ Complete** |
| Hypertension | 5th Edition | - | 📋 Ingested (raw) |
| Stable Coronary Artery Disease | 2nd Edition | - | 📋 Ingested (raw) |
| Atrial Fibrillation | 2012 | 12 | ✅ Complete |
| NSTEMI | 2011 | - | 📋 Ingested (raw) |
| Cancer Pain | 2nd Edition | - | 📋 Ingested (raw) |
| Breast Cancer | 3rd Edition | - | 📋 Ingested (raw) |
| Heart Disease in Pregnancy | 2nd Edition | - | 📋 Ingested (raw) |
| CVD Prevention in Women | 2016 | 9 | ✅ Complete |
| Primary & Secondary Prevention of CVD | 2017 | - | 📋 Ingested (raw) |
| Prevention, Diagnosis & Mgmt of IE | - | - | 📋 Ingested (raw) |
| Nasopharyngeal Carcinoma | - | - | 📋 Ingested (raw) |
| Anaesthesia Medication Safety | 2024 | - | 📋 Ingested (raw) |

### RAG-Optimized Document Structure

The fully standardized CPGs (STEMI, Ischaemic Stroke, NSTE-ACS, Dyslipidaemia, Heart Failure, ED) follow a consistent structure designed for optimal agentic retrieval:

- **RAG-Optimized Metadata** — Each section file includes an HTML-comment metadata block (`<!-- METADATA ... -->`) immediately after the first heading, categorising the content by domain (e.g., `diagnosis`, `reperfusion_therapy`, `secondary_prevention`), defining key `use_case`, `patient_input`, and `output` fields, and flagging `critical` sections for high-priority retrieval.
- **Localized Abbreviation Tables** — Each section file contains its own glossary of abbreviations used, eliminating cross-file lookups.
- **Contextual Anchors (Overlapping)** — Sections that reference other chapters embed summarized content from the referenced section as contextual anchors, enabling single-chunk retrieval.
- **Evidence Keys** — Each section contains its own Levels of Evidence Scale and Grades of Recommendations table for self-contained interpretation.
- **Standardized Recommendation Blocks** — Recommendations use consistent `[Level, Grade]` formatting.
- **Pure Markdown** — No HTML tags except for necessary entities (`<br>`, `&ge;`, `&le;`) for table cell formatting.

### Recent Changes (April 2026)

- **Layer 1 Metadata Standardization** — Applied the authorized Layer 1 metadata block to all sections across **Dyslipidaemia (6th Edition)**, **CVD Prevention in Women (2016)**, and **Atrial Fibrillation (2012)**. Each block includes standardized `category`, `use_case`, `patient_input`, `output`, `critical`, and `treatment_type` fields compliant with `METADATA_README.md`, aligning metadata keywords with each guideline's specific clinical context.
- **NSTE-ACS (3rd Ed) — RAG-Optimized Ingestion Complete** — 12 section files covering introduction, definitions, pathogenesis, diagnosis, risk scores, pre-hospital management, in-hospital management, special groups, post-discharge, cardiac rehabilitation, quality assurance, and appendices.
- **RAG-Optimized Metadata Standardization** — Added structured `<!-- METADATA -->` blocks to all sections across **Ischaemic Stroke (18 sections)**, **STEMI (20 sections)**, and **Erectile Dysfunction (12 sections)**. Each block includes `category`, `use_case`, `patient_input`, `output`, `critical`, and `treatment_type` fields to enable downstream RAG systems to classify and prioritise chunk retrieval.
- **STEMI (4th Ed) — Full RAG-Optimized Ingestion Complete** — All 20 section files (Sections 0–19) are now fully self-contained, atomic knowledge chunks:
  - **Cross-reference elimination** — Every "See Section X" pointer has been replaced with the literal, evidence-graded content from the source section.
  - **Abbreviation table harmonisation** — Each section's abbreviation table has been expanded to include all terms introduced by embedded overlapping content, ensuring zero undefined acronyms per chunk.
  - **Table 1: Levels of Evidence & Grades of Recommendation** — Embedded at the end of every clinical section (Sections 4–17), enabling self-contained interpretation of `[Grade X, Level Y]` annotations.
  - **PDF-verified tables** — Tables 6, 7, 8, 14, 15, 19 repositioned and corrected against source PDF.
  - **Sections 20–21 consolidated** — References and Acknowledgements merged into Section 19 (Appendices).
- **Repository cleanup** — Removed unnecessary files (temp outputs, one-off Python scripts, backup files, AI scaffolding docs). Moved source PDFs from `markdown/` to `documents/`. Fixed corrupted `.gitignore`.

---

## 🚧 Next Steps

| Priority | Task |
|----------|------|
| 🔴 High | RAG-optimize remaining raw CPGs (Hypertension, SCAD, etc.) |
| 🔴 High | Test with more clinical queries across all CPGs |
| 🟡 Medium | Implement local LLM via Ollama |
| 🟡 Medium | Add reflection agent for improved responses |
| 🟢 Future | Mobile-friendly frontend |

---

## ⚠️ Disclaimer

This system provides clinical decision support based on Malaysia's Clinical Practice Guidelines (CPGs). It is intended as a reference tool and should not replace professional medical judgment. Always consult qualified healthcare providers for patient care decisions.

---

## 🙏 Acknowledgments

- Malaysia Ministry of Health for CPG development
- Graphiti by Zep for temporal knowledge graphs
- Pydantic AI for the agent framework
