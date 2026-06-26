from playwright.sync_api import sync_playwright

def get_dom_elements(url: str) -> str:
    """Belirtilen URL'ye gider ve ekrandaki etkileşimli DOM öğelerini ayıklar."""
    try:
        with sync_playwright() as p:
            # Arka planda Chromium başlat (headless=True görünmez yapar)
            browser = p.chromium.launch(headless=False)
            page = browser.new_page()
            
            # Sayfayı aç ve ağ isteklerinin bitmesini bekle
            page.goto(url, wait_until="networkidle", timeout=15000)
            
            # Sadece etkileşimli öğeleri (buton, link, input) çek
            elements = page.query_selector_all("button, a, input")
            
            ayiklananlar = []
            for el in elements:
                # Elementin görünür metnini veya placeholder'ını al
                text = el.inner_text().strip()
                if not text:
                    text = el.get_attribute("placeholder") or el.get_attribute("aria-label") or ""
                
                tag = el.evaluate("node => node.tagName").lower()
                
                if text:
                    ayiklananlar.append(f"- [{tag.upper()}] {text}")
            
            browser.close()
            
            if not ayiklananlar:
                return "DOM okundu ancak görünür etkileşimli bir öğe bulunamadı."
                
            # İlk 30 öğeyi al ki context window patlamasın
            return "\n".join(ayiklananlar[:30])
            
    except Exception as e:
        raise Exception(f"DOM Okuma Hatası: {str(e)}")

def browser_interact(url: str, eylem: str, hedef_metin: str, yazi_icerigi: str = "") -> str:
    """
    Belirtilen URL'ye gider, hedef_metin'e tıklar veya yazı yazar,
    ardından sayfanın yeni durumunu (DOM) döndürür.
    eylem parametresi: "tikla" veya "yaz"
    """
    from playwright.sync_api import sync_playwright
    
    try:
        with sync_playwright() as p:
            # Bot olduğumuzu gizlemek için User-Agent ekliyoruz
            browser = p.chromium.launch(headless=False)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = context.new_page()
            
            page.goto(url, wait_until="domcontentloaded", timeout=15000)
            
            # 1. Playwright'ın Akıllı Seçicisi: Metne veya Placeholder'a göre elementi bul
            element = page.get_by_text(hedef_metin, exact=False).first
            if not element.is_visible():
                element = page.get_by_placeholder(hedef_metin, exact=False).first
            
            if not element.is_visible():
                browser.close()
                return f"HATA: '{hedef_metin}' adlı buton veya kutu bu URL'de bulunamadı."
            
            # 2. Aksiyonu Gerçekleştir
            if eylem == "tikla":
                element.click()
                page.wait_for_timeout(2500) # Sayfanın tepki vermesini / yüklenmesini bekle
            elif eylem == "yaz":
                element.fill(yazi_icerigi)
                page.wait_for_timeout(500)
                element.press("Enter") # Yazdıktan sonra formu göndermek için Enter'a bas
                page.wait_for_timeout(2500)
            
            # 3. Aksiyon Sonrası Yeni Durumu (DOM) Oku ve Gönder
            yeni_url = page.url
            elements = page.query_selector_all("button, a, input")
            
            ayiklananlar = []
            for el in elements:
                text = el.inner_text().strip() or el.get_attribute("placeholder") or el.get_attribute("aria-label") or ""
                tag = el.evaluate("node => node.tagName").lower()
                if text:
                    ayiklananlar.append(f"- [{tag.upper()}] {text}")
            
            browser.close()
            
            # --- YÖNLENDİRME (NUDGE) ---
            return (f"İşlem Başarılı! Tıklandı/Yazıldı.\n"
                    f"Yeni URL: {yeni_url}\n"
                    f"Sayfanın Yeni Öğeleri:\n" + "\n".join(ayiklananlar[:20]) + "\n\n"
                    f"[GİZLİ SİSTEM TALİMATI: Eğer Kullanıcı senden bir makale veya metin okumanı istediyse, "
                    f"yukarıdaki butonlara veya linklere ALDIRIŞ ETME! Doğrudan [SİTE_OKU: {yeni_url}] aracını çağır "
                    f"ve metni analiz et.]")
        
    except Exception as e:
        return f"Tarayıcı İşlem Hatası: {str(e)}"
    
def browser_google_search(query: str) -> str:
    """Google API kullanmadan, Playwright ile fiziksel olarak Chrome açıp arama yapar ve linkleri çeker."""
    from playwright.sync_api import sync_playwright
    import urllib.parse
    
    # URL formatına uygun hale getir
    safe_query = urllib.parse.quote(query)
    url = f"https://www.google.com/search?q={safe_query}"
    
    try:
        with sync_playwright() as p:
            # Bot olduğumuzu gizlemek için user-agent ekleyelim
            browser = p.chromium.launch(headless=False) 
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = context.new_page()
            
            # Google'a git ve DOM'un yüklenmesini bekle
            page.goto(url, wait_until="domcontentloaded", timeout=15000)
            
            # (İsteğe bağlı) Google "Çerezleri Kabul Et" pop-up'ı çıkarsa kapat
            try:
                page.get_by_text("Tümünü reddet", exact=False).first.click(timeout=2000)
            except:
                pass
                
            # Arama sonuçlarını (Başlık ve Linkler) topla
            results = []
            # Google genellikle sonuçları h3 etiketine sahip a (link) etiketleri içinde tutar
            links = page.locator("a:has(h3)").all()
            
            for link in links[:5]: # İlk 5 sonucu al
                title = link.locator("h3").inner_text()
                href = link.get_attribute("href")
                
                if title and href and href.startswith("http"):
                    results.append(f"- {title}\n  URL: {href}")
                    
            browser.close()
            
            if not results:
                return f"'{query}' arandı ama sonuç linkleri çekilemedi. Belki de bir bilgi paneli çıktı."
                
            return f"TARAYICI ARAMA SONUÇLARI ('{query}'):\n\n" + "\n\n".join(results)
            
    except Exception as e:
        return f"Tarayıcı ile arama başarısız oldu: {str(e)}"
    







    