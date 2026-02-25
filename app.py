import streamlit as st
import pandas as pd
import requests
import yfinance as yf

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Equity Terminal (Legacy Bypass)", layout="wide")

# !!! INSERISCI LA TUA API KEY QUI !!!
API_KEY = "dPrkP3WNj0gkNIT71CKIZYM8iX3e6tKG" 

# --- FUNZIONE IBRIDA (FMP RAW + YF METADATA) ---
@st.cache_data(ttl=86400)
def fetch_data_bypass(ticker):
    # 1. RECUPERO DATI GREZZI DA FMP (Endpoint Aperti)
    base_url = "https://financialmodelingprep.com/api/v3"
    
    try:
        # A. Conto Economico (Income Statement)
        url_inc = f"{base_url}/income-statement/{ticker}?period=annual&limit=1&apikey={API_KEY}"
        res_inc = requests.get(url_inc).json()
        
        # Se FMP restituisce errore o lista vuota, ci fermiamo
        if "Error Message" in str(res_inc) or not res_inc:
            return None
            
        income = res_inc[0]

        # B. Stato Patrimoniale (Balance Sheet)
        url_bs = f"{base_url}/balance-sheet-statement/{ticker}?period=annual&limit=1&apikey={API_KEY}"
        balance = requests.get(url_bs).json()[0]
        
        # C. Flussi di Cassa (Cash Flow)
        url_cf = f"{base_url}/cash-flow-statement/{ticker}?period=annual&limit=1&apikey={API_KEY}"
        cashflow = requests.get(url_cf).json()[0]
        
        # 2. RECUPERO METADATI DA YFINANCE (Solo Nome, Settore, Prezzo)
        # Usiamo yf.Ticker che è molto leggero se non chiediamo lo storico
        yf_asset = yf.Ticker(ticker)
        # fast_info non fa scraping, usa l'API interna di Yahoo
        price = yf_asset.fast_info.get('last_price', 0)
        try:
            # Info base per nome e settore
            info = yf_asset.info
            name = info.get('longName', ticker)
            sector = info.get('sector', 'N/A')
            market_cap = info.get('marketCap', 1)
        except:
            name = ticker
            sector = "N/A"
            market_cap = 1

        # 3. CALCOLI MANUALI (Aggiriamo i Legacy Endpoints)
        
        # ROE = Net Income / Total Equity
        ni = income.get('netIncome', 0)
        equity = balance.get('totalStockholdersEquity', 1)
        roe = (ni / equity) * 100
        
        # Profit Margin = Net Income / Revenue
        rev = income.get('revenue', 1)
        margin = (ni / rev) * 100
        
        # Owner Earnings = NI + Dep&Amort - CapEx
        dep = cashflow.get('depreciationAndAmortization', 0)
        capex = abs(cashflow.get('capitalExpenditure', 0))
        oe = ni + dep - capex
        
        # Cash / Debt Ratio
        cash_total = balance.get('cashAndCashEquivalents', 0) + balance.get('shortTermInvestments', 0)
        debt_total = balance.get('totalDebt', 0)
        cd_ratio = cash_total / debt_total if debt_total > 0 else 0
        
        # Dividend Yield = Dividendi Pagati / Market Cap
        div_paid = abs(cashflow.get('dividendsPaid', 0))
        div_yield = (div_paid / market_cap) * 100
        
        # Piotroski Proxy (Calcolo manuale sui dati grezzi)
        f_score = 0
        if ni > 0: f_score += 2
        if cashflow.get('operatingCashFlow', 0) > ni: f_score += 3
        curr_assets = balance.get('totalCurrentAssets', 0)
        curr_liab = balance.get('totalCurrentLiabilities', 0)
        if curr_liab > 0 and (curr_assets / curr_liab) > 1.2: f_score += 2
        if balance.get('totalDebt', 0) < equity: f_score += 2
        
        # Altman Proxy (Basato su Leva Finanziaria)
        # Z-Score vero richiede volatilità, usiamo Debt/Assets come proxy sicuro
        total_assets = balance.get('totalAssets', 1)
        lev = debt_total / total_assets
        altman = "LOW RISK" if lev < 0.5 else "MEDIUM" if lev < 0.75 else "HIGH RISK"
        
        # Beneish Proxy (Crescita crediti vs Vendite)
        receivables = balance.get('netReceivables', 0)
        beneish = "CONSERVATIVE" if (receivables / total_assets) < 0.3 else "CHECK AUDIT"

        return {
            "name": name,
            "sector": sector,
            "metrics": {
                "ROE": roe,
                "Margin": margin,
                "Yield": div_yield,
                "OE": oe,
                "CD": cd_ratio,
                "FScore": f_score,
                "Altman": altman,
                "Beneish": beneish
            }
        }

    except Exception as e:
        return None

