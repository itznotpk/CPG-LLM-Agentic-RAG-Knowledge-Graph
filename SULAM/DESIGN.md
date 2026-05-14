# SULAM Design System

## Aesthetic
Editorial/clinical magazine style with refined typography hierarchy and clean minimal layout. Professional but approachable, emphasizing clarity over ornamentation.

## Typography

### Typefaces
- **Display:** Fraunces (serif) — for step titles and major headings. 700 weight. Conveys editorial authority and authenticity.
- **Body:** Geist Sans — default body text, UI labels, form inputs.
- **Mono:** Geist Mono — technical labels, captions, meta information (uppercase, letter-spaced).

### Hierarchy
| Element | Font | Size | Weight | Usage |
|---------|------|------|--------|-------|
| Page title | Fraunces | 30px | 700 | "Medical Detective" heading |
| Step title | Fraunces | 20px | 700 | "Reading the clues", "Choosing..." |
| Caption | Geist Mono | 13px | 500 | Uppercase meta (AI step, RAG step) |
| Body text | Geist Sans | 15px | 400 | Main content, descriptions |
| Secondary | Geist Sans | 14px | 400 | Detail lines in cards |
| Label | Geist Mono | 11px | 500 | Sidebar labels, mini chips |

### Spacing
- Line-height on display: 1.15–1.2
- Line-height on body: 1.5
- Step card padding: 20px vertical, 22px horizontal (increased from 16/18 to accommodate larger titles)
- Gap between step number and content: 14px

## Color

### Palette
- **Primary:** `#2f5fd0` (clinical blue)
- **Primary soft:** `#dce6fb`
- **Primary ink:** `#1c3c8c`
- **Heath accent:** `#8b86a8` (muted lavender for secondary labels)
- **Text:** `#161a23` (ink), `#5b6273` (ink-soft)
- **Neutral:** `#f4f6fb` (bg), `#ffffff` (surface), `#e3e6ee` (line)

### Status Colors
- Complete: `#2a9d6c` (green)
- Error: `#c0433f` (red)
- Warning: `#b4843a` (amber)

## Components

### Step Cards
- 20px top/bottom padding, 22px left/right
- Rounded corners: 16px
- Title: Fraunces 20px, 700 weight
- Caption: Geist Mono 13px, uppercase, letter-spaced
- Status badge: Chip style, top-right aligned

### Typography Principles
1. **Step titles are prominent:** Use display font (Fraunces) at 20px to draw attention and convey editorial/clinical authority.
2. **Captions explain the technical step:** Mono font, uppercase, slightly larger than before (13px vs 11px) to improve scannability.
3. **No orphaned labels:** All text in a card should have clear visual hierarchy and breathing room.

## Architecture Diagram

### How It Works
**Layout:** Original compact SVG with 9 nodes + 5-stage pipeline in center. Clean, static diagram (no drag/pan/zoom).

**Components:**
1. **Patient Case** (User icon, blue) → input
2. **AI Orchestrator** (Brain icon, blue, highlighted) → center decision-maker
3. **Vector DB** (Database icon, lavender) → semantic search
4. **Knowledge Graph** (GitBranch icon, lavender) → entity relations
5. **Clinical Pipeline** (5 stages: DDx → CPG Routing → Evidence Retrieval → Plan Synthesis → Safety Review)
6. **Safety Critic** (Shield icon, red) → pharmacovigilance parallel agent
7. **Graph Navigator** (TrendingUp icon, red) → multi-morbidity reasoning parallel agent
8. **Cited Care Plan** (FileText icon, green) → final output

**Icons:** Lucide React (no emojis)
- User, Brain, Database, GitBranch, Shield, TrendingUp, FileText
- Color-coded by role and stroke width 1.5

**Connector flows:**
- Blue flows: primary orchestrator decisions
- Red flows: safety agent feedback
- Faint flows: return data to pipeline

**Styling:**
- Blue (`#2f5fd0`): Orchestrator, input
- Lavender (`#8b86a8`): Data sources
- Red (`#c0433f`): Safety agents
- Green (`#2a9d6c`): Output
- Glassmorphism nodes (rgba frosting, 12px radius)
- Dark gradient canvas (`#0f1520` → `#1b2436`)

**Animations:**
- Flowing dashed connectors (wave effect)
- Orchestrator highlight: glow ring (rotating dashes) + 4px blur
- Stage boxes: staggered fade-in (0.12s per stage)

## Last Updated
2026-05-15 — Upgraded typography (Fraunces 20px titles), reverted architecture to original size, added Safety Critic & Graph Navigator agents with icon-based design
