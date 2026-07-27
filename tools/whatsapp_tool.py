"""
Ghost Operator - WhatsApp Web Tool
Tarayıcı (Playwright) + Vision kombinasyonu ile WhatsApp Web etkileşimi.

Mimari:
- DOM (get_by_placeholder / locator + click)  -> HAREKET: sohbet açma, yazma, gönderme
- Screenshot + Vision                          -> OKUMA: gelen mesajları anlama

Neden ikiye ayırdık: WhatsApp Web'in mesaj listesi virtualized (scroll'da
DOM'dan silinip yeniden oluşuyor), ayrıca resim/sesli mesaj/reaksiyon/okundu
tiki gibi şeyler DOM text'inde anlamlı çıkmıyor. Bu yüzden "okuma" işini
ekran görüntüsü + vision modele bırakıyoruz, DOM'u sadece tıklama/yazma
için kullanıyoruz.

Oturum kalıcılığı:
launch_persistent_context ile bir user_data_dir kullanıyoruz. İlk
çalıştırmada QR kod okutman gerekiyor (headless=False bu yüzden şart),
sonrasında session cookie'leri diskte kaldığı için bir daha QR istemiyor.
"""

import os
import time
from playwright.sync_api import sync_playwright

# ── Oturum durumu (modül seviyesinde singleton) ─────────────────────────────
# Her çağrıda sıfırdan tarayıcı açmıyoruz - hem yavaş olur hem de WhatsApp
# Web oturumu (QR eşleşmesi) taze bir context'te sürekli bozulur.
_playwright = None
_context = None
_page = None

USER_DATA_DIR = os.path.join(
    os.path.expanduser("~"), "Desktop", "Ghost_Memory", "whatsapp_session"
)

# WhatsApp Web arayüz dili TR/EN olabilir - ikisini de deniyoruz
CHAT_LIST_SELECTOR = 'div[aria-label="Sohbet listesi"], div[aria-label="Chat list"]'
MESAJ_KUTUSU_SELECTOR = 'div[aria-label="Yazışma metni girişi"], div[aria-label="Type a message"]'


def _get_page():
    """Tarayıcıyı (varsa) canlı tutar, yoksa açar/oturumu geri yükler."""
    global _playwright, _context, _page

    if _page is not None:
        try:
            _page.title()  # sayfa/tarayıcı hâlâ ayakta mı diye ufak bir yoklama
            return _page
        except Exception:
            _playwright = None
            _context = None
            _page = None

    os.makedirs(USER_DATA_DIR, exist_ok=True)
    _playwright = sync_playwright().start()
    _context = _playwright.chromium.launch_persistent_context(
        USER_DATA_DIR,
        headless=False,
        viewport={"width": 1280, "height": 800},
    )
    _page = _context.pages[0] if _context.pages else _context.new_page()
    _page.goto("https://web.whatsapp.com", wait_until="domcontentloaded", timeout=30000)

    # İlk açılışta QR taraması gerekebilir - sohbet listesi görünene kadar bekle
    try:
        _page.wait_for_selector(CHAT_LIST_SELECTOR, timeout=90000)
    except Exception:
        # Selector WhatsApp güncellemesiyle değişmiş olabilir, sessizce geç -
        # sonraki adımlar zaten kendi hata kontrollerini yapıyor
        pass

    return _page


def whatsapp_kapat():
    """Tarayıcı oturumunu kapatır (Ghost kapanırken _on_close içinden
    çağırman iyi olur, arka planda açık tarayıcı kalmasın)."""
    global _playwright, _context, _page
    try:
        if _context:
            _context.close()
        if _playwright:
            _playwright.stop()
    except Exception as e:
        print(f"[WHATSAPP] Kapatma hatası: {e}")
    finally:
        _playwright = None
        _context = None
        _page = None


def whatsapp_sohbet_ac(kisi_adi: str) -> str:
    """Arama kutusuna kişi/grup adını yazar, ilk sonuca tıklayarak sohbeti açar."""
    try:
        page = _get_page()

        # 1. GÜNCELLEME: Arama kutusunu sol paneldeki (side) yazılabilir alana göre daha genel bir yöntemle buluyoruz.
        arama_kutusu = page.locator('div[id="side"] div[contenteditable="true"]').first
        
        if arama_kutusu.count() == 0:
            return "HATA: Arama kutusu bulunamadı. WhatsApp arayüzü tam yüklenmemiş olabilir."

        arama_kutusu.click()
        arama_kutusu.fill(kisi_adi)
        page.wait_for_timeout(1500)  # Arama sonuçlarının gelmesini bekle

        # 2. GÜNCELLEME: Kişiyi bulurken doğrudan isim text'ine (title) odaklanıyoruz.
        kisi_elementi = page.locator(f'span[title="{kisi_adi}"]').first
        
        # Eğer title ile bulamazsa, sol menü (pane-side) içinde ismi içeren herhangi bir öğeyi arar.
        if kisi_elementi.count() == 0:
            kisi_elementi = page.locator('div[id="pane-side"]').get_by_text(kisi_adi, exact=False).first
            
        if kisi_elementi.count() == 0:
            return f"HATA: '{kisi_adi}' için sohbet bulunamadı."

        kisi_elementi.click()
        page.wait_for_timeout(1000)
        
        return f"'{kisi_adi}' sohbeti açıldı."

    except Exception as e:
        return f"WhatsApp sohbet açma hatası: {str(e)}"


