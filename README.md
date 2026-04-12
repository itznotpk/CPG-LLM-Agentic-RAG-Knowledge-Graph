# Malaysia CPG Agentic RAG with Knowledge Graph

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Pydantic AI](https://img.shields.io/badge/Pydantic_AI-Agent_Framework-E92063?style=for-the-badge&logo=pydantic&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-pgvector-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)
![Neo4j](https://img.shields.io/badge/Neo4j-Knowledge_Graph-4581C3?style=for-the-badge&logo=neo4j&logoColor=white)
![Gemini](https://img.shields.io/badge/Google_Gemini-LLM_&_Embeddings-4285F4?style=for-the-badge&logo=google&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-API-009688?style=for-the-badge&logo=fastapi&logoColor=white)

An intelligent **Clinical Practice Guidelines (CPG) Assistant** that combines **Agentic RAG** (Retrieval-Augmented Generation) with a **Knowledge Graph** to provide evidence-based clinical decision support across **multiple Malaysia CPGs**.

---

## 📑 Content Overview

| Section | Description |
|---------|-------------|
| [What This System Does](#-what-this-system-does) | Core capabilities overview |
| [Supported CPGs](#-supported-cpgs) | All clinical guidelines currently ingested |
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
│  USER: "What is the LDL-C target for a very high-risk patient  │
│         with acute coronary syndrome?"                          │
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
│  RESPONSE: "For very high-risk patients (e.g. ACS), the        │
│  LDL-C target is <1.4 mmol/L, with ≥50% reduction from        │
│  baseline. [Grade A, Level I]"                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Core Capabilities

- **Ingests CPG markdown documents** with hierarchical structure parsing
- **Dynamic LLM entity extraction** with 10 medical entity categories
- **Builds a knowledge graph** in Neo4j with entity summaries
- **Enables semantic search** via Vector DB (PostgreSQL + pgvector)
- **Provides clinical decision support** via conversational AI agent
- **Web Frontend** for clinical case analysis
- **Multi-CPG support** — handles multiple clinical guidelines simultaneously

---

## 📚 Supported CPGs

The system currently supports **6 Malaysia Clinical Practice Guidelines**, each with high-fidelity, RAG-optimized markdown sections:

| # | CPG Title | Edition | Sections | Status |
|---|-----------|---------|----------|--------|
| 1 | **Management of Dyslipidaemia** | 6th Edition | 17 sections (incl. appendices & references) | ✅ Complete |
| 2 | **Management of Erectile Dysfunction** | — | 14 sections (incl. appendix) | ✅ Complete |
| 3 | **Management of Breast Cancer** | 3rd Edition | 16 sections (incl. appendices) | ✅ Complete |
| 4 | **Management of Cancer Pain** | 2nd Edition | 15 sections | ✅ Complete |
| 5 | **Management of Hypertension** | 5th Edition | 16 sections (incl. appendix & references) | ✅ Complete |
| 6 | **Stable Coronary Artery Disease** | 2nd Edition | 16 sections (incl. appendix & references) | ✅ Complete |

### Dyslipidaemia (6th Edition) — Section Breakdown

| File | Topic |
|------|-------|
| `section-1-introduction.md` | Introduction & Epidemiology |
| `section-2-measurement.md` | Lipid Measurement |
| `section-3-classification.md` | Classification of Dyslipidaemia |
| `section-4-cv-risk-factor.md` | Cardiovascular Risk Factors |
| `section-5-risk-assessment.md` | CV Risk Assessment & Stratification |
| `section-6-target-lipid-levels.md` | Target Lipid Levels |
| `section-7-1-tlc.md` | Therapeutic Lifestyle Changes |
| `section-7-2-drugs.md` | Pharmacological Treatment |
| `section-8-primary-prevention.md` | Primary Prevention |
| `section-9-secondary-prevention.md` | Secondary Prevention |
| `section-10-specific-conditions.md` | Specific Clinical Conditions |
| `section-11-specific-disorders.md` | Specific Lipid Disorders |
| `section-12-special-groups.md` | Special Groups |
| `section-13-adherence.md` | Adherence & Compliance |
| `section-14-quality-indicators.md` | Quality Performance Indicators |
| `section-15-faqs.md` | Frequently Asked Questions |
| `appendices.md` | Appendices & Supplementary Data |

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
│  │  • System Prompt: Multi-CPG Clinical Assistant                 │  │
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
│ • Document chunks│  │ • Entity nodes   │  │ • Drug summaries     │
│ • Embeddings     │  │ • RELATES_TO     │  │ • Condition details  │
│ • CPG metadata   │  │ • MENTIONS       │  │ • Treatment pathways │
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
        → Gets summaries like "Atorvastatin (10–80 mg daily...)"

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

### `get_algorithm_pathway` Tool

Navigate CPG algorithms step-by-step and find next treatment steps:

```
get_algorithm_pathway(
    current_step="Statin intolerance",      # Current clinical situation
    condition="Dyslipidaemia"               # Medical context
)

Returns:
  - next_steps: What to do next in the pathway
  - pathway_facts: Related graph facts
  - alternatives: Options when treatment fails
```

**Use When:**
- Following CPG algorithms
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
| `MEDICATIONS` | Atorvastatin, Rosuvastatin, Ezetimibe, PCSK9 inhibitors |
| `CONDITIONS` | Dyslipidaemia, ACS, Familial Hypercholesterolaemia, CKD |
| `PROCEDURES` | Coronary angiography, CABG, PCI, Lifestyle modification |
| `DIAGNOSTIC_TOOLS` | Lipid profile, IIEF-5, HbA1c, FRS, SCORE2 |
| `RISK_FACTORS` | Smoking, Obesity, Diabetes, Hypertension |
| `ADVERSE_EVENTS` | Myopathy, Rhabdomyolysis, Hepatotoxicity, Flushing |
| `ORGANIZATIONS` | MOH Malaysia, WHO, EAU, ACC/AHA, ESC/EAS |
| `CONTRAINDICATIONS` | Active liver disease, Pregnancy, Nitrates with PDE5i |
| `DOSAGES` | 10 mg initial, 80 mg max, once daily, 24-hour washout |
| `RISK_CATEGORIES` | Low Risk, Moderate Risk, High Risk, Very High Risk |

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

### Dyslipidaemia
```
What is the LDL-C target for very high-risk patients?
What are the side effects of statins?
When should PCSK9 inhibitors be considered?
How do you manage statin intolerance?
```

### Erectile Dysfunction
```
What is the recommended initial dose for Sildenafil?
What are the contraindications for PDE5 inhibitors?
How long does Tadalafil's effect last?
```

### Hypertension
```
What is the first-line treatment for hypertension in diabetic patients?
When should resistant hypertension be suspected?
What are the BP targets for elderly patients?
```

### Breast Cancer
```
What are the screening recommendations for breast cancer?
When is neoadjuvant chemotherapy indicated?
What are the risk factors for familial breast cancer?
```

### Cancer Pain
```
What is the WHO analgesic ladder approach?
How should opioid rotation be performed?
What are the non-pharmacological options for cancer pain?
```

### Stable Coronary Artery Disease
```
What are the diagnostic criteria for stable angina?
When is coronary angiography indicated?
What is the optimal medical therapy for SCAD?
```

---

## 📁 Project Structure

```
CPG-LLM-Agentic-RAG-Knowledge-Graph/
├── agent/
│   ├── __init__.py
│   ├── agent.py          # Pydantic AI agent with tools
│   ├── tools.py          # Tool implementations (dynamic)
│   ├── prompts.py        # System prompt for CPG assistant
│   ├── providers.py      # LLM/embedding provider config
│   ├── models.py         # Pydantic data models
│   ├── api.py            # FastAPI backend server
│   ├── db_utils.py       # PostgreSQL utilities
│   └── graph_utils.py    # Neo4j/Graphiti utilities + entity queries
├── ingestion/
│   ├── __init__.py
│   ├── ingest.py         # Main ingestion pipeline
│   ├── cpg_parser.py     # Hierarchical CPG PDF parser
│   ├── graph_builder.py  # Entity extraction (10 categories)
│   ├── chunker.py        # Semantic chunking
│   └── embedder.py       # Embedding generation
├── frontend/
│   ├── run.py            # FastAPI frontend server
│   ├── base.html         # Base template
│   ├── index.html        # Main page
│   └── results.html      # Results display
├── markdown/                              # CPG markdown files (RAG-optimized)
│   ├── Dyslipidaemia(6th-Edition)/        # 17 section files
│   ├── Erectile-Dysfunction/              # 14 section files
│   ├── Breast-Cancer(3rd Edition)/        # 16 section files
│   ├── Cancer-Pain(2nd Edition)/          # 15 section files
│   ├── Hypertension(5th Edition)/         # 16 section files
│   └── Stable-Coronary-Artery-Disease(2nd Edition)/  # 16 section files
├── ddx/                  # ICD-11 Differential Diagnosis Engine
│   ├── data/             # ICD-11 code markdown files
│   ├── ingest_icd11.py   # ICD-11 ingestion script
│   ├── search_ddx.py     # DDx search with semantic matching
│   ├── migrate_inclusion_embeddings.py
│   └── README.md         # DDx module documentation
├── sql/
│   └── schema.sql        # Database schema
├── tests/                # Test suite
│   └── test_framework/
├── cli.py                # Command-line interface
├── requirements.txt      # Python dependencies
├── .env.example          # Environment variable template
├── PLANNING.md           # Architecture & design document
├── TASK.md               # Development task tracker
└── CLAUDE.md             # AI assistant context
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
| 🔴 High | Ingest all 6 CPGs into vector DB and knowledge graph |
| 🔴 High | Test cross-CPG clinical queries |
| 🟡 Medium | Implement chunk verifier agent (Phase 10) |
| 🟡 Medium | Implement local LLM via Ollama (Phase 9) |
| 🟡 Medium | Add reflection agent for improved responses |
| 🟢 Future | Mobile-friendly frontend |
| 🟢 Future | Add more Malaysia CPGs |

---

## ⚠️ Disclaimer

This system provides clinical decision support based on Malaysia's Clinical Practice Guidelines. It is intended as a reference tool and should not replace professional medical judgment. Always consult qualified healthcare providers for patient care decisions.

---

## 🙏 Acknowledgments

- Malaysia Ministry of Health for CPG development
- Graphiti by Zep for temporal knowledge graphs
- Pydantic AI for the agent framework
