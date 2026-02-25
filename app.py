import streamlit as st
import yfinance as yf
import pandas as pd
import requests

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Terminal Pro (Robust)", layout="wide")

# --- SIMULATORE BROWSER (Per evitare blocchi su BABA/ADR) ---
def get_session():
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36'
    })
    return session

# --- ESTRAZIONE INTELLIGENTE ---
def get_val(data, keys_list, default=0):
    if not data: return default
    for k in keys_list:
        if k in data and data[k] is not None:
            return data[k]
    return default

@st.cache_data(ttl=3600)
def fetch_robust_data(ticker):
    try:
        # Usiamo la sessione personalizzata
        session = get_session()
        asset = yf.Ticker(ticker, session=session)
        
        # Tentativo 1: Oggetto Info Completo
        try:
            i = asset.info
        except:
            i = {}
        
        # Tentativo 2: Fast Info (Se Info fallisce o manca il prezzo)
        # fast_info è un database diverso di Yahoo, spesso più aggiornato sui prezzi
        try:
            fast_price = asset.fast_info.get('last_price')
        except:
            fast_price = None

        # Strategia di recupero PREZZO (Cruciale per non dare "Dati non trovati")
        price = fast_price if fast_price else get_val(i, ['currentPrice', 'regularMarketPrice', 'ask', 'previousClose'])
        
        # Se non abbiamo nemmeno il prezzo, il ticker è probabilmente errato
        if not price or price == 0:
            return None

        # --- RECUPERO DATI BILANCIO ---
        # Cerchiamo i dati con nomi alternativi (Yahoo spesso li cambia per le azioni estere)
        
        # 1. Redditività
        roe = get_val(i, ['returnOnEquity', 'trailingAnnualDividendYield']) * 100
        margin = get_val(i, ['profitMargins', 'netProfitMargin']) * 100
        div_yield = get_val(i, ['dividendYield', 'trailingAnnualDividendYield']) * 100
        
        # 2. Owner Earnings (Buffett)
        ni = get_val(i, ['netIncomeToCommon', 'netIncome'])
        
        # Stima Ammortamenti se mancano (fallback al 5% dei ricavi)
        rev = get_val(i, ['totalRevenue', 'totalRevenue'])
        dep = get_val(i, ['depreciation', 'depreciationAndAmortization'], rev * 0.05)
        
        # Capex (Spesso manca in info, lo stimiamo dal Free Cash Flow se c'è)
        ocf = get_val(i, ['operatingCashflow', 'operatingCashFlow'])
        fcf = get_val(i, ['freeCashflow', 'freeCashFlow'])
        
        if ocf and fcf:
            capex = abs(ocf - fcf)
        else:
            capex = get_val(i, ['capitalExpenditures'], rev * 0.08) # Stima 8% ricavi se manca
            
        oe = ni + dep - capex
        
        # 3. Cash & Debt
        cash = get_val(i, ['totalCash', 'cashAndCashEquivalents'])
        debt = get_val(i, ['totalDebt', 'longTermDebt'])
        cd_ratio = cash / debt if debt > 0 else 0
        
        # 4. Scores
        f_score = 0
        if roe > 10: f_score += 3
        if get_val(i, ['currentRatio']) > 1.2: f_score += 3
        if ocf > ni: f_score += 3
        
        # Risk Metrics
        audit = get_val(i, ['auditRisk'], 5)
        board = get_val(i, ['boardRisk'], 5)

        return {
            "name": get_val(i, ['longName', 'shortName'], ticker),
            "sector": get_val(i, ['sector', 'industry'], "N/A"),
            "currency": get_val(i, ['currency', 'financialCurrency'], "USD"),
            "metrics": {
                "Price": price,
                "ROE": roe,
                "Margin": margin,
                "Yield": div_yield,
                "OE": oe,
                "CD": cd_ratio,
                "FScore": f_score,
                "Altman": audit,
                "Beneish": board
            }
        }
    except Exception as e:
        # Se fallisce tutto, restituisci l'errore per capire perché
        st.error(f"Errore interno su {ticker}: {e}")
        return None

