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
    
    if p <= tm: st.success(f"### 🔥 SOTTOVALUTATO (Target MoS: ${












