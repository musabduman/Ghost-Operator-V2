import asyncio
import edge_tts
import pygame
import os
import threading
import re
import uuid

class GhostSpeech:
    def __init__(self, app=None):
        self.voice = "tr-TR-EmelNeural" 
        
        # Pygame mixer'ı başlat
        if not pygame.mixer.get_init():
            pygame.mixer.init()

    def _temizle(self, metin):
        # 1. HATA ÇÖZÜMÜ: Eğer model [SPEAK: Merhaba] gibi bir şey üretirse, 
        # sadece SPEAK etiketini silip "Merhaba" metnini kurtarıyoruz.
        metin = re.sub(r'\[SPEAK:(.*?)\]', r'\1', metin, flags=re.IGNORECASE)
        
        # Kalan gereksiz SİSTEM veya Düşünce etiketlerini temizle
        metin = re.sub(r'\[.*?\]', '', metin)
        return metin.strip()

    def speak(self, metin, on_complete=None):
        threading.Thread(target=self._run_speech, args=(metin,on_complete), daemon=True).start()

    def _run_speech(self, metin, on_complete):
        metin = self._temizle(metin)
        
        # 2. HATA ÇÖZÜMÜ: Metin boş gelse bile mikrofonu tekrar açıp öyle çıkıyoruz.
        if not metin or len(metin) < 1:
            if on_complete:
                on_complete()
            return

        # Dosya çakışmalarını önlemek için dinamik dosya adı
        temp_file = f"ghost_voice_{uuid.uuid4().hex}.mp3"
        
        try:
            # Sesi üret ve dinamik dosyaya kaydet
            asyncio.run(self._generate_audio(metin, temp_file))
            
            # Kaydedilen sesi çal (Bu fonksiyon bitene kadar kod aşağı inmez)
            self._play_audio(temp_file)
            
        except Exception as e:
            print(f"Ghost Konuşma Hatası: {e}")
        finally:
            # 3. KESİN GÜVENLİK: Her şey bittikten sonra mikrofonu aç ve çöpü temizle
            if on_complete:
                on_complete()
                
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except:
                    pass

    async def _generate_audio(self, metin, dosya_yolu):
        communicate = edge_tts.Communicate(metin, self.voice)
        await communicate.save(dosya_yolu)

    def _play_audio(self, dosya_yolu):
        try:
            pygame.mixer.music.stop()
            pygame.mixer.music.load(dosya_yolu)
            pygame.mixer.music.play()
            
            # DOĞAL MIC LOCK: Müzik çaldığı sürece sistemi burada kilitler.
            # Mikrofon (on_complete) asla bu döngü bitmeden tetiklenemez.
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)
                
            pygame.mixer.music.unload() 
        except Exception as e:
            print(f"Oynatma Hatası: {e}")