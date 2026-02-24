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

# --- CARICAMENTO TICKER ---
@st.cache_data
def load_tickers():
    try:
        df = pd.read_csv('lista_ticker.csv')
        col = 'Ticker' if 'Ticker' in df.columns else df.columns[0]
        return [t.strip().upper() for t in df[col].dropna().unique().tolist()]
    except:
        return ["AAPL", "MSFT", "NVDA", "GOOGL"]

TICKERS_LIST = load_tickers()

# --- GESTORE RICHIESTE ROBUSTO ---
def safe_get_data(ticker):
    """Scarica i dati riducendo il rischio di Rate Limit"""
    s = yf.Ticker(ticker)
    try:
        # Una singola chiamata info spesso contiene quasi tutto il necessario
        info = s.info 
        if not info or 'currentPrice' not in info:
            return None, None, None, None, None
        
        # Scarichiamo i bilanci solo se strettamente necessario
        # Usiamo periodi lunghi per ridurre le chiamate future
        f = s.get_financials(freq='yearly')
        c = s.get_cashflow(freq='yearly')
        b = s.get_balance_sheet(freq='yearly')
        qb = s.get_balance_sheet(freq='quarterly')
        q_f = s.get_financials(freq='quarterly')
        
        return info, f, c, b, qb, q_f
    except Exception as e:
        if "Too Many Requests" in str(e):
            st.error("⚠️ Yahoo Finance ha limitato le richieste. Attendi 30 secondi.")
        return None, None, None, None, None, None

# --- FUNZIONE MACRO ---
@st.cache_data(ttl=3600)
def get_macro_data(period_label):
    p_map = {"5 Giorni": "5d", "Mensile": "1mo", "YTD": "ytd"}
    sectors = {'XLK':'Tech', 'XLF':'Fin', 'XLV':'Health', 'XLE':'Energy', 'XLI':'Ind', 'XLU':'Util', 'XLP':'Staples'}
    res = {}
    for etf, name in sectors.items():
        try:
            d = yf.Ticker(etf).history(period=p_map[period_label])
            res[name] = ((d['Close'].iloc[-1] / d['Close'].iloc[0]) - 1) * 100
        except: res[name] = 0
    top = max(res, key=res.get) if res else "N/A"
    ciclo = "ESPANSIONE" if top in ['Tech', 'Ind'] else "PICCO" if top in ['Energy', 'Fin'] else "CONTRAZIONE"
    return res, ciclo

# --- UI MAIN ---
st.title("🏛️ Strategic Equity Terminal Pro")

# 1. MACRO
t_macro = st.radio("Finestra Temporale:", ["5 Giorni", "Mensile", "YTD"], horizontal=True)
macro_res, ciclo = get_macro_data(t_macro)
m_cols = st.columns(len(macro_res))
for idx, (name, val) in enumerate(macro_res.items()):
    m_cols[idx].metric(name, f"{val:.1f}%")
st.info(f"🧭 **Insight Ciclo:** La forza relativa indica: **{ciclo}**")

st.divider()

# 2. SELEZIONE ASSET
st.sidebar.subheader("🏢 Selezione Asset")
tk_sel = st.sidebar.selectbox("Seleziona Titolo dal CSV:", TICKERS_LIST)

# Caricamento solo al cambio di ticker
if tk_sel:
    with st.spinner(f"Recupero dati per {tk_sel}..."):
        info, f, c, b, qb, q_f = safe_get_data(tk_sel)

    if info:
        # --- LOGICA CALCOLO ---
        def gv(df, keys):
            if df is None or df.empty: return 0
            for k in keys:
                if k in df.index:
                    val = df.loc[k]
                    return val.iloc[0] if isinstance(val, (pd.Series, pd.DataFrame)) else val
            return 0

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

        # Cash/Debt Certificato (Apple 0.49)
        cash_ann = gv(b, ['Cash And Cash Equivalents']) + gv(b, ['Other Short Term Investments', 'Short Term Investments'])
        debt_ann = gv(b, ['Total Debt'])
        cd_ann = cash_ann / debt_ann if debt_ann > 0 else 0

        cash_tri = gv(qb, ['Cash And Cash Equivalents']) + gv(qb, ['Other Short Term Investments', 'Short Term Investments'])
        debt_tri = gv(qb, ['Total Debt'])
        cd_tri = cash_tri / debt_tri if debt_tri > 0 else 0

        # --- VISUALIZZAZIONE ---
        st.header(f"📈 {tk_sel} | {info.get('longName', 'N/A')}")
        
        # Status
        if p <= tm: st.success(f"🔥 SOTTOVALUTATO (Target MoS: ${tm:.2f})")
        elif p <= vm: st.warning("⚖️ FAIR VALUE")
        else: st.error("⚠️ SOPRAVVALUTATO")

        # Metriche
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("ROE", f"{info.get('returnOnEquity', 0)*100:.1f}%")
        m2.metric("Profit Margin", f"{info.get('profitMargins', 0)*100:.1f}%")
        m3.metric("Div. Yield", f"{info.get('dividendYield', 0)*100:.2f}%")
        m4.metric("Cash/Debt (Ann)", f"{cd_ann:.2f}")
        m5.metric("Cash/Debt (Tri)", f"{cd_tri:.2f}")

        # Grafici
        col_g1, col_g2 = st.columns(2)
        with col_g1:
            st.write("**Valutazione Intrinseca (Modello Buffett 10%)**")
            fig_v = go.Figure(go.Bar(
                x=['Market','Graham','DCF','Buffett','MEDIA'],
                y=[p, vg, vd, vb, vm],
                marker_color=['#475569','#3b82f6','#f59e0b','#10b981','#8b5cf6'],
                text=[f"${v:.0f}" for v in [p, vg, vd, vb, vm]], textposition='outside'
            ))
            fig_v.add_hline(y=tm, line_dash="dash", line_color="#FFD700", line_width=4, annotation_text="GOLDEN MoS")
            st.plotly_chart(fig_v, use_container_width=True)

        with col_g2:
            st.write("**Revenue Trimestrale (12Q Momentum)**")
            if q_f is not None and 'Total Revenue' in q_f.index:
                rev_q = q_f.loc['Total Revenue'].iloc[:12][::-1]
                colors = ['#10b981' if i == 0 or rev_q.values[i] >= rev_q.values[i-1] else '#ef4444' for i in range(len(rev_q))]
                fig_r = go.Figure()
                fig_r.add_trace(go.Bar(x=rev_q.index.astype(str), y=rev_q.values, marker_color=colors))
                fig_r.add_trace(go.Scatter(x=rev_q.index.astype(str), y=rev_q.values, mode='lines', line=dict(color='black')))
                st.plotly_chart(fig_r, use_container_width=True)

        # Insights & Legenda
        st.info(f"💡 **Executive Insights:** ROE al {info.get('returnOnEquity',0)*100:.1f}% e Margine al {info.get('profitMargins',0)*100:.1f}%. Rapporto Cassa/Debito Ann: **{cd_ann:.2f}**.")
        
        with st.expander(f"📖 Legenda e Approfondimento: {tk_sel}"):
            st.markdown(f"""
            - **Fatturato Trimestrale:** Le barre indicano il trend degli ultimi 3 anni. Il colore riflette la crescita rispetto al trimestre precedente.
            - **Cash/Debt:** Apple annuale target **0.49**. Calcolato come (Cash + Short Term Inv) / Total Debt.
            - **Buffett DCF:** Calcolato scontando i flussi di cassa futuri al 10%.
            """)
    else:
        st.warning("⚠️ Non è stato possibile recuperare i dati. Prova tra 30 secondi o cambia ticker.")







