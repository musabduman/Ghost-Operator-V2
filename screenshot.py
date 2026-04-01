import base64
import PIL.ImageGrab
import os
import threading
import pytesseract

from vison import groq_vision_analiz
def screenshot_çek(self, kayit_yolu, soru):
    try:
        ekran = PIL.ImageGrab.grab(all_screens=True)
        ekran.save(kayit_yolu)
        self.deiconify()
        
        # Entry'de yazı varsa onu soru olarak kullan
        girdideki_soru = self.entry.get().strip()
        if girdideki_soru:
            soru = girdideki_soru
            self.entry.delete(0, 'end')
        
        if not soru:
            soru = "Bu ekran görüntüsünde ne var? Kısaca özetle."

        self.log_text.insert("end", f"\n📸 Screenshot alındı. Ghost analiz ediyor...\n")
        self.update()
            
        def vision_istegi():
            kod_bulundu_mu, saf_kod, mesaj= groq_vision_analiz(soru, kayit_yolu)
            if kod_bulundu_mu:
                self.after(0, lambda: self.log_text.insert("end", f"SİSTEM: Groq ekranda kod tespit etti! Uzman modele paslanıyor...\n", "green"))
            
            # GUI GÜNCELLEMELERİ ANA THREAD'E YÖNLENDİRİLDİ
            self.after(0, lambda: self.log_text.insert("end", f"Ghost (Vision): {mesaj}\n"))
            self.after(0, lambda: self.log_text.see("end"))
    
        threading.Thread(target=vision_istegi, daemon=True).start()

    except Exception as e:
        self.deiconify()
        self.log_text.insert("end", f"SİSTEM HATA: Screenshot alınamadı. {e}\n")
        self.log_text.see("end")

def screenshot_al_ve_yorumla(self, soru=None):
    kayit_yolu = os.path.join(os.path.expanduser("~"), "ghost_screenshot.png")
    
    # Ghost'u küçült, ekranı yakala, geri aç
    self.iconify()
    self.after(300, lambda: screenshot_çek(self, kayit_yolu, soru))