# --- UI ---
st.title("🏛️ Terminal Pro (Robust Edition)")
st.caption("Analisi Resiliente: Funziona anche con ADR e dati parziali")

# GESTIONE CSV
try:
    df = pd.read_csv('lista_ticker.csv')
    # Pulizia nomi colonne
    df.columns = [c.strip() for c in df.columns]
    col = next((c for c in df.columns if c.lower() in ['ticker', 'symbol']), None)
    if col:
        lista_t = df[col].dropna().unique().tolist()
    else:
        lista_t = ["BABA", "AAPL", "NVDA"]
except:
    lista_t = ["BABA", "AAPL", "NVDA", "AMZN", "GOOGL"]

tk_sel = st.sidebar.selectbox("Seleziona Asset:", lista_t)

if tk_sel:
    with st.spinner(f"Analisi profonda di {tk_sel}..."):
        data = fetch_robust_data(tk_sel)

    if data:
        m = data["metrics"]
        st.header(f"📈 {data['name']} | 🏭 {data['sector']}")
        st.caption(f"Prezzo Rilevato: {data['currency']} {m['Price']:.2f}")
        
        # 1. KPI
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("ROE", f"{m['ROE']:.2f}%")
        c2.metric("PROFIT MARGIN", f"{m['Margin']:.2f}%")
        c3.metric("DIV. YIELD", f"{(m['Yield']/100):.2f}%") # Modifica richiesta
        c4.metric("OWNER EARNINGS", f"${m['OE']/1e9:.2f}B")

        st.write("---")

        # 2. SOLIDITÀ
        cc1, cc2, cc3, cc4 = st.columns(4)
        apple_ref = 0.49
        delta = m['CD'] - apple_ref
        
        cc1.metric("CASH/DEBT", f"{m['CD']:.2f}", delta=f"{delta:.2f} vs AAPL")
        cc2.metric("PIOTROSKI SCORE", f"{m['FScore']}/9")
        
        # Traduzione Rischio in etichette
        altman_risk = "LOW" if m['Altman'] < 5 else "MEDIUM" if m['Altman'] < 8 else "HIGH"
        beneish_risk = "SAFE" if m['Beneish'] < 5 else "CHECK AUDIT"
        
        cc3.metric("ALTMAN RISK", altman_risk)
        cc4.metric("BENEISH SCORE", beneish_risk)

        # 3. EXECUTIVE INSIGHTS
        st.divider()
        st.subheader("💡 Executive Insights")
        
        col_a, col_b = st.columns(2)
        with col_a:
            if m['ROE'] > 15: st.success(f"**Efficienza:** Eccellente ({m['ROE']:.1f}%).")
            else: st.info(f"**Efficienza:** Standard ({m['ROE']:.1f}%).")
            
            if m['CD'] > apple_ref: st.success("**Liquidità:** Superiore ad Apple. Bilancio 'Cash Rich'.")
            else: st.warning("**Liquidità:** Inferiore ad Apple. Monitorare il debito.")

        with col_b:
            if m['FScore'] >= 6: st.success(f"**Fondamentali:** Solidi (Score {m['FScore']}/9).")
            else: st.error(f"**Fondamentali:** Deboli (Score {m['FScore']}/9).")

        # LEGENDA
        with st.expander("📖 LEGENDA METRICHE"):
            st.markdown("""
            * **Cash/Debt:** Parametro chiave di solidità. Benchmark Apple: **0.49**.
            * **Owner Earnings:** Flusso di cassa reale (Utile + Ammortamenti - Capex).
            * **Piotroski Score:** Salute finanziaria (9=Max).
            """)
            st.write("[Image of Altman Z-score zones of credit strength]")

    else:
        st.error(f"Nessun dato recuperabile per {tk_sel}.")
        st.info("Yahoo Finance potrebbe aver bloccato temporaneamente il tuo IP.")
        st.markdown("**Soluzione:** Vai su 'Manage App' in basso a destra -> 'Reboot App'. Questo cambia IP e sblocca la situazione.")
        

























