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

## Architecture

```
Query → Vector Search (10 candidates) → Morbidity Tabulation Layer → Top 5
                                              ↓
                                   ✗ Remove if exclusion matches (NO list)
                                   ✓ Boost if inclusion matches (YES list)
```

## Quick Start

### 1. Ingest ICD-11 Codes
```bash
python ddx/ingest_icd11.py
```

### 2. Run DDx Search (Interactive)
```bash
python ddx/search_ddx.py
```

### 3. Single Query
```bash
python ddx/search_ddx.py "difficulty maintaining erection"
```

---

## Test Cases

### TC-01: Inclusion Match (Synonym Detection)
**Query:** `impotence`  
**Expected:** HA01.1 shows "✓ MATCH" with matched term "Impotence"

### TC-02: Direct Semantic Match
**Query:** `difficulty achieving erection`  
**Expected:** HA01.1 ranks high by similarity (no inclusion match)

### TC-03: Female-Specific Query
**Query:** `reduced vaginal lubrication during arousal`  
**Expected:** HA01.0 (Female sexual arousal dysfunction) ranks high

### TC-04: Inclusion Boost Demonstration
**Query:** `inability to orgasm due to medication side effects`  
**Expected:** HA02.0 boosted to #1 via inclusion match despite lower similarity

---

## Test Results: TC-04 (Inclusion Boost)

| Rank | Code | Similarity | Inclusion Match | Why Ranked Higher? |
|------|------|------------|-----------------|---------------------|
| #1 | HA02.0 | 60.9% | ✓ "Psychogenic anorgasmy" | Boosted by inclusion match |
| #2 | HA02 | 69.4% | No | Higher similarity but no match |
| #3 | HA02.Z | 68.9% | No | |
| #4 | HA02.Y | 67.0% | No | |
| #5 | HA01.Z | 62.4% | No | |

**Key Observation:** HA02.0 ranked #1 despite having **lower similarity** (60.9%) than HA02 (69.4%) because it matched the inclusion term "Psychogenic anorgasmy". This demonstrates the boost logic is working correctly.

---

## Example Output

```
══════════════════════════════════════════════════════════════════════
  🏥  ICD-11 DIFFERENTIAL DIAGNOSIS ENGINE  🏥
     Chapter 17: Conditions Related to Sexual Health
══════════════════════════════════════════════════════════════════════

🩺 Patient condition: inability to orgasm due to medication side effects

  ┌──────────────────────────────────────────────────────────────────┐
  │  🟡 #1  [HA02.0      ]  Anorgasmia                      ✓ MATCH │
  │      Similarity: ███████░░░  60.9%                     │
  │      ↳ Matched: "Psychogenic anorgasmy"                │
  └──────────────────────────────────────────────────────────────────┘
```

---

## Database
- **Table**: `icd11_codes` in Neon (PostgreSQL + pgvector)
- **Embedding**: Title + Description + Inclusions → 768d vector
- **Stored but not embedded**: Exclusions, Parent, Chapter (for filtering)
- **Does NOT modify** any other tables
