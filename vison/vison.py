import base64
import re
import requests

OLLAMA_URL = "http://localhost:11434/api/chat"
VISION_MODEL = "llava:latest"  # veya llava:13b, llava:34b ne indirdiysen

def groq_vision_analiz(soru, resim_yolu):
    try:
        with open(resim_yolu, "rb") as f:
            encoded_string = base64.b64encode(f.read()).decode('utf-8')

        yonetici_sorusu = f"""
        {soru}
        
        Eğer ekranda yazılım kodu görürsen, o kodu [KOD_BASLANGICI] ve [KOD_BITISI] etiketleri arasına yaz.
        Kod yoksa sadece ekranı açıkla.
        """

        payload = {
            "model": VISION_MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": yonetici_sorusu,
                    "images": [encoded_string]  # Ollama böyle alıyor
                }
            ],
            "stream": False,
            "options": {"temperature": 0.2}
        }

        response = requests.post(OLLAMA_URL, json=payload, timeout=120)
        cevap = response.json()["message"]["content"]

        kod_eslesme = re.search(r'\[KOD_BASLANGICI\](.*?)\[KOD_BITISI\]', cevap, re.DOTALL)
        
        if kod_eslesme:
            cikarilan_kod = kod_eslesme.group(1).strip()
            return True, cikarilan_kod, f"Kod tespit edildi.\n\n{cikarilan_kod[:150]}..."

        return False, None, cevap

    except Exception as e:
        return False, None, f"Vision Hatası: {str(e)}"