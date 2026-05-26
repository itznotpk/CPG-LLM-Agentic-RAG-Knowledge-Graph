import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Mic, MicOff, Volume2, VolumeX, Square, Play, Pause, Loader2, Cloud, CloudOff } from 'lucide-react';
import { Button, Badge } from '../shared';
import { useTheme } from '../../context/ThemeContext';

// Browser-native Web Speech API (fallback)
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
const speechSynthesis = window.speechSynthesis;

const CLINICAL_API_BASE = import.meta.env.VITE_CLINICAL_API_URL || 'http://localhost:8058';

// ── Animated Waveform Bars (recording indicator) ──────────────────────────
function WaveformBars({ isActive, barCount = 5, className = '' }) {
  return (
    <div className={`flex items-center gap-[3px] h-4 ${className}`}>
      {Array.from({ length: barCount }).map((_, i) => (
        <div
          key={i}
          className="w-[3px] rounded-full transition-all"
          style={{
            height: isActive ? '100%' : '30%',
            backgroundColor: isActive ? '#ef4444' : '#94a3b8',
            animation: isActive ? `waveform ${0.4 + i * 0.12}s ease-in-out infinite alternate` : 'none',
            animationDelay: `${i * 0.08}s`,
          }}
        />
      ))}
    </div>
  );
}

// Inject keyframes once
if (typeof document !== 'undefined' && !document.getElementById('waveform-keyframes')) {
  const style = document.createElement('style');
  style.id = 'waveform-keyframes';
  style.textContent = `
    @keyframes waveform {
      0%   { height: 25%; }
      100% { height: 100%; }
    }
    @keyframes stt-pulse {
      0%, 100% { box-shadow: 0 0 0 0 rgba(239,68,68,0.4); }
      50%      { box-shadow: 0 0 0 8px rgba(239,68,68,0); }
    }
  `;
  document.head.appendChild(style);
}


