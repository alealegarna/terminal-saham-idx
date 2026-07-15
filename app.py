import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import time
import requests
from datetime import datetime

# 1. KONFIGURASI HALAMAN & STYLE BLOOMBERG TERMINAL
st.set_page_config(page_title="IDX BLOOMBERG TERMINAL - 24/7 ENGINE", layout="wide", initial_sidebar_state="collapsed")

bloomberg_style = """
<style>
    .stApp { background-color: #000000; color: #E0E0E0; font-family: 'Courier New', Courier, monospace; }
    h1, h2, h3 { color: #FF9900 !important; font-family: 'Courier New', Courier, monospace; font-weight: bold; }
    div[data-testid="stTable"] { border: 1px solid #FF9900; }
    table { width: 100%; border-collapse: collapse; }
    th { background-color: #111111; color: #FF9900; border-bottom: 2px solid #FF9900; padding: 8px; text-align: left; font-size: 14px; }
    td { border-bottom: 1px solid #222222; padding: 8px; font-size: 13px; color: #CCCCCC; }
    .metric-card { background-color: #0d0d0d; border: 1px solid #FF9900; padding: 10px; text-align: center; }
    .metric-title { color: #FF9900; font-size: 12px; }
    .metric-value { font-size: 20px; font-weight: bold; }
    .green-text { color: #00FF00; font-weight: bold; }
    .red-text { color: #FF0000; font-weight: bold; }
    .amber-text { color: #FF9900; font-weight: bold; }
    .status-box { padding: 8px; border: 1px solid #00FF00; background-color: #001a00; color: #00FF00; text-align: center; font-weight: bold; margin-bottom: 15px; }
</style>
"""
st.markdown(bloomberg_style, unsafe_allow_html=True)

# 2. FUNGSI PENCULIK DAFTAR SAHAM OTOMATIS (WEB SCRAPER)
@st.cache_data(ttl=86400)
def ambil_daftar_saham(mode):
    if mode == "🔥 LQ45 (45 Saham Paling Likuid & Aktif)":
        return [
            "BBCA.JK", "BBRI.JK", "BMRI.JK", "BBNI.JK", "TLKM.JK", "ASII.JK", "ADRO.JK", "UNTR.JK", "PGAS.JK", "GOTO.JK", 
            "BRIS.JK", "ANTM.JK", "ICBP.JK", "KLBF.JK", "PTBA.JK", "AMRT.JK", "CPIN.JK", "EXCL.JK", "INDF.JK", "INKP.JK", 
            "INCO.JK", "ITMG.JK", "MEDC.JK", "MDKA.JK", "PGEO.JK", "PTMP.JK", "SIDO.JK", "SMGR.JK", "UNVR.JK", "AKRA.JK", 
            "AMMN.JK", "ARTO.JK", "BRPT.JK", "BUKA.JK", "EMTK.JK", "ESSA.JK", "HRUM.JK", "INTP.JK", "MBMA.JK", "MTEL.JK", 
            "PTPP.JK", "SCMA.JK", "TOWR.JK", "WIKA.JK"
        ]
    elif mode == "🌌 SEMUA EMITEN BEI (~900+ Saham - Sapu Jagat)":
        try:
            url = "https://id.wikipedia.org/wiki/Daftar_emiten_di_Bursa_Efek_Indonesia"
            tables = pd.read_html(url)
            tickers = []
            for df in tables:
                for col in df.columns:
                    if str(col).strip().lower() in ['kode', 'kode saham', 'ticker', 'emiten']:
                        t_list = df[col].dropna().astype(str).tolist()
                        for t in t_list:
                            clean_t = t.strip().upper()
                            if len(clean_t) == 4 and clean_t.isalpha():
                                tickers.append(clean_t + ".JK")
            if tickers:
                return sorted(list(set(tickers)))
        except Exception:
            pass
    return ["BBCA.JK", "BBRI.JK", "BMRI.JK", "BBNI.JK", "TLKM.JK", "ASII.JK", "ADRO.JK", "GOTO.JK", "BRIS.JK", "ANTM.JK"]

