import { useState } from 'react';
import Sidebar from './components/Sidebar.jsx';
import DetectiveView from './components/detective/DetectiveView.jsx';
import ArchitectureView from './components/architecture/ArchitectureView.jsx';
import GraphView from './components/graph/GraphView.jsx';

const TABS = [
  { id: 'detective',     label: 'Medical Detective' },
  { id: 'architecture',  label: 'How It Works' },
  { id: 'graph',         label: 'Knowledge Graph' },
];

export default function App() {
  const [activeTab, setActiveTab] = useState('detective');

  return (
    <div className="app-shell">
      <Sidebar tabs={TABS} activeTab={activeTab} onTabChange={setActiveTab} />
      <main className="main-content">
        {activeTab === 'detective'    && <DetectiveView />}
        {activeTab === 'architecture' && <ArchitectureView />}
        {activeTab === 'graph'        && <GraphView />}
      </main>
    </div>
  );
}
