import { useState, useEffect } from 'react';

export default function MemoryPanel({ isVisible }) {
  const [data, setData] = useState({ goals: [], recent_events: [] });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (isVisible) {
      setLoading(true);
      fetch('http://127.0.0.1:8000/api/memory')
        .then(r => r.json())
        .then(d => {
          setData(d);
          setLoading(false);
        })
        .catch(e => {
          console.error(e);
          setLoading(false);
        });
    }
  }, [isVisible]);

  return (
    <div style={{ padding: '16px', height: '100%', overflowY: 'auto', backgroundColor: '#111', color: '#ccc' }}>
      {loading ? (
        <div style={{ color: '#888' }}>Hafıza yükleniyor...</div>
      ) : (
        <div style={{ display: 'flex', gap: '24px' }}>
          <div style={{ flex: 1 }}>
            <h3 style={{ color: 'var(--accent-color)', marginBottom: '12px', fontSize: '14px' }}>Aktif Hedefler</h3>
            {data.goals?.length === 0 && <span style={{ color: '#555' }}>Hedef yok.</span>}
            <ul style={{ listStyleType: 'none', padding: 0 }}>
              {data.goals?.map((g, i) => (
                <li key={i} style={{ backgroundColor: '#1a1a1a', padding: '8px', marginBottom: '8px', borderRadius: '4px' }}>
                  {g.hedef_icerigi}
                </li>
              ))}
            </ul>
          </div>
          <div style={{ flex: 1 }}>
            <h3 style={{ color: '#ffcc00', marginBottom: '12px', fontSize: '14px' }}>Son Olaylar (Episodic)</h3>
            {data.recent_events?.length === 0 && <span style={{ color: '#555' }}>Olay yok.</span>}
            <ul style={{ listStyleType: 'none', padding: 0 }}>
              {data.recent_events?.map((e, i) => (
                <li key={i} style={{ borderBottom: '1px solid #222', paddingBottom: '8px', marginBottom: '8px', fontSize: '13px' }}>
                  <span style={{ color: '#888', display: 'block', fontSize: '11px' }}>{e.zaman}</span>
                  <strong>{e.rol}: </strong>{e.icerik}
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </div>
  );
}
