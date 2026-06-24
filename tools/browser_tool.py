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