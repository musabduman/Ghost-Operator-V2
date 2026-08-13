import { MessageSquare, Settings, Bell, Code } from 'lucide-react';

export default function Sidebar({ sessions, currentSession, onSelectSession }) {
  return (
    <div className="sidebar">
      <div style={{ padding: '20px 16px', borderBottom: '1px solid var(--border-color)' }}>
        <h2 style={{ fontSize: '14px', color: '#888', letterSpacing: '1px' }}>GHOST OPERATOR</h2>
      </div>

      <div style={{ padding: '16px' }}>
        <button 
          style={{
            width: '100%',
            padding: '10px',
            backgroundColor: 'transparent',
            border: '1px solid #1e3028',
            color: 'var(--accent-color)',
            borderRadius: '6px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '8px'
          }}
        >
          <MessageSquare size={16} /> Yeni Sohbet
        </button>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: '0 8px' }}>
        {sessions.map(s => (
          <div 
            key={s.id} 
            onClick={() => onSelectSession(s.id)}
            style={{
              padding: '12px 16px',
              margin: '4px 0',
              borderRadius: '6px',
              backgroundColor: currentSession === s.id ? '#0f1a17' : 'transparent',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              borderLeft: currentSession === s.id ? '3px solid var(--accent-color)' : '3px solid transparent'
            }}
          >
            <div style={{ display: 'flex', flexDirection: 'column' }}>
              <span style={{ color: currentSession === s.id ? 'var(--accent-color)' : '#aaa', fontSize: '13px' }}>{s.title}</span>
              <span style={{ color: currentSession === s.id ? '#2a3a2a' : '#555', fontSize: '11px', marginTop: '4px' }}>{s.date}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
