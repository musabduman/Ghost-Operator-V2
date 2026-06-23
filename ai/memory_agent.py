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
        Sen arka planda çalışan görünmez bir veri analistisin.
        Kullanıcının mesajını okuyup, bunun KALICI HAFIZAYA yazılmaya değer; teknik, kişisel, proje odaklı veya önemli bir tercih bilgisi olup olmadığına karar vereceksin.
        
        "Naber", "Nasılsın", "Teşekkürler", "Tamam", "Hadi yapalım" gibi günlük veya geçici sohbetleri KESİNLİKLE YANITLAMA. Sadece "BOS" yaz.
        
        Eğer önemli bir bilgi varsa (Örn: "Ltx 2.3'ü güncelledim", "Şifre 1234", "Docker kullanmayı sevmiyorum"), bunu kalıcı hafızaya uygun şekilde, 3. tekil şahısla ve kısa özetleyerek yaz. 
        Örnek Çıktı: "Kullanıcı Ltx 2.3 projesini güncelledi."
        
        SADECE özet metni veya BOS yaz. Asla etiket, açıklama veya sohbet kullanma.
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
            response = requests.post(self.api_url, json=payload, timeout=10)
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