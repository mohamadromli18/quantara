import os
import urllib.parse
import feedparser
import yfinance as yf
import requests
from google import genai
from supabase import create_client, Client

# Inisialisasi Koneksi Supabase
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
SUPABASE: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Inisialisasi Kredensial Telegram & Gemini
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_NEWS_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_NEWS_CHAT_ID")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# Konfigurasi Client Gemini AI (menggunakan google-genai SDK terbaru)
ai_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

# Daftar topik komoditas & makro yang ingin dipantau
COMMODITY_TARGETS = [
    {
        "category": "Gula",
        "ticker": "SB=F", # Sugar Futures
        "query": "harga gula OR emiten gula OR gula mentah",
        "affected": ["ICBP.JK", "MYOR.JK", "SIDO.JK"]
    },
    {
        "category": "Batu Bara",
        "ticker": None, # Newcastle Coal Futures
        "query": "harga batu bara OR ekspor batu bara OR emiten batu bara",
        "affected": ["ADRO.JK", "PTBA.JK", "ITMG.JK", "BYAN.JK", "HRUM.JK"]
    },
    {
        "category": "Nikel & Tambang",
        "ticker": None, # Menggunakan indikator berita/makro jika ticker global tidak stabil
        "query": "harga nikel OR smelter nikel OR emiten nikel",
        "affected": ["INCO.JK", "ANTM.JK", "MBMA.JK", "NCKL.JK", "TINS.JK"]
    },
    {
        "category": "Shipping & Logistik (Tongkang)",
        "ticker": None, 
        "query": "sewa kapal tongkang OR tarif angkut komoditas OR shipping logistik",
        "affected": ["SMDR.JK", "TMAS.JK", "BIRD.JK", "HAIS.JK", "PSSI.JK"]
    },
    {
        "category": "Gandum & Kakao",
        "ticker": "CC=F", # Cocoa Futures
        "query": "harga gandum OR harga kakao cokelat OR emiten konsumsi",
        "affected": ["ICBP.JK", "INDF.JK", "MYOR.JK"]
    }
]

def fetch_commodity_price(ticker_symbol):
    """Fungsi fleksibel untuk mengecek harga komoditas via yfinance"""
    if not ticker_symbol:
        return "N/A (Indikator Makro/Logistik)"
    try:
        data = yf.Ticker(ticker_symbol)
        hist = data.history(period="1d")
        if not hist.empty:
            price = hist.iloc[-1]['Close']
            return f"{price:.2f}"
    except Exception as e:
        print(f"Gagal ambil harga {ticker_symbol}: {e}")
    return "Data tidak tersedia"

def analyze_with_ai(news_title, news_summary, category):
    """
    Menggunakan Google Gemini API untuk analisis sentimen, dampak emiten, dan rekomendasi aksi secara dinamis.
    """
    default_score = 0.5
    default_impact = "Pergerakan makro berdampak secara tidak langsung terhadap operasional emiten."
    default_action = "Pantau perkembangan berita lanjutan di sektor terkait."

    if not ai_client:
        return default_score, default_impact, default_action

    prompt = f"""
    Bertindaklah sebagai Analis Pasar Keuangan Senior IHSG. Analisis berita berikut untuk kategori komoditas/makro: {category}.
    Judul Berita: {news_title}
    Ringkasan: {news_summary}

    Berikan hasil analisis dalam format persis seperti ini tanpa teks tambahan di luar format:
    SKOR: [Angka desimal antara 0.0 sampai 1.0, di mana 1.0 sangat positif/bullish dan 0.0 sangat negatif/bearish]
    DAMPAK: [Penjelasan singkat 1-2 kalimat mengenai dampak terhadap margin atau biaya emiten terkait]
    AKSI: [Rekomendasi taktis singkat bagi investor saham]
    """

    try:
        response = ai_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        text = response.text.strip()
        
        # Parsing sederhana hasil dari respons AI
        lines = text.split("\n")
        score = default_score
        impact = default_impact
        action = default_action
        
        for line in lines:
            if line.startswith("SKOR:"):
                try:
                    score = float(line.replace("SKOR:", "").strip())
                except ValueError:
                    pass
            elif line.startswith("DAMPAK:"):
                impact = line.replace("DAMPAK:", "").strip()
            elif line.startswith("AKSI:"):
                action = line.replace("AKSI:", "").strip()
                
        return score, impact, action
    except Exception as e:
        print(f"❌ Gagal memproses analisis Gemini AI: {e}")
        return default_score, default_impact, default_action

def run_news_scanner():
    print("🔍 Memulai pemindaian berita multi-komoditas & sentimen pasar...")
    
    for target in COMMODITY_TARGETS:
        category = target["category"]
        raw_query = target["query"]
        encoded_query = urllib.parse.quote(raw_query)
        rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=id&gl=ID&ceid=ID:id"
        
        feed = feedparser.parse(rss_url)
        current_price = fetch_commodity_price(target["ticker"])
        
        # Ambil 2 berita paling mutakhir per kategori
        for entry in feed.entries[:2]:
            url = entry.link
            
            # 1. Cek Duplikasi ke Supabase
            existing = SUPABASE.table("news_sentiments").select("id").eq("news_url", url).execute()
            if existing.data:
                continue
                
            title = entry.title
            summary = entry.get("summary", "")
            
            # 2. Analisis Sentimen (AI) - DIPERBAIKI: Menerima 3 return value secara pas
            score, impact, action = analyze_with_ai(title, summary, category)
            affected_tickers = target["affected"]
            
            # 3. Simpan Log ke Supabase
            payload = {
                "news_title": title,
                "news_url": url,
                "category": category,
                "sentiment_score": score,
                "affected_tickers": affected_tickers,
                "impact_analysis": impact,
                "recommended_action": action,
                "commodity_price": str(current_price)
            }
            SUPABASE.table("news_sentiments").insert(payload).execute()
            
            # 4. Format & Kirim Notifikasi Telegram Khusus Berita
            message = (
                f"🚨 *QUANTARA NEWS RADAR [{category.upper()}]*\n\n"
                f"📰 *Judul:* {title}\n"
                f"📊 *Skor Sentimen:* `{score} / 1.0`\n"
                f"📈 *Harga Komoditas Acuan:* `{current_price}`\n"
                f"🏭 *Emiten Terdampak:* `{', '.join(affected_tickers)}`\n\n"
                f"💡 *Analisis Dampak:*\n{impact}\n\n"
                f"🛠 *Action Plan:*\n{action}\n\n"
                f"🔗 [Baca Berita Selengkapnya]({url})"
            )
            
            send_telegram_alert(message)
            print(f"✅ Notifikasi berita baru terkirim: {category} - {title[:30]}...")

def send_telegram_alert(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Kredensial Telegram News tidak ditemukan!")
        return
    api_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": False
    }
    try:
        requests.post(api_url, json=payload)
        print("✅ Notifikasi Berita Telegram terkirim!")
    except Exception as e:
        print(f"❌ Gagal kirim Telegram: {e}")

if __name__ == "__main__":
    run_news_scanner()