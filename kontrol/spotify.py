import spotipy
import os
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv

# .env dosyasının tam yolunu gösteriyoruz ki CWD neresi olursa olsun bulabilsin
env_path = r"C:\Users\dum4n\Desktop\vs.code\asistan\apı_key.env"

load_dotenv(dotenv_path=env_path)

# --- AYARLAR ---
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI") # Dashboard'daki ile birebir aynı olmalı

# İzinler: Şarkı değiştirme, durdurma ve şu an çalanı görme
SCOPE = "user-modify-playback-state user-read-playback-state user-read-currently-playing playlist-read-private playlist-read-collaborative"

class SpotifyManager:
    def __init__(self):
        self.sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            redirect_uri=REDIRECT_URI,
            scope=SCOPE,
            open_browser=True # Giriş için tarayıcıyı otomatik açar
        ))

    def current_track(self):
        """Şu an çalan şarkı bilgisini döndürür."""
        track = self.sp.current_user_playing_track()
        if track and track['is_playing']:
            return f"{track['item']['artists'][0]['name']} - {track['item']['name']}"
        return "Şu an müzik çalmıyor."
        
    def play_specific_song(self, song_name):
        try:
            devices = self.sp.devices()
            if not devices['devices']:
                raise spotipy.exceptions.SpotifyException(404, -1, "No active device")

            device_id = None
            for d in devices['devices']:
                if d['is_active']:
                    device_id = d['id']
                    break
            if not device_id:
                device_id = devices['devices'][0]['id']

            result = self.sp.search(q=song_name, type="track", limit=1)
            tracks = result['tracks']['items']
            if not tracks:
                return f"Patron, '{song_name}' diye bir şey bulamadım."

            track_uri = tracks[0]['uri']
            track_name = tracks[0]['name']
            artist_name = tracks[0]['artists'][0]['name']

            self.sp.start_playback(device_id=device_id, uris=[track_uri])
            return f"BAŞARILI: '{artist_name} - {track_name}' çalmaya başladı. KESİNLİKLE sadece [GOREV_BITTI: ...] ile bitir."

        except spotipy.exceptions.SpotifyException as e:
            if e.http_status == 404 or "No active device" in str(e) or "NO_ACTIVE_DEVICE" in str(e):
                raise
            # 404 dışı ama playback ile ilgili bir hata da genelde cihaz kaynaklıdır
            raise spotipy.exceptions.SpotifyException(e.http_status, -1, f"DEVICE_ISSUE: {e}")
        
        
    def wake_active_device(self):
        devices = self.sp.devices()
        if not devices['devices']:
            return None
        device_id = devices['devices'][0]['id']
        self.sp.transfer_playback(device_id=device_id, force_play=False)
        return device_id

    def play_playlist(self, playlist_name):
        """Kullanıcının kendi kütüphanesindeki bir çalma listesini bulup açar."""
        try:
            # 1. Cihaz kontrolü (Önceki hatayı yaşamamak için)
            devices = self.sp.devices()
            if not devices['devices']:
                return "Patron, açık bir Spotify bulamadım. Uygulamayı açar mısın?"
            
            device_id = None
            for d in devices['devices']:
                if d['is_active']:
                    device_id = d['id']
                    break
            if not device_id:
                device_id = devices['devices'][0]['id']

            # 2. Senin kütüphane listelerini çek (Son 50 listeye bakar)
            playlists = self.sp.current_user_playlists(limit=50)
            hedef_uri = None
            gercek_isim = None

            # 3. İsimleri karşılaştırarak listeyi bul
            for pl in playlists['items']:
                if playlist_name.lower() in pl['name'].lower():
                    hedef_uri = pl['uri']
                    gercek_isim = pl['name']
                    break
            
            if not hedef_uri:
                return f"Patron, kütüphanende '{playlist_name}' adında bir liste bulamadım."

            # 4. Çalma listesini başlat (context_uri kullanıyoruz dikkat et!)
            self.sp.start_playback(device_id=device_id, context_uri=hedef_uri)
            return f"BAŞARILI: '{gercek_isim}' listesi başlatıldı. Lütfen bir daha [PLAYLIST_AÇ] aracını ÇAĞIRMA. İşlemi sonlandırmak için KESİNLİKLE [GOREV_BITTI: <nihai_cevap>] etiketini kullan."

        except spotipy.exceptions.SpotifyException as e:
            return f"Çalma listesi açılamadı. Detay: {e}"
           
    def next_track(self):
        self.sp.next_track()
        return "Bir sonraki şarkıya geçildi."

    def previous_track(self):
        self.sp.previous_track()
        return "Önceki şarkıya dönüldü."

    def pause_playback(self):
        self.sp.pause_playback()
        return "Müzik durduruldu."

    def start_playback(self):
        self.sp.start_playback()
        return "Müzik devam ettiriliyor."

# Test etmek için alt kısmı kullanabilirsin
if __name__ == "__main__":
    spotify = SpotifyManager()
    print(spotify.current_track())