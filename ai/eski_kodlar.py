"""    
    def _process_worker_tags(self, cevap: str) -> tuple[str, str]:
        aktif_model = "GPT-OSS 120B (Yönetici)"
        kod_istegi_eslesme = re.search(r'\[KOD_ISTE:\s*(.*?)\s*\|\s*(.*?)\]', cevap, flags=re.DOTALL | re.IGNORECASE)
        
        if kod_istegi_eslesme:
            raw_yolu = kod_istegi_eslesme.group(1).strip()
            dosya_yolu = self.yol_duzelt(raw_yolu)
            talimat = kod_istegi_eslesme.group(2).strip()
            aktif_model = "Qwen 480B (Mühendis Kodluyor...)"
            
            try:
                mevcut_kod = ""
                if os.path.exists(dosya_yolu):
                    try:
                        with open(dosya_yolu, "r", encoding="utf-8") as f:
                            mevcut_kod = f.read()
                    except Exception:
                        pass

                saf_kod = self.worker.saf_kod_uret(talimat=talimat, mevcut_kod=mevcut_kod)
                    
                ui_formati = f"[DOSYA_YAZ: {dosya_yolu}]\n<<<KOD_BASLANGIC>>>\n{saf_kod}\n<<<KOD_BITIS>>>"
                cevap = cevap.replace(kod_istegi_eslesme.group(0), ui_formati)
                
            except Exception as e:
                cevap = f"[SİSTEM HATA] Taşeron koda ulaşamadı: {e}"

        return cevap, aktif_model

    def _raw_supervisor_call(self) -> tuple[str, str]:
        try:
            res = self.supervisor._raw_call()
            self.supervisor.add_assistant(res)
            return self._process_worker_tags(res)
        except Exception as e:
            raise Exception(f"Supervisor çöktü: {e}")

    def generate(self, user_input: str) -> tuple[str, str]:
        res = self.supervisor.generate(user_input)
        return self._process_worker_tags(res)
            
    def __call__(self, user_input):
        return self.generate(user_input)
    

 
    def load_history(self, messages: list):
        self.mesaj_gecmisi = [{"role": "system", "content": self.ana_kurallar}]
        for m in messages:
            llm_role = "assistant" if m["role"].lower() == "ghost" else "user"
            self.mesaj_gecmisi.append({
                "role": llm_role,
                "content": m["text"]
            })
    
    
    def add_assistant(self, content: str):
        self.mesaj_gecmisi.append({"role": "assistant", "content": content})
        # Geçmişi sınırla mantığını buraya aldık ki raw_call sonrası da otomatik çalışsın
        if len(self.mesaj_gecmisi) > 22:
            self.mesaj_gecmisi = [self.mesaj_gecmisi[0]] + self.mesaj_gecmisi[-10:]

            
    def generate(self, user_input: str) -> str:
        self.add_user(user_input)
        try:
            res = self._raw_call()
            self.add_assistant(res)
            return res
        except Exception as e:
            self.mesaj_gecmisi.pop()
            raise Exception(f"Yönetici Çöktü: {e}")

    """
