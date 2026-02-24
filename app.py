import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import os

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Strategic Equity Terminal Pro", layout="wide")

# Helper per estrarre dati in modo sicuro
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
    lista_t = ["AAPL", "MSFT", "GOOGL", "NVDA", "BRK-B", "META"]

# --- MOTORE DI ANALISI PROFONDA ---
@st.cache_data(ttl=86400)
def fetch_asset_data(ticker):
    try:
        s = yf.Ticker(ticker)
        i, f, c, b = s.info, s.financials, s.cashflow, s.balance_sheet
        q_f, q_b = s.quarterly_financials, s.quarterly_balance_sheet
        
        p = i.get('currentPrice', 0)
        e = i.get('trailingEps', 1)
        sh = i.get('sharesOutstanding', 1)
        
        # Calcolo Owner Earnings (OE)
        ni = get_val(f, ['Net Income'])
        dep = get_val(c, ['Depreciation And Amortization'])
        capx = abs(get_val(c, ['Capital Expenditure']))
        oe = ni + dep - capx
        
        # Buffett DCF (Sconto 10%) - Proiezione 10 anni
        growth, discount = 0.05, 0.10
        fcf_base = i.get('freeCashflow', oe)
        proj_fcf = [fcf_base * (1 + growth)**n for n in range(1, 11)]
        vb = sum([v / (1 + discount)**n for n, v in enumerate(proj_fcf, 1)]) / sh if sh > 0 else 0
        
        vg = e * (8.5 + 17)
        vd = (fcf_base * 15) / sh
        vm = (vg + vd + vb) / 3
        tm = vm * 0.75 # Golden MoS

        def calc_cd(df):
            cash = get_val(df, ['Cash And Cash Equivalents']) + get_val(df, ['Other Short Term Investments', 'Short Term Investments'])
            debt = get_val(df, ['Total Debt'])
            return cash / debt if debt > 0 else 0

        return {
            "info": i, "vals": (p, vm, tm, oe, vg, vd, vb),
            "q_f": q_f, "f": f,
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
st.title("🏛️ Equity Analysis Terminal Pro")

tk_sel = st.sidebar.selectbox("Seleziona Ticker:", lista_t)
asset = fetch_asset_data(tk_sel)

if asset:
    i = asset["info"]
    p, vm, tm, oe, vg, vd, vb = asset["vals"]
    m = asset["metrics"]
    
    # Pre-calcolo variabili per evitare errori nelle f-strings
    oe_billions = m['OE'] / 1e9
    m_cap_trillions = i.get('marketCap', 0) / 1e12
    
    st.header(f"📈 {i.get('longName', tk_sel)}")
    
    if p <= tm: st.success(f"### 🔥 SOTTOVALUTATO (Target MoS: ${tm:.2f})")
    elif p <= vm: st.warning(f"### ⚖️ PREZZO EQUO (Fair Value: ${vm:.2f})")
    else: st.error(f"### ⚠️ SOPRAVVALUTATO (Fair Value: ${vm:.2f})")

    # METRICHE PURE
    st.subheader("📋 Metriche Pure & Analisi Cassa")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("ROE", f"{m['ROE']:.1f}%")
    c2.metric("Profit Margin", f"{m['Margin']:.1f}%")
    c3.metric("Div. Yield", f"{m['DivYield']:.2f}%")
    c4.metric("Cash/Debt (Ann)", f"{m['CashDebtAnn']:.2f}")
    c5.metric("Cash/Debt (Tri)", f"{m['CashDebtTri']:.2f}")
    
    sc1, sc2, sc3 = st.columns(3)
    sc1.metric("Owner Earnings", f"${oe_billions:.2f}B")
    sc2.metric("Payout Ratio", f"{m['Payout']:.1f}%")
    sc3.metric("Market Cap", f"${m_cap_trillions:.2f}T")

    st.divider()

    # GRAFICI
    g1, g2 = st.columns(2)
    with g1:
        st.subheader("Valutazioni Intrinseche (Buffett 10%)")
        fig_v = go.Figure(go.Bar(x=['Market', 'Graham', 'DCF Std', 'Buffett 10%', 'MEDIA'], 
                                 y=[p, vg, vd, vb, vm], 
                                 marker_color=['#1e293b', '#3b82f6', '#f97316', '#10b981', '#8b5cf6']))
        fig_v.add_hline(y=tm, line_dash="dash", line_color="#FFD700", line_width=3, annotation_text="GOLDEN MoS")
        st.plotly_chart(fig_v, use_container_width=True)

    with g2:
        st.subheader("Andamento Fatturato (Revenue)")
        if not asset["f"].empty and 'Total Revenue' in asset["f"].index:
            rev_data = asset["f"].loc['Total Revenue'].iloc[::-1]
            fig_r = go.Figure(go.Bar(x=rev_data.index.astype(str), y=rev_data.values, marker_color='#334155'))
            st.plotly_chart(fig_r, use_container_width=True)

    # QUALITY INSIGHTS
    st.subheader("💡 Executive Quality Insights")
    score = 0
    if m['ROE'] > 15: score += 1
    if m['Margin'] > 15: score += 1
    if m['CashDebtAnn'] > 0.45: score += 1
    qual = "ECCELLENTE" if score == 3 else "SOLIDA" if score == 2 else "DEBOLE"
    
    st.info(f"**Verdetto:** Asset di qualità **{qual}**. Rapporto Cassa/Debito a **{m['CashDebtAnn']:.2f}** (Target Apple 0.49). "
            f"ROE al **{m['ROE']:.1f}%** con Owner Earnings di **${oe_billions:.2f}B**.")

    # LEGENDA
    with st.expander("📖 LEGENDA E LOGICA DI ANALISI"):
        st.markdown(f"""
        ### 💰 Modelli di Valutazione
        - **Buffett 10%:** Valore basato sui flussi di cassa proiettati a 10 anni e scontati al 10%.
        - **Golden MoS:** Linea dorata; rappresenta lo sconto del 25% sulla media dei modelli.
        
        ### 📊 Metriche Pure
        - **ROE:** Return on Equity. Sopra il 15% indica un forte vantaggio competitivo.
        - **Cash/Debt:** Rapporto tra liquidità e debito. Apple ha un benchmark di circa 0.49.
        - **Owner Earnings:** Utile Netto + Ammortamenti - CAPEX. La cassa reale prodotta.
        """)
else:
    st.error("Dati non disponibili per questo Ticker.")












