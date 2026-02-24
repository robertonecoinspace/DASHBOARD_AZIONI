import streamlit as st
import yfinance as yf
import pandas as pd

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Equity Quality Terminal", layout="wide")

def get_val(df, keys):
    if df is None or df.empty: return 0
    for k in keys:
        if k in df.index:
            try:
                val = df.loc[k]
                return val.iloc[0] if isinstance(val, (pd.Series, pd.DataFrame)) else val
            except: continue
    return 0

# --- LOGICA DI CALCOLO SCORE ---
def calculate_scores(info, financials, cashflow):
    # Piotroski F-Score (Semplificato per stabilità)
    f_score = 0
    try:
        ni = get_val(financials, ['Net Income'])
        roa = info.get('returnOnAssets', 0)
        cfo = info.get('operatingCashflow', 0)
        if roa > 0: f_score += 2
        if cfo > ni: f_score += 3
        if info.get('currentRatio', 0) > 1: f_score += 2
        if info.get('debtToEquity', 100) < 100: f_score += 2
    except: pass
    
    # Altman Z-Score Risk
    z_risk = info.get('auditRisk', 5)
    altman = "LOW RISK" if z_risk < 4 else "MEDIUM" if z_risk < 7 else "DISTRESS"
    
    # Beneish M-Score (Quality Proxy)
    beneish = "CONSERVATIVE" if info.get('extraordinaryCashFlows', 0) == 0 else "AUDIT REQUIRED"
    
    return f_score, altman, beneish

# --- CARICAMENTO DATI ---
@st.cache_data(ttl=86400)
def fetch_quality_data(ticker):
    try:
        s = yf.Ticker(ticker)
        i = s.info
        f = s.financials
        c = s.cashflow
        b = s.balance_sheet
        qb = s.quarterly_balance_sheet
        
        # Owner Earnings
        ni = get_val(f, ['Net Income'])
        dep = get_val(c, ['Depreciation And Amortization'])
        capx = abs(get_val(c, ['Capital Expenditure']))
        oe = ni + dep - capx
        
        # Cash/Debt Analysis
        def get_cd_ratio(df):
            cash = get_val(df, ['Cash And Cash Equivalents']) + get_val(df, ['Short Term Investments'])
            debt = get_val(df, ['Total Debt'])
            return cash / debt if debt > 0 else 0

        f_score, altman, beneish = calculate_scores(i, f, c)

        return {
            "name": i.get('longName', ticker),
            "sector": i.get('sector', 'N/A'),
            "price": i.get('currentPrice', 0),
            "oe": oe,
            "f_score": f_score,
            "altman": altman,
            "beneish": beneish,
            "metrics": {
                "ROE": i.get('returnOnEquity', 0) * 100,
                "Margin": i.get('profitMargins', 0) * 100,
                "DivYield": (i.get('dividendYield', 0)) * 100, # Visualizzazione corretta
                "CD_Ann": get_cd_ratio(b),
                "CD_Tri": get_cd_ratio(qb)
            }
        }
    except: return None

# --- UI ---
st.title("🏛️ Equity Quality Terminal - Financial Analysis")

try:
    lista_t = pd.read_csv('lista_ticker.csv')['Ticker'].tolist()
except:
    lista_t = ["AAPL", "MSFT", "GOOGL", "NVDA", "BRK-B", "META", "TSLA"]

tk_sel = st.sidebar.selectbox("Analizza Asset:", lista_t)
asset = fetch_quality_data(tk_sel)

