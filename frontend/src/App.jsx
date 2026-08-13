import { useState, useEffect, useRef } from 'react'
import Sidebar from './components/Sidebar'
import ChatArea from './components/ChatArea'
import CodePanel from './components/CodePanel'

function App() {
  const [currentSession, setCurrentSession] = useState("headless_core_session");
  const [isCodePanelVisible, setIsCodePanelVisible] = useState(false);
  
  const [sessions, setSessions] = useState([]);
  const [messages, setMessages] = useState([]);
  const [fileData, setFileData] = useState(null);
  
  const ws = useRef(null);

  useEffect(() => {
    // Fetch initial sessions
    fetch('http://127.0.0.1:8000/api/sessions')
      .then(r => r.json())
      .then(data => setSessions(data))
      .catch(e => console.error("Session load error:", e));

    // Connect WebSocket
    connectWs();
    return () => {
      if(ws.current) ws.current.close();
    }
  }, []);

  const connectWs = () => {
    ws.current = new WebSocket('ws://127.0.0.1:8000/ws');
    ws.current.onmessage = (event) => {
      const payload = JSON.parse(event.data);
      if (payload.type === 'message') {
        setMessages(prev => [...prev, { role: payload.role, content: payload.text }]);
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
      }
    };
    ws.current.onclose = () => {
      setTimeout(connectWs, 3000);
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
      />

      <CodePanel 
        isVisible={isCodePanelVisible}
        onClose={() => setIsCodePanelVisible(false)}
        fileData={fileData}
        onApprove={handleApprove}
        onReject={handleReject}
      />
    </div>
  )
}

export default App
