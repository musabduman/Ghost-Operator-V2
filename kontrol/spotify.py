import spotipy
from spotipy.oauth2 import SpotifyOAuth

# --- AYARLAR ---
CLIENT_ID = "34f3acf6e935473e86e1785e9c95f60a"
CLIENT_SECRET = "f378aa54fb0f438688c06a939f760082"
REDIRECT_URI = "http://127.0.0.1:8888/callback" # Dashboard'daki ile birebir aynı olmalı

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
        """İstenen şarkıyı aratır ve anında çalmaya başlar."""
        try:
            # 1. Önce aktif cihazları bul
            devices = self.sp.devices()
            if not devices['devices']:
                return "Patron, açık bir Spotify bulamadım. Uygulamayı açıp arkada hazır bekletir misin?"
            
            # Cihaz ID'sini belirle (Eğer aktif cihaz yoksa listedeki ilk cihazı seçer)
            device_id = None
            for d in devices['devices']:
                if d['is_active']:
                    device_id = d['id']
                    break
            
            if not device_id:
                # Aktif işaretli cihaz yoksa bile listedeki ilk cihazı zorla kullan
                device_id = devices['devices'][0]['id']

            # 1. Spotify'da şarkıyı arat (Sadece track/şarkı arıyoruz)
            result = self.sp.search(q=song_name, type="track", limit=1)
            tracks = result['tracks']['items']
            
            if not tracks:
                return f"Patron, '{song_name}' diye bir şey bulamadım."
            
            # 2. Şarkının URI (Spotify ID) bilgisini al
            track_uri = tracks[0]['uri']
            track_name = tracks[0]['name']
            artist_name = tracks[0]['artists'][0]['name']

            # 3. Şarkıyı çal
            self.sp.start_playback(uris=[track_uri])
            return f"{artist_name} - {track_name} açılıyor."
            
        except spotipy.exceptions.SpotifyException as e:
            # Hata yakalama (Cihaz aktif değilse veya Premium yoksa genelde bura patlar)
            return f"Şarkı açılamadı. Spotify arka planda açık mı kontrol et patron. Detay: {e}"

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
            return f"'{gercek_isim}' listesini başlattım. Keyfini çıkar patron!"

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