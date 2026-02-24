import streamlit as st
import yfinance as yf
import pandas as pd
import requests

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Equity Quality Terminal v3", layout="wide")

# Funzione per simulare un browser reale ed evitare i blocchi
def get_session():
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
    })
    return session

# --- CORE ENGINE: ANALISI DI BILANCIO ---
@st.cache_data(ttl=86400)
def fetch_certified_quality(ticker):
    try:
        session = get_session()
        asset = yf.Ticker(ticker, session=session)
        i = asset.info
        
        if not i or 'currentPrice' not in i:
            return None

        # 1. Indicatori di Bilancio (ROE, Margini, Div)
        roe = i.get('returnOnEquity', 0) * 100
        margin = i.get('profitMargins', 0) * 100
        div_yield = i.get('dividendYield', 0) * 100
        
        # 2. Owner Earnings (Buffett: NI + D&A - CapEx)
        ni = i.get('netIncomeToCommon', 0)
        da = i.get('depreciation', 0)
        capex = abs(i.get('capitalExpenditure', 0))
        oe = ni + da - capex
        
        # 3. Solidità Cash/Debt (Benchmark Apple 0.49)
        cash = i.get('totalCash', 0)
        debt = i.get('totalDebt', 0)
        cd_ratio = cash / debt if debt > 0 else 0
        
        # 4. Scores e Rischio (Analisi Multidimensionale)
        f_score = 0
        if roe > 15: f_score += 3
        if i.get('currentRatio', 0) > 1.5: f_score += 3
        if i.get('operatingCashflow', 0) > ni: f_score += 3
        
        altman_risk = i.get('auditRisk', 5)
        beneish_risk = i.get('boardRisk', 5)

        return {
            "name": i.get('longName', ticker),
            "sector": i.get('sector', 'N/A'),
            "oe": oe,
            "f_score": f_score,
            "altman": "LOW" if altman_risk < 4 else "MEDIUM" if altman_risk < 7 else "HIGH",
            "beneish": "CONSERVATIVE" if beneish_risk < 5 else "CHECK AUDIT",
            "metrics": {
                "ROE": roe,
                "Margin": margin,
                "Yield": div_yield,
                "CD": cd_ratio
            }
        }
    except:
        return None

# --- UI ---
st.title("🏛️ Equity Quality Terminal Pro")
st.caption("Certificazione Bilanci | Benchmark Apple Cash/Debt: 0.49")

# Caricamento Ticker dal file CSV
try:
    lista_t = pd.read_csv('lista_ticker.csv')['Ticker'].dropna().unique().tolist()
except:
    st.warning("⚠️ File 'lista_ticker.csv' non trovato. Caricamento ticker di default.")
    lista_t = ["AAPL", "MSFT", "GOOGL", "NVDA", "BRK-B", "TSLA"]

tk_sel = st.sidebar.selectbox("Seleziona Asset dal CSV:", lista_t)
asset_data = fetch_certified_quality(tk_sel)

if asset_data:
    m = asset_data["metrics"]
    st.header(f"📈 {asset_data['name']} | 🏭 {asset_data['sector']}")
    
    # --- PERFORMANCE & PROFITTI ---
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("ROE", f"{m['ROE']:.2f}%")
    c2.metric("PROFIT MARGIN", f"{m['Margin']:.2f}%")
    # Dividend Yield diviso 100 come richiesto
    c3.metric("DIV. YIELD", f"{(m['Yield']/100):.2f}%")
    c4.metric("OWNER EARNINGS", f"${asset_data['oe']/1e9:.2f}B")

    st.write("---")

    # --- SOLIDITÀ & RISCHIO ---
    st.subheader("🛡️ Analisi del Rischio e Solidità")
    cc1, cc2, cc3, cc4 = st.columns(4)
    
    apple_ref = 0.49
    delta_a = m['CD'] - apple_ref
    
    cc1.metric("CASH/DEBT (ANN)", f"{m['CD']:.2f}", delta=f"{delta_a:.2f} vs AAPL")
    cc2.metric("PIOTROSKI SCORE", f"{asset_data['f_score']}/9")
    cc3.metric("ALTMAN RISK", asset_data['altman'])
    cc4.metric("BENEISH SCORE", asset_data['beneish'])

    # --- EXECUTIVE INSIGHTS ANALYZER ---
    st.divider()
    st.subheader("💡 Executive Quality Insights")
    
    col_a, col_b = st.columns(2)
    with col_a:
        if m['ROE'] > 20 and m['Margin'] > 15:
            st.success("**Efficienza Operativa:** Eccellente. L'azienda genera extra-profitti consistenti rispetto al capitale investito.")
        else:
            st.info("**Efficienza Operativa:** Rendimento standard. L'azienda non mostra un vantaggio competitivo (Moat) dirompente.")
            
        if m['CD'] > apple_ref:
            st.success(f"**Solidità Finanziaria:** Struttura di cassa superiore al benchmark Apple ({apple_ref}). Sicurezza finanziaria ai vertici.")
        else:
            st.warning("**Solidità Finanziaria:** Copertura debito inferiore ad Apple. Verificare l'esposizione a tassi variabili.")

    with col_b:
        if asset_data['f_score'] >= 6 and asset_data['altman'] == "LOW":
            st.success("**Verdetto Rischio:** Bilancio Solido. Non si rilevano criticità contabili o pericoli di insolvenza immediati.")
        else:
            st.error("**Verdetto Rischio:** Allerta. Gli indicatori suggeriscono di analizzare meglio la qualità dei crediti o la gestione del debito.")

    # --- LEGENDA ---
    with st.expander("📖 LEGENDA LOGICA E MATEMATICA"):
        st.markdown("""
        ### ⚖️ Spiegazione Parametri
        - **ROE:** `Utile Netto / Capitale Proprio`. Efficienza del management nell'uso dei soldi degli azionisti.
        - **Owner Earnings:** `Utile Netto + Ammortamenti - CapEx`. Cash flow reale "alla Buffett".
        - **Piotroski Score:** Valutazione della salute finanziaria su 9 punti (Profitto, Leva, Liquidità).
        - **Altman Z-Score:** Predice la stabilità finanziaria a 2 anni.
        - **Beneish M-Score:** Verifica probabile manipolazione degli utili.
        - **Cash/Debt:** Capacità di estinzione del debito con cassa pronta. **Apple (0.49)** è il nostro Gold Standard.
        """)
        
else:
    st.error("⚠️ Errore di connessione. Se il problema persiste, Yahoo ha bloccato l'IP del server. Prova a riavviare l'app o seleziona un ticker differente.")




















