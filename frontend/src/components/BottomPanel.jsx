import { useState } from 'react';
import { Terminal, Brain, Settings, X, ChevronUp, ChevronDown } from 'lucide-react';
import TerminalPanel from './TerminalPanel';
import MemoryPanel from './MemoryPanel';
import SettingsPanel from './SettingsPanel';

export default function BottomPanel({ activeTab, setActiveTab, logs }) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [height, setHeight] = useState(300);

  if (!activeTab) return null;

  return (
    <div style={{
      position: 'absolute',
      bottom: 0,
      left: 0,
      right: 0,
      height: isExpanded ? '80vh' : `${height}px`,
      backgroundColor: '#161616',
      borderTop: '1px solid var(--border-color)',
      display: 'flex',
      flexDirection: 'column',
      zIndex: 50,
      transition: 'height 0.3s ease'
    }}>
      {/* Header */}
      <div style={{
        height: '40px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 16px',
        backgroundColor: '#111',
        borderBottom: '1px solid var(--border-color)'
      }}>
        <div style={{ display: 'flex', gap: '16px' }}>
          <button 
            onClick={() => setActiveTab('terminal')}
            style={{ display: 'flex', alignItems: 'center', gap: '6px', color: activeTab === 'terminal' ? 'var(--accent-color)' : '#888', backgroundColor: 'transparent' }}
          >
            <Terminal size={14} /> Terminal
          </button>
          <button 
            onClick={() => setActiveTab('memory')}
            style={{ display: 'flex', alignItems: 'center', gap: '6px', color: activeTab === 'memory' ? 'var(--accent-color)' : '#888', backgroundColor: 'transparent' }}
          >
            <Brain size={14} /> Hafıza
          </button>
          <button 
            onClick={() => setActiveTab('settings')}
            style={{ display: 'flex', alignItems: 'center', gap: '6px', color: activeTab === 'settings' ? 'var(--accent-color)' : '#888', backgroundColor: 'transparent' }}
          >
            <Settings size={14} /> Ayarlar
          </button>
        </div>
        
        <div style={{ display: 'flex', gap: '8px' }}>
          <button onClick={() => setIsExpanded(!isExpanded)} style={{ backgroundColor: 'transparent', color: '#888' }}>
            {isExpanded ? <ChevronDown size={18} /> : <ChevronUp size={18} />}
          </button>
          <button onClick={() => setActiveTab(null)} style={{ backgroundColor: 'transparent', color: '#888' }}>
            <X size={18} />
          </button>
        </div>
      </div>

      {/* Content */}
      <div style={{ flex: 1, overflow: 'hidden' }}>
        {activeTab === 'terminal' && <TerminalPanel logs={logs} />}
        {activeTab === 'memory' && <MemoryPanel isVisible={activeTab === 'memory'} />}
        {activeTab === 'settings' && <SettingsPanel isVisible={activeTab === 'settings'} />}
      </div>
    </div>
  );
}
