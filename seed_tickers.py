import os
from supabase import create_client, Client

# Inisialisasi Koneksi (Pastikan Anda sudah melakukan export SUPABASE_URL & KEY di terminal)
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_KEY")
supabase: Client = create_client(url, key)

# Daftar saham liquid terkurasi berdasarkan sektor strategis
tickers_to_add = [
    # Sektor Keuangan (Finance)
    "BBCA.JK", "BBRI.JK", "BMRI.JK", "BBNI.JK", "ARTO.JK", "BRIS.JK", "BBTN.JK", "BNGA.JK",
    # Sektor Energi (Energy)
    "ADRO.JK", "PTBA.JK", "ITMG.JK", "PGAS.JK", "MEDC.JK", "AKRA.JK", "HRUM.JK", "INDY.JK",
    # Sektor Infrastruktur (Infrastructure)
    "TLKM.JK", "JSMR.JK", "EXCL.JK", "ISAT.JK", "TBIG.JK", "TOWR.JK", "MTEL.JK", "WIKA.JK",
    # Sektor Kesehatan & Konsumsi (Health & Consumer)
    "KLBF.JK", "MIKA.JK", "HEAL.JK", "ICBP.JK", "INDF.JK", "UNVR.JK", "MYOR.JK", "AMRT.JK",
    # Sektor Material Dasar (Basic Materials)
    "ASII.JK", "UNTR.JK", "ANTM.JK", "INCO.JK", "MDKA.JK", "SMGR.JK", "INTP.JK", "BRPT.JK",
    # Sektor Teknologi & Lainnya
    "GOTO.JK", "BUKA.JK", "AMMN.JK", "BREN.JK", "CUAN.JK"
]

print("Menyuntikkan data ticker ke Supabase...")

for ticker in tickers_to_add:
    try:
        # Menggunakan upsert agar tidak duplikat jika saham sudah ada di database
        supabase.table("master_ticker").upsert({
            "ticker_id": ticker,
            "is_active": True
        }).execute()
        print(f"✅ Berhasil ditambahkan: {ticker}")
    except Exception as e:
        print(f"❌ Gagal memproses {ticker}: {e}")

print("\nProses pembaruan master_ticker selesai!")