import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

# 1. KONFIGURASI HALAMAN & STYLE BLOOMBERG TERMINAL
st.set_page_config(page_title="IDX BLOOMBERG TERMINAL", layout="wide", initial_sidebar_state="collapsed")

bloomberg_style = """
<style>
    /* Background Hitam Pekat ala Bloomberg */
    .stApp { background-color: #000000; color: #E0E0E0; font-family: 'Courier New', Courier, monospace; }
    /* Header Oranye/Amber */
    h1, h2, h3 { color: #FF9900 !important; font-family: 'Courier New', Courier, monospace; font-weight: bold; }
    /* Table Styling */
    div[data-testid="stTable"] { border: 1px solid #FF9900; }
    table { width: 100%; border-collapse: collapse; }
    th { background-color: #111111; color: #FF9900; border-bottom: 2px solid #FF9900; padding: 8px; text-align: left; font-size: 14px; }
    td { border-bottom: 1px solid #222222; padding: 8px; font-size: 13px; color: #CCCCCC; }
    /* Metric Card ala Terminal */
    .metric-card { background-color: #0d0d0d; border: 1px solid #FF9900; padding: 10px; border-radius: 0px; text-align: center; }
    .metric-title { color: #FF9900; font-size: 12px; }
    .metric-value { font-size: 20px; font-weight: bold; }
    .green-text { color: #00FF00; font-weight: bold; }
    .red-text { color: #FF0000; font-weight: bold; }
    .amber-text { color: #FF9900; font-weight: bold; }
</style>
"""
st.markdown(bloomberg_style, unsafe_allow_html=True)

# 2. DAFTAR SAHAM BEI (Bisa ditambah sesuai keinginan)
DEFAULT_TICKERS = [
    "BBCA.JK", "BBRI.JK", "BMRI.JK", "BBNI.JK", "TLKM.JK", 
    "ASII.JK", "ADRO.JK", "UNTR.JK", "PGAS.JK", "GOTO.JK", 
    "BRIS.JK", "ANTM.JK", "ICBP.JK", "KLBF.JK", "PTBA.JK"
]

# 3. FUNGSI PERHITUNGAN TEKNIKAL & STATISTIK
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
    mfi = 100 - (100 / (1 + (pos_flow_sum / neg_flow_sum)))
    return mfi

