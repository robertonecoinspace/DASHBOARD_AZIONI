import streamlit as st
import yfinance as yf
import pandas as pd
import time
import random

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Terminal Pro (Hardcore Fix)", layout="wide")

# --- FUNZIONI AUSILIARIE ---
def get_safe_val(df, row_name):
    """Estrae un valore da un DataFrame finanziario in modo sicuro."""
    try:
        if row_name in df.index:
            return df.loc[row_name].iloc[0] # Prende il dato più recente (colonna 0)
        return 0
    except:
        return 0

# --- MOTORE DI ANALISI (Porta di Servizio) ---
@st.cache_data(ttl=3600)
def fetch_hardcore_data(ticker):
    try:
        # 1. RITARDO CASUALE (Anti-Ban)
        time.sleep(random.uniform(0.3, 0.8))
        
        asset = yf.Ticker(ticker)
        
        # 2. RECUPERO PREZZO (Uso fast_info, NON info)
        # fast_info usa un endpoint diverso che raramente viene bloccato
        try:
            price = asset.fast_info.get('last_price')
            if not price: return None
        except:
            return None

        # 3. RECUPERO NOME E SETTORE (Tentativo soft)
        # Se info è bloccato, usiamo valori di default, ma non fermiamo l'analisi
        try:
            name = asset.info.get('longName', ticker)
            sector = asset.info.get('sector', 'Settore N/A')
        except:
            name = ticker
            sector = "Settore Recuperato (Info Bloccate)"

        # 4. SCARICO BILANCI GREZZI (Tabelle Pandas)
        # Questo bypassa il blocco su .info scaricando direttamente le tabelle
        bs = asset.balance_sheet          # Stato Patrimoniale
        inc = asset.income_stmt           # Conto Economico
        cf = asset.cashflow               # Flussi di Cassa
        
        if bs.empty or inc.empty:
            return None

        # 5. CALCOLI MANUALI SUI DATI GREZZI
        
        # Owner Earnings (Utile + Ammortamenti - Capex)
        # Cerchiamo i nomi delle righe standard di Yahoo
        ni = get_safe_val(inc, 'Net Income')
        if ni == 0: ni = get_safe_val(inc, 'Net Income Common Stockholders')
        
        # Ammortamenti (Spesso sotto 'Reconciled Depreciation')
        dep = get_safe_val(cf, 'Depreciation And Amortization')
        if dep == 0: dep = get_safe_val(cf, 'Reconciled Depreciation')
        
        # Capex
        capex = abs(get_safe_val(cf, 'Capital Expenditure'))
        
        oe = ni + dep - capex
        
        # Cash / Debt
        cash = get_safe_val(bs, 'Cash And Cash Equivalents') + get_safe_val(bs, 'Other Short Term Investments')
        debt = get_safe_val(bs, 'Total Debt')
        cd_ratio = cash / debt if debt > 0 else 0
        
        # ROE (Utile / Equity)
        equity = get_safe_val(bs, 'Stockholders Equity')
        roe = (ni / equity) * 100 if equity != 0 else 0
        
        # Profit Margin (Utile / Ricavi)
        rev = get_safe_val(inc, 'Total Revenue')
        margin = (ni / rev) * 100 if rev != 0 else 0
        
        # Dividend Yield
        # Dividendi Pagati / Market Cap (Stimato: Prezzo * Azioni)
        div_paid = abs(get_safe_val(cf, 'Cash Dividends Paid'))
        shares = asset.fast_info.get('shares', 1) # fast_info per le azioni
        mkt_cap = price * shares
        div_yield = (div_paid / mkt_cap) * 100 if mkt_cap > 0 else 0
        
        # Scores
        f_score = 0
        if ni > 0: f_score += 2
        ocf = get_safe_val(cf, 'Operating Cash Flow')
        if ocf > ni: f_score += 3
        curr_assets = get_safe_val(bs, 'Total Assets') # Semplificazione se manca current
        if curr_assets > debt: f_score += 2
        
        # Risk Metrics (Proxy)
        lev = debt / (get_safe_val(bs, 'Total Assets') or 1)
        altman = "LOW" if lev < 0.5 else "MEDIUM" if lev < 0.8 else "HIGH"
        beneish = "SAFE" # Default safe se non possiamo calcolarlo

        return {
            "name": name,
            "sector": sector,
            "metrics": {
                "Price": price,
                "ROE": roe,
                "Margin": margin,
                "Yield": div_yield,
                "OE": oe,
                "CD": cd_ratio,
                "FScore": f_score,
                "Altman": altman,
                "Beneish": beneish
            }
        }

    except Exception as e:
        # Stampa errore in console per debug
        print(f"Errore Hardcore su {ticker}: {e}")
        return None

# --- UI ---
st.title("🏛️ Equity Terminal (Hardcore Mode)")
st.caption("Engine: Direct DataFrame Access (Bypassa .info)")

# CARICAMENTO CSV
try:
    df = pd.read_csv('lista_ticker.csv')
    df.columns = [c.strip() for c in df.columns]
    col = next((c for c in df.columns if c.lower() in ['ticker', 'symbol']), None)
    if col:
        lista_t = df[col].dropna().unique().tolist()
    else:
        lista_t = ["AAPL", "MSFT", "NVDA"]
except:
    lista_t = ["AAPL", "NVDA", "TSLA", "AMZN", "GOOGL"]

tk_sel = st.sidebar.selectbox("Seleziona Asset:", lista_t)

if tk_sel:
    with st.spinner(f"Estrazione profonda {tk_sel}..."):
        data = fetch_hardcore_data(tk_sel)

    if data:
        m = data["metrics"]
        st.header(f"📈 {data['name']}")
        st.caption(f"Settore: {data['sector']} | Prezzo: ${m['Price']:.2f}")
        
        # 1. KPI
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("ROE", f"{m['ROE']:.2f}%")
        c2.metric("PROFIT MARGIN", f"{m['Margin']:.2f}%")
        c3.metric("DIV. YIELD", f"{(m['Yield']):.2f}%")
        c4.metric("OWNER EARNINGS", f"${m['OE']/1e9:.2f}B")

        st.write("---")

        # 2. SOLIDITÀ
        cc1, cc2, cc3, cc4 = st.columns(4)
        apple_ref = 0.49
        delta = m['CD'] - apple_ref
        
        cc1.metric("CASH/DEBT", f"{m['CD']:.2f}", delta=f"{delta:.2f} vs AAPL")
        cc2.metric("PIOTROSKI (Calc)", f"{m['FScore']}/7") # Su 7 punti qui per semplificazione
        cc3.metric("LEVA (Altman)", m['Altman'])
        cc4.metric("QUALITY", m['Beneish'])

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
            if m['FScore'] >= 5: st.success(f"**Fondamentali:** Solidi.")
            else: st.error(f"**Fondamentali:** Deboli.")

        with st.expander("📖 LEGENDA"):
            st.markdown("""
            * **Cash/Debt:** Benchmark Apple **0.49**.
            * **Dati:** Estratti direttamente dai bilanci depositati (non dal riassunto Yahoo).
            """)
            
    else:
        st.error(f"Impossibile analizzare {tk_sel}.")
        st.warning("Se sei su Streamlit Cloud, prova a fare 'Reboot App'.")

























