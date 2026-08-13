import { useState, useRef, useEffect } from 'react';
import { Send, Bell, Settings, Eye } from 'lucide-react';

export default function ChatArea({ messages, onSendMessage, toggleCodePanel }) {
  const [input, setInput] = useState("");
  const scrollRef = useRef(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const handleSend = () => {
    if (input.trim()) {
      onSendMessage(input);
      setInput("");
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
          <button style={{ backgroundColor: 'transparent', color: '#888' }}><Bell size={18} /></button>
          <button style={{ backgroundColor: 'transparent', color: '#888' }}><Settings size={18} /></button>
          <button style={{ backgroundColor: 'transparent', color: '#888' }} onClick={toggleCodePanel}><Eye size={18} /></button>
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
