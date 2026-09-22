import os
import sys
import time
import signal
import threading
from datetime import datetime, timezone
import schedule

from config.settings import AppSettings
from config.logging_config import setup_logging, get_logger, log_critical_with_notification
from data.mt5_connector import MT5Connector
from notifications.notifier import Notifier
from execution.order_executor import OrderExecutor
from execution.trailing_stop import TrailingStopManager
from strategy.combined_strategy import CombinedStrategy
from analysis.technical.indicators import TechnicalIndicators


class ForexAIBot:
    """Ana Bot Çalıştırma Sınıfı."""

    def __init__(self):
        # 1. Konfigürasyon ve Loglama
        self.logger = setup_logging()
        self.settings = AppSettings()
        
        self.logger.info("Forex AI Bot Başlatılıyor...")
        
        # 2. Bileşenleri Başlat
        self.notifier = Notifier(self.settings)
        self.connector = MT5Connector(self.settings)
        
        # Strateji ve Yürütme bileşenleri
        self.strategy = CombinedStrategy(self.settings)
        self.executor = OrderExecutor(self.settings, self.connector)
        self.trailing_manager = TrailingStopManager(self.settings, self.connector)
        
        # Bot durumu
        self.is_running = False
        self.symbols = self.settings.trading.get('symbols', ['EURUSD'])
        self.magic_number = self.settings.trading.get('magic_number', 1001)

        # Modelleri önceden yükle
        self.logger.info("Makine Öğrenimi modelleri yükleniyor...")
        if not self.strategy.predictor.is_ready:
            try:
                self.strategy.predictor.load_models()
                self.logger.info("Modeller başarıyla yüklendi.")
            except Exception as e:
                self.logger.warning(f"Modeller yüklenirken hata oluştu: {e}")
                self.logger.warning("Eğitim yapılmamış olabilir. Bot sadece LLM ile çalışmayı deneyecek.")

    def start(self):
        """Bot döngüsünü başlatır."""
        # MT5 Bağlantısını başlat
        if not self.connector.connect():
            msg = "MT5 bağlantısı kurulamadı. Bot başlatılamıyor."
            log_critical_with_notification(self.logger, msg, self.notifier)
            sys.exit(1)
            
        self.notifier.send_alert("🚀 Forex AI Bot aktif edildi ve piyasa izleniyor.")
        self.is_running = True

        # Günlük özet raporu için zamanlayıcı (Örn: her akşam 21:00)
        summary_hour = self.settings.notifications_config.get('daily_summary_hour', 21)
        schedule.every().day.at(f"{summary_hour:02d}:00").do(self._send_daily_summary)

        # İz süren stop için periyodik Thread (Ana döngüyü bloklamamak için)
        trailing_thread = threading.Thread(target=self._trailing_stop_loop, daemon=True)
        trailing_thread.start()

        self.logger.info(f"İzlenen semboller: {self.symbols}")
        
        try:
            while self.is_running:
                # 1. Zamanlanmış görevleri çalıştır (Günlük özet vs.)
                schedule.run_pending()
                
                # 2. Bağlantıyı doğrula
                if not self.connector.ensure_connected():
                    self.logger.warning("MT5 bağlantısı koptu, yeniden bağlanmayı deniyor...")
                    time.sleep(10)
                    continue
                
                # 3. Her sembol için stratejiyi çalıştır
                for symbol in self.symbols:
                    self._process_symbol(symbol)
                    time.sleep(2) # Semboller arası bekleme API limitlerini korur
                    
                # 4. Döngü beklemesi
                # İdeal senaryoda bu süre, seçilen zaman dilimine (Timeframe) göre ayarlanır.
                # Örn: H1 işlem yapılıyorsa saat başlarını beklemek daha verimlidir.
                # Şimdilik basitlik için 5 dakikada bir (300sn) tam döngü.
                self.logger.info("Tam döngü tamamlandı. 5 dakika bekleniyor...")
                time.sleep(300)
                
        except KeyboardInterrupt:
            self.logger.info("Kullanıcı tarafından durduruldu (Ctrl+C).")
        except Exception as e:
            msg = f"Bot ana döngüsünde kritik hata: {e}"
            log_critical_with_notification(self.logger, msg, self.notifier)
        finally:
            self.stop()

    def _process_symbol(self, symbol: str):
        """Bir sembol için analiz yapıp gerekirse emir gönderir."""
        self.logger.info(f"[{symbol}] Analiz başlatılıyor...")
        try:
            decision = self.strategy.analyze_and_decide(symbol)
            action = decision.get('action', 'HOLD')
            
            if action in ['BUY', 'SELL']:
                volume = decision.get('suggested_volume', 0.0)
                sl = decision.get('suggested_sl', 0.0)
                tp = decision.get('suggested_tp', 0.0)
                reason = decision.get('reason', '')
                
                if volume > 0:
                    self.logger.info(f"[{symbol}] Sinyal: {action} (Lot: {volume}, SL: {sl}, TP: {tp}) - Neden: {reason}")
                    
                    # Emri borsaya ilet
                    result = self.executor.execute_trade(
                        symbol=symbol,
                        direction=action,
                        volume=volume,
                        sl=sl,
                        tp=tp,
                        comment=f"AI_{action[:1]}"
                    )
                    
                    if not result.get('success'):
                        self.logger.error(f"[{symbol}] Emir gerçekleştirilemedi: {result.get('reason')}")
            else:
                self.logger.debug(f"[{symbol}] İşlem yok (HOLD). Neden: {decision.get('reason')}")
                
        except Exception as e:
            self.logger.exception(f"[{symbol}] Analiz sırasında hata: {e}")

    def _trailing_stop_loop(self):
        """İz süren stopları (Trailing Stop) sık aralıklarla günceller."""
        import MetaTrader5 as mt5
        ti = TechnicalIndicators(self.settings)
        
        while self.is_running:
            try:
                if not self.connector.ensure_connected():
                    time.sleep(10)
                    continue
                    
                # Açık pozisyonu olan semboller için güncel ATR hesapla
                positions = mt5.positions_get(magic=self.magic_number)
                
                if positions:
                    active_symbols = set([p.symbol for p in positions])
                    current_atrs = {}
                    
                    for sym in active_symbols:
                        # Hızlıca ATR hesaplamak için son 100 mumu çek
                        df = self.strategy.fetcher.fetch_ohlcv(sym, mt5.TIMEFRAME_M15, 100)
                        if not df.empty:
                            df_atr = ti.add_atr(df.copy())
                            atr_col = [c for c in df_atr.columns if 'atr' in c]
                            if atr_col:
                                current_atrs[sym] = df_atr.iloc[-1][atr_col[0]]
                    
                    if current_atrs:
                        self.trailing_manager.update_trailing_stops(current_atrs)
            
            except Exception as e:
                self.logger.error(f"Trailing stop döngüsünde hata: {e}")
                
            # Trailing stop kontrolleri daha sık yapılır (Örn: 30 saniye)
            time.sleep(30)

    def _send_daily_summary(self):
        """Telegram'a günlük performans özeti gönderir."""
        import MetaTrader5 as mt5
        if not self.connector.ensure_connected():
            return
            
        try:
            # Sadece bugünün işlemlerini çek
            today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            
            # mt5.history_deals_get kullanarak günlük işlemlerin özeti çıkarılabilir
            # Basitlik için sadece hesap durumu gönderiliyor
            info = self.connector.get_account_info()
            if info:
                stats = {
                    "total_trades": "Hesaplanıyor...",
                    "winning_trades": "-",
                    "losing_trades": "-",
                    "total_profit": info['profit'],
                    "win_rate": 0.0,
                    "balance": info['balance'],
                    "equity": info['equity']
                }
                self.notifier.send_daily_summary(stats)
        except Exception as e:
            self.logger.error(f"Günlük özet gönderilemedi: {e}")

    def stop(self):
        """Botu durdurur ve kaynakları serbest bırakır."""
        self.is_running = False
        self.logger.info("Bot durduruluyor...")
        self.notifier.send_alert("🛑 Forex AI Bot durduruldu.")
        self.connector.disconnect()
        self.logger.info("MT5 bağlantısı kapatıldı. Çıkış yapılıyor.")


def handle_signals(signum, frame):
    """İşletim sisteminden gelen durdurma sinyallerini yakalar (Ctrl+C)."""
    raise KeyboardInterrupt()


if __name__ == "__main__":
    signal.signal(signal.SIGINT, handle_signals)
    signal.signal(signal.SIGTERM, handle_signals)
    
    bot = ForexAIBot()
    bot.start()
