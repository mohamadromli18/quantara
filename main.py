import os
import yfinance as yf
import pandas as pd
from supabase import create_client, Client

# 1. Inisialisasi Koneksi ke Supabase
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_KEY")
supabase: Client = create_client(url, key)

def run_scraper():
    print("Memulai penarikan data pasar...")
    # Ambil daftar ticker yang aktif dari master_ticker
    response = supabase.table("master_ticker").select("ticker_id").eq("is_active", True).execute()
    tickers = [row['ticker_id'] for row in response.data]
    
    if not tickers:
        print("Tidak ada ticker aktif di database.")
        return

    print(f"Menarik data pasar untuk: {tickers}")
    
    # Tarik data yfinance dan masukkan ke Supabase
    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="1d")
            
            if hist.empty:
                print(f"Data kosong untuk {ticker}")
                continue
                
            row = hist.iloc[-1]
            date_str = hist.index[-1].strftime('%Y-%m-%d')
            
            payload = {
                "ticker_id": ticker,
                "trade_date": date_str,
                "open_price": float(row['Open']),
                "high_price": float(row['High']),
                "low_price": float(row['Low']),
                "close_price": float(row['Close']),
                "volume": int(row['Volume'])
            }
            
            # Insert data ke Supabase
            supabase.table("eod_market_data").insert(payload).execute()
            print(f"✅ Sukses: {ticker} untuk tanggal {date_str}")
            
        except Exception as e:
            print(f"❌ Gagal memproses {ticker}: {e}")

def detect_anomalies():
    print("\nMemulai pemindaian anomali pasar...")
    
    response = supabase.table("master_ticker").select("ticker_id").eq("is_active", True).execute()
    tickers = [row['ticker_id'] for row in response.data]
    
    for ticker in tickers:
        try:
            history = supabase.table("eod_market_data").select("*").eq("ticker_id", ticker).order("trade_date", desc=True).limit(35).execute()
            
            if len(history.data) < 25:
                continue
                
            df = pd.DataFrame(history.data)
            df = df.sort_values("trade_date").reset_index(drop=True)
            
            # 1. Kalkulasi Indikator Dasar
            df['Vol_SMA20'] = df['volume'].rolling(window=20).mean()
            df['High_20'] = df['high_price'].rolling(window=20).max().shift(1)
            df['Low_20'] = df['low_price'].rolling(window=20).min().shift(1)
            df['SMA_20'] = df['close_price'].rolling(window=20).mean()
            df['Std_20'] = df['close_price'].rolling(window=20).std()
            
            # 2. Kalkulasi Volatilitas (Bollinger Bands)
            df['BB_Upper'] = df['SMA_20'] + (df['Std_20'] * 2)
            df['BB_Lower'] = df['SMA_20'] - (df['Std_20'] * 2)
            df['BB_Bandwidth'] = (df['BB_Upper'] - df['BB_Lower']) / df['SMA_20']
            
            # 3. Kalkulasi Momentum (RSI 14)
            delta = df['close_price'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            df['RSI_14'] = 100 - (100 / (1 + rs))
            
            # Ambil data 2 hari terakhir untuk perbandingan
            latest = df.iloc[-1]
            prev = df.iloc[-2]
            
            anomalies = []
            
            # --- BLOK LOGIKA 7 ANOMALI PASAR ---
            
            # Anomali 1: Volume Spike
            if latest['volume'] > (2 * latest['Vol_SMA20']):
                anomalies.append("Volume Spike")
                
            # Anomali 2: Breakout
            if latest['close_price'] > latest['High_20']:
                anomalies.append("Breakout")
                
            # Anomali 3: Bullish Divergence (Sederhana)
            # Harga lebih rendah dari 5 hari lalu, tapi momentum (RSI) meningkat
            if (latest['close_price'] < df.iloc[-5]['close_price']) and (latest['RSI_14'] > df.iloc[-5]['RSI_14']) and (latest['RSI_14'] < 40):
                anomalies.append("Bullish Divergence")
                
            # Anomali 4: Volatility Contraction
            # Lebar pita Bollinger sangat sempit (< 5%) menandakan konsolidasi ketat
            if latest['BB_Bandwidth'] < 0.05:
                anomalies.append("Volatility Contraction")
                
            # Anomali 5: Support Rejection (Pin Bar / Hammer)
            body = abs(latest['open_price'] - latest['close_price'])
            lower_shadow = min(latest['open_price'], latest['close_price']) - latest['low_price']
            # Ekor bawah 2x lebih panjang dari bodi, terjadi di area dekat support (toleransi 2%)
            if (lower_shadow > (2 * body)) and (latest['low_price'] <= (latest['Low_20'] * 1.02)) and (body > 0):
                anomalies.append("Support Rejection")
                
            # Anomali 6: Bear Trap (False Breakdown)
            # Sempat menjebol support ke bawah, tapi ditarik naik dan ditutup di atas support
            if (latest['low_price'] < latest['Low_20']) and (latest['close_price'] > latest['Low_20']):
                anomalies.append("Bear Trap")
                
            # Anomali 7: Runaway Gap
            # Melompat naik dari level tertinggi kemarin dengan volume tinggi
            if (latest['low_price'] > prev['high_price']) and (latest['volume'] > (1.5 * latest['Vol_SMA20'])):
                anomalies.append("Runaway Gap")
                
            # --- SIMPAN HASIL KE DATABASE ---
            if anomalies:
                anomaly_str = " & ".join(anomalies)
                print(f"🔥 JEJAK TERDETEKSI pada {ticker}: {anomaly_str}")
                
                payload = {
                    "ticker_id": ticker,
                    "detection_date": latest['trade_date'],
                    "anomaly_type": anomaly_str,
                    "probability_score": min(100, len(anomalies) * 15 + 40) # Dinamis berdasarkan jumlah anomali
                }
                
                supabase.table("watchlist_calon_raja").insert(payload).execute()
                
        except Exception as e:
            print(f"❌ Gagal memindai {ticker}: {e}")

if __name__ == "__main__":
    run_scraper()
    detect_anomalies()