#!/usr/bin/env python3
"""CPG RAG Frontend - Clean Implementation"""
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

HTML_PAGE = r"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CPG RAG Assistant</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <style>
        .loader { border: 4px solid #f3f3f3; border-top: 4px solid #3498db; border-radius: 50%; width: 50px; height: 50px; animation: spin 1s linear infinite; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
        .pulse { animation: pulse 1.5s ease-in-out infinite; }
        .step-active { background: #3b82f6; color: white; }
        .step-done { background: #22c55e; color: white; }
        .step-waiting { background: #374151; color: #9ca3af; }
        /* Add spacing between content items */
        .content-spaced p { margin-bottom: 1rem; }
        .content-spaced li { margin-bottom: 0.75rem; }
        .content-spaced strong { display: inline-block; margin-top: 0.5rem; }
    </style>
</head>
<body class="bg-gradient-to-br from-slate-900 via-blue-900 to-slate-900 min-h-screen">
<div class="container mx-auto px-4 py-8 max-w-6xl">
    <div class="text-center mb-8">
        <h1 class="text-4xl font-bold text-white mb-2">🏥 CPG Clinical Assistant</h1>
        <p class="text-gray-300">Evidence-based clinical decision support powered by AI</p>
    </div>

    <!-- Query Section -->
    <div id="querySection" class="bg-white/10 backdrop-blur rounded-2xl p-6 mb-6">
        <h2 class="text-xl font-semibold text-white mb-4">📝 Describe Your Clinical Case</h2>
        <textarea id="queryInput" rows="4" class="w-full bg-white/20 border border-white/30 rounded-xl p-4 text-white placeholder-gray-400 focus:ring-2 focus:ring-blue-400 focus:outline-none" placeholder="Enter clinical case details..."></textarea>
        <button id="analyzeBtn" class="w-full mt-4 bg-gradient-to-r from-blue-500 to-cyan-500 hover:from-blue-600 hover:to-cyan-600 text-white font-bold py-4 rounded-xl transition transform hover:scale-[1.02]">🔍 Analyze Case</button>
        <p class="text-gray-400 text-sm mt-6 mb-3 text-center">Or select a test case:</p>
        <div id="testCases" class="grid grid-cols-1 md:grid-cols-3 gap-3"></div>
    </div>

    <!-- Loading Section with AI Steps -->
    <div id="loadingSection" class="hidden">
        <div class="bg-white/10 backdrop-blur rounded-2xl p-8">
            <div class="text-center mb-8">
                <div class="loader mx-auto mb-4"></div>
                <h2 class="text-2xl font-bold text-white mb-2">🤖 AI is Analyzing...</h2>
                <p id="currentStep" class="text-cyan-400 text-lg pulse">Initializing analysis...</p>
            </div>
            <!-- Progress Steps -->
            <div class="max-w-2xl mx-auto">
                <div class="flex items-center justify-between mb-4">
                    <div id="step1" class="flex items-center gap-2 px-4 py-2 rounded-full step-waiting">
                        <span>1</span><span class="hidden md:inline">Parsing Query</span>
                    </div>
                    <div class="flex-1 h-1 bg-gray-600 mx-2"></div>
                    <div id="step2" class="flex items-center gap-2 px-4 py-2 rounded-full step-waiting">
                        <span>2</span><span class="hidden md:inline">Knowledge Graph</span>
                    </div>
                    <div class="flex-1 h-1 bg-gray-600 mx-2"></div>
                    <div id="step3" class="flex items-center gap-2 px-4 py-2 rounded-full step-waiting">
                        <span>3</span><span class="hidden md:inline">Vector Search</span>
                    </div>
                    <div class="flex-1 h-1 bg-gray-600 mx-2"></div>
                    <div id="step4" class="flex items-center gap-2 px-4 py-2 rounded-full step-waiting">
                        <span>4</span><span class="hidden md:inline">Generating</span>
                    </div>
                </div>
                <div id="stepDetails" class="bg-black/30 rounded-xl p-4 text-gray-300 text-sm font-mono">
                    <p>🔄 Starting analysis pipeline...</p>
                </div>
            </div>
        </div>
    </div>

    <!-- Results Section -->
    <div id="resultsSection" class="hidden">
        <div class="flex justify-between items-center mb-6">
            <h2 class="text-2xl font-bold text-white">📋 Clinical Recommendations</h2>
            <button id="newQueryBtn" class="bg-white/20 hover:bg-white/30 text-white px-6 py-2 rounded-lg transition">← New Query</button>
        </div>
        <div class="bg-blue-900/50 rounded-xl p-4 mb-6">
            <p class="text-gray-400 text-sm">Patient Query:</p>
            <p id="queryDisplay" class="text-white font-medium"></p>
        </div>

        <!-- 4 Main Sections -->
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
            <!-- 1) Summary -->
            <div class="bg-white rounded-2xl shadow-xl overflow-hidden">
                <div class="bg-gradient-to-r from-blue-500 to-blue-600 text-white p-4">
                    <h3 class="font-bold text-lg">📋 1) Clinical Summary</h3>
                </div>
                <div id="summaryContent" class="p-5 prose prose-sm max-w-none text-gray-700 content-spaced"></div>
            </div>
            <!-- 2) Medication Changes -->
            <div class="bg-white rounded-2xl shadow-xl overflow-hidden">
                <div class="bg-gradient-to-r from-purple-500 to-violet-600 text-white p-4">
                    <h3 class="font-bold text-lg">💊 2) Medication Changes</h3>
                </div>
                <div id="medicationsContent" class="p-5 prose prose-sm max-w-none text-gray-700 content-spaced"></div>
            </div>
            <!-- 3) Patient Education & Counseling -->
            <div class="bg-white rounded-2xl shadow-xl overflow-hidden">
                <div class="bg-gradient-to-r from-green-500 to-emerald-600 text-white p-4">
                    <h3 class="font-bold text-lg">📚 3) Patient Education & Counseling</h3>
                </div>
                <div id="educationContent" class="p-5 prose prose-sm max-w-none text-gray-700 content-spaced"></div>
            </div>
            <!-- 4) Monitoring & Next Steps -->
            <div class="bg-white rounded-2xl shadow-xl overflow-hidden">
                <div class="bg-gradient-to-r from-orange-500 to-amber-600 text-white p-4">
                    <h3 class="font-bold text-lg">📊 4) Monitoring & Next Steps</h3>
                </div>
                <div id="monitoringContent" class="p-5 prose prose-sm max-w-none text-gray-700 content-spaced"></div>
            </div>
        </div>

        <!-- References/Sources -->
        <div class="bg-white rounded-2xl shadow-xl overflow-hidden mb-6">
            <div class="bg-gradient-to-r from-gray-600 to-gray-700 text-white p-4">
                <h3 class="font-bold text-lg">📚 References & Sources</h3>
            </div>
            <div id="sourcesContent" class="p-5 max-h-80 overflow-y-auto"></div>
        </div>

        <!-- Tools Used -->
        <div class="bg-white/10 rounded-2xl p-4 mb-6">
            <h3 class="text-white font-bold mb-3">🛠️ Tools Used by AI</h3>
            <div id="toolsUsed" class="flex flex-wrap gap-2"></div>
        </div>

        <!-- Raw Response -->
        <details class="bg-gray-800 rounded-xl p-4">
            <summary class="text-white cursor-pointer font-medium">🔧 Raw AI Response (Debug)</summary>
            <pre id="rawResponse" class="text-gray-300 text-xs mt-3 whitespace-pre-wrap max-h-64 overflow-auto bg-black/50 p-4 rounded-lg"></pre>
        </details>
    </div>
