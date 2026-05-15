import { useState } from 'react';
import Lobby from './components/Lobby.jsx';
import QuestionList from './components/QuestionList.jsx';
import ManualQuiz from './components/ManualQuiz.jsx';
import AIQuiz from './components/AIQuiz.jsx';
import ResultPage from './components/ResultPage.jsx';

export default function App() {
  const [mode, setMode]                         = useState(null);  // null | 'manual' | 'ai'
  const [activeQuestionId, setActiveQuestionId] = useState(null);
  const [result, setResult]                     = useState(null);  // { selectedOption, elapsedMs }

  const goLobby    = () => { setMode(null); setActiveQuestionId(null); setResult(null); };
  const goList     = (m) => { setMode(m); setActiveQuestionId(null); setResult(null); };
  const goQuestion = (qId) => { setActiveQuestionId(qId); setResult(null); };
  const backToList = () => { setActiveQuestionId(null); setResult(null); };

  const handleAnswer = (selectedOption, elapsedMs) => setResult({ selectedOption, elapsedMs });

  if (result && activeQuestionId && mode) {
    return (
      <ResultPage
        questionId={activeQuestionId}
        mode={mode}
        selectedOption={result.selectedOption}
        elapsedMs={result.elapsedMs}
        onBackToList={backToList}
        onBackToLobby={goLobby}
      />
    );
  }

  if (!mode) return <Lobby onStart={goList} />;

  if (!activeQuestionId) return (
    <QuestionList mode={mode} onSelectQuestion={goQuestion} onBack={goLobby} />
  );

  if (mode === 'manual') return (
    <ManualQuiz questionId={activeQuestionId} onAnswer={handleAnswer} onBack={backToList} />
  );

  return <AIQuiz questionId={activeQuestionId} onAnswer={handleAnswer} onBack={backToList} />;
}
