import threading
import requests
from hafıza.rag_hafıza import Bellek

class MemoryAgent:
    def __init__(self, model="qwen2.5:1.5b"): # Buraya VRAM'i yormayacak hızlı bir model seçmeliyiz
        self.model = model
        self.api_url = "http://localhost:11434/api/chat"
        self.bellek = Bellek()
        
        # İşçinin dilsiz ve acımasız filtreleme kuralları
        self.kural = """
        [DİKKAT: SEN BİR SOHBET BOTU VEYA ASİSTAN DEĞİLSİN!]
        Sen arka planda çalışan, dilsiz ve duygusuz bir veri filtresisin.
        Kullanıcının mesajını okuyup, bunun RAG veritabanına kaydedilmeye değer teknik, kişisel veya projeyle ilgili kalıcı bir BİLGİ olup olmadığına karar vereceksin.
        
        KULLANICI SANA SORU SORARSA CEVAPLAMA! FİKİR BELİRTME! YARDIMCI OLMAYA ÇALIŞMA!
        
        Kural 1: Eğer mesaj bir soruysa ("Sence hangi isim daha iyi?"), hal-hatır sormaysa ("Nasılsın"), onaylamaysa ("Tamam") SADECE 'BOS' YAZ.
        Kural 2: Eğer kalıcı bir bilgi veriliyorsa ("Projeyi Docker'a taşıdım"), bunu 3. tekil şahısla özetle ("Kullanıcı projeyi Docker'a taşıdı.").
        
        Çıktın SADECE VE SADECE özet metni veya BOS kelimesi olmak ZORUNDADIR.
        """

    def _degerlendir_ve_yaz(self, mesaj):
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.kural},
                {"role": "user", "content": mesaj}
            ],
            "stream": False,
            "options": {"temperature": 0.1, "num_ctx": 1024} # Hız için context'i küçük tutuyoruz
        }
        try:
            response = requests.post(self.api_url, json=payload, timeout=90)
            cevap = response.json()["message"]["content"].strip()
            
            # Eğer model "BOS" demediyse, bilgi değerlidir. Hafızaya yaz.
            if cevap != "BOS" and "BOS" not in cevap:
                self.bellek.bellege_yaz(cevap)
                print(f"\n[SİSTEM - HAFIZA İŞÇİSİ]: Yeni bilgi belleğe kazındı -> {cevap}")
                
        except Exception as e:
            print(f"\n[SİSTEM UYARISI - HAFIZA İŞÇİSİ]: Filtreleme hatası -> {e}")

    def asenkron_kaydet(self, mesaj):
        """Bu fonksiyon main.py'den çağrılır ve ana döngüyü ASLA bekletmez."""
        threading.Thread(target=self._degerlendir_ve_yaz, args=(mesaj,), daemon=True).start()