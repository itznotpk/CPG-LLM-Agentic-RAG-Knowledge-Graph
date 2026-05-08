import React, { useState, useEffect, useCallback } from 'react';
import { Mic, MicOff, Volume2, VolumeX, Square, Play, Pause } from 'lucide-react';
import { Button, Badge } from '../shared';
import { useTheme } from '../../context/ThemeContext';

// Check for browser support
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
const speechSynthesis = window.speechSynthesis;

// Voice Input Button Component
export function VoiceInputButton({ onTranscript, disabled = false, className = '' }) {
  const { isDark } = useTheme();
  const [isListening, setIsListening] = useState(false);
  const [isSupported, setIsSupported] = useState(true);
  const [recognition, setRecognition] = useState(null);
  const [interimTranscript, setInterimTranscript] = useState('');

  useEffect(() => {
    if (!SpeechRecognition) {
      setIsSupported(false);
      return;
    }

    const recognitionInstance = new SpeechRecognition();
    recognitionInstance.continuous = true;
    recognitionInstance.interimResults = true;
    recognitionInstance.lang = 'en-US';

    recognitionInstance.onresult = (event) => {
      let interim = '';
      let final = '';

      for (let i = event.resultIndex; i < event.results.length; i++) {
        const transcript = event.results[i][0].transcript;
        if (event.results[i].isFinal) {
          final += transcript + ' ';
        } else {
          interim += transcript;
        }
      }

      setInterimTranscript(interim);
      if (final && onTranscript) {
        onTranscript(final.trim());
      }
    };

    recognitionInstance.onerror = (event) => {
      console.error('Speech recognition error:', event.error);
      setIsListening(false);
    };

    recognitionInstance.onend = () => {
      setIsListening(false);
      setInterimTranscript('');
    };

    setRecognition(recognitionInstance);

    return () => {
      if (recognitionInstance) {
        recognitionInstance.stop();
      }
    };
  }, [onTranscript]);

  const toggleListening = useCallback(() => {
    if (!recognition) return;

    if (isListening) {
      recognition.stop();
      setIsListening(false);
    } else {
      recognition.start();
      setIsListening(true);
    }
  }, [recognition, isListening]);

  if (!isSupported) {
    return (
      <Button
        variant="secondary"
        size="sm"
        disabled
        className={className}
        title="Speech recognition not supported in this browser"
      >
        <MicOff className="w-4 h-4" />
      </Button>
    );
  }

  return (
    <div className="relative">
      <Button
        variant={isListening ? 'danger' : 'secondary'}
        size="sm"
        icon={isListening ? MicOff : Mic}
        onClick={toggleListening}
        disabled={disabled}
        className={`${className} ${isListening ? 'animate-pulse' : ''}`}
        title={isListening ? 'Stop listening' : 'Start voice input'}
      >
        {isListening ? 'Stop' : 'Voice'}
      </Button>
      
      {isListening && interimTranscript && (
        <div className={`absolute top-full left-0 mt-2 p-2 backdrop-blur-sm rounded-lg shadow-lg border min-w-[200px] max-w-[300px] z-10 ${isDark ? 'bg-slate-800/90 border-white/10' : 'bg-white/90 border-slate-200'}`}>
          <p className={`text-xs mb-1 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>Listening...</p>
          <p className={`text-sm italic ${isDark ? 'text-slate-200' : 'text-slate-700'}`}>{interimTranscript}</p>
        </div>
      )}
      
      {isListening && (
        <div className="absolute -top-1 -right-1">
          <span className="relative flex h-3 w-3">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-3 w-3 bg-red-500"></span>
          </span>
        </div>
      )}
    </div>
  );
}

// Text-to-Speech Component
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
    utterance.rate = 0.9;
    utterance.pitch = 1;
    utterance.volume = 1;

    // Try to use a natural-sounding voice
    const voices = speechSynthesis.getVoices();
    const preferredVoice = voices.find(v => 
      v.name.includes('Google') || v.name.includes('Natural') || v.lang.startsWith('en')
    );
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

// Voice Status Indicator
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
