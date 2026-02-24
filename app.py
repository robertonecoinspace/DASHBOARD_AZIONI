import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import os

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Strategic Equity Terminal Pro", layout="wide")

# Helper per estrarre dati in modo sicuro
def get_val(df, keys):
    if df is None or df.empty: return 0
    for k in keys:
        if k in df.index:
            val = df.loc[k]
            return val.iloc[0] if isinstance(val, (pd.Series, pd.DataFrame)) else val
    return 0

# --- CARICAMENTO TICKERS ---
try:
    lista_t = pd.read_csv('lista_ticker.csv')['Ticker'].tolist()
except:
    lista_t = ["AAPL", "MSFT", "GOOGL", "NVDA", "BRK-B", "META"]

# --- MOTORE DI ANALISI PROFONDA ---
@st.cache_data(ttl=86400)
def fetch_asset_data(ticker):
    try:
        s = yf.Ticker(ticker)
        i, f, c, b = s.info, s.financials, s.cashflow, s.balance_sheet
        q_f, q_b = s.quarterly_financials, s.quarterly_balance_sheet
        
        # Prezzo e EPS
        p = i.get('currentPrice', 0)
        e = i.get('trailingEps', 1)
        sh = i.get('sharesOutstanding', 1)
        
        # Calcolo Owner Earnings (OE)
        ni = get_val(f, ['Net Income'])
        dep = get_val(c, ['Depreciation And Amortization'])
        capx = abs(get_val(c, ['Capital Expenditure']))
        oe = ni + dep - capx
        
        # 1. Buffett DCF (Sconto 10%) - Proiezione 10 anni
        growth, discount = 0.05, 0.10
        fcf_base = i.get('freeCashflow', oe)
        proj_fcf = [fcf_base * (1 + growth)**n for n in range(1, 11)]
        vb = sum([v / (1 + discount)**n for n, v in enumerate(proj_fcf, 1)]) / sh if sh > 0 else 0
        
        # Altri Modelli (Graham e DCF standard)
        vg = e * (8.5 + 17)
        vd = (fcf_base * 15) / sh
        vm = (vg + vd + vb) / 3
        tm = vm * 0.75 # Golden MoS (25% sconto)

        # Calcolo Cassa/Debito (Benchmark Apple 0.49)
        def calc_cd(df):
            cash = get_val(df, ['Cash And Cash Equivalents']) + get_val(df, ['Other Short Term Investments', 'Short Term Investments'])
            debt = get_val(df, ['Total Debt'])
            return cash / debt if debt > 0 else 0

        return {
            "info": i, "vals": (p, vm, tm, oe, vg, vd, vb),
            "q_f": q_f, "f": f,
            "metrics": {
                "ROE": i.get('returnOnEquity', 0) * 100,
                "Margin": i.get('profitMargins', 0) * 100,
                "DivYield": i.get('dividendYield', 0) * 100,
                "Payout": i.get('payoutRatio', 0) * 100,
                "CashDebtAnn": calc_cd(b),
                "CashDebtTri": calc_cd(q_b),
                "OE": oe
            }
        }
    except: return None

# --- UI PRINCIPALE ---
st.title("🏛️ Equity Analysis Terminal Pro")

# Sidebar Selezione
tk_sel = st.sidebar.selectbox("Seleziona Ticker per l'analisi:", lista_t)
asset = fetch_asset_data(tk_sel)

