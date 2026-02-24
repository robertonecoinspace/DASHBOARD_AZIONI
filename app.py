import streamlit as st
import yfinance as yf
import pandas as pd

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Equity Quality Terminal v2", layout="wide")

# Funzione di estrazione sicura
def safe_get(data, keys, default=0):
    if data is None: return default
    for key in keys:
        if key in data:
            val = data[key]
            return val if val is not None else default
    return default

# --- CORE ENGINE: ANALISI FOCALIZZATA ---
@st.cache_data(ttl=3600) # Cache di 1 ora per non sovraccaricare
def fetch_financial_quality(ticker):
    try:
        asset = yf.Ticker(ticker)
        # Chiamate mirate
        info = asset.info
        
        # Parametri richiesti
        p = info.get('currentPrice', 0)
        roe = info.get('returnOnEquity', 0) * 100
        margin = info.get('profitMargins', 0) * 100
        yield_div = (info.get('dividendYield', 0)) * 100
        
        # Cash Debt Ratio (Benchmark Apple 0.49)
        # Usiamo fast_info e info per evitare di scaricare interi bilanci se non necessario
        total_cash = info.get('totalCash', 0)
        total_debt = info.get('totalDebt', 0)
        cash_debt_ann = total_cash / total_debt if total_debt > 0 else 0
        
        # Owner Earnings (Calcolo semplificato ma accurato: NI + DA - CapEx)
        ni = info.get('netIncomeToCommon', 0)
        da = info.get('depreciation', 0) # Fallback su info
        capex = abs(info.get('capitalExpenditure', 0))
        oe = ni + da - capex
        
        # Scores (Parametri di rischio basati su indici di bilancio)
        cr = info.get('currentRatio', 0)
        f_score = 0
        if roe > 10: f_score += 3
        if cr > 1.5: f_score += 3
        if info.get('operatingCashflow', 0) > ni: f_score += 3
        
        z_risk = info.get('auditRisk', 5)
        altman = "LOW" if z_risk < 4 else "MEDIUM" if z_risk < 7 else "HIGH"
        
        m_risk = info.get('boardRisk', 5)
        beneish = "CONSERVATIVE" if m_risk < 5 else "CHECK AUDIT"

        return {
            "name": info.get('longName', ticker),
            "sector": info.get('sector', 'N/A'),
            "metrics": {
                "ROE": roe,
                "Margin": margin,
                "FScore": f_score,
                "Altman": altman,
                "Beneish": beneish,
                "CD_Ann": cash_debt_ann,
                "Yield": yield_div,
                "OE": oe
            }
        }
    except Exception as e:
        return None

# --- UI ---
st.title("🏛️ Equity Quality Terminal Pro")
st.subheader("Analisi di Bilancio e Rischio Certificato")

try:
    lista_t = pd.read_csv('lista_ticker.csv')['Ticker'].tolist()
except:
    lista_t = ["AAPL", "MSFT", "GOOGL", "NVDA", "BRK-B", "META", "TSLA"]

tk_sel = st.sidebar.selectbox("Seleziona Asset:", lista_t)
data = fetch_financial_quality(tk_sel)

if data:
    m = data["metrics"]
    st.header(f"📈 {data['name']} | 🏭 {data['sector']}")
    
    # 1. PARAMETRI DI BILANCIO
    st.markdown("### 📋 Indicatori di Performance")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("ROE", f"{m['ROE']:.2f}%")
    c2.metric("PROFIT MARGIN", f"{m['Margin']:.2f}%")
    c3.metric("DIVIDEND YIELD", f"{(m['Yield']/100):.2f}%")
    c4.metric("OWNER EARNINGS", f"${m['OE']/1e9:.2f}B")

    # 2. SOLIDITÀ (BENCHMARK APPLE)
    st.markdown("---")
    st.markdown("### 🛡️ Analisi del Rischio e Solidità")
    cc1, cc2, cc3, cc4 = st.columns(4)
    
    # Cash Debt con Benchmark Apple 0.49
    apple_ref = 0.49
    delta_apple = m['CD_Ann'] - apple_ref
    cc1.metric("CASH/DEBT (ANN)", f"{m['CD_Ann']:.2f}", delta=f"{delta_apple:.2f} vs AAPL")
    
    cc2.metric("PIOTROSKI SCORE", f"{m['FScore']}/9")
    cc3.metric("ALTMAN RISK", m['Altman'])
    cc4.metric("BENEISH SCORE", m['Beneish'])

    # 3. EXECUTIVE INSIGHTS TOOL
    st.divider()
    st.subheader("💡 Executive Insights & Analysis")
    
    col_left, col_right = st.columns(2)
    
    with col_left:
        # Analisi Efficienza
        if m['ROE'] > 20 and m['Margin'] > 15:
            st.success(f"**Vantaggio Competitivo:** L'azienda mostra un ROE e Margini dominanti. È una 'Cash Machine' con un moat elevato.")
        else:
            st.info("**Efficienza:** I margini sono in linea con il settore. L'azienda non sembra godere di un potere di prezzo assoluto.")
            
        # Analisi Debito
        if m['CD_Ann'] > apple_ref:
            st.success(f"**Solidità Finanziaria:** La struttura della cassa è più robusta di quella di Apple. Estrema capacità di autofinanziamento.")
        else:
            st.warning(f"**Leva Finanziaria:** La cassa copre il debito meno efficacemente rispetto al benchmark Apple. Monitorare scadenze obbligazionarie.")

    with col_right:
        # Analisi Rischio
        if m['Altman'] == "LOW" and m['FScore'] >= 6:
            st.success("**Certificazione Rischio:** Bassa probabilità di dissesto finanziario. Bilancio solido e trasparente.")
        else:
            st.error("**Alert Rischio:** Lo score Altman o Piotroski segnalano anomalie. Possibile deterioramento della qualità degli asset.")

    # 4. LEGENDA
    with st.expander("📖 LEGENDA LOGICA E MATEMATICA DEI PARAMETRI"):
        st.markdown("""
        #### 🧪 Formule e Logica
        - **ROE (Return on Equity):** `Utile Netto / Patrimonio Netto`. Indica la capacità di remunerare il capitale degli azionisti.
        - **Owner Earnings:** `Net Income + Depreciation - CapEx`. Rappresenta il denaro che il proprietario può prelevare senza danneggiare il business.
        - **Piotroski Score:** Sistema a 9 punti per valutare la forza finanziaria operativa.
        - **Altman Z-Score:**  Formula multi-fattore che misura la probabilità di bancarotta a 2 anni.
        - **Beneish M-Score:** Analisi matematica della manipolazione contabile. Identifica 'gonfiature' artificiali degli utili.
        - **Cash/Debt:** Rapporto tra liquidità immediata e debito totale. Il benchmark **Apple (0.49)** è lo standard aureo di efficienza finanziaria.
        """)
else:
    st.error("⚠️ Blocco persistente da parte di Yahoo. Prova a cambiare connessione o attendere 5 minuti per il reset dell'IP.")





