</div>

<script>
const TEST_CASES = [
    {title: "🩺 ED + Comorbidities", desc: "45yo with HTN, DM", query: "45-year-old male with erectile dysfunction, hypertension, and diabetes. Currently on metformin and amlodipine."},
    {title: "😰 Young Adult ED", desc: "28yo performance anxiety", query: "28-year-old male with performance anxiety and mild erectile dysfunction. No other medical conditions. First relationship."},
    {title: "🏥 Post-Prostatectomy", desc: "62yo post-surgery", query: "62-year-old male with severe erectile dysfunction post radical prostatectomy for prostate cancer 6 months ago."},
    {title: "💔 Cardiac History", desc: "55yo CAD, stent", query: "55-year-old male with ED who failed sildenafil 100mg. History of coronary artery disease with stent placement 2 years ago."},
    {title: "🚬 Lifestyle ED", desc: "38yo obese smoker", query: "38-year-old male with low libido and erectile dysfunction. BMI 32, sedentary lifestyle, smoker for 15 years."},
    {title: "🧪 Low Testosterone", desc: "50yo hypogonadism", query: "50-year-old male with diabetes, ED, and symptoms of hypogonadism including fatigue and decreased muscle mass."},
    {title: "⚠️ Nitrate User", desc: "60yo contraindication", query: "60-year-old male with ED currently taking isosorbide dinitrate for angina. Wants to try sildenafil."},
    {title: "💊 PDE5i Failure", desc: "52yo refractory", query: "52-year-old male who has failed sildenafil, tadalafil, and vardenafil at maximum doses. Looking for alternatives."},
    {title: "🔬 New Diagnosis", desc: "40yo first presentation", query: "40-year-old male presenting with new onset erectile dysfunction for 3 months. No prior medical history."}
];