if asset:
    i = asset["info"]
    p, vm, tm, oe, vg, vd, vb = asset["vals"]
    m = asset["metrics"]
    
    st.header(f"📈 {i.get('longName', tk_sel)}")
    
    # 🎯 Status e Valutazione Prezzo
    if p <= tm: st.success(f"### 🔥 SOTTOVALUTATO (Target MoS: ${tm:.2f})")
    elif p <= vm: st.warning(f"### ⚖️ PREZZO EQUO (Fair Value: ${vm:.2f})")
    else: st.error(f"### ⚠️ SOPRAVVALUTATO (Prezzo: ${p:.2f} | Fair Value: ${vm:.2f})")

    # 📊 SEZIONE METRICHE PURE
    st.subheader("📋 Metriche Pure & Analisi della Cassa")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("ROE", f"{m['ROE']:.1f}%")
    c2.metric("Profit Margin", f"{m['Margin']:.1f}%")
    c3.metric("Div. Yield", f"{m['DivYield']:.2f}%")
    c4.metric("Cash/Debt (Ann)", f"{m['CashDebtAnn']:.2f}")
    c5.metric("Cash/Debt (Tri)", f"{m['CashDebtTri']:.2f}")
    
    # Layout Metriche Secondarie
    sc1, sc2, sc3 = st.columns(3)
    sc1.metric("Owner Earnings", f"${m['OE']/1e9:.2f}B")
    sc2.metric("Payout Ratio", f"{m['Payout']:.1f}%")
    sc3.metric("Market Cap", f"${i.get('marketCap', 0)/1e12:.2f}T")

    st.divider()

    # 📉 GRAFICI VALUTAZIONE E FATTURATO
    g1, g2 = st.columns(2)
    
    with g1:
        st.subheader("Valutazioni Intrinseche (Buffett 10%)")
        v_labels = ['Market', 'Graham', 'DCF Std', 'Buffett 10%', 'MEDIA']
        v_data = [p, vg, vd, vb, vm]
        fig_v = go.Figure(go.Bar(x=v_labels, y=v_data, 
                                 marker_color=['#1e293b', '#3b82f6', '#f97316', '#10b981', '#8b5cf6'],
                                 text=[f"${v:.0f}" for v in v_data], textposition='outside'))
        # Linea MoS Dorata
        fig_v.add_hline(y=tm, line_dash="dash", line_color="#FFD700", line_width=3, 
                        annotation_text="GOLDEN MoS (Buy Zone)", annotation_position="top left")
        fig_v.update_layout(height=450, template="plotly_white")
        st.plotly_chart(fig_v, use_container_width=True)

    with g2:
        st.subheader("Andamento Fatturato (Revenue Momentum)")
        if not asset["f"].empty and 'Total Revenue' in asset["f"].index:
            rev_data = asset["f"].loc['Total Revenue'].iloc[::-1]
            colors = ['#1e293b'] * len(rev_data) # Colore costante per fatturato storico
            fig_r = go.Figure(go.Bar(x=rev_data.index.astype(str), y=rev_data.values, marker_color='#334155'))
            fig_r.update_layout(height=450, template="plotly_white")
            st.plotly_chart(fig_r, use_container_width=True)

    # 💡 INSIGHTS DI QUALITÀ (Executive Report)
    st.subheader("💡 Executive Quality Insights")
    score = 0
    if m['ROE'] > 15: score += 1
    if m['Margin'] > 15: score += 1
    if m['CashDebtAnn'] > 0.45: score += 1
    
    qualita = "ECCELLENTE" if score == 3 else "SOLIDA" if score == 2 else "DEBOLE/SPECULATIVA"
    
    st.info(f"""
    * **Solidità Finanziaria:** Il rapporto Cassa/Debito è **{m['CashDebtAnn']:.2f}**. {'L\'azienda possiede una liquidità di ferro paragonabile ai parametri Apple.' if m['CashDebtAnn'] > 0.48 else 'La gestione del debito richiede attenzione, pur essendo nel range di operatività.'}
    * **Qualità del Business:** Un ROE del **{m['ROE']:.1f}%** e un Profit Margin del **{m['Margin']:.1f}%** sono segnali di un vantaggio competitivo {'molto forte e resiliente.' if score >= 2 else 'che necessita di verifiche sui costi operativi.'}
    * **Generazione di Cassa:** Con Owner Earnings pari a **${m['OE']/1e9:.2f}B**, l'azienda genera cassa reale oltre il semplice dato contabile degli utili.
    * **Verdetto Finale:** Asset di qualità **{qualita}**.
    """)

    # 📖 LEGENDA ENCICLOPEDICA DINAMICA
    with st.expander(f"📖 LEGENDA E LOGICA DI ANALISI: {tk_sel}"):
        st.markdown(f"""
        ### 💰 Modelli di Valutazione
        - **Buffett 10% (DCF):** Valore intrinseco calcolato proiettando i flussi di cassa per 10 anni e scontandoli al **10%** (tasso di rendimento minimo richiesto).
        - **Golden MoS:** Rappresentata dalla **linea dorata**. È il prezzo d'ingresso che include un margine di sicurezza del 25% sulla media dei modelli. Comprare sotto questa linea protegge il capitale.
        - **Graham Model:** Stima il valore basandosi sugli EPS correnti e un moltiplicatore di crescita prudenziale.

        ### 📋 Metriche Pure
        - **ROE ({m['ROE']:.1f}%):** Indica l'efficienza nel generare profitti dal capitale degli azionisti. Valori > 15% indicano un "Moat".
        - **Profit Margin ({m['Margin']:.1f}%):** Quanto dei ricavi totali diventa guadagno netto. Più è alto, più l'azienda è protetta dall'inflazione.
        - **Cash/Debt ({m['CashDebtAnn']:.2f}):** Rapporto fondamentale di solvibilità. Il benchmark **Apple (0.49)** indica che per ogni dollaro di debito ci sono circa 50 centesimi di cassa pronta.
        - **Owner Earnings:** La cassa reale prodotta (Utile + Ammortamenti - CAPEX). È il parametro preferito da Warren Buffett.
        """)
else:
    st.error("Dati non disponibili o limite API raggiunto. Riprova tra 15 minuti.")












