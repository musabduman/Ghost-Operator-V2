"""
Ghost Operator - WhatsApp Web Tool
Tarayıcı (Playwright) + Vision kombinasyonu ile WhatsApp Web etkileşimi.

Mimari:
- WhatsAppWorker (Thread-safe singleton): Playwright nesneleri sadece tek bir
  arka plan thread'i içinde yaşar. Komutlar handler/UI thread'lerinden Queue
  aracılığıyla bu worker'a iletilir. Bu sayede Playwright Sync API'nin
  thread'ler arası çökmesi engellenir.
- Lock Dosyası Temizliği: Eski oturumlardan kalan kilit (SingletonLock/LOCK)
  dosyaları Chromium başlatılmadan önce otomatik temizlenir.
- DOM (locator + click/fill) -> HAREKET: sohbet açma, yazma, gönderme
- Screenshot + Vision         -> OKUMA: gelen mesajları anlama
"""

import os
import time
import queue
import threading
from playwright.sync_api import sync_playwright

USER_DATA_DIR = os.path.join(
    os.path.expanduser("~"), "Desktop", "Ghost_Memory", "whatsapp_session"
)

# WhatsApp Web arayüz dili TR/EN seçicileri
CHAT_LIST_SELECTOR = 'div[id="pane-side"], div[id="side"]'


def _clean_lock_files():
    """Önceki beklenmeyen kapanışlardan kalan kilit dosyalarını temizler."""
    if not os.path.exists(USER_DATA_DIR):
        return
    lock_files = [
        "lockfile",
        "LOCK",
        "DevToolsActivePort",
        "SingletonLock",
        "SingletonCookie",
        "SingletonSocket",
    ]
    for root, dirs, files in os.walk(USER_DATA_DIR):
        for f in files:
            if f in lock_files or f.startswith("Singleton"):
                file_path = os.path.join(root, f)
                try:
                    os.remove(file_path)
                except Exception:
                    pass