// ── Voice Input Button (Google Cloud STT via backend proxy) ───────────────
export function VoiceInputButton({ onTranscript, disabled = false, className = '' }) {
  const { isDark } = useTheme();
  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [recordingDuration, setRecordingDuration] = useState(0);
  const [error, setError] = useState('');

  const mediaRecorderRef = useRef(null);
  const chunksRef = useRef([]);
  const streamRef = useRef(null);
  const timerRef = useRef(null);

  // Clean up on unmount
  useEffect(() => {
    return () => {
      stopRecording(true);
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, []);

  const startRecording = useCallback(async () => {
    setError('');
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          sampleRate: 48000,
          echoCancellation: true,
          noiseSuppression: true,
        },
      });
      streamRef.current = stream;

      // Prefer webm/opus (best compatibility + quality for Google STT)
      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : MediaRecorder.isTypeSupported('audio/webm')
          ? 'audio/webm'
          : 'audio/ogg';

      const recorder = new MediaRecorder(stream, { mimeType });
      mediaRecorderRef.current = recorder;
      chunksRef.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      recorder.onstop = async () => {
        // Assemble the Blob and send to backend
        const blob = new Blob(chunksRef.current, { type: mimeType });
        chunksRef.current = [];

        if (blob.size < 100) {
          setError('Recording too short');
          return;
        }

        setIsTranscribing(true);
        try {
          const formData = new FormData();
          formData.append('audio', blob, 'recording.webm');

          const resp = await fetch(`${CLINICAL_API_BASE}/clinical/stt`, {
            method: 'POST',
            body: formData,
          });

          if (!resp.ok) {
            const errBody = await resp.json().catch(() => ({ detail: resp.statusText }));
            throw new Error(errBody.detail || `STT error ${resp.status}`);
          }

          const data = await resp.json();
          if (data.transcript && onTranscript) {
            onTranscript(data.transcript);
          } else if (!data.transcript) {
            setError('No speech detected');
          }
        } catch (err) {
          console.error('STT error:', err);
          setError(err.message || 'Transcription failed');
        } finally {
          setIsTranscribing(false);
        }
      };

      recorder.start(250); // collect in 250ms chunks
      setIsRecording(true);
      setRecordingDuration(0);

      // Duration timer
      timerRef.current = setInterval(() => {
        setRecordingDuration(d => d + 1);
      }, 1000);
    } catch (err) {
      console.error('Mic access error:', err);
      if (err.name === 'NotAllowedError') {
        setError('Microphone permission denied');
      } else {
        setError('Microphone not available');
      }
    }
  }, [onTranscript]);

  const stopRecording = useCallback((silent = false) => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(t => t.stop());
      streamRef.current = null;
    }
    setIsRecording(false);
  }, []);

  const toggle = useCallback(() => {
    if (isRecording) {
      stopRecording();
    } else {
      startRecording();
    }
  }, [isRecording, startRecording, stopRecording]);

  const formatDuration = (s) => {
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return `${m}:${sec.toString().padStart(2, '0')}`;
  };

  // ── Transcribing state (spinner) ──
  if (isTranscribing) {
    return (
      <div className={`flex items-center gap-2 ${className}`}>
        <div className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border text-sm font-medium ${
          isDark ? 'border-[var(--accent-primary)]/40 text-[var(--accent-primary)] bg-[var(--accent-primary)]/10'
                 : 'border-teal-300 text-teal-700 bg-teal-50'
        }`}>
          <Loader2 className="w-4 h-4 animate-spin" />
          <span>Transcribing…</span>
        </div>
      </div>
    );
  }

  // ── Recording state (live indicator) ──
  if (isRecording) {
    return (
      <div className={`flex items-center gap-2 ${className}`}>
        {/* Duration badge */}
        <div className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border text-sm font-medium ${
          isDark ? 'border-red-500/30 text-red-400 bg-red-500/10' : 'border-red-200 text-red-600 bg-red-50'
        }`} style={{ animation: 'stt-pulse 2s ease-in-out infinite' }}>
          <WaveformBars isActive barCount={4} />
          <span className="tabular-nums">{formatDuration(recordingDuration)}</span>
        </div>

        {/* Stop button */}
        <button
          onClick={() => stopRecording()}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium bg-red-600 text-white hover:bg-red-700 transition-colors"
        >
          <Square className="w-3.5 h-3.5" fill="currentColor" />
          Stop
        </button>
      </div>
    );
  }

  // ── Idle state (start button) ──
  return (
    <div className="relative">
      <button
        onClick={toggle}
        disabled={disabled}
        className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium border transition-all ${
          isDark
            ? 'border-white/20 text-slate-300 hover:bg-white/10 hover:border-[var(--accent-primary)]/40'
            : 'border-slate-300 text-slate-600 hover:bg-teal-50 hover:border-teal-300'
        } disabled:opacity-40 disabled:cursor-not-allowed`}
        title="Record voice note (Google Cloud STT)"
      >
        <Mic className="w-4 h-4" strokeWidth={1.5} />
        <Cloud className="w-3 h-3 opacity-50" strokeWidth={1.5} />
        Dictate
      </button>

      {/* Error tooltip */}
      {error && (
        <div className={`absolute top-full left-0 mt-2 p-2 rounded-lg shadow-lg border text-xs z-20 max-w-[240px] ${
          isDark ? 'bg-slate-800/95 border-red-500/30 text-red-400' : 'bg-white border-red-200 text-red-600'
        }`}>
          {error}
          <button
            onClick={() => setError('')}
            className="ml-2 underline opacity-70 hover:opacity-100"
          >dismiss</button>
        </div>
      )}
    </div>
  );
}

// ── Text-to-Speech Component (unchanged — browser native) ─────────────────
export function TextToSpeechButton({ text, label = 'Read Aloud', className = '' }) {
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [isSupported, setIsSupported] = useState(true);

  useEffect(() => {
    if (!speechSynthesis) {
      setIsSupported(false);
    }
    
    return () => {
      if (speechSynthesis) {
        speechSynthesis.cancel();
      }
    };
  }, []);

  const speak = useCallback(() => {
    if (!speechSynthesis || !text) return;

    if (isSpeaking && !isPaused) {
      speechSynthesis.pause();
      setIsPaused(true);
      return;
    }

    if (isPaused) {
      speechSynthesis.resume();
      setIsPaused(false);
      return;
    }

    // Cancel any ongoing speech
    speechSynthesis.cancel();

    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate  = 0.88;   // slightly slower — calm clinical tone
    utterance.pitch = 1.08;   // slightly higher — softer, female-friendly
    utterance.volume = 1;

    // Female voice priority list — works across Chrome/Edge/Windows
    const voices = speechSynthesis.getVoices();
    const FEMALE_PRIORITY = [
      'Microsoft Aria Online (Natural)',   // Edge neural (best)
      'Microsoft Aria',                    // Edge fallback
      'Google UK English Female',          // Chrome soft female
      'Google US English',                 // Chrome generic (usually female)
      'Microsoft Zira',                    // Windows classic female
      'Microsoft Jenny Online (Natural)',  // Edge neural alt
      'Samantha',                          // macOS / Safari female
    ];
    const preferredVoice =
      FEMALE_PRIORITY.map(name => voices.find(v => v.name === name)).find(Boolean) ||
      voices.find(v => /female/i.test(v.name) && v.lang.startsWith('en')) ||
      voices.find(v => v.lang.startsWith('en-'));
    if (preferredVoice) {
      utterance.voice = preferredVoice;
    }

    utterance.onstart = () => {
      setIsSpeaking(true);
      setIsPaused(false);
    };

    utterance.onend = () => {
      setIsSpeaking(false);
      setIsPaused(false);
    };

    utterance.onerror = () => {
      setIsSpeaking(false);
      setIsPaused(false);
    };

    speechSynthesis.speak(utterance);
  }, [text, isSpeaking, isPaused]);

  const stop = useCallback(() => {
    if (speechSynthesis) {
      speechSynthesis.cancel();
      setIsSpeaking(false);
      setIsPaused(false);
    }
  }, []);

  if (!isSupported) {
    return null;
  }

  return (
    <div className={`flex items-center gap-2 ${className}`}>
      <Button
        variant={isSpeaking ? 'primary' : 'secondary'}
        size="sm"
        icon={isSpeaking && !isPaused ? Pause : isSpeaking && isPaused ? Play : Volume2}
        onClick={speak}
        disabled={!text}
      >
        {isSpeaking && !isPaused ? 'Pause' : isSpeaking && isPaused ? 'Resume' : label}
      </Button>
      
      {isSpeaking && (
        <Button
          variant="danger"
          size="sm"
          icon={Square}
          onClick={stop}
        >
          Stop
        </Button>
      )}
    </div>
  );
}

// ── Voice Status Indicator ────────────────────────────────────────────────
export function VoiceStatusIndicator({ isListening }) {
  if (!isListening) return null;
  
  return (
    <div className="flex items-center gap-2 px-3 py-1.5 bg-red-100 rounded-full">
      <span className="relative flex h-2 w-2">
        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
        <span className="relative inline-flex rounded-full h-2 w-2 bg-red-500"></span>
      </span>
      <span className="text-xs font-medium text-red-700">Recording...</span>
    </div>
  );
}
