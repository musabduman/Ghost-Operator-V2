import base64
import re
from groq import Groq

# Vision modülü, ana dosyadan bağımsız kendi bağlantısını kuruyor
client = Groq(api_key=config.groq_api_key)

def groq_vision_analiz(soru, resim_yolu):
    """
    Ekran görüntüsünü alır, API'ye gönderir ve içinde kod varsa ayıklar.
    Geriye 3 şey döndürür: (KodBulunduMu, AyiklananKod, Mesaj)
    """
    try:
        # 1. Resmi dijital şifreye (Base64) çevir
        with open(resim_yolu, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')

        # 2. Yönlendirici Promptu
        yonetici_sorusu = f"""
        {soru}
        
        GİZLİ SİSTEM TALİMATI: Sen Ghost Operator'ın baş yöneticisisin. 
        Eğer bu ekran görüntüsünde bir yazılım kodu (Python, C, Dart vs.) görürsen, o kodu TASTAMAM çıkar ve SADECE [KOD_BASLANGICI] ile [KOD_BITISI] etiketleri arasına yaz. 
        Eğer kod yoksa, sadece resmi normal bir şekilde açıkla.
        DETAYLI BİR ŞEKİLDE OKU 
        Örnek:
            Bir şarkı listesindeki şarkıların isimlerini oku.
        """

        mesajlar = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": yonetici_sorusu},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{encoded_string}"},
                    },
                ],
            }
        ]

        # 3. Groq'a gönder
        response = client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct", 
            messages=mesajlar,
            temperature=0.2
        )
        cevap = response.choices[0].message.content

        # 4. Kod ayıklayıcı (Regex)
        kod_eslesme = re.search(r'\[KOD_BASLANGICI\](.*?)\[KOD_BITISI\]', cevap, re.DOTALL)
        
        if kod_eslesme:
            cikarilan_kod = kod_eslesme.group(1).strip()
            # Kod bulduysa True, kodu ve mesajı yolla
            return True, cikarilan_kod, f"Groq kodu yakaladı ve ayıkladı. (Hazır olduğunda PyTorch devralacak)\n\nAyıklanan Kod:\n{cikarilan_kod[:150]}..."

        # Kod bulamadıysa False, kod yok, sadece mesajı yolla
        return False, None, cevap

    except Exception as e:
        return False, None, f"Vision API Hatası: {str(e)}"