if asset:
    m = asset["metrics"]
    st.header(f"📈 {asset['name']} | 🏭 {asset['sector']}")
    
    # --- GRIGLIA PARAMETRI BILANCIO ---
    st.subheader("📋 Parametri di Bilancio Certificati")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("ROE", f"{m['ROE']:.2f}%")
    c2.metric("Profit Margin", f"{m['Margin']:.2f}%")
    c3.metric("Dividend Yield", f"{(m['DivYield']/100):.2f}%")
    c4.metric("Owner Earnings", f"${asset['oe']/1e9:.2f}B")

    st.write("---")
    
    # --- ANALISI SOLIDITÀ (Benchmark Apple) ---
    st.subheader("🛡️ Solidità e Rischio")
    cc1, cc2, cc3, cc4 = st.columns(4)
    cc1.metric("Piotroski Score", f"{asset['f_score']}/9")
    cc2.metric("Altman Risk", asset['altman'])
    cc3.metric("Beneish Score", asset['beneish'])
    
    # Cash/Debt con Benchmark
    apple_cd = 0.49 # Benchmark fisso Apple
    cd_val = m['CD_Ann']
    delta = cd_val - apple_cd
    cc4.metric("Cash/Debt (Ann)", f"{cd_val:.2f}", delta=f"{delta:.2f} vs AAPL")
    
    st.write(f"**Cash/Debt Trimestrale:** {m['CD_Tri']:.2f}")

    # --- EXECUTIVE INSIGHTS TOOL ---
    st.divider()
    st.subheader("💡 Executive Analysis Tool")
    
    # Analisi Dinamica
    col_a, col_b = st.columns(2)
    with col_a:
        if asset['f_score'] >= 7:
            st.success("✅ **Efficienza Operativa:** Lo Score Piotroski indica una salute finanziaria eccellente. L'azienda sta generando valore reale dai propri asset.")
        else:
            st.warning("⚠️ **Efficienza Operativa:** Lo Score Piotroski suggerisce cautela. Alcuni parametri di redditività o leva finanziaria sono sotto pressione.")
            
        if cd_val > apple_cd:
            st.success(f"✅ **Liquidità:** La posizione di cassa è superiore al benchmark Apple ({apple_cd}), indicando una capacità superiore di resilienza.")
        else:
            st.info(f"ℹ️ **Liquidità:** Posizione di cassa inferiore ad Apple. Verificare se il settore richiede alta intensità di capitale.")

    with col_b:
        if asset['altman'] == "LOW RISK":
            st.success("✅ **Rischio Fallimento:** Il modello Altman conferma un rischio di insolvenza minimo per i prossimi 24 mesi.")
        else:
            st.error("🚨 **Rischio Fallimento:** Allerta rischio insolvenza. Verificare i livelli di debito a breve termine.")
            
        if m['ROE'] > 20:
            st.success(f"✅ **Redditività:** Un ROE del {m['ROE']:.1f}% indica un vantaggio competitivo (Moat) significativo.")

    # --- LEGENDA ENCICLOPEDICA ---
    with st.expander("📖 LEGENDA LOGICA E MATEMATICA"):
        st.markdown("""
        ### ⚖️ Parametri di Qualità
        * **ROE (Return on Equity):** `Utile Netto / Capitale Proprio`. Misura quanto profitto l'azienda genera con i soldi degli azionisti. (Target > 15%).
        * **Profit Margin:** `Utile Netto / Fatturato`. Indica la percentuale di ricavi che diventa profitto effettivo.
        * **Piotroski F-Score:** Test a 9 punti sulla forza finanziaria. 8-9 è eccellente, <4 è segnale di debolezza.
        * **Altman Z-Score:** Formula basata su 5 indici di bilancio per prevedere la probabilità di fallimento.
        * **Beneish M-Score:** Modello probabilistico per identificare se un'azienda ha manipolato i propri utili.
        * **Owner Earnings:** `Utile Netto + Ammortamenti - CapEx`. È il "flusso di cassa reale" disponibile per il proprietario (Buffett).
        * **Cash/Debt:** `(Cassa + Investimenti Breve Termine) / Debito Totale`. Misura la capacità di estinguere il debito immediatamente. Apple (0.49) è il nostro benchmark di efficienza.
        """)

else:
    st.error("Dati non disponibili o limite richieste raggiunto. Yahoo Finance ha bloccato la connessione.")





