const AI_STEPS = [
    {step: 1, msg: "🔍 Parsing clinical query and extracting key information..."},
    {step: 2, msg: "🔗 Searching Knowledge Graph for patient classification and drug interactions..."},
    {step: 3, msg: "📄 Performing Vector Search on CPG documents..."},
    {step: 4, msg: "✨ Generating clinical recommendations based on guidelines..."}
];

let stepInterval = null;

function renderTestCases() {
    document.getElementById('testCases').innerHTML = TEST_CASES.map((tc, i) =>
        `<button class="bg-white/10 hover:bg-white/20 border border-white/20 rounded-xl p-4 text-left transition transform hover:scale-[1.02]" onclick="selectCase(${i})">
            <p class="text-white font-medium">${tc.title}</p>
            <p class="text-gray-400 text-sm">${tc.desc}</p>
        </button>`
    ).join('');
}

function selectCase(idx) {
    document.getElementById('queryInput').value = TEST_CASES[idx].query;
}

function showSection(id) {
    ['querySection', 'loadingSection', 'resultsSection'].forEach(s => document.getElementById(s).classList.add('hidden'));
    document.getElementById(id).classList.remove('hidden');
}

function updateStep(stepNum) {
    for (let i = 1; i <= 4; i++) {
        const el = document.getElementById('step' + i);
        if (i < stepNum) el.className = 'flex items-center gap-2 px-4 py-2 rounded-full step-done';
        else if (i === stepNum) el.className = 'flex items-center gap-2 px-4 py-2 rounded-full step-active';
        else el.className = 'flex items-center gap-2 px-4 py-2 rounded-full step-waiting';
    }
    const stepInfo = AI_STEPS.find(s => s.step === stepNum);
    if (stepInfo) {
        document.getElementById('currentStep').textContent = stepInfo.msg;
        document.getElementById('stepDetails').innerHTML += `<p>${stepInfo.msg}</p>`;
    }
}

function startLoadingAnimation() {
    document.getElementById('stepDetails').innerHTML = '<p>🔄 Starting analysis pipeline...</p>';
    let currentStep = 1;
    updateStep(currentStep);
    stepInterval = setInterval(() => {
        currentStep++;
        if (currentStep <= 4) updateStep(currentStep);
    }, 2000);
}

function stopLoadingAnimation() {
    if (stepInterval) { clearInterval(stepInterval); stepInterval = null; }
    for (let i = 1; i <= 4; i++) document.getElementById('step' + i).className = 'flex items-center gap-2 px-4 py-2 rounded-full step-done';
    document.getElementById('currentStep').textContent = '✅ Analysis complete!';
}

function addLineSpacing(text) {
    // Add double line breaks after lines ending with a period that are followed by a line starting with bold text (like "Lifestyle:", "Drug:", etc.)
    return text
        .replace(/(\*\*[^*]+\*\*:)/g, '\n\n$1')  // Add blank line before bold labels like **Lifestyle:**
        .replace(/^- /gm, '\n- ')  // Add blank line before list items
        .replace(/\n{3,}/g, '\n\n')  // Clean up excessive line breaks
        .trim();
}

function parseResponse(text) {
    const sections = {summary: '', medications: '', education: '', monitoring: ''};
    const lines = text.split('\n');
    let current = null, content = [];
    for (let line of lines) {
        const lower = line.toLowerCase();
        if (lower.includes('1)') && lower.includes('summary')) { if (current) sections[current] = content.join('\n'); current = 'summary'; content = []; }
        else if (lower.includes('2)') && lower.includes('medication')) { if (current) sections[current] = content.join('\n'); current = 'medications'; content = []; }
        else if (lower.includes('3)') && (lower.includes('education') || lower.includes('counseling'))) { if (current) sections[current] = content.join('\n'); current = 'education'; content = []; }
        else if (lower.includes('4)') && (lower.includes('monitoring') || lower.includes('next'))) { if (current) sections[current] = content.join('\n'); current = 'monitoring'; content = []; }
        else if (current) content.push(line);
    }
    if (current) sections[current] = content.join('\n');
    if (!sections.summary && !sections.medications && !sections.education && !sections.monitoring) sections.summary = text;
    if (!sections.summary) sections.summary = 'Clinical assessment based on CPG guidelines.';
    if (!sections.medications) sections.medications = 'See clinical summary for medication details.';
    if (!sections.education) sections.education = 'Discuss treatment options with patient.';
    if (!sections.monitoring) sections.monitoring = 'Follow up as clinically indicated.';
    // Add spacing to each section
    for (let key in sections) { sections[key] = addLineSpacing(sections[key]); }
    return sections;
}

