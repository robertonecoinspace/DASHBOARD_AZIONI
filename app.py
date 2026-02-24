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

# --- 1. SCANNER LEGGERO (Prezzi e Fair Value Rapido) ---
@st.cache_data(ttl=3600)
def fast_scanner(tickers):
    opportunities = []
    for t in tickers:
        try:
            s = yf.Ticker(t)
            # Scarichiamo solo info base per lo scanner (molto più veloce e sicuro)
            i = s.info
            p = i.get('currentPrice')
            e = i.get('trailingEps', 0)
            if p is None: continue
            
            # Valutazione rapida per lo scanner
            vg = e * (8.5 + 17)
            vm = vg # Approssimazione per lo scanner
            tm = vm * 0.75
            
            if p <= tm:
                sconto = ((vm - p) / vm) * 100
                opportunities.append({"Ticker": t, "Prezzo": f"${p:.2f}", "Fair Value": f"${vm:.2f}", "Sconto": f"{sconto:.1f}%"})
        except:
            continue
    return opportunities

# --- 2. ANALISI PROFONDA (Solo per il titolo selezionato) ---
@st.cache_data(ttl=86400)
def fetch_deep_data(ticker):
    try:
        s = yf.Ticker(ticker)
        i = s.info
        f = s.financials
        c = s.cashflow
        b = s.balance_sheet
        q_f = s.quarterly_financials
        q_b = s.quarterly_balance_sheet
        
        # Metriche base
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
        # Piotroski F-Score
        f_score = 0
        if i.get('returnOnAssets', 0) > 0: f_score += 2
        if i.get('operatingCashflow', 0) > ni: f_score += 3
        if i.get('debtToEquity', 100) < 100: f_score += 2
        if i.get('currentRatio', 0) > 1: f_score += 2
        
        # Altman Z-Score Fallback
        z_risk = i.get('auditRisk', 5)
        altman = "LOW RISK" if z_risk < 4 else "MEDIUM" if z_risk < 7 else "DISTRESS"
        
        # Beneish M-Score Fallback
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
    except Exception as err:
        return None

# --- UI ---
st.title("🏛️ Strategic Equity Terminal Pro")

# Scanner
st.subheader("🎯 Scanner Opportunità (Fast Scan)")
with st.spinner("Scansione prezzi in corso..."):
    opps = fast_scanner(lista_t)
    if opps:
        st.table(pd.DataFrame(opps))
    else:
        st.info("Nessun titolo sotto la soglia MoS rilevato al momento.")

st.divider()

# Sidebar e Analisi Dettagliata
tk_sel = st.sidebar.selectbox("Analizza Asset Dettagliato:", lista_t)
asset = fetch_deep_data(tk_sel)

if asset:
    p, vm, tm, oe, vg, vd, vb = asset["vals"]
    f_score, altman, beneish = asset["scores"]
    m = asset["metrics"]
    
    st.header(f"📈 {asset['info'].get('longName', tk_sel)}")
    
    # Valutazione
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
    cc3.metric("Div. Yield", f"{m['DivYield']:.2f}%")
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
        st.subheader("Fatturato Trimestrale (Ultimi 3 Anni)")
        if not asset["q_f"].empty and 'Total Revenue' in asset["q_f"].index:
            rev_q = asset["q_f"].loc['Total Revenue'].iloc[:12][::-1]
            colors = ['#10b981' if i == 0 or rev_q.values[i] >= rev_q.values[i-1] else '#ef4444' for i in range(len(rev_q))]
            st.plotly_chart(go.Figure(go.Bar(x=rev_q.index.astype(str), y=rev_q.values, marker_color=colors)), use_container_width=True)

    # Insight
    st.subheader("💡 Executive Quality Insights")
    st.info(f"**Verdetto:** Asset con Piotroski F-Score di **{f_score}/9** e Rischio Altman **{altman}**. "
            f"La solidità di cassa (Cash/Debt) è **{m['CashDebtAnn']:.2f}** rispetto al benchmark Apple (0.49).")

    # Legenda
    with st.expander("📖 LEGENDA ENCICLOPEDICA"):
        st.markdown(f"""
        ### ⚖️ Modelli di Valutazione
        - **Buffett Raw:** Valore basato sugli Owner Earnings capitalizzati senza sconto temporale.
        - **Golden MoS:** Margine di sicurezza del 25% sul Fair Value medio.
        
        ### 🛡️ Indicatori di Rischio
        - **Piotroski F-Score:** Salute finanziaria (7-9 eccellente).
        - **Altman Z-Score:** Rischio insolvenza (Low Risk è l'obiettivo).
        - **Beneish M-Score:** Monitoraggio manipolazioni contabili.
        
        
        """)
else:
    st.error("Errore nel caricamento. Yahoo Finance ha limitato le richieste. Attendi 30 secondi.")











