"""
core/patterns.py — Tüm regex pattern'ları tek yerde.
Ghost'un etiketlerini yakalayan zırhlı ve boşluk toleranslı yapı.
"""
import re

# Kurallar:
# 1. \s* : Etiketin içindeki rastgele boşlukları tolere eder (Örn: [ OPEN_APP : chrome ]).
# 2. re.IGNORECASE : Büyük/küçük harf duyarsızlığı sağlar (Örn: [open_app: ...]).
# 3. re.DOTALL : Nokta (.) karakterinin satır atlamalarını (\n) kapsamasını sağlar (Dosya yazma aracı için kritik).

PATTERNS = {
    "klasor_ac":     re.compile(r'\[\s*OPEN_FOLDER\s*:\s*(.*?)\s*\]', re.IGNORECASE),
    "uygulama_ac":   re.compile(r'\[\s*OPEN_APP\s*:\s*(.*?)\s*\]', re.IGNORECASE),
    "sarki_ac":      re.compile(r'\[\s*ŞARKI_AÇ\s*:\s*(.*?)\s*\]', re.IGNORECASE),
    "playlist_ac":   re.compile(r'\[\s*PLAYLIST_AÇ\s*:\s*(.*?)\s*\]', re.IGNORECASE),
    "arama":         re.compile(r'\[\s*ARAMA\s*:\s*(.*?)\s*\]', re.IGNORECASE),
    "not_al":        re.compile(r'\[\s*NOT_AL\s*:\s*(.*?)\s*\]', re.IGNORECASE),
    "klasor_yap":    re.compile(r'\[\s*KLASOR_YAP\s*:\s*(.*?)\s*\]', re.IGNORECASE),
    "dosya_oku":     re.compile(r'\[\s*DOSYA_OKU\s*:\s*(.*?)\s*\]', re.IGNORECASE),
    "kodu_calistir": re.compile(r'\[\s*KODU_CALISTIR\s*:\s*(.*?)\s*\]', re.IGNORECASE),
    "klasor_incele": re.compile(r'\[\s*KLASOR_INCELE\s*:\s*(.*?)\s*\]', re.IGNORECASE),
    # Format: [TARAYICI_TIKLA: url | buton_adi]
    "tarayici_tikla": re.compile(r'\[\s*TARAYICI_TIKLA\s*:\s*(.*?)\s*\|\s*(.*?)\s*\]', re.IGNORECASE),
    
    # Format: [TARAYICI_YAZ: url | kutu_adi | yazilacak_metin]
    "tarayici_yaz": re.compile(r'\[\s*TARAYICI_YAZ\s*:\s*(.*?)\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\]', re.IGNORECASE),
    
    # ── Tarayıcı ve Masaüstü Gözlem Aracı ─────────────────────────────────────
    "gozlem_yap": re.compile(r'\[\s*GOZLEM_YAP\s*:\s*(.*?)\s*\]', re.IGNORECASE),
    
    # Format: [SİTE_OKU: url]
    "site_oku": re.compile(r'\[\s*SİTE_OKU\s*:\s*(.*?)\s*\]', re.IGNORECASE),
    
    # ── İSTİSNA: Çift Parametreli Araç (Dosya Yolu ve Kod Bloğu) ───────────────
    "dosya_yaz":     re.compile(
        r'\[\s*DOSYA_YAZ\s*:\s*(.*?)\s*\]\s*<<<KOD_BASLANGIC>>>\s*(.*?)\s*<<<KOD_BITIS>>>',
        re.DOTALL | re.IGNORECASE
    ),
    #Görevler bitince loopdan çıkabilmek için.
    "gorev_bitti": re.compile(r'\[GOREV_BITTI:\s*(.*?)\]', flags=re.IGNORECASE | re.DOTALL),

}