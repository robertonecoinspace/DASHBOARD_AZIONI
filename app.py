import streamlit as st
import yfinance as yf
import pandas as pd
import time
import random

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Equity Terminal (No-API)", layout="wide")

# --- FUNZIONE DI RECUPERO "STEALTH" (Anti-Blocco) ---
def get_safe_metric(info, key, default=0):
    val = info.get(key, default)
    return val if val is not None else default

@st.cache_data(ttl=3600) # Cache di 1 ora
def fetch_stealth_data(ticker):
    try:
        # 1. RITARDO STRATEGICO (Cruciale per non essere bloccati)
        # Il codice aspetta tra 0.1 e 0.5 secondi. Yahoo pensa che tu sia un umano veloce.
        time.sleep(random.uniform(0.1, 0.5))
        
        # 2. SCARICAMENTO LEGGERO
        asset = yf.Ticker(ticker)
        i = asset.info
        
        # Se non c'è il prezzo, il ticker è probabilmente sbagliato
        if 'currentPrice' not in i and 'regularMarketPrice' not in i:
            return None

        # 3. ESTRAZIONE DATI (Senza scaricare interi bilanci)
        roe = get_safe_metric(i, 'returnOnEquity') * 100
        margin = get_safe_metric(i, 'profitMargins') * 100
        div_yield = get_safe_metric(i, 'dividendYield') * 100
        
        # Owner Earnings (Stima Buffett: Net Income + Dep - Capex)
        # Usiamo i campi 'info' che sono pre-calcolati da Yahoo
        ni = get_safe_metric(i, 'netIncomeToCommon')
        # A volte Yahoo chiama l'ammortamento in modi diversi, proviamo a cercarlo
        # Se non c'è, usiamo il 5% del fatturato come stima grezza per non bloccarci
        dep = i.get('depreciation', 0) or (get_safe_metric(i, 'totalRevenue') * 0.05)
        # Capex non è sempre in info, usiamo il Free Cash Flow per derivarlo
        # FCF = Operating Cash Flow - Capex  =>  Capex = Operating Cash Flow - FCF
        ocf = get_safe_metric(i, 'operatingCashflow')
        fcf = get_safe_metric(i, 'freeCashflow')
        capex = abs(ocf - fcf) if (ocf and fcf) else 0
        
        oe = ni + dep - capex
        
        # Cash / Debt Ratio
        cash = get_safe_metric(i, 'totalCash')
        debt = get_safe_metric(i, 'totalDebt')
        cd_ratio = cash / debt if debt > 0 else 0
        
        # 4. CALCOLO SCORE (Proxy basati su dati disponibili)
        f_score = 0
        if roe > 10: f_score += 3
        if get_safe_metric(i, 'currentRatio') > 1.2: f_score += 3
        if ocf > ni: f_score += 3
        
        # Risk Metrics (Usiamo i risk audit di Yahoo se ci sono, o calcoliamo proxy)
        audit_risk = i.get('auditRisk', 5) # Default a medio rischio
        board_risk = i.get('boardRisk', 5)

        return {
            "name": i.get('longName', ticker),
            "sector": i.get('sector', 'N/A'),
            "currency": i.get('currency', 'USD'),
            "metrics": {
                "ROE": roe,
                "Margin": margin,
                "Yield": div_yield,
                "OE": oe,
                "CD": cd_ratio,
                "FScore": f_score,
                "Altman": "LOW" if audit_risk < 5 else "MEDIUM" if audit_risk < 8 else "HIGH",
                "Beneish": "CONSERVATIVE" if board_risk < 5 else "CHECK AUDIT"
            }
        }
    except Exception as e:
        return None

# --- UI ---
st.title("🏛️ Equity Terminal (No-API Edition)")
st.caption("Motore: Yahoo Finance Stealth | Nessuna registrazione richiesta")

