import yfinance as yf
import numpy as np
from datetime import datetime, timedelta
from transformers import AutoTokenizer, AutoModelForCausalLM
import torch

class StockAnalyzer:
    def __init__(self, symbol):
        self.symbol = symbol
        self.data = None
        self.current_price = None
        self.model_name = "gpt-oss:20b-cloud"
        self.tokenizer = None
        self.model = None
        
    def load_model(self):
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self.model = AutoModelForCausalLM.from_pretrained(self.model_name)
        except Exception as e:
            print(f"Model yükleme hatası: {e}")
    
    def fetch_data(self, period="1y"):
        try:
            ticker = yf.Ticker(self.symbol)
            self.data = ticker.history(period=period)
            if not self.data.empty:
                self.current_price = self.data['Close'].iloc[-1]
            return self.data
        except Exception as e:
            print(f"Veri çekme hatası: {e}")
            return None
    
    def fetch_yearly_data(self):
        try:
            ticker = yf.Ticker(self.symbol)
            yearly_data = ticker.history(period="1y")
            return yearly_data
        except Exception as e:
            print(f"Yıllık veri çekme hatası: {e}")
            return None
            
    def calculate_basic_metrics(self):
        if self.data is None or self.data.empty:
            return None
            
        try:
            prices = self.data['Close']
            returns = prices.pct_change().dropna()
            
            metrics = {
                'current_price': self.current_price,
                '52_week_high': prices.max(),
                '52_week_low': prices.min(),
                'avg_30d_volume': self.data['Volume'][-30:].mean(),
                'volatility': returns.std() * np.sqrt(252),
                'sharpe_ratio': (returns.mean() / returns.std()) * np.sqrt(252) if returns.std() > 0 else 0,
                'rsi': self._calculate_rsi(prices),
                'support_level': prices[-60:].min(),
                'resistance_level': prices[-60:].max()
            }
            return metrics
        except Exception as e:
            print(f"Metrik hesaplama hatası: {e}")
            return None
    
    def _calculate_rsi(self, prices, window=14):
        try:
            delta = prices.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            return rsi.iloc[-1] if not rsi.empty else 50
        except Exception as e:
            print(f"RSI hesaplama hatası: {e}")
            return 50

    def generate_analysis(self, symbol, metrics):
        if not self.model or not self.tokenizer:
            self.load_model()
            
        prompt = self.generate_gemini_prompt(symbol, metrics)
        
        try:
            inputs = self.tokenizer.encode(prompt, return_tensors="pt", max_length=1024, truncation=True)
            with torch.no_grad():
                outputs = self.model.generate(inputs, max_new_tokens=500, temperature=0.7, do_sample=True)
            analysis = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
            return analysis[len(prompt):]  # Sadece yeni oluşturulan kısmı döndür
        except Exception as e:
            print(f"Analiz oluşturma hatası: {e}")
            return ""
            
    def generate_gemini_prompt(self, symbol, metrics):
        try:
            prompt = f"""Hisse Senedi Analizi: {symbol}

TEMEL VERİLER:
- Güncel Fiyat: ${metrics['current_price']:.2f}
- 52 Haftalık En Yüksek: ${metrics['52_week_high']:.2f}
- 52 Haftalık En Düşük: ${metrics['52_week_low']:.2f}
- Ortalama Günlük Hacim (30 gün): {metrics['avg_30d_volume']:,.0f}
- Volatilite: {metrics['volatility']:.2%}
- Sharpe Oranı: {metrics['sharpe_ratio']:.2f}
- RSI (14 gün): {metrics['rsi']:.1f}
- Destek Seviyesi: ${metrics['support_level']:.2f}
- Direnç Seviyesi: ${metrics['resistance_level']:.2f}

LÜTFEN ANALİZİNİ YAP:
1. Teknik göstergeler açısından kısa vadeli ve uzun vadeli trendi değerlendir
2. Mevcut fiyatın tarihsel seviyelere göre konumunu analiz et
3. RSI değerine bakarak aşırı alım/aşırı satım durumunu yorumla
4. Volatilite ve Sharpe oranına göre risk-getiri dengesini değerlendir
5. Destek ve direnç seviyelerinin kısa vadeli fiyat hareketleri üzerindeki etkilerini açıkla
6. Hissenin genel piyasa koşullarındaki performansına dair yatırım tavsiyesi ver
7. Potansiyel hedef fiyat aralığını belirt (detaylı teknik analiz temelli)

Ekstra değerlendirme kriterleri:
- Makroekonomik faktörlerin etkisi
- Sektörel karşılaştırmalar
- Finansal sağlık göstergeleri (varsa)
"""
            return prompt
        except Exception as e:
            print(f"Prompt oluşturma hatası: {e}")
            return ""

# Örnek kullanım
if __name__ == "__main__":
    try:
        analyzer = StockAnalyzer("AAPL")
        data = analyzer.fetch_data()
        if data is not None:
            metrics = analyzer.calculate_basic_metrics()
            if metrics:
                analysis = analyzer.generate_analysis("AAPL", metrics)
                print("Oluşturulan Analiz:")
                print(analysis)
                print(f"\nMevcut Fiyat: ${metrics['current_price']:.2f}")
                print(f"RSI: {metrics['rsi']:.1f}")
                print(f"Volatilite: {metrics['volatility']:.2%}")
                
                # Yıllık veri çekme örneği
                yearly_data = analyzer.fetch_yearly_data()
                if yearly_data is not None:
                    print(f"Yıllık en yüksek: ${yearly_data['High'].max():.2f}")
                    print(f"Yıllık en düşük: ${yearly_data['Low'].min():.2f}")
            else:
                print("Metrikler hesaplanamadı.")
        else:
            print("Veri çekilemedi.")
    except Exception as e:
        print(f"Program çalıştırma hatası: {e}")