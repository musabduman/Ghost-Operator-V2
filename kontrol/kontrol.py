import webbrowser
import keyboard

def google_arama(sorgu):
        # Arama sorgusunu Google formatına çevir ve tarayıcıda aç
        url = f"https://www.google.com/search?q={sorgu}"
        webbrowser.open(url)
        return True

def muzik_kontrol(islem):
    # Windows medya tuşlarını simüle et (Spotify, Tarayıcı vs. her şeyde çalışır)
    try:
        if islem == "sonraki":
            keyboard.send("next track")
        elif islem == "önceki":
            keyboard.send("previous track")
        elif islem in ["durdur", "başlat", "oynat"]:
            keyboard.send("play/pause media")
        return True
    except:
        return False