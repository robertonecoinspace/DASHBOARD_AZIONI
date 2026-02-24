import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import os

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Strategic Equity Terminal", layout="wide")

# Tema
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
def get_macro_data(period_label):
    p_map = {"5 Giorni": "5d", "Mensile": "1mo", "YTD": "ytd"}
    sectors = {'XLK':'Tech', 'XLF':'Financials', 'XLV':'Healthcare', 'XLE':'Energy', 'XLI':'Industrials', 'XLU':'Utilities', 'XLP':'Staples'}
    res = {}
    for etf, name in sectors.items():
        try:
            d = yf.Ticker(etf).history(period=p_map[period_label])
            res[name] = ((d['Close'].iloc[-1] / d['Close'].iloc[0]) - 1) * 100
        except: res[name] = 0
    
    top = max(res, key=res.get) if res else "N/A"
    if top in ['Tech', 'Industrials']: ciclo = "ESPANSIONE (Early/Mid Cycle)"
    elif top in ['Energy', 'Financials']: ciclo = "PICCO (Late Cycle)"
    else: ciclo = "CONTRAZIONE (Recessionary)"
    return res, ciclo

# --- ANALISI PROFONDA ---
@st.cache_data(ttl=86400)
def fetch_stock_data(ticker):
    try:
        s = yf.Ticker(ticker)
        i, f, c, b = s.info, s.financials, s.cashflow, s.balance_sheet
        qb, qf = s.quarterly_balance_sheet, s.quarterly_financials
        
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
        growth, discount = 0.05, 0.10
        proj_fcf = [fcf * (1 + growth)**n for n in range(1, 11)]
        vb = sum([v / (1 + discount)**n for n, v in enumerate(proj_fcf, 1)]) / sh if sh > 0 else 0
        
        vg, vd = e * (8.5 + 17), (fcf * 15) / sh
        vm = (vg + vd + vb) / 3
        tm = vm * 0.75

        def calc_cd(df):
            cash = gv(df, ['Cash And Cash Equivalents']) + gv(df, ['Other Short Term Investments', 'Short Term Investments'])
            debt = gv(df, ['Total Debt'])
            return cash / debt if debt > 0 else 0

        return {
            'ticker': ticker, 'p': p, 'vm': vm, 'tm': tm, 'vb': vb,
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

# --- UI MAIN ---
st.title("🏛️ Strategic Equity Terminal Pro")

# 1. MACRO
st.subheader("🌐 Analisi Macro & Ciclo Economico")
t_macro = st.radio("Seleziona Finestra Temporale:", ["5 Giorni", "Mensile", "YTD"], horizontal=True)
m_data, ciclo = get_macro_data(t_macro)
m_cols = st.columns(len(m_data))
for idx, (name, val) in enumerate(m_data.items()):
    m_cols[idx].metric(name, f"{val:.1f}%")
st.info(f"🧭 **Fase Ciclo Stimata:** {ciclo}")



st.divider()

# 2. ANALISI ASSET
st.sidebar.subheader("🏢 Selezione Asset")
tk_sel = st.sidebar.selectbox("Ticker da analizzare:", TICKERS_LIST)

d = fetch_stock_data(tk_sel)

if d:
    st.header(f"📈 {tk_sel} | {d['info'].get('longName', '')}")
    
    # Status bar
    if d['p'] <= d['tm']: st.success(f"🔥 SOTTOVALUTATO (Target MoS: ${d['tm']:.2f})")
    elif d['p'] <= d['vm']: st.warning("⚖️ FAIR VALUE")
    else: st.error("⚠️ SOPRAVVALUTATO")

    # Metriche
    m = d['metrics']
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("ROE", f"{m['ROE']:.1f}%")
    c2.metric("Profit Margin", f"{m['Margin']:.1f}%")
    c3.metric("Div. Yield", f"{m['DivYield']:.2f}%")
    c4.metric("Cash/Debt (Ann)", f"{m['CashDebtAnn']:.2f}")
    c5.metric("Cash/Debt (Tri)", f"{m['CashDebtTri']:.2f}")

    # Grafici
    g1, g2 = st.columns(2)
    with g1:
        st.write("**Valutazione Buffett (10% Disc)**")
        v_list = [d['p'], d['models']['Graham'], d['models']['DCF'], d['models']['Buffett'], d['vm']]
        fig_v = go.Figure(go.Bar(x=['Market','Graham','DCF','Buffett','MEDIA'], y=v_list, marker_color=['#475569','#3b82f6','#f59e0b','#10b981','#8b5cf6'], text=[f"${v:.0f}" for v in v_list], textposition='outside'))
        fig_v.add_hline(y=d['tm'], line_dash="dash", line_color="#FFD700", line_width=4, annotation_text="GOLDEN MoS")
        st.plotly_chart(fig_v, use_container_width=True)

    with g2:
        st.write("**Revenue Trimestrale (Momentum)**")
        if not d['q_f'].empty and 'Total Revenue' in d['q_f'].index:
            rev_q = d['q_f'].loc['Total Revenue'].iloc[:12][::-1]
            colors = ['#10b981' if i == 0 or rev_q.values[i] >= rev_q.values[i-1] else '#ef4444' for i in range(len(rev_q))]
            fig_r = go.Figure(go.Bar(x=rev_q.index.astype(str), y=rev_q.values, marker_color=colors))
            fig_r.add_trace(go.Scatter(x=rev_q.index.astype(str), y=rev_q.values, mode='lines', line=dict(color='black')))
            st.plotly_chart(fig_r, use_container_width=True)

    # EXECUTIVE INSIGHTS
    st.subheader("💡 Executive Insights & Quality Assessment")
    
    # Valutazione Qualità
    q_score = 0
    if m['ROE'] > 15: q_score += 1
    if m['Margin'] > 15: q_score += 1
    if m['CashDebtAnn'] > 0.40: q_score += 1
    
    qualita = "ECCELLENTE" if q_score == 3 else "BUONA" if q_score == 2 else "SPECULATIVA/DEBOLE"
    
    st.info(f"""
    * **Solidità Finanziaria:** Con un rapporto Cash/Debt di **{m['CashDebtAnn']:.2f}**, l'azienda mostra una {'capacità di copertura del debito robusta' if m['CashDebtAnn'] > 0.48 else 'struttura finanziaria che richiede monitoraggio'}.
    * **Qualità del Business:** Il ROE del **{m['ROE']:.1f}%** combinato con un margine netto del **{m['Margin']:.1f}%** indica un vantaggio competitivo {'estremamente forte (Moat)' if q_score >= 2 else 'nella media o in erosione'}.
    * **Generazione di Cassa:** Gli Owner Earnings (Utile Reale) sono stimati a **${(m['OwnerEarnings']/1e9):.2f}B**, a conferma della capacità di sostenere dividendi e investimenti.
    * **Giudizio Sintetico:** Asset di qualità **{qualita}**.
    """)

    # LEGENDA APPROFONDITA
    with st.expander(f"📖 LEGENDA TECNICA APPROFONDITA PER {tk_sel}"):
        st.markdown(f"""
        ### 1. Metriche di Redditività e Qualità
        - **ROE (Return on Equity):** Misura quanto profitto genera l'azienda per ogni euro di capitale proprio. Valori > 15% indicano un business efficiente e spesso un "Moat" (vantaggio competitivo).
        - **Profit Margin:** La percentuale di fatturato che rimane come utile netto. Sopra il 20% è tipico dei leader di settore.
        - **Owner Earnings:** Concetto caro a Buffett. È il flusso di cassa reale che rimane all'azionista dopo che l'azienda ha investito per mantenere la sua posizione competitiva.

        ### 2. Metriche di Debito e Solvibilità
        - **Cash/Debt (Target Apple 0.49):** Questo terminale calcola la liquidità totale (Cash + Investimenti Breve Termine) diviso il Debito Totale. Un valore di 1.00 significa che l'azienda potrebbe estinguere tutto il debito domani. Per Apple, il target storico è circa 0.49.
        - **Payout Ratio:** La percentuale di utili pagata come dividendo. Sotto il 60% è considerato molto sicuro.

        ### 3. Modelli di Valutazione (Grafico)
        - **Buffett DCF (10% Disc):** Calcola il valore attuale di tutti i flussi di cassa che l'azienda produrrà nei prossimi 10 anni, scontati al 10% (il rendimento minimo preteso da un investitore prudente).
        - **Modello Graham:** Valutazione basata sugli utili correnti e sulle prospettive di crescita teoriche (Utile x (8.5 + 2g)).
        - **Golden MoS (Margin of Safety):** La linea tratteggiata dorata rappresenta lo sconto del 25% sulla media dei modelli. Entrare sotto questa linea massimizza la protezione del capitale.
        """)









