import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from fpdf import FPDF
import os

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Strategic Equity Terminal Pro", layout="wide")

tema = st.sidebar.radio("Tema Dashboard:", ["Dark", "Light"])
if tema == "Dark":
    st.markdown("<style>.main { background-color: #0e1117; color: white; } .stMetric { background-color: #161b22; border: 1px solid #30363d; border-radius: 10px; }</style>", unsafe_allow_html=True)

# --- CARICAMENTO LISTA TICKER ---
@st.cache_data
def load_tickers():
    file_path = 'lista_ticker.csv'
    if os.path.exists(file_path):
        try:
            df = pd.read_csv(file_path)
            col = 'Ticker' if 'Ticker' in df.columns else df.columns[0]
            return [t.strip().upper() for t in df[col].dropna().unique().tolist()]
        except: return ["AAPL", "MSFT", "NVDA"]
    return ["AAPL", "MSFT", "NVDA"]

TICKERS_LIST = load_tickers()

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

# --- ANALISI PROFONDA (ROBUSTA) ---
@st.cache_data(ttl=3600)
def fetch_stock_data(ticker):
    try:
        s = yf.Ticker(ticker)
        i = s.info
        if not i or 'currentPrice' not in i: return None

        # Caricamento sicuro dei Dataframe
        def get_df(func):
            try: return func()
            except: return pd.DataFrame()

        f = get_df(lambda: s.financials)
        c = get_df(lambda: s.cashflow)
        b = get_df(lambda: s.balance_sheet)
        qb = get_df(lambda: s.quarterly_balance_sheet)
        q_f = get_df(lambda: s.quarterly_financials)

        def gv(df, keys):
            if df is None or df.empty: return 0
            for k in keys:
                if k in df.index:
                    val = df.loc[k]
                    return val.iloc[0] if isinstance(val, (pd.Series, pd.DataFrame)) else val
            return 0

        # Metriche Base
        p = i.get('currentPrice', 0)
        e = i.get('trailingEps', 1)
        sh = i.get('sharesOutstanding', 1)
        ni = gv(f, ['Net Income'])
        fcf = i.get('freeCashflow', 0) if i.get('freeCashflow') else (ni * 0.8) # Fallback

        # Buffett DCF (Sconto 10%)
        growth, discount = 0.05, 0.10
        vb = ((fcf * (1 + growth)) / (discount - growth)) / sh if sh > 0 else 0
        
        vg = e * (8.5 + 17)
        vd = (fcf * 15) / sh
        vm = (vg + vd + vb) / 3
        tm = vm * 0.75

        # CASSA/DEBITO (Apple Fix 0.49)
        def calc_cd(df):
            cash = gv(df, ['Cash And Cash Equivalents']) + gv(df, ['Other Short Term Investments', 'Short Term Investments'])
            debt = gv(df, ['Total Debt'])
            return cash / debt if debt > 0 else 0

        return {
            'ticker': ticker, 'p': p, 'vm': vm, 'tm': tm,
            'models': {'Graham': vg, 'DCF Std': vd, 'Buffett': vb},
            'metrics': {
                'ROE': i.get('returnOnEquity', 0) * 100,
                'Margin': i.get('profitMargins', 0) * 100,
                'DivYield': i.get('dividendYield', 0) * 100,
                'Payout': i.get('payoutRatio', 0) * 100,
                'CashDebtAnn': calc_cd(b),
                'CashDebtTri': calc_cd(qb),
                'OwnerEarnings': ni + gv(c, ['Depreciation And Amortization']) - abs(gv(c, ['Capital Expenditure']))
            },
            'info': i, 'q_f': q_f, 'sector': i.get('sector', 'N/A')
        }
    except Exception as err:
        st.error(f"Errore tecnico nel caricamento di {ticker}: {err}")
        return None

# --- UI MAIN ---
st.title("🏛️ Strategic Equity Terminal Pro")

# 1. MACRO
st.subheader("🌐 Analisi Macro & Ciclo Economico")
t_macro = st.radio("Finestra Temporale:", ["5 Giorni", "Mensile", "YTD"], horizontal=True)
macro_res, ciclo = get_macro_data(t_macro)
m_cols = st.columns(len(macro_res))
for idx, (name, val) in enumerate(macro_res.items()):
    m_cols[idx].metric(name, f"{val:.1f}%")
