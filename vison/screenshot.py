import base64
import PIL.ImageGrab
import os
import threading

# Vison modülünü doğru yoldan import ettiğinden emin ol
from vison.vison import minimax_vision_analiz  # (veya llava_vision_analiz)

# 1. AŞAMA: UI'dan Tetiklenen Ana Fonksiyon
def screenshot_al_ve_yorumla(self, soru=None):
    """
    Butona basıldığında veya F9'a basıldığında bu çalışır.
    UI sadece 'self' gönderir. Kayıt yolunu bu fonksiyon kendisi üretir.
    """
    # Kayıt yolunu otomatik belirle
    kayit_yolu = os.path.join(os.path.expanduser("~"), "ghost_screenshot.png")
    
    # Ghost'un arayüzünü gizle (kendi uygulamasının ekran görüntüsünü çekmesin)
    self.iconify()
    
    # Pencere kapandıktan 300 milisaniye sonra arka plan işlemini başlat
    self.after(300, lambda: _arka_planda_cek_ve_yorumla(self, kayit_yolu, soru))


# 2. AŞAMA: Ekranı Çeken ve Yorumlayan Arka Plan Fonksiyonu
def _arka_planda_cek_ve_yorumla(self, kayit_yolu, soru):
    try:
        # Ekranı çek ve kaydet
        ekran = PIL.ImageGrab.grab(all_screens=True)
        ekran.save(kayit_yolu)
        
        self.deiconify()
        
        girdideki_soru = self.entry.get().strip()
        if girdideki_soru:
            soru = girdideki_soru
            self.entry.delete(0, 'end')
        
        gosterilecek_soru = soru if soru else "Ekranda ne görüyorsun?"
            
        if not soru:
            soru = "Bu ekran görüntüsünde ne var? Kısaca özetle."

        self.record_message("user", gosterilecek_soru)

        # 1. YENİLİK: Modeli Vision olarak değiştir ve rengini mor yap
        self.set_model_label("Aktif Durum: Gözler Açık (Vision)...", "#a352cc") 
        
        #self.record_message("ghost", "📸 Screenshot alındı. Gözlerimi açıyorum, bekle Patron...")
        self.update()
            
        def vision_istegi():
            kod_bulundu_mu, saf_kod, mesaj = minimax_vision_analiz(soru, kayit_yolu)
            
            if kod_bulundu_mu and saf_kod:
                birlesik = f"[SİSTEM BİLGİSİ: Ekran görüntüsünden aşağıdaki kod çıkarıldı]\n{saf_kod}\n\n[KULLANICI İSTEĞİ]: {soru}"
            else:
                birlesik = f"[SİSTEM GÜNCELLEMESİ: Ghost, şu an ekrana baktın ve şunları tespit ettin:\n{mesaj}]\n\n[KULLANICI İSTEĞİ]: {soru}"
            
            # 2. YENİLİK: Vision bitti, sıra 120B ana modele geçti ibaresi
            self.set_model_label("Aktif Durum: Düşünüyor (Ana Model)...", "#00FFcc")
            
            cevap, aktif_model = self.command_handler.controller.generate(birlesik)
            
            self.after(0, lambda: self.record_message("ghost", cevap))
            
            # 3. YENİLİK: İşlem bitince son modeli ekrana yaz
            self.after(0, lambda: self.set_model_label(f"Aktif Durum: {aktif_model}", "#00FFcc"))
        
        threading.Thread(target=vision_istegi, daemon=True).start()

    except Exception as e:
        self.deiconify()
        self.after(0, lambda: self.log(f"SİSTEM HATA: Screenshot alınamadı. {e}", "red"))