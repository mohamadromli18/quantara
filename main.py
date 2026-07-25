import pandas as pd

def detect_anomalies():
    print("Memulai pemindaian anomali pasar...")
    
    # 1. Ambil daftar ticker
    response = supabase.table("master_ticker").select("ticker_id").eq("is_active", True).execute()
    tickers = [row['ticker_id'] for row in response.data]
    
    for ticker in tickers:
        try:
            # 2. Tarik data historis (30 baris terakhir) untuk kalkulasi
            history = supabase.table("eod_market_data").select("*").eq("ticker_id", ticker).order("trade_date", desc=True).limit(30).execute()
            
            if len(history.data) < 20:
                print(f"Data tidak cukup untuk {ticker} (butuh minimal 20 hari).")
                continue
                
            # 3. Ubah ke Pandas DataFrame dan urutkan dari tanggal terlama ke terbaru
            df = pd.DataFrame(history.data)
            df = df.sort_values("trade_date").reset_index(drop=True)
            
            # 4. Kalkulasi Indikator Kuantitatif Dasar
            # SMA 20 untuk Volume
            df['Vol_SMA20'] = df['volume'].rolling(window=20).mean()
            # Nilai Tertinggi 20 Hari (Resistensi), digeser 1 hari agar tidak menghitung hari ini
            df['High_20'] = df['high_price'].rolling(window=20).max().shift(1) 
            
            # Ambil data hari terakhir (hari ini)
            latest = df.iloc[-1]
            
            anomalies = []
            
            # Logika Anomali 1: Volume Spike (Volume hari ini > 200% dari rata-rata 20 hari)
            if latest['volume'] > (2 * latest['Vol_SMA20']):
                anomalies.append("Volume Spike")
                
            # Logika Anomali 2: Breakout (Harga penutupan hari ini menembus resistensi 20 hari terakhir)
            if latest['close_price'] > latest['High_20']:
                anomalies.append("Breakout")
                
            # 5. Jika ada anomali, catat ke Watchlist Calon Raja
            if anomalies:
                anomaly_str = " & ".join(anomalies)
                print(f"🔥 JEJAK TERDETEKSI pada {ticker}: {anomaly_str}")
                
                payload = {
                    "ticker_id": ticker,
                    "detection_date": latest['trade_date'],
                    "anomaly_type": anomaly_str,
                    "probability_score": 75 # Skor statis sementara, akan didinamiskan nanti
                }
                
                supabase.table("watchlist_calon_raja").insert(payload).execute()
                
        except Exception as e:
            print(f"❌ Gagal memindai {ticker}: {e}")

# Ubah blok pengeksekusi utama di paling bawah file:
if __name__ == "__main__":
    run_scraper()
    detect_anomalies()