import time
import threading
from hafıza.episodic_db import EpisodicDB
from hafıza.rag_hafıza import Bellek

class Scheduler:
    def __init__(self, app):
        self.app = app
        self.db = EpisodicDB()
        self.bellek = Bellek()
        self._running = False
        self._thread = None
        self._check_interval = 60  # 60 saniyede bir kontrol et

        self._sistem_gorevlerini_baslat()

    def _sistem_gorevlerini_baslat(self):
        # Eğer hafıza budama görevi yoksa ekle (24 saatte bir çalışacak şekilde)
        gorevler = self.db.calisacak_gorevleri_getir()
        budama_var = any(g["gorev_tanimi"] == "hafiza_budama" for g in gorevler)
        if not budama_var:
            self.db.gorev_ekle("hafiza_budama", 24.0, is_system_task=1)
            print("[SİSTEM - SCHEDULER]: Hafıza budama sistemi görevi kaydedildi (24 saat).")

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        print("[SİSTEM - SCHEDULER]: Arka plan işçisi (Zamanlayıcı) başlatıldı.")

    def stop(self):
        self._running = False

    def _loop(self):
        while self._running:
            try:
                self._gorevleri_kontrol_et()
            except Exception as e:
                print(f"[SİSTEM HATA - SCHEDULER]: Döngü hatası: {e}")
            
            # Ana thread'i kilitlemeden uyut
            for _ in range(self._check_interval):
                if not self._running:
                    break
                time.sleep(1)

    def _gorevleri_kontrol_et(self):
        su_an = time.time()
        gorevler = self.db.calisacak_gorevleri_getir()
        
        for gorev in gorevler:
            periyot_saniye = float(gorev["periyot_saat"]) * 3600
            son_calisma = int(gorev["son_calisma"])
            
            if (su_an - son_calisma) >= periyot_saniye:
                # Görev zamanı geldi
                print(f"[SİSTEM - SCHEDULER]: Görev tetikleniyor -> {gorev['gorev_tanimi']}")
                self._gorevi_calistir(gorev)
                self.db.gorev_calisma_zamanini_guncelle(gorev["id"])

    def _gorevi_calistir(self, gorev):
        is_system = int(gorev["is_system_task"])
        tanim = gorev["gorev_tanimi"]

        if is_system == 1:
            if tanim == "hafiza_budama":
                try:
                    sonuc = self.bellek.bellek_budamasi_yap()
                    if sonuc and sonuc != "Bellek boş, budama yapılmadı.":
                        self.db.bildirim_ekle(f"Sistem Görevi [Hafıza Budama]: {sonuc}")
                except Exception as e:
                    self.db.bildirim_ekle(f"Sistem Görevi [Hafıza Budama] Hata: {e}")
            else:
                print(f"[SİSTEM UYARISI]: Bilinmeyen sistem görevi: {tanim}")
        else:
            # LLM Görevi
            # Ghost'a arka planda çalışmasını söyleyen özel bir prompt gönderiyoruz
            prompt = f"[ZAMANLANMIŞ GÖREV TETİKLEYİCİSİ]: Sen periyodik bir görev için uyandırıldın. Görev tanımı: '{tanim}'. Lütfen bu görevi arka planda araçlarını kullanarak sessizce yerine getir. İşlemin bittiğinde kullanıcıya seslenme, sadece ne yaptığını açıklayan çok kısa bir GÖREV ÖZETİ döndür (bu özet bildirim merkezine düşecek). Eğer görev sırasında bir hata alırsan veya bilgi bulamazsan, bunu da özete ekle."
            
            threading.Thread(target=self._llm_gorevi_yurut, args=(prompt, tanim), daemon=True).start()

    def _llm_gorevi_yurut(self, prompt, tanim):
        try:
            # Ghost meşgulse bekle (thread-safety)
            while getattr(self.app.command_handler, "su_an_mesgul", False):
                time.sleep(2)
                
            self.app.command_handler.su_an_mesgul = True
            
            # Ghost'un beynine ulaşmak için GhostController kullanıyoruz
            # command_handler üzerinden erişim
            controller = self.app.command_handler.controller
            
            # Arka plan görevi olduğu için UI sohbet geçmişini kirletmemesi lazım
            cevap, model = controller.tek_seferlik_gorev(prompt)
            
            # Cevabı bildirimlere at
            self.db.bildirim_ekle(f"Görev [{tanim}]: {cevap.strip()}")
        except Exception as e:
            self.db.bildirim_ekle(f"Görev Hatası [{tanim}]: {str(e)}")
        finally:
            self.app.command_handler.su_an_mesgul = False
