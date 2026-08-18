from fastapi import FastAPI, Request, Depends, HTTPException, Header
from pydantic import BaseModel
import threading
import sys
import os
import core.config
core.config.USE_DOCKER_CORE = False  # SUNUCU KENDİ KENDİNE PROXY YAPMAMALIDIR!

from handler.command_handler import CommandHandler
from sessions.session_manager import save_session
from core.config import GHOST_TOKEN

app = FastAPI(title="Ghost Core Server")

async def verify_token(x_ghost_token: str = Header(None)):
    if not x_ghost_token or x_ghost_token != GHOST_TOKEN:
        raise HTTPException(status_code=403, detail="Geçersiz veya eksik Ghost Token (Güvenlik İhlali)")
    return x_ghost_token

class HeadlessApp:
    def __init__(self):
        self.voice_mode = False
        self._expanded = True
        self.messages = []
        self.current_session_id = "headless_core_session"
        self.command_handler = CommandHandler(self)
        self.is_busy = False

    def log(self, text, tag=""):
        print(f"[{tag.upper() if tag else 'INFO'}] {text}")

    def record_message(self, role, text):
        self.messages.append({"role": role, "text": text})
        print(f"\n[{role.upper()}]: {text}\n")

    def set_model_label(self, text, color=""):
        print(f">> {text}")

    def after(self, delay, func):
        threading.Timer(delay/1000.0, func).start()

headless_ghost = HeadlessApp()

class ChatRequest(BaseModel):
    message: str

@app.post("/chat", dependencies=[Depends(verify_token)])
def chat(req: ChatRequest):
    if headless_ghost.is_busy:
        return {"status": "busy", "response": "Şu an başka bir işlem yapıyorum."}
    
    headless_ghost.is_busy = True
    try:
        cevap, _ = headless_ghost.command_handler.controller(req.message)
        headless_ghost.record_message("ghost", cevap)
        return {"status": "ok", "response": cevap}
    except Exception as e:
        return {"status": "error", "response": str(e)}
    finally:
        headless_ghost.is_busy = False

@app.get("/history", dependencies=[Depends(verify_token)])
def get_history():
    return {"messages": headless_ghost.messages}

import subprocess

worker_process = None

@app.on_event("startup")
def startup_event():
    global worker_process
    worker_script = os.path.join(os.path.dirname(__file__), "core", "skill_worker.py")
    if os.path.exists(worker_script):
        worker_process = subprocess.Popen([sys.executable, worker_script])
        print(f"Skill Worker başlatıldı (PID: {worker_process.pid})")

@app.on_event("shutdown")
def shutdown_event():
    global worker_process
    if worker_process:
        worker_process.terminate()
        worker_process.wait()
        print("Skill Worker kapatıldı.")

@app.post("/restart_worker", dependencies=[Depends(verify_token)])
def restart_worker():
    global worker_process
    if worker_process:
        worker_process.terminate()
        worker_process.wait()
    worker_script = os.path.join(os.path.dirname(__file__), "core", "skill_worker.py")
    worker_process = subprocess.Popen([sys.executable, worker_script])
    return {"status": "ok", "message": "Worker yeniden başlatıldı"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)