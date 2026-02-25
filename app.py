import streamlit as st
import pandas as pd
import requests

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Terminal - Pure FMP Data", layout="wide")

# !!! INSERISCI QUI LA TUA API KEY DI FMP !!!
API_KEY = "dPrkP3WNj0gkNIT71CKIZYM8iX3e6tKG" 

# --- FUNZIONE DI RECUPERO DATI (SOLO FMP - NIENTE YAHOO) ---
@st.cache_data(ttl=3600)
def fetch_pure_fmp_data(ticker):
    if "INSERISCI" in API_KEY:
        return {"error": "Manca API Key"}

    base_url = "https://financialmodelingprep.com/api/v3"
    
    try:
        # 1. SCARICHIAMO I BILANCI (Questi sono aperti anche ai Free User)
        # Income Statement
        url_inc = f"{base_url}/income-statement/{ticker}?period=annual&limit=1&apikey={API_KEY}"
        res_inc = requests.get(url_inc).json()
        
        # CONTROLLO ERRORI FMP
        if not res_inc: 
            return {"error": "Ticker non trovato o Dati Vuoti (Prova ad aggiungere .MI o .PA)"}
        if "Error Message" in str(res_inc):
            return {"error": f"Errore API FMP: {res_inc.get('Error Message')}"}
            
        income = res_inc[0]

        # Balance Sheet
        url_bs = f"{base_url}/balance-sheet-statement/{ticker}?period=annual&limit=1&apikey={API_KEY}"
        balance = requests.get(url_bs).json()[0]
        
        # Cash Flow
        url_cf = f"{base_url}/cash-flow-statement/{ticker}?period=annual&limit=1&apikey={API_KEY}"
        cashflow = requests.get(url_cf).json()[0]

        # 2. CALCOLI MATEMATICI (Facciamo noi quello che FMP blocca)
        
        # Dati Grezzi
        ni = income.get('netIncome', 0)
        rev = income.get('revenue', 1)
        equity = balance.get('totalStockholdersEquity', 1)
        cash = balance.get('cashAndCashEquivalents', 0) + balance.get('shortTermInvestments', 0)
        debt = balance.get('totalDebt', 0)
        
        # -- Calcolo Metriche --
        
        # ROE
        roe = (ni / equity) * 100
        
        # Profit Margin
        margin = (ni / rev) * 100
        
        # Owner Earnings (Buffett)
        dep = cashflow.get('depreciationAndAmortization', 0)
        capex = abs(cashflow.get('capitalExpenditure', 0))
        oe = ni + dep - capex
        
        # Cash / Debt Ratio
        cd_ratio = cash / debt if debt > 0 else 0
        
        # Dividend Yield (Stima: Dividendi pagati / (Utile / EPS) * Prezzo... 
        # Ma senza prezzo real-time è difficile. Usiamo Dividend Payout Ratio come proxy o 0)
        div_paid = abs(cashflow.get('dividendsPaid', 0))
        # Senza market cap (che è bloccato su Profile), non possiamo calcolare il Yield % preciso.
        # Restituiamo il valore assoluto dei dividendi pagati.
        
        # Piotroski Proxy (Semplificato)
        f_score = 0
        if ni > 0: f_score += 2
        if cashflow.get('operatingCashFlow', 0) > ni: f_score += 3
        curr_assets = balance.get('totalCurrentAssets', 0)
        curr_liab = balance.get('totalCurrentLiabilities', 0)
        if curr_liab > 0 and (curr_assets / curr_liab) > 1.2: f_score += 2
        if debt < equity: f_score += 2
        
        # Altman Proxy (Leva)
        total_assets = balance.get('totalAssets', 1)
        lev = debt / total_assets
        altman = "LOW RISK" if lev < 0.5 else "MEDIUM" if lev < 0.75 else "HIGH RISK"
        
        # Beneish Proxy (Receivables)
        rec = balance.get('netReceivables', 0)
        beneish = "CONSERVATIVE" if (rec / total_assets) < 0.3 else "CHECK AUDIT"

        return {
            "symbol": income.get('symbol', ticker),
            "currency": income.get('reportedCurrency', 'N/A'),
            "metrics": {
                "ROE": roe,
                "Margin": margin,
                "OE": oe,
                "CD": cd_ratio,
                "FScore": f_score,
                "Altman": altman,
                "Beneish": beneish
            }
        }

    except Exception as e:
        return {"error": f"Errore Tecnico Imprevisto: {str(e)}"}

