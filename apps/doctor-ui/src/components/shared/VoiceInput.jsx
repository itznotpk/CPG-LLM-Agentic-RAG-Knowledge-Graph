import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Mic, MicOff, Volume2, VolumeX, Square, Play, Pause, Loader2, Cloud, CloudOff, FileText, X } from 'lucide-react';
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


// ── Transcript Modal (consultation mode) ─────────────────────────────────
function TranscriptModal({ turns, onClose, isDark }) {
  if (!turns || turns.length === 0) return null;
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      onClick={onClose}
    >
      <div
        className={`relative w-full max-w-lg mx-4 rounded-xl shadow-2xl border overflow-hidden ${
          isDark ? 'bg-slate-900 border-white/10' : 'bg-white border-slate-200'
        }`}
        onClick={e => e.stopPropagation()}
      >
        <div className={`flex items-center justify-between px-4 py-3 border-b ${isDark ? 'border-white/10' : 'border-slate-100'}`}>
          <span className={`text-sm font-semibold ${isDark ? 'text-white' : 'text-slate-800'}`}>
            Consultation Transcript
          </span>
          <button
            onClick={onClose}
            className={`text-xs px-2 py-1 rounded ${isDark ? 'text-slate-400 hover:text-white' : 'text-slate-500 hover:text-slate-800'}`}
          >
            Close
          </button>
        </div>
        <div className="p-4 max-h-96 overflow-y-auto space-y-2">
          {turns.map((t, i) => (
            <div key={i} className="flex gap-2">
              <span className={`text-xs font-semibold shrink-0 w-14 pt-0.5 ${
                t.speaker === 'Doctor'
                  ? (isDark ? 'text-teal-400' : 'text-teal-600')
                  : (isDark ? 'text-violet-400' : 'text-violet-600')
              }`}>
                {t.speaker}
              </span>
              <span className={`text-sm leading-snug ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
                {t.text}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function TranscriptLogButton({ onClick, isDark }) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium border transition-colors ${
        isDark
          ? 'border-white/20 text-slate-300 hover:bg-white/10 hover:border-[var(--accent-primary)]/40'
          : 'border-slate-300 text-slate-600 hover:bg-slate-50 hover:border-teal-300'
      }`}
      title="View consultation transcript log"
    >
      <FileText className="w-4 h-4" strokeWidth={1.5} />
      Transcript Log
    </button>
  );
}

const CONSULTATION_MAX_SECONDS = 12 * 60; // 12 min hard cap
const CONSULTATION_WARN_SECONDS = 10 * 60; // 10 min warning

// ── Voice Input Button (Google Cloud STT via backend proxy) ───────────────
export function VoiceInputButton({ onTranscript, disabled = false, className = '', mode = 'dictate' }) {
  const { isDark } = useTheme();
  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [recordingDuration, setRecordingDuration] = useState(0);
  const [error, setError] = useState('');

  // Consultation-mode extras
  const [transcriptTurns, setTranscriptTurns] = useState(null);
  const [showModal, setShowModal] = useState(false);
  const [processingDone, setProcessingDone] = useState(false);

  const mediaRecorderRef = useRef(null);
  const chunksRef = useRef([]);
  const streamRef = useRef(null);
  const timerRef = useRef(null);
  const hardStopRef = useRef(null);
  const discardRecordingRef = useRef(false);

  // Clean up on unmount
  useEffect(() => {
    return () => {
      stopRecording(true);
      if (timerRef.current) clearInterval(timerRef.current);
      if (hardStopRef.current) clearTimeout(hardStopRef.current);
    };
  }, []);

  const startRecording = useCallback(async () => {
    setError('');
    setProcessingDone(false);
    setTranscriptTurns(null);
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
      discardRecordingRef.current = false;

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      recorder.onstop = async () => {
        if (discardRecordingRef.current) {
          chunksRef.current = [];
          discardRecordingRef.current = false;
          return;
        }

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

          const endpoint = mode === 'consultation'
            ? `${CLINICAL_API_BASE}/clinical/consultation/process`
            : `${CLINICAL_API_BASE}/clinical/stt`;

          const resp = await fetch(endpoint, {
            method: 'POST',
            body: formData,
            // No timeout on fetch — longrunning poll can take 30–90 s
          });

          if (!resp.ok) {
            const errBody = await resp.json().catch(() => ({ detail: resp.statusText }));
            throw new Error(errBody.detail || `STT error ${resp.status}`);
          }

          const data = await resp.json();

          if (mode === 'consultation') {
            // Store turns for optional transcript viewer
            if (data.transcript && data.transcript.length > 0) {
              setTranscriptTurns(data.transcript);
            }
            if (data.summary && onTranscript) {
              onTranscript(data.summary);
              setProcessingDone(true);
              setTimeout(() => setProcessingDone(false), 3000);
            } else if (data.transcript && data.transcript.length > 0) {
              setError('Transcription succeeded but summary failed — check backend logs');
            } else {
              setError('No speech detected in recording');
            }
          } else {
            if (data.transcript && onTranscript) {
              onTranscript(data.transcript);
            } else if (!data.transcript) {
              setError('No speech detected');
            }
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

      timerRef.current = setInterval(() => {
        setRecordingDuration(d => d + 1);
      }, 1000);

      // Hard stop at 12 min for consultation mode
      if (mode === 'consultation') {
        hardStopRef.current = setTimeout(() => {
          stopRecording();
        }, CONSULTATION_MAX_SECONDS * 1000);
      }
    } catch (err) {
      console.error('Mic access error:', err);
      if (err.name === 'NotAllowedError') {
        setError('Microphone permission denied');
      } else {
        setError('Microphone not available');
      }
    }
  }, [onTranscript, mode]);

  const stopRecording = useCallback((silent = false) => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    if (hardStopRef.current) {
      clearTimeout(hardStopRef.current);
      hardStopRef.current = null;
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

  const cancelRecording = useCallback(() => {
    discardRecordingRef.current = true;
    chunksRef.current = [];
    setError('');
    stopRecording(true);
  }, [stopRecording]);

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

  const isNearLimit = mode === 'consultation' && recordingDuration >= CONSULTATION_WARN_SECONDS;

  // ── Transcribing / processing state (spinner) ──
  if (isTranscribing) {
    return (
      <div className={`flex items-center gap-2 ${className}`}>
        <div className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border text-sm font-medium ${
          isDark ? 'border-[var(--accent-primary)]/40 text-[var(--accent-primary)] bg-[var(--accent-primary)]/10'
                 : 'border-teal-300 text-teal-700 bg-teal-50'
        }`}>
          <Loader2 className="w-4 h-4 animate-spin" />
          <span>
            {mode === 'consultation'
              ? 'Processing consultation… (this can take up to a minute)'
              : 'Transcribing…'}
          </span>
        </div>
        {mode === 'consultation' && transcriptTurns && (
          <button
            onClick={() => setShowModal(true)}
            className={`text-xs px-2 py-1 rounded border ${
              isDark ? 'border-white/20 text-slate-400 hover:text-white' : 'border-slate-300 text-slate-500 hover:text-slate-800'
            }`}
          >
            View Transcript
          </button>
        )}
        {showModal && (
          <TranscriptModal turns={transcriptTurns} onClose={() => setShowModal(false)} isDark={isDark} />
        )}
      </div>
    );
  }

  // ── Recording state (live indicator) ──
  if (isRecording) {
    return (
      <div className={`flex items-center gap-2 ${className}`}>
        {/* Duration badge */}
        <div className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border text-sm font-medium ${
          isNearLimit
            ? (isDark ? 'border-amber-500/40 text-amber-400 bg-amber-500/10' : 'border-amber-300 text-amber-700 bg-amber-50')
            : (isDark ? 'border-red-500/30 text-red-400 bg-red-500/10' : 'border-red-200 text-red-600 bg-red-50')
        }`} style={{ animation: 'stt-pulse 2s ease-in-out infinite' }}>
          <WaveformBars isActive barCount={4} />
          <span className="tabular-nums">{formatDuration(recordingDuration)}</span>
          {isNearLimit && <span className="text-xs opacity-75">limit soon</span>}
        </div>

        {/* Stop button */}
        <button
          onClick={() => stopRecording()}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium bg-red-600 text-white hover:bg-red-700 transition-colors"
        >
          <Square className="w-3.5 h-3.5" fill="currentColor" />
          Stop
        </button>
        <button
          onClick={cancelRecording}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium border transition-colors ${
            isDark
              ? 'border-white/20 text-slate-300 hover:bg-white/10'
              : 'border-slate-300 text-slate-600 hover:bg-slate-50'
          }`}
          title="Cancel and discard this recording"
        >
          <X className="w-3.5 h-3.5" strokeWidth={2} />
          Cancel
        </button>
      </div>
    );
  }

  // ── Done state (brief checkmark, consultation mode) ──
  if (processingDone && mode === 'consultation') {
    return (
      <div className={`flex items-center gap-2 ${className}`}>
        <div className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border text-sm font-medium ${
          isDark ? 'border-emerald-500/30 text-emerald-400 bg-emerald-500/10' : 'border-emerald-200 text-emerald-700 bg-emerald-50'
        }`}>
          <span>&#10003; Summary added</span>
        </div>
        {transcriptTurns && (
          <button
            onClick={() => setShowModal(true)}
            className={`text-xs px-2 py-1 rounded border ${
              isDark ? 'border-white/20 text-slate-400 hover:text-white' : 'border-slate-300 text-slate-500 hover:text-slate-800'
            }`}
          >
            View Transcript
          </button>
        )}
        {showModal && (
          <TranscriptModal turns={transcriptTurns} onClose={() => setShowModal(false)} isDark={isDark} />
        )}
      </div>
    );
  }

  // ── Idle state (start button) ──
  return (
    <div className={`flex items-center gap-2 ${className}`}>
      <div className="relative">
        <button
          onClick={toggle}
          disabled={disabled}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium border transition-all ${
            isDark
              ? 'border-white/20 text-slate-300 hover:bg-white/10 hover:border-[var(--accent-primary)]/40'
              : 'border-slate-300 text-slate-600 hover:bg-teal-50 hover:border-teal-300'
          } disabled:opacity-40 disabled:cursor-not-allowed`}
          title={mode === 'consultation' ? 'Record consultation (Google Cloud STT + Gemini summary)' : 'Record voice note (Google Cloud STT)'}
        >
          <Mic className="w-4 h-4" strokeWidth={1.5} />
          <Cloud className="w-3 h-3 opacity-50" strokeWidth={1.5} />
          {mode === 'consultation' ? 'Record Consult' : 'Dictate'}
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
      {mode === 'consultation' && transcriptTurns && (
        <TranscriptLogButton onClick={() => setShowModal(true)} isDark={isDark} />
      )}
      {showModal && (
        <TranscriptModal turns={transcriptTurns} onClose={() => setShowModal(false)} isDark={isDark} />
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
