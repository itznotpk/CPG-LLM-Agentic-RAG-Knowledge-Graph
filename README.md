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

# Interactive differential diagnosis search
python ddx/search_ddx.py
```

The DDx Engine uses vector search + Morbidity Tabulation Layer for ICD-11 code suggestions. See [ddx/README.md](ddx/README.md) for details.

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
├── markdown/             # CPG markdown files
│   ├── section-3-diagnosis.md
│   ├── section-4-treatment.md
│   ├── section-5-tcm.md
│   ├── section-6-followup.md
│   ├── section-7-referral.md
│   ├── section-8-special-populations.md
│   ├── section-9-implementation.md
│   └── appendix-6-treatment.md
├── ddx/                  # ICD-11 Differential Diagnosis Engine
│   ├── data/             # ICD-11 code markdown files
│   ├── ingest_icd11.py   # ICD-11 ingestion script
│   ├── search_ddx.py     # DDx search with Morbidity Tabulation Layer
│   └── README.md         # DDx module documentation
├── sql/
│   └── schema.sql        # Database schema
├── cli.py                # Command-line interface
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

## 🚧 Next Steps

| Priority | Task |
|----------|------|
| 🔴 High | Add more CPG sections for comprehensive coverage |
| 🔴 High | Test with more clinical queries |
| 🟡 Medium | Implement local LLM via Ollama |
| 🟡 Medium | Add reflection agent for improved responses |
| 🟢 Future | Mobile-friendly frontend |

---

## ⚠️ Disclaimer

This system provides clinical decision support based on Malaysia's CPG for ED Management. It is intended as a reference tool and should not replace professional medical judgment. Always consult qualified healthcare providers for patient care decisions.

---

## 🙏 Acknowledgments

- Malaysia Ministry of Health for CPG development
- Graphiti by Zep for temporal knowledge graphs
- Pydantic AI for the agent framework
