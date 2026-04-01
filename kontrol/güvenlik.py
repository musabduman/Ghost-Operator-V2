def guvenlik_kontrolu(komut):
    komut_kucuk = komut.lower()
    
    # Sadece tek başına yazıldığında tehlikeli olanlar
    tam_kelimeler = ["del", "format"]
    for kelime in tam_kelimeler:
        if kelime in komut_kucuk.split(): 
            return False
            
    # İçinde geçmesi bile tehlikeli olan kalıplar
    tehlikeli_kaliplar = ["system32", "rm -rf"]
    for kalip in tehlikeli_kaliplar:
        if kalip in komut_kucuk:
            return False
            
    return True