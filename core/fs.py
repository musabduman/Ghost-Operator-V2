"""
core/fs.py — Dosya sistemi yardımcıları.
UI'dan tamamen bağımsız, test edilebilir fonksiyonlar.
"""
import os
import difflib
import subprocess
import sys

def akilli_yol_cozucu(raw: str) -> str:
    """Ghost'un verdiği hatalı/eksik yolu gerçek yola dönüştürür."""
    user_home = os.path.expanduser("~")
    path = os.path.normpath(raw.strip())

    if "Users\\" in path:
        parts = path.split("\\")
        if len(parts) > 3:
            path = os.path.join(user_home, *parts[3:])
    elif not path.startswith("C:"):
        path = os.path.join(user_home, path)

    return path


def alternatif_yol_bul(bad_path: str) -> str | None:
    """Yazım hatalı klasör adı için en yakın eşleşmeyi döndürür."""
    parent = os.path.dirname(bad_path)
    target = os.path.basename(bad_path)
    if not os.path.exists(parent):
        return None
    try:
        candidates = os.listdir(parent)
        matches = difflib.get_close_matches(target, candidates, n=1, cutoff=0.5)
        if matches:
            return os.path.join(parent, matches[0])
    except OSError:
        pass
    return None


def derin_arama(path: str) -> str | None:
    """Desktop / Documents / Downloads altında klasör adına göre arar."""
    target = os.path.basename(path).lower()
    home   = os.path.expanduser("~")
    roots  = [
        os.path.join(home, "Desktop"),
        os.path.join(home, "Documents"),
        os.path.join(home, "Downloads"),
    ]
    for root in roots:
        if not os.path.exists(root):
            continue
        for dirpath, dirs, _ in os.walk(root):
            for d in dirs:
                if target in d.lower():
                    return os.path.join(dirpath, d)
    return None

def dosya_bul(dosya_yolu: str, aktif_proje_dizini: str = None) -> str:
    """
    LLM'in verdiği kısa dosya adını sistemde arar ve tam yolunu döndürür.
    Böylece LLM'in uzun/sabit (C:\\Users\\...) yollar tahmin etmesine gerek kalmaz.
    """
    if os.path.isabs(dosya_yolu) and os.path.exists(dosya_yolu):
        return dosya_yolu
        
    hedef_adi = os.path.basename(dosya_yolu)
    
    # 1. Önce aktif proje dizininde derinlemesine ara
    if aktif_proje_dizini and os.path.exists(aktif_proje_dizini):
        for root, dirs, files in os.walk(aktif_proje_dizini):
            # Gereksiz klasörleri atla (hız için)
            dirs[:] = [d for d in dirs if d not in (".git", "node_modules", "venv", ".venv", "__pycache__")]
            if hedef_adi in files:
                return os.path.join(root, dosya_yolu if dosya_yolu in files else hedef_adi)
                
    # 2. Bulunamadıysa genel çalışma alanlarında ara
    home = os.path.expanduser("~")
    roots = [
        os.path.join(home, "Desktop"),
        os.path.join(home, "Documents")
    ]
    
    for r in roots:
        if not os.path.exists(r):
            continue
        for root, dirs, files in os.walk(r):
            dirs[:] = [d for d in dirs if d not in (".git", "node_modules", "venv", ".venv", "__pycache__")]
            if hedef_adi in files:
                return os.path.join(root, hedef_adi)
                
    # 3. Hiçbir yerde yoksa, muhtemelen YENİ yazılacak bir dosyadır.
    if aktif_proje_dizini:
        return os.path.join(aktif_proje_dizini, dosya_yolu)
        
    return dosya_yolu


def kodu_calistir(path: str) -> dict:
    """Python dosyasını çalıştırır; sonucu dict olarak döndürür."""
    try:
        result = subprocess.run(
            [sys.executable, path],
            capture_output=True,
            text=True,
            timeout=15,
        )
        stdout = result.stdout.strip()
        stderr = result.stderr.strip()
        return {
            "basarili": result.returncode == 0,
            "cikti":    stdout or "(çıktı yok)",
            "hata":     stderr or None,
        }
    except subprocess.TimeoutExpired:
        return {"basarili": False, "cikti": None, "hata": "ZAMAN AŞIMI: Kod 15 saniyede bitmedi."}
    except Exception as e:
        return {"basarili": False, "cikti": None, "hata": str(e)}