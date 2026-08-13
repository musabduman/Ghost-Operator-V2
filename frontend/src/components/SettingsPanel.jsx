import { useState, useEffect } from 'react';
import { Save } from 'lucide-react';

export default function SettingsPanel({ isVisible }) {
  const [data, setData] = useState({ env: {}, prefs: {} });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (isVisible) {
      setLoading(true);
      fetch('http://127.0.0.1:8000/api/settings')
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

  const handleChange = (type, key, value) => {
    setData(prev => ({
      ...prev,
      [type]: {
        ...prev[type],
        [key]: value
      }
    }));
  };

  const handleSave = () => {
    fetch('http://127.0.0.1:8000/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    })
    .then(r => r.json())
    .then(d => alert("Ayarlar kaydedildi!"))
    .catch(e => alert("Hata: " + e.message));
  };

  if (loading) return <div style={{ padding: '16px', color: '#888' }}>Ayarlar yükleniyor...</div>;

  return (
    <div style={{ padding: '24px', height: '100%', overflowY: 'auto', backgroundColor: '#111', color: '#ccc' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <h2 style={{ margin: 0, color: 'var(--accent-color)' }}>Ghost Ayarları</h2>
        <button 
          onClick={handleSave}
          style={{
            display: 'flex', alignItems: 'center', gap: '8px',
            backgroundColor: 'var(--accent-color)', color: '#000',
            padding: '8px 16px', borderRadius: '6px', fontWeight: 'bold'
          }}
        >
          <Save size={16} /> Kaydet
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px' }}>
        {/* Model ve API Ayarları */}
        <div>
          <h3 style={{ borderBottom: '1px solid #333', paddingBottom: '8px', marginBottom: '16px' }}>API Anahtarları (.env)</h3>
          
          <div style={{ marginBottom: '12px' }}>
            <label style={{ display: 'block', fontSize: '12px', color: '#888', marginBottom: '4px' }}>Ollama API Key (Zorunlu değil)</label>
            <input 
              type="password"
              value={data.env.OLLAMA_API_KEY || ""}
              onChange={(e) => handleChange('env', 'OLLAMA_API_KEY', e.target.value)}
              style={{ width: '100%', padding: '8px', backgroundColor: '#1a1a1a', border: '1px solid #333', color: '#fff', borderRadius: '4px' }}
            />
          </div>
          
          <div style={{ marginBottom: '12px' }}>
            <label style={{ display: 'block', fontSize: '12px', color: '#888', marginBottom: '4px' }}>NVIDIA API Key</label>
            <input 
              type="password"
              value={data.env.NVIDIA_API_KEY || ""}
              onChange={(e) => handleChange('env', 'NVIDIA_API_KEY', e.target.value)}
              style={{ width: '100%', padding: '8px', backgroundColor: '#1a1a1a', border: '1px solid #333', color: '#fff', borderRadius: '4px' }}
            />
          </div>
          
          <div style={{ marginBottom: '12px' }}>
            <label style={{ display: 'block', fontSize: '12px', color: '#888', marginBottom: '4px' }}>Telegram API Key (Zorunlu değil)</label>
            <input 
              type="password"
              value={data.env.TELEGRAM_BOT_TOKEN || ""}
              onChange={(e) => handleChange('env', 'TELEGRAM_BOT_TOKEN', e.target.value)}
              style={{ width: '100%', padding: '8px', backgroundColor: '#1a1a1a', border: '1px solid #333', color: '#fff', borderRadius: '4px' }}
            />
          </div>

          <div style={{ marginBottom: '12px' }}>
            <label style={{ display: 'block', fontSize: '12px', color: '#888', marginBottom: '4px' }}>Sunucu IP Adresi (Zorunlu değil)</label>
            <input 
              type="text"
              value={data.env.SERVER_IP || ""}
              onChange={(e) => handleChange('env', 'SERVER_IP', e.target.value)}
              style={{ width: '100%', padding: '8px', backgroundColor: '#1a1a1a', border: '1px solid #333', color: '#fff', borderRadius: '4px' }}
              placeholder="192.168.1.x"
            />
          </div>
        </div>

        {/* Uygulama Tercihleri */}
        <div>
          <h3 style={{ borderBottom: '1px solid #333', paddingBottom: '8px', marginBottom: '16px' }}>Kişisel Tercihler</h3>
          
          <div style={{ marginBottom: '12px' }}>
            <label style={{ display: 'block', fontSize: '12px', color: '#888', marginBottom: '4px' }}>Dil Seçimi</label>
            <select 
              value={data.prefs.language || "Türkçe"}
              onChange={(e) => handleChange('prefs', 'language', e.target.value)}
              style={{ width: '100%', padding: '8px', backgroundColor: '#1a1a1a', border: '1px solid #333', color: '#fff', borderRadius: '4px' }}
            >
              <option>Türkçe</option>
              <option>English</option>
            </select>
          </div>
          
          <div style={{ marginBottom: '12px' }}>
            <label style={{ display: 'block', fontSize: '12px', color: '#888', marginBottom: '4px' }}>Ghost Token (Güvenlik)</label>
            <input 
              type="text"
              readOnly
              value={data.prefs.ghost_token || ""}
              style={{ width: '100%', padding: '8px', backgroundColor: '#111', border: '1px solid #222', color: '#555', borderRadius: '4px' }}
            />
          </div>
          
          <div style={{ marginBottom: '12px' }}>
            <label style={{ display: 'block', fontSize: '12px', color: '#888', marginBottom: '4px' }}>Özel Kurallar (Prompt Ekki)</label>
            <textarea 
              value={data.prefs.custom_rules || ""}
              onChange={(e) => handleChange('prefs', 'custom_rules', e.target.value)}
              style={{ width: '100%', padding: '8px', height: '80px', backgroundColor: '#1a1a1a', border: '1px solid #333', color: '#fff', borderRadius: '4px', resize: 'vertical' }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
