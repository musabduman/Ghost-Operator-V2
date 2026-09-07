import os

with open("hafıza/rag_hafıza.py", "r", encoding="utf-8") as f:
    code = f.read()

old_benzerini = """    def benzerini_bul_metadata_ile(self, metin, esik=0.15):
        \"\"\"Benzer kaydı arar ve bulursa metadata'sını da döndürür.\"\"\"
        if self.collection.count() == 0:
            return None
        try:
            embedding = self._get_embedding(metin)
            results = self.collection.query(
                query_embeddings=[embedding],
                n_results=1,
                include=["documents", "metadatas", "distances"],
            )"""
new_benzerini = """    def benzerini_bul_metadata_ile(self, metin, esik=0.15, proje_adi=None):
        \"\"\"Benzer kaydı arar ve bulursa metadata'sını da döndürür.\"\"\"
        if self.collection.count() == 0:
            return None
        try:
            embedding = self._get_embedding(metin)
            where = {"proje_adi": proje_adi} if proje_adi else None
            results = self.collection.query(
                query_embeddings=[embedding],
                n_results=1,
                include=["documents", "metadatas", "distances"],
                where=where
            )"""
code = code.replace(old_benzerini, new_benzerini)
with open("hafıza/rag_hafıza.py", "w", encoding="utf-8") as f:
    f.write(code)
print("Patched rag_hafıza.py benzerini_bul_metadata_ile")

with open("ai/librarian_agent.py", "r", encoding="utf-8") as f:
    code = f.read()

old_librarian = """                            benzer = self.bellek.benzerini_bul_metadata_ile(fact)"""
new_librarian = """                            benzer = self.bellek.benzerini_bul_metadata_ile(fact, proje_adi=proje_adi)"""
code = code.replace(old_librarian, new_librarian)
with open("ai/librarian_agent.py", "w", encoding="utf-8") as f:
    f.write(code)
print("Patched librarian_agent.py benzerini_bul_metadata_ile call")
