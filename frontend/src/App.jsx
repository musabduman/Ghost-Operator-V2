import { useState, useEffect, useRef } from 'react'
import Sidebar from './components/Sidebar'
import ChatArea from './components/ChatArea'
import CodePanel from './components/CodePanel'
import BottomPanel from './components/BottomPanel'

function App() {
  const [currentSession, setCurrentSession] = useState("headless_core_session");
  const [isCodePanelVisible, setIsCodePanelVisible] = useState(false);
  const [activeBottomTab, setActiveBottomTab] = useState(null); // 'terminal', 'memory', 'settings'
  const [voiceState, setVoiceState] = useState('idle');
  
  const [sessions, setSessions] = useState([]);
  const [messages, setMessages] = useState([]);
  const [fileData, setFileData] = useState(null);
  const [logs, setLogs] = useState([]);
  const [isThinking, setIsThinking] = useState(false);
  const [streamingMessage, setStreamingMessage] = useState("");
  
  const ws = useRef(null);

  useEffect(() => {
    fetch('http://127.0.0.1:8000/api/sessions')
      .then(r => r.json())
      .then(data => setSessions(data))
      .catch(e => console.error("Session load error:", e));

    connectWs();
    return () => { 
      if(ws.current) {
        ws.current.onclose = null;
        ws.current.onmessage = null;
        ws.current.close();
        ws.current = null;
      }
    }
  }, []);

  const connectWs = () => {
    if (ws.current && (ws.current.readyState === WebSocket.OPEN || ws.current.readyState === WebSocket.CONNECTING)) {
      return;
    }
    
    const socket = new WebSocket('ws://127.0.0.1:8000/ws');
    ws.current = socket;
    
    socket.onmessage = (event) => {
      const payload = JSON.parse(event.data);
      if (payload.type === 'message') {
        setMessages(prev => [...prev, { role: payload.role, content: payload.text }]);
        setIsThinking(false);
        setStreamingMessage("");
      } else if (payload.type === 'chat_thinking') {
        setIsThinking(true);
        setStreamingMessage("");
      } else if (payload.type === 'chat_stream_start') {
        setIsThinking(false);
        setStreamingMessage("");
      } else if (payload.type === 'chat_stream') {
        setIsThinking(false);
        setStreamingMessage(prev => prev + payload.chunk);
      } else if (payload.type === 'diff_request') {
        setMessages(prev => [...prev, { role: 'ai', content: payload.description || 'Patron, şu dosyada değişiklik yapıyorum. Lütfen incele:', hasDiff: true }]);
        setFileData({
          action_id: payload.action_id,
          path: payload.path,
          language: payload.path.split('.').pop() || 'python',
          isDiff: true,
          originalContent: payload.originalContent,
          modifiedContent: payload.modifiedContent
        });
        setIsCodePanelVisible(true);
      } else if (payload.type === 'log') {
        setLogs(prev => [...prev, { text: payload.text, tag: payload.tag, ts: Date.now() }]);
      } else if (payload.type === 'voice_state') {
        setVoiceState(payload.state);
      }
    };
    
    socket.onclose = () => {
      if (ws.current === socket) {
        setTimeout(connectWs, 3000);
      }
    }
  }

  const handleSendMessage = (text) => {
    if (ws.current && ws.current.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify({ type: 'chat', text }));
    }
  };

  const handleApprove = () => {
    if (ws.current && fileData) {
      ws.current.send(JSON.stringify({ type: 'diff_response', action_id: fileData.action_id, approved: true, reason: "" }));
      setMessages(prev => [...prev, { role: 'ai', content: 'Değişiklikler onaylandı.' }]);
      setFileData(prev => ({ ...prev, isDiff: false, content: prev.modifiedContent }));
    }
  };

  const handleReject = () => {
    if (ws.current && fileData) {
      ws.current.send(JSON.stringify({ type: 'diff_response', action_id: fileData.action_id, approved: false, reason: "Reddedildi." }));
      setMessages(prev => [...prev, { role: 'ai', content: 'Değişiklik reddedildi.' }]);
      setIsCodePanelVisible(false);
    }
  };
  
  const toggleVoiceMode = () => {
    if (ws.current && ws.current.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify({ type: 'toggle_voice' }));
    }
  };

  return (
    <div className="app-container">
      <Sidebar 
        sessions={sessions} 
        currentSession={currentSession}
        onSelectSession={setCurrentSession}
      />
      
      <ChatArea 
        messages={messages} 
        onSendMessage={handleSendMessage} 
        toggleCodePanel={() => setIsCodePanelVisible(!isCodePanelVisible)}
        setActiveBottomTab={setActiveBottomTab}
        voiceState={voiceState}
        toggleVoiceMode={toggleVoiceMode}
        isThinking={isThinking}
        streamingMessage={streamingMessage}
      />

      <CodePanel 
        isVisible={isCodePanelVisible}
        onClose={() => setIsCodePanelVisible(false)}
        fileData={fileData}
        onApprove={handleApprove}
        onReject={handleReject}
      />
      
      <BottomPanel 
        activeTab={activeBottomTab} 
        setActiveTab={setActiveBottomTab} 
        logs={logs} 
      />
    </div>
  )
}

export default App
