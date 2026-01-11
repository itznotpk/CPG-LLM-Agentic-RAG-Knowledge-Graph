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
</head>
<body class="bg-gray-100 min-h-screen">
    <header class="bg-blue-600 text-white py-4 shadow">
        <div class="container mx-auto px-4">
            <h1 class="text-2xl font-bold">🏥 CPG RAG Assistant</h1>
            <p class="text-blue-200 text-sm">Clinical Practice Guidelines - Malaysia</p>
        </div>
    </header>

    <main class="container mx-auto px-4 py-8 max-w-5xl">
        <!-- Query Form -->
        <div class="bg-white rounded-lg shadow p-6 mb-6">
            <h2 class="text-xl font-bold text-gray-800 mb-4">Enter Clinical Query</h2>
            <textarea id="query" rows="4"
                class="w-full border border-gray-300 rounded-lg p-3 mb-4 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                placeholder="e.g., 45-year-old male with erectile dysfunction, hypertension, and diabetes..."></textarea>
            <button onclick="sendQuery()" id="submitBtn"
                class="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 rounded-lg transition">
                Analyze Case
            </button>
        </div>

        <!-- Sample Cases -->
        <div class="bg-white rounded-lg shadow p-6 mb-6">
            <h3 class="font-bold text-gray-700 mb-3">Sample Cases (click to use)</h3>
            <div class="space-y-2">
                <button onclick="setQuery('45-year-old male with erectile dysfunction, hypertension, and diabetes')"
                    class="w-full text-left p-3 border rounded hover:bg-gray-50 text-sm">
                    <strong>ED with Comorbidities</strong> - 45yo male with HTN, DM
                </button>
                <button onclick="setQuery('28-year-old male with performance anxiety and mild erectile dysfunction')"
                    class="w-full text-left p-3 border rounded hover:bg-gray-50 text-sm">
                    <strong>Young Adult ED</strong> - 28yo male with anxiety
                </button>
            </div>
        </div>

        <!-- Results Section (hidden initially) -->
        <div id="results" class="hidden">
            <!-- Results Grid -->
            <div class="grid md:grid-cols-2 gap-6">
                <!-- Summary -->
                <div class="bg-white rounded-lg shadow overflow-hidden">
                    <div class="bg-blue-600 text-white p-4">
                        <h3 class="text-lg font-bold">📋 Summary</h3>
                    </div>
                    <div id="summary" class="p-4 prose prose-sm max-w-none text-gray-700"></div>
                </div>

                <!-- Follow-up Care Plan -->
                <div class="bg-white rounded-lg shadow overflow-hidden">
                    <div class="bg-green-600 text-white p-4">
                        <h3 class="text-lg font-bold">📅 Follow-up Care Plan</h3>
                    </div>
                    <div id="followup" class="p-4 prose prose-sm max-w-none text-gray-700"></div>
                </div>

                <!-- Medications -->
                <div class="bg-white rounded-lg shadow overflow-hidden">
                    <div class="bg-purple-600 text-white p-4">
                        <h3 class="text-lg font-bold">💊 Medications</h3>
                    </div>
                    <div id="medications" class="p-4 prose prose-sm max-w-none text-gray-700"></div>
                </div>

                <!-- Next Steps -->
                <div class="bg-white rounded-lg shadow overflow-hidden">
                    <div class="bg-orange-600 text-white p-4">
                        <h3 class="text-lg font-bold">➡️ Next Steps</h3>
                    </div>
                    <div id="nextsteps" class="p-4 prose prose-sm max-w-none text-gray-700"></div>
                </div>
            </div>

            <!-- Sources Section -->
            <div class="bg-white rounded-lg shadow overflow-hidden mt-6">
                <div class="bg-gray-700 text-white p-4 cursor-pointer" onclick="toggleSources()">
                    <h3 class="text-lg font-bold flex items-center justify-between">
                        <span>📚 Sources Used</span>
                        <span id="sourcesToggle" class="text-sm">▼ Show</span>
                    </h3>
                </div>
                <div id="sources" class="hidden p-4 max-h-96 overflow-y-auto">
                    <div id="sourcesList" class="space-y-3"></div>
                </div>
            </div>

            <!-- Disclaimer -->
            <div class="bg-yellow-50 border border-yellow-200 rounded-lg p-4 mt-6">
                <p class="text-yellow-800 text-sm">
                    ⚠️ <strong>Clinical Disclaimer:</strong> This AI-generated analysis is based on CPG and should be used as a decision support tool only. Always exercise clinical judgment.
                </p>
            </div>
        </div>

        <!-- Loading indicator -->
        <div id="loading" class="hidden text-center py-8">
            <div class="inline-block animate-spin rounded-full h-8 w-8 border-4 border-blue-600 border-t-transparent"></div>
            <p class="mt-2 text-gray-600">Analyzing...</p>
        </div>

        <!-- Error display -->
        <div id="error" class="hidden bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-6"></div>
    </main>

    <script>
        const BACKEND_URL = 'http://localhost:8058';

        function setQuery(text) {
            document.getElementById('query').value = text;
        }

        function parseResponse(text) {
            // Parse the structured response into sections
            const sections = {
                summary: '',
                followup: '',
                medications: '',
                nextsteps: ''
            };

            // Split by ## headers
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

            // If no sections found, put everything in summary
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
                sourcesList.innerHTML = '<p class="text-gray-500 italic">No sources retrieved for this query.</p>';
                return;
            }

            const html = sources.map((source, index) => {
                const toolBadge = source.tool === 'graph_search'
                    ? '<span class="bg-green-100 text-green-800 text-xs px-2 py-1 rounded">Knowledge Graph</span>'
                    : '<span class="bg-blue-100 text-blue-800 text-xs px-2 py-1 rounded">Vector Search</span>';

                return `
                    <div class="border rounded-lg p-3 bg-gray-50">
                        <div class="flex items-center justify-between mb-2">
                            <span class="font-semibold text-sm text-gray-700">${source.document_title || 'Unknown'}</span>
                            <div class="flex items-center gap-2">
                                ${toolBadge}
                                <span class="text-xs text-gray-500">Score: ${source.score}</span>
                            </div>
                        </div>
                        <p class="text-sm text-gray-600">${source.content}</p>
                    </div>
                `;
            }).join('');

            sourcesList.innerHTML = html;
        }

        async function sendQuery() {
            const query = document.getElementById('query').value.trim();
            if (!query) {
                alert('Please enter a clinical query');
                return;
            }

            // Show loading, hide results/error
            document.getElementById('loading').classList.remove('hidden');
            document.getElementById('results').classList.add('hidden');
            document.getElementById('error').classList.add('hidden');
            document.getElementById('submitBtn').disabled = true;
            // Reset sources toggle
            document.getElementById('sources').classList.add('hidden');
            document.getElementById('sourcesToggle').textContent = '▼ Show';

            try {
                const response = await fetch(`${BACKEND_URL}/chat`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message: query })
                });

                if (!response.ok) {
                    throw new Error(`Server error: ${response.status}`);
                }

                const data = await response.json();
                const message = data.message || 'No response received';

                // Parse and display sections
                const sections = parseResponse(message);

                document.getElementById('summary').innerHTML = marked.parse(sections.summary || 'No summary available.');
                document.getElementById('followup').innerHTML = marked.parse(sections.followup || 'No follow-up plan available.');
                document.getElementById('medications').innerHTML = marked.parse(sections.medications || 'No medication suggestions available.');
                document.getElementById('nextsteps').innerHTML = marked.parse(sections.nextsteps || 'No next steps available.');

                // Display sources
                renderSources(data.sources || []);

                document.getElementById('results').classList.remove('hidden');

            } catch (err) {
                document.getElementById('error').textContent = `Error: ${err.message}`;
                document.getElementById('error').classList.remove('hidden');
            } finally {
                document.getElementById('loading').classList.add('hidden');
                document.getElementById('submitBtn').disabled = false;
            }
        }

        // Allow Ctrl+Enter to submit
        document.getElementById('query').addEventListener('keydown', (e) => {
            if (e.ctrlKey && e.key === 'Enter') sendQuery();
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
