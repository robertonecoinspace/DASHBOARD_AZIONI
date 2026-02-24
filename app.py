import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import os
import time

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Team Equity Terminal", layout="wide")

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

# --- ANALISI PROFONDA (SALVA-IP) ---
@st.cache_data(ttl=86400) # 24 ore di cache
def fetch_stock_data(ticker):
    try:
        s = yf.Ticker(ticker)
        i = s.info
        if not i or 'currentPrice' not in i: return None
        
        # Scarichiamo i bilanci
        f, c, b = s.financials, s.cashflow, s.balance_sheet
        qb, qf = s.quarterly_balance_sheet, s.quarterly_financials
        
        def gv(df, keys):
            if df is None or df.empty: return 0
            for k in keys:
                if k in df.index:
                    val = df.loc[k]
                    return val.iloc[0] if isinstance(val, (pd.Series, pd.DataFrame)) else val
            return 0

        # Calcoli Buffett & Modelli
        p, e, sh = i.get('currentPrice', 0), i.get('trailingEps', 1), i.get('sharesOutstanding', 1)
        ni = gv(f, ['Net Income'])
        fcf = i.get('freeCashflow', ni * 0.8)
        
        # Buffett DCF 10%
        growth, discount = 0.05, 0.10
        proj_fcf = [fcf * (1 + growth)**n for n in range(1, 11)]
        vb = sum([v / (1 + discount)**n for n, v in enumerate(proj_fcf, 1)]) / sh if sh > 0 else 0
        
        vg, vd = e * (8.5 + 17), (fcf * 15) / sh
        vm = (vg + vd + vb) / 3
        tm = vm * 0.75

        # Cassa/Debito (Apple target 0.49)
        def calc_cd(df):
            cash = gv(df, ['Cash And Cash Equivalents']) + gv(df, ['Other Short Term Investments', 'Short Term Investments'])
            debt = gv(df, ['Total Debt'])
            return cash / debt if debt > 0 else 0

        return {
            'ticker': ticker, 'p': p, 'vm': vm, 'tm': tm,
            'models': {'Graham': vg, 'DCF': vd, 'Buffett': vb},
            'metrics': {
                'ROE': i.get('returnOnEquity', 0) * 100,
                'Margin': i.get('profitMargins', 0) * 100,
                'DivYield': i.get('dividendYield', 0) * 100,
                'Payout': i.get('payoutRatio', 0) * 100,
                'CashDebtAnn': calc_cd(b),
                'CashDebtTri': calc_cd(qb),
                'OwnerEarnings': ni + gv(c, ['Depreciation And Amortization']) - abs(gv(c, ['Capital Expenditure']))
            },
            'info': i, 'q_f': qf
        }
    except: return None

# --- UI ---
st.title("🏛️ Strategic Equity Terminal (Team Edition)")

# 1. MACRO (Sempre attiva ma leggera)
with st.expander("🌐 Visualizza Performance Settori & Ciclo"):
    sectors = {'XLK':'Tech', 'XLF':'Fin', 'XLV':'Health', 'XLE':'Energy', 'XLI':'Ind', 'XLU':'Util', 'XLP':'Staples'}
    m_cols = st.columns(len(sectors))
    for idx, (etf, name) in enumerate(sectors.items()):
        try:
            d = yf.Ticker(etf).history(period="1mo")
            perf = ((d['Close'].iloc[-1] / d['Close'].iloc[0]) - 1) * 100
            m_cols[idx].metric(name, f"{perf:.1f}%")
        except: pass

st.divider()

# 2. FAST SCAN MANUALE (Riduce drasticamente le richieste)
st.subheader("🎯 Fast Scan Opportunità")
if st.button("🚀 Avvia Scansione (Solo i primi 10 titoli)"):
    with st.spinner("Scansione dei Moat e Upside in corso..."):
        scan_data = []
        for t in TICKERS_LIST[:10]:
            try:
                tk = yf.Ticker(t)
                inf = tk.info
                cp, tp = inf.get('currentPrice', 0), inf.get('targetMeanPrice', 0)
                roe, margin = inf.get('returnOnEquity', 0), inf.get('profitMargins', 0)
                moat = "💎 WIDE MOAT" if roe > 0.15 and margin > 0.20 else "Standard"
                if cp > 0 and (tp > cp * 1.15 or moat == "💎 WIDE MOAT"):
                    scan_data.append({"Ticker": t, "Upside": f"{((tp/cp)-1)*100:.1f}%", "Moat": moat, "ROE": f"{roe*100:.1f}%"})
                time.sleep(0.2) # Piccolo respiro tra richieste
            except: continue
        if scan_data: st.table(pd.DataFrame(scan_data))
        else: st.warning("Nessun candidato trovato o limite raggiunto.")

st.divider()

# 3. ANALISI DETTAGLIATA
st.sidebar.subheader("🏢 Selezione Titolo")
tk_sel = st.sidebar.selectbox("Analizza Asset:", TICKERS_LIST)

d = fetch_stock_data(tk_sel)

if d:
    st.header(f"📈 {tk_sel} | {d['info'].get('longName', '')}")
    
    # Status
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

    # Grafici
    col1, col2 = st.columns(2)
    with col1:
        st.write("**Valutazione Buffett (10% Disc)**")
        vals = [d['p'], d['models']['Graham'], d['models']['DCF'], d['models']['Buffett'], d['vm']]
        fig_v = go.Figure(go.Bar(x=['Market','Graham','DCF','Buffett','MEDIA'], y=vals, marker_color=['#475569','#3b82f6','#f59e0b','#10b981','#8b5cf6']))
        fig_v.add_hline(y=d['tm'], line_dash="dash", line_color="#FFD700", line_width=4, annotation_text="GOLDEN MoS")
        st.plotly_chart(fig_v, use_container_width=True)

    with col2:
        st.write("**Revenue Trimestrale (12Q)**")
        if not d['q_f'].empty and 'Total Revenue' in d['q_f'].index:
            rev_q = d['q_f'].loc['Total Revenue'].iloc[:12][::-1]
            colors = ['#10b981' if i == 0 or rev_q.values[i] >= rev_q.values[i-1] else '#ef4444' for i in range(len(rev_q))]
            fig_r = go.Figure(go.Bar(x=rev_q.index.astype(str), y=rev_q.values, marker_color=colors))
            fig_r.add_trace(go.Scatter(x=rev_q.index.astype(str), y=rev_q.values, mode='lines', line=dict(color='black')))
            st.plotly_chart(fig_r, use_container_width=True)

    st.info(f"💡 **Executive Insights:** ROE al {m['ROE']:.1f}% e Rapporto Cassa/Debito Ann: {m['CashDebtAnn']:.2f}.")
    
    with st.expander("📖 Legenda Tecnica"):
        st.write("Modello Buffett: Somma dei flussi di cassa scontati al 10%. Cassa Apple: Valore target 0.49.")









