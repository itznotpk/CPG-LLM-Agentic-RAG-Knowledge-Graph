# 🏥 CPG RAG Assistant Frontend

A beautiful, responsive web interface for the Malaysia Clinical Practice Guidelines RAG Assistant.

## 🚀 Quick Start

### Option 1: One-Command Start
```bash
python run.py
```

### Option 2: Manual Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Start server
python main.py
```

## 📁 Project Structure

```
cpg-rag-frontend/
├── main.py                 # FastAPI backend server
├── run.py                  # One-click runner script
├── requirements.txt        # Python dependencies
├── templates/              # Jinja2 HTML templates
│   ├── base.html          # Base template with styling
│   ├── index.html         # Home page with query form
│   └── results.html       # Results page with 4-section layout
└── README_FRONTEND.md     # This file
```

## ✨ Features

### 🎨 Beautiful UI
- **Responsive design** with Tailwind CSS
- **Professional medical theme** with gradient headers
- **Card-based layout** for easy reading
- **Font Awesome icons** for visual clarity

### 🔍 Query Interface
- **Large text area** for clinical queries
- **Sample cases** for quick testing
- **Form validation** and user feedback

### 📊 Results Display
- **4-section analysis layout:**
  - 🔵 **Clinical Summary** (Blue card)
  - 🟢 **Follow-up Care Plan** (Green card)  
  - 🟣 **Medication Suggestions** (Purple card)
  - 🟠 **Next Steps** (Orange card)

### 🛡️ Safety Features
- **Clinical disclaimer** on results page
- **Professional medical styling**
- **Evidence-based language**

## 🧪 Testing

### Sample Queries
1. **"45-year-old male with erectile dysfunction, hypertension, and diabetes"**
2. **"28-year-old male with performance anxiety and mild erectile dysfunction"**
3. **"62-year-old male with erectile dysfunction following radical prostatectomy"**
4. **"55-year-old male with erectile dysfunction and recent myocardial infarction"**

### Expected Results
Each query returns a comprehensive 4-section analysis with:
- Clinical assessment and key findings
- Structured follow-up care plans
- Evidence-based medication recommendations
- Actionable next steps with timelines

## 🔧 Customization

### Modify Mock Data
Edit the `mock_results` dictionary in `main.py`:

```python
mock_results = {
    "query": query,
    "summary": "Your clinical summary HTML...",
    "followup_plan": "Your follow-up plan HTML...",
    "medications": "Your medication suggestions HTML...",
    "next_steps": "Your next steps HTML..."
}
```

### Update Styling
- **Colors:** Modify Tailwind classes in templates
- **Layout:** Edit the grid structure in `results.html`
- **Icons:** Change Font Awesome icons in templates

### Add New Sections
1. Add new data to `mock_results` in `main.py`
2. Create new card in `results.html`
3. Choose appropriate color scheme

## 🌐 API Endpoints

- **`GET /`** - Home page with query form
- **`POST /analyze`** - Process clinical query (form data)
- **`GET /analyze?query=...`** - Process clinical query (URL params)
- **`GET /health`** - Health check endpoint

## 🔗 Integration

To integrate with your RAG backend, replace the mock data in `process_analysis()`:

```python
async def process_analysis(request: Request, query: str):
    # Replace this with your RAG system
    rag_response = await your_rag_system.analyze(query)
    
    return templates.TemplateResponse("results.html", {
        "request": request,
        "query": query,
        "summary": rag_response.summary,
        "followup_plan": rag_response.followup_plan,
        "medications": rag_response.medications,
        "next_steps": rag_response.next_steps
    })
```

## 🐛 Troubleshooting

### Port 8000 in use
```bash
# Find and kill process using port 8000
lI'll create all the necessary files for you. Let me put the complete frontend system together:

````python path=main.py mode=EDIT
from fastapi import FastAPI, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import uvicorn

app = FastAPI(title="CPG RAG Assistant")