# --- UI ---
st.title("🏛️ Equity Terminal (FMP Raw + YF Hybrid)")
st.caption("Motore Ibrido: Dati Contabili FMP + Prezzi Yahoo (Nessun Blocco Legacy)")

# Gestione CSV
try:
    df = pd.read_csv('lista_ticker.csv')
    # Cerca la colonna ticker
    col = next((c for c in df.columns if 'ick' in c or 'ymbo' in c), None)
    lista_t = df[col].dropna().unique().tolist() if col else ["AAPL", "NVDA"]
except:
    lista_t = ["AAPL", "NVDA", "TSLA", "MSFT"]

tk_sel = st.sidebar.selectbox("Seleziona Ticker:", lista_t)

if API_KEY == "INSERISCI_LA_TUA_API_KEY_QUI":
    st.error("⛔ Inserisci la tua API Key FMP nel codice!")
else:
    data = fetch_data_bypass(tk_sel)

    if data:
        m = data["metrics"]
        st.header(f"📈 {data['name']} | 🏭 {data['sector']}")
        
        # KPI PRINCIPALI
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("ROE", f"{m['ROE']:.2f}%")
        c2.metric("PROFIT MARGIN", f"{m['Margin']:.2f}%")
        c3.metric("DIV. YIELD", f"{m['Yield']:.2f}%")
        c4.metric("OWNER EARNINGS", f"${m['OE']/1e9:.2f}B")
        
        st.write("---")
        
        # SOLIDITÀ & RISCHIO
        cc1, cc2, cc3, cc4 = st.columns(4)
        cc1.metric("CASH/DEBT", f"{m['CD']:.2f}", delta=f"{m['CD']-0.49:.2f} vs AAPL")
        cc2.metric("PIOTROSKI (Calc)", f"{m['FScore']}/9")
        cc3.metric("ALTMAN PROXY", m['Altman'])
        cc4.metric("BENEISH PROXY", m['Beneish'])
        
        # EXECUTIVE INSIGHTS
        st.divider()
        st.subheader("💡 Analisi Automatica")
        
        col1, col2 = st.columns(2)
        with col1:
            if m['ROE'] > 15: st.success("✅ **Redditività:** L'azienda genera ottimi profitti dal capitale.")
            else: st.info("ℹ️ **Redditività:** Standard di mercato.")
            
            if m['CD'] > 0.49: st.success("✅ **Liquidità:** Posizione di cassa superiore al benchmark Apple.")
            else: st.warning("⚠️ **Liquidità:** Attenzione ai livelli di debito.")
            
        with col2:
            if m['FScore'] >= 6: st.success("✅ **Bilancio:** Fondamentali solidi (Piotroski > 6).")
            else: st.error("🚨 **Bilancio:** Debolezza nei fondamentali.")

    else:
        st.error("Dati non trovati.")
        st.info("Possibili cause:")
        st.markdown("1. Il Ticker è errato (Es: per azioni italiane usa `.MI`).")
        st.markdown("2. Hai finito le chiamate API giornaliere.")
























