import { useCallback, useEffect, useRef, useState } from 'react';

// rPPG is mounted inside the main backend at /rppg.
// Override with VITE_RPPG_URL for other machines (e.g. ws://192.168.x.x:8058/rppg).
const RPPG_BASE    = import.meta.env.VITE_RPPG_URL || 'http://127.0.0.1:8058/rppg';
const RPPG_WS_URL  = RPPG_BASE.replace(/^http/, 'ws') + '/ws';
const RPPG_HTTP    = RPPG_BASE.replace(/^ws/, 'http');
const FRAME_INTERVAL = 100; // ms between frames sent (10 fps)

// Which physical camera to use. Accepts either a name fragment ("logi") or a
// numeric index ("1"). Matching by name is preferred — it survives reboots and
// re-plugging, where index order can change.
//
// The value is read from ?cam=… ONCE and persisted to localStorage. This is
// necessary because the app's router uses <Navigate replace/> redirects, which
// drop the query string before the hook runs — so we can't rely on the URL
// surviving. Set it once via ?cam=logi and it sticks across reloads/redirects.
// Priority: ?cam=… in URL → saved localStorage value → VITE_CAMERA → default.
const CAM_STORAGE_KEY = 'rppgCameraSelector';
function getCameraSelector() {
  const fromUrl = new URLSearchParams(window.location.search).get('cam');
  if (fromUrl !== null) {
    // '' explicitly clears the saved preference (back to browser default).
    try {
      if (fromUrl === '') localStorage.removeItem(CAM_STORAGE_KEY);
      else localStorage.setItem(CAM_STORAGE_KEY, fromUrl);
    } catch { /* ignore storage errors */ }
    if (fromUrl !== '') return fromUrl;
  }
  try {
    const saved = localStorage.getItem(CAM_STORAGE_KEY);
    if (saved) return saved;
  } catch { /* ignore */ }
  const fromEnv = import.meta.env.VITE_CAMERA;
  if (fromEnv !== undefined && fromEnv !== '') return fromEnv;
  return null;
}

// enumerateDevices() only returns real deviceIds + labels AFTER camera
// permission has been granted once. So we probe for permission, enumerate,
// then return constraints targeting the matched camera by deviceId.
async function buildVideoConstraints() {
  const sel = getCameraSelector();
  if (sel === null) {
    return { width: 640, height: 480, facingMode: 'user' };
  }
  const list = async () =>
    (await navigator.mediaDevices.enumerateDevices()).filter(d => d.kind === 'videoinput');

  let cams = await list();
  if (cams.length === 0 || !cams.some(c => c.deviceId) || !cams.some(c => c.label)) {
    try {
      const probe = await navigator.mediaDevices.getUserMedia({ video: true });
      probe.getTracks().forEach(t => t.stop());
      cams = await list();
    } catch (e) {
      console.warn('[rppg-camera] permission probe failed:', e);
    }
  }
  console.log('[rppg-camera] available video inputs:',
    cams.map((c, i) => `${i}: ${c.label || '(no label)'} [${c.deviceId ? 'id ok' : 'NO id'}]`));

  // Try name match first (case-insensitive substring), then fall back to index.
  let chosen = null;
  const asNumber = Number(sel);
  if (sel.trim() !== '' && !Number.isNaN(asNumber) && Number.isInteger(asNumber)) {
    chosen = cams[asNumber];
    console.log(`[rppg-camera] selector "${sel}" treated as index ${asNumber}`);
  } else {
    const needle = sel.toLowerCase();
    chosen = cams.find(c => (c.label || '').toLowerCase().includes(needle));
    console.log(`[rppg-camera] selector "${sel}" matched by label →`, chosen?.label || 'none');
  }

  if (!chosen || !chosen.deviceId) {
    console.warn(`[rppg-camera] selector "${sel}" unavailable (${cams.length} cams); using default`);
    return { width: 640, height: 480, facingMode: 'user' };
  }
  console.log(`[rppg-camera] using: ${chosen.label || chosen.deviceId}`);
  return { width: 640, height: 480, deviceId: { exact: chosen.deviceId } };
}

/**
 * Connects to the rPPG POC WebSocket, streams webcam frames, and returns
 * live vitals as they are computed by the rPPG server.
 * Supabase saving is NOT done here — it happens only on explicit "Apply" action.
 *
 * @param {object}  options
 * @param {boolean} options.autoStart  start immediately on mount (default true)
 * @returns {{ vitals, connected, status, start, stop }}
 */
export function useRPPGStream({ autoStart = true } = {}) {
  const [vitals,      setVitals]      = useState(null);
  const [connected,   setConnected]   = useState(false);
  const [mediaStream, setMediaStream] = useState(null);
  // 'idle' | 'requesting' | 'streaming' | 'error'
  const [status,    setStatus]    = useState('idle');

  const wsRef      = useRef(null);
  const videoRef   = useRef(null);
  const canvasRef  = useRef(null);
  const mediaRef   = useRef(null);
  const frameTimer = useRef(null);

  const stop = useCallback(() => {
    clearInterval(frameTimer.current);
    wsRef.current?.close();
    mediaRef.current?.getTracks().forEach(t => t.stop());
    wsRef.current    = null;
    mediaRef.current = null;
    setConnected(false);
    setMediaStream(null);
    setStatus('idle');
  }, []);

  const start = useCallback(async () => {
    stop();
    setStatus('requesting');

    // Reset server-side buffers so stale data from the previous patient doesn't bleed in.
    try { await fetch(`${RPPG_HTTP}/api/reset`, { method: 'POST' }); } catch { /* optional */ }

    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        video: await buildVideoConstraints(),
      });
    } catch {
      setStatus('error');
      return;
    }

    console.log('[rppg-camera] active track:', stream.getVideoTracks()[0]?.label);
    mediaRef.current = stream;
    setMediaStream(stream);

    const video = document.createElement('video');
    video.srcObject = stream;
    video.muted     = true;
    await video.play();
    videoRef.current = video;

    const canvas = document.createElement('canvas');
    canvas.width  = 640;
    canvas.height = 480;
    canvasRef.current = canvas;

    const ws = new WebSocket(RPPG_WS_URL);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      setStatus('streaming');

      frameTimer.current = setInterval(() => {
        if (ws.readyState !== WebSocket.OPEN) return;
        const ctx = canvasRef.current.getContext('2d');
        ctx.drawImage(videoRef.current, 0, 0, 640, 480);
        const b64 = canvasRef.current.toDataURL('image/jpeg', 0.7).split(',')[1];
        ws.send(JSON.stringify({ type: 'frame', data: b64 }));
      }, FRAME_INTERVAL);
    };

    ws.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data);
        if (data.type === 'ping') return;

        if (data.type === 'esp32') {
          // ESP32 direct push — merge into existing vitals, don't overwrite camera fields
          setVitals(prev => prev
            ? { ...prev, esp32: data }
            : { esp32: data, face_detected: false, buffer_pct: 0, quality: 0 }
          );
        } else {
          setVitals(data);
        }
      } catch { /* ignore */ }
    };

    ws.onclose = () => {
      clearInterval(frameTimer.current);
      setConnected(false);
      setStatus('idle');
    };

    ws.onerror = () => setStatus('error');
  }, [stop]);

  useEffect(() => {
    if (autoStart) start();
    return stop;
  }, []); // eslint-disable-line

  return { vitals, connected, status, start, stop, mediaStream };
}
