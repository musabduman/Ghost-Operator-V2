import os

# 1. Update handler/command_handler.py
handler_path = "handler/command_handler.py"
with open(handler_path, "r", encoding="utf-8") as f:
    handler_code = f.read()

# Insert bind
bind_str = '''        tool_registry.bind_handler("proje_hafizasi_sil", self._tool_proje_hafizasi_sil)
        tool_registry.bind_handler("calisma_durumu_guncelle", self._tool_calisma_durumu_guncelle)'''
handler_code = handler_code.replace('        tool_registry.bind_handler("proje_hafizasi_sil", self._tool_proje_hafizasi_sil)', bind_str)

# Update _tool_durum_getir to show new fields
old_durum_getir_end = """        return (
            f"Proje: {durum['proje_adi']}\\n"
            f"Aktif Dizin: {durum['aktif_dizin']}\\n"
            f"Son Dokunulan Dosyalar: {', '.join(dosyalar[:5])}\\n"
            f"Son Görev Özeti: {durum['son_gorev_ozeti']}"
        )"""
new_durum_getir_end = """        
        bekleyen = durum.get("pending_action", "Yok")
        hata = durum.get("son_hata", "Yok")
        baglam = durum.get("mevcut_context", "Bilinmiyor")
        
        return (
            f"Proje: {durum['proje_adi']}\\n"
            f"Aktif Dizin: {durum['aktif_dizin']}\\n"
            f"Son Dokunulan Dosyalar: {', '.join(dosyalar[:5])}\\n"
            f"Mevcut Bağlam: {baglam}\\n"
            f"Bekleyen İşlem: {bekleyen}\\n"
            f"Son Hata: {hata}\\n"
            f"Son Görev Özeti: {durum['son_gorev_ozeti']}"
        )"""

# Fallback string replace depending on formatting
if 'Son Grev -zeti' in handler_code or 'Son Görev Özeti' in handler_code:
    # Use regex
    import re
    # We will just replace the return block of _tool_durum_getir
    pattern = r"return \(\s*f\"Proje: \{durum\['proje_adi'\]\}\\n\".*?f\"Son G.*?rev .*?zeti: \{durum\['son_gorev_ozeti'\]\}\"\s*\)"
    match = re.search(pattern, handler_code, re.DOTALL)
    if match:
        handler_code = handler_code[:match.start()] + new_durum_getir_end + handler_code[match.end():]
    else:
        print("Regex match failed for durum_getir return block")

# Add _tool_calisma_durumu_guncelle
handler_method = '''

    def _tool_calisma_durumu_guncelle(self, mevcut_context: str, pending_action: str) -> str:
        try:
            son_proje = self.episodic_db.son_aktif_projeyi_getir()
            if not son_proje:
                return "Aktif bir proje bulunamadı."
            
            self.episodic_db.durum_guncelle(
                proje_adi=son_proje["proje_adi"],
                mevcut_context=mevcut_context,
                pending_action=pending_action
            )
            return f"Çalışma durumu güncellendi.\\nBağlam: {mevcut_context}\\nBekleyen: {pending_action}"
        except Exception as e:
            return f"Durum güncellenirken hata: {str(e)}"
'''

handler_code += handler_method

# Add auto-update of son_hata in run_tool
# We need to find `if success and isim in DURUM_GUNCELLENECEK_ARACLAR:`
old_run_tool_part = """        if success and isim in DURUM_GUNCELLENECEK_ARACLAR:
            proje_notu = self._proje_durumu_guncelle(isim, args)"""
new_run_tool_part = """        if success and isim in DURUM_GUNCELLENECEK_ARACLAR:
            proje_notu = self._proje_durumu_guncelle(isim, args)
        elif not success:
            # Otomatik son_hata guncellemesi
            son_proje = self.episodic_db.son_aktif_projeyi_getir()
            if son_proje:
                hata_metni = str(result)[:500] if result else "Bilinmeyen hata"
                self.episodic_db.durum_guncelle(
                    proje_adi=son_proje["proje_adi"],
                    son_hata=f"[{isim} başarısız] {hata_metni}"
                )"""
handler_code = handler_code.replace(old_run_tool_part, new_run_tool_part)

with open(handler_path, "w", encoding="utf-8") as f:
    f.write(handler_code)
print("Patched handler/command_handler.py")
