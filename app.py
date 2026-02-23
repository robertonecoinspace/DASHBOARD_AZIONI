import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from fpdf import FPDF
from datetime import datetime

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Strategic Equity Terminal", layout="wide")

# Lista Ticker Predefinita (Puoi espanderla)
DEFAULT_TICKERS = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "BRK-B", "TSLA", "AVGO", "COST"]

# --- FUNZIONI DI CALCOLO ---
@st.cache_data(ttl=3600)
def get_macro_rotation():
    """Analizza la rotazione settoriale tramite ETF Proxy"""
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
    """Estrae dati profondi e calcola metriche intrinseche e di solidità"""
    try:
        s = yf.Ticker(ticker)
        i, f, c, b = s.info, s.financials, s.cashflow, s.balance_sheet
        qb = s.quarterly_balance_sheet
        
        def gv(df, keys):
            for k in keys:
                if k in df.index:
                    val = df.loc[k]
                    return val.iloc[0] if isinstance(val, (pd.Series, pd.DataFrame)) else val
            return 0

        p = i.get('currentPrice', 0)
        e = i.get('trailingEps', 1)
        sh = i.get('sharesOutstanding', 1)
        ni = gv(f, ['Net Income'])
        
        # OWNER EARNINGS (BUFFETT)
        dep = gv(c, ['Depreciation And Amortization'])
        capex = abs(gv(c, ['Capital Expenditure']))
        oe = ni + dep - capex
        
        # VALUTAZIONI INTRINSECHE
        vg = e * (8.5 + 17)
        vd = (i.get('freeCashflow', oe) * 15) / sh
        vb = (oe / sh) / 0.05
        vm = (vg + vd + vb) / 3
        tm = vm * 0.75

        # --- CASSA/DEBITO PRECISA (CORRETTA PER APPLE E BIG TECH) ---
        # Include Short Term Investments nella liquidità
        total_debt_ann = i.get('totalDebt', 1)
        cash_ann = i.get('totalCash', 0) 
        ratio_ann = cash_ann / total_debt_ann if total_debt_ann > 0 else 0

        # Trimestrale: Cassa + Titoli Negoziabili / Debito Totale
        q_liquidity = gv(qb, ['Cash And Cash Equivalents']) + gv(qb, ['Other Short Term Investments', 'Short Term Investments'])
        q_total_debt = gv(qb, ['Total Debt'])
        ratio_tri = q_liquidity / q_total_debt if q_total_debt > 0 else 0

        return {
            'ticker': ticker, 'p': p, 'vm': vm, 'tm': tm, 
            'status': "Sottovalutato" if p <= tm else "Equo
