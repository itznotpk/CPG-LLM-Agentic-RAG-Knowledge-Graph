import { useCallback, useEffect, useRef, useState } from 'react';

// rPPG backend runs separately on port 8090.
// Override with VITE_RPPG_URL for other machines (e.g. ws://192.168.x.x:8090).
const RPPG_WS_URL = (import.meta.env.VITE_RPPG_URL || 'ws://127.0.0.1:8090') + '/ws';
const FRAME_INTERVAL = 100; // ms between frames sent (10 fps)

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

    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 640, height: 480, facingMode: 'user' },
      });
    } catch {
      setStatus('error');
      return;
    }

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
