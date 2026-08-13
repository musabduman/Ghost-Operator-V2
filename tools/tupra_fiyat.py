import requests
import json

def get_tupras_price():
    url = "https://query1.finance.yahoo.com/v8/finance/chart/TUPRS.IS"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        result = data["chart"]["result"][0]
        meta = result["meta"]
        price = meta["regularMarketPrice"]
        currency = meta["currency"]
        print(f"Tüpraş (TUPRS.IS) Güncel Fiyat: {price} {currency}")
    except requests.exceptions.RequestException as e:
        print(f"API isteği sırasında hata oluştu: {e}")
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        print(f"Veri işlenirken hata oluştu: {e}")
    except Exception as e:
        print(f"Beklenmeyen bir hata oluştu: {e}")

if __name__ == "__main__":
    get_tupras_price()