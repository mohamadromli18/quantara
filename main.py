import os
import yfinance as yf
from supabase import create_client, Client

# 1. Inisialisasi Koneksi ke Supabase
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_KEY")
supabase: Client = create_client(url, key)

def run_scraper():
    # 2. Ambil daftar ticker yang aktif dari master_ticker
    response = supabase.table("master_ticker").select("ticker_id").eq("is_active", True).execute()
    tickers = [row['ticker_id'] for row in response.data]
    
    if not tickers:
        print("Tidak ada ticker aktif di database.")
        return

    print(f"Menarik data pasar untuk: {tickers}")
    
    # 3. Tarik data yfinance dan masukkan ke Supabase
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

if __name__ == "__main__":
    run_scraper()