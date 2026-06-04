# SULAM — Medical Detective Booth UI

An educational demo for secondary-school community-service booths showing how an agentic RAG clinical assistant processes a patient case in real time.

## Prerequisites

- The CPG-LLM backend must be running on **port 8058** before using Tab A.
- Node.js 18+

## Setup

```bash
cd SULAM
npm install
npm run dev
```

The app starts on **http://localhost:5174**. Tabs B and C (How It Works, Knowledge Graph) work with the backend offline.

## Tabs

| Tab | Requires backend? |
|-----|:-----------------:|
| A — Medical Detective | Yes (port 8058) |
| B — How It Works | No |
| C — Knowledge Graph | No |

## Environment

Copy `.env.example` to `.env` if you need to point at a different backend URL:

```
VITE_CLINICAL_API_URL=http://localhost:8058
```
