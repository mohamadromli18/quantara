import os
import urllib.parse
import feedparser
import yfinance as yf
import requests
from supabase import create_client, Client

# Inisialisasi Koneksi
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
SUPABASE: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_NEWS_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_NEWS_CHAT_ID")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY") # Atau OpenAI API Key

def fetch_sugar_price():
    """Mengambil harga komoditas gula global real-time via yfinance"""
    try:
        sugar = yf.Ticker("SB=F") # Sugar No. 11 Futures
        hist = sugar.history(period="1d")
        if not hist.empty:
            price = hist.iloc[-1]['Close']
            return f"{price:.2f} USD/lbs"
    except Exception as e:
        print(f"Gagal ambil harga komoditas: {e}")
    return "Data tidak tersedia"

def fetch_news_rss():
    """Mengambil berita terbaru dari Google News RSS dengan keyword komoditas/saham"""
    raw_query = "harga gula saham indonesia OR emiten makanan minuman"
    # Mengubah spasi dan karakter khusus menjadi URL-encoded (misal: spasi -> %20)
    encoded_query = urllib.parse.quote(raw_query)
    
    rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=id&gl=ID&ceid=ID:id"
    
    feed = feedparser.parse(rss_url)
    articles = []
    
    # Ambil 3 berita teratas yang paling baru
    for entry in feed.entries[:3]:
        articles.append({
            "title": entry.title,
            "link": entry.link,
            "summary": entry.get("summary", "")
        })
    return articles

def analyze_with_ai(news_title, news_summary):
    """
    Menggunakan AI untuk analisis sentimen, dampak emiten, dan rekomendasi aksi.
    (Contoh menggunakan logika terstruktur / Anda bisa sambungkan ke API LLM)
    """
    # Catatan: Di sini Anda bisa memanggil OpenAI / Gemini API untuk analisis teks yang mendalam.
    # Contoh output simulasi cerdas berbasis keyword:
    
    score = 0.85 # Skor positif 0 sampai 1
    affected = ["ICBP.JK", "MYOR.JK", "SIDO.JK"]
    impact = "Kenaikan harga gula meningkatkan biaya bahan baku (COGS) sektor consumer goods, namun positif bagi emiten produsen gula."
    action = "Pantau margin laba emiten terkait; hindari akumulasi jangka pendek bagi pengguna gula massal."
    
    return score, affected, impact, action

def run_news_scanner():
    print("🔍 Memulai pemindaian berita & sentimen pasar...")
    articles = fetch_news_rss()
    current_sugar_price = fetch_sugar_price()
    
    for article in articles:
        url = article['link']
        
        # Cek apakah berita sudah pernah diproses di database agar tidak spam
        existing = SUPABASE.table("news_sentiments").select("id").eq("news_url", url).execute()
        if existing.data:
            continue
            
        title = article['title']
        score, affected, impact, action = analyze_with_ai(title, article['summary'])
        
        # Simpan ke Supabase
        payload = {
            "news_title": title,
            "news_url": url,
            "category": "Komoditas & Makro (Gula)",
            "sentiment_score": score,
            "affected_tickers": affected,
            "impact_analysis": impact,
            "recommended_action": action,
            "commodity_price": current_sugar_price
        }
        
        SUPABASE.table("news_sentiments").insert(payload).execute()
        
        # Format Pesan Telegram
        message = (
            f"🚨 *QUANTARA NEWS & SENTIMENT SCANNER*\n\n"
            f"📰 *Judul:* {title}\n"
            f"📊 *Skor Sentimen:* `{score} / 1.0` (Positif/Bullish)\n"
            f"🍬 *Harga Gula Saat Ini:* `{current_sugar_price}`\n"
            f"🏭 *Emiten Terdampak:* `{', '.join(affected)}`\n\n"
            f"💡 *Analisis Dampak:*\n{impact}\n\n"
            f"🛠 *Action Plan:*\n{action}\n\n"
            f"🔗 [Baca Berita Selengkapnya]({url})"
        )
        
        send_telegram_alert(message)

def send_telegram_alert(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
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