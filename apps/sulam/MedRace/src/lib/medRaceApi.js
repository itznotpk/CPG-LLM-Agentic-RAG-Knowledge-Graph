const BASE = import.meta.env.VITE_CLINICAL_API_URL || 'http://localhost:8058';

export async function streamAIAnswer(question, onText, onTools) {
  const response = await fetch(`${BASE}/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message: question,
      session_id: null,
      user_id: 'medrace_player',
      search_type: 'hybrid',
    }),
  });

  if (!response.ok) {
    const text = await response.text().catch(() => response.statusText);
    throw new Error(`API error ${response.status}: ${text}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop();
    for (const line of lines) {
      if (!line.startsWith('data: ')) continue;
      try {
        const data = JSON.parse(line.slice(6));
        if (data.type === 'text')  onText(data.content || '');
        if (data.type === 'tools') onTools(data.tools || []);
        if (data.type === 'end')   return;
        if (data.type === 'error') throw new Error(data.content || 'Stream error');
      } catch (e) {
        if (e.message !== 'Stream error') continue;
        throw e;
      }
    }
  }
}
