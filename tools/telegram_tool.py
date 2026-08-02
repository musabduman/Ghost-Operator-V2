import os
import threading
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters


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
        user = update.effective_user.username or update.effective_user.full_name
        text = update.message.text
        chat_id = update.effective_chat.id
        self._last_chat_id = chat_id
        self.ui_callback(text, user, chat_id)

    def _thread_target(self):
        self.app = ApplicationBuilder().token(self.token).build()
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message))
        self.app.run_polling()  # senkron, kendi event loop'unu içeride açıp kapatıyor

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