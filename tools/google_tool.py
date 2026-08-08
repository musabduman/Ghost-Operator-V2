import requests
from ddgs import DDGS
import trafilatura

def search_duckduckgo(query):
    """DuckDuckGo ile arama yapar."""
    results = []
    with DDGS() as ddgs:
        for r in ddgs.text(query, max_results=5):
            results.append({
                "title": r.get("title"),
                "link": r.get("href"),
                "snippet": r.get("body")
            })
    return results

def _format_results(results: list) -> str:
    """Sonuç listesini modelin okuyabileceği temiz string'e çevirir."""
    if not results:
        return ""
    satirlar = []
    for i, r in enumerate(results, 1):
        satirlar.append(
            f"{i}. {r.get('title', 'Başlık yok')}\n"
            f"   URL: {r.get('link', '-')}\n"
            f"   Özet: {r.get('snippet', '-')}"
        )
    return "\n\n".join(satirlar)

def ghost_search_tool(query) -> str:
    """Ghost'un ana arama aracı (DuckDuckGo). Her zaman string döndürür."""
    print(f"Ghost aranıyor: '{query}'...")
    try:
        results = search_duckduckgo(query)
        formatted = _format_results(results)
        if formatted:
            return formatted
        return "DuckDuckGo'da sonuç bulunamadı."
    except Exception as e:
        print(f"DuckDuckGo başarısız: {e}")
        return f"Arama başarısız oldu. Hata: {e}"

def read_webpage(url):
    """Ghost'un bulduğu linkin içine girip içeriği okumasını sağlar."""
    print(f"Ghost şu linki okuyor: {url}")
    downloaded = trafilatura.fetch_url(url)
    if downloaded:
        text = trafilatura.extract(downloaded)
        return text
    return "Site içeriği okunamadı."