def hitung_rsi(data, window=14):
    delta = data['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def hitung_mfi(data, window=14):
    typical_price = (data['High'] + data['Low'] + data['Close']) / 3
    money_flow = typical_price * data['Volume']
    positive_flow = np.where(typical_price > typical_price.shift(1), money_flow, 0)
    negative_flow = np.where(typical_price < typical_price.shift(1), money_flow, 0)
    pos_flow_sum = pd.Series(positive_flow).rolling(window=window).sum()
    neg_flow_sum = pd.Series(negative_flow).rolling(window=window).sum()
    return 100 - (100 / (1 + (pos_flow_sum / neg_flow_sum)))

# 3. ENGINE UTAMA 24/7 (ANTI-LIBUR / ANTI-PASAR TUTUP)
def analisa_pasar_masal(tickers, progress_bar, status_text):
    hasil = []
    total_saham = len(tickers)
    tanggal_data_terakhir = "N/A"
    
    for i, ticker in enumerate(tickers):
        progress_pct = int(((i + 1) / total_saham) * 100)
        progress_bar.progress(progress_pct)
        status_text.markdown(f"**> SCANNING RADAR [{i+1}/{total_saham}]:** Memindai `{ticker}`... *(Mode 24/7 Aktif)*")
        
        try:
            saham = yf.Ticker(ticker)
            df = saham.history(period="6mo")
            
            # --- RAHASIA 24/7: PEMBERSIH BAR HANTU ---
            # Hapus data yang volumenya 0 atau kosong (hari libur/akhir pekan yang disisipkan Yahoo)
            df = df.dropna(subset=['Close', 'Volume'])
            df = df[df['Volume'] > 0] 
            
            # Jika setelah dibersihkan datanya tinggal sedikit / kosong, berarti saham mati permanen
            if df.empty or len(df) < 50:
                continue

            # Ambil tanggal dari baris terakhir yang valid untuk info di layar
            if tanggal_data_terakhir == "N/A":
                tanggal_data_terakhir = str(df.index[-1].date())

            # --- RADAR PRE-FILTER ---
            # Karena sudah difilter df['Volume'] > 0 di atas, iloc[-1] DIJAMIN adalah hari kerja terakhir!
            if df['Close'].iloc[-1] <= 50:
                continue # Tetap lewati saham gocap/tidur

            info = saham.info
            close = df['Close'].iloc[-1]
            high_20 = df['High'].tail(20).max()
            low_20 = df['Low'].tail(20).min()
            vol_last = df['Volume'].iloc[-1]
            vol_avg = df['Volume'].tail(20).mean()

            # --- A. VALUE INVESTING (Max 25 Poin) ---
            pe = info.get('trailingPE', 0) or 0
            pb = info.get('priceToBook', 0) or 0
            roe = (info.get('returnOnEquity', 0) or 0) * 100
            
            val_score = 0
            if 0 < pe < 15: val_score += 10
            if 0 < pb < 2.0: val_score += 8
            if roe > 15: val_score += 7

            # --- B. ANALISA TRANSAKSI / BANDARMOLOGI (Max 25 Poin) ---
            bandar_score = 0
            if vol_last > (vol_avg * 1.5) and df['Close'].iloc[-1] > df['Open'].iloc[-1]:
                bandar_score += 15
            if df['Close'].iloc[-1] > df['Close'].tail(5).mean():
                bandar_score += 10

            # --- C. SWING & MONEY FLOW (Max 35 Poin) ---
            df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
            df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
            df['RSI'] = hitung_rsi(df)
            df['MFI'] = hitung_mfi(df)
            
            rsi_last = df['RSI'].iloc[-1]
            mfi_last = df['MFI'].iloc[-1] if not pd.isna(df['MFI'].iloc[-1]) else 50
            ema20 = df['EMA20'].iloc[-1]
            ema50 = df['EMA50'].iloc[-1]

            swing_score = 0
            if close > ema20 > ema50: swing_score += 15
            if 40 <= rsi_last <= 60: swing_score += 10
            if mfi_last > 50: swing_score += 10

            # --- D. CORPORATE ACTION (Max 15 Poin) ---
            div_yield = (info.get('dividendYield', 0) or 0) * 100
            corp_score = 15 if div_yield > 5.0 else (10 if div_yield > 2.0 else 0)

            # --- TOTAL PROBABILITAS & RISK/REWARD ---
            total_prob = val_score + bandar_score + swing_score + corp_score
            target_price = high_20 if high_20 > close else close * 1.05
            stop_price = low_20 if low_20 < close else close * 0.97
            
            peluang_naik_pct = ((target_price - close) / close) * 100
            risiko_turun_pct = ((close - stop_price) / close) * 100
            rr_ratio = peluang_naik_pct / risiko_turun_pct if risiko_turun_pct > 0 else 0

            if total_prob >= 70 and rr_ratio > 1.5:
                sinyal = "STRONG BUY 🟢"
            elif total_prob >= 55:
                sinyal = "BUY / HOLD 🟡"
            else:
                sinyal = "WAIT / SELL 🔴"

            hasil.append({
                "Ticker": ticker.replace(".JK", ""),
                "Harga": f"Rp {int(close):,}",
                "Probabilitas": total_prob,
                "Sinyal": sinyal,
                "Peluang (+)": f"+{peluang_naik_pct:.1f}%",
                "Risiko (-)": f"-{risiko_turun_pct:.1f}%",
                "R:R Ratio": f"{rr_ratio:.2f}x",
                "PER": f"{pe:.1f}x" if pe > 0 else "N/A",
                "Div Yield": f"{div_yield:.1f}%",
                "MFI (Flow)": f"{mfi_last:.1f}"
            })
            time.sleep(0.05)
            
        except Exception:
            continue
            
    return pd.DataFrame(hasil), tanggal_data_terakhir

# 4. ANTARMUKA TERMINAL
st.markdown("<h1>> IDX QUANTITATIVE TERMINAL // 24/7 ALL-WEATHER ENGINE</h1>", unsafe_allow_html=True)
st.markdown("<div class='status-box'>⚡ SYSTEM READY 24/7: Jika bursa tutup/libur, sistem otomatis menganalisa data penutupan hari kerja terakhir (EOD).</div>", unsafe_allow_html=True)
st.markdown("---")

col1, col2 = st.columns([3, 1])
with col1:
    mode_pilihan = st.selectbox(
        "PILIH RUANG LINGKUP PEMANTAUAN PASAR:",
        [
            "🔥 LQ45 (45 Saham Paling Likuid & Aktif)",
            "🌌 SEMUA EMITEN BEI (~900+ Saham - Sapu Jagat)",
            "✍️ Input Manual Kustom"
        ]
    )
    
    if mode_pilihan == "✍️ Input Manual Kustom":
        input_tickers = st.text_input("Ketik kode saham (pisahkan dengan koma):", "BBCA.JK, BBRI.JK, BMRI.JK, BBNI.JK")
        tickers_to_run = [t.strip().upper() + (".JK" if not t.strip().endswith(".JK") else "") for t in input_tickers.split(",") if t.strip()]
    else:
        tickers_to_run = ambil_daftar_saham(mode_pilihan)
        st.caption(f"ℹ️ Sistem siap memindai **{len(tickers_to_run)} saham** pada mode ini.")

with col2:
    st.markdown("<br>", unsafe_allow_html=True)
    run_btn = st.button("🚀 JALANKAN RADAR PASAR", use_container_width=True)

if run_btn:
    st.markdown("---")
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    df_result, tgl_terakhir = analisa_pasar_masal(tickers_to_run, progress_bar, status_text)
    
    progress_bar.empty()
    status_text.markdown(f"### ✅ PEMINDAIAN SELESAI! (Berbasis Data Perdagangan Terakhir: **{tgl_terakhir}**)")
    
    if not df_result.empty:
        df_result = df_result.sort_values(by="Probabilitas", ascending=False)
        top_pick = df_result.iloc[0]
        
        st.markdown("### > TOP RECOMMENDED STOCK BY SYSTEM")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.markdown(f'<div class="metric-card"><div class="metric-title">TOP TICKER</div><div class="metric-value amber-text">{top_pick["Ticker"]}</div></div>', unsafe_allow_html=True)
        with c2:
            st.markdown(f'<div class="metric-card"><div class="metric-title">PROBABILITAS NAIK</div><div class="metric-value green-text">{top_pick["Probabilitas"]}%</div></div>', unsafe_allow_html=True)
        with c3:
            st.markdown(f'<div class="metric-card"><div class="metric-title">PELUANG (REWARD)</div><div class="metric-value green-text">{top_pick["Peluang (+)"]}</div></div>', unsafe_allow_html=True)
        with c4:
            st.markdown(f'<div class="metric-card"><div class="metric-title">RISIKO (STOP LOSS)</div><div class="metric-value red-text">{top_pick["Risiko (-)"]}</div></div>', unsafe_allow_html=True)
        
        st.markdown("---")
        st.markdown(f"### > LIVE / EOD STOCK MONITORING TABLE ({len(df_result)} Saham Aktif Lolos Filter)")
        
        def color_prob(val):
            color = '#00FF00' if val >= 70 else ('#FF9900' if val >= 55 else '#FF0000')
            return f'color: {color}; font-weight: bold;'
            
        styled_df = df_result.style.applymap(color_prob, subset=['Probabilitas'])
        st.dataframe(styled_df, use_container_width=True, hide_index=True)
        
    else:
        st.error("❌ Tidak ada saham yang lolos filter.")

st.markdown("---")
st.markdown("<div style='font-size: 11px; color: #666;'>SYSTEM DISCLAIMER: Algoritma otomatis memfilter hari perdagangan aktif (Volume > 0). Jika bursa tutup, perhitungan probabilitas dan R:R didasarkan pada harga penutupan hari kerja terakhir (End-of-Day).</div>", unsafe_allow_html=True)
