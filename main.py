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
    
    # Ambil daftar ticker
    response = supabase.table("master_ticker").select("ticker_id").eq("is_active", True).execute()
    tickers = [row['ticker_id'] for row in response.data]
    
    for ticker in tickers:
        try:
            # Tarik data historis (30 baris terakhir) untuk kalkulasi
            history = supabase.table("eod_market_data").select("*").eq("ticker_id", ticker).order("trade_date", desc=True).limit(30).execute()
            
            if len(history.data) < 20:
                print(f"Data tidak cukup untuk {ticker} (butuh minimal 20 hari).")
                continue
                
            # Ubah ke Pandas DataFrame dan urutkan dari tanggal terlama ke terbaru
            df = pd.DataFrame(history.data)
            df = df.sort_values("trade_date").reset_index(drop=True)
            
            # Kalkulasi Indikator Kuantitatif Dasar
            df['Vol_SMA20'] = df['volume'].rolling(window=20).mean()
            df['High_20'] = df['high_price'].rolling(window=20).max().shift(1) 
            
            latest = df.iloc[-1]
            anomalies = []
            
            # Logika Anomali 1: Volume Spike
            if latest['volume'] > (2 * latest['Vol_SMA20']):
                anomalies.append("Volume Spike")
                
            # Logika Anomali 2: Breakout
            if latest['close_price'] > latest['High_20']:
                anomalies.append("Breakout")
                
            # Jika ada anomali, catat ke Watchlist
            if anomalies:
                anomaly_str = " & ".join(anomalies)
                print(f"🔥 JEJAK TERDETEKSI pada {ticker}: {anomaly_str}")
                
                payload = {
                    "ticker_id": ticker,
                    "detection_date": latest['trade_date'],
                    "anomaly_type": anomaly_str,
                    "probability_score": 75 
                }
                
                supabase.table("watchlist_calon_raja").insert(payload).execute()
                
        except Exception as e:
            print(f"❌ Gagal memindai {ticker}: {e}")

if __name__ == "__main__":
    run_scraper()
    detect_anomalies()