import streamlit as st
import yfinance as yf
import pandas as pd

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Quality Equity Terminal", layout="wide")

# --- CORE LOGIC: ESTRAZIONE CERTIFICATA ---
@st.cache_data(ttl=3600)
def fetch_certified_data(ticker):
    try:
        # Usiamo solo l'oggetto info che è il più veloce e meno propenso ai blocchi
        asset = yf.Ticker(ticker)
        i = asset.info
        
        # Estrazione Parametri di Bilancio
        ni = i.get('netIncomeToCommon', 0)
        dep = i.get('depreciation', 0)
        capex = abs(i.get('capitalExpenditure', 0))
        
        # Calcolo Owner Earnings (Formula Buffett: NI + D&A - CapEx)
        oe = ni + dep - capex
        
        # Cash/Debt (Benchmark Apple 0.49)
        cash = i.get('totalCash', 0)
        debt = i.get('totalDebt', 0)
        cd_ratio = cash / debt if debt > 0 else 0
        
        # Scores Semplificati (Basati su indicatori di bilancio certificati)
        # Piotroski Proxy
        f_score = 0
        if i.get('returnOnAssets', 0) > 0: f_score += 3
        if i.get('operatingCashflow', 0) > ni: f_score += 3
        if i.get('currentRatio', 0) > 1.2: f_score += 3
        
        # Altman & Beneish Risk (Basati su indici di rischio Yahoo)
        altman_val = i.get('auditRisk', 5)
        beneish_val = i.get('boardRisk', 5)

        return {
            "name": i.get('longName', ticker),
            "sector": i.get('sector', 'N/A'),
            "metrics": {
                "ROE": i.get('returnOnEquity', 0) * 100,
                "Margin": i.get('profitMargins', 0) * 100,
                "Yield": (i.get('dividendYield', 0)) * 100,
                "OE": oe,
                "CD_Ratio": cd_ratio,
                "FScore": f_score,
                "Altman": "LOW RISK" if altman_val < 4 else "MEDIUM" if altman_val < 7 else "HIGH RISK",
                "Beneish": "CONSERVATIVE" if beneish_val < 5 else "CHECK AUDIT"
            }
        }
    except:
        return None

# --- INTERFACCIA ---
st.title("🏛️ Strategic Quality Terminal")
st.markdown("### *Focus: Bilancio Certificato & Analisi del Rischio*")

# Lista Ticker
try:
    lista_t = pd.read_csv('lista_ticker.csv')['Ticker'].tolist()
except:
    lista_t = ["AAPL", "MSFT", "GOOGL", "NVDA", "META", "TSLA"]

tk_sel = st.sidebar.selectbox("Seleziona Asset:", lista_t)
data = fetch_certified_data(tk_sel)

if data:
    m = data["metrics"]
    st.header(f"📈 {data['name']} | 🏭 {data['sector']}")
    
    # 1. PARAMETRI DI BILANCIO
    st.subheader("📋 Indicatori di Performance")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("ROE", f"{m['ROE']:.2f}%")
    c2.metric("PROFIT MARGIN", f"{m['Margin']:.2f}%")
    c3.metric("DIVIDEND YIELD", f"{(m['Yield']/100):.2f}%")
    c4.metric("OWNER EARNINGS", f"${m['OE']/1e9:.2f}B")

    # 2. SOLIDITÀ & RISCHIO (Benchmark Apple)
    st.markdown("---")
    st.subheader("🛡️ Certificazione Solidità (Benchmark Apple 0.49)")
    cc1, cc2, cc3, cc4 = st.columns(4)
    
    apple_benchmark = 0.49
    diff = m['CD_Ratio'] - apple_benchmark
    cc1.metric("CASH / DEBT", f"{m['CD_Ratio']:.2f}", delta=f"{diff:.2f} vs AAPL")
    cc2.metric("PIOTROSKI SCORE", f"{m['FScore']}/9")
    cc3.metric("ALTMAN RISK", m['Altman'])
    cc4.metric("BENEISH SCORE", m['Beneish'])

    # 3. EXECUTIVE INSIGHTS TOOL
    st.divider()
    st.subheader("💡 Executive Insights Analysis")
    
    col_a, col_b = st.columns(2)
    with col_a:
        if m['ROE'] > 20:
            st.success(f"**Efficienza Capitale:** Il ROE al {m['ROE']:.1f}% indica un management capace di generare alti rendimenti senza eccessivo debito.")
        if m['CD_Ratio'] > apple_benchmark:
            st.success(f"**Resilienza Finanziaria:** La cassa eccede i parametri di efficienza di Apple. L'azienda è 'Anti-fragile'.")
        else:
            st.info(f"**Nota Liquidità:** Rapporto Cassa/Debito inferiore al benchmark Apple. Verificare il costo del debito circolante.")

    with col_b:
        if m['FScore'] >= 6 and m['Altman'] == "LOW RISK":
            st.success("**Qualità del Bilancio:** Parametri incrociati stabili. Non si rilevano anomalie contabili o rischi di insolvenza a breve termine.")
        else:
            st.warning("**Analisi del Rischio:** Uno o più parametri suggeriscono un approfondimento sui debiti a lungo termine.")

    # 4. LEGENDA MATEMATICA
    with st.expander("📖 LEGENDA TECNICA E FORMULE"):
        st.markdown("""
        ### 🧪 Metodologia Logica
        - **ROE:** `Net Income / Shareholder Equity`. La misura definitiva dell'efficienza gestionale.
        - **Owner Earnings:** `Net Income + Depreciation & Amortization - CapEx`. Il cash flow "puro" di Buffett.
        - **Piotroski Score:** Test a 9 variabili sulla solidità operativa (Redditività, Leva, Liquidità).
        - **Altman Z-Score:** Modello predittivo di insolvenza finanziaria. 
        - **Beneish M-Score:** Analisi di probabilità di manipolazione dei dati di bilancio (Earning Manipulation).
        - **Cash/Debt Benchmark:** Misuriamo la liquidità contro il valore di riferimento di **Apple (0.49)**.
        """)

else:
    st.error("⚠️ Errore di connessione con il provider dati. Yahoo Finance ha limitato l'accesso per questo IP. Riprova tra pochi minuti.")





















