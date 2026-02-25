import streamlit as st
import pandas as pd
import requests

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Terminal: Pure Raw Data", layout="wide")

# !!! INSERISCI QUI LA TUA API KEY DI FMP !!!
API_KEY = "dPrkP3WNj0gkNIT71CKIZYM8iX3e6tKG" 

# --- MOTORE DI CALCOLO MANUALE (Bypassa i blocchi Legacy) ---
@st.cache_data(ttl=3600)
def fetch_raw_data_and_calculate(ticker):
    if "INSERISCI" in API_KEY:
        return {"error": "Manca API Key"}

    base_url = "https://financialmodelingprep.com/api/v3"
    
    try:
        # 1. SCARICHIAMO I 3 DOCUMENTI CONTABILI (Questi sono solitamente aperti)
        # Limit=1 ci dà l'ultimo anno disponibile
        
        # A. Income Statement (Conto Economico)
        url_inc = f"{base_url}/income-statement/{ticker}?period=annual&limit=1&apikey={API_KEY}"
        res_inc = requests.get(url_inc).json()
        
        # Controllo Errori FMP immediato
        if "Error Message" in str(res_inc):
            # Se bloccano anche questo, il ticker è sbagliato o l'account ha problemi
            return {"error": f"FMP Error: {res_inc.get('Error Message')}"}
        if not res_inc:
            return {"error": "Ticker non trovato. Se italiano, usa .MI (es. ENI.MI)"}
            
        income = res_inc[0]

        # B. Balance Sheet (Stato Patrimoniale)
        url_bs = f"{base_url}/balance-sheet-statement/{ticker}?period=annual&limit=1&apikey={API_KEY}"
        res_bs = requests.get(url_bs).json()
        if not res_bs: return {"error": "Balance Sheet non trovato"}
        balance = res_bs[0]
        
        # C. Cash Flow (Flussi di Cassa)
        url_cf = f"{base_url}/cash-flow-statement/{ticker}?period=annual&limit=1&apikey={API_KEY}"
        res_cf = requests.get(url_cf).json()
        if not res_cf: return {"error": "Cash Flow non trovato"}
        cashflow = res_cf[0]

        # 2. CALCOLI MATEMATICI (Facciamo noi il lavoro di FMP)
        
        # Dati Grezzi
        ni = income.get('netIncome', 0)
        rev = income.get('revenue', 1)
        equity = balance.get('totalStockholdersEquity', 1)
        total_assets = balance.get('totalAssets', 1)
        total_debt = balance.get('totalDebt', 0)
        cash = balance.get('cashAndCashEquivalents', 0) + balance.get('shortTermInvestments', 0)
        
        # -- Calcolo Metriche --
        
        # ROE = Utile Netto / Patrimonio Netto
        roe = (ni / equity) * 100
        
        # Profit Margin = Utile Netto / Fatturato
        margin = (ni / rev) * 100
        
        # Owner Earnings (Buffett) = NI + Dep&Amort - CapEx
        dep = cashflow.get('depreciationAndAmortization', 0)
        capex = abs(cashflow.get('capitalExpenditure', 0))
        oe = ni + dep - capex
        
        # Cash / Debt Ratio
        cd_ratio = cash / total_debt if total_debt > 0 else 0
        
        # Dividend Yield
        # NOTA: Senza endpoint "Quote" (bloccato), non abbiamo il prezzo dell'azione in tempo reale.
        # Non possiamo calcolare il Yield % preciso. Mostriamo quanto hanno pagato in totale.
        div_paid = abs(cashflow.get('dividendsPaid', 0))
        
        # Piotroski Proxy (Semplificato sui dati annuali)
        f_score = 0
        if ni > 0: f_score += 2 # Utile positivo
        if cashflow.get('operatingCashFlow', 0) > ni: f_score += 3 # Cash > Utile (Qualità)
        curr_assets = balance.get('totalCurrentAssets', 0)
        curr_liab = balance.get('totalCurrentLiabilities', 0)
        if curr_liab > 0 and (curr_assets / curr_liab) > 1.2: f_score += 2 # Liquidità
        if total_debt < equity: f_score += 2 # Solvibilità base
        
        # Altman Proxy (Leva Finanziaria come indicatore di rischio)
        lev = total_debt / total_assets
        altman = "LOW RISK" if lev < 0.5 else "MEDIUM" if lev < 0.75 else "HIGH RISK"
        
        # Beneish Proxy (Crediti vs Asset Totali)
        rec = balance.get('netReceivables', 0)
        beneish = "CONSERVATIVE" if (rec / total_assets) < 0.3 else "CHECK AUDIT"

        return {
            "symbol": income.get('symbol'),
            "currency": income.get('reportedCurrency'),
            "date": income.get('date'),
            "metrics": {
                "ROE": roe,
                "Margin": margin,
                "OE": oe,
                "CD": cd_ratio,
                "DivPaid": div_paid,
                "FScore": f_score,
                "Altman": altman,
                "Beneish": beneish
            }
        }

    except Exception as e:
        return {"error": f"Errore Tecnico: {str(e)}"}