# --- UI ---
st.title("🏛️ Pure Data Terminal (No-Yahoo Edition)")
st.info("Questo terminale usa SOLO i bilanci grezzi di FMP. Non si blocca mai, ma richiede Ticker precisi.")

# INPUT MANUALE DI EMERGENZA
col_search, col_csv = st.columns([1, 2])

with col_search:
    st.subheader("🔍 Test Manuale")
    manual_ticker = st.text_input("Scrivi un Ticker (es. AAPL, ENI.MI, MC.PA):").upper()

with col_csv:
    st.subheader("📂 Da File CSV")
    try:
        df = pd.read_csv('lista_ticker.csv')
        # Cerca colonne
        col = next((c for c in df.columns if 'ick' in c or 'ymbo' in c), None)
        lista_t = df[col].dropna().unique().tolist() if col else []
    except:
        lista_t = []
    
    csv_ticker = st.selectbox("Seleziona dal file:", lista_t) if lista_t else None

# Logica di Selezione: Se scrivi a mano, usa quello. Altrimenti usa il menu.
ticker_to_use = manual_ticker if manual_ticker else csv_ticker

if API_KEY == "INSERISCI_LA_TUA_API_KEY_QUI":
    st.error("⛔ Devi inserire la API KEY nel codice alla riga 9!")
    st.stop()

if ticker_to_use:
    st.divider()
    st.write(f"Analisi in corso per: **{ticker_to_use}**...")
    
    data = fetch_pure_fmp_data(ticker_to_use)
    
    # GESTIONE ERRORI
    if "error" in data:
        st.error(f"❌ {data['error']}")
        st.warning("Se cerchi un'azione italiana, assicurati di aver scritto **.MI** alla fine (es. ENI.MI).")
        
        # DEBUGGER PER CAPIRE COSA SUCCEDE
        with st.expander("🕵️‍♂️ Vedi Risposta API Grezza (Debug)"):
            test_url = f"https://financialmodelingprep.com/api/v3/income-statement/{ticker_to_use}?period=annual&limit=1&apikey=TUAKEY"
            st.write(f"Ho chiamato questo URL: {test_url}")
            st.write("Se ricevi [], FMP non ha dati per questo ticker nel piano Free.")
            
    else:
        # VISUALIZZAZIONE DATI
        m = data["metrics"]
        st.header(f"📊 Dati Finanziari: {data['symbol']}")
        st.caption(f"Valuta Report: {data['currency']}")
        
        # 1. KPI
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("ROE (Equity)", f"{m['ROE']:.2f}%")
        c2.metric("PROFIT MARGIN", f"{m['Margin']:.2f}%")
        c3.metric("OWNER EARNINGS", f"{m['OE']/1e9:.2f}B")
        c4.metric("CASH / DEBT", f"{m['CD']:.2f}")

        st.write("---")
        
        # 2. RISCHIO
        cc1, cc2, cc3 = st.columns(3)
        cc1.metric("PIOTROSKI (Calc)", f"{m['FScore']}/9")
        cc2.metric("LEVA (Altman Proxy)", m['Altman'])
        cc3.metric("QUALITY (Beneish)", m['Beneish'])
        
        # 3. ANALISI
        st.success("✅ **Dati scaricati con successo.**")
        st.info("""
        **Nota:** Poiché non usiamo Yahoo Finance (per evitare blocchi) e FMP Free blocca i profili aziendali:
        1. Non vediamo il Nome completo o il Settore.
        2. Non possiamo calcolare il Dividend Yield % preciso (manca il prezzo real-time).
        Tutto il resto è calcolato matematicamente dai bilanci ufficiali.
        """)
























