# MHNexus CPG LLM Web Application

A modern, AI-powered Clinical Practice Guideline (CPG) web application built with React, Vite, Tailwind CSS, and Supabase. This application assists healthcare providers in generating evidence-based care plans using AI recommendations, with a comprehensive dashboard and patient management system.

![MHNexus CPG LLM](https://img.shields.io/badge/MHNexus-CPG%20LLM-0b5e3c?style=for-the-badge)
![React](https://img.shields.io/badge/React-18.2-61DAFB?style=flat-square&logo=react)
![Vite](https://img.shields.io/badge/Vite-5.x-646CFF?style=flat-square&logo=vite)
![Tailwind CSS](https://img.shields.io/badge/Tailwind-3.x-38B2AC?style=flat-square&logo=tailwind-css)
![Supabase](https://img.shields.io/badge/Supabase-Backend-3ECF8E?style=flat-square&logo=supabase)


## 🌟 Features

**Latest Update (2026-01-18):**
- **Multiple Consultations per Patient**: Each patient can now have multiple consultation records
  - New `consultation_number` column for per-patient sequence (1, 2, 3... for each NRIC)
  - Global `id` for technical/internal use
  - New SQL migration: `supabase/consultations_migration_v2.sql`
- **New RPC Functions**:
  - `start_consultation(nric, notes)` - Creates new consultation row
  - `update_consultation(id, ...)` - Updates existing consultation by ID
  - `get_patient_consultations(nric, limit)` - Gets all consultations for a patient
  - `get_latest_consultation(nric)` - Gets most recent consultation
- **My Patients Enhancement**: Diagnoses section now shows ALL diagnoses from ALL consultations
- **TCA Date Fix**: Next Review Date from Step 3 now correctly synced to database

**Previous Update (2026-01-16):**
- **Complete Care Plan Sync**: All Step 3 Care Plan data syncs to database
- **Dynamic Follow-up Display**: Step 4 Plan Summary shows actual TCA date
- **Timezone Fix**: All timestamps display correctly in UTC+08:00

### 🏠 Sidebar Navigation & Dashboard

#### Home
- **Today's Schedule**: Collapsible visual timeline of patient appointments with filters & sorting
- **Quick Stats**: Consultations completed, pending reviews, patients seen
- **Patient Cards**: Color-coded by priority (emergency, follow-up, regular)
- **Patient Quick View**: Modal with patient summary and PDF/CSV export
- **Start Consult**: One-click access to begin patient consultation
- **Status Filters**: All, Waiting, In Progress, Done
- **Sort Options**: By time or urgency level
- **Toast Notifications**: Real-time feedback for user actions

#### My Patients
- **Patient Registry**: Searchable patient database with initial-based colored avatars
- **Status Filters**: Active, Follow-up, Discharged tabs for easy management
- **Inline Expansion**: Click any patient row to view full details directly below it
- **Diagnoses Sync**: Shows selected differential diagnoses from consultations (synced from database)
- **3-Column Detail Layout**: Vital Signs, Clinical Notes, and Medications displayed side-by-side
- **Scrollable Lists**: Long diagnoses/medications lists have max-height containers
- **Medical History**: Access detailed historical data (conditions, meds, labs, procedures) in a dedicated modal
- **Quick Actions**: View history, view vital charts, schedule appointment, and start consult
- **Risk Indicators**: Visual badges and single-line displays for patient risk levels

#### Settings
- **Profile Management**: Name, specialty, license, contact info
- **Notifications**: Email, push, SMS, emergency alert preferences
- **Appearance**: Light/Dark/System theme with 6 accent colors (Cyan, Blue, Purple, Emerald, Amber, Rose)
- **System Config**: Session timeout, auto-save, data sync settings

### 🔄 Core Workflow (4-Step Process)

#### 1. Data Input Section
- **NRIC Validation**: Secure and formatted NSN lookup (`xxxxxx-xx-xxxx`) with real-time validation feedback.
- **MPIS Auto-Fill**: If the NSN exists in MPIS, patient info is automatically retrieved and vital signs history is synced.
- **Manual Entry if No MPIS**: Graceful fallback to manual data entry for new patients.
- **Consultation Chart View**: Non-disruptive modal to view vital sign trends during patient assessment.
- **Vitals Grid**: Structured input for BP, HR, Temp, SpO2, RR, and auto-calculated BMI.
- **Clinical Notes**: Speech-to-text dictation support with a "Confirm" step for review before AI analysis.
- **Medical Alerts**: Structured input for allergies and current medications.

#### 2. AI Diagnosis Section
- **AI-Generated Differential Diagnoses**: Ranked by probability
- **Multiple Selection**: Click to select one or more diagnoses for care plan generation
- **ICD-11 Codes**: Automatically assigned to each diagnosis
- **Risk Assessment Badges**: High/Medium/Low risk indicators
- **Database Storage**: Selected diagnoses saved to consultations table and accumulated over time

#### 3. Care Plan Section
- **Clinical Summary**: AI-generated patient overview
- **Drug Safety Alerts**: Drug interactions, allergy alerts, contraindications
- **Medication Recommendations**: 
  - 🔴 STOP medications (with reasons & CPG references)
  - 🟢 START medications (with dosing & CPG references)
  - 🟡 CHANGE medications (before → after dosing with KIV notes)
  - 🔵 CONTINUE medications (with CPG references)
- **Interventions & Procedures**: With CPT codes and urgency levels
- **Monitoring & Testing**: Schedules with frequency (e.g., "Now, then q3 months")
- **Referrals**: Specialist referrals with priority badges
- **Lifestyle & Self-Management Goals**: Diet, exercise, weight management
- **Follow-up**: Scheduling recommendations
- **CPG References**: Evidence-based guideline citations

#### 4. Output Section
- **Complete Care Plan Summary**: Finalized recommendations
- **PDF Export**: Generate downloadable care plan documents
- **Print Support**: Browser print functionality

### 🆕 Advanced Features

#### Clinical Decision Support (CDS)
- **Drug Interaction Checker**: Alerts for dangerous combinations
- **Allergy Alerts**: Cross-references patient allergies with prescribed medications
- **Contraindication Warnings**: Condition-based medication alerts
- **Dosage Calculator**: eGFR-based renal dosing adjustments

#### Enhanced AI Interaction
- **Regenerate Care Plan**: Request alternative recommendations
- **Feedback Options**: More Conservative, More Aggressive, Different Approach, etc.
- **Custom Feedback Input**: Free-text feedback for RAG improvement

#### Voice & Dictation
- **Speech-to-Text**: Voice input for clinical notes (Web Speech API)
- **Read Aloud**: Text-to-speech for care plan summaries
- **Real-time Transcription Preview**


#### Approval Workflow (Updated)
- **Simple Approve/Reject**: Approve or reject care plan with feedback
- **Regenerate on Reject**: Add feedback and regenerate care plan in-place
- **Approval Required**: Must approve before generating report
- **History Tracking**: Audit trail with timestamps

#### Analytics Dashboard
- **Usage Metrics**: Total sessions, weekly trends
- **Time Saved**: Efficiency calculations
- **Acceptance Rate**: Care plan recommendation adoption
- **Top Diagnoses**: Frequency breakdown
- **Recent Activity Feed**: Real-time usage log
- **AI Performance Metrics**: Confidence scores, active users

## 🎨 Design System

### Theme System
- **Light/Dark/System Modes**: Light theme as default, automatic detection or manual selection
- **6 Accent Colors**: Cyan (default), Blue, Purple, Emerald, Amber, Rose
- **CSS Custom Properties**: Dynamic theming via `--accent-primary`, `--accent-primary-hover`, `--accent-secondary`
- **Full Accent Color Integration**: All UI components dynamically respond to accent color selection
- **LocalStorage Persistence**: Theme and accent preferences saved across sessions

### Visual Design
- **Glassmorphism UI**: Modern translucent card design with blur effects and accent-colored borders
- **Color Palette**: 
  - Light Mode: White backgrounds with subtle shadows and accent highlights
  - Dark Mode: Slate-900 backgrounds with accent-colored borders and gradient accents
- **Typography**: Optimized contrast for both themes
- **Responsive**: Mobile-first design approach with collapsible sidebar
- **Dynamic Icons**: Section icons follow the selected accent color

### UI Components (All Accent-Aware)
- GlassCard, GlassPanel (glassmorphism containers with accent borders)
- Button (primary, secondary, success, danger, ghost, outline - all with accent colors)
- Badge (status, confidence, risk, code - with accent theming)
- Input, TextArea, Select (form controls with accent focus rings)
- ProgressBar, StepIndicator (accent-colored progress indicators)
- Skeleton loaders (loading states with accent highlights)

## 📁 Project Structure

```
src/
├── App.jsx                 # Main application with sidebar routing
├── main.jsx                # React entry point
├── index.css               # Tailwind CSS + theme variables
├── components/
│   ├── layout/
│   │   ├── Layout.jsx      # Header & Footer components
│   │   ├── Sidebar.jsx     # Collapsible navigation sidebar
│   │   └── index.js
│   ├── pages/
│   │   ├── Home.jsx        # Main dashboard with schedule, filters & quick view
│   │   ├── MyPatients.jsx  # Patient registry & search
│   │   └── Settings.jsx    # User preferences & config
│   ├── sections/
│   │   ├── DataInputSection.jsx
│   │   ├── DiagnosisSection.jsx
│   │   ├── CarePlanSection.jsx
│   │   ├── OutputSection.jsx
│   │   ├── DashboardSection.jsx
│   │   ├── ClinicalDecisionSupport.jsx
│   │   ├── PatientDemographics.jsx
│   │   ├── ClinicalNotes.jsx
│   │   ├── VitalsGrid.jsx
│   │   ├── MPISSync.jsx
│   │   └── index.js
│   └── shared/
│       ├── GlassCard.jsx
│       ├── Button.jsx
│       ├── Input.jsx
│       ├── Badge.jsx
│       ├── ProgressBar.jsx
│       ├── VoiceInput.jsx
│       ├── NotesComments.jsx
│       ├── ApprovalWorkflow.jsx
│       ├── RegenerateButton.jsx
│       ├── Notification.jsx    # Toast notification system
│       ├── PatientQuickView.jsx # Patient modal with export
│       └── index.js
├── context/
│   ├── AppContext.jsx      # Global state management
│   └── ThemeContext.jsx    # Theme & accent color management
├── data/
│   ├── sampleData.js       # Demo data for testing
│   ├── clinicalRulesData.js # CDS rules database
│   └── scheduleData.js     # Dashboard mock data
├── lib/
│   └── supabase.js         # Supabase client configuration
└── utils/
    └── pdfGenerator.js     # PDF export functionality

supabase/
└── schema.sql              # Complete database schema

docs/
└── SUPABASE_SETUP.md       # Backend setup guide
```

## 🚀 Getting Started

### Prerequisites
- Node.js 18.x or higher
- npm 9.x or higher

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd "MHNexus CPG LLM Web App"
```

2. Install dependencies:
```bash
npm install
```

3. Start the development server:
```bash
npm run dev
```

4. Open your browser at `http://localhost:5173`

### Build for Production

```bash
npm run build
```

The built files will be in the `dist/` directory.

### Preview Production Build

```bash
npm run preview
```

## 📦 Dependencies

### Production Dependencies
| Package | Version | Purpose |
|---------|---------|---------|
| react | ^18.2.0 | UI framework |
| react-dom | ^18.2.0 | React DOM rendering |
| lucide-react | ^0.294.0 | Icon library |
| jspdf | ^2.5.2 | PDF generation |
| jspdf-autotable | ^3.8.4 | PDF table formatting || @supabase/supabase-js | ^2.89.0 | Backend integration |
### Development Dependencies
| Package | Version | Purpose |
|---------|---------|---------|
| vite | ^5.0.8 | Build tool & dev server |
| @vitejs/plugin-react | ^4.2.1 | React plugin for Vite |
| tailwindcss | ^3.3.6 | CSS framework |
| postcss | ^8.4.32 | CSS processing |
| autoprefixer | ^10.4.16 | CSS vendor prefixes |

## 🔧 Configuration Files

- `vite.config.js` - Vite build configuration
- `tailwind.config.js` - Tailwind CSS customization
- `postcss.config.js` - PostCSS plugins
- `package.json` - Project dependencies and scripts

## 🌐 Browser Support

- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+

**Note**: Voice features require browser support for Web Speech API.

## � Supabase Backend Integration

The application includes complete Supabase backend setup:

### Database Schema (16 Tables)
- **profiles**: User/doctor accounts with settings
- **patients**: Patient registry with demographics
- **patient_allergies/comorbidities/medications**: Patient medical data
- **appointments**: Scheduling with triage support
- **vitals**: Vital signs with auto-status calculation
- **consultations**: Clinical encounters
- **diagnoses**: AI and manual diagnoses
- **care_plans**: Treatment plans with AI integration
- **care_plan_medications/interventions/investigations**: Plan components
- **cds_alerts**: Clinical decision support alerts
- **audit_log**: Complete action tracking
- **usage_metrics**: Analytics and performance data

### Storage Buckets
- `patient-documents`: Medical documents and lab results
- `profile-avatars`: User profile pictures
- `care-plan-exports`: Generated PDF care plans

### Setup Instructions
See [docs/SUPABASE_SETUP.md](docs/SUPABASE_SETUP.md) for complete setup guide.

## 🩺 rPPG Vital Scanner Integration (2026-05-21)

The Doctor UI now includes a **contactless vital signs scanner** powered by remote photoplethysmography (rPPG) and an optional ESP32 hardware sensor.

### How It Works

1. The doctor opens a patient consultation and clicks the **rPPG Scan** button
2. The browser streams webcam frames to the **rPPG backend** (Python/FastAPI) via WebSocket
3. The backend extracts a Blood Volume Pulse (BVP) waveform from subtle skin colour changes in the patient's **forehead region** using two methods in parallel:
   - **POS algorithm** — traditional signal processing (fast, always-on)
   - **EfficientPhys deep learning model** — neural network for a second independent estimate
4. Both methods compute: **Heart Rate, SpO₂, Respiratory Rate, Blood Pressure**
5. If an **ESP32 MAX30100 finger sensor** is connected, hardware HR, SpO₂ and temperature are received via HTTP and blended with the camera readings
6. The doctor clicks **Apply to Vitals** — all values fill the consultation form automatically and are saved to Supabase `live_vitals`

### UI Entry Points

| Component | Location | Description |
|---|---|---|
| `LiveVitalsWidget` | Top of consultation page | Compact live bar — HR · SpO₂ · BP · RR · Quality% with "Apply to Vitals" button |
| `RPPGScanModal` | Scan button in patient chart | Full-screen camera view with face guide, live vitals panel, and "Apply X of 6 vitals" button |

### Starting Everything

Three separate terminals are required:

```bash
# Terminal 1 — rPPG backend (port 8090)
python rppg_poc/rppg_vitals.py

# Terminal 2 — Doctor UI backend (port 8058)
uvicorn agent.api:app --port 8058

# Terminal 3 — Doctor UI frontend (port 5173)
cd "Doctor UI"
npm run dev
```

| Service | URL |
|---|---|
| Doctor UI | http://localhost:5173 |
| API Backend | http://localhost:8058 |
| rPPG Backend | http://localhost:8090 |
| rPPG POC Standalone | http://localhost:8090 |

### ESP32 Hardware Sensor

The MAX30100 finger sensor posts to `http://<host>:8090/api/vitals`. When a reading arrives, the Doctor UI status bar shows **ESP32** badge and prioritises hardware SpO₂ and temperature over camera estimates.

### Signal Quality

The rPPG backend computes a **true SNR-based signal quality** (peak BVP power vs noise floor). Quality is displayed as a colour-coded bar:
- **Green (>60%)** — reliable reading
- **Amber (30–60%)** — usable but noisy
- **Red (<30%)** — position face closer, improve lighting

### Key Technical Notes
- ROI is **forehead-only** (top 22% of face) — avoids glasses glare which was the largest error driver in validation
- Hardware SpO₂ uses jump rejection (±10%) to discard contact-loss spikes
- When ESP32 sends `hr=0` (no finger), UI shows "👆 Place Finger" instead of "--"
- Session minimum enforced at **2 minutes** before vitals can be saved

## 📄 License

Proprietary - MHNexus Healthcare Solutions

## 👥 Team

- **MHNexus Development Team**
- Chua Zhu Heng (Leader)
- Chin Pei Kang
- Lim Zhi Pin
- Low Jia Qi
- Satish Rao

---


---

For a full list of changes, see [CHANGELOG.md](CHANGELOG.md).

**Version**: 1.9.0 (rPPG Vital Scanner + Doctor UI Integration, May 2026)
**Last Updated**: May 21, 2026
