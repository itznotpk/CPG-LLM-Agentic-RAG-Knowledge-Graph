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
        {/* DetectiveView stays mounted so its in-flight SSE stream and stage
            state survive tab switches. Other tabs unmount as usual. */}
        <div style={{ display: activeTab === 'detective' ? 'contents' : 'none' }}>
          <DetectiveView />
        </div>
        {activeTab === 'architecture' && <ArchitectureView />}
        {activeTab === 'graph'        && <GraphView />}
      </main>
    </div>
  );
}
