from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

HTML_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CPG RAG Assistant</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <style>
        @keyframes pulse-ring {
            0% { transform: scale(0.8); opacity: 1; }
            100% { transform: scale(2); opacity: 0; }
        }
        @keyframes float {
            0%, 100% { transform: translateY(0px); }
            50% { transform: translateY(-10px); }
        }
        .pulse-ring { animation: pulse-ring 1.5s ease-out infinite; }
        .float { animation: float 2s ease-in-out infinite; }
        .fade-in { animation: fadeIn 0.5s ease-out; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }
    </style>
</head>
<body class="bg-gradient-to-br from-slate-900 via-blue-900 to-slate-900 min-h-screen">

    <!-- PAGE 1: Query Input -->
    <div id="queryPage" class="min-h-screen flex flex-col">
        <div class="flex-1 flex items-center justify-center p-4">
            <div class="max-w-2xl w-full">
                <!-- Logo & Title -->
                <div class="text-center mb-8">
                    <div class="inline-block p-4 bg-blue-500/20 rounded-full mb-4">
                        <span class="text-5xl">🏥</span>
                    </div>
                    <h1 class="text-4xl font-bold text-white mb-2">CPG RAG Assistant</h1>
                    <p class="text-blue-300">Clinical Practice Guidelines - Malaysia ED Management</p>
                </div>

                <!-- Query Card -->
                <div class="bg-white/10 backdrop-blur-lg rounded-2xl p-6 shadow-2xl border border-white/20">
                    <h2 class="text-xl font-semibold text-white mb-4">Describe Your Clinical Case</h2>
                    <textarea id="query" rows="4"
                        class="w-full bg-white/10 border border-white/30 rounded-xl p-4 text-white placeholder-gray-400 focus:ring-2 focus:ring-blue-400 focus:border-transparent resize-none"
                        placeholder="e.g., 45-year-old male with erectile dysfunction, hypertension, and diabetes..."></textarea>
                    <button onclick="startAnalysis()" id="submitBtn"
                        class="w-full mt-4 bg-gradient-to-r from-blue-500 to-cyan-500 hover:from-blue-600 hover:to-cyan-600 text-white font-bold py-4 rounded-xl transition-all transform hover:scale-[1.02] shadow-lg">
                        🔍 Analyze Case
                    </button>
                </div>

                <!-- Sample Cases -->
                <div class="mt-6">
                    <p class="text-gray-400 text-sm mb-3 text-center">Or try a sample case:</p>
                    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                        <button onclick="setQuery('45-year-old male with erectile dysfunction, hypertension, and diabetes. Currently on metformin and amlodipine.')"
                            class="bg-white/5 hover:bg-white/10 border border-white/10 rounded-xl p-4 text-left transition">
                            <p class="text-white font-medium">🩺 ED with Comorbidities</p>
                            <p class="text-gray-400 text-sm">45yo male with HTN, DM on medications</p>
                        </button>
                        <button onclick="setQuery('28-year-old male with performance anxiety and mild erectile dysfunction. No other medical conditions. First relationship.')"
                            class="bg-white/5 hover:bg-white/10 border border-white/10 rounded-xl p-4 text-left transition">
                            <p class="text-white font-medium">😰 Young Adult ED</p>
                            <p class="text-gray-400 text-sm">28yo with performance anxiety</p>
                        </button>
                        <button onclick="setQuery('62-year-old male with severe erectile dysfunction post radical prostatectomy for prostate cancer 6 months ago.')"
                            class="bg-white/5 hover:bg-white/10 border border-white/10 rounded-xl p-4 text-left transition">
                            <p class="text-white font-medium">🏥 Post-Prostatectomy ED</p>
                            <p class="text-gray-400 text-sm">62yo post prostate cancer surgery</p>
                        </button>
                        <button onclick="setQuery('55-year-old male with ED who failed sildenafil 100mg. History of coronary artery disease with stent placement 2 years ago.')"
                            class="bg-white/5 hover:bg-white/10 border border-white/10 rounded-xl p-4 text-left transition">
                            <p class="text-white font-medium">💔 ED with Cardiac History</p>
                            <p class="text-gray-400 text-sm">55yo CAD, PDE5i failure</p>
                        </button>
                        <button onclick="setQuery('38-year-old male with low libido and erectile dysfunction. BMI 32, sedentary lifestyle, smoker for 15 years.')"
                            class="bg-white/5 hover:bg-white/10 border border-white/10 rounded-xl p-4 text-left transition">
                            <p class="text-white font-medium">🚬 Lifestyle-Related ED</p>
                            <p class="text-gray-400 text-sm">38yo obese smoker, low libido</p>
                        </button>
                        <button onclick="setQuery('50-year-old male with diabetes, ED, and symptoms of hypogonadism including fatigue and decreased muscle mass. Morning testosterone pending.')"
                            class="bg-white/5 hover:bg-white/10 border border-white/10 rounded-xl p-4 text-left transition">
                            <p class="text-white font-medium">🧪 ED with Low Testosterone</p>
                            <p class="text-gray-400 text-sm">50yo DM, suspected hypogonadism</p>
                        </button>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- PAGE 2: Analyzing Full Screen -->
    <div id="analyzingPage" class="hidden fixed inset-0 bg-gradient-to-br from-slate-900 via-blue-900 to-slate-900 z-50">
        <div class="min-h-screen flex flex-col items-center justify-center p-4">
            <!-- Animated Icon -->
            <div class="relative mb-8">
                <div class="absolute inset-0 bg-blue-500 rounded-full pulse-ring"></div>
                <div class="relative p-6 bg-gradient-to-br from-blue-500 to-cyan-500 rounded-full float">
                    <span class="text-5xl">🧠</span>
                </div>
            </div>

            <!-- Status Text -->
            <h2 class="text-3xl font-bold text-white mb-4">Analyzing Your Case</h2>
            <p id="analysisStatus" class="text-blue-300 text-lg mb-8">Searching clinical guidelines...</p>

            <!-- Progress Steps -->
            <div class="max-w-md w-full space-y-3">
                <div id="step1" class="flex items-center gap-3 text-gray-400">
                    <div class="w-6 h-6 rounded-full border-2 border-current flex items-center justify-center">
                        <span class="text-xs">1</span>
                    </div>
                    <span>Searching knowledge base</span>
                </div>
                <div id="step2" class="flex items-center gap-3 text-gray-500">
                    <div class="w-6 h-6 rounded-full border-2 border-current flex items-center justify-center">
                        <span class="text-xs">2</span>
                    </div>
                    <span>Analyzing clinical context</span>
                </div>
                <div id="step3" class="flex items-center gap-3 text-gray-500">
                    <div class="w-6 h-6 rounded-full border-2 border-current flex items-center justify-center">
                        <span class="text-xs">3</span>
                    </div>
                    <span>Generating recommendations</span>
                </div>
            </div>

            <!-- Query Preview -->
            <div class="mt-8 max-w-lg w-full bg-white/5 rounded-xl p-4 border border-white/10">
                <p class="text-gray-400 text-sm mb-1">Your query:</p>
                <p id="queryPreview" class="text-white"></p>
            </div>
        </div>
    </div>

    <!-- PAGE 3: Results -->
    <div id="resultsPage" class="hidden min-h-screen">
        <!-- Header with Back Button -->
        <header class="bg-white/10 backdrop-blur-lg border-b border-white/10 sticky top-0 z-40">
            <div class="container mx-auto px-4 py-4 flex items-center justify-between">
                <button onclick="goBack()" class="flex items-center gap-2 text-white hover:text-blue-300 transition">
                    <span>←</span> New Query
                </button>
                <h1 class="text-xl font-bold text-white">🏥 CPG Analysis Results</h1>
                <div class="w-24"></div>
            </div>
        </header>

        <main class="container mx-auto px-4 py-8 max-w-6xl">
            <!-- Query Summary -->
            <div class="bg-white/10 backdrop-blur rounded-xl p-4 mb-6 border border-white/10 fade-in">
                <p class="text-gray-400 text-sm">Analysis for:</p>
                <p id="resultQueryText" class="text-white font-medium"></p>
            </div>

            <!-- Results Grid -->
            <div class="grid md:grid-cols-2 gap-6 mb-6">
                <!-- Summary -->
                <div class="bg-white rounded-2xl shadow-xl overflow-hidden fade-in" style="animation-delay: 0.1s">
                    <div class="bg-gradient-to-r from-blue-500 to-blue-600 text-white p-4">
                        <h3 class="text-lg font-bold flex items-center gap-2">📋 Summary</h3>
                    </div>
                    <div id="summary" class="p-5 prose prose-sm max-w-none text-gray-700"></div>
                </div>

                <!-- Follow-up Care Plan -->
                <div class="bg-white rounded-2xl shadow-xl overflow-hidden fade-in" style="animation-delay: 0.2s">
                    <div class="bg-gradient-to-r from-green-500 to-emerald-600 text-white p-4">
                        <h3 class="text-lg font-bold flex items-center gap-2">📅 Follow-up Care Plan</h3>
                    </div>
                    <div id="followup" class="p-5 prose prose-sm max-w-none text-gray-700"></div>
                </div>

                <!-- Medications -->
                <div class="bg-white rounded-2xl shadow-xl overflow-hidden fade-in" style="animation-delay: 0.3s">
                    <div class="bg-gradient-to-r from-purple-500 to-violet-600 text-white p-4">
                        <h3 class="text-lg font-bold flex items-center gap-2">💊 Medications</h3>
                    </div>
                    <div id="medications" class="p-5 prose prose-sm max-w-none text-gray-700"></div>
                </div>

                <!-- Next Steps -->
                <div class="bg-white rounded-2xl shadow-xl overflow-hidden fade-in" style="animation-delay: 0.4s">
                    <div class="bg-gradient-to-r from-orange-500 to-amber-600 text-white p-4">
                        <h3 class="text-lg font-bold flex items-center gap-2">➡️ Next Steps</h3>
                    </div>
                    <div id="nextsteps" class="p-5 prose prose-sm max-w-none text-gray-700"></div>
                </div>
            </div>

            <!-- Sources Section -->
            <div class="bg-white rounded-2xl shadow-xl overflow-hidden fade-in mb-6" style="animation-delay: 0.5s">
                <div class="bg-gradient-to-r from-gray-700 to-gray-800 text-white p-4 cursor-pointer" onclick="toggleSources()">
                    <h3 class="text-lg font-bold flex items-center justify-between">
                        <span class="flex items-center gap-2">📚 Sources Used</span>
                        <span id="sourcesToggle" class="text-sm bg-white/20 px-3 py-1 rounded-full">▼ Show</span>
                    </h3>
                </div>
                <div id="sources" class="hidden p-5 max-h-96 overflow-y-auto bg-gray-50">
                    <div id="sourcesList" class="space-y-3"></div>
                </div>
            </div>

            <!-- Disclaimer -->
            <div class="bg-amber-50 border border-amber-200 rounded-xl p-4 fade-in" style="animation-delay: 0.6s">
                <p class="text-amber-800 text-sm">
                    ⚠️ <strong>Clinical Disclaimer:</strong> This AI-generated analysis is based on CPG and should be used as a decision support tool only. Always exercise clinical judgment.
                </p>
            </div>
        </main>
    </div>

    <!-- Error Modal -->
    <div id="errorModal" class="hidden fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
        <div class="bg-white rounded-2xl p-6 max-w-md w-full">
            <div class="text-center">
                <span class="text-5xl mb-4 block">❌</span>
                <h3 class="text-xl font-bold text-gray-800 mb-2">Analysis Failed</h3>
                <p id="errorText" class="text-gray-600 mb-4"></p>
                <button onclick="closeError()" class="bg-blue-500 hover:bg-blue-600 text-white font-semibold py-2 px-6 rounded-lg">
                    Try Again
                </button>
            </div>
        </div>
    </div>

    <script>
        const BACKEND_URL = 'http://localhost:8058';
        let currentQuery = '';

        function setQuery(text) {
            document.getElementById('query').value = text;
        }

        function showPage(pageId) {
            ['queryPage', 'analyzingPage', 'resultsPage'].forEach(id => {
                document.getElementById(id).classList.add('hidden');
            });
            document.getElementById(pageId).classList.remove('hidden');
        }

        function goBack() {
            showPage('queryPage');
        }

        function closeError() {
            document.getElementById('errorModal').classList.add('hidden');
            showPage('queryPage');
        }

        function updateAnalysisStep(step) {
            const steps = ['step1', 'step2', 'step3'];
            const messages = [
                'Searching knowledge base...',
                'Analyzing clinical context...',
                'Generating recommendations...'
            ];

            steps.forEach((s, i) => {
                const el = document.getElementById(s);
                if (i < step) {
                    el.classList.remove('text-gray-400', 'text-gray-500', 'text-blue-400');
                    el.classList.add('text-green-400');
                } else if (i === step) {
                    el.classList.remove('text-gray-400', 'text-gray-500', 'text-green-400');
                    el.classList.add('text-blue-400');
                } else {
                    el.classList.remove('text-blue-400', 'text-green-400');
                    el.classList.add('text-gray-500');
                }
            });

            if (step < messages.length) {
                document.getElementById('analysisStatus').textContent = messages[step];
            }
        }

        function parseResponse(text) {
            const sections = { summary: '', followup: '', medications: '', nextsteps: '' };
            const parts = text.split(/##\\s+/);

            for (const part of parts) {
                const lower = part.toLowerCase();
                if (lower.startsWith('summary')) {
                    sections.summary = part.replace(/^summary\\s*/i, '').trim();
                } else if (lower.startsWith('follow-up') || lower.startsWith('followup') || lower.startsWith('follow up')) {
                    sections.followup = part.replace(/^follow[\\-\\s]?up\\s*(care\\s*)?plan\\s*/i, '').trim();
                } else if (lower.startsWith('medication')) {
                    sections.medications = part.replace(/^medications?\\s*/i, '').trim();
                } else if (lower.startsWith('next step')) {
                    sections.nextsteps = part.replace(/^next\\s*steps?\\s*/i, '').trim();
                }
            }

            if (!sections.summary && !sections.followup && !sections.medications && !sections.nextsteps) {
                sections.summary = text;
            }
            return sections;
        }

        function toggleSources() {
            const sourcesDiv = document.getElementById('sources');
            const toggleText = document.getElementById('sourcesToggle');
            if (sourcesDiv.classList.contains('hidden')) {
                sourcesDiv.classList.remove('hidden');
                toggleText.textContent = '▲ Hide';
            } else {
                sourcesDiv.classList.add('hidden');
                toggleText.textContent = '▼ Show';
            }
        }

        function renderSources(sources) {
            const sourcesList = document.getElementById('sourcesList');
            if (!sources || sources.length === 0) {
                sourcesList.innerHTML = '<p class="text-gray-500 italic">No sources retrieved.</p>';
                return;
            }

            sourcesList.innerHTML = sources.map(source => {
                const badge = source.tool === 'graph_search'
                    ? '<span class="bg-green-100 text-green-800 text-xs px-2 py-1 rounded-full">Knowledge Graph</span>'
                    : '<span class="bg-blue-100 text-blue-800 text-xs px-2 py-1 rounded-full">Vector Search</span>';
                return `
                    <div class="border rounded-xl p-4 bg-white shadow-sm">
                        <div class="flex items-center justify-between mb-2">
                            <span class="font-semibold text-gray-800">${source.document_title || 'Unknown'}</span>
                            <div class="flex items-center gap-2">
                                ${badge}
                                <span class="text-xs text-gray-500">Score: ${source.score}</span>
                            </div>
                        </div>
                        <p class="text-sm text-gray-600">${source.content}</p>
                    </div>
                `;
            }).join('');
        }

        async function startAnalysis() {
            currentQuery = document.getElementById('query').value.trim();
            if (!currentQuery) {
                alert('Please enter a clinical query');
                return;
            }

            // Show analyzing page
            document.getElementById('queryPreview').textContent = currentQuery;
            showPage('analyzingPage');
            updateAnalysisStep(0);

            // Simulate step progression
            setTimeout(() => updateAnalysisStep(1), 1500);
            setTimeout(() => updateAnalysisStep(2), 3000);

            try {
                const response = await fetch(`${BACKEND_URL}/chat`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message: currentQuery })
                });

                if (!response.ok) throw new Error(`Server error: ${response.status}`);

                const data = await response.json();
                const message = data.message || 'No response received';
                const sections = parseResponse(message);

                // Populate results
                document.getElementById('resultQueryText').textContent = currentQuery;
                document.getElementById('summary').innerHTML = marked.parse(sections.summary || 'No summary available.');
                document.getElementById('followup').innerHTML = marked.parse(sections.followup || 'No follow-up plan available.');
                document.getElementById('medications').innerHTML = marked.parse(sections.medications || 'No medication suggestions.');
                document.getElementById('nextsteps').innerHTML = marked.parse(sections.nextsteps || 'No next steps available.');
                renderSources(data.sources || []);

                // Reset sources toggle
                document.getElementById('sources').classList.add('hidden');
                document.getElementById('sourcesToggle').textContent = '▼ Show';

                // Show results page
                showPage('resultsPage');

            } catch (err) {
                document.getElementById('errorText').textContent = err.message;
                document.getElementById('errorModal').classList.remove('hidden');
            }
        }

        // Ctrl+Enter to submit
        document.getElementById('query').addEventListener('keydown', (e) => {
            if (e.ctrlKey && e.key === 'Enter') startAnalysis();
        });
    </script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def home():
    return HTML_PAGE

@app.get("/health")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8080)