class _WhatsAppWorker(threading.Thread):
    def __init__(self):
        super().__init__(name="WhatsAppWorker", daemon=True)
        self.cmd_queue = queue.Queue()
        self._playwright = None
        self._context = None
        self._page = None

    def run(self):
        while True:
            cmd, args, resp_queue = self.cmd_queue.get()
            if cmd == "stop":
                self._close_browser()
                resp_queue.put("Oturum kapatıldı.")
                self.cmd_queue.task_done()
                break

            try:
                res = self._handle_cmd(cmd, args)
                resp_queue.put(res)
            except Exception as e:
                resp_queue.put(f"WhatsApp İşlem Hatası: {e}")
            finally:
                self.cmd_queue.task_done()

    def _ensure_browser(self):
        if self._page is not None:
            try:
                self._page.title()
                return self._page
            except Exception:
                self._close_browser()

        _clean_lock_files()
        os.makedirs(USER_DATA_DIR, exist_ok=True)

        try:
            self._playwright = sync_playwright().start()
            self._context = self._playwright.chromium.launch_persistent_context(
                USER_DATA_DIR,
                headless=False,
                viewport={"width": 1280, "height": 800},
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled",
                    "--no-first-run",
                    "--no-default-browser-check",
                ],
            )
            self._page = self._context.pages[0] if self._context.pages else self._context.new_page()
            self._page.goto("https://web.whatsapp.com", wait_until="domcontentloaded", timeout=30000)

            # İlk açılışta yüklenmesini bekle
            try:
                self._page.wait_for_selector(CHAT_LIST_SELECTOR, timeout=15000)
            except Exception:
                pass

            return self._page
        except Exception as e:
            self._close_browser()
            raise Exception(f"Playwright/Chromium başlatılamadı: {e}")

    def _close_browser(self):
        try:
            if self._context:
                self._context.close()
        except Exception:
            pass
        try:
            if self._playwright:
                self._playwright.stop()
        except Exception:
            pass
        self._page = None
        self._context = None
        self._playwright = None

    def _handle_cmd(self, cmd: str, args: dict) -> str:
        if cmd == "kapat":
            self._close_browser()
            return "WhatsApp oturumu kapatıldı."

        page = self._ensure_browser()

        # QR kodu açık mı kontrol et
        if page.locator('canvas, div[data-ref]').count() > 0 and page.locator('div[id="side"]').count() == 0:
            return (
                "WhatsApp Web henüz oturum açmamış görünüyor (QR Kodu ekranı). "
                "Lütfen açılan tarayıcıdaki QR kodunu telefonunuzdan taratın."
            )

        if cmd == "sohbet_ac":
            kisi_adi = args["kisi_adi"]

            # Arama kutusuna ulaş (WhatsApp güncel DOM yapısına uyumlu çoklu seçici)
            arama_kutusu = page.locator(
                'input[placeholder*="Aratın"], '
                'input[placeholder*="Search"], '
                'input[aria-label*="Aratın"], '
                'input[aria-label*="Search"], '
                'div[id="side"] input, '
                'div[id="side"] div[contenteditable="true"], '
                'div[id="side"] [role="textbox"], '
                'div[aria-label="Arama metni girişi"], '
                'div[aria-label="Search input text box"]'
            ).first

            if arama_kutusu.count() == 0:
                return "HATA: WhatsApp arama kutusu bulunamadı. WhatsApp arayüzü tam yüklenmemiş olabilir."

            arama_kutusu.click()
            # Önceki aramayı temizle
            page.keyboard.press("Control+A")
            page.keyboard.press("Backspace")
            arama_kutusu.fill(kisi_adi)
            page.wait_for_timeout(1500)

            # Kişiyi ismiyle veya liste içindeki metniyle bul
            kisi_elementi = page.locator(f'span[title="{kisi_adi}"]').first
            if kisi_elementi.count() == 0:
                kisi_elementi = page.locator('div[id="pane-side"]').get_by_text(kisi_adi, exact=False).first
            if kisi_elementi.count() == 0:
                kisi_elementi = page.locator(f'span:has-text("{kisi_adi}")').first

            if kisi_elementi.count() == 0:
                return f"HATA: '{kisi_adi}' için WhatsApp üzerinde sohbet bulunamadı."

            kisi_elementi.click()
            page.wait_for_timeout(1000)
            return f"'{kisi_adi}' sohbeti açıldı."

        elif cmd == "mesaj_gonder":
            kisi_adi = args["kisi_adi"]
            mesaj = args["mesaj"]

            acma_res = self._handle_cmd("sohbet_ac", {"kisi_adi": kisi_adi})
            if acma_res.startswith("HATA"):
                return acma_res

            # Mesaj yazma alanını bul
            mesaj_kutusu = page.locator(
                'footer div[contenteditable="true"], '
                'footer [role="textbox"], '
                'footer p.selectable-text, '
                'div[aria-label="Yazışma metni girişi"], '
                'div[aria-label="Type a message"]'
            ).first

            if mesaj_kutusu.count() == 0:
                return "HATA: Mesaj yazma kutusu bulunamadı (WhatsApp DOM yapısı değişmiş veya sohbet aktif değil)."

            mesaj_kutusu.click()
            mesaj_kutusu.fill(mesaj)
            page.wait_for_timeout(500)
            mesaj_kutusu.press("Enter")
            page.wait_for_timeout(1000)

            return f"'{kisi_adi}' kişisine mesaj gönderildi: \"{mesaj}\""

        elif cmd == "ekran_yorumla":
            vision_yorumla_fn = args.get("vision_yorumla_fn")

            screenshot_dir = os.path.join(
                os.path.expanduser("~"), "Desktop", "Ghost_Memory", "whatsapp_screenshots"
            )
            os.makedirs(screenshot_dir, exist_ok=True)
            screenshot_path = os.path.join(screenshot_dir, f"wa_{int(time.time())}.png")

            page.screenshot(path=screenshot_path)

            yorumla = vision_yorumla_fn or self._varsayilan_wa_vision
            return yorumla(screenshot_path)

        return "Bilinmeyen komut."

    @staticmethod
    def _varsayilan_wa_vision(screenshot_path: str) -> str:
        from vison.vison import minimax_vision_analiz

        soru = (
            "Bu bir WhatsApp Web sohbet ekranı. Ekranda görünen mesajları "
            "kimden geldiğini, sırasını ve içeriğini (metin/resim/sesli mesaj/"
            "reaksiyon gibi) kısaca özetle. Kod arama, sadece sohbeti anlat."
        )
        _, _, mesaj = minimax_vision_analiz(soru, screenshot_path)
        return mesaj


# ── Global Singleton Yönetici ──────────────────────────────────────────────
_worker_instance = None
_worker_lock = threading.Lock()


def _get_worker() -> _WhatsAppWorker:
    global _worker_instance
    with _worker_lock:
        if _worker_instance is None or not _worker_instance.is_alive():
            _worker_instance = _WhatsAppWorker()
            _worker_instance.start()
        return _worker_instance


def _exec_wa(cmd: str, **kwargs) -> str:
    worker = _get_worker()
    resp_q = queue.Queue()
    worker.cmd_queue.put((cmd, kwargs, resp_q))
    try:
        return resp_q.get(timeout=120)
    except queue.Empty:
        return "HATA: WhatsApp işlemi zaman aşımına uğradı."


# ── Modül Dışına Açılan Fonksiyonlar ──────────────────────────────────────
def whatsapp_sohbet_ac(kisi_adi: str) -> str:
    """Arama kutusuna kişi/grup adını yazar, sohbeti açar."""
    return _exec_wa("sohbet_ac", kisi_adi=kisi_adi)


def whatsapp_mesaj_gonder(kisi_adi: str, mesaj: str) -> str:
    """Belirtilen kişiye sohbeti açıp mesaj yazıp gönderir."""
    return _exec_wa("mesaj_gonder", kisi_adi=kisi_adi, mesaj=mesaj)


def whatsapp_ekrani_yorumla(vision_yorumla_fn=None) -> str:
    """Açık olan sohbetin ekran görüntüsünü alıp vision modeli ile yorumlar."""
    return _exec_wa("ekran_yorumla", vision_yorumla_fn=vision_yorumla_fn)


def whatsapp_kapat() -> str:
    """WhatsApp oturumunu ve arka plandaki Playwright tarayıcısını kapatır."""
    return _exec_wa("kapat")