st.info(f"🧭 **Insight Ciclo:** La forza relativa indica: **{ciclo}**")

st.divider()

# 2. FAST SCAN
st.subheader("🎯 Fast Scan: Candidati Sottovalutati")
@st.cache_data(ttl=3600)
def fast_scan(tickers):
    res = []
    for t in tickers[:12]:
        try:
            inf = yf.Ticker(t).info
            cp, tp = inf.get('currentPrice', 0), inf.get('targetMeanPrice', 0)
            if cp > 0 and tp > cp * 1.15:
                res.append({"Ticker": t, "Upside": f"{((tp/cp)-1)*100:.1f}%", "ROE": f"{inf.get('returnOnEquity',0)*100:.1f}%"})
        except: continue
    return res
st.table(pd.DataFrame(fast_scan(TICKERS_LIST)))

st.divider()

# 3. ANALISI DETTAGLIATA (IL CUORE)
st.sidebar.subheader("🏢 Selezione Asset")
tk_sel = st.sidebar.selectbox("Analizza Ticker:", TICKERS_LIST)

# Carichiamo i dati
d = fetch_stock_data(tk_sel)

if d:
    # Questa parte ora è protetta e verrà mostrata correttamente
    st.header(f"📈 {tk_sel} | {d['info'].get('longName', 'N/A')}")
    
    # STATUS BAR
    if d['p'] <= d['tm']: st.success(f"🔥 SOTTOVALUTATO (Target MoS: ${d['tm']:.2f})")
    elif d['p'] <= d['vm']: st.warning("⚖️ FAIR VALUE")
    else: st.error("⚠️ SOPRAVVALUTATO")

    # METRICHE
    m = d['metrics']
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("ROE", f"{m['ROE']:.1f}%")
    c2.metric("Profit Margin", f"{m['Margin']:.1f}%")
    c3.metric("Div. Yield", f"{m['DivYield']:.2f}%")
    c4.metric("Cash/Debt (Ann)", f"{m['CashDebtAnn']:.2f}")
    c5.metric("Cash/Debt (Tri)", f"{m['CashDebtTri']:.2f}")

    # GRAFICI
    g1, g2 = st.columns(2)
    with g1:
        st.write("**Valutazione (Modello Buffett 10% Disc)**")
        names = ['Market','Graham','DCF','Buffett','MEDIA']
        vals = [d['p'], d['models']['Graham'], d['models']['DCF Std'], d['models']['Buffett'], d['vm']]
        fig_v = go.Figure(go.Bar(x=names, y=vals, marker_color=['#475569','#3b82f6','#f59e0b','#10b981','#8b5cf6'], text=[f"${v:.0f}" for v in vals], textposition='outside'))
        fig_v.add_hline(y=d['tm'], line_dash="dash", line_color="#FFD700", line_width=4, annotation_text="GOLDEN MoS")
        st.plotly_chart(fig_v, use_container_width=True)

    with g2:
        st.write("**Revenue Trimestrale (Momentum)**")
        if not d['q_f'].empty and 'Total Revenue' in d['q_f'].index:
            rev_q = d['q_f'].loc['Total Revenue'].iloc[:12][::-1]
            colors = ['#10b981' if i == 0 or rev_q.values[i] >= rev_q.values[i-1] else '#ef4444' for i in range(len(rev_q))]
            fig_r = go.Figure()
            fig_r.add_trace(go.Bar(x=rev_q.index.astype(str), y=rev_q.values, marker_color=colors))
            fig_r.add_trace(go.Scatter(x=rev_q.index.astype(str), y=rev_q.values, mode='lines', line=dict(color='black')))
            st.plotly_chart(fig_r, use_container_width=True)
        else:
            st.warning("Dati trimestrali non disponibili per questo ticker.")

    # INSIGHTS
    st.info(f"💡 **Executive Insights:** ROE al {m['ROE']:.1f}% e Margine al {m['Margin']:.1f}%. Rapporto Cassa/Debito Ann: **{m['CashDebtAnn']:.2f}**.")

    # LEGENDA DINAMICA
    with st.expander(f"📖 Legenda e Approfondimento: {tk_sel}"):
        st.write(f"Dati basati sull'ultimo bilancio di {tk_sel}. La linea dorata rappresenta lo sconto del 25% rispetto al valore intrinseco medio.")
else:
    st.error("Seleziona un altro ticker o controlla la connessione.





