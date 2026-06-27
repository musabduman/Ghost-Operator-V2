"""
core/patterns.py — Tüm regex pattern'ları tek yerde.
Ghost'un etiketlerini yakalayan zırhlı ve boşluk toleranslı yapı.
"""
import re

PATTERNS = {
    "klasor_ac":      re.compile(r'\[\s*OPEN_FOLDER\s*:\s*(.*?)\s*\]', re.IGNORECASE),
    "uygulama_ac":    re.compile(r'\[\s*OPEN_APP\s*:\s*(.*?)\s*\]', re.IGNORECASE),
    "sarki_ac":       re.compile(r'\[\s*ŞARKI_AÇ\s*:\s*(.*?)\s*\]', re.IGNORECASE),
    "playlist_ac":    re.compile(r'\[\s*PLAYLIST_AÇ\s*:\s*(.*?)\s*\]', re.IGNORECASE),
    "arama":          re.compile(r'\[\s*ARAMA\s*:\s*(.*?)\s*\]', re.IGNORECASE),
    "not_al":         re.compile(r'\[\s*NOT_AL\s*:\s*(.*?)\s*\]', re.IGNORECASE),
    "klasor_yap":     re.compile(r'\[\s*KLASOR_YAP\s*:\s*(.*?)\s*\]', re.IGNORECASE),
    "dosya_oku":      re.compile(r'\[\s*DOSYA_OKU\s*:\s*(.*?)\s*\]', re.IGNORECASE),
    "kodu_calistir":  re.compile(r'\[\s*KODU_CALISTIR\s*:\s*(.*?)\s*\]', re.IGNORECASE),
    "klasor_incele":  re.compile(r'\[\s*KLASOR_INCELE\s*:\s*(.*?)\s*\]', re.IGNORECASE),
    "tarayici_tikla": re.compile(r'\[\s*TARAYICI_TIKLA\s*:\s*(.*?)\s*\|\s*(.*?)\s*\]', re.IGNORECASE),
    "tarayici_yaz":   re.compile(r'\[\s*TARAYICI_YAZ\s*:\s*(.*?)\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\]', re.IGNORECASE),
    "gozlem_yap":     re.compile(r'\[\s*GOZLEM_YAP\s*:\s*(.*?)\s*\]', re.IGNORECASE),
    "site_oku":       re.compile(r'\[\s*SİTE_OKU\s*:\s*(.*?)\s*\]', re.IGNORECASE),
    "dosya_yaz":      re.compile(
        r'\[\s*DOSYA_YAZ\s*:\s*(.*?)\s*\]\s*<<<KOD_BASLANGIC>>>\s*(.*?)\s*<<<KOD_BITIS>>>',
        re.DOTALL | re.IGNORECASE
    ),
    
    # DÜZELTME: Bu iki etiket boşluklara karşı zırhlı hale getirildi (\s* eklendi)
    "gorev_bitti":     re.compile(r'\[\s*GOREV_BITTI\s*:\s*(.*?)\s*\]', flags=re.IGNORECASE | re.DOTALL),
    "ekran_goruntusu": re.compile(r'\[\s*EKRAN_GORUNTUSU\s*:\s*(.*?)\s*\]', flags=re.IGNORECASE | re.DOTALL),
}