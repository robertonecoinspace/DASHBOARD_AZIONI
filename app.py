import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Strategic Equity Terminal Pro", layout="wide")

def get_val(df, keys):
    if df is None or df.empty: return 0
    for k in keys:
        if k in df.index:
            try:
                val = df.loc[k]
                return val.iloc[0] if isinstance(val, (pd.Series, pd.DataFrame)) else val
            except: continue
    return 0

# --- CARICAMENTO ---
try:
    lista_t = pd.read_csv('lista_ticker.csv')['Ticker'].tolist()
except:
    lista_t = ["AAPL", "MSFT", "GOOGL", "NVDA", "BRK-B", "META", "TSLA"]

# --- SCANNER LIGHT (Per non farsi bloccare) ---
@st.cache_data(ttl=3600)
def run_scanner(tickers):
    opportunities = []
    for t in tickers[:15]: # Limita i primi 15 per evitare ban immediati
        try:
            s = yf.Ticker(t)
            # Chiediamo solo il prezzo, operazione leggerissima
            p = s.fast_info.get('last_price')
            e = s.info.get('trailingEps', 0)
            if p:
                vm_est = (e * 20 + e * 25) / 2
                tm_est = vm_est * 0.75
                if p <= tm_est:
                    opportunities.append({"Ticker": t, "Prezzo": f"${p:.2f}", "Sconto": "Sotto MoS"})
        except: continue
    return opportunities

# --- ANALISI PROFONDA ---
@st.cache_data(ttl=86400) # Cache pesante per 24 ore
def fetch_deep_data(ticker):
    try:
        s = yf.Ticker(ticker)
        # Scarichiamo i dati a blocchi per gestire i timeout
        i = s.info
        f = s.financials
        c = s.cashflow
        b = s.balance_sheet
        q_f = s.quarterly_financials
        
        p = i.get('currentPrice', 0)
        e = i.get('trailingEps', 1)
        sh = i.get('sharesOutstanding', 1)
        
        # Calcolo Owner Earnings con Fallback
        ni = get_val(f, ['Net Income'])
        dep = get_val(c, ['Depreciation And Amortization'])
        capx = abs(get_val(c, ['Capital Expenditure']))
        oe = ni + dep - capx
        
        vb = (oe * 20) / sh if sh > 0 else 0
        vg = e * (8.5 + 17)
        vd = (i.get('freeCashflow', oe) * 15) / sh
        vm = (vg + vd + vb) / 3
        tm = vm * 0.75

        # Scores semplificati per evitare crash su dati mancanti
        f_score = 0
        try:
            if i.get('returnOnAssets', 0) > 0: f_score += 3
            if i.get('operatingCashflow', 0) > ni: f_score += 3
            if i.get('currentRatio', 0) > 1: f_score += 3
        except: pass

        return {
            "info": i, "vals": (p, vm, tm, oe, vg, vd, vb),
            "q_f": q_f, "f_score": f_score,
            "metrics": {
                "ROE": i.get('returnOnEquity', 0) * 100,
                "Margin": i.get('profitMargins', 0) * 100,
                "DivYield": i.get('dividendYield', 0) * 100,
                "CashDebtAnn": (get_val(b, ['Cash And Cash Equivalents']) / get_val(b, ['Total Debt'])) if get_val(b, ['Total Debt']) > 0 else 0
            }
        }
    except: return None

# --- UI ---
st.title("🏛️ Strategic Equity Terminal Pro")

opps = run_scanner(lista_t)
if opps: st.table(pd.DataFrame(opps))

st.divider()

tk_sel = st.sidebar.selectbox("Seleziona Asset:", lista_t)
asset = fetch_deep_data(tk_sel)

if asset:
    i = asset['info']
    p, vm, tm, oe, vg, vd, vb = asset["vals"]
    m = asset["metrics"]
    
    st.header(f"📈 {i.get('longName', tk_sel)} | 🏭 {i.get('sector', 'N/A')}")
    
    # Metriche principali
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Piotroski (Est)", f"{asset['f_score']}/9")
    c2.metric("Div. Yield", f"{(m['DivYield'] / 100):.2f}%")
    c3.metric("Owner Earnings", f"${oe/1e9:.2f}B")
    c4.metric("ROE", f"{m['ROE']:.1f}%")
    
    # Grafico Valutazione
    st.plotly_chart(go.Figure(go.Bar(x=['Mkt', 'Graham', 'DCF', 'Buffett', 'FAIR'], y=[p, vg, vd, vb, vm])).add_hline(y=tm, line_color="gold"), use_container_width=True)

else:
    st.warning("⚠️ Yahoo Finance sta limitando le richieste per questo ticker. Prova tra 30 secondi o seleziona un altro titolo.")












