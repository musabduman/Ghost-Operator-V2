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
            Sen bir veri etiketleyicisin. Tek görevin şu:

            Kullanıcı mesajı kalıcı bir GERÇEK BİLGİ içeriyor mu?
            - Evet → tek cümleyle özetle, 3. şahısla yaz
            - Hayır → sadece BOS yaz

            BOS olacak örnekler:
            - Sorular, selamlaşma, onaylama, komutlar

            SADECE özet veya BOS yaz. Başka hiçbir şey yazma.

            ÖRENKELER:
            Aşağıdaki örneklere göre etiketle:

            Mesaj: "Nasılsın?"
            Çıktı: BOS

            Mesaj: "Ghost Operator'ı Ollama ile entegre ettim."
            Çıktı: Kullanıcı Ghost Operator'ı Ollama ile entegre etti.

            Mesaj: "Tamam anladım"
            Çıktı: BOS

            Mesaj: "RTX 4050 kullanıyorum"
            Çıktı: Kullanıcının GPU'su RTX 4050'dir.

            Şimdi etiketle:
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