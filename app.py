import streamlit as st
import pandas as pd
import requests

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="DEBUG Equity Terminal", layout="wide")
st.title("🛠️ DIAGNOSTICA TERMINAL")

# --- 1. INSERIMENTO API KEY (Diretto, per testare) ---
st.sidebar.header("1. Configurazione")
api_key_input = st.sidebar.text_input("Incolla qui la tua API Key FMP:", type="password")

# --- 2. CARICAMENTO CSV (Con controllo errori) ---
st.subheader("Step 1: Controllo Lista Ticker")
try:
    df = pd.read_csv('lista_ticker.csv')
    st.write("File CSV letto correttamente. Ecco le prime righe:")
    st.dataframe(df.head(3))
    
    # Cerchiamo la colonna giusta
    possible_cols = ['Ticker', 'ticker', 'Symbol', 'symbol', 'Simbolo']
    col_name = next((c for c in possible_cols if c in df.columns), None)
    
    if col_name:
        lista_t = df[col_name].dropna().unique().tolist()
        st.success(f"✅ Trovati {len(lista_t)} ticker nella colonna '{col_name}'.")
    else:
        st.error("❌ Errore CSV: Non trovo una colonna chiamata 'Ticker', 'Symbol' o 'Simbolo'. Rinomina la colonna nel tuo file Excel/CSV.")
        lista_t = ["AAPL", "NVDA", "TSLA"] # Fallback
except Exception as e:
    st.error(f"❌ Errore lettura file CSV: {e}")
    st.info("Sto usando una lista di default per testare.")
    lista_t = ["AAPL", "NVDA", "TSLA"]

# --- 3. TEST CONNESSIONE API ---
st.subheader("Step 2: Test Connessione Dati")
tk_sel = st.sidebar.selectbox("Seleziona Asset:", lista_t)

if st.button("Lancia Analisi") or tk_sel:
    if not api_key_input:
        st.warning("⚠️ Inserisci la API Key nella barra laterale a sinistra!")
        st.stop()

    st.write(f"Tentativo di connessione per: **{tk_sel}**...")
    
    # URL DI TEST (Profilo Aziendale)
    url = f"https://financialmodelingprep.com/api/v3/profile/{tk_sel}?apikey={api_key_input}"
    
    try:
        response = requests.get(url)
        data = response.json()
        
        # --- DEBUG VISIVO ---
        if "Error Message" in data:
             st.error(f"⛔ Errore API FMP: {data['Error Message']}")
             st.info("Suggerimento: La tua chiave potrebbe essere errata o hai superato i limiti gratuiti.")
        
        elif not data:
            st.error("⛔ Dati Vuoti. Il Ticker potrebbe essere errato per FMP.")
            st.info(f"Se è un'azione italiana, prova ad aggiungere .MI (es. {tk_sel}.MI)")
            
        else:
            profile = data[0]
            st.success("✅ CONNESSIONE RIUSCITA!")
            
            # --- VISUALIZZAZIONE DATI ---
            st.markdown(f"### {profile['companyName']} ({profile['symbol']})")
            st.metric("Prezzo Attuale", f"${profile['price']}")
            st.metric("Settore", profile['sector'])
            
            # Recupero Key Metrics (ROE, ecc)
            metrics_url = f"https://financialmodelingprep.com/api/v3/key-metrics-ttm/{tk_sel}?apikey={api_key_input}"
            m_data = requests.get(metrics_url).json()
            
            if m_data:
                m = m_data[0]
                st.write("---")
                c1, c2, c3 = st.columns(3)
                c1.metric("ROE", f"{m.get('roeTTM', 0)*100:.2f}%")
                c2.metric("Profit Margin", f"{m.get('netProfitMarginTTM', 0)*100:.2f}%")
                c3.metric("Div Yield", f"{m.get('dividendYieldPercentageTTM', 0):.2f}%")
                
                # Calcolo Owner Earnings (Semplificato)
                st.write("---")
                st.info("Calcolo Owner Earnings in corso...")
                cf_url = f"https://financialmodelingprep.com/api/v3/cash-flow-statement/{tk_sel}?limit=1&apikey={api_key_input}"
                cf_data = requests.get(cf_url).json()
                
                if cf_data:
                    cf = cf_data[0]
                    ni = cf.get('netIncome', 0)
                    dep = cf.get('depreciationAndAmortization', 0)
                    capex = abs(cf.get('capitalExpenditure', 0))
                    oe = ni + dep - capex
                    
                    st.metric("OWNER EARNINGS (Buffett)", f"${oe/1e9:.2f}B")
                else:
                    st.warning("Dati Cash Flow non disponibili per questo ticker.")
            else:
                st.warning("Metriche avanzate non disponibili (forse ticker troppo piccolo o ETF).")

    except Exception as e:
        st.error(f"Errore Tecnico: {e}")






















