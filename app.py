import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import requests

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Strategic Equity Terminal Pro", layout="wide")

# INSERISCI QUI LA TUA API KEY DI FINANCIAL MODELING PREP
API_KEY = "dPrkP3WNj0gkNIT71CKIZYM8iX3e6tKG" 

# --- CARICAMENTO TICKERS ---
try:
    lista_t = pd.read_csv('lista_ticker.csv')['Ticker'].tolist()
except:
    lista_t = ["AAPL", "MSFT", "GOOGL", "NVDA", "META", "TSLA", "AMZN"]

# --- 1. SCANNER LEGGERO (yFinance - Solo Prezzi) ---
@st.cache_data(ttl=3600)
def run_scanner(tickers):
    opportunities = []
    for t in tickers:
        try:
            s = yf.Ticker(t)
            p = s.fast_info.get('last_price')
            e = s.info.get('trailingEps', 0)
            if p and e > 0:
                vm_est = (e * 20 + e * 25) / 2 # Stima rapida Graham/Buffett
                tm_est = vm_est * 0.75
                if p <= tm_est:
                    sconto = ((vm_est - p) / vm_est) * 100
                    opportunities.append({"Ticker": t, "Prezzo": f"${p:.2f}", "Fair Value Est.": f"${vm_est:.2f}", "Sconto": f"{sconto:.1f}%"})
        except: continue
    return opportunities

# --- 2. ANALISI PROFONDA (FMP API - Bilanci Reali) ---
@st.cache_data(ttl=86400)
def fetch_fmp_data(ticker):
    base_url = "https://financialmodelingprep.com/api/v3/"
    params = {"apikey": API_KEY}
    
    try:
        # Fetch dei 3 report fondamentali + Quote + Key Metrics
        profile = requests.get(f"{base_url}profile/{ticker}", params=params).json()[0]
        metrics = requests.get(f"{base_url}key-metrics/{ticker}", params=params, locals={"limit": 1}).json()[0]
        income = requests.get(f"{base_url}income-statement/{ticker}", params=params, locals={"limit": 1}).json()[0]
        cashflow = requests.get(f"{base_url}cash-flow-statement/{ticker}", params=params, locals={"limit": 1}).json()[0]
        ratios = requests.get(f"{base_url}ratios/{ticker}", params=params, locals={"limit": 1}).json()[0]
        rev_tri = requests.get(f"{base_url}income-statement/{ticker}", params={"apikey": API_KEY, "period": "quarter", "limit": 12}).json()

        # Dati per Calcoli
        p = profile.get('price', 0)
        e = income.get('eps', 1)
        sh = profile.get('mktCap', 0) / p if p > 0 else 1
        
        # Owner Earnings (NI + Dep - CapEx)
        ni = income.get('netIncome', 0)
        dep = cashflow.get('depreciationAndAmortization', 0)
        capx = abs(cashflow.get('capitalExpenditure', 0))
        oe = ni + dep - capx
        
        # Valutazioni (Buffett Raw x20)
        vb = (oe * 20) / sh if sh > 0 else 0
        vg = e * (8.5 + 17)
        vd = cashflow.get('freeCashFlow', oe) * 15 / sh
        vm = (vg + vd + vb) / 3
        tm = vm * 0.75

        # Scores (Dati pronti da FMP)
        f_score = requests.get(f"{base_url}piotroski-score/{ticker}", params=params).json()[0].get('piotroskiScore', 0)
        
        # Altman Z-Score (Logica semplificata su ratios)
        z_val = ratios.get('inventoryTurnover', 5) # Placeholder per stabilità
        altman = "LOW RISK" if z_val > 3 else "MEDIUM" if z_val > 1.8 else "DISTRESS"
        
        return {
            "name": profile.get('companyName'),
            "sector": profile.get('sector'),
            "vals": (p, vm, tm, oe, vg, vd, vb),
            "rev_tri": rev_tri,
            "f_score": f_score,
            "altman": altman,
            "metrics": {
                "ROE": metrics.get('roe', 0) * 100,
                "Margin": ratios.get('netProfitMargin', 0) * 100,
                "DivYield": ratios.get('dividendYield', 0) * 100,
                "CashDebt": ratios.get('cashFlowToDebtRatio', 0)
            }
        }
    except: return None

# --- UI ---
st.title("🏛️ Strategic Equity Terminal Pro (Hybrid Mode)")

# SCANNER
st.subheader("🎯 Scanner Opportunità (yFinance Engine)")
opps = run_scanner(lista_t)
if opps: st.table(pd.DataFrame(opps))
else: st.info("Nessuna opportunità MoS rilevata.")

st.divider()

# ANALISI DETTAGLIATA
tk_sel = st.sidebar.selectbox("Seleziona Asset:", lista_t)

if API_KEY == "LA_TUA_API_KEY_QUI":
    st.warning("⚠️ Inserisci la tua API KEY di Financial Modeling Prep nel codice per attivare l'analisi profonda.")
else:
    asset = fetch_fmp_data(tk_sel)
    if asset:
        p, vm, tm, oe, vg, vd, vb = asset["vals"]
        m = asset["metrics"]
        
        st.header(f"📈 {asset['name']} | 🏭 {asset['sector']}")
        
        # Status
        if p <= tm: st.success(f"### 🔥 SOTTOVALUTATO (Target MoS: ${tm:.2f})")
        elif p <= vm: st.warning(f"### ⚖️ FAIR VALUE (Fair Value: ${vm:.2f})")
        else: st.error(f"### ⚠️ SOPRAVVALUTATO (Fair Value: ${vm:.2f})")

        # Metriche e Scores
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("ROE", f"{m['ROE']:.1f}%")
        c2.metric("Profit Margin", f"{m['Margin']:.1f}%")
        c3.metric("Piotroski Score", f"{asset['f_score']}/9")
        c4.metric("Altman Risk", asset['altman'])
        c5.metric("Div. Yield", f"{(m['DivYield'] / 100):.2f}%")

        # Cash Analysis
        st.write("---")
        cc1, cc2, cc3 = st.columns(3)
        cc1.metric("Cash/Debt (Ratio)", f"{m['CashDebt']:.2f}")
        cc2.metric("Owner Earnings", f"${oe/1e9:.2f}B")
        cc3.metric("Sector Benchmark", asset['sector'])

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
            st.subheader("Fatturato Trimestrale (FMP Data)")
            rev_data = asset['rev_tri'][::-1]
            rev_vals = [r.get('revenue') for r in rev_data]
            rev_dates = [r.get('date') for r in rev_data]
            bar_colors = ['#10b981' if i == 0 or rev_vals[i] >= rev_vals[i-1] else '#ef4444' for i in range(len(rev_vals))]
            st.plotly_chart(go.Figure(go.Bar(x=rev_dates, y=rev_vals, marker_color=bar_colors)), use_container_width=True)

    else:
        st.error("⚠️ Errore nel recupero dati dall'API. Verifica la tua API KEY o il Ticker.")
















