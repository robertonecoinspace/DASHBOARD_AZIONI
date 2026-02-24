import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Equity Analysis Terminal", layout="wide")

def get_val(df, keys):
    if df is None or df.empty: return 0
    for k in keys:
        if k in df.index: 
            val = df.loc[k]
            return val.iloc[0] if isinstance(val, (pd.Series, pd.DataFrame)) else val
    return 0

@st.cache_data(ttl=3600)
def load_all_data(ticker_list):
    """Calcola tutto in una volta sola per la massima velocità"""
    summary = []
    detailed_data = {}
    for t in ticker_list:
        try:
            s = yf.Ticker(t)
            i = s.info
            f = s.financials
            c = s.cashflow
            b = s.balance_sheet
            if 'currentPrice' not in i: continue
            
            # Calcoli Intrinseci
            p = i.get('currentPrice', 0)
            e = i.get('trailingEps', 1)
            sh = i.get('sharesOutstanding', 1)
            ni = get_val(f, ['Net Income'])
            dep = get_val(c, ['Depreciation And Amortization'])
            capx = abs(get_val(c, ['Capital Expenditure']))
            oe = ni + dep - capx
            
            vg = e * (8.5 + 17)
            vd = (i.get('freeCashflow', oe) * 15) / sh
            vb = (oe / sh) / 0.05
            vm = (vg + vd + vb) / 3
            tm = vm * 0.75
            
            detailed_data[t] = {"info": i, "fina": f, "cf": c, "bal": b, "hist": s.history(period="5y"), "vals": (p, vm, tm, oe, ni, vg, vd, vb)}
            
            if p <= tm:
                summary.append({"Ticker": t, "Prezzo": f"${p:.2f}", "Fair Value": f"${vm:.2f}", "Sconto": f"{((vm-p)/vm)*100:.1f}%"})
        except: continue
    return summary, detailed_data

# --- CARICAMENTO ---
try:
    lista_t = pd.read_csv('lista_ticker.csv')['Ticker'].tolist()
except:
    lista_t = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "BRK-B"]

with st.spinner("Inizializzazione Terminale..."):
    scanner_res, all_assets = load_all_data(lista_t)

# --- UI ---
st.title("🏛️ Strategic Investment Terminal")

# 🎯 TOP PANEL: OPPORTUNITÀ
st.subheader("🎯 Stock Opportunities (MoS > 25%)")
if scanner_res:
    st.table(pd.DataFrame(scanner_res))
else:
    st.info("Nessuna opportunità rilevata nella lista attuale.")

st.divider()

# 📊 SIDEBAR & ANALISI DETTAGLIATA
tk_sel = st.sidebar.selectbox("Seleziona Asset per Analisi:", lista_t)

if tk_sel in all_assets:
    asset = all_assets[tk_sel]
    p, vm, tm, oe, ni, vg, vd, vb = asset["vals"]
    i, f, b = asset["info"], asset["fina"], asset["bal"]
    
    st.header(f"📈 Report Dettagliato: {tk_sel}")
    
    # Valutazione Prezzo (Sottovalutato/Sopravvalutato)
    if p <= tm:
        st.success(f"### 💎 SOTTOVALUTATO (Target MoS: ${tm:.2f})")
    elif p <= vm:
        st.warning(f"### ⚖️ PREZZO EQUO (Fair Value: ${vm:.2f})")
    else:
        st.error(f"### ⚠️ SOPRAVVALUTATO (Fair Value: ${vm:.2f})")

    # Layout a colonne per KPI
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Market Price", f"${p:.2f}")
    c1.metric("P/E Ratio", f"{i.get('trailingPE', 0):.2f}")
    
    debt = i.get('totalDebt', 1)
    cash = i.get('totalCash', 0)
    c2.metric("Debt/Equity", f"{i.get('debtToEquity', 0):.2f}")
    c2.metric("Cash/Debt", f"{cash/debt:.2f}" if debt > 0 else "N/A")
    
    # Piotroski F-Score Semplificato
    f_score = 0
    if i.get('returnOnAssets', 0) > 0: f_score += 3
    if i.get('operatingCashflow', 0) > ni: f_score += 3
    if i.get('debtToEquity', 100) < 100: f_score += 3
    c3.metric("Piotroski Score", f"{f_score}/9")
    c3.metric("Revenue Growth", f"{((f.loc['Total Revenue'].iloc[0]/f.loc['Total Revenue'].iloc[-1])-1)*100:.1f}%")
    
    c4.metric("Altman Risk", "LOW" if i.get('auditRisk', 5) < 5 else "MEDIUM")
    c4.metric("Owner Earnings", f"${oe/1e9:.1f}B")

    # GRAFICI
    col_g1, col_g2 = st.columns(2)
    
    with col_g1:
        st.subheader("Valutazioni Intrinseche")
        fig_v = go.Figure()
        fig_v.add_trace(go.Bar(x=['Market', 'Graham', 'DCF', 'Buffett', 'AVG'], y=[p, vg, vd, vb, vm], 
                               marker_color=['#1e293b', '#3b82f6', '#f97316', '#10b981', '#8b5cf6']))
        fig_v.update_layout(template="plotly_white", height=400)
        st.plotly_chart(fig_v, use_container_width=True)

    with col_g2:
        st.subheader("Andamento Fatturato (Revenue)")
        rev_data = f.loc['Total Revenue'].iloc[::-1] # Inverte per avere ordine cronologico
        fig_r = go.Figure()
        fig_r.add_trace(go.Bar(x=rev_data.index.astype(str), y=rev_data.values, marker_color='#334155'))
        fig_r.update_layout(template="plotly_white", height=400)
        st.plotly_chart(fig_r, use_container_width=True)

    # LEGENDA
    with st.expander("📖 LEGENDA E INSIGHT TECNICI"):
        l1, l2 = st.columns(2)
        with l1:
            st.markdown("#### 🛡️ Indicatori di Solidità")
            st.write("**Piotroski Score:** Misura la salute finanziaria. Un punteggio elevato (7-9) indica un'azienda molto solida.")
            st.write("**Debt/Equity:** Se superiore a 200, l'azienda potrebbe essere troppo indebitata.")
            st.write("**Cash/Debt:** Indica quanti dollari di cassa ci sono per ogni dollaro di debito.")
        with l2:
            st.markdown("#### 💰 Modelli di Valutazione")
            st.write("**Graham Model:** Valutazione basata su EPS e crescita attesa.")
            st.write("**Buffett (Owner Earnings):** Il valore basato sulla cassa reale prodotta al netto delle spese capitali.")
            st.write("**Andamento Fatturato:** Se le barre sono crescenti, l'azienda sta espandendo la sua quota di mercato.")












