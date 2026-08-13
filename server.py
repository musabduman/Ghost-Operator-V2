from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import threading
import sys
import os
import json
import asyncio
import uuid

# Ayarları çek ve çekirdek yapılandırmayı yap
import core.config
core.config.USE_DOCKER_CORE = False

from handler.command_handler import CommandHandler
from sessions.session_manager import list_sessions, load_session, save_session, new_session_id

app = FastAPI(title="Ghost Operator Web API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Local host için serbest
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                pass

    def broadcast_sync(self, message: dict):
        """Thread-safe way to broadcast from synchronous threads"""
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.broadcast(message))
        except RuntimeError:
            asyncio.run(self.broadcast(message))

manager = ConnectionManager()

class WebGhostApp:
    def __init__(self):
        self.voice_mode = False
        self._expanded = True
        self.messages = []
        self.current_session_id = new_session_id()
        self.command_handler = CommandHandler(self)
        self.is_busy = False
        self.pending_diffs = {}  # { action_id: (event, result_holder) }

    def log(self, text, tag=""):
        manager.broadcast_sync({"type": "log", "text": text, "tag": tag})

    def record_message(self, role, text):
        self.messages.append({"role": role, "text": text})
        manager.broadcast_sync({"type": "message", "role": role, "text": text})

    def set_model_label(self, text, color=""):
        manager.broadcast_sync({"type": "status", "text": text})

    def after(self, delay, func):
        threading.Timer(delay/1000.0, func).start()

    def request_diff_approval(self, yol, eski_icerik, icerik, aciklama, event, result_holder):
        action_id = str(uuid.uuid4())
        self.pending_diffs[action_id] = (event, result_holder)
        manager.broadcast_sync({
            "type": "diff_request",
            "action_id": action_id,
            "path": yol,
            "originalContent": eski_icerik,
            "modifiedContent": icerik,
            "description": aciklama
        })

ghost_app = WebGhostApp()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)
            
            if payload.get("type") == "chat":
                msg = payload.get("text", "")
                if msg:
                    ghost_app.record_message("user", msg)
                    
                    def run_chat():
                        ghost_app.is_busy = True
                        try:
                            cevap, _ = ghost_app.command_handler.controller(msg)
                            ghost_app.record_message("ghost", cevap)
                        except Exception as e:
                            ghost_app.log(f"Hata: {str(e)}", "red")
                        finally:
                            ghost_app.is_busy = False
                    
                    threading.Thread(target=run_chat, daemon=True).start()
                    
            elif payload.get("type") == "diff_response":
                action_id = payload.get("action_id")
                approved = payload.get("approved", False)
                reason = payload.get("reason", "")
                
                if action_id in ghost_app.pending_diffs:
                    event, result_holder = ghost_app.pending_diffs.pop(action_id)
                    result_holder["approved"] = approved
                    result_holder["reason"] = reason
                    event.set()

    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.get("/api/sessions")
def get_sessions():
    return list_sessions(limit=50)

@app.get("/api/sessions/{session_id}")
def get_session(session_id: str):
    data = load_session(session_id)
    ghost_app.current_session_id = session_id
    ghost_app.messages = data.get("messages", [])
    if hasattr(ghost_app.command_handler.controller, "supervisor"):
        ghost_app.command_handler.controller.supervisor.load_history(ghost_app.messages)
    return data

if __name__ == "__main__":
    import uvicorn
    print("Ghost Backend Server başlatılıyor (Port 8000)...")
    uvicorn.run(app, host="127.0.0.1", port=8000)