# Templates
templates = Jinja2Templates(directory="templates")

# Static files (if needed later)
# app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """
    Home page with query input form.
    """
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/analyze", response_class=HTMLResponse)
async def analyze_get(request: Request, query: str):
    """
    Handle GET request for analysis (from URL params).
    """
    return await process_analysis(request, query)

@app.post("/analyze", response_class=HTMLResponse)
async def analyze_post(request: Request, query: str = Form(...)):
    """
    Handle POST request for analysis (from form).
    """
    return await process_analysis(request, query)

async def process_analysis(request: Request, query: str):
    """
    Process the clinical query and return results.
    
    Args:
        request: FastAPI request object
        query: Clinical query string
        
    Returns:
        TemplateResponse: Rendered results page
    """
    # TODO: Replace with actual RAG processing
    # This is mock data for testing the UI
    
    mock_results = {
        "query": query,
        "summary": """
        <p><strong>Patient Presentation:</strong> 45-year-old male with erectile dysfunction, hypertension, and diabetes.</p>
        <p><strong>Key Findings:</strong></p>
        <ul>
            <li>ED symptoms for 6 months duration</li>
            <li>Comorbid conditions: HTN, DM</li>
            <li>Current medications may contribute to ED</li>
            <li>Cardiovascular risk factors present</li>
        </ul>
        <p><strong>Clinical Assessment:</strong> Multifactorial ED with vascular and medication-related components.</p>
        """,
        
        "followup_plan": """
        <p><strong>Immediate Actions:</strong></p>
        <ul>
            <li>Comprehensive cardiovascular assessment</li>
            <li>Review and optimize current medications</li>
            <li>Lifestyle counseling (diet, exercise, smoking cessation)</li>
        </ul>
        <p><strong>Follow-up Schedule:</strong></p>
        <ul>
            <li>2 weeks: Medication review and adjustment</li>
            <li>4 weeks: Response assessment</li>
            <li>3 months: Comprehensive re-evaluation</li>
        </ul>
        """,
        
        "medications": """
        <p><strong>First-line Treatment:</strong></p>
        <ul>
            <li><strong>Sildenafil 50mg</strong> - Start 1 hour before activity, may adjust to 25-100mg</li>
            <li><strong>Alternative:</strong> Tadalafil 10mg PRN or 5mg daily</li>
        </ul>
        <p><strong>Considerations:</strong></p>
        <ul>
            <li>Monitor for drug interactions with current medications</li>
            <li>Contraindicated with nitrates</li>
            <li>Caution with alpha-blockers</li>
        </ul>
        <p><strong>Adjunct Therapy:</strong></p>
        <ul>
            <li>Optimize diabetes control (target HbA1c &lt;7%)</li>
            <li>Consider ACE inhibitor switch if lisinopril contributing</li>
        </ul>
        """,
        
        "next_steps": """
        <p><strong>Immediate (1-2 weeks):</strong></p>
        <ul>
            <li>Laboratory workup: Testosterone, lipid panel, HbA1c</li>
            <li>ECG and cardiovascular risk stratification</li>
            <li>Patient education on PDE5 inhibitor use</li>
        </ul>
        <p><strong>Short-term (1-3 months):</strong></p>
        <ul>
            <li>Monitor treatment response and side effects</li>
            <li>Lifestyle modification support</li>
            <li>Consider referral to endocrinology for diabetes optimization</li>
        </ul>
        <p><strong>Long-term (3-6 months):</strong></p>
        <ul>
            <li>Reassess treatment efficacy</li>
            <li>Consider alternative therapies if inadequate response</li>
            <li>Ongoing cardiovascular risk management</li>
        </ul>
        """
    }
    
    return templates.TemplateResponse("results.html", {
        "request": request,
        **mock_results
    })

@app.get("/health")
async def health_check():
    """
    Health check endpoint.
    """
    return {"status": "healthy", "service": "CPG RAG Assistant"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)