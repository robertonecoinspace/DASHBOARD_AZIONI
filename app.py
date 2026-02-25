import streamlit as st
import yfinance as yf
import pandas as pd
import time
import random

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Terminal Pro (Native)", layout="wide")

# --- FUNZIONI DI UTILITÀ ---
def get_safe(data, keys, default=0):
    """Cerca una chiave in una lista di possibili nomi. Restituisce default se non trova nulla."""
    if not data: return default
    for k in keys:
        if k in data and data[k] is not None:
            return data[k]
    return default

# --- MOTORE DI ANALISI (Nativo yFinance) ---
@st.cache_data(ttl=3600)
def fetch_native_data(ticker):
    try:
        # 1. RITARDO UMANO (Cruciale: Evita il blocco 429)
        # Aspettiamo un tempo casuale tra 0.2 e 0.6 secondi
        time.sleep(random.uniform(0.2, 0.6))
        
        # 2. ISTANZA TICKER (Senza sessioni custom!)
        asset = yf.Ticker(ticker)
        
        # 3. RECUPERO DATI (Info completa)
        try:
            i = asset.info
        except:
            return None # Se fallisce info, il ticker è probabilmente rotto

        # Strategia Recupero Prezzo (Multi-chiave per BABA/ADR)
        price = get_safe(i, ['currentPrice', 'regularMarketPrice', 'bid', 'previousClose'])
        
        if not price:
            # Ultimo tentativo con fast_info (database diverso)
            try:
                price = asset.fast_info.get('last_price', 0)
            except:
                return None

        # --- ESTRAZIONE METRICHE ---
        
        # Redditività
        roe = get_safe(i, ['returnOnEquity', 'trailingAnnualDividendYield']) * 100
        margin = get_safe(i, ['profitMargins', 'netProfitMargin']) * 100
        div_yield = get_safe(i, ['dividendYield', 'trailingAnnualDividendYield']) * 100
        
        # Owner Earnings (Stima Buffett)
        ni = get_safe(i, ['netIncomeToCommon', 'netIncome'])
        
        # Ammortamenti (Spesso mancano nei dati info rapidi, usiamo fallback)
        rev = get_safe(i, ['totalRevenue', 'totalRevenue'], 1)
        dep = get_safe(i, ['depreciation', 'depreciationAndAmortization'])
        if dep == 0: dep = rev * 0.04 # Stima prudenziale 4% fatturato se manca il dato
        
        # Capex (Derivato o stimato)
        ocf = get_safe(i, ['operatingCashflow', 'operatingCashFlow'])
        fcf = get_safe(i, ['freeCashflow', 'freeCashFlow'])
        
        if ocf != 0 and fcf != 0:
            capex = abs(ocf - fcf)
        else:
            capex = rev * 0.05 # Stima 5% fatturato se mancano i flussi
            
        oe = ni + dep - capex
        
        # Cash & Debt
        cash = get_safe(i, ['totalCash', 'cashAndCashEquivalents'])
        debt = get_safe(i, ['totalDebt', 'longTermDebt'])
        cd_ratio = cash / debt if debt > 0 else 0
        
        # Scores & Risk
        f_score = 0
        if roe > 10: f_score += 3
        if get_safe(i, ['currentRatio']) > 1.1: f_score += 3
        if ocf > ni: f_score += 3
        
        audit_risk = get_safe(i, ['auditRisk'], 5)
        board_risk = get_safe(i, ['boardRisk'], 5)

        return {
            "name": get_safe(i, ['longName', 'shortName'], ticker),
            "sector": get_safe(i, ['sector', 'industry'], "N/A"),
            "currency": get_safe(i, ['currency', 'financialCurrency'], "USD"),
            "metrics": {
                "Price": price,
                "ROE": roe,
                "Margin": margin,
                "Yield": div_yield,
                "OE": oe,
                "CD": cd_ratio,
                "FScore": f_score,
                "Altman": audit_risk,
                "Beneish": board_risk
            }
        }

    except Exception as e:
        # Per debug, stampa l'errore in console ma non blocca l'app
        print(f"Errore su {ticker}: {e}")
        return None

# --- UI ---
st.title("🏛️ Equity Terminal (Native YF)")
st.caption("Engine: yFinance Native (Auto-Throttling)")

# CARICAMENTO CSV
try:
    df = pd.read_csv('lista_ticker.csv')
    df.columns = [c.strip() for c in df.columns]
    col = next((c for c in df.columns if c.lower() in ['ticker', 'symbol']), None)
    if col:
        lista_t = df[col].dropna().unique().tolist()
    else:
        lista_t = ["AAPL", "BABA", "NVDA"]
except:
    lista_t = ["AAPL", "BABA", "NVDA", "AMZN", "GOOGL"]

# SIDEBAR
tk_sel = st.sidebar.selectbox("Seleziona Asset:", lista_t)

if tk_sel:
    with st.spinner(f"Analisi nativa di {tk_sel}..."):
        data = fetch_native_data(tk_sel)

    if data:
        m = data["metrics"]
        st.header(f"📈 {data['name']} | 🏭 {data['sector']}")
        st.caption(f"Prezzo: {data['currency']} {m['Price']:.2f}")
        
        # 1. KPI
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("ROE", f"{m['ROE']:.2f}%")
        c2.metric("PROFIT MARGIN", f"{m['Margin']:.2f}%")
        c3.metric("DIV. YIELD", f"{(m['Yield']/100):.2f}%")
        c4.metric("OWNER EARNINGS", f"${m['OE']/1e9:.2f}B")

        st.write("---")

        # 2. SOLIDITÀ
        cc1, cc2, cc3, cc4 = st.columns(4)
        apple_ref = 0.49
        delta = m['CD'] - apple_ref
        
        cc1.metric("CASH/DEBT", f"{m['CD']:.2f}", delta=f"{delta:.2f} vs AAPL")
        cc2.metric("PIOTROSKI SCORE", f"{m['FScore']}/9")
        
        # Traduzione Rischio
        risk_label = "LOW" if m['Altman'] < 5 else "MEDIUM" if m['Altman'] < 8 else "HIGH"
        quality_label = "SAFE" if m['Beneish'] < 5 else "CHECK AUDIT"
        
        cc3.metric("ALTMAN RISK", risk_label)
        cc4.metric("BENEISH SCORE", quality_label)

        # 3. INSIGHTS
        st.divider()
        st.subheader("💡 Executive Insights")
        
        col_a, col_b = st.columns(2)
        with col_a:
            if m['ROE'] > 15: st.success(f"**Efficienza:** Eccellente ({m['ROE']:.1f}%).")
            else: st.info(f"**Efficienza:** Standard ({m['ROE']:.1f}%).")
            
            if m['CD'] > apple_ref: st.success("**Liquidità:** Superiore ad Apple.")
            else: st.warning("**Liquidità:** Inferiore ad Apple.")

        with col_b:
            if m['FScore'] >= 6: st.success(f"**Fondamentali:** Solidi (Score {m['FScore']}/9).")
            else: st.error(f"**Fondamentali:** Deboli (Score {m['FScore']}/9).")

        with st.expander("📖 LEGENDA"):
            st.markdown("""
            * **Cash/Debt:** Benchmark Apple **0.49**.
            * **Owner Earnings:** Utile + Ammortamenti - Capex (Stima Buffett).
            """)
            st.write("")

    else:
        st.error(f"Impossibile analizzare {tk_sel}.")
        st.info("Suggerimenti: Controlla che il ticker sia corretto (es. BABA per USA, 9988.HK per Hong Kong).")


























