import customtkinter as ctk
import os
import re 
import difflib
import threading
import traceback
import subprocess

from rag_hafıza import Bellek
from kontrol.güvenlik import guvenlik_kontrolu
from ai.llm import ChatLLM
from ai.llm import GhostController
from kontrol.spotify import SpotifyManager
from kontrol.kontrol import google_arama, muzik_kontrol 
from screenshot import screenshot_al_ve_yorumla

hafiza = Bellek("ghost_akis")
# SPOTIFY'I BAŞLATALIM (Importların hemen altına ekle)
ghost_spotify = SpotifyManager()

# Arayüz Ayarları
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

class GhostOperatorUI(ctk.CTk):
    
    # ← Tüm pattern'ler burada, bir kez derlenir, her yerden erişilir
    PATTERNS = {
        "klasor_ac":    re.compile(r'\[.*?OPEN_FOLDER:\s*(.*?)\]',   re.IGNORECASE),
        "uygulama_ac":  re.compile(r'\[.*?OPEN_APP:\s*(.*?)\]',      re.IGNORECASE),
        "sarki_ac":     re.compile(r'\[.*?ŞARKI_AÇ:\s*(.*?)\]',      re.IGNORECASE),
        "playlist_ac":  re.compile(r'\[.*?PLAYLIST_AÇ:\s*(.*?)\]',   re.IGNORECASE),
        "arama":        re.compile(r'\[.*?ARAMA:\s*(.*?)\]',         re.IGNORECASE),
        "not_al":       re.compile(r'\[.*?NOT_AL:\s*(.*?)\]',        re.IGNORECASE),
        "klasor_yap":   re.compile(r'\[.*?KLASOR_YAP:\s*(.*?)\]',    re.IGNORECASE),
        "dosya_oku":    re.compile(r'\[.*?DOSYA_OKU:\s*(.*?)\]',     re.IGNORECASE),
        "kodu_calistir":re.compile(r'\[.*?KODU_CALISTIR:\s*(.*?)\]', re.IGNORECASE),
        "dosya_yaz":    re.compile(r'\[DOSYA_YAZ:\s*(.*?)\]\s*<<<KOD_BASLANGIC>>>(.*?)<<<KOD_BITIS>>>', re.DOTALL | re.IGNORECASE),
        "klasor_incele":re.compile(r'\[.*?KLASOR_INCELE:\s*(.*?)\]', re.IGNORECASE)
    }
    
    def __init__(self):
        super().__init__()

        self.title("Ghost Operator v2")
        self.geometry("380x500")
        self.attributes('-alpha', 0.98) 
        # SİHİRLİ DOKUNUŞ: HER ZAMAN ÜSTTE KALSIN
        self.attributes('-topmost', True)
        
        # Başlık
        self.baslik = ctk.CTkLabel(
            self, 
            text="GHOST OPERATOR", 
            font=("Consolas", 22, "bold"), 
            text_color="#3F3F3F"  # Neon mavi/turkuaz bir renk
        )
        self.baslik.pack(pady=(10, 0))
        
        # --- YENİ EKLENEN KISIM: AKTİF MODEL GÖSTERGESİ ---
        self.model_label = ctk.CTkLabel(
            self,
            text="Aktif Zeka: Bekliyor...",
            font=("Consolas", 11, "italic"),
            text_color="#888888" # Başlangıçta sönük gri
        )
        self.model_label.pack(pady=(0, 5))
        # Log (Sohbet) Ekranı
        # fg_color="transparent" diyerek iç kutunun da şeffaf olmasını sağlıyoruz
        
        self.log_text = ctk.CTkTextbox(
            self, 
            width=340, 
            height=250, 
            font=("Consolas", 13),
            fg_color="#1e1e1e", # Çok koyu gri
            border_color="#333333",
            border_width=1
        )
        
        self.ss_button = ctk.CTkButton(
            self,
            text="📸 Ekranı Yorumla (F9)",
            width=360,
            height=35,
            font=("Consolas", 13),
            fg_color="#2a2a2a",
            hover_color="#3a3a3a",
            command=lambda: screenshot_al_ve_yorumla(self, self.entry.get().strip())
        )
        self.ss_button.pack(pady=(0, 5))
        
        self.log_text.pack(pady=10)
        self.log_text.insert("0.0", "Sistem Hazır. Patrondan komut bekliyor...\n\n")

        # Komut Giriş Alanı
        self.entry = ctk.CTkEntry(self, placeholder_text="Patrondan komut bekliyor...", width=340, height=40, font=("Consolas", 14))
        self.entry.pack(pady=(5, 20))
        
        # Enter tuşuna basınca komut_isleme fonksiyonunu çalıştır
        self.entry.bind("<Return>", self.komut_isleme)
        
        # (Diğer ayarlarının altına ekle)
        # --- DİNAMİK SAYDAMLIK TETİKLEYİCİLERİ ---
        self.bind("<FocusIn>", self.fare_ustunde)
        self.bind("<FocusOut>", self.fare_ayrildi)
        
        self.ghost_controller = GhostController()
        
        # --- RENK ETİKETLERİNİ SİSTEME ÖĞRETİYORUZ ---
        self.log_text.tag_config("green", foreground="#00FFcc") # Matrix/Neon yeşili
        self.log_text.tag_config("red", foreground="#FF3333")   # Hata kırmızısı
    
        # --- MEDYA KONTROL BUTONLARI ---
        self.medya_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.medya_frame.pack(pady=(0, 10))

        self.btn_onceki = ctk.CTkButton(self.medya_frame, text="⏮", width=40, height=30, fg_color="#333333", hover_color="#444444", command=lambda: muzik_kontrol("önceki"))
        self.btn_onceki.pack(side="left", padx=5)

        self.btn_durdur = ctk.CTkButton(self.medya_frame, text="⏯", width=40, height=30, fg_color="#333333", hover_color="#444444", command=lambda: muzik_kontrol("durdur"))
        self.btn_durdur.pack(side="left", padx=5)

        self.btn_sonraki = ctk.CTkButton(self.medya_frame, text="⏭", width=40, height=30, fg_color="#333333", hover_color="#444444", command=lambda: muzik_kontrol("sonraki"))
        self.btn_sonraki.pack(side="left", padx=5)    
    
    def fare_ustunde(self, event):
        # Fare uygulamanın üstüne gelince saydamlığı %95 yap (neredeyse tam net)
        self.attributes('-alpha', 0.98)

    def fare_ayrildi(self, event):
        # Fare uygulamadan çıkınca tekrar hayalet moduna (%60 saydam) dön
        self.attributes('-alpha', 0.60)

    def alternatif_yol_bul(self, hatali_yol):
        # Yolu ikiye böleriz: C:\Users\Musab\Documnts -> Ebeveyn: C:\Users\Musab | Aranan: Documnts
        ebeveyn_dizin = os.path.dirname(hatali_yol)
        aranan_klasor = os.path.basename(hatali_yol)

        # Eğer ebeveyn dizin gerçekten varsa, içine bakabiliriz
        if os.path.exists(ebeveyn_dizin):
            try:
                mevcut_icerik = os.listdir(ebeveyn_dizin) # O klasördeki tüm dosyaları listele
                # %50'den fazla benzeyen en iyi 1 eşleşmeyi getir
                eslesmeler = difflib.get_close_matches(aranan_klasor, mevcut_icerik, n=1, cutoff=0.5)
                
                if eslesmeler:
                    # Eşleşme bulunduysa, orijinal ebeveyn dizinle yeni doğru adı birleştirip geri yolla
                    return os.path.join(ebeveyn_dizin, eslesmeler[0])
            except Exception:
                pass # Yetki hatası vs. olursa sessizce geç
        return None

    def akilli_yol_cozucu(self, gelen_yol):
        user_home = os.path.expanduser("~") # C:\Users\dum4n
        
        # 1. Ters slashları Windows standardına çevir ve temizle
        yol = os.path.normpath(gelen_yol.strip())
        
        # 2. Eğer Ghost "C:\Users\Musab" diye başladıysa, o kısmı söküp at, gerçeğini tak
        if "Users\\" in yol:
            parcalar = yol.split("\\")
            # Parçalar: ['C:', 'Users', 'Musab', 'Desktop', 'test.py']
            if len(parcalar) > 3:
                # Sadece 'Desktop\test.py' kısmını al ve gerçek ev dizinine bağla
                yol = os.path.join(user_home, *parcalar[3:])
                
        # 3. Eğer Ghost sadece "Desktop\test.py" dediyse (başı boşsa)
        elif not yol.startswith("C:"):
            yol = os.path.join(user_home, yol)
            
        return yol

    def ghost_beyin(self, user_input):
        cevap, aktif_model = self.ghost_controller.generate(user_input)
        renk = "#00FFcc" if "oss" in aktif_model.lower() else "#FF9500" 
        self.after(0, lambda: self.model_label.configure(text=f"Aktif Zeka: {aktif_model}", text_color=renk))
        return cevap
    
    def kodu_calistir(self, dosya_yolu):
        try:
            # timeout=15 → 15 saniyede bitmezse zorla öldür (sonsuz döngü koruması)
            sonuc = subprocess.run(
                ["python", dosya_yolu],
                capture_output=True,   # stdout ve stderr'i yakala
                text=True,             # bytes değil string olarak ver
                timeout=15
            )
            
            stdout = sonuc.stdout.strip()
            stderr = sonuc.stderr.strip()
            
            # Çıktıyı temiz bir pakete sar
            return {
                "basarili": sonuc.returncode == 0,  # 0 = hatasız çalıştı
                "cikti": stdout if stdout else "(çıktı yok)",
                "hata": stderr if stderr else None
            }
        except subprocess.TimeoutExpired:
            return {"basarili": False, "cikti": None, "hata": "ZAMAN AŞIMI: Kod 15 saniyede bitmedi."}
        except Exception as e:
            return {"basarili": False, "cikti": None, "hata": str(e)}
        
    def derin_arama(self, aranan_yol):
        # Sadece en sondaki ismi al ve küçük harfe çevir (Örn: "Dart")
        aranan_isim = os.path.basename(aranan_yol).lower()
        
        # Windows'taki ana kullanıcı klasörlerini otomatik bul
        kullanici_dizini = os.path.expanduser("~")
        arama_yerleri = [
            os.path.join(kullanici_dizini, "Desktop"),
            os.path.join(kullanici_dizini, "Documents"),
            os.path.join(kullanici_dizini, "Downloads")
        ]
        
        for ana_dizin in arama_yerleri:
            if not os.path.exists(ana_dizin): 
                continue
                
            # os.walk ile klasörlerin en dibine kadar iniyoruz
            for root, dirs, files in os.walk(ana_dizin):
                for d in dirs:
                    # Klasör adının içinde "dart" kelimesi geçiyorsa bulduk demektir!
                    if aranan_isim in d.lower():
                        return os.path.join(root, d) # Gerçek yolu döndür
        return None
    
    def komut_isleme(self, event):
        # 1. KULLANICI GİRDİSİ
        self.user_input = self.entry.get()
        if not self.user_input.strip():
            return

        self.log_text.insert("end", f"\nSen: {self.user_input}\n")
        self.entry.delete(0, 'end')

        self.after(0, lambda:self.log_text.insert("end", "Ghost düşünüyor...\n"))
        self.after(0, lambda: self.model_label.configure(text="Aktif Zeka: Yönlendiriliyor...", text_color = "#888888"))

        self.update()

        # 3. ARKA PLAN İŞÇİSİ (Arayüz donmasın diye yaratılan fonksiyon)
        def gemma_istegi_yap(derinlik=0, aktif_input=None):       
            if aktif_input is None: 
                aktif_input = self.user_input

            islem_yapildi = False
            # ← KORUMA KALKANI: 2'den fazla iç içe çağrıya izin verme
            if derinlik > 2:
                self.after(0, lambda: self.log_text.insert(
                    "end", 
                    "SİSTEM: Maksimum döngü derinliğine ulaşıldı, işlem durduruldu.\n", 
                    "red"
                ))
                return 
        
            try:    
                # 1. RAG ENJEKSİYONU (Sadece kullanıcı direktifleriyse hafızayı tara)
                zenginlestirilmis_input = aktif_input
                if "GİZLİ SİSTEM BİLGİSİ" not in aktif_input:
                    # Sorulan soruya benzer geçmiş notları getir
                    hatirlananlar = hafiza.sorgula(aktif_input, limit=2)
                    
                    if hatirlananlar:
                        # Gelen liste elemanlarını birleştir
                        baglam_metni = "\n- ".join(hatirlananlar)
                        # Ghost'a soruyu sormadan önce eski anılarını fısılda
                        zenginlestirilmis_input = (
                            f"[SİSTEM NOTU: Geçmiş hafızandan şu bilgileri hatırlıyorsun:\n"
                            f"- {baglam_metni}\n"
                            f"Eğer bu bilgiler kullanıcının sorusuyla ilgiliyse cevaplarken kullan.]\n\n"
                            f"Kullanıcı Komutu: {aktif_input}"
                        )              
                # 2. Zenginleştirilmiş (veya normal) inputu beyne yolla
                cevap = self.ghost_beyin(zenginlestirilmis_input)
                    
                # --- EKRAN TEMİZLİĞİ (Sadece DOSYA_YAZ etiketini ve içindeki kodu gizler) ---
                ekran_cevabi = re.sub(
                    r'\[.*?KOD_BASLANGIC>>>.*?<<<KOD_BITIS>>>',
                    '[⚙️ Kod dosyaya yazılıyor...]',
                    cevap,
                    flags=re.IGNORECASE | re.DOTALL
                )             
                
                ekran_cevabi = re.sub(
                    r'\[KOD_ISTE:.*?\]', 
                    '[🛠️ Mühendise sinyal gönderildi...]', 
                    ekran_cevabi, 
                    flags=re.IGNORECASE
                )
                # GUI GÜNCELLEMELERİ THREAD GÜVENLİ HALE GETİRİLDİ
                self.after(0, lambda: self.log_text.insert("end", f"Ghost: {ekran_cevabi}\n"))
                self.after(0, lambda: self.log_text.see("end"))

                if not guvenlik_kontrolu(self.user_input):
                    self.after(0, lambda:self.log_text.insert("end", "SİSTEM: Tehlikeli komut algılandı! İşlem reddedildi.\n", "red"))
                    return
                
                # --- 4. KLASÖR AÇMA YAKALAYICI ---
                eşleşme = self.PATTERNS["klasor_ac"].search(cevap)
                if eşleşme:
                    klasor_yolu = self.akilli_yol_cozucu(eşleşme.group(1))
                    if os.path.exists(klasor_yolu):
                        os.startfile(klasor_yolu)
                        self.after(0, lambda:self.log_text.insert("end", f"SİSTEM: '{klasor_yolu}' başarıyla açıldı.\n", "green"))
                    else:
                        self.after(0, lambda:self.log_text.insert("end", f"SİSTEM: Ghost salladı, derin arama yapılıyor...\n"))
                        gercek_yol = self.derin_arama(klasor_yolu)
                        if gercek_yol:
                            os.startfile(gercek_yol)
                            self.after(0, lambda:self.log_text.insert("end", f"SİSTEM: Bulundu ve açıldı -> {gercek_yol}\n", "green"))
                        else:
                            self.after(0, lambda:self.log_text.insert("end", f"SİSTEM HATA: Klasör bulunamadı.\n", "red"))

                # --- 5. UYGULAMA AÇMA YAKALAYICI ---
                app_eslesme = self.PATTERNS["uygulama_ac"].search(cevap)
                if app_eslesme:
                    uygulama_adi = app_eslesme.group(1).strip().lower()
                    self.after(0, lambda:self.log_text.insert("end", f"SİSTEM: '{uygulama_adi}' başlatılıyor...\n", "green"))
                    
                    # Gizli yollar (Kendi bilgisayarına göre düzenle)
                    ozel_uygulamalar = {
                        "cursor": r"C:\Users\dum4n\AppData\Local\Programs\cursor\Cursor.exe",
                        "whatsapp": "whatsapp://",
                        "discord": r"C:\Users\dum4n\AppData\Local\Discord\Update.exe --processStart Discord.exe"
                    }
                    
                    try:
                        if uygulama_adi in ozel_uygulamalar:
                            os.startfile(ozel_uygulamalar[uygulama_adi])
                        else:
                            os.system(f"start {uygulama_adi}")
                    except Exception as e:
                        self.after(0, lambda e=e: self.log_text.insert("end", f"SİSTEM HATA: Uygulama açılamadı. {e}\n", "red"))
                
                # --- 6 SPESİFİK ŞARKI AÇMA YAKALAYICI ---
                sarki_eslesme = self.PATTERNS["sarki_ac"].search(cevap)
                if sarki_eslesme:
                    aranan_sarki = sarki_eslesme.group(1).strip()
                    self.after(0, lambda: self.log_text.insert("end", f"SİSTEM: Spotify'da '{aranan_sarki}' aranıyor...\n", "green"))
                    # Doğrudan Spotify dosyamızdaki fonksiyonu çalıştırıyoruz!
                    try:
                        sonuc = ghost_spotify.play_specific_song(aranan_sarki)
                        self.after(0, lambda: self.log_text.insert("end", f"SİSTEM: {sonuc}\n", "green"))
                    except Exception as e:
                        hata_mesaji=str(e).lower()
                        # Eğer Spotify "Aktif cihaz yok" (NO_ACTIVE_DEVICE) hatası verirse
                        if "device" in hata_mesaji or "active" in hata_mesaji or "not found" in hata_mesaji:
                
                            # B PLANI: Cihazı uyandırmak için "mesela yanii" playlistini tetikle
                            try:
                                ghost_spotify.play_playlist("mesela yanii") # Playlisti çalarak cihazı uyandır
                                import time
                                time.sleep(2) # Spotify'ın uyanması için 2 saniye bekle
                                
                                # ŞİMDİ ŞARKIYI TEKRAR ÇALMAYI DENE
                                # ... (Buraya üstteki şarkı çalma kodunu tekrar koy) ...
                                
                                self.after(0, lambda: self.log_text.insert("end", f"SİSTEM: Cihaz uyandırıldı ve '{aranan_sarki}' açıldı.\n", "green"))
                            
                            except Exception as e2:
                                return f"Cihazı uyandırma denemesi de başarısız oldu: {e2}"
                        
                        # Başka bir hataysa normal fırlat
                        raise Exception(f"Şarkı açılamadı: {e}")
                            
                # --- 6.5 PLAYLIST AÇMA YAKALAYICI ---
                playlist_eslesme = self.PATTERNS["playlist_ac"].search(cevap)
                if playlist_eslesme:
                    aranan_liste = playlist_eslesme.group(1).strip()
                    self.after(0, lambda: self.log_text.insert("end", f"SİSTEM: Spotify kütüphanesinde '{aranan_liste}' listesi aranıyor...\n", "green"))
                    
                    try:
                        # Doğrudan spotify_handler.py içindeki playlist fonksiyonunu çağırıyoruz
                        sonuc = ghost_spotify.play_playlist(aranan_liste)
                        self.after(0, lambda: self.log_text.insert("end", f"SİSTEM: {sonuc}\n", "green"))
                    except Exception as e:
                        self.after(0, lambda: self.log_text.insert("end", f"SİSTEM HATA (Spotify): {e}\n", "red"))  
                
                # --- 7. GOOGLE ARAMA YAKALAYICI ---
                arama_eslesme = self.PATTERNS["arama"].search(cevap)
                if arama_eslesme:
                    aranacak_kelime = arama_eslesme.group(1).strip()
                    google_arama(aranacak_kelime)
                    self.after(0, lambda: self.log_text.insert("end", f"SİSTEM: Google'da '{aranacak_kelime}' aranıyor...\n", "green"))
            
                # --- 8. HAFIZAYA YAZMA (ÖĞRENME) YAKALAYICI ---
                not_eslesme = self.PATTERNS["not_al"].search(cevap)
                if not_eslesme:
                    alinacak_not = not_eslesme.group(1).strip()
                    # Hafıza sınıfındaki learn fonksiyonunu tetikliyoruz!
                    hafiza.bellege_yaz(alinacak_not)
                    self.after(0, lambda: self.log_text.insert("end", f"SİSTEM: Beyne kazındı -> '{alinacak_not}'\n", "green"))
                
                # --- 9. KLASÖR OLUŞTURMA YAKALAYICI ---
                klasor_yap_eslesme = self.PATTERNS["klasor_yap"].search(cevap)
                
                if klasor_yap_eslesme:
                    klasor_yolu = self.akilli_yol_cozucu(klasor_yap_eslesme.group(1))
                    try:
                        os.makedirs(klasor_yolu, exist_ok=True)
                        self.after(0, lambda: self.log_text.insert("end", f"SİSTEM: Klasör başarıyla oluşturuldu -> {klasor_yolu}\n", "green"))
                    except Exception as e:
                        self.after(0, lambda: self.log_text.insert("end", f"SİSTEM HATA (Klasör Yap): {e}\n", "red"))

                # --- 9.5 KLASÖR İNCELEME (RÖNTGEN) YAKALAYICI ---
                klasor_incele_eslesme = self.PATTERNS["klasor_incele"].search(cevap)
                
                if klasor_incele_eslesme and not islem_yapildi:
                    incelenecek_yol = self.akilli_yol_cozucu(klasor_incele_eslesme.group(1))
                    if os.path.exists(incelenecek_yol) and os.path.isdir(incelenecek_yol):
                        dosyalar = os.listdir(incelenecek_yol)
                        liste = ", ".join(dosyalar) if dosyalar else "Klasör boş."
                        self.after(0, lambda: self.log_text.insert("end", f"SİSTEM: Klasör tarandı -> {liste}\n", "green"))
                        gizli_istek = (
                            f"GİZLİ SİSTEM BİLGİSİ: '{incelenecek_yol}' klasörünün içeriği: {liste}\n"
                            f"Kullanıcının isteğine göre doğru dosyayı seç ve işleme devam et."
                        )
                        self.user_input = gizli_istek
                        islem_yapildi = True
                        gemma_istegi_yap(derinlik + 1)
                    else:
                        self.after(0, lambda: self.log_text.insert("end", f"SİSTEM HATA: Klasör bulunamadı -> {incelenecek_yol}\n", "red"))
            
                # --- 10. DOSYA YAZMA (KOD ÜRETME) YAKALAYICI ---
                # re.DOTALL sayesinde çok satırlı kodları (enter tuşuna basılmış olsa bile) kopmadan yakalarız.
                dosya_yaz_eslesme = self.PATTERNS["dosya_yaz"].search(cevap)
                
                if dosya_yaz_eslesme:
                    raw_yolu = dosya_yaz_eslesme.group(1).strip()
                    dosya_yolu = os.path.normpath(raw_yolu)
                    kod_icerigi = dosya_yaz_eslesme.group(2).strip()
                    
                    try:
                        # Eğer dosyanın olacağı klasör yoksa, önce o klasörü otomatik oluşturur (Çökme engellendi)
                        klasor= os.path.dirname(dosya_yolu)
                        if klasor:
                            os.makedirs(klasor, exist_ok=True)

                        # Dosyayı "w" (write) modunda oluştur ve içine kodu bas
                        with open(dosya_yolu, "w", encoding="utf-8") as f:
                            f.write(kod_icerigi)
                            
                        self.after(0, lambda: self.log_text.insert("end", f"SİSTEM: Dosya başarıyla yazıldı -> {dosya_yolu}\n", "green"))
                        islem_yapildi = True # Yazma yapıldıysa okumaya geçmesini YASAKLA!
            
                    except Exception as e:
                        self.after(0, lambda e=e: self.log_text.insert("end", f"SİSTEM HATA (Dosya Yazma): {e}\n", "red"))
     
                # --- 11. KODU ÇALIŞTIRMA VE OTO-DÜZELTME YAKALAYICI ---
                calistir_eslesme = self.PATTERNS["kodu_calistir"].search(cevap)
                if calistir_eslesme:
                    calistirilacak_yol = self.akilli_yol_cozucu(calistir_eslesme.group(1))
                    self.after(0, lambda: self.log_text.insert(
                        "end", f"SİSTEM: '{calistirilacak_yol}' çalıştırılıyor...\n", "green"
                    ))               
                    # Motoru çalıştır, sonucu al
                    sonuc = self.kodu_calistir(calistirilacak_yol)
                
                    # DURUM A: Kod tertemiz çalıştı
                    if sonuc["basarili"]:
                        self.after(0, lambda: self.log_text.insert(
                            "end", f"SİSTEM ✅ Kod başarıyla çalıştı:\n{sonuc['cikti']}\n", "green"
                        ))    
                    # DURUM B: Hata var → Ghost'a gönder, düzeltmesini iste
                    else:
                        self.after(0, lambda: self.log_text.insert(
                            "end", f"SİSTEM ⚠️ Hata tespit edildi, Ghost düzeltiyor...\n", "red"
                        ))
                        
                        if derinlik < 2:
                            gizli_istek = (
                                f"GİZLİ SİSTEM BİLGİSİ: '{calistirilacak_yol}' çalıştırdım, hata:\n\n{sonuc['hata']}\n\n"
                                f"Önce [DOSYA_OKU: {calistirilacak_yol}] ile oku, hatayı düzelt ve SADECE şu formatla kaydet:\n"
                                f"[DOSYA_YAZ: {calistirilacak_yol}]\n<<<KOD_BASLANGIC>>>\n(kod)\n<<<KOD_BITIS>>>\n"
                                f"Sonra [KODU_CALISTIR: {calistirilacak_yol}] ile test et."
                            )
                            self.user_input = gizli_istek
                            islem_yapildi = True
                            gemma_istegi_yap(derinlik + 1)  # ← sayaç artıyor, limit korunuyor
                            
                            # 2 deneme de olmadı → pes etme, çıktıyı Patrona ver
                        else:
                                self.after(0, lambda: self.log_text.insert(
                                    "end", 
                                    f"SİSTEM: 2 düzeltme denemesi başarısız. Son hata:\n{sonuc['hata']}\n", 
                                    "red"
                                ))

                # --- 12. DOSYA OKUMA VE AKILLI HATA YÖNETİMİ (RÖNTGEN) ---
                dosya_oku_eslesme = self.PATTERNS["dosya_oku"].search(cevap)
                # KALKAN: Yazma yapıldıysa VEYA zaten gizli döngüdeysek tekrar okumasına ASLA izin verme!
                if dosya_oku_eslesme and not islem_yapildi and "GİZLİ SİSTEM BİLGİSİ" not in self.user_input:
                    okunacak_yol = self.akilli_yol_cozucu(dosya_oku_eslesme.group(1))
                    
                    # 1. DURUM: DOSYA GERÇEKTEN VARSA (Normal Okuma Döngüsü)
                    if os.path.exists(okunacak_yol) and os.path.isfile(okunacak_yol):
                        try:
                            with open(okunacak_yol, "r", encoding="utf-8") as f:
                                icerik = f.read()
                            
                            self.after(0, lambda: self.log_text.insert("end", f"SİSTEM: '{okunacak_yol}' okundu, Ghost analiz ediyor...\n", "green"))
                            
                            gizli_istek = (
                                f"GİZLİ SİSTEM BİLGİSİ: '{okunacak_yol}' dosyasının içeriği aşağıdadır:\n\n{icerik}\n\n"
                                f"Şimdi kullanıcının az önceki isteğine dön ve bu içeriğe göre hareket et.\n"
                                f"EĞER kullanıcı kodu değiştirmeyi, düzeltmeyi veya ekleme yapmayı istediyse, SADECE şu formatı kullanarak kodu kaydet:\n"
                                f"[DOSYA_YAZ: {okunacak_yol}]\n<<<KOD_BASLANGIC>>>\n(yeni_kod)\n<<<KOD_BITIS>>>\n\n"
                                f"EĞER kullanıcı sadece dosyayla ilgili bir soru sorduysa (örneğin 'bu ne işe yarıyor', 'kaydediyor mu' gibi), "
                                f"DOSYA_YAZ ETİKETİNİ ASLA KULLANMA. Sadece soruyu sözlü olarak, Türkçe cevapla."
                            )

                            self.user_input = gizli_istek
                            islem_yapildi = True # Döngü kalkanı
                            gemma_istegi_yap(derinlik+1)
                            
                        except Exception as e:
                            self.after(0, lambda e=e: self.log_text.insert("end", f"SİSTEM HATA (Dosya Okuma): {e}\n", "red"))
                            
                    # 2. DURUM: DOSYA YOKSA (Röntgen Gücü Devreye Girer)
                    else:
                        klasor_yolu = os.path.dirname(okunacak_yol)
                        
                        # Dosya yok ama en azından bulunduğu klasör var mı diye bakıyoruz
                        if os.path.exists(klasor_yolu) and os.path.isdir(klasor_yolu):
                            # Klasörü tara
                            dosyalar = os.listdir(klasor_yolu)
                            dosya_listesi = ", ".join(dosyalar) if dosyalar else "Klasör tamamen boş."
                            
                            self.after(0, lambda: self.log_text.insert("end", f"SİSTEM HATA: Dosya bulunamadı! Ghost klasörü röntgenliyor...\n", "red"))
                            
                            # Ghost'a durumu çaktırmadan bildirip yeni konuşma ürettiriyoruz
                            gizli_istek = f"GİZLİ SİSTEM BİLGİSİ: Okumaya çalıştığın '{okunacak_yol}' dosyası YOK. Ancak bulunduğu klasörde ({klasor_yolu}) şu dosyalar var: {dosya_listesi}. Lütfen kullanıcıya aradığı dosyanın olmadığını söyle ve klasördeki mevcut dosyaları listeleyip 'Hangisine bakıyoruz Patron?' diye kibarca sor."
                            self.user_input = gizli_istek
                            islem_yapildi = True
                            gemma_istegi_yap(derinlik+1)
                            
                        else:
                            # Ne dosya var ne de klasör! (Tamamen yanlış yol verilmiş)
                            self.after(0, lambda: self.log_text.insert("end", f"SİSTEM HATA: Klasör yolu da geçersiz!\n", "red"))
                            gizli_istek = f"GİZLİ SİSTEM BİLGİSİ: '{okunacak_yol}' tamamen geçersiz bir yol. Kullanıcıya bu yolun yanlış olduğunu bildir."
                            self.user_input = gizli_istek
                            islem_yapildi = True
                            gemma_istegi_yap(derinlik+1)

            except Exception as e:
                # Hatanın arka plandaki tüm şeceresini (hangi satırda, neden koptuğunu) çeker
                hata_detayi = traceback.format_exc()
                
                # Kalkanı (self.after) burada da kullanıyoruz ki arayüz çökmesin!
                self.after(0, lambda: self.log_text.insert("end", f"SİSTEM HATA RÖNTGENİ:\n{hata_detayi}\n", "red"))
                self.after(0, lambda : self.log_text.see("end"))

        # gemma_istegi_yap isimli iç fonksiyonu tanımlamayı bitirdik, şimdi onu arka planda başlatıyoruz.
        mevcut_input = self.user_input  # Kopyasını al, ezilmesin
        threading.Thread(target=lambda: gemma_istegi_yap(0, mevcut_input), daemon=True).start()

if __name__ == "__main__":
    app = GhostOperatorUI()
    app.mainloop()