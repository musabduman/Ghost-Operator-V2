import requests
from ddgs import DDGS
import trafilatura
import os
from dotenv import load_dotenv

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
SEARCH_ENGINE_ID = os.getenv("SEARCH_ENGINE_ID")

def search_google(query):
    """Google API ile arama yapar."""
    url = f"https://www.googleapis.com/customsearch/v1?key={GOOGLE_API_KEY}&cx={SEARCH_ENGINE_ID}&q={query}"
    response = requests.get(url)
    
    if response.status_code == 429:
        raise Exception("QuotaExceeded")
    elif response.status_code != 200:
        raise Exception(f"Google API Hatası: {response.status_code}")
        
    data = response.json()
    results = []
    for item in data.get("items", [])[:5]: # İlk 5 sonucu alıyoruz
        results.append({
            "title": item.get("title"),
            "link": item.get("link"),
            "snippet": item.get("snippet")
        })
    return results

def search_duckduckgo(query):
    """Fallback (B Planı) olarak DuckDuckGo ile arama yapar."""
    results = []
    with DDGS() as ddgs:
        # DuckDuckGo'dan ilk 5 sonucu al
        for r in ddgs.text(query, max_results=5):
            results.append({
                "title": r.get("title"),
                "link": r.get("href"),
                "snippet": r.get("body")
            })
    return results

def ghost_search_tool(query):
    """Ghost'un ana arama aracı. Önce Google'ı dener, çökerse DDG'ye geçer."""
    print(f"Ghost aranıyor: '{query}'...")
    try:
        results = search_google(query)
        print("Arama Google üzerinden başarıyla yapıldı.")
        return results
    except Exception as e:
        if str(e) == "QuotaExceeded":
            print("Google kotası dolmuş! Ghost yedek sisteme (DuckDuckGo) geçiş yapıyor...")
            return search_duckduckgo(query)
        else:
            print(f"Beklenmeyen bir hata oluştu: {e}. DuckDuckGo deneniyor...")
            return search_duckduckgo(query)

def read_webpage(url):
    """Ghost'un bulduğu linkin içine girip içeriği okumasını sağlar."""
    print(f"Ghost şu linki okuyor: {url}")
    downloaded = trafilatura.fetch_url(url)
    if downloaded:
        # Sadece ana metni çıkar (reklamsız, menüsüz temiz metin)
        text = trafilatura.extract(downloaded)
        return text
    return "Site içeriği okunamadı."