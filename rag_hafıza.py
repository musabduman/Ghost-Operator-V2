import chromadb
import ollama
import os
import hashlib

class Bellek:
    def __init__(self, collection_name="bellek"):
        db_path = os.path.join(os.path.expanduser("~"), "Masaüstü", "Ghost_Memory", "VektorDB")
        self.client = chromadb.PersistentClient(path=db_path)
        self.collection_name = collection_name
        self.collection = self.client.get_or_create_collection(name=self.collection_name)

    def bellege_yaz(self, metin):
        embedding = ollama.embeddings(model="nomic-embed-text", prompt=metin)["embedding"]
        metin_hash = hashlib.md5(metin.encode()).hexdigest()
        self.collection.add(
            documents=[metin],
            embeddings=[embedding],
            ids=[metin_hash]
        )

    def sorgula(self, soru, limit=3):
        try:
            embedding = ollama.embeddings(model="nomic-embed-text", prompt=soru)["embedding"]
            results = self.collection.query(
                query_embeddings=[embedding],
                n_results=limit
            )
            # Eğer sonuç boş dönmezse listeyi ver, boşsa boş liste dön
            if results["documents"] and results["documents"][0]:
                return results["documents"][0] 
            return []
        
        except Exception as e:
            return []