# --- UI ---
st.title("🏛️ Raw Data Terminal (No-Legacy)")
st.caption("Analisi calcolata direttamente dai Bilanci Ufficiali (Bypassa limiti FMP 2025)")

# GESTIONE CSV
try:
    df = pd.read_csv('lista_ticker.csv')
    # Cerca la colonna Ticker in modo intelligente
    col = next((c for c in df.columns if 'ick' in c or 'ymbo' in c), None)
    if col:
        lista_t = df[col].dropna().unique().tolist()
    else:
        st.error("Colonna Ticker non trovata nel CSV. Uso default.")
        lista_t = ["AAPL", "NVDA"]
except:
    st.warning("File CSV non trovato. Uso default.")
    lista_t = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]

# SELEZIONE
tk_sel = st.sidebar.selectbox("Seleziona Asset:", lista_t)

if st.sidebar.button("ANALIZZA") or tk_sel:
    if API_KEY == "INSERISCI_LA_TUA_API_KEY_QUI":
        st.error("⛔ Devi inserire la API KEY nel codice!")
        st.stop()
        
    st.write(f"Scaricamento bilanci per **{tk_sel}**...")
    
    data = fetch_raw_data_and_calculate(tk_sel)
    
    if "error" in data:
        st.error(f"❌ {data['error']}")
        st.info("💡 Se è un'azione italiana, assicurati che il CSV contenga **.MI** (es. ENI.MI)")
    else:
        m = data["metrics"]
        
        st.header(f"📊 Analisi Fondamentale: {data['symbol']}")
        st.caption(f"Ultimo Bilancio Disponibile: {data['date']} | Valuta: {data['currency']}")
        
        # 1. KPI PERFORMANCE
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("ROE (Equity)", f"{m['ROE']:.2f}%")
        c2.metric("PROFIT MARGIN", f"{m['Margin']:.2f}%")
        c3.metric("DIVIDENDI PAGATI", f"{m['DivPaid']/1e9:.2f}B") # Valore assoluto perché il prezzo è bloccato
        c4.metric("OWNER EARNINGS", f"${m['OE']/1e9:.2f}B")

        st.write("---")
        
        # 2. SOLIDITÀ
        cc1, cc2, cc3, cc4 = st.columns(4)
        apple_ref = 0.49
        cc1.metric("CASH/DEBT", f"{m['CD']:.2f}", delta=f"{m['CD'] - apple_ref:.2f} vs AAPL")
        cc2.metric("PIOTROSKI (Calc)", f"{m['FScore']}/9")
        cc3.metric("LEVA (Altman Proxy)", m['Altman'])
        cc4.metric("QUALITY (Beneish)", m['Beneish'])
        
        # 3. EXECUTIVE INSIGHTS
        st.divider()
        col1, col2 = st.columns(2)
        with col1:
            if m['ROE'] > 15: st.success("✅ **Redditività:** L'azienda genera alti profitti sul capitale.")
            else: st.info("ℹ️ **Redditività:** Standard di mercato.")
            
            if m['CD'] > apple_ref: st.success("✅ **Liquidità:** Posizione di cassa superiore al benchmark Apple.")
            else: st.warning("⚠️ **Liquidità:** Attenzione ai livelli di debito.")
            
        with col2:
            if m['FScore'] >= 6: st.success("✅ **Bilancio:** Fondamentali solidi (Piotroski > 6).")
            else: st.error("🚨 **Bilancio:** Debolezza nei fondamentali.")
            
        with st.expander("📖 LEGENDA ENCICLOPEDICA"):
            st.markdown("""
            ### 🛠️ Come funziona questo terminale?
            Poiché FMP ha bloccato gli endpoint semplici, questo codice scarica i **3 Bilanci Ufficiali** e calcola tutto a mano:
            * **ROE:** `Utile / Patrimonio Netto`
            * **Owner Earnings:** `Utile + Ammortamenti - Capex`
            * **Dividendi:** Mostriamo il totale pagato (Cash Flow) perché senza il prezzo dell'azione (bloccato) non possiamo calcolare la %.
            * **Altman:** Stimato usando il rapporto Debito/Asset Totali.
            """)
            st.write("")

