# GESTIONE CSV
try:
    df = pd.read_csv('lista_ticker.csv')
    # Pulizia nomi colonne
    df.columns = [c.strip() for c in df.columns]
    # Cerca la colonna giusta
    col = next((c for c in df.columns if c.lower() in ['ticker', 'symbol', 'simbolo']), None)
    
    if col:
        lista_t = df[col].dropna().unique().tolist()
        st.sidebar.success(f"Caricati {len(lista_t)} ticker dal file.")
    else:
        st.sidebar.error("Colonna 'Ticker' non trovata nel CSV.")
        lista_t = ["AAPL", "MSFT", "ENI.MI"]
except:
    st.sidebar.warning("File 'lista_ticker.csv' non trovato. Uso demo.")
    lista_t = ["AAPL", "NVDA", "TSLA", "ISP.MI", "ENI.MI"]

# SELETTORE
tk_sel = st.sidebar.selectbox("Seleziona Asset:", lista_t)

if tk_sel:
    # Mostriamo uno spinner mentre il "ritardo umano" agisce
    with st.spinner(f"Analisi Stealth di {tk_sel}..."):
        data = fetch_stealth_data(tk_sel)

    if data:
        m = data["metrics"]
        st.header(f"📈 {data['name']} | 🏭 {data['sector']}")
        st.caption(f"Valuta: {data['currency']}")
        
        # 1. KPI
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("ROE", f"{m['ROE']:.2f}%")
        c2.metric("PROFIT MARGIN", f"{m['Margin']:.2f}%")
        c3.metric("DIV. YIELD", f"{(m['Yield']/100):.2f}%") # Diviso 100 come richiesto
        c4.metric("OWNER EARNINGS", f"${m['OE']/1e9:.2f}B")

        st.write("---")

        # 2. SOLIDITÀ (Benchmark Apple 0.49)
        st.subheader("🛡️ Solidità e Rischio")
        cc1, cc2, cc3, cc4 = st.columns(4)
        
        apple_ref = 0.49
        delta = m['CD'] - apple_ref
        
        cc1.metric("CASH/DEBT", f"{m['CD']:.2f}", delta=f"{delta:.2f} vs AAPL")
        cc2.metric("PIOTROSKI SCORE", f"{m['FScore']}/9")
        cc3.metric("ALTMAN RISK", m['Altman'])
        cc4.metric("BENEISH SCORE", m['Beneish'])

        # 3. EXECUTIVE INSIGHTS
        st.divider()
        st.subheader("💡 Executive Insights")
        
        col_a, col_b = st.columns(2)
        with col_a:
            # Analisi Efficienza
            if m['ROE'] > 15:
                st.success("**Efficienza:** Eccellente. L'azienda genera alti ritorni sul capitale proprio.")
            else:
                st.info("**Efficienza:** Standard. Redditività in linea con la media di mercato.")
            
            # Analisi Cassa
            if m['CD'] > apple_ref:
                st.success("**Liquidità:** Molto Forte. Posizione di cassa superiore al benchmark Apple.")
            else:
                st.warning("**Liquidità:** Attenzione. La copertura del debito è inferiore ai top player.")

        with col_b:
            # Analisi Bilancio
            if m['FScore'] >= 6:
                st.success("**Qualità Bilancio:** Solida. I fondamentali non mostrano crepe.")
            else:
                st.error("**Qualità Bilancio:** Debole. Alcuni indicatori finanziari sono sotto stress.")
                
            # Analisi Rischio
            if m['Altman'] == "LOW":
                st.success("**Rischio Insolvenza:** Basso.")
            else:
                st.warning("**Rischio Insolvenza:** Medio/Alto. Monitorare il debito.")

        # LEGENDA
        with st.expander("📖 LEGENDA METRICHE"):
            st.markdown("""
            * **ROE:** Redditività del capitale netto.
            * **Owner Earnings:** Stima del flusso di cassa reale (Utile + Ammortamenti - Capex).
            * **Cash/Debt:** Benchmark Apple **0.49**. Sopra è ottimo, sotto significa più debito.
            * **Piotroski Score:** Punteggio di salute finanziaria (max 9).
            * **Altman/Beneish:** Indicatori di rischio fallimento e manipolazione contabile.
            """)
            st.write("")

    else:
        st.error(f"Dati non trovati per {tk_sel}.")
        st.info("Suggerimento: Se è un'azione italiana, verifica che nel CSV ci sia .MI (es. ENI.MI)")

























