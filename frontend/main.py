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
        .sidebar-open { transform: translateX(0); }
        .sidebar-closed { transform: translateX(-100%); }
        .history-item:hover { background: rgba(255,255,255,0.1); }
    </style>
</head>
<body class="bg-gradient-to-br from-slate-900 via-blue-900 to-slate-900 min-h-screen">

    <!-- Chat History Sidebar -->
    <div id="historySidebar" class="fixed left-0 top-0 h-full w-80 bg-slate-900/95 backdrop-blur-lg border-r border-white/10 z-50 transition-transform duration-300 sidebar-closed">
        <div class="flex flex-col h-full">
            <!-- Sidebar Header -->
            <div class="p-4 border-b border-white/10 flex items-center justify-between">
                <h2 class="text-lg font-bold text-white flex items-center gap-2">
                    <span>📜</span> Chat History
                </h2>
                <button onclick="toggleSidebar()" class="text-gray-400 hover:text-white text-xl">&times;</button>
            </div>

            <!-- History List -->
            <div id="historyList" class="flex-1 overflow-y-auto p-3 space-y-2">
                <p class="text-gray-500 text-sm text-center py-8">No history yet</p>
            </div>

            <!-- Clear History -->
            <div class="p-3 border-t border-white/10">
                <button onclick="clearHistory()" class="w-full bg-red-500/20 hover:bg-red-500/30 text-red-400 py-2 rounded-lg text-sm transition">
                    🗑️ Clear History
                </button>
            </div>
        </div>
    </div>

    <!-- Sidebar Toggle Button (always visible) -->
    <button onclick="toggleSidebar()" id="sidebarToggle" class="fixed left-4 top-4 z-40 bg-white/10 hover:bg-white/20 backdrop-blur p-3 rounded-xl border border-white/20 transition">
        <span class="text-white text-lg">📜</span>
        <span id="historyBadge" class="hidden absolute -top-1 -right-1 bg-blue-500 text-white text-xs w-5 h-5 rounded-full flex items-center justify-center">0</span>
    </button>

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

                <!-- Test Cases Dropdown -->
                <div class="mt-6">
                    <p class="text-gray-400 text-sm mb-3 text-center">Or select a test case:</p>
                    <div class="relative">
                        <button onclick="toggleTestCaseDropdown()" id="testCaseBtn"
                            class="w-full bg-white/10 hover:bg-white/15 border border-white/20 rounded-xl p-4 text-left transition flex items-center justify-between">
                            <div>
                                <p class="text-white font-medium">🧪 Select Test Case</p>
                                <p class="text-gray-400 text-sm">15 CPG-validated clinical scenarios</p>
                            </div>
                            <span class="text-white text-xl" id="dropdownArrow">▼</span>
                        </button>

                        <!-- Dropdown Panel -->
                        <div id="testCaseDropdown" class="hidden absolute z-50 w-full mt-2 bg-slate-800/95 backdrop-blur-lg border border-white/20 rounded-xl shadow-2xl max-h-96 overflow-y-auto">
                            <div class="p-2">
                                <!-- Difficulty Filter -->
                                <div class="flex gap-2 p-2 border-b border-white/10 mb-2">
                                    <button onclick="filterTestCases('all')" class="filter-btn active px-3 py-1 rounded-lg text-xs font-medium bg-blue-500 text-white">All</button>
                                    <button onclick="filterTestCases('easy')" class="filter-btn px-3 py-1 rounded-lg text-xs font-medium bg-white/10 text-gray-300 hover:bg-white/20">Easy</button>
                                    <button onclick="filterTestCases('medium')" class="filter-btn px-3 py-1 rounded-lg text-xs font-medium bg-white/10 text-gray-300 hover:bg-white/20">Medium</button>
                                    <button onclick="filterTestCases('hard')" class="filter-btn px-3 py-1 rounded-lg text-xs font-medium bg-white/10 text-gray-300 hover:bg-white/20">Hard</button>
                                </div>

                                <!-- Test Cases List -->
                                <div id="testCasesList"></div>
                            </div>
                        </div>
                    </div>

                    <!-- Quick Sample Buttons -->
                    <div class="grid grid-cols-1 md:grid-cols-3 gap-3 mt-4">
                        <button onclick="setQuery('45-year-old male with erectile dysfunction, hypertension, and diabetes. Currently on metformin and amlodipine.')"
                            class="bg-white/5 hover:bg-white/10 border border-white/10 rounded-xl p-3 text-left transition">
                            <p class="text-white font-medium text-sm">🩺 ED + Comorbidities</p>
                        </button>
                        <button onclick="setQuery('68-year-old male with severe ED, diabetes, stable angina, on nitroglycerin PRN. IIEF-5 score 6.')"
                            class="bg-white/5 hover:bg-white/10 border border-white/10 rounded-xl p-3 text-left transition">
                            <p class="text-white font-medium text-sm">⚠️ Nitrate User (Hard)</p>
                        </button>
                        <button onclick="setQuery('62-year-old male with severe ED post radical prostatectomy for prostate cancer 6 months ago.')"
                            class="bg-white/5 hover:bg-white/10 border border-white/10 rounded-xl p-3 text-left transition">
                            <p class="text-white font-medium text-sm">🏥 Post-Prostatectomy</p>
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
                    <span id="analysisIcon" class="text-5xl">🔍</span>
                </div>
            </div>

            <!-- Status Text -->
            <h2 class="text-3xl font-bold text-white mb-2">Analyzing Your Case</h2>
            <p id="analysisStatus" class="text-blue-300 text-lg mb-2 h-7 transition-all">Initializing AI agent...</p>
            <p id="analysisDetail" class="text-gray-400 text-sm mb-8 h-5 italic"></p>

            <!-- Progress Steps -->
            <div class="max-w-md w-full space-y-3">
                <div id="step1" class="flex items-center gap-3 text-gray-400 transition-all">
                    <div class="w-8 h-8 rounded-full border-2 border-current flex items-center justify-center">
                        <span id="step1Icon" class="text-sm">1</span>
                    </div>
                    <div>
                        <span class="font-medium">Searching Knowledge Base</span>
                        <p id="step1Detail" class="text-xs text-gray-500"></p>
                    </div>
                </div>
                <div id="step2" class="flex items-center gap-3 text-gray-500 transition-all">
                    <div class="w-8 h-8 rounded-full border-2 border-current flex items-center justify-center">
                        <span id="step2Icon" class="text-sm">2</span>
                    </div>
                    <div>
                        <span class="font-medium">Analyzing Clinical Context</span>
                        <p id="step2Detail" class="text-xs text-gray-500"></p>
                    </div>
                </div>
                <div id="step3" class="flex items-center gap-3 text-gray-500 transition-all">
                    <div class="w-8 h-8 rounded-full border-2 border-current flex items-center justify-center">
                        <span id="step3Icon" class="text-sm">3</span>
                    </div>
                    <div>
                        <span class="font-medium">Generating Recommendations</span>
                        <p id="step3Detail" class="text-xs text-gray-500"></p>
                    </div>
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

            <!-- Related Questions -->
            <div class="bg-white rounded-2xl shadow-xl overflow-hidden fade-in mb-6" style="animation-delay: 0.55s">
                <div class="bg-gradient-to-r from-cyan-500 to-blue-500 text-white p-4">
                    <h3 class="text-lg font-bold flex items-center gap-2">💡 Related Questions</h3>
                </div>
                <div id="relatedQuestions" class="p-5">
                    <div class="grid gap-3" id="relatedQuestionsGrid">
                        <!-- Will be populated dynamically -->
                    </div>
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
        let chatHistory = JSON.parse(localStorage.getItem('cpgChatHistory') || '[]');
        let currentFilter = 'all';

        // CPG-Validated Test Cases (Generated from ED CPG Guidelines)
        const TEST_CASES = [
            { id: "TC001", title: "Mild-Moderate ED + Hypertension", difficulty: "easy", focus: "pde5i_selection", icon: "💊",
              query: "52-year-old male with mild-moderate ED (IIEF-5: 14), hypertension controlled with Amlodipine 5mg. BP 130/80, BMI 28. What is the recommended first-line treatment?" },
            { id: "TC002", title: "Severe ED + Nitrate Use", difficulty: "hard", focus: "cardiac_risk", icon: "⚠️",
              query: "68-year-old male with severe ED (IIEF-5: 6), Type 2 diabetes, stable angina on Nitroglycerin PRN. Also on Metformin, Atorvastatin, Aspirin. BP 140/90, BMI 32. What are safe treatment options?" },
            { id: "TC003", title: "Psychogenic ED + Anxiety", difficulty: "medium", focus: "psychogenic_ed", icon: "😰",
              query: "45-year-old male with mild-moderate ED (IIEF-5: 15), anxiety, relationship problems, on Sertraline 50mg. BP 120/80, BMI 24. What is appropriate management for ED related to psychological factors?" },
            { id: "TC004", title: "Post-Prostatectomy ED", difficulty: "medium", focus: "post_prostatectomy", icon: "🏥",
              query: "62-year-old male with severe ED (IIEF-5: 7) following radical prostatectomy 6 months ago. BP 130/85, BMI 27. What is recommended treatment approach?" },
            { id: "TC005", title: "Vasculogenic ED Post-Trauma", difficulty: "medium", focus: "vasculogenic_ed", icon: "🩻",
              query: "38-year-old male with moderate ED (IIEF-5: 10) of sudden onset after pelvic fracture 3 months ago. BP 125/80, BMI 25. What diagnostic tests are indicated?" },
            { id: "TC006", title: "Sildenafil Treatment Failure", difficulty: "medium", focus: "treatment_failure", icon: "🔄",
              query: "70-year-old male with moderate ED (IIEF-5: 9), hypertension, hyperlipidemia. Currently on Sildenafil 100mg with no improvement. What are next steps?" },
            { id: "TC007", title: "New-Onset ED + CV Risk", difficulty: "easy", focus: "cv_risk_assessment", icon: "❤️",
              query: "58-year-old male smoker with new-onset mild ED (IIEF-5: 19). No known medical history. BP 145/90, BMI 30. What initial lab tests are recommended?" },
            { id: "TC008", title: "ED + Premature Ejaculation", difficulty: "medium", focus: "psychological_assessment", icon: "🧠",
              query: "42-year-old male with mild ED (IIEF-5: 20) and premature ejaculation. No medical history. BP 120/80, BMI 23. How should coexisting ED and PE be managed?" },
            { id: "TC009", title: "ED on Warfarin", difficulty: "medium", focus: "cardiac_risk", icon: "💉",
              query: "75-year-old male with severe ED (IIEF-5: 6), atrial fibrillation on Warfarin and Digoxin. BP 130/80, irregular HR 75. What ED treatments are safe?" },
            { id: "TC010", title: "ED After Alpha-Blocker", difficulty: "easy", focus: "pde5i_selection", icon: "💊",
              query: "60-year-old male with mild ED (IIEF-5: 18) that started after beginning Tamsulosin for BPH. BP 125/75, BMI 27. How should ED be treated with concurrent alpha-blocker?" },
            { id: "TC011", title: "Diabetic + Obese ED", difficulty: "medium", focus: "diabetes", icon: "🍬",
              query: "55-year-old male with moderate ED (IIEF-5: 11) and decreased libido, Type 2 diabetes on Metformin, obesity. BP 135/85, BMI 33. What are appropriate management steps?" },
            { id: "TC012", title: "Tadalafil Treatment Failure", difficulty: "medium", focus: "treatment_failure", icon: "🔄",
              query: "48-year-old male with moderate ED (IIEF-5: 10) despite using Tadalafil 20mg PRN. No other medical history. BP 120/80, BMI 26. What are next steps?" },
            { id: "TC013", title: "Young Male + Low Desire", difficulty: "medium", focus: "psychological_assessment", icon: "🧪",
              query: "28-year-old male with mild ED (IIEF-5: 21) and decreased sexual desire. No medical history. BP 110/70, BMI 22. What evaluation is necessary?" },
            { id: "TC014", title: "ED + Recent MI", difficulty: "hard", focus: "cardiac_risk", icon: "🚨",
              query: "65-year-old male with moderate ED (IIEF-5: 10), had myocardial infarction 3 weeks ago. On Aspirin, Metoprolol. BP 120/80, HR 60. What is appropriate ED management?" },
            { id: "TC015", title: "ED + Peyronie's Disease", difficulty: "medium", focus: "physical_exam", icon: "🔍",
              query: "50-year-old male with mild-moderate ED (IIEF-5: 13) and Peyronie's disease. BP 120/80, BMI 25. How should ED be managed with Peyronie's?" }
        ];

        // Initialize on load
        document.addEventListener('DOMContentLoaded', () => {
            renderHistoryList();
            updateHistoryBadge();
            renderTestCases();
        });

        function setQuery(text) {
            document.getElementById('query').value = text;
            // Close dropdown if open
            document.getElementById('testCaseDropdown').classList.add('hidden');
            document.getElementById('dropdownArrow').textContent = '▼';
        }

        // ============ TEST CASES DROPDOWN ============
        function toggleTestCaseDropdown() {
            const dropdown = document.getElementById('testCaseDropdown');
            const arrow = document.getElementById('dropdownArrow');
            if (dropdown.classList.contains('hidden')) {
                dropdown.classList.remove('hidden');
                arrow.textContent = '▲';
            } else {
                dropdown.classList.add('hidden');
                arrow.textContent = '▼';
            }
        }

        function filterTestCases(difficulty) {
            currentFilter = difficulty;
            // Update button styles
            document.querySelectorAll('.filter-btn').forEach(btn => {
                btn.classList.remove('active', 'bg-blue-500', 'text-white');
                btn.classList.add('bg-white/10', 'text-gray-300');
            });
            event.target.classList.add('active', 'bg-blue-500', 'text-white');
            event.target.classList.remove('bg-white/10', 'text-gray-300');
            renderTestCases();
        }

        function renderTestCases() {
            const filtered = currentFilter === 'all'
                ? TEST_CASES
                : TEST_CASES.filter(tc => tc.difficulty === currentFilter);

            const diffColors = { easy: 'bg-green-500/20 text-green-300', medium: 'bg-yellow-500/20 text-yellow-300', hard: 'bg-red-500/20 text-red-300' };

            document.getElementById('testCasesList').innerHTML = filtered.map(tc => `
                <button onclick="selectTestCase('${tc.id}')"
                    class="w-full text-left p-3 hover:bg-white/10 rounded-lg transition border-b border-white/5 last:border-0">
                    <div class="flex items-start gap-3">
                        <span class="text-2xl">${tc.icon}</span>
                        <div class="flex-1">
                            <div class="flex items-center gap-2">
                                <span class="text-white font-medium">${tc.id}: ${tc.title}</span>
                                <span class="px-2 py-0.5 rounded text-xs ${diffColors[tc.difficulty]}">${tc.difficulty}</span>
                            </div>
                            <p class="text-gray-400 text-sm mt-1 line-clamp-2">${tc.query.substring(0, 100)}...</p>
                        </div>
                    </div>
                </button>
            `).join('');
        }

        function selectTestCase(id) {
            const tc = TEST_CASES.find(t => t.id === id);
            if (tc) {
                setQuery(tc.query);
            }
        }

        // Close dropdown when clicking outside
        document.addEventListener('click', (e) => {
            const dropdown = document.getElementById('testCaseDropdown');
            const btn = document.getElementById('testCaseBtn');
            if (dropdown && !dropdown.contains(e.target) && !btn.contains(e.target)) {
                dropdown.classList.add('hidden');
                document.getElementById('dropdownArrow').textContent = '▼';
            }
        });

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

        // ============ SIDEBAR FUNCTIONS ============
        function toggleSidebar() {
            const sidebar = document.getElementById('historySidebar');
            if (sidebar.classList.contains('sidebar-closed')) {
                sidebar.classList.remove('sidebar-closed');
                sidebar.classList.add('sidebar-open');
            } else {
                sidebar.classList.remove('sidebar-open');
                sidebar.classList.add('sidebar-closed');
            }
        }

        function saveToHistory(query, summary) {
            const entry = {
                id: Date.now(),
                query: query,
                summary: summary.substring(0, 100) + (summary.length > 100 ? '...' : ''),
                timestamp: new Date().toLocaleString()
            };
            chatHistory.unshift(entry);
            if (chatHistory.length > 20) chatHistory.pop(); // Keep last 20
            localStorage.setItem('cpgChatHistory', JSON.stringify(chatHistory));
            renderHistoryList();
            updateHistoryBadge();
        }

        function renderHistoryList() {
            const list = document.getElementById('historyList');
            if (chatHistory.length === 0) {
                list.innerHTML = '<p class="text-gray-500 text-sm text-center py-8">No history yet</p>';
                return;
            }
            list.innerHTML = chatHistory.map(item => `
                <div class="history-item p-3 rounded-lg cursor-pointer border border-white/5 transition" onclick="loadFromHistory('${item.query.replace(/'/g, "\\'")}')">
                    <p class="text-white text-sm font-medium truncate">${item.query}</p>
                    <p class="text-gray-400 text-xs mt-1 truncate">${item.summary}</p>
                    <p class="text-gray-500 text-xs mt-1">${item.timestamp}</p>
                </div>
            `).join('');
        }

        function loadFromHistory(query) {
            document.getElementById('query').value = query;
            toggleSidebar();
            showPage('queryPage');
        }

        function clearHistory() {
            if (confirm('Clear all chat history?')) {
                chatHistory = [];
                localStorage.removeItem('cpgChatHistory');
                renderHistoryList();
                updateHistoryBadge();
            }
        }

        function updateHistoryBadge() {
            const badge = document.getElementById('historyBadge');
            if (chatHistory.length > 0) {
                badge.textContent = chatHistory.length;
                badge.classList.remove('hidden');
            } else {
                badge.classList.add('hidden');
            }
        }

        // ============ RELATED QUESTIONS ============
        function generateRelatedQuestions(query, response) {
            // Generate contextual follow-up questions based on the query
            const relatedQuestions = [];
            const queryLower = query.toLowerCase();

            // Base questions that are always relevant
            const baseQuestions = [
                "What are the contraindications I should be aware of?",
                "What lifestyle modifications should be recommended?",
                "When should the patient be referred to a specialist?"
            ];

            // Condition-specific questions
            if (queryLower.includes('diabetes') || queryLower.includes('dm')) {
                relatedQuestions.push("How does diabetes affect ED treatment choice?");
                relatedQuestions.push("What is the HbA1c target for ED patients with diabetes?");
            }
            if (queryLower.includes('hypertension') || queryLower.includes('htn') || queryLower.includes('blood pressure')) {
                relatedQuestions.push("Which antihypertensives are preferred in ED patients?");
                relatedQuestions.push("Can I use PDE5 inhibitors with antihypertensive medications?");
            }
            if (queryLower.includes('cardiac') || queryLower.includes('heart') || queryLower.includes('cad') || queryLower.includes('coronary')) {
                relatedQuestions.push("What cardiac workup is needed before starting ED treatment?");
                relatedQuestions.push("What is the Princeton III algorithm for cardiac risk?");
            }
            if (queryLower.includes('pde5') || queryLower.includes('sildenafil') || queryLower.includes('tadalafil')) {
                relatedQuestions.push("What are the dosing recommendations for PDE5 inhibitors?");
                relatedQuestions.push("What if the patient fails first-line PDE5 inhibitor therapy?");
            }
            if (queryLower.includes('testosterone') || queryLower.includes('hypogonadism') || queryLower.includes('low t')) {
                relatedQuestions.push("When should testosterone replacement be considered?");
                relatedQuestions.push("What monitoring is needed for testosterone therapy?");
            }
            if (queryLower.includes('anxiety') || queryLower.includes('psychological') || queryLower.includes('depression')) {
                relatedQuestions.push("When should psychosexual therapy be recommended?");
                relatedQuestions.push("How do SSRIs affect erectile function?");
            }
            if (queryLower.includes('prostatectomy') || queryLower.includes('prostate') || queryLower.includes('surgery')) {
                relatedQuestions.push("What is penile rehabilitation after prostatectomy?");
                relatedQuestions.push("What are second-line options for post-surgical ED?");
            }

            // Add base questions if we don't have enough
            while (relatedQuestions.length < 4 && baseQuestions.length > 0) {
                relatedQuestions.push(baseQuestions.shift());
            }

            // Limit to 4 questions
            return relatedQuestions.slice(0, 4);
        }

        function renderRelatedQuestions(questions) {
            const grid = document.getElementById('relatedQuestionsGrid');
            grid.innerHTML = questions.map(q => `
                <button onclick="askRelatedQuestion('${q.replace(/'/g, "\\'")}')"
                    class="text-left p-3 bg-gray-50 hover:bg-blue-50 border border-gray-200 hover:border-blue-300 rounded-xl transition group">
                    <span class="text-gray-600 group-hover:text-blue-600 text-sm flex items-center gap-2">
                        <span class="text-blue-500">→</span> ${q}
                    </span>
                </button>
            `).join('');
        }

        function askRelatedQuestion(question) {
            document.getElementById('query').value = question;
            showPage('queryPage');
            startAnalysis();
        }

        // Dynamic status messages for each step
        const analysisMessages = {
            step1: {
                icon: '🔍',
                status: 'Searching Knowledge Base',
                details: [
                    'Querying vector database for relevant CPG sections...',
                    'Finding clinical guidelines for erectile dysfunction...',
                    'Searching treatment algorithms and protocols...',
                    'Retrieving medication recommendations...',
                    'Scanning diagnostic criteria and assessments...',
                    'Looking up contraindications and precautions...'
                ],
                stepDetail: 'Vector search + Knowledge graph'
            },
            step2: {
                icon: '🧠',
                status: 'Analyzing Clinical Context',
                details: [
                    'Evaluating patient risk factors...',
                    'Cross-referencing comorbidities with guidelines...',
                    'Checking drug interactions and contraindications...',
                    'Assessing cardiovascular risk profile...',
                    'Matching patient profile to treatment pathways...',
                    'Reviewing lifestyle factors and history...'
                ],
                stepDetail: 'AI reasoning with CPG context'
            },
            step3: {
                icon: '📋',
                status: 'Generating Recommendations',
                details: [
                    'Formulating personalized treatment plan...',
                    'Prioritizing evidence-based interventions...',
                    'Creating follow-up care schedule...',
                    'Compiling medication options with dosing...',
                    'Drafting clinical summary and next steps...',
                    'Finalizing recommendations...'
                ],
                stepDetail: 'Structured response generation'
            }
        };

        let detailInterval = null;

        function updateAnalysisStep(step) {
            const steps = ['step1', 'step2', 'step3'];
            const stepKeys = ['step1', 'step2', 'step3'];

            // Clear previous interval
            if (detailInterval) clearInterval(detailInterval);

            steps.forEach((s, i) => {
                const el = document.getElementById(s);
                const iconEl = document.getElementById(s + 'Icon');
                const detailEl = document.getElementById(s + 'Detail');

                if (i < step) {
                    el.classList.remove('text-gray-400', 'text-gray-500', 'text-blue-400');
                    el.classList.add('text-green-400');
                    iconEl.textContent = '✓';
                    detailEl.textContent = 'Complete';
                } else if (i === step) {
                    el.classList.remove('text-gray-400', 'text-gray-500', 'text-green-400');
                    el.classList.add('text-blue-400');
                    iconEl.textContent = '⟳';
                    detailEl.textContent = analysisMessages[stepKeys[i]].stepDetail;
                } else {
                    el.classList.remove('text-blue-400', 'text-green-400');
                    el.classList.add('text-gray-500');
                    iconEl.textContent = (i + 1).toString();
                    detailEl.textContent = '';
                }
            });

            if (step < stepKeys.length) {
                const currentStep = analysisMessages[stepKeys[step]];
                document.getElementById('analysisIcon').textContent = currentStep.icon;
                document.getElementById('analysisStatus').textContent = currentStep.status;

                // Cycle through detail messages
                let detailIndex = 0;
                document.getElementById('analysisDetail').textContent = currentStep.details[0];

                detailInterval = setInterval(() => {
                    detailIndex = (detailIndex + 1) % currentStep.details.length;
                    document.getElementById('analysisDetail').textContent = currentStep.details[detailIndex];
                }, 2000);
            }
        }

        function stopDetailAnimation() {
            if (detailInterval) {
                clearInterval(detailInterval);
                detailInterval = null;
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

            // Reset step icons before starting
            ['step1', 'step2', 'step3'].forEach((s, i) => {
                document.getElementById(s + 'Icon').textContent = (i + 1).toString();
                document.getElementById(s + 'Detail').textContent = '';
            });

            // Show analyzing page
            document.getElementById('queryPreview').textContent = currentQuery;
            showPage('analyzingPage');
            updateAnalysisStep(0);

            // Simulate step progression based on typical response time
            const step1Timer = setTimeout(() => updateAnalysisStep(1), 3000);
            const step2Timer = setTimeout(() => updateAnalysisStep(2), 7000);

            try {
                const response = await fetch(`${BACKEND_URL}/chat`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message: currentQuery })
                });

                // Clear timers and stop animation
                clearTimeout(step1Timer);
                clearTimeout(step2Timer);
                stopDetailAnimation();

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

                // Save to history
                saveToHistory(currentQuery, sections.summary || message.substring(0, 100));

                // Generate and render related questions
                const relatedQs = generateRelatedQuestions(currentQuery, message);
                renderRelatedQuestions(relatedQs);

                // Reset sources toggle
                document.getElementById('sources').classList.add('hidden');
                document.getElementById('sourcesToggle').textContent = '▼ Show';

                // Show results page
                showPage('resultsPage');

            } catch (err) {
                clearTimeout(step1Timer);
                clearTimeout(step2Timer);
                stopDetailAnimation();
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
