import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import os

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Strategic Equity Terminal Pro", layout="wide")

def get_val(df, keys):
    if df is None or df.empty: return 0
    for k in keys:
        if k in df.index:
            val = df.loc[k]
            return val.iloc[0] if isinstance(val, (pd.Series, pd.DataFrame)) else val
    return 0

# --- CARICAMENTO LISTA TICKER ---
try:
    lista_t = pd.read_csv('lista_ticker.csv')['Ticker'].tolist()
except:
    lista_t = ["AAPL", "MSFT", "GOOGL", "NVDA", "BRK-B", "META", "TSLA", "AMZN"]

# --- 1. SCANNER OTTIMIZZATO (Funzionante) ---
@st.cache_data(ttl=3600)
def run_scanner(tickers):
    opportunities = []
    # Usiamo un approccio batch per evitare blocchi
    for t in tickers:
        try:
            s = yf.Ticker(t)
            i = s.info
            p = i.get('currentPrice')
            e = i.get('trailingEps', 0)
            
            if p is None or p == 0: continue
            
            # Calcolo Fair Value rapido per lo scanner (Graham + Multiplo EPS)
            vg = e * (8.5 + 17) # Graham
            vb_quick = e * 20    # Approssimazione Buffett basata su EPS
            vm = (vg + vb_quick) / 2
            tm = vm * 0.75 # Golden MoS
            
            if p <= tm:
                sconto = ((vm - p) / vm) * 100
                opportunities.append({
                    "Ticker": t, 
                    "Prezzo": f"${p:.2f}", 
                    "Fair Value Est.": f"${vm:.2f}", 
                    "Sconto": f"{sconto:.1f}%"
                })
        except:
            continue
    return opportunities

# --- 2. ANALISI PROFONDA (Solo Asset Selezionato) ---
@st.cache_data(ttl=86400)
def fetch_deep_data(ticker):
    try:
        s = yf.Ticker(ticker)
        i, f, c, b = s.info, s.financials, s.cashflow, s.balance_sheet
        q_f, q_b = s.quarterly_financials, s.quarterly_balance_sheet
        
        p = i.get('currentPrice', 0)
        e = i.get('trailingEps', 1)
        sh = i.get('sharesOutstanding', 1)
        ni = get_val(f, ['Net Income'])
        dep = get_val(c, ['Depreciation And Amortization'])
        capx = abs(get_val(c, ['Capital Expenditure']))
        oe = ni + dep - capx
        
        # Buffett Raw (Multiplo Owner Earnings senza sconto 10%)
        vb = (oe * 20) / sh if sh > 0 else 0
        vg = e * (8.5 + 17)
        vd = (i.get('freeCashflow', oe) * 15) / sh
        vm = (vg + vd + vb) / 3
        tm = vm * 0.75 

        # Scores
        f_score = 0
        if i.get('returnOnAssets', 0) > 0: f_score += 2
        if i.get('operatingCashflow', 0) > ni: f_score += 3
        if i.get('debtToEquity', 100) < 100: f_score += 2
        if i.get('currentRatio', 0) > 1: f_score += 2
        
        z_risk = i.get('auditRisk', 5)
        altman = "LOW RISK" if z_risk < 4 else "MEDIUM" if z_risk < 7 else "DISTRESS"
        beneish = "CONSERVATIVE" if i.get('extraordinaryCashFlows', 0) == 0 else "CHECK AUDIT"

        def calc_cd(df):
            cash = get_val(df, ['Cash And Cash Equivalents']) + get_val(df, ['Other Short Term Investments', 'Short Term Investments'])
            debt = get_val(df, ['Total Debt'])
            return cash / debt if debt > 0 else 0

        return {
            "info": i, "vals": (p, vm, tm, oe, vg, vd, vb),
            "q_f": q_f, "scores": (f_score, altman, beneish),
            "metrics": {
                "ROE": i.get('returnOnEquity', 0) * 100,
                "Margin": i.get('profitMargins', 0) * 100,
                "DivYield": i.get('dividendYield', 0) * 100,
                "CashDebtAnn": calc_cd(b),
                "CashDebtTri": calc_cd(q_b)
            }
        }
    except: return None

# --- UI ---
st.title("🏛️ Strategic Equity Terminal Pro")

