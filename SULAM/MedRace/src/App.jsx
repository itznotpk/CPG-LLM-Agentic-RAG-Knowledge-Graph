import { useState, useCallback } from 'react';
import { shuffleCards } from './data/cards.js';
import Lobby from './components/Lobby.jsx';
import RaceScreen from './components/RaceScreen.jsx';
import ResultsScreen from './components/ResultsScreen.jsx';

const HINT_PENALTY_MS = 10_000;

const freshState = () => ({
  phase: 'lobby',
  activeQuestion: null,
  shuffledCards: [],
  startTime: null,
  manualState: {
    flippedCards: new Set(),
    answer: '',
    submittedAt: null,
    submitted: false,
    hintUsed: false,
    penaltyMs: 0,
  },
  aiState: { answer: '', toolsUsed: [], completedAt: null, isStreaming: false, error: null },
});

export default function App() {
  const [state, setState] = useState(freshState);

  const startCountdown = useCallback((question) => {
    setState(prev => ({
      ...prev,
      phase: 'countdown',
      activeQuestion: question,
      shuffledCards: shuffleCards(),
    }));
  }, []);

  const beginRace = useCallback(() => {
    setState(prev => ({
      ...prev,
      phase: 'racing',
      startTime: Date.now(),
      aiState: { ...prev.aiState, isStreaming: true },
    }));
  }, []);

  const flipCard = useCallback((cardId) => {
    setState(prev => {
      if (prev.manualState.submitted) return prev;
      const next = new Set(prev.manualState.flippedCards);
      next.add(cardId);
      return { ...prev, manualState: { ...prev.manualState, flippedCards: next } };
    });
  }, []);

  const setManualAnswer = useCallback((answer) => {
    setState(prev => ({ ...prev, manualState: { ...prev.manualState, answer } }));
  }, []);

  const submitManual = useCallback(() => {
    setState(prev => {
      if (prev.manualState.submitted || !prev.manualState.answer.trim()) return prev;
      const rawTime = Date.now() - prev.startTime;
      return {
        ...prev,
        manualState: {
          ...prev.manualState,
          submitted: true,
          submittedAt: rawTime + prev.manualState.penaltyMs,
        },
      };
    });
  }, []);

  const useHint = useCallback(() => {
    setState(prev => {
      if (prev.manualState.hintUsed || prev.manualState.submitted) return prev;
      return {
        ...prev,
        manualState: {
          ...prev.manualState,
          hintUsed: true,
          penaltyMs: prev.manualState.penaltyMs + HINT_PENALTY_MS,
        },
      };
    });
  }, []);

  const onAIText  = useCallback((chunk) => setState(prev => ({ ...prev, aiState: { ...prev.aiState, answer: prev.aiState.answer + chunk } })), []);
  const onAITools = useCallback((tools) => setState(prev => ({ ...prev, aiState: { ...prev.aiState, toolsUsed: tools } })), []);
  const onAIDone  = useCallback(() => setState(prev => ({ ...prev, aiState: { ...prev.aiState, isStreaming: false, completedAt: Date.now() - prev.startTime } })), []);
  const onAIError = useCallback((err) => setState(prev => ({ ...prev, aiState: { ...prev.aiState, isStreaming: false, error: err } })), []);

  const goResults = useCallback(() => setState(prev => ({ ...prev, phase: 'results' })), []);
  const reset     = useCallback(() => setState(freshState()), []);

  const { phase, activeQuestion, shuffledCards, startTime, manualState, aiState } = state;

  if (phase === 'lobby') return <Lobby onStart={startCountdown} />;

  if (phase === 'results') return (
    <ResultsScreen
      question={activeQuestion}
      shuffledCards={shuffledCards}
      manualState={manualState}
      aiState={aiState}
      onReset={reset}
    />
  );

  return (
    <RaceScreen
      phase={phase}
      question={activeQuestion}
      cards={shuffledCards}
      startTime={startTime}
      manualState={manualState}
      aiState={aiState}
      onCountdownEnd={beginRace}
      onFlipCard={flipCard}
      onManualAnswer={setManualAnswer}
      onSubmitManual={submitManual}
      onUseHint={useHint}
      onAIText={onAIText}
      onAITools={onAITools}
      onAIDone={onAIDone}
      onAIError={onAIError}
      onShowResults={goResults}
    />
  );
}
