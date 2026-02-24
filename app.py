import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from fpdf import FPDF
import time

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Strategic Equity Terminal Pro", layout="wide")

# Tema
tema = st.sidebar.radio("Tema Dashboard:", ["Dark", "Light"])
if tema == "Dark":
    st.markdown("<style>.main { background-color: #0e1117; color: white; } .stMetric { background-color: #161b22; border: 1px solid #30363d; }</style>", unsafe_allow_html=True)

# --- CARICAMENTO TICKER DAL CSV ---
@st.cache_data
def load_tickers():
    try:
        df = pd.read_csv('lista_ticker.csv')
        col = 'Ticker' if 'Ticker' in df.columns else df.columns[0]
        return [t.strip().upper() for t in df[col].dropna().unique().tolist()]
    except:
        return ["AAPL", "MSFT", "NVDA", "GOOGL"]

TICKERS_LIST = load_tickers()

# --- GESTORE RICHIESTE CON BACKOFF ---
@st.cache_data(ttl=86400) # Cache di 24 ore per non sovraccaricare Yahoo
def fetch_full_data(ticker):
    s = yf.Ticker(ticker)
    try:
        # Chiamata 1: Info base (Veloce)
        info = s.info
        if not info or 'currentPrice' not in info:
            return None
        
        # Chiamata 2: Dati Storici (Macro/Trend)
        history = s.history(period="1y")

        # Chiamata 3: Bilanci (Il punto critico)
        # Usiamo i nuovi metodi più stabili
        f = s.financials
        c = s.cashflow
        b = s.balance_sheet
        qb = s.quarterly_balance_sheet
        q_f = s.quarterly_financials
        
        return {
            "info": info, "f": f, "c": c, "b": b, "qb": qb, "q_f": q_f, "history": history
        }
    except Exception as e:
        return str(e)

# --- LOGICA MACRO ---
@st.cache_data(ttl=3600)
def get_macro_summary(period_label):
    p_map = {"5 Giorni": "5d", "Mensile": "1mo", "YTD": "ytd"}
    sectors = {'XLK':'Tech', 'XLF':'Fin', 'XLV':'Health', 'XLE':'Energy', 'XLI':'Ind', 'XLU':'Util', 'XLP':'Staples'}
    res = {}
    for etf, name in sectors.items():
        try:
            d = yf.Ticker(etf).history(period=p_map[period_label])
            res[name] = ((d['Close'].iloc[-1] / d['Close'].iloc[0]) - 1) * 100
        except: res[name] = 0
    return res

# --- UI MAIN ---
st.title("🏛️ Strategic Equity Terminal Pro")

# 1. SEZIONE MACRO
t_macro = st.radio("Finestra Temporale:", ["5 Giorni", "Mensile", "YTD"], horizontal=True)
macro_res = get_macro_summary(t_macro)
m_cols = st.columns(len(macro_res))
for idx, (name, val) in enumerate(macro_res.items()):
    m_cols[idx].metric(name, f"{val:.1f}%")



st.divider()

# 2. SELEZIONE ASSET
st.sidebar.subheader("🏢 Selezione Asset")
tk_sel = st.sidebar.selectbox("Seleziona Titolo dal CSV:", TICKERS_LIST)

if tk_sel:
    with st.spinner(f"Sincronizzazione dati per {tk_sel}..."):
        data_bundle = fetch_full_data(tk_sel)

    if isinstance(data_bundle, dict):
        # Estrazione Dati
        info = data_bundle['info']
        f, c, b, qb, q_f = data_bundle['f'], data_bundle['c'], data_bundle['b'], data_bundle['qb'], data_bundle['q_f']

        def gv(df, keys):
            if df is None or df.empty: return 0
            for k in keys:
                if k in df.index:
                    val = df.loc[k]
                    return val.iloc[0] if isinstance(val, (pd.Series, pd.DataFrame)) else val
            return 0

        # Calcoli Metriche e Valutazione
        p = info.get('currentPrice', 0)
        e = info.get('trailingEps', 1)
        sh = info.get('sharesOutstanding', 1)
        ni = gv(f, ['Net Income'])
        fcf = info.get('freeCashflow', ni * 0.8)
        
        # Buffett DCF (10% sconto)
        vb = ((fcf * 1.05) / (0.10 - 0.05)) / sh if sh > 0 else 0
        vg = e * (8.5 + 17)
        vd = (fcf * 15) / sh
        vm = (vg + vd + vb) / 3
        tm = vm * 0.75

        # Cassa/Debito (Apple Fix 0.49)
        cd_ann = (gv(b, ['Cash And Cash Equivalents']) + gv(b, ['Other Short Term Investments'])) / gv(b, ['Total Debt']) if gv(b, ['Total Debt']) > 0 else 0

        # --- VISUALIZZAZIONE ---
        st.header(f"📈 {tk_sel} | {info.get('longName', 'N/A')}")
        
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("ROE", f"{info.get('returnOnEquity', 0)*100:.1f}%")
        m2.metric("Profit Margin", f"{info.get('profitMargins', 0)*100:.1f}%")
        m3.metric("Div. Yield", f"{info.get('dividendYield', 0)*100:.2f}%")
        m4.metric("Cash/Debt (Ann)", f"{cd_ann:.2f}")
        m5.metric("Owner Earnings", f"${(ni/1e9):.1f}B")

        # Grafici
        col_g1, col_g2 = st.columns(2)
        with col_g1:
            st.write("**Valutazione Intrinseca (Modello Buffett)**")
            fig_v = go.Figure(go.Bar(
                x=['Market','Graham','DCF','Buffett','MEDIA'],
                y=[p, vg, vd, vb, vm],
                marker_color=['#475569','#3b82f6','#f59e0b','#10b981','#8b5cf6'],
                text=[f"${v:.0f}" for v in [p, vg, vd, vb, vm]], textposition='outside'
            ))
            fig_v.add_hline(y=tm, line_dash="dash", line_color="#FFD700", line_width=4, annotation_text="GOLDEN MoS")
            st.plotly_chart(fig_v, use_container_width=True)

        with col_g2:
            st.write("**Revenue Trimestrale (Momentum)**")
            if not q_f.empty and 'Total Revenue' in q_f.index:
                rev_q = q_f.loc['Total Revenue'].iloc[:12][::-1]
                colors = ['#10b981' if i == 0 or rev_q.values[i] >= rev_q.values[i-1] else '#ef4444' for i in range(len(rev_q))]
                fig_r = go.Figure(go.Bar(x=rev_q.index.astype(str), y=rev_q.values, marker_color=colors))
                fig_r.add_trace(go.Scatter(x=rev_q.index.astype(str), y=rev_q.values, mode='lines', line=dict(color='black')))
                st.plotly_chart(fig_r, use_container_width=True)

        # Executive Insights
        st.info(f"💡 **Insights:** ROE al {info.get('returnOnEquity',0)*100:.1f}% e Payout al {info.get('payoutRatio',0)*100:.1f}%. Solidità Cash/Debt: {cd_ann:.2f}.")

    else:
        st.error(f"⚠️ Limite raggiunto o Ticker non valido. Errore: {data_bundle}")
        st.button("🔄 Riprova tra 10 secondi")







