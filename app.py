import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from fpdf import FPDF
from datetime import datetime

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Strategic Equity Terminal", layout="wide")

# Lista Ticker Monitorati
DEFAULT_TICKERS = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "BRK-B", "TSLA", "AVGO", "COST"]

# --- FUNZIONI DI CALCOLO ---
@st.cache_data(ttl=3600)
def get_macro_rotation():
    sector_map = {
        'XLK': 'Technology', 'XLF': 'Financials', 'XLV': 'Healthcare', 
        'XLE': 'Energy', 'XLI': 'Industrials', 'XLU': 'Utilities', 'XLP': 'Staples'
    }
    macro_results = {}
    for etf, name in sector_map.items():
        try:
            d = yf.Ticker(etf).history(period="3mo")
            perf = ((d['Close'].iloc[-1] / d['Close'].iloc[0]) - 1) * 100
            macro_results[name] = perf
        except: macro_results[name] = 0
    return macro_results

@st.cache_data(ttl=3600)
def fetch_stock_data(ticker):
    try:
        s = yf.Ticker(ticker)
        i = s.info
        f = s.financials
        c = s.cashflow
        qb = s.quarterly_balance_sheet
        
        if 'currentPrice' not in i: return None

        def gv(df, keys):
            for k in keys:
                if k in df.index:
                    val = df.loc[k]
                    return val.iloc[0] if isinstance(val, (pd.Series, pd.DataFrame)) else val
            return 0

        # Metriche Prezzo e Utili
        p = i.get('currentPrice', 0)
        e = i.get('trailingEps', 1)
        sh = i.get('sharesOutstanding', 1)
        ni = gv(f, ['Net Income'])
        
        # Buffett Owner Earnings
        dep = gv(c, ['Depreciation And Amortization'])
        capex = abs(gv(c, ['Capital Expenditure']))
        oe = ni + dep - capex
        
        # Valutazioni Intrinseche
        vg = e * (8.5 + 17)
        vd = (i.get('freeCashflow', oe) * 15) / sh
        vb = (oe / sh) / 0.05
        vm = (vg + vd + vb) / 3
        tm = vm * 0.75

        # --- LOGICA CASSA/DEBITO (PRECISIONE APPLE 0.74/0.49) ---
        total_debt_ann = i.get('totalDebt', 1)
        cash_ann = i.get('totalCash', 0) 
        ratio_ann = cash_ann / total_debt_ann if total_debt_ann > 0 else 0

        # Calcolo Trimestrale inclusi Investimenti Breve Termine
        q_liquidity = gv(qb, ['Cash And Cash Equivalents']) + gv(qb, ['Other Short Term Investments', 'Short Term Investments'])
        q_total_debt = gv(qb, ['Total Debt'])
        ratio_tri = q_liquidity / q_total_debt if q_total_debt > 0 else 0

        return {
            'ticker': ticker, 'p': p, 'vm': vm, 'tm': tm, 
            'status': "Sottovalutato" if p <= tm else ("Equo" if p <= vm else "Sopravvalutato"),
            'models': {'Graham': vg, 'DCF': vd, 'Buffett': vb},
            'ratios': {
                'Piotroski': 7 if i.get('returnOnAssets', 0) > 0 else 4,
                'Altman': "LOW" if i.get('auditRisk', 5) < 5 else "MEDIUM",
                'Beneish': "SANO" if i.get('payoutRatio', 0) < 0.8 else "RISCHIO",
                'CashDebtAnn': ratio_ann, 'CashDebtTri': ratio_tri,
                'DivYield': i.get('dividendYield', 0) * 100,
                'Payout': i.get('payoutRatio', 0) * 100,
                'Insider': i.get('heldPercentInsiders', 0) * 100,
                'DebtEq': i.get('debtToEquity', 0)
            },
            'info': i, 'fina': f, 'oe': oe, 'ni': ni, 'sector': i.get('sector', 'N/A')
        }
    except: return None

# --- UI MAIN ---
st.title("🏛️ Strategic Investment Terminal")

# 1. ANALISI MACRO
st.subheader("🌐 Market Context & Sector Rotation")
macro = get_macro_rotation()
col_m1, col_m2 = st.columns([1, 2])

with col_m1:
    top_sector = max(macro, key=macro.get)
    st.metric("Leading Sector (3M)", top_sector, f"{macro[top_sector]:.1f}%")
    ciclo = "LATE CYCLE / RECESSION" if top_sector in ['Healthcare', 'Utilities', 'Staples'] else "EARLY / MID CYCLE"
    st.write(f"Estimated Phase: **{ciclo}**")

with col_m2:
    fig_macro = go.Figure(go.Bar(x=list(macro.keys()), y=list(macro.values()), 
                                 marker_color=['#10b981' if x > 0 else '#ef4444' for x in macro.values()]))
    fig_macro.update_layout(height=250, margin=dict(t=20, b=0, l=0, r=0), template="plotly_white")
    st.plotly_chart(fig_macro, use_container_width=True)



st.divider()

# 2. SCANNER SOTTOVALUTATI
st.subheader("🎯 Scanner: Migliori Opportunità (MoS > 25%)")
all_data = [fetch_stock_data(t) for t in DEFAULT_TICKERS]
valid_data = [r for r in all_data if r is not None]
    
under_df = pd.DataFrame([
    {'Ticker': r['ticker'], 'Prezzo': f"${r['p']:.2f}", 'Fair Value': f"${r['vm']:.2f}", 'Sconto': f"{((r['vm']-r['p'])/r['vm'])*100:.1f}%"}
    for r in valid_data if r['status'] == "Sottovalutato"
])
if not under_df.empty:
    st.table(under_df)
else:
    st.info("Ness

