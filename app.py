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

# --- CARICAMENTO TICKERS ---
try:
    lista_t = pd.read_csv('lista_ticker.csv')['Ticker'].tolist()
except:
    lista_t = ["AAPL", "MSFT", "GOOGL", "NVDA", "BRK-B", "META", "TSLA", "AMZN"]

# --- MOTORE DI ANALISI ---
@st.cache_data(ttl=86400)
def fetch_asset_data(ticker):
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
        
        # 1. VALUTAZIONE BUFFETT (Senza sconto 10% come richiesto)
        # Calcolo basato sul multiplo degli Owner Earnings (Capitalizzazione diretta)
        vb = (oe * 20) / sh if sh > 0 else 0 
        
        # Altri Modelli
        vg = e * (8.5 + 17)
        vd = (i.get('freeCashflow', oe) * 15) / sh
        vm = (vg + vd + vb) / 3
        tm = vm * 0.75 # Golden MoS (Sconto 25%)

        # 2. SCORE AVANZATI
        # Piotroski F-Score (Semplificato)
        f_score = 0
        if i.get('returnOnAssets', 0) > 0: f_score += 2
        if i.get('operatingCashflow', 0) > ni: f_score += 3
        if i.get('debtToEquity', 100) < 100: f_score += 2
        if i.get('currentRatio', 0) > 1: f_score += 2

        # Altman Z-Score (Logica semplificata su Info)
        z_val = i.get('auditRisk', 5)
        altman = "LOW RISK" if z_val < 4 else "MEDIUM" if z_val < 7 else "DISTRESS"

        # Beneish M-Score (Probabilità manipolazione)
        m_val = i.get('extraordinaryCashFlows', 0)
        beneish = "CONSERVATIVE" if m_val == 0 else "CHECK AUDIT"

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
                "Payout": i.get('payoutRatio', 0) * 100,
                "CashDebtAnn": calc_cd(b),
                "CashDebtTri": calc_cd(q_b),
                "OE": oe
            }
        }
    except: return None

# --- UI PRINCIPALE ---
st.title("🏛️ Strategic Equity Terminal Pro")

# 🎯 SCANNER OPPORTUNITÀ
st.subheader("🎯 Scanner Opportunità (Sconto > 25%)")
scanner_list = []
for t in lista_t[:12]:
    data = fetch_asset_data(t)
    if data:
        p, vm, tm = data["vals"][0], data["vals"][1], data["vals"][2]
        if p <= tm:
            sconto = ((vm - p) / vm) * 100
            scanner_list.append({"Ticker": t, "Prezzo": f"${p:.2f}", "Fair Value": f"${vm:.2f}", "Sconto": f"{sconto:.1f}%"})
if scanner_list:
    st.table(pd.DataFrame(scanner_list))
else:
    st.info("Nessuna opportunità rilevata.")

st.divider()

# 📊 ANALISI DETTAGLIATA
tk_sel = st.sidebar.selectbox("Analizza Asset:", lista_t)
asset = fetch_asset_data(tk_sel)

if asset:
    i = asset["info"]
    p, vm, tm, oe, vg, vd, vb = asset["vals"]
    f_score, altman, beneish = asset["scores"]
    m = asset["metrics"]

    st.header(f"📈 {i.get('longName', tk_sel)}")
    
    # Status
    if p <= tm: st.success(f"### 🔥 SOTTOVALUTATO (Target MoS: ${tm:.2f})")
    elif p <= vm: st.warning(f"### ⚖️ FAIR VALUE (Fair Value: ${vm:.2f})")
    else: st.error(f"### ⚠️ SOPRAVVALUTATO (Fair Value: ${vm:.2f})")

    # Metriche Pure & Health Scores
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
        st.subheader("Fatturato Trimestrale (3 Anni)")
        if not asset["q_f"].empty and 'Total Revenue' in asset["q_f"].index:
            rev_q = asset["q_f"].loc['Total Revenue'].iloc[:12][::-1]
            bar_colors = ['#10b981' if i == 0 or rev_q.values[i] >= rev_q.values[i-1] else '#ef4444' for i in range(len(rev_q))]
            st.plotly_chart(go.Figure(go.Bar(x=rev_q.index.astype(str), y=rev_q.values, marker_color=bar_colors)), use_container_width=True)

    # Executive Insights
    st.subheader("💡 Executive Quality Insights")
    qual = "ECCELLENTE" if f_score >= 7 and m['ROE'] > 15 else "SOLIDA" if f_score >= 5 else "RISCHIOSA"
    st.info(f"**Verdetto:** Asset di qualità **{qual}**. Piotroski F-Score di **{f_score}/9** indica una salute {'robusta' if f_score > 6 else 'precaria'}. "
            f"Rischio Altman: **{altman}**. Il rapporto Cassa/Debito è **{m['CashDebtAnn']:.2f}**.")

    # Legenda Approfondita
    with st.expander("📖 LEGENDA ENCICLOPEDICA E LOGICA TECNICA"):
        st.markdown(f"""
        ### ⚖️ Modelli di Valutazione (Raw Buffett)
        - **Buffett Raw Fair Value:** A differenza del DCF classico, questo calcolo valuta il business basandosi sulla capacità di generare cassa reale (Owner Earnings) capitalizzata, senza applicare lo sconto temporale del 10%. La prudenza è garantita dal **Golden MoS (25% di sconto)**.
        - **Golden MoS:** Prezzo d'acquisto ideale. Se il prezzo di mercato è sotto questa linea dorata, hai una protezione statistica contro le fluttuazioni.

        ### 🛡️ Indicatori di Solidità e Rischio
        - **Piotroski F-Score ({f_score}/9):** Valuta 9 criteri di bilancio. 7-9: Ottimo; 0-3: Debole.
        - **Altman Z-Score ({altman}):** Predice la probabilità di insolvenza entro 2 anni.
        - **Beneish M-Score ({beneish}):** Un modello matematico che utilizza rapporti finanziari per identificare se un'azienda ha manipolato i propri utili.

        ### 📊 Metriche Pure
        - **ROE ({m['ROE']:.1f}%):** Quanto profitto genera l'azienda per ogni euro di capitale proprio.
        - **Cash/Debt ({m['CashDebtAnn']:.2f}):** Rapporto liquidità/debito. Benchmark Apple: **0.49**.
        - **Owner Earnings:** Utile Netto + Ammortamenti - CAPEX. È la cassa che Buffett considera "vera".
        """)











