import { useEffect, useRef } from 'react';

export default function TerminalPanel({ logs }) {
  const scrollRef = useRef(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs]);

  const getColor = (tag) => {
    switch (tag) {
      case 'red': return '#ff4444';
      case 'green': return '#00ffcc';
      case 'yellow': return '#ffcc00';
      case 'blue': return '#4488ff';
      default: return '#cccccc';
    }
  }

  return (
    <div style={{ padding: '16px', height: '100%', overflowY: 'auto', backgroundColor: '#000', fontFamily: 'var(--font-mono)' }} ref={scrollRef}>
      {logs.length === 0 && <div style={{ color: '#555' }}>Sistem başlatıldı... Log bekleniyor.</div>}
      {logs.map((log, i) => (
        <div key={i} style={{ marginBottom: '4px', fontSize: '12px', color: getColor(log.tag) }}>
          <span style={{ opacity: 0.5 }}>[{new Date(log.ts || Date.now()).toLocaleTimeString()}]</span> {log.text}
        </div>
      ))}
    </div>
  );
}
