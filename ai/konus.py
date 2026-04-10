import asyncio
import edge_tts
import pygame
import os
import threading
import re

class GhostSpeech:
    def __init__(self):
        # Sesi burada seçiyoruz. Ahmet tok bir erkek sesi, Emel ise kadın sesidir.
        self.voice = "tr-TR-AhmetNeural" 
        self.output_file = "ghost_voice.mp3"
        
        # Pygame mixer'ı başlat (Hata vermemesi için kontrol ekledik)
        if not pygame.mixer.get_init():
            pygame.mixer.init()

    def _temizle(self, metin):
        # [Düşünce] veya [SİSTEM] gibi parantez içi yazıları okumaması için temizler
        metin = re.sub(r'\[.*?\]', '', metin)
        return metin.strip()

    def speak(self, metin, on_complete=None):
        # Arayüzün donmaması için her konuşmayı ayrı bir "işçi" (thread) yapar
        threading.Thread(target=self._run_speech, args=(metin,on_complete), daemon=True).start()

    def _run_speech(self, metin, on_complete):
        metin = self._temizle(metin)
        if not metin or len(metin) < 1:
            return

        try:
            # Sesi üret ve mp3 olarak kaydet
            asyncio.run(self._generate_audio(metin))
            # Kaydedilen sesi çal
            self._play_audio()
            if on_complete:
                on_complete()
        except Exception as e:
            print(f"Ghost Konuşma Hatası: {e}")

    async def _generate_audio(self, metin):
        communicate = edge_tts.Communicate(metin, self.voice)
        await communicate.save(self.output_file)

    def _play_audio(self):
        try:
            pygame.mixer.music.load(self.output_file)
            pygame.mixer.music.play()
            # Ses bitene kadar dosyayı kilitle (çakışma olmasın)
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)
            pygame.mixer.music.unload() 
        except Exception as e:
            print(f"Oynatma Hatası: {e}")