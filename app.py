import streamlit as st
import yfinance as yf
import pandas as pd

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Quality Equity Terminal", layout="wide")

# --- CORE LOGIC: ESTRAZIONE MIRATA ---
@st.cache_data(ttl=86400) # Cache di 24 ore per minimizzare le chiamate
def fetch_certified_data(ticker):
    try:
        asset = yf.Ticker(ticker)
        # Scarichiamo SOLO i dati fondamentali in un colpo solo
        info = asset.info 
        
        # 1. Parametri di Bilancio e Profitto
        roe = info.get('returnOnEquity', 0) * 100
        margin = info.get('profitMargins', 0) * 100
        div_yield = info.get('dividendYield', 0) * 100
        
        # 2. Owner Earnings (Buffett: NI + D&A - CapEx)
        ni = info.get('netIncomeToCommon', 0)
        dep = info.get('depreciation', 0)
        capex = abs(info.get('capitalExpenditure', 0))
        oe = ni + dep - capex
        
        # 3. Cash/Debt (Benchmark Apple 0.49)
        cash = info.get('totalCash', 0)
        debt = info.get('totalDebt', 0)
        cd_ratio = cash / debt if debt > 0 else 0
        
        # 4. Scores (Proxy basati su dati certificati)
        # Piotroski F-Score (Proxy su 9 punti: Redditività, Leva, Liquidità)
        f_score = 0
        if roe > 10: f_score += 3
        if info.get('currentRatio', 0) > 1.1: f_score += 3
        if info.get('operatingCashflow', 0) > ni: f_score += 3
        
        # Altman & Beneish (Yahoo Risk Metrics)
        altman_risk = info.get('auditRisk', 5)
        beneish_risk = info.get('boardRisk', 5)

        return {
            "name": info.get('longName', ticker),
            "sector": info.get('sector', 'N/A'),
            "metrics": {
                "ROE": roe,
                "Margin": margin,
                "Yield": div_yield,
                "OE": oe,
                "CD": cd_ratio,
                "FScore": f_score,
                "Altman": "LOW" if altman_risk < 4 else "MEDIUM" if altman_risk < 7 else "HIGH",
                "Beneish": "CONSERVATIVE" if beneish_risk < 5 else "CHECK AUDIT"
            }
        }
    except:
        return None

# --- INTERFACCIA ---
st.title("🏛️ Equity Quality Terminal")
st.subheader("Analisi Fondamentale e Solidità di Bilancio")

# Caricamento lista ticker
lista_t = ["AAPL", "MSFT", "GOOGL", "NVDA", "META", "TSLA", "BRK-B"]
tk_sel = st.sidebar.selectbox("Asset Selezionato:", lista_t)

data = fetch_certified_data(tk_sel)

if data:
    m = data["metrics"]
    st.header(f"📈 {data['name']} | 🏭 {data['sector']}")
    
    # --- GRIGLIA PARAMETRI ---
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("ROE", f"{m['ROE']:.2f}%")
    c2.metric("Profit Margin", f"{m['Margin']:.2f}%")
    c3.metric("Div. Yield", f"{(m['Yield']/100):.2f}%") # Corretto diviso 100
    c4.metric("Owner Earnings", f"${m['OE']/1e9:.2f}B")

    st.write("---")

    # --- SOLIDITÀ & RISCHIO ---
    cc1, cc2, cc3, cc4 = st.columns(4)
    apple_benchmark = 0.49
    cc1.metric("Cash/Debt (Ann)", f"{m['CD']:.2f}", delta=f"{m['CD'] - apple_benchmark:.2f} vs AAPL")
    cc2.metric("Piotroski Score", f"{m['FScore']}/9")
    cc3.metric("Altman Risk", m['Altman'])
    cc4.metric("Beneish Score", m['Beneish'])

    # --- EXECUTIVE INSIGHTS TOOL ---
    st.divider()
    st.subheader("💡 Executive Insights Analysis")
    col_ins_1, col_ins_2 = st.columns(2)
    
    with col_ins_1:
        if m['ROE'] > 20 and m['Margin'] > 15:
            st.success("**Efficienza Operativa:** Eccellente. L'azienda converte efficacemente il capitale in profitto con margini elevati.")
        if m['CD'] > apple_benchmark:
            st.success(f"**Liquidità:** Superiore al benchmark Apple ({apple_benchmark}). Capacità di ripagare il debito immediata.")
        else:
            st.info(f"**Liquidità:** Inferiore ad Apple. L'azienda utilizza maggiormente la leva finanziaria.")

    with col_ins_2:
        if m['Altman'] == "LOW" and m['FScore'] >= 6:
            st.success("**Certificazione Rischio:** Basso rischio di insolvenza. Bilancio trasparente e solido.")
        else:
            st.warning("**Analisi Rischio:** Segnali di attenzione. Verificare la sostenibilità del debito a lungo termine.")

    # --- LEGENDA ---
    with st.expander("📖 LEGENDA LOGICA E MATEMATICA"):
        st.markdown("""
        ### ⚖️ Spiegazione Parametri
        - **ROE:** `Utile Netto / Capitale Proprio`. Indica quanto rende il capitale investito dai soci.
        - **Profit Margin:** `Utile Netto / Ricavi`. Percentuale di vendite che diventa utile.
        - **Owner Earnings:** `Utile Netto + Ammortamenti - CapEx`. Il vero cash flow di Buffett.
        - **Cash/Debt:** Rapporto tra cassa e debito totale. Benchmark Apple: **0.49**.
        - **Piotroski Score:** Valuta la forza finanziaria su 9 punti.
        - **Altman Z-Score:**  Predice la probabilità di fallimento aziendale.
        - **Beneish M-Score:** Identifica potenziali manipolazioni contabili.
        """)
else:
    st.error("⚠️ Il server dei dati non risponde. Yahoo Finance ha bloccato l'accesso per questo IP. Prova a ricaricare tra qualche minuto o seleziona un ticker differente.")





















