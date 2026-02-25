import streamlit as st
import pandas as pd
import requests

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Equity Terminal (New API Fix)", layout="wide")

# !!! INSERISCI QUI LA TUA API KEY DI FMP !!!
API_KEY = "dPrkP3WNj0gkNIT71CKIZYM8iX3e6tKG" 

# --- FUNZIONE DI RECUPERO DATI GREZZI (NO LEGACY ENDPOINTS) ---
@st.cache_data(ttl=3600)
def fetch_raw_financials(ticker):
    if "INSERISCI" in API_KEY:
        return "NO_KEY"
    
    base_url = "https://financialmodelingprep.com/api/v3"
    
    try:
        # 1. QUOTE (Sostituisce Profile per Prezzo e Nome)
        # Questo endpoint solitamente funziona anche per i nuovi account
        q_url = f"{base_url}/quote/{ticker}?apikey={API_KEY}"
        quote_data = requests.get(q_url).json()
        if not quote_data: return None
        quote = quote_data[0]
        
        # 2. INCOME STATEMENT (Limit=1 per i dati più recenti)
        inc_url = f"{base_url}/income-statement/{ticker}?period=annual&limit=1&apikey={API_KEY}"
        inc_data = requests.get(inc_url).json()
        if not inc_data: return None
        income = inc_data[0]
        
        # 3. BALANCE SHEET
        bs_url = f"{base_url}/balance-sheet-statement/{ticker}?period=annual&limit=1&apikey={API_KEY}"
        bs_data = requests.get(bs_url).json()
        if not bs_data: return None
        balance = bs_data[0]
        
        # 4. CASH FLOW
        cf_url = f"{base_url}/cash-flow-statement/{ticker}?period=annual&limit=1&apikey={API_KEY}"
        cf_data = requests.get(cf_url).json()
        if not cf_data: return None
        cashflow = cf_data[0]

        # --- CALCOLI MANUALI (Aggira il blocco Legacy) ---
        
        # Dati Base
        price = quote.get('price', 0)
        name = quote.get('name', ticker)
        eps = income.get('eps', 0)
        
        # ROE = Net Income / Total Equity
        ni = income.get('netIncome', 0)
        equity = balance.get('totalStockholdersEquity', 1) # Evita div/0
        roe = (ni / equity) * 100
        
        # Profit Margin = Net Income / Revenue
        rev = income.get('revenue', 1)
        margin = (ni / rev) * 100
        
        # Owner Earnings (Buffett) = Net Income + Dep&Amort - Capex
        dep = cashflow.get('depreciationAndAmortization', 0)
        capex = abs(cashflow.get('capitalExpenditure', 0))
        oe = ni + dep - capex
        
        # Cash / Debt Ratio
        cash_total = balance.get('cashAndCashEquivalents', 0) + balance.get('shortTermInvestments', 0)
        debt_total = balance.get('totalDebt', 0)
        cd_ratio = cash_total / debt_total if debt_total > 0 else 0
        
        # Dividend Yield (Calcolato manuale: Dividendi pagati / Market Cap)
        div_paid = abs(cashflow.get('dividendsPaid', 0))
        mkt_cap = quote.get('marketCap', 1)
        div_yield = (div_paid / mkt_cap) * 100
        
        # Piotroski Proxy (Calcolo semplificato sui dati che abbiamo)
        f_score = 0
        if ni > 0: f_score += 3 # Profittevole
        if cashflow.get('operatingCashFlow', 0) > ni: f_score += 3 # Qualità utili
        if balance.get('totalCurrentAssets', 0) > balance.get('totalCurrentLiabilities', 0): f_score += 3 # Liquidità
        
        # Altman Proxy (Basato su Debito/Asset)
        total_assets = balance.get('totalAssets', 1)
        lev_ratio = debt_total / total_assets
        altman = "LOW RISK" if lev_ratio < 0.5 else "MEDIUM" if lev_ratio < 0.8 else "HIGH RISK"
        
        # Beneish Proxy (Basato su crescita crediti vs ricavi - semplificato)
        receivables = balance.get('netReceivables', 0)
        beneish = "CONSERVATIVE" if (receivables/total_assets) < 0.3 else "CHECK AUDIT"

        return {
            "name": name,
            "sector": "Dati Grezzi (Settore N/A)", # Profile è bloccato, quindi il settore non lo vediamo
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
        return f"ERR: {str(e)}"

# --- UI ---
st.title("🏛️ Equity Terminal (Fix Legacy API)")
st.caption("Motore di Calcolo Manuale - Aggira i blocchi FMP 2025")

# Gestione Lista Ticker
try:
    df = pd.read_csv('lista_ticker.csv')
    # Cerca la colonna giusta
    col_name = next((c for c in df.columns if 'ick' in c or 'sym' in c or 'imbol' in c), None)
    if col_name:
        lista_t = df[col_name].dropna().unique().tolist()
    else:
        st.error("Colonna Ticker non trovata nel CSV.")
        lista_t = ["AAPL", "MSFT", "GOOGL"]
except:
    lista_t = ["AAPL", "NVDA", "TSLA"]

tk_sel = st.sidebar.selectbox("Asset:", lista_t)
data = fetch_raw_financials(tk_sel)

if isinstance(data, str): # Gestione Errori
    if data == "NO_KEY":
        st.error("Inserisci la API KEY nel codice!")
    else:
        st.error(f"Errore tecnico: {data}")
        st.info("Controlla che il ticker sia corretto (es. 'ENI.MI' per Milano).")

elif data:
    m = data["metrics"]
    st.header(f"📈 {data['name']}")
    
    # 1. Performance
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("ROE", f"{m['ROE']:.2f}%")
    c2.metric("PROFIT MARGIN", f"{m['Margin']:.2f}%")
    c3.metric("DIV. YIELD", f"{(m['Yield']):.2f}%")
    c4.metric("OWNER EARNINGS", f"${m['OE']/1e9:.2f}B")
    
    st.write("---")
    
    # 2. Solidità
    cc1, cc2, cc3, cc4 = st.columns(4)
    cc1.metric("CASH/DEBT", f"{m['CD']:.2f}", delta=f"{m['CD']-0.49:.2f} vs AAPL")
    cc2.metric("PIOTROSKI (Est)", f"{m['FScore']}/9")
    cc3.metric("LEVA (Altman Proxy)", m['Altman'])
    cc4.metric("QUALITY (Beneish)", m['Beneish'])
    
    st.divider()
    
    # 3. Insights
    col1, col2 = st.columns(2)
    with col1:
        if m['ROE'] > 15: st.success("✅ **Redditività:** Ottima. L'azienda genera alti profitti sul capitale.")
        else: st.info("ℹ️ **Redditività:** Standard per il mercato.")
        
        if m['CD'] > 0.49: st.success("✅ **Cassa:** Posizione finanziaria netta molto solida.")
        else: st.warning("⚠️ **Cassa:** Fare attenzione ai livelli di debito.")
        
    with col2:
        if m['FScore'] >= 6: st.success("✅ **Bilancio:** I fondamentali sono robusti.")
        else: st.error("🚨 **Bilancio:** Alcuni indicatori mostrano debolezza.")
        
    with st.expander("Perché funziona questo codice?"):
        st.write("""
        Questo codice non usa gli endpoint 'Profile' o 'Ratios' che FMP ha bloccato.
        Scarica invece i **Bilanci Grezzi (Income, Balance, Cash Flow)** e calcola 
        manualmente ROE, Margini e Yield usando le formule matematiche standard.
        """)

else:
    st.warning("Nessun dato trovato. Verifica il Ticker.")























