const BASE = import.meta.env.VITE_CLINICAL_API_URL || 'http://localhost:8058';

/**
 * Stream the clinical pipeline for a pre-formed caseBody object.
 * @param {Object}   caseBody        - already in PatientCase shape from sampleCases.js
 * @param {Function} onStageUpdate   - called with each stage_update payload
 * @param {Function} onThinkingChunk - called with each thinking_delta payload
 * @param {Function} onSubStep       - called with each sub_step payload (optional)
 * @returns {Promise<ClinicalPlanResponse>}  resolves with the final_result payload
 */
export async function streamDetectivePlan(caseBody, onStageUpdate, onThinkingChunk, onSubStep) {
  const response = await fetch(`${BASE}/clinical/plan/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ case: caseBody }),
  });

  if (!response.ok) {
    const text = await response.text().catch(() => response.statusText);
    throw new Error(`API error ${response.status}: ${text}`);
  }

  return new Promise((resolve, reject) => {
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    const pump = async () => {
      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) {
            reject(new Error('Stream ended without final_result'));
            return;
          }
          buffer += decoder.decode(value, { stream: true });

          const frames = buffer.split('\n\n');
          buffer = frames.pop();

          for (const frame of frames) {
            if (!frame.trim()) continue;

            let eventType = 'message';
            let dataStr = '';
            for (const line of frame.split('\n')) {
              if (line.startsWith('event: '))      eventType = line.slice(7).trim();
              else if (line.startsWith('data: '))  dataStr   = line.slice(6).trim();
            }
            if (!dataStr) continue;

            let payload;
            try { payload = JSON.parse(dataStr); } catch { continue; }

            if      (eventType === 'stage_update'   && onStageUpdate)    onStageUpdate(payload);
            else if (eventType === 'thinking_delta' && onThinkingChunk)  onThinkingChunk(payload);
            else if (eventType === 'sub_step'       && onSubStep)        onSubStep(payload);
            else if (eventType === 'final_result')                        resolve(payload);
            else if (eventType === 'error')                               reject(new Error(payload.detail || 'Pipeline error'));
            else if (eventType === 'done')                                return;
          }
        }
      } catch (err) {
        reject(err);
      }
    };

    pump();
  });
}
