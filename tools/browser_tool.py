from playwright.sync_api import sync_playwright

def get_dom_elements(url: str) -> str:
    """Belirtilen URL'ye gider ve ekrandaki etkileşimli DOM öğelerini ayıklar."""
    try:
        with sync_playwright() as p:
            # Arka planda Chromium başlat (headless=True görünmez yapar)
            browser = p.chromium.launch(headless=True)
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
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = context.new_page()
            
            page.goto(url, wait_until="networkidle", timeout=15000)
            
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
            
            return (f"İşlem Başarılı! Tıklandı/Yazıldı.\n"
                    f"Yeni URL: {yeni_url}\n"
                    f"Sayfanın Yeni Öğeleri:\n" + "\n".join(ayiklananlar[:20]))
            
    except Exception as e:
        return f"Tarayıcı İşlem Hatası: {str(e)}"