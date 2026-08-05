import os
import pytest
from core.fs import dosya_bul, derin_arama

def test_dosya_bul_with_absolute_path(tmp_path):
    # Geçici bir dosya yarat
    test_file = tmp_path / "test_dosya.txt"
    test_file.write_text("merhaba")
    
    # Mutlak yol verildiğinde aynen dönmeli
    abs_path = str(test_file.absolute())
    assert dosya_bul(abs_path) == abs_path

def test_dosya_bul_fallback(tmp_path):
    # Eğer aktif proje yoksa ve dosya genel yerlerde de yoksa
    # dosya adı olduğu gibi dönmeli
    assert dosya_bul("olmayan_dosya_123.py") == "olmayan_dosya_123.py"

def test_derin_arama_missing_path():
    assert derin_arama("hayali_klasor_qwertyuiop") is None
