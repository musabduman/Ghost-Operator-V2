import requests

url = "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT"

try:
    response = requests.get(url)
    data = response.json()
    price = float(data['price'])
    print(f"Güncel BTC Fiyatı: ${price:,.2f}")
except Exception as e:
    print(f"Bir hata oluştu: {e}")