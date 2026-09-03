import os
import yfinance as yf
import pandas as pd
import requests
from supabase import create_client, Client

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_KEY")
supabase: Client = create_client(url, key)

def send_telegram_alert(message):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    
    if not token or not chat_id:
        print("⚠️ Kredensial Telegram tidak ditemukan!")
        return
        
    api_url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown"
    }
    
    try:
        requests.post(api_url, json=payload)
        print("✅ Notifikasi Telegram berhasil dikirim!")
    except Exception as e:
        print(f"❌ Gagal mengirim Telegram: {e}")

def run_scraper():
    print("Memulai penarikan data pasar...")
    response = supabase.table("master_ticker").select("ticker_id").eq("is_active", True).execute()
    tickers = [row['ticker_id'] for row in response.data]
    
    if not tickers:
        print("Tidak ada ticker aktif di database.")
        return

    print(f"Menarik data pasar untuk: {tickers}")
    
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
            
            supabase.table("eod_market_data").insert(payload).execute()
            print(f"✅ Sukses: {ticker} untuk tanggal {date_str}")
            
        except Exception as e:
            print(f"❌ Gagal memproses {ticker}: {e}")

def detect_anomalies():
    print("\nMemulai pemindaian anomali pasar...")
    
    response = supabase.table("master_ticker").select("ticker_id").eq("is_active", True).execute()
    tickers = [row['ticker_id'] for row in response.data]
    
    daily_alerts = [] 
    
    for ticker in tickers:
        try:
            history = supabase.table("eod_market_data").select("*").eq("ticker_id", ticker).order("trade_date", desc=True).limit(35).execute()
            
            if len(history.data) < 25:
                continue
                
            df = pd.DataFrame(history.data)
            df = df.sort_values("trade_date").reset_index(drop=True)
            
            df['Vol_SMA20'] = df['volume'].rolling(window=20).mean()
            df['High_20'] = df['high_price'].rolling(window=20).max().shift(1)
            df['Low_20'] = df['low_price'].rolling(window=20).min().shift(1)
            df['SMA_20'] = df['close_price'].rolling(window=20).mean()
            df['Std_20'] = df['close_price'].rolling(window=20).std()
            
            df['BB_Upper'] = df['SMA_20'] + (df['Std_20'] * 2)
            df['BB_Lower'] = df['SMA_20'] - (df['Std_20'] * 2)
            df['BB_Bandwidth'] = (df['BB_Upper'] - df['BB_Lower']) / df['SMA_20']
            
            delta = df['close_price'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            df['RSI_14'] = 100 - (100 / (1 + rs))
            
            latest = df.iloc[-1]
            prev = df.iloc[-2]
            
            anomalies = []
            
            if latest['volume'] > (2 * latest['Vol_SMA20']):
                anomalies.append("Volume Spike")
                
            if latest['close_price'] > latest['High_20']:
                anomalies.append("Breakout")
                
            if (latest['close_price'] < df.iloc[-5]['close_price']) and (latest['RSI_14'] > df.iloc[-5]['RSI_14']) and (latest['RSI_14'] < 40):
                anomalies.append("Bullish Divergence")
                
            if latest['BB_Bandwidth'] < 0.05:
                anomalies.append("Volatility Contraction")
                
            body = abs(latest['open_price'] - latest['close_price'])
            lower_shadow = min(latest['open_price'], latest['close_price']) - latest['low_price']
            if (lower_shadow > (2 * body)) and (latest['low_price'] <= (latest['Low_20'] * 1.02)) and (body > 0):
                anomalies.append("Support Rejection")
                
            if (latest['low_price'] < latest['Low_20']) and (latest['close_price'] > latest['Low_20']):
                anomalies.append("Bear Trap")
                
            if (latest['low_price'] > prev['high_price']) and (latest['volume'] > (1.5 * latest['Vol_SMA20'])):
                anomalies.append("Runaway Gap")
                
            if anomalies:
                anomaly_str = " & ".join(anomalies)
                print(f"🔥 JEJAK TERDETEKSI pada {ticker}: {anomaly_str}")
                
                payload = {
                    "ticker_id": ticker,
                    "detection_date": latest['trade_date'],
                    "anomaly_type": anomaly_str,
                    "probability_score": min(100, len(anomalies) * 15 + 40) 
                }
                
                supabase.table("watchlist_calon_raja").insert(payload).execute()
                
                daily_alerts.append(f"🎯 *{ticker}*: {anomaly_str}")
                
        except Exception as e:
            print(f"❌ Gagal memindai {ticker}: {e}")
            
    if daily_alerts:
        pesan = "📊 *Laporan Harian Quantara*\nJejak anomali terdeteksi hari ini:\n\n"
        pesan += "\n".join(daily_alerts)
        pesan += "\n\n_Silakan periksa chart untuk konfirmasi!_"
        send_telegram_alert(pesan)
    else:
        print("Tidak ada anomali kuat hari ini.")

if __name__ == "__main__":
    run_scraper()
    detect_anomalies()