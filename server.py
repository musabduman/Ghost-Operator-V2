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
        self.loop = None

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        self.loop = asyncio.get_running_loop()

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except:
                self.active_connections.remove(connection)

    def broadcast_sync(self, message: dict):
        """Thread-safe way to broadcast from synchronous threads"""
        if self.loop is None:
            return
        asyncio.run_coroutine_threadsafe(self.broadcast(message), self.loop)

manager = ConnectionManager()

from handler.voice_handler import VoiceHandler
from ai.konus import GhostSpeech

class WebGhostApp:
    def __init__(self):
        self.voice_mode = False
        self._expanded = True
        self.messages = []
        self.current_session_id = new_session_id()
        self.voice_handler = VoiceHandler(self)
        self.konus = GhostSpeech(self)
        self.command_handler = CommandHandler(self)
        self.is_busy = False
        self.pending_diffs = {}  # { action_id: (event, result_holder) }

    def log(self, text, tag=""):
        manager.broadcast_sync({"type": "log", "text": text, "tag": tag})

    def record_message(self, role, text):
        self.messages.append({"role": role, "text": text})
        manager.broadcast_sync({"type": "message", "role": role, "text": text})
        
    def broadcast_stream_start(self):
        manager.broadcast_sync({"type": "chat_stream_start"})

    def broadcast_stream(self, chunk):
        manager.broadcast_sync({"type": "chat_stream", "chunk": chunk})
        
    def broadcast_thinking(self):
        manager.broadcast_sync({"type": "chat_thinking"})

    def set_model_label(self, text, color=""):
        manager.broadcast_sync({"type": "status", "text": text})

    def after(self, delay, func):
        threading.Timer(delay/1000.0, func).start()

    def update(self):
        pass

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
    
    # Send existing messages to the new client
    for msg in ghost_app.messages:
        await websocket.send_json({"type": "message", "role": msg.get("role"), "text": msg.get("text")})
        
    try:
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)
            
            if payload.get("type") == "chat":
                msg = payload.get("text", "")
                if msg:
                    ghost_app.command_handler.handle(voice_text=msg)
                    
            elif payload.get("type") == "diff_response":
                action_id = payload.get("action_id")
                approved = payload.get("approved", False)
                reason = payload.get("reason", "")
                
                if action_id in ghost_app.pending_diffs:
                    event, result_holder = ghost_app.pending_diffs.pop(action_id)
                    result_holder["approved"] = approved
                    result_holder["reason"] = reason
                    event.set()
                    
            elif payload.get("type") == "toggle_voice":
                ghost_app.voice_mode = not ghost_app.voice_mode
                if ghost_app.voice_mode:
                    ghost_app.log("SİSTEM: Ses Modu Aktif.", "green")
                    try:
                        ghost_app.voice_handler.start_listening()
                        manager.broadcast_sync({"type": "voice_state", "state": "listening"})
                    except Exception as e:
                        ghost_app.log(f"Mikrofon başlatılamadı: {e}", "red")
                else:
                    ghost_app.log("SİSTEM: Ses Modu Kapatıldı.", "yellow")
                    try:
                        ghost_app.voice_handler.is_listening = False
                        manager.broadcast_sync({"type": "voice_state", "state": "idle"})
                    except: pass

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

# --- SETTINGS API ---
ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")

def _read_env() -> dict:
    values = {}
    if not os.path.exists(ENV_PATH): return values
    with open(ENV_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"): continue
            if "=" in line:
                k, _, v = line.partition("=")
                values[k.strip()] = v.strip().strip('"').strip("'")
    return values

def _write_env(values: dict):
    lines = []
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()
            
    updated_keys = set()
    for i, line in enumerate(lines):
        striped = line.strip()
        if not striped or striped.startswith("#"): continue
        if "=" in striped:
            k, _, _ = striped.partition("=")
            k = k.strip()
            if k in values:
                lines[i] = f'{k} = "{values[k]}"\n'
                updated_keys.add(k)
                
    for k, v in values.items():
        if k not in updated_keys:
            lines.append(f'{k} = "{v}"\n')
            
    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.writelines(lines)

from pydantic import BaseModel
from typing import Dict, Any

class SettingsPayload(BaseModel):
    env: Dict[str, str]
    prefs: Dict[str, Any]

@app.get("/api/settings")
def get_settings():
    from core.config import load_user_prefs
    return {
        "env": _read_env(),
        "prefs": load_user_prefs()
    }

@app.post("/api/settings")
def save_settings(payload: SettingsPayload):
    from core.config import save_user_prefs
    _write_env(payload.env)
    save_user_prefs(payload.prefs)
    return {"status": "success"}

# --- MEMORY API ---
@app.get("/api/memory")
def get_memory():
    try:
        from hafıza.episodic_db import EpisodicDB
        db = EpisodicDB()
        goals = db.aktif_hedefleri_getir()
        recent = db.son_olaylari_getir(20)
        return {"status": "success", "goals": goals, "recent_events": recent}
    except Exception as e:
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    import uvicorn
    print("Ghost Backend Server başlatılıyor (Port 8000)...")
    uvicorn.run(app, host="127.0.0.1", port=8000)
