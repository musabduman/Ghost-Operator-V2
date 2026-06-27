import base64
import re
import requests

OLLAMA_URL = "http://localhost:11434/api/chat"
VISION_MODEL = "minimax-m3:cloud"  # veya llava:13b, llava:34b ne indirdiysen

def llava_vision_analiz(soru, resim_yolu):
    try:
        with open(resim_yolu, "rb") as f:
            encoded_string = base64.b64encode(f.read()).decode('utf-8')
        if not soru :
            yonetici_sorusu = f"""
            
            Eğer ekranda yazılım kodu görürsen, o kodu [KOD_BASLANGICI] ve [KOD_BITISI] etiketleri arasına yaz.
            Kod yoksa sadece ekranı açıkla.
            """
        else:
            yonetici_sorusu=soru

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
            "options": {"temperature": 0.2},
            "keep_alive": 0
        }

        response = requests.post(OLLAMA_URL, json=payload, timeout=120)
        # 1. HTTP seviyesindeki hataları yakala
        if response.status_code != 200:
            return False, None, f"API Bağlantı Hatası (HTTP {response.status_code}): {response.text}"
            
        json_yanit = response.json()
        
        # 2. JSON içerisindeki Ollama/API hatalarını yakala
        if "error" in json_yanit:
            return False, None, f"Model Hatası: {json_yanit['error']}"
        
        cevap = response.json()["message"]["content"]

        kod_eslesme = re.search(r'\[KOD_BASLANGICI\](.*?)\[KOD_BITISI\]', cevap, re.DOTALL)
        
        if kod_eslesme:
            cikarilan_kod = kod_eslesme.group(1).strip()
            return True, cikarilan_kod, f"Kod tespit edildi.\n\n{cikarilan_kod[:150]}..."

        return False, None, cevap

    except Exception as e:
        return False, None, f"Vision Hatası: {str(e)}"