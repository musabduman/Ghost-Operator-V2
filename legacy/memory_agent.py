import threading
import requests
from hafıza.rag_hafıza import Bellek


class MemoryAgent:
    def __init__(self, model="gpt-oss:20b"):
        # NOT: Bu sınıflandırma işi ağır bir model istemiyor — tek satırlık
        # bir "kalıcı bilgi mi değil mi" kararı veriyoruz. 120b-cloud yerine
        # elindeki en hızlı/hafif modeli ver (yerelde çalışan küçük bir model
        # de olur). Supervisor'la aynı ağır modeli kullanmak gereksiz maliyet.
        self.model = model
        self.api_url = "http://localhost:11434/api/chat"
        self.bellek = Bellek()

        # Aynı anda birden fazla thread bellege_yaz çağırabilir
        # (asenkron_kaydet her mesajda yeni bir thread açıyor).
        # Bellek/Chroma tarafı thread-safe olsa da olmasa da, burada
        # sıralı yazmayı garanti ediyoruz.
        self._yazma_kilidi = threading.Lock()

        # İşçinin dilsiz ve acımasız filtreleme kuralları
        self.kural = """
            Sen bir veri etiketleyicisin. Tek görevin şu:

            Kullanıcının SON mesajı kalıcı bir GERÇEK BİLGİ içeriyor mu?
            Karar verirken önceki mesajları sadece bağlam için kullan, onları etiketleme.

            - Evet → tek cümleyle özetle, 3. şahısla yaz
            - Hayır → sadece BOS yaz

            BOS olacak örnekler:
            - Sorular, selamlaşma, onaylama, komutlar
            - Önceki mesajla bağlamı olmadan anlamsız kısa cevaplar ("evet", "o da öyle")
              EĞER bağlamla birlikte gerçek bir bilgi taşıyorsa (örn: önceki mesaj
              "GPU'n ne?" ve son mesaj "RTX 4050"), bağlamı kullanarak özetle.

            SADECE özet veya BOS yaz. Başka hiçbir şey yazma.

            ÖRNEKLER:
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

    def _mesaj_govdesi_olustur(self, mesaj, gecmis_baglam=None):
        """Son mesajı, varsa önceki 1-2 mesajla birlikte modele sunar.
        Bağlamsız etiketleme kısa/atıf içeren mesajları (örn. "o da öyle")
        yanlış BOS'a düşürüyordu."""
        if not gecmis_baglam:
            return mesaj
        baglam_metni = "\n".join(f"- {m}" for m in gecmis_baglam[-2:])
        return f"[ÖNCEKİ BAĞLAM]\n{baglam_metni}\n\n[SON MESAJ]\n{mesaj}"

    def _degerlendir_ve_yaz(self, mesaj, gecmis_baglam=None):
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.kural},
                {"role": "user", "content": self._mesaj_govdesi_olustur(mesaj, gecmis_baglam)},
            ],
            "stream": False,
            "options": {"temperature": 0.1, "num_ctx": 1024},
        }
        try:
            response = requests.post(self.api_url, json=payload, timeout=90)
            response.raise_for_status()
            data = response.json()

            cevap = data["message"]["content"].strip()

            if cevap == "BOS" or "BOS" in cevap:
                return

            # Yazmadan önce Chroma'da çok benzer bir kayıt var mı diye bak.
            # Aynı bilginin (RTX 4050 gibi) her seferinde kopya olarak
            # birikmesini önlüyor.
            benzer = self.bellek.benzerini_bul(cevap)
            if benzer is not None:
                print(
                    f"\n[SİSTEM - HAFIZA İŞÇİSİ]: Zaten kayıtlı bir bilgiye çok benziyor, "
                    f"atlandı -> {cevap}\n  (mevcut kayıt: {benzer})"
                )
                return

            with self._yazma_kilidi:
                self.bellek.bellege_yaz(cevap)
            print(f"\n[SİSTEM - HAFIZA İŞÇİSİ]: Yeni bilgi belleğe kazındı -> {cevap}")

        except Exception as e:
            print(f"\n[SİSTEM UYARISI - HAFIZA İŞÇİSİ]: Filtreleme hatası -> {e}")

    def asenkron_kaydet(self, mesaj, gecmis_baglam=None):
        """main.py'den çağrılır, ana döngüyü ASLA bekletmez.

        gecmis_baglam: son 1-2 mesajı içeren opsiyonel bir liste — kısa/atıf
        içeren mesajların doğru sınıflandırılması için (opsiyonel, geriye
        dönük uyumlu; vermezsen eski davranışın aynısı)."""
        threading.Thread(
            target=self._degerlendir_ve_yaz, args=(mesaj, gecmis_baglam), daemon=True
        ).start()