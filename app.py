import streamlit as st
import pandas as pd
import requests

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Terminal Debugger", layout="wide")
st.title("🕵️‍♂️ FMP API Debugger")

# --- SIDEBAR: CONFIGURAZIONE ---
st.sidebar.header("Configurazione")
api_key = st.sidebar.text_input("Inserisci API Key FMP:", type="password")
ticker_input = st.sidebar.text_input("Inserisci Ticker (es. AAPL, ENI.MI):", value="AAPL")

# --- FUNZIONE DEBUG ---
def test_connection(ticker, key):
    if not key:
        st.error("Manca la API Key!")
        return

    base_url = "https://financialmodelingprep.com/api/v3"
    
    # 1. TEST PREZZO (Endpoint Quote - Solitamente aperto)
    st.subheader(f"Test 1: Ricerca Ticker '{ticker}'")
    url_quote = f"{base_url}/quote/{ticker}?apikey={key}"
    
    try:
        r = requests.get(url_quote)
        data = r.json()
        
        # Mostriamo cosa risponde ESATTAMENTE l'API
        st.write(f"📡 Status Code: {r.status_code}")
        st.write("📦 Risposta Grezza API:")
        st.json(data)

        if "Error Message" in str(data):
            st.error("⛔ ERRORE API: La chiave non è valida o hai usato endpoint bloccati.")
            return

        if not data:
            st.error(f"⛔ LISTA VUOTA: FMP non trova il ticker '{ticker}'.")
            st.info("💡 SUGGERIMENTI:")
            st.markdown("- Se è un'azione **italiana**, aggiungi **.MI** (es. `ENI.MI`, `ISP.MI`, `RACE.MI`)")
            st.markdown("- Se è **francese**, aggiungi **.PA** (es. `MC.PA`)")
            st.markdown("- Se è **inglese**, aggiungi **.L**")
            return

        # Se siamo qui, il Ticker esiste!
        price = data[0].get('price', 0)
        name = data[0].get('name', 'N/A')
        st.success(f"✅ Trovato: **{name}** a **${price}**")
        
        # 2. TEST BILANCIO (Income Statement)
        st.subheader("Test 2: Scarico Bilancio")
        url_inc = f"{base_url}/income-statement/{ticker}?period=annual&limit=1&apikey={key}"
        r_inc = requests.get(url_inc)
        data_inc = r_inc.json()
        
        if not data_inc:
            st.warning("⚠️ Bilancio non disponibile (forse ETF o fondo senza income statement standard).")
        else:
            inc = data_inc[0]
            rev = inc.get('revenue', 0)
            ni = inc.get('netIncome', 0)
            st.success(f"✅ Bilancio OK. Fatturato: ${rev:,.0f} | Utile: ${ni:,.0f}")
            
            # Calcolo ROE al volo per dimostrazione
            st.info(f"Test Calcolo: Margin = {(ni/rev)*100:.2f}%")

    except Exception as e:
        st.error(f"Errore Tecnico imprevisto: {e}")

# --- ESECUZIONE ---
if st.button("LANCIA DIAGNOSI"):
    test_connection(ticker_input, api_key)























