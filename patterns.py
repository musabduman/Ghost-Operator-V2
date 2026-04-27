"""
core/patterns.py — Tüm regex pattern'ları tek yerde.
Değiştirmen gereken bir şey varsa sadece buraya bakarsın.
"""
import re

PATTERNS = {
    "klasor_ac":     re.compile(r'\[.*?OPEN_FOLDER:\s*(.*?)\]',    re.IGNORECASE),
    "uygulama_ac":   re.compile(r'\[.*?OPEN_APP:\s*(.*?)\]',       re.IGNORECASE),
    "sarki_ac":      re.compile(r'\[.*?ŞARKI_AÇ:\s*(.*?)\]',       re.IGNORECASE),
    "playlist_ac":   re.compile(r'\[.*?PLAYLIST_AÇ:\s*(.*?)\]',    re.IGNORECASE),
    "arama":         re.compile(r'\[.*?ARAMA:\s*(.*?)\]',          re.IGNORECASE),
    "not_al":        re.compile(r'\[.*?NOT_AL:\s*(.*?)\]',         re.IGNORECASE),
    "klasor_yap":    re.compile(r'\[.*?KLASOR_YAP:\s*(.*?)\]',     re.IGNORECASE),
    "dosya_oku":     re.compile(r'\[.*?DOSYA_OKU:\s*(.*?)\]',      re.IGNORECASE),
    "kodu_calistir": re.compile(r'\[.*?KODU_CALISTIR:\s*(.*?)\]',  re.IGNORECASE),
    "dosya_yaz":     re.compile(
        r'\[DOSYA_YAZ:\s*(.*?)\]\s*<<<KOD_BASLANGIC>>>(.*?)<<<KOD_BITIS>>>',
        re.DOTALL | re.IGNORECASE,
    ),
    "klasor_incele": re.compile(r'\[.*?KLASOR_INCELE:\s*(.*?)\]',  re.IGNORECASE),
}