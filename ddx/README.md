# ICD-11 DDx Prototype

🏥 **Differential Diagnosis Engine** using ICD-11 codes with vector search + Morbidity Tabulation Layer.

## Scope
- **Chapter 17**: Conditions related to sexual health
- **Section**: HA00-HA0Z Sexual Dysfunctions (47 codes)

## Files
| File | Purpose |
|------|---------|
| `data/ha00_sexual_dysfunctions.md` | ICD-11 codes source data |
| `ingest_icd11.py` | Parse markdown → generate embeddings → insert to Neon |
| `search_ddx.py` | Interactive CLI with Morbidity Tabulation Layer |
| `migrate_inclusion_embeddings.py` | Add semantic matching for inclusions |

## Architecture

```
Query → Normalize → Vector Search (10) → Tabulation Filter → Top 5
              ↓                               ↓
      Lowercase, strip          ✗ Exclusion match → REMOVE
      punctuation               ✓ Inclusion match (semantic) → BOOST
```

### Two-Stage Retrieval
1. **Vector Similarity Search**: Embedding comparison for semantic matching
2. **Morbidity Tabulation Layer**: ICD-11 coding rules enforcement
   - **Exclusions**: Substring match → Remove candidate
   - **Inclusions**: Semantic similarity > 70% → Boost ranking

## Quick Start

### 1. Ingest ICD-11 Codes
```bash
python ddx/ingest_icd11.py
```

### 2. Migrate Inclusion Embeddings (one-time)
```bash
python ddx/migrate_inclusion_embeddings.py
```

### 3. Run DDx Search (Interactive)
```bash
python ddx/search_ddx.py
```

### 4. Single Query
```bash
python ddx/search_ddx.py "difficulty maintaining erection"
```

---

## Test Cases

### TC-01: Semantic Search (Vector Similarity)
**Query:** `difficulty maintaining erection`  
**Expected:** HA01.1 (Male erectile dysfunction) ranks #1 via semantic matching

### TC-02: Inclusion Match (Semantic Similarity)
**Query:** `psychological inability to reach orgasm`  
**Expected:** HA02.0 with `[MATCH]` showing "Semantic match: Psychogenic anorgasmy (75.6%)"

### TC-03: Exclusion Filter
**Query:** `male early ejaculation`  
**Expected:** HA02 REMOVED from results (exclusion applies)

---

## Example Output

```
🩺 Patient condition: psychological inability to reach orgasm

🔍 Searching ICD-11 database...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  📋 QUERY: psychological inability to reach orgasm
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  ┌────────┬────────────┬──────────────────────────────────────────┐
  │ 🟠 #1  │ HA02.0     │ Anorgasmia                      [MATCH] │
  ├────────────────────────────────────────────────────────────────┤
  │Confidence:  69.1%                                              │
  │ ↳ Semantic match: "Psychogenic anorgasmy" (75.6%)              │
  │Anorgasmia is characterised by the absence or marked...         │
  └────────────────────────────────────────────────────────────────┘
```

---

## Features

### Query Preprocessing
- **Normalization**: Lowercase, strip punctuation, collapse whitespace
- **Validation**: Min 3 chars, max 500 chars, must contain letters

### Semantic Inclusion Matching
- Compares query embedding with pre-computed inclusion embeddings
- Threshold: 70% similarity for match
- Shows match percentage in results

---

## Database
- **Table**: `icd11_codes` in Neon (PostgreSQL + pgvector)
- **Columns**: code, title, description, inclusions, exclusions, inclusion_embeddings, embedding
- **Does NOT modify** any other tables
