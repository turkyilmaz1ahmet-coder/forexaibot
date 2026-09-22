# 🤖 Forex AI Bot

Python kullanarak MetaTrader 5 üzerinden döviz (Forex) piyasalarında algoritmik ticaret yapan, **Yapay Zeka** (LSTM, XGBoost) ve **Büyük Dil Modelleri** (OpenAI GPT-4o-mini) destekli tam otomatik al-sat botu.

Bu proje, hem teknik analiz (fiyat hareketleri) hem de temel analiz (haber ve ekonomik takvim verileri) metotlarını birleştirerek bir ekonomist gibi kararlar alır.

## ✨ Temel Özellikler

- **MT5 Gerçek Zamanlı Entegrasyon**: MetaTrader 5'ten OHLCV verisi çekme ve anında piyasa emri iletme. Otomatik yeniden bağlanma (auto-reconnect).
- **Teknik Analiz (pandas_ta)**: RSI, MACD, Bollinger Bands, ATR, EMA ve Hacim gibi 10+ göstergenin tam entegrasyonu.
- **Yapay Zeka (Zaman Serisi Tahmini)**: 
  - Keras tabanlı **LSTM** (Uzun-Kısa Süreli Bellek) modeli.
  - Ağaç tabanlı **XGBoost** modeli.
  - İki modelin ağırlıklı Ensemble (birleştirilmiş) olasılık çıktısı.
- **LLM Destekli Temel Analiz**:
  - NewsAPI üzerinden finansal haber çekimi.
  - OpenAI (GPT-4o-mini) ile haberlerin döviz çiftlerine (bullish/bearish) etkisini JSON formatında derecelendirme (Ekonomist Skoru).
- **Gelişmiş Risk Yönetimi**: Bakiyenin %'si üzerinden otomatik Lot hesaplama. Spread limitleri ve ATR tabanlı Dinamik Stop-Loss (SL) / Take-Profit (TP). Kârı koruyan İz Süren Stop (Trailing Stop).
- **Telegram Bildirimleri**: Yeni işlemler, hatalar ve günlük performans özetleri için anlık uyarılar.
- **Backtrader Simülasyonu**: Geçmiş veri üzerinde strateji testleri.

## 📁 Proje Mimarisi

- `config/` - Ayarlar (YAML, .env) ve loglama yapılandırması.
- `data/` - MT5 bağlantısı, OHLCV verisi ve haber API'si etkileşimleri.
- `analysis/`
  - `technical/` - İndikatörler ve Machine Learning için feature engineering.
  - `fundamental/` - LLM ile haberlerin duygu (sentiment) analizi.
- `models/` - LSTM ve XGBoost model tanımları, eğitim (`train.py`) ve tahmin (`predict.py`) scriptleri.
- `strategy/` - Teknik (ML) ve Temel (LLM) sinyalleri birleştirip nihai kararı veren beyin.
- `execution/` - Lot hesabı (Risk), emri piyasaya iletme ve trailing stop.
- `backtest/` - Backtrader entegrasyonu (Sizer, Commission, custom DataFeed).
- `scripts/` - `main.py`, model eğitme ve test için pratik başlatıcılar.

## 🚀 Kurulum ve Başlangıç

### 1. Gereksinimler
- **Windows İşletim Sistemi** (MetaTrader 5 Python kütüphanesi sadece Windows destekler)
- **Python 3.10 veya üzeri**
- Bilgisayarınızda kurulu, giriş yapılmış ve "Algo Trading" (Oto İşlem) izni verilmiş **MetaTrader 5 (MT5)** terminali.

### 2. İndirme ve Sanal Ortam
```powershell
# Proje dizininde sanal ortam oluşturun
python -m venv venv
.\venv\Scripts\Activate.ps1

# Bağımlılıkları yükleyin
pip install -r requirements.txt
```

### 3. Yapılandırma
`.env.example` dosyasını kopyalayarak `.env` isimli bir dosya oluşturun ve içini doldurun:
```ini
MT5_LOGIN=12345678
MT5_PASSWORD=sifreniz
MT5_SERVER=Broker-Demo
OPENAI_API_KEY=sk-your-key
TELEGRAM_BOT_TOKEN=your-token
TELEGRAM_CHAT_ID=your-chat-id
NEWS_API_KEY=your-newsapi-key
```

Botun ince ayarlarını (indikatör periyotları, risk oranı vb.) değiştirmek için `settings.yaml` dosyasını kullanabilirsiniz.

### 4. Modelleri Eğitme (İlk Çalıştırmadan Önce Önerilir)
Kendi verinizle ML modellerini baştan eğitmek için:
```powershell
python scripts\train_model.py --symbol EURUSD --version v1
```

### 5. Botu Başlatma
Canlı piyasada veya Demoda işlem yapmaya başlamak için (MT5 açık olmalıdır):
```powershell
python main.py
```

## 🧪 Backtest Çalıştırma
```powershell
python scripts\run_backtest.py
```

## ⚠️ Uyarılar ve Yasal Bilgilendirme
Bu proje açık kaynaklı bir deneme ve eğitim çalışmasıdır. Gerçek parayla (Live) işlem yapmadan önce botu mutlaka **Demo** modunda (`settings.yaml` içinde `trading.mode: "demo"` ve `paper_trading.enabled: true`) haftalarca test edin. Algoritmik işlemler yüksek risk içerir, geliştirici herhangi bir maddi kayıptan sorumlu tutulamaz.
