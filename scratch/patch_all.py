import os

# 1. Update core/tool_registry.py
registry_path = "core/tool_registry.py"
with open(registry_path, "a", encoding="utf-8") as f:
    f.write('''
ghost_tool(
    name="proje_hafizasi_ekle",
    description="Projenin statik hafızasına (L2) kalıcı bir kural, mimari kararı veya kısıtlama ekler. Bu bilgi her zaman ajanın bağlamında (context) tutulur.",
    params={
        "kategori": ("string", "Eklenecek kategori: architecture, decisions, current_goals, known_errors veya constraints"),
        "bilgi": ("string", "Eklenecek yeni kural veya bilgi")
    },
)(None)

ghost_tool(
    name="proje_hafizasi_sil",
    description="Projenin statik hafızasından (L2) geçerliliğini yitirmiş bir bilgiyi siler.",
    params={
        "kategori": ("string", "Silinecek kategori: architecture, decisions, current_goals, known_errors veya constraints"),
        "bilgi": ("string", "Silinecek kuralın/bilginin tam metni")
    },
)(None)
''')
print("Patched core/tool_registry.py")

# 2. Update handler/command_handler.py
handler_path = "handler/command_handler.py"
with open(handler_path, "r", encoding="utf-8") as f:
    handler_code = f.read()

# Insert binds
bind_str = '''        tool_registry.bind_handler("periyodik_gorev_sil", self._tool_periyodik_gorev_sil)
        tool_registry.bind_handler("proje_hafizasi_ekle", self._tool_proje_hafizasi_ekle)
        tool_registry.bind_handler("proje_hafizasi_sil", self._tool_proje_hafizasi_sil)'''
handler_code = handler_code.replace('        tool_registry.bind_handler("periyodik_gorev_sil", self._tool_periyodik_gorev_sil)', bind_str)

# Insert handlers
handlers_str = '''

    def _tool_proje_hafizasi_ekle(self, kategori: str, bilgi: str) -> str:
        try:
            from hafıza.project_memory import ProjectMemoryL2
            son_proje = self.episodic_db.son_aktif_projeyi_getir()
            if not son_proje or not son_proje.get("aktif_dizin"):
                return "Şu an aktif bir proje bulunamadı. Lütfen önce bir projede çalışın."
            l2 = ProjectMemoryL2(son_proje["aktif_dizin"])
            l2.add_item(kategori, bilgi)
            return f"Proje hafızasına '{kategori}' kategorisine eklendi: {bilgi}"
        except Exception as e:
            return f"Hafızaya eklenirken hata: {str(e)}"

    def _tool_proje_hafizasi_sil(self, kategori: str, bilgi: str) -> str:
        try:
            from hafıza.project_memory import ProjectMemoryL2
            son_proje = self.episodic_db.son_aktif_projeyi_getir()
            if not son_proje or not son_proje.get("aktif_dizin"):
                return "Şu an aktif bir proje bulunamadı."
            l2 = ProjectMemoryL2(son_proje["aktif_dizin"])
            l2.remove_item(kategori, bilgi)
            return f"Proje hafızasından silindi: {bilgi}"
        except Exception as e:
            return f"Hafızadan silinirken hata: {str(e)}"
'''

handler_code += handlers_str
with open(handler_path, "w", encoding="utf-8") as f:
    f.write(handler_code)
print("Patched handler/command_handler.py")

# 3. Update ai/llm.py
llm_path = "ai/llm.py"
with open(llm_path, "r", encoding="utf-8") as f:
    llm_code = f.read()

# We want to insert Project L2 Memory into `ana_kurallar`.
# We'll insert it right after `ogrenilmis_kurallar` block around line 150.
insertion_code = '''
        # Project L2 Memory
        try:
            from hafıza.episodic_db import EpisodicDB
            from hafıza.project_memory import ProjectMemoryL2
            db = EpisodicDB()
            son_proje = db.son_aktif_projeyi_getir()
            if son_proje and son_proje.get("aktif_dizin"):
                l2 = ProjectMemoryL2(son_proje["aktif_dizin"])
                l2_context = l2.get_formatted_context()
                if l2_context:
                    self.ana_kurallar += f"\\n\\n{l2_context}\\n"
        except Exception as e:
            logger.error(f"Project L2 Memory yüklenemedi: {e}")
'''

# Find the spot
target = '''        except Exception as e:
            logger.error(f"Harness state yüklenemedi: {e}")'''
if target in llm_code:
    llm_code = llm_code.replace(target, target + "\n" + insertion_code)
    with open(llm_path, "w", encoding="utf-8") as f:
        f.write(llm_code)
    print("Patched ai/llm.py")
else:
    print("Could not find target in ai/llm.py!")
