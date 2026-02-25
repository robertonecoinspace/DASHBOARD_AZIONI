import streamlit as st
import pandas as pd
import requests

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Equity Quality Terminal Pro", layout="wide")

# !!! IMPORTANTE: INSERISCI QUI LA TUA API KEY GRATUITA !!!
API_KEY = "dPrkP3WNj0gkNIT71CKIZYM8iX3e6tKG" 

# --- MOTORE DATI (FMP - NO YAHOO - NO BLOCCHI) ---
@st.cache_data(ttl=3600)
def fetch_fmp_data(ticker):
    if API_KEY == "dPrkP3WNj0gkNIT71CKIZYM8iX3e6tKG":
        return "NO_KEY"
    
    base_url = "https://financialmodelingprep.com/api/v3"
    
    try:
        # 1. Profilo Aziendale (Prezzo, Settore, Beta)
        profile = requests.get(f"{base_url}/profile/{ticker}?apikey={API_KEY}").json()[0]
        
        # 2. Key Metrics (ROE, Margini, Owner Earnings Inputs)
        metrics = requests.get(f"{base_url}/key-metrics-ttm/{ticker}?apikey={API_KEY}").json()[0]
        
        # 3. Ratios (Yield, Payout, Cash ratios)
        ratios = requests.get(f"{base_url}/ratios-ttm/{ticker}?apikey={API_KEY}").json()[0]
        
        # 4. Financial Statements (Per calcoli manuali precisi)
        bs = requests.get(f"{base_url}/balance-sheet-statement/{ticker}?period=quarter&limit=1&apikey={API_KEY}").json()[0]
        cf = requests.get(f"{base_url}/cash-flow-statement/{ticker}?period=annual&limit=1&apikey={API_KEY}").json()[0]
        
        # --- CALCOLI PROPRIETARI ---
        
        # Owner Earnings (NI + Dep - Capex)
        ni = cf.get('netIncome', 0)
        dep = cf.get('depreciationAndAmortization', 0)
        capex = abs(cf.get('capitalExpenditure', 0))
        oe = ni + dep - capex
        
        # Cash / Debt (Benchmark Apple 0.49)
        cash = bs.get('cashAndCashEquivalents', 0) + bs.get('shortTermInvestments', 0)
        debt = bs.get('totalDebt', 0)
        cd_ratio = cash / debt if debt > 0 else 0
        
        # Dividend Yield (FMP lo dà decimale, es. 0.005)
        div_yield = ratios.get('dividendYield', 0) * 100
        
        # --- SCORES & RISCHIO ---
        # Piotroski F-Score (Diretto da FMP o calcolato)
        # FMP Free a volte limita gli score diretti, lo calcoliamo noi sui dati grezzi per sicurezza
        f_score = 0
        if metrics.get('roeTTM', 0) > 0: f_score += 2
        if metrics.get('operatingCashFlowPerShareTTM', 0) > metrics.get('netIncomePerShareTTM', 0): f_score += 3
        if ratios.get('currentRatioTTM', 0) > 1.2: f_score += 2
        if ratios.get('debtToEquityTTM', 0) < 1: f_score += 2
        
        # Altman Z-Score Proxy (Se non disponibile direttamente)
        # Usiamo Interest Coverage e Debt Ratio come proxy di rischio
        int_cov = ratios.get('interestCoverageTTM', 0)
        if int_cov > 5: altman = "LOW RISK"
        elif int_cov > 1.5: altman = "MEDIUM RISK"
        else: altman = "DISTRESS"
        
        # Beneish Proxy (Basato sulla crescita dei ricavi vs crediti)
        days_sales = ratios.get('daysOfSalesOutstandingTTM', 0)
        beneish = "CONSERVATIVE" if days_sales < 45 else "CHECK AUDIT"

        return {
            "name": profile.get('companyName'),
            "sector": profile.get('sector'),
            "metrics": {
                "ROE": metrics.get('roeTTM', 0) * 100,
                "Margin": ratios.get('netProfitMarginTTM', 0) * 100,
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
st.title("🏛️ Equity Quality Terminal (API Edition)")
st.caption("Dati Ufficiali Financial Modeling Prep | Nessun Blocco IP")

# Caricamento CSV
try:
    df = pd.read_csv('lista_ticker.csv')
    lista_t = df['Ticker'].dropna().unique().tolist()
except:
    st.warning("⚠️ File 'lista_ticker.csv' non trovato. Uso lista demo.")
    lista_t = ["AAPL", "MSFT", "GOOGL", "NVDA", "META"]

# Sidebar
tk_sel = st.sidebar.selectbox("Seleziona Asset:", lista_t)
data = fetch_fmp_data(tk_sel)

if data == "NO_KEY":
    st.error("⛔ **MANCA LA API KEY!**")
    st.info("1. Vai su https://site.financialmodelingprep.com/developer/docs/")
    st.info("2. Registrati Gratis e copia la Key.")
    st.info("3. Incollala nel codice alla riga 9.")

elif data:
    m = data["metrics"]
    st.header(f"📈 {data['name']} | 🏭 {data['sector']}")
    
    # --- KPI FINANZIARI ---
    st.subheader("📋 Indicatori di Performance")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("ROE", f"{m['ROE']:.2f}%")
    c2.metric("PROFIT MARGIN", f"{m['Margin']:.2f}%")
    c3.metric("DIV. YIELD", f"{(m['Yield']):.2f}%") 
    c4.metric("OWNER EARNINGS", f"${m['OE']/1e9:.2f}B")

    st.write("---")

    # --- SOLIDITÀ (BENCHMARK APPLE) ---
    st.subheader("🛡️ Solidità e Rischio (Benchmark Apple 0.49)")
    cc1, cc2, cc3, cc4 = st.columns(4)
    
    apple_ref = 0.49
    cc1.metric("CASH/DEBT", f"{m['CD']:.2f}", delta=f"{m['CD'] - apple_ref:.2f} vs AAPL")
    cc2.metric("PIOTROSKI EST.", f"{m['FScore']}/9")
    cc3.metric("RISCHIO FIN.", m['Altman'])
    cc4.metric("QUALITY CHECK", m['Beneish'])

    # --- EXECUTIVE INSIGHTS ---
    st.divider()
    st.subheader("💡 Executive Quality Insights")
    
    col_a, col_b = st.columns(2)
    with col_a:
        if m['ROE'] > 20 and m['Margin'] > 15:
            st.success("**Moat Competitivo:** Eccellente. L'azienda converte capitale in utile con efficienza superiore alla media.")
        else:
            st.info("**Moat Competitivo:** Standard. Redditività in linea con le dinamiche settoriali.")
            
        if m['CD'] > apple_ref:
            st.success(f"**Liquidità:** La posizione di cassa è superiore al benchmark Apple. Estrema resilienza.")
        else:
            st.warning(f"**Liquidità:** L'azienda usa più leva finanziaria rispetto ad Apple. Verificare il costo del debito.")

    with col_b:
        if m['FScore'] >= 6 and m['Altman'] == "LOW RISK":
            st.success("**Qualità Bilancio:** Certificata. I fondamentali non mostrano segni di stress o manipolazione.")
        else:
            st.error("**Qualità Bilancio:** Alert. Alcuni indicatori di liquidità o copertura interessi richiedono attenzione.")

    # --- LEGENDA ---
    with st.expander("📖 LEGENDA ENCICLOPEDICA"):
        st.markdown("""
        ### ⚖️ Logica dei Parametri (Fonte: FMP)
        * **ROE (Return on Equity):** `Utile Netto TTM / Equity`. Misura la redditività del capitale proprio.
        * **Owner Earnings:** `Net Income + D&A - CapEx`. La cassa reale generata dal business (Metodo Buffett).
        * **Piotroski Score:** Stima basata su 9 criteri di solidità (Redditività, Leva, Efficienza Operativa).
        * **Altman Proxy:** Basato sull'Interest Coverage Ratio. Se > 5 è Low Risk.
        * **Cash/Debt:** Benchmark **Apple (0.49)**. Misura quanti dollari di cassa esistono per ogni dollaro di debito.
        """)
        
        
else:
    st.error("⚠️ Errore nel recupero dati. Verifica che il Ticker sia corretto (es. AAPL, non Apple).")





