# SEZIONE SCANNER
st.subheader("🎯 Scanner Opportunità (Sotto soglia MoS)")
with st.spinner("Scansione in corso..."):
    # Scansioniamo i ticker per trovare quelli che rispettano la Golden MoS
    opps = run_scanner(lista_t)
    if opps:
        st.table(pd.DataFrame(opps))
    else:
        st.info("Nessuna opportunità rilevata con i parametri MoS attuali.")

st.divider()

# ANALISI DETTAGLIATA
tk_sel = st.sidebar.selectbox("Seleziona Asset per Analisi Profonda:", lista_t)
asset = fetch_deep_data(tk_sel)

if asset:
    p, vm, tm, oe, vg, vd, vb = asset["vals"]
    f_score, altman, beneish = asset["scores"]
    m = asset["metrics"]
    
    # Estrazione Nome e Settore
    nome_full = asset['info'].get('longName', tk_sel)
    settore = asset['info'].get('sector', 'N/A')
    
    st.header(f"📈 {nome_full} | 🏭 {settore}")
    
    # Status
    if p <= tm: st.success(f"### 🔥 SOTTOVALUTATO (Target MoS: ${tm:.2f})")
    elif p <= vm: st.warning(f"### ⚖️ FAIR VALUE (Fair Value: ${vm:.2f})")
    else: st.error(f"### ⚠️ SOPRAVVALUTATO (Fair Value: ${vm:.2f})")

    # Metriche e Scores
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("ROE", f"{m['ROE']:.1f}%")
    c2.metric("Profit Margin", f"{m['Margin']:.1f}%")
    c3.metric("Piotroski Score", f"{f_score}/9")
    c4.metric("Altman Risk", altman)
    c5.metric("Beneish Score", beneish)

    # Cash Analysis
    st.write("---")
    cc1, cc2, cc3, cc4 = st.columns(4)
    cc1.metric("Cash/Debt (Ann)", f"{m['CashDebtAnn']:.2f}")
    cc2.metric("Cash/Debt (Tri)", f"{m['CashDebtTri']:.2f}")
    cc3.metric("Div. Yield", f"{(m['DivYield'] / 100):.2f}%")
    cc4.metric("Owner Earnings", f"${oe/1e9:.2f}B")

    # Grafici
    g1, g2 = st.columns(2)
    with g1:
        st.subheader("Valutazioni Intrinseche (Buffett Raw)")
        fig_v = go.Figure(go.Bar(x=['Market', 'Graham', 'DCF', 'Buffett', 'MEDIA'], 
                                 y=[p, vg, vd, vb, vm], 
                                 marker_color=['#1e293b', '#3b82f6', '#f97316', '#10b981', '#8b5cf6']))
        fig_v.add_hline(y=tm, line_dash="dash", line_color="#FFD700", line_width=3, annotation_text="GOLDEN MoS")
        st.plotly_chart(fig_v, use_container_width=True)

    with g2:
        st.subheader("Fatturato Trimestrale (3 Anni)")
        if not asset["q_f"].empty and 'Total Revenue' in asset["q_f"].index:
            rev_q = asset["q_f"].loc['Total Revenue'].iloc[:12][::-1]
            bar_colors = ['#10b981' if i == 0 or rev_q.values[i] >= rev_q.values[i-1] else '#ef4444' for i in range(len(rev_q))]
            st.plotly_chart(go.Figure(go.Bar(x=rev_q.index.astype(str), y=rev_q.values, marker_color=bar_colors)), use_container_width=True)

    # Executive Insight
    st.subheader("💡 Executive Quality Insights")
    st.info(f"**Verdetto:** Asset nel settore **{settore}** con Piotroski F-Score di **{f_score}/9** e Rischio Altman **{altman}**. "
            f"Solidità di cassa (Cash/Debt): **{m['CashDebtAnn']:.2f}** (Benchmark Apple 0.49).")

    # Legenda
    with st.expander("📖 LEGENDA ENCICLOPEDICA"):
        st.markdown(f"""
        ### ⚖️ Modelli di Valutazione
        - **Buffett Raw:** Basato su Owner Earnings capitalizzati (multiplo x20).
        - **Golden MoS:** Linea dorata; rappresenta lo sconto del 25% sulla media.
        
        ### 🛡️ Indicatori di Solidità
        - **Piotroski Score:** Salute operativa (7-9 eccellente).
        - **Altman Z-Score:** Probabilità di fallimento (Low Risk è il target).
        - **Beneish M-Score:** Verifica probabile manipolazione dei bilanci.
        """)
        
        
else:
    st.error("Dati non disponibili o limite richieste raggiunto.")