function renderSources(sources) {
    if (!sources || sources.length === 0) return '<p class="text-gray-500 italic">No sources retrieved.</p>';
    return sources.map((s, i) => {
        const tool = (s.tool || '').toLowerCase();
        let badge = '<span class="bg-blue-100 text-blue-800 text-xs px-2 py-1 rounded-full">📄 Vector</span>';
        if (tool.includes('graph')) badge = '<span class="bg-green-100 text-green-800 text-xs px-2 py-1 rounded-full">🔗 Graph</span>';
        else if (tool.includes('drug')) badge = '<span class="bg-purple-100 text-purple-800 text-xs px-2 py-1 rounded-full">💊 Drug</span>';
        else if (tool.includes('algorithm')) badge = '<span class="bg-orange-100 text-orange-800 text-xs px-2 py-1 rounded-full">📋 Algorithm</span>';
        const score = s.score ? parseFloat(s.score).toFixed(2) : 'N/A';
        return `<div class="border border-gray-200 rounded-xl p-4 mb-3 hover:shadow-md transition">
            <div class="flex justify-between items-start mb-2">
                <span class="font-semibold text-gray-800">[${i+1}] ${s.document_title || s.title || 'CPG Document'}</span>
                <div class="flex gap-2">${badge}<span class="text-xs text-gray-500 bg-gray-100 px-2 py-1 rounded">Score: ${score}</span></div>
            </div>
            <p class="text-sm text-gray-600">${s.content || s.text || 'No preview available.'}</p>
        </div>`;
    }).join('');
}

function renderTools(tools) {
    if (!tools || tools.length === 0) return '<span class="text-gray-400">No tools recorded</span>';
    const colors = {graph_search: 'bg-green-500', vector_search: 'bg-blue-500', hybrid_search: 'bg-purple-500', get_drug_information: 'bg-pink-500', get_algorithm_pathway: 'bg-orange-500'};
    return tools.map(t => {
        const name = t.tool_name || t.name || t;
        const color = colors[name] || 'bg-gray-500';
        return `<span class="${color} text-white text-sm px-3 py-1 rounded-full">${name}</span>`;
    }).join('');
}

async function analyze() {
    const query = document.getElementById('queryInput').value.trim();
    if (!query) { alert('Please enter a clinical query'); return; }
    showSection('loadingSection');
    startLoadingAnimation();
    try {
        const res = await fetch('http://127.0.0.1:8058/chat', {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({message: query})
        });
        const data = await res.json();
        stopLoadingAnimation();
        const msg = data.message || 'No response received';
        const sections = parseResponse(msg);
        document.getElementById('queryDisplay').textContent = query;
        document.getElementById('summaryContent').innerHTML = marked.parse(sections.summary);
        document.getElementById('medicationsContent').innerHTML = marked.parse(sections.medications);
        document.getElementById('educationContent').innerHTML = marked.parse(sections.education);
        document.getElementById('monitoringContent').innerHTML = marked.parse(sections.monitoring);
        document.getElementById('sourcesContent').innerHTML = renderSources(data.sources || []);
        document.getElementById('toolsUsed').innerHTML = renderTools(data.tools_used || []);
        document.getElementById('rawResponse').textContent = msg;
        showSection('resultsSection');
    } catch (e) {
        stopLoadingAnimation();
        alert('Error connecting to backend: ' + e.message + '\n\nMake sure backend is running on port 8058');
        showSection('querySection');
    }
}

document.addEventListener('DOMContentLoaded', () => {
    renderTestCases();
    document.getElementById('analyzeBtn').onclick = analyze;
    document.getElementById('newQueryBtn').onclick = () => showSection('querySection');
});
</script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def home():
    return HTML_PAGE

if __name__ == "__main__":
    print("🏥 CPG Clinical Assistant Frontend")
    print("=" * 40)
    print("📍 Frontend: http://127.0.0.1:8080")
    print("📍 Backend should be running on: http://127.0.0.1:8058")
    print("=" * 40)
    uvicorn.run(app, host="127.0.0.1", port=8080)