from fastapi import FastAPI, Request, Depends, HTTPException, Header
from pydantic import BaseModel
import threading
import sys
import os

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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)