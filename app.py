import streamlit as st
import yfinance as yf
import pandas as pd

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Equity Quality Terminal", layout="wide")

def get_val(df, keys):
    if df is None or df.empty: return 0
    for k in keys:
        if k in df.index:
            try:
                val = df.loc[k]
                return val.iloc[0] if isinstance(val, (pd.Series, pd.DataFrame)) else val
            except: continue
    return 0

# --- CORE ENGINE: ESTRAZIONE MIRATA (Anti-Blocco) ---
@st.cache_data(ttl=86400) # Cache 24h per ridurre al minimo le richieste
def fetch_quality_metrics(ticker):
    try:
        # Usiamo l'approccio più leggero possibile: solo l'oggetto info
        asset = yf.Ticker(ticker)
        i = asset.info
        
        if not i or 'currentPrice' not in i:
            return None

        # 1. Parametri di Bilancio e Profitto
        roe = i.get('returnOnEquity', 0) * 100
        margin = i.get('profitMargins', 0) * 100
        # Dividend Yield (visualizzato diviso 100 come richiesto)
        div_yield = i.get('dividendYield', 0) * 100
        
        # 2. Owner Earnings (Buffett: NI + D&A - CapEx)
        ni = i.get('netIncomeToCommon', 0)
        dep = i.get('depreciation', 0)
        capex = abs(i.get('capitalExpenditure', 0))
        oe = ni + dep - capex
        
        # 3. Cash/Debt (Benchmark Apple 0.49)
        cash = i.get('totalCash', 0)
        debt = i.get('totalDebt', 0)
        cd_ratio = cash / debt if debt > 0 else 0
        
        # 4. Scores e Rischio
        # Piotroski F-Score Proxy (Efficienza, Leva, Liquidità)
        f_score = 0
        if roe > 12: f_score += 3
        if i.get('currentRatio', 0) > 1.2: f_score += 3
        if i.get('operatingCashflow', 0) > ni: f_score += 3
        
        # Altman & Beneish Risk (Basati su indicatori di audit e governance)
        altman_idx = i.get('auditRisk', 5)
        beneish_idx = i.get('boardRisk', 5)

        return {
            "name": i.get('longName', ticker),
            "sector": i.get('sector', 'N/A'),
            "oe": oe,
            "f_score": f_score,
            "altman": "LOW RISK" if altman_idx





















