import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from fpdf import FPDF
import os
import time

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Strategic Equity Terminal Pro", layout="wide")

# Tema Dinamico
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
        except: return ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN"]
    return ["AAPL", "MSFT", "NVDA"]

TICKERS_LIST = load_tickers()

# --- LOGICA MACRO & CICLO ---
@st.cache_data(ttl=3600)
def get_macro_data(period="1mo"):
    sectors = {'XLK':'Tech', 'XLF':'Financials', 'XLV':'Healthcare', 'XLE':'Energy', 'XLI':'Industrials', 'XLU':'Utilities', 'XLP':'Staples'}
    res = {}
    p_map = {"5 Giorni": "5d", "Mensile": "1mo", "YTD": "ytd"}
    for etf, name in sectors.items():
        try:
            d = yf.Ticker(etf).history(period=p_map[period])
            if not d.empty:
                perf = ((d['Close'].iloc[-1] / d['Close'].iloc[0]) - 1) * 100
                res[name] = perf
        except: res[name] = 0
    
    def estimate_cycle(data):
        if not data: return "N/D"
        top = max(data, key=data.get)
        if top in ['Tech', 'Industrials']: return "ESPANSIONE (Early/Mid Cycle)"
        if top in ['Energy', 'Financials']: return "PICCO (Late Cycle)"
        if top in ['Healthcare', 'Staples', 'Utilities']: return "CONTRAZIONE (Recessionary)"
        return "FASE DI TRANSIZIONE"
    
    return res, estimate_cycle(res)

