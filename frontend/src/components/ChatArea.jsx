import { useState, useRef, useEffect } from 'react';
import { Send, Bell, Settings, Eye, Terminal, Brain } from 'lucide-react';

export default function ChatArea({ messages, onSendMessage, toggleCodePanel, setActiveBottomTab, voiceState, toggleVoiceMode, isThinking, streamingMessage }) {
  const [input, setInput] = useState("");
  const scrollRef = useRef(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, isThinking, streamingMessage]);

  const handleSend = () => {
    if (input.trim()) {
      onSendMessage(input);
      setInput("");
    }
  };

  const getVoiceColor = () => {
    switch (voiceState) {
      case 'listening': return '#10b981';
      case 'speaking': return '#3b82f6';
      case 'thinking': return '#f59e0b';
      case 'idle':
      default: return '#888';
    }
  };

  return (
    <div className="main-content">
      {/* Top Bar */}
      <div className="app-header">
        <div style={{ color: '#aaa', fontSize: '12px' }}>
          Aktif Zeka: <span style={{ fontStyle: 'italic' }}>GPT-OSS 120B (Yönetici)</span>
        </div>
        <div style={{ display: 'flex', gap: '16px' }}>
          <button 
            onClick={toggleVoiceMode}
            style={{ backgroundColor: 'transparent', color: getVoiceColor(), display: 'flex', alignItems: 'center', gap: '4px' }}
            title="Sesli Asistan Modu"
          >
            <span style={{ 
              width: '8px', height: '8px', borderRadius: '50%', 
              backgroundColor: getVoiceColor(), 
              boxShadow: voiceState !== 'idle' ? `0 0 8px ${getVoiceColor()}` : 'none' 
            }} />
            Ses
          </button>
          
          <button onClick={() => setActiveBottomTab('terminal')} style={{ backgroundColor: 'transparent', color: '#888' }} title="Terminal (Loglar)">
            <Terminal size={18} />
          </button>
          <button onClick={() => setActiveBottomTab('memory')} style={{ backgroundColor: 'transparent', color: '#888' }} title="Hafıza">
            <Brain size={18} />
          </button>
          <button onClick={() => setActiveBottomTab('settings')} style={{ backgroundColor: 'transparent', color: '#888' }} title="Ayarlar">
            <Settings size={18} />
          </button>
          <button style={{ backgroundColor: 'transparent', color: '#888' }} onClick={toggleCodePanel} title="Kod Görüntüleyici">
            <Eye size={18} />
          </button>
        </div>
      </div>

      {/* Chat Messages */}
      <div className="chat-scroll-area" ref={scrollRef}>
        {messages.map((m, i) => (
          <div key={i} className={`chat-bubble ${m.role === 'user' ? 'user' : 'ai'}`}>
            {m.content}
            {m.hasDiff && (
              <div style={{ marginTop: '12px' }}>
                <button 
                  onClick={toggleCodePanel}
                  style={{
                    backgroundColor: 'transparent',
                    border: '1px solid var(--accent-color)',
                    color: 'var(--accent-color)',
                    padding: '6px 12px',
                    borderRadius: '4px',
                    fontSize: '12px'
                  }}
                >
                  Kodu İncele
                </button>
              </div>
            )}
          </div>
        ))}

        {isThinking && !streamingMessage && (
          <div className="chat-bubble ai thinking" style={{ fontStyle: 'italic', opacity: 0.7 }}>
            Ghost Düşünüyor... 🤔
          </div>
        )}
        
        {streamingMessage && (
          <div className="chat-bubble ai streaming">
            {streamingMessage}
            <span style={{ animation: 'blink 1s step-end infinite' }}>|</span>
          </div>
        )}
      </div>

      {/* Input Area */}
      <div className="chat-input-container">
        <textarea
          className="chat-input"
          placeholder="Ghost'a ne yaptırmak istersin?"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              handleSend();
            }
          }}
        />
        <button className="send-btn" onClick={handleSend}>
          <Send size={18} />
        </button>
      </div>
    </div>
  );
}
