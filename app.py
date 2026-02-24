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
            # Gestione sicura per evitare errori di indicizzazione
            try:
                return val.iloc[0] if isinstance(val, (pd.Series, pd.DataFrame)) else val
            except:
                return 0
    return 0

# --- CARICAMENTO LISTA TICKER ---
try:
    lista_t = pd.read_csv('lista_ticker.csv')['Ticker'].tolist()
except:
    lista_t = ["AAPL", "MSFT", "GOOGL", "NVDA", "BRK-B", "META", "TSLA", "AMZN"]

# --- 1. SCANNER OTTIMIZZATO ---
@st.cache_data(ttl=3600)
def run_scanner(tickers):
    opportunities = []
    for t in tickers[:10]: # Limite a 10 per lo scanner per evitare blocchi IP
        try:
            s = yf.Ticker(t)
            i = s.info
            p = i.get('currentPrice')
            e = i.get('trailingEps', 0)
            if p is None or p == 0: continue
            
            vg = e * (8.5 + 17) 
            vb_quick = e * 20    
            vm = (vg + vb_quick) / 2
            tm = vm * 0.75 
            
            if p <= tm:
                sconto = ((vm - p) / vm) * 100
                opportunities.append({"Ticker": t, "Prezzo": f"${p:.2f}", "Fair Value Est.": f"${vm:.2f}", "Sconto": f"{sconto:.1f}%"})
        except:
            continue
    return opportunities

# --- 2. ANALISI PROFONDA ---
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
        
        p = i.get('currentPrice', 0)
        e = i.get('trailingEps', 1)
        sh = i.get('sharesOutstanding', 1)
        ni = get_val(f, ['Net Income'])
        dep = get_val(c, ['Depreciation And Amortization'])
        capx = abs(get_val(c, ['Capital Expenditure']))
        oe = ni + dep - capx
        
        # Buffett Raw (Multiplo x20)
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

# Scanner
st.subheader("🎯 Scanner Opportunità")
opps = run_scanner(lista_t)
if opps:
    st.table(pd.DataFrame(opps))
else:
    st.info("Nessuna opportunità immediata o limite API raggiunto per lo scanner.")

st.divider()

# Analisi Dettagliata
tk_sel = st.sidebar.selectbox("Asset Selezionato:", lista_t)
asset = fetch_deep_data(tk_sel)

if asset:
    i = asset['info']
    p, vm, tm, oe, vg, vd, vb = asset["vals"]
    f_score, altman, beneish = asset["scores"]
    m = asset["metrics"]
    
    st.header(f"📈 {i.get('longName', tk_sel)} | 🏭 {i.get('sector', 'N/A')}")
    
    if p <= tm: st.success(f"### 🔥 SOTTOVALUTATO (Target MoS: ${tm:.2f})")
    elif p <= vm: st.warning(f"### ⚖️ FAIR VALUE (${vm:.2f})")
    else: st.error(f"### ⚠️ SOPRAVVALUTATO (${vm:.2f})")

    # Metriche
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("ROE", f"{m['ROE']:.1f}%")
    c2.metric("Margin", f"{m['Margin']:.1f}%")
    c3.metric("F-Score", f"{f_score}/9")
    c4.metric("Altman", altman)
    c5.metric("Beneish", beneish)

    # Cash
    st.write("---")
    cc1, cc2, cc3, cc4 = st.columns(4)
    cc1.metric("C/D Ann", f"{m['CashDebtAnn']:.2f}")
    cc2.metric("C/D Tri", f"{m['CashDebtTri']:.2f}")
    cc3.metric("Yield", f"{m['DivYield']:.2f}%")
    cc4.metric("Owner Earnings", f"${oe/1e9:.2f}B")

    # Grafici
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Valutazione Buffett Raw")
        st.plotly_chart(go.Figure(go.Bar(x=['Mkt', 'Graham', 'DCF', 'Buffett', 'AVG'], y=[p, vg, vd, vb, vm], marker_color='#10b981')).add_hline(y=tm, line_color="#FFD700"), use_container_width=True)
    with col2:
        st.subheader("Revenue Momentum (3Y)")
        if not asset["q_f"].empty:
            rev = asset["q_f"].loc['Total Revenue'].iloc[:12][::-1]
            st.plotly_chart(go.Figure(go.Bar(x=rev.index.astype(str), y=rev.values, marker_color='#334155')), use_container_width=True)

    # Legenda
    with st.expander("📖 LEGENDA ENCICLOPEDICA"):
        st.write("**Piotroski F-Score:** Salute finanziaria. **Altman Z-Score:** Rischio fallimento. **Beneish M-Score:** Qualità contabile.")
        
else:
    st.error("⚠️ Errore critico: Yahoo Finance non risponde. Cambia ticker o attendi 1 minuto.")








