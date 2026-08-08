import os
import threading
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

# ── Yetkili kullanıcı IP/ID'leri ───────────────────────────────────────────────
# Buraya eklenmeyen hiçbir Telegram user_id mesaj gönderemez.
# Birden fazla ID eklemek için apı_key.env'de virgülle ayır: "111,222,333"
_env_ids = os.getenv("TELEGRAM_ALLOWED_IP", "1357186275")
ALLOWED_USER_IDS: set = {
    int(uid.strip()) for uid in _env_ids.split(",") if uid.strip().isdigit()
}


class TelegramBridge:
    def __init__(self, ui_callback, token: str = None):
        """
        ui_callback(text, user, chat_id): main.py'nin verdiği gerçek işleme
        fonksiyonu. Ayrı bir thread'den çağrılır, Tkinter'a dokunuyorsa
        kendi içinde self.after(0, ...) kullanmalı.
        """
        self.ui_callback = ui_callback
        self.token = token or os.getenv("TELEGRAM_BOT_TOKEN")
        if not self.token:
            raise ValueError("TELEGRAM_BOT_TOKEN eksik")
        self.app = None
        self._thread = None
        self._last_chat_id = None  # telegram_mesaj_gonder chat_id verilmezse buraya düşer

    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        user    = update.effective_user.username or update.effective_user.full_name
        text    = update.message.text
        chat_id = update.effective_chat.id

        # ── Yetki kontrolü ────────────────────────────────────────────────────
        if user_id not in ALLOWED_USER_IDS:
            print(f"[TELEGRAM GÜVENLİK] Yetkisiz erişim engellendi → user_id={user_id}, user={user}")
            try:
                url = f"https://api.telegram.org/bot{self.token}/sendMessage"
                requests.post(url, json={
                    "chat_id": chat_id,
                    "text": "⛔ Bu bot özel kullanıma aittir. Erişim yetkiniz bulunmamaktadır."
                }, timeout=10)
            except Exception:
                pass
            return  # İşleme alma, sessizce reddet

        self._last_chat_id = chat_id
        self.ui_callback(text, user, chat_id)

    def _thread_target(self):
        import time
        self.app = ApplicationBuilder().token(self.token).build()
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message))
        
        while True:
            try:
                self.app.run_polling()  # senkron, kendi event loop'unu içeride açıp kapatıyor
                break # Eğer düzgünce kapanırsa döngüden çık
            except Exception as e:
                print(f"[TELEGRAM UYARISI] Telegram sunucularına bağlanılamadı (Ağ hatası: {str(e)}). 5 saniye sonra tekrar denenecek...")
                time.sleep(5)

    def start_in_background(self):
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._thread_target, daemon=True)
        self._thread.start()

    def mesaj_gonder(self, text: str, chat_id: int = None):
        """
        Cevap gönderme. Bilerek python-telegram-bot'un kendi async bot
        client'ını kullanmıyoruz — o, _thread_target içinde açılan event
        loop'a bağlı, başka bir thread'den (Tkinter tarafından) doğrudan
        çağrılırsa event loop çakışması olur. Düz HTTP isteği bu sorunu
        tamamen ortadan kaldırıyor, thread-safe.
        """
        chat_id = chat_id or self._last_chat_id
        if not chat_id:
            raise ValueError("Henüz bilinen bir Telegram chat_id yok — Patron önce Telegram'dan bir mesaj atmalı.")

        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        response = requests.post(url, json={"chat_id": chat_id, "text": text}, timeout=15)
        response.raise_for_status()