def whatsapp_mesaj_gonder(kisi_adi: str, mesaj: str) -> str:
    """Belirtilen kişiye sohbeti açıp mesaj yazar ve gönderir."""
    try:
        page = _get_page()

        acma_sonucu = whatsapp_sohbet_ac(kisi_adi)
        if acma_sonucu.startswith("HATA"):
            return acma_sonucu

        # 3. GÜNCELLEME: Mesaj kutusunu aria-label (dil bağımlı) yerine, daima var olan footer içindeki contenteditable ile buluyoruz.
        mesaj_kutusu = page.locator('footer div[contenteditable="true"]').first
        
        if mesaj_kutusu.count() == 0:
            return "HATA: Mesaj yazma kutusu bulunamadı (WhatsApp DOM yapısı değişmiş veya sohbet aktif değil)."

        mesaj_kutusu.click()
        mesaj_kutusu.fill(mesaj)
        page.wait_for_timeout(500)
        mesaj_kutusu.press("Enter")
        page.wait_for_timeout(1000) # Mesajın sunucuya iletilmesi için kısa bir bekleme

        return f"'{kisi_adi}' kişisine mesaj gönderildi: \"{mesaj}\""

    except Exception as e:
        return f"WhatsApp mesaj gönderme hatası: {str(e)}"

def _varsayilan_wa_vision(screenshot_path: str) -> str:
    """vision_yorumla_fn verilmezse kullanılan varsayılan wrapper.
    minimax_vision_analiz'i (soru, resim_yolu) -> (kod_bulundu_mu, saf_kod,
    mesaj) imzasıyla WhatsApp'a özel bir soruyla çağırıp sadece mesaj
    kısmını döndürür. Kod tespiti burada anlamsız olduğu için o kısmı
    kullanmıyoruz.

    Lazy import: bu dosya vison/ modülüne sert bağımlı olmasın diye
    import'u fonksiyon içinde tutuyoruz - whatsapp_tool.py'yi vison
    kurulu olmayan bir ortamda da (örn. sadece DOM testleri için)
    import edebilesin.
    """
    from vison.vison import minimax_vision_analiz

    soru = (
        "Bu bir WhatsApp Web sohbet ekranı. Ekranda görünen mesajları "
        "kimden geldiğini, sırasını ve içeriğini (metin/resim/sesli mesaj/"
        "reaksiyon gibi) kısaca özetle. Kod arama, sadece sohbeti anlat."
    )
    _, _, mesaj = minimax_vision_analiz(soru, screenshot_path)
    return mesaj


def whatsapp_ekrani_yorumla(vision_yorumla_fn=None) -> str:
    """Açık olan sohbetin ekran görüntüsünü alır ve vision fonksiyonuna
    yorumlatır. Mesajları OKUMA işini burada yapıyoruz (bkz. dosya başındaki
    mimari notu).

    vision_yorumla_fn: (screenshot_path: str) -> str imzasında bir fonksiyon.
    Verilmezse _varsayilan_wa_vision kullanılır (minimax_vision_analiz'i
    WhatsApp'a özel bir soruyla çağırır). command_handler'dan farklı bir
    model/soru şablonu kullanmak istersen kendi fonksiyonunu geçebilirsin.

    Not: minimax_vision_analiz her çağrıda keep_alive=0 kullanıyor, yani
    her okumada vision modeli yeniden yükleniyor. Sık sık ekran okutacaksan
    (örn. sohbeti aktif takip ederken) bu yavaşlık yaratır - o senaryoda
    vison.py'deki keep_alive değerini ayrı bir profil için değiştirmeyi
    düşünebilirsin.
    """
    try:
        page = _get_page()

        screenshot_dir = os.path.join(
            os.path.expanduser("~"), "Desktop", "Ghost_Memory", "whatsapp_screenshots"
        )
        os.makedirs(screenshot_dir, exist_ok=True)
        screenshot_path = os.path.join(screenshot_dir, f"wa_{int(time.time())}.png")

        page.screenshot(path=screenshot_path)

        yorumla = vision_yorumla_fn or _varsayilan_wa_vision
        return yorumla(screenshot_path)

    except Exception as e:
        return f"WhatsApp ekran yorumlama hatası: {str(e)}"