# --- ANALISI PROFONDA (OTTIMIZZATA) ---
@st.cache_data(ttl=86400) # Cache 24 ore per proteggere l'IP
def fetch_stock_data(ticker):
    try:
        s = yf.Ticker(ticker)
        # Chiamate raggruppate
        i = s.info
        if not i or 'currentPrice' not in i: return None
        
        f = s.financials
        c = s.cashflow
        b = s.balance_sheet
        qb = s.quarterly_balance_sheet
        q_f = s.quarterly_financials
        
        def gv(df, keys):
            if df is None or df.empty: return 0
            for k in keys:
                if k in df.index:
                    val = df.loc[k]
                    return val.iloc[0] if isinstance(val, (pd.Series, pd.DataFrame)) else val
            return 0

        p, e, sh = i.get('currentPrice', 0), i.get('trailingEps', 1), i.get('sharesOutstanding', 1)
        ni = gv(f, ['Net Income'])
        fcf = i.get('freeCashflow', ni * 0.8)
        
        # Buffett DCF (Sconto 10%)
        growth, discount_rate = 0.05, 0.10
        projected_fcf = [fcf * (1 + growth)**n for n in range(1, 11)]
        dcf_val = sum([val / (1 + discount_rate)**n for n, val in enumerate(projected_fcf, 1)])
        vb = dcf_val / sh if sh > 0 else 0
        
        vg = e * (8.5 + 17)
        vd = (fcf * 15) / sh
        vm = (vg + vd + vb) / 3
        tm = vm * 0.75

        def calc_cd(df):
            cash = gv(df, ['Cash And Cash Equivalents']) + gv(df, ['Other Short Term Investments', 'Short Term Investments'])
            debt = gv(df, ['Total Debt'])
            return cash / debt if debt > 0 else 0

        return {
            'ticker': ticker, 'p': p, 'vm': vm, 'tm': tm, 'vb': vb,
            'models': {'Graham': vg, 'DCF Standard': vd, 'Buffett DCF (10%)': vb},
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
    except Exception as ex:
        if "429" in str(ex): st.error("⚠️ Yahoo Finance: Troppe richieste. Riprova più tardi.")
        return None

# --- FAST SCAN LOGIC ---
@st.cache_data(ttl=3600)
def fast_scan_logic(tickers):
    results = []
    for t in tickers[:12]: # Limite ridotto per evitare blocchi IP
        try:
            inf = yf.Ticker(t).info
            cp, tp = inf.get('currentPrice', 0), inf.get('targetMeanPrice', 0)
            roe, margin = inf.get('returnOnEquity', 0), inf.get('profitMargins', 0)
            moat = "💎 WIDE MOAT" if roe > 0.15 and margin > 0.20 else "Standard"
            if cp > 0 and (tp > cp * 1.15 or moat == "💎 WIDE MOAT"):
                results.append({"Ticker": t, "Upside": f"{((tp/cp)-1)*100:.1f}%", "Moat/Leader": moat, "ROE": f"{roe*100:.1f}%"})
        except: continue
    return results

# --- UI MAIN ---
st.title("🏛️ Strategic Equity Terminal Pro")

# 1. SEZIONE MACRO
st.subheader("🌐 Analisi Macro & Ciclo Economico")
t_macro = st.radio("Finestra Temporale:", ["5 Giorni", "Mensile", "YTD"], horizontal=True)
macro_res, ciclo = get_macro_data(t_macro)

m_cols = st.columns(len(macro_res))
for idx, (name, val) in enumerate(macro_res.items()):
    m_cols[idx].metric(name, f"{val:.1f}%")

st.info(f"🧭 **Insight Ciclo:** La forza relativa attuale indica una fase di: **{ciclo}**")


st.divider()

# 2. FAST SCAN
st.subheader("🎯 Fast Scan: Leader & Candidati Sottovalutati")
fast_results = fast_scan_logic(TICKERS_LIST)
if fast_results:
    st.table(pd.DataFrame(fast_results))
else:
    st.info("Nessuna opportunità rilevata o limite API raggiunto.")

st.divider()

# 3. ANALISI DETTAGLIATA
st.sidebar.subheader("🏢 Selezione Asset")
tk_sel = st.sidebar.selectbox("Analizza Ticker:", TICKERS_LIST)

with st.spinner(f"Sincronizzazione dati per {tk_sel}..."):
    d = fetch_stock_data(tk_sel)

if d:
    st.header(f"📈 {tk_sel} | {d['info'].get('longName', '')}")
    
    if d['p'] <= d['tm']: st.success(f"🔥 SOTTOVALUTATO (Target MoS: ${d['tm']:.2f})")
    elif d['p'] <= d['vm']: st.warning("⚖️ FAIR VALUE")
    else: st.error("⚠️ SOPRAVVALUTATO")

    m = d['metrics']
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("ROE", f"{m['ROE']:.1f}%")
    c2.metric("Profit Margin", f"{m['Margin']:.1f}%")
    c3.metric("Div. Yield", f"{m['DivYield']:.2f}%")
    c4.metric("Cash/Debt (Ann)", f"{m['CashDebtAnn']:.2f}")
    c5.metric("Cash/Debt (Tri)", f"{m['CashDebtTri']:.2f}")

    g1, g2 = st.columns(2)
    with g1:
        st.write("**Valutazione (Modello Buffett 10% Disc)**")
        names = ['Market','Graham','DCF Std','Buffett','MEDIA']
        vals = [d['p'], d['models']['Graham'], d['models']['DCF Standard'], d['models']['Buffett DCF (10%)'], d['vm']]
        fig_v = go.Figure(go.Bar(x=names, y=vals, marker_color=['#475569','#3b82f6','#f59e0b','#10b981','#8b5cf6'], text=[f"${v:.0f}" for v in vals], textposition='outside'))
        fig_v.add_hline(y=d['tm'], line_dash="dash", line_color="#FFD700", line_width=4, annotation_text="GOLDEN MoS")
        st.plotly_chart(fig_v, use_container_width=True)

    with g2:
        st.write("**Revenue Trimestrale (Ultimi 3 Anni)**")
        if not d['q_f'].empty and 'Total Revenue' in d['q_f'].index:
            rev_q = d['q_f'].loc['Total Revenue'].iloc[:12][::-1]
            colors = ['#10b981' if i == 0 or rev_q.values[i] >= rev_q.values[i-1] else '#ef4444' for i in range(len(rev_q))]
            fig_r = go.Figure()
            fig_r.add_trace(go.Bar(x=rev_q.index.astype(str), y=rev_q.values, marker_color=colors))
            fig_r.add_trace(go.Scatter(x=rev_q.index.astype(str), y=rev_q.values, mode='lines', line=dict(color='black')))
            st.plotly_chart(fig_r, use_container_width=True)

    st.info(f"""
    💡 **Executive Insights per {tk_sel}:**
    * **Qualità:** ROE al **{m['ROE']:.1f}%** e Margine al **{m['Margin']:.1f}%**.
    * **Efficienza:** Owner Earnings stimati in **${m['OwnerEarnings']/1e9:.1f}B**. 
    * **Solvibilità:** Rapporto Cash/Debt annuale di **{m['CashDebtAnn']:.2f}** (Target Apple 0.49).
    """)

    with st.expander(f"📖 LEGENDA E APPROFONDIMENTO: {tk_sel}"):
        st.markdown(f"""
        - **ROE ({m['ROE']:.1f}%):** Redditività del capitale proprio. Ottimo sopra il 15%.
        - **Buffett DCF (10%):** Flussi di cassa scontati al rendimento minimo richiesto del 10%.
        - **Cash/Debt:** Cassa e investimenti brevi diviso debito totale. Valore Apple: **0.49**.
        """)








