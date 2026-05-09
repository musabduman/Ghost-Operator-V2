# core/planner.py
from ai.llm import GhostController

class PlannerAgent:
    def __init__(self):
        self.controller = GhostController()

    def plan_olustur(self, user_input: str) -> list[str]:
        prompt = f"""GİZLİ SİSTEM BİLGİSİ: Sen Ghost'un stratejik planlama merkezisin.
            Kullanıcının isteğini analiz et ve görevin karmaşıklığına göre SADECE 0 veya 1 ile cevap ver.

            KURAL 1: İstek tek bir adımla çözülebilecek basit bir eylemse (örn: müzik aç, google'da ara, klasör aç) SADECE "0" yaz. Başka hiçbir harf veya kelime kullanma.
            
            KURAL 2: Eğer çok adımlı, araştırma ve düzeltme gerektiren karmaşık bir görevse (örn: "klasörü incele, main.py'yi bul, oku ve hatayı düzelt"), ilk satıra "1" yaz. Sonraki satırlarda her bir adımı "ADIM: <görev>" formatında listele.
            
            KURAL 3 (ÇOK ÖNEMLİ): Bir dosya oluşturmak ve içine kod/metin yazmak İKİ AYRI ADIM DEĞİLDİR. Eğer kullanıcı "X dosyası oluştur ve içine Y yaz" diyorsa, bunu KESİNLİKLE tek bir adımda birleştir (Örn: "ADIM: X dosyasını oluşturup içine Y kodunu yaz"). Asla "dosyayı oluştur" ve "kodu yaz" diye ikiye bölme!

            Kullanıcı İsteği: {user_input}

            Cevap Formatı (Sıkı kurallara uy):
            0
            veya
            1
            ADIM: ...
            ADIM: ...
            """
        cevap, _ = self.controller(prompt)
        cevap = cevap.strip()
        
        # Eğer cevap 0 ile başlıyorsa tek adımlık basit komuttur
        if cevap.startswith("0"):
            return [user_input]
        
        # 1 ile başlıyorsa adımları listeye topla
        adimlar = []
        for satir in cevap.split('\n'):
            if satir.upper().strip().startswith('ADIM:'):
                # Başındaki "ADIM: " etiketini atıp net görevi alıyoruz
                adimlar.append(satir[5:].strip())
                
        # LLM'in 1 deyip adım üretmemesi (halüsinasyon) ihtimaline karşı güvenlik ağı
        if not adimlar:
            return [user_input]
            
        return adimlar