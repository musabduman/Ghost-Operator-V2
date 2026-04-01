from rag_hafiza import Bellek

class GhostController:
    def __init__(self):
        self.bellek = Bellek()

    def generate(self, user_input):
        docs = self.bellek.sorgula(user_input)
        history_reminder = "[GEÇMİŞ HATIRLATMASI: " + ", ".join(docs) + "]"
        # ... (kalan kod)