# 4. ENGINE UTAMA: ANALISA & SKORING
@st.cache_data(ttl=300) # Cache 5 menit
def analisa_saham(tickers):
    hasil = []
    for ticker in tickers:
        try:
            saham = yf.Ticker(ticker)
            df = saham.history(period="6mo")
            info = saham.info
            
            if df.empty or len(df) < 50:
                continue

            # Data Harga & Volume Terakhir
            close = df['Close'].iloc[-1]
            high_20 = df['High'].tail(20).max()
            low_20 = df['Low'].tail(20).min()
            vol_last = df['Volume'].iloc[-1]
            vol_avg = df['Volume'].tail(20).mean()

            # --- A. VALUE INVESTING (Max 25 Poin) ---
            pe = info.get('trailingPE', 0)
            pb = info.get('priceToBook', 0)
            roe = info.get('returnOnEquity', 0) * 100 if info.get('returnOnEquity') else 0
            
            val_score = 0
            if 0 < pe < 15: val_score += 10
            if 0 < pb < 2.0: val_score += 8
            if roe > 15: val_score += 7

            # --- B. ANALISA TRANSAKSI / BANDARMOLOGI (Max 25 Poin) ---
            # Proksi: Volume Spike + Price Action (Akumulasi)
            bandar_score = 0
            if vol_last > (vol_avg * 1.5) and df['Close'].iloc[-1] > df['Open'].iloc[-1]:
                bandar_score += 15 # Ada dorongan volume beli masif
            if df['Close'].iloc[-1] > df['Close'].tail(5).mean():
                bandar_score += 10 # Tren jangka pendek diakumulasi

            # --- C. SWING & MONEY FLOW (Max 35 Poin) ---
            df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
            df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
            df['RSI'] = hitung_rsi(df)
            df['MFI'] = hitung_mfi(df).iloc[-1]
            
            rsi_last = df['RSI'].iloc[-1]
            mfi_last = df['MFI']
            ema20 = df['EMA20'].iloc[-1]
            ema50 = df['EMA50'].iloc[-1]

            swing_score = 0
            if close > ema20 > ema50: swing_score += 15 # Uptrend terkonfirmasi
            if 40 <= rsi_last <= 60: swing_score += 10 # Ruang naik masih lebar
            if mfi_last > 50: swing_score += 10 # Arus uang masuk kuat

            # --- D. CORPORATE ACTION (Max 15 Poin) ---
            div_yield = (info.get('dividendYield', 0) or 0) * 100
            corp_score = 15 if div_yield > 5.0 else (10 if div_yield > 2.0 else 0)

            # --- TOTAL PROBABILITAS NAIK ---
            total_prob = val_score + bandar_score + swing_score + corp_score

            # --- RISK & REWARD (Persentase) ---
            # Target (Reward): Resistance tertinggi 20 hari atau +5% jika di harga tertinggi
            target_price = high_20 if high_20 > close else close * 1.05
            # Stop Loss (Risk): Support terendah 20 hari atau -3%
            stop_price = low_20 if low_20 < close else close * 0.97
            
            peluang_naik_pct = ((target_price - close) / close) * 100
            risiko_turun_pct = ((close - stop_price) / close) * 100
            rr_ratio = peluang_naik_pct / risiko_turun_pct if risiko_turun_pct > 0 else 0

            # --- SINYAL ---
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
        except Exception as e:
            continue
            
    return pd.DataFrame(hasil)

# 5. ANTARMUKA TERMINAL
st.markdown("<h1>> IDX QUANTITATIVE TERMINAL // BEI MONITOR</h1>", unsafe_allow_html=True)
st.markdown("---")

# Panel Kontrol
col1, col2 = st.columns([3, 1])
with col1:
    input_tickers = st.text_input("INPUT TICKER (Pisahkan dengan koma, gunakan format .JK):", 
                                  value=", ".join(DEFAULT_TICKERS))
with col2:
    st.markdown("<br>", unsafe_allow_html=True)
    run_btn = st.button("🚀 JALANKAN PEMANTAUAN", use_container_width=True)

tickers_to_run = [t.strip() for t in input_tickers.split(",")]

# Eksekusi Mesin
with st.spinner("MENGHUBUNGKAN KE FEED DATA BEI & MENGHITUNG ALGORITMA..."):
    df_result = analisa_saham(tickers_to_run)

if not df_result.empty:
    # Sortir berdasarkan Probabilitas Tertinggi
    df_result = df_result.sort_values(by="Probabilitas", ascending=False)
    
    # Ringkasan Pasar (Top Pick)
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
    st.markdown("### > LIVE STOCK MONITORING TABLE")
    
    # Render Tabel Formatting ala Bloomberg
    def color_prob(val):
        color = '#00FF00' if val >= 70 else ('#FF9900' if val >= 55 else '#FF0000')
        return f'color: {color}; font-weight: bold;'
        
    styled_df = df_result.style.applymap(color_prob, subset=['Probabilitas'])
    st.dataframe(styled_df, use_container_width=True, hide_index=True)
    
else:
    st.error("Data tidak ditemukan atau gagal ditarik dari API.")

st.markdown("---")
st.markdown("<div style='font-size: 11px; color: #666;'>SYSTEM DISCLAIMER: Probabilitas dihitung berdasarkan gabungan bobot Value Investing (25%), Bandarmologi/Volume Flow (25%), Technical Swing (35%), dan Corporate Action (15%). Bukan saran keuangan mutlak.</div>", unsafe_allow_html=True)
