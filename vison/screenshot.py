import base64
import PIL.ImageGrab
import os
import threading

# Vison modülünü doğru yoldan import ettiğinden emin ol
from vison.vison import groq_vision_analiz

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

        # UI Kuralı: Sistemi log yerine doğrudan chat balonuna yansıt
        self.record_message("ghost", "📸 Screenshot alındı. Gözlerimi açıyorum, bekle Patron...")
        self.update()
            
        def vision_istegi():
            kod_bulundu_mu, saf_kod, mesaj = groq_vision_analiz(soru, kayit_yolu)
            
            if kod_bulundu_mu and saf_kod:
                # Kodu + kullanıcı sorusunu ana modele (120b) ilet
                # O zaten gerekirse Qwen'e [KOD_ISTE] ile yönlendirecek
                birlesik = f"Ekran görüntüsünden çıkarılan kod:\n\n{saf_kod}\n\nKullanıcının isteği: {soru}"
                cevap, aktif_model = self.command_handler.controller.generate(birlesik)
                self.after(0, lambda: self.record_message("ghost", cevap))
            else:
                # Kod yok, LLaVA'nın yorumunu direkt göster
                self.after(0, lambda: self.record_message("ghost", mesaj))
                threading.Thread(target=vision_istegi, daemon=True).start()

    except Exception as e:
        self.deiconify()
        self.after(0, lambda: self.log(f"SİSTEM HATA: Screenshot alınamadı. {e}", "red"))

def screenshot_al_ve_yorumla(self, soru=None):
    kayit_yolu = os.path.join(os.path.expanduser("~"), "ghost_screenshot.png")
    
    self.iconify()
    self.after(300, lambda: screenshot_çek(self, kayit_yolu, soru))