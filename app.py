import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import os

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Strategic Equity Terminal Pro", layout="wide")

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
    lista_t = ["AAPL", "MSFT", "GOOGL", "NVDA", "BRK-B", "META", "TSLA", "AMZN"]

# --- MOTORE DI ANALISI ---
@st.cache_data(ttl=86400)
def fetch_asset_data(ticker):
    try:
        s = yf.Ticker(ticker)
        i, f, c, b = s.info, s.financials, s.cashflow, s.balance_sheet
        q_f, q_b = s.quarterly_financials, s.quarterly_balance_sheet
        
        p = i.get('currentPrice', 0)
        e = i.get('trailingEps', 1)
        sh = i.get('sharesOutstanding', 1)
        
        ni = get_val(f, ['Net Income'])
        dep = get_val(c, ['Depreciation And Amortization'])
        capx = abs(get_val(c, ['Capital Expenditure']))
        oe = ni + dep - capx
        
        # Buffett DCF (Sconto 10%)
        growth, discount = 0.05, 0.10
        fcf_base = i.get('freeCashflow', oe)
        proj_fcf = [fcf_base * (1 + growth)**n for n in range(1, 11)]
        vb = sum([v / (1 + discount)**n for n, v in enumerate(proj_fcf, 1)]) / sh if sh > 0 else 0
        
        vg = e * (8.5 + 17)
        vd = (fcf_base * 15) / sh
        vm = (vg + vd + vb) / 3
        tm = vm * 0.75 # Golden MoS

        def calc_cd(df):
            cash = get_val(df, ['Cash And Cash Equivalents']) + get_val(df, ['Other Short Term Investments', 'Short Term Investments'])
            debt = get_val(df, ['Total Debt'])
            return cash / debt if debt > 0 else 0

        return {
            "info": i, "vals": (p, vm, tm, oe, vg, vd, vb),
            "q_f": q_f, "metrics": {
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
st.title("🏛️ Strategic Equity Terminal Pro")

# 🎯 SEZIONE 1: SCANNER OPPORTUNITÀ
st.subheader("🎯 Scanner Opportunità (Sconto > 25%)")
with st.spinner("Scansione della lista in corso..."):
    scanner_list = []
    for t in lista_t[:15]: # Limitato per stabilità
        data = fetch_asset_data(t)
        if data:
            p, vm, tm = data["vals"][0], data["vals"][1], data["vals"][2]
            if p <= tm:
                sconto = ((vm - p) / vm) * 100
                scanner_list.append({"Ticker": t, "Prezzo": f"${p:.2f}", "Fair Value": f"${vm:.2f}", "Sconto": f"{sconto:.1f}%"})
    
    if scanner_list:
        st.table(pd.DataFrame(scanner_list))
    else:
        st.info("Nessun titolo attualmente sotto il prezzo MoS (Margin of Safety).")

st.divider()

# 📊 SEZIONE 2: ANALISI DETTAGLIATA
tk_sel = st.sidebar.selectbox("Analizza Asset:", lista_t)
asset = fetch_asset_data(tk_sel)

if asset:
    i = asset["info"]
    p, vm, tm, oe, vg, vd, vb = asset["vals"]
    m = asset["metrics"]
    oe_bn = m['OE'] / 1e9

    st.header(f"📈 {i.get('longName', tk_sel)}")
    
    # Status Valutazione
    if p <= tm: st.success(f"### 🔥 SOTTOVALUTATO (Target MoS: ${tm:.2f})")
    elif p <= vm: st.warning(f"### ⚖️ FAIR VALUE (Fair Value: ${vm:.2f})")
    else: st.error(f"### ⚠️ SOPRAVVALUTATO (Fair Value: ${vm:.2f})")

    # Metriche Pure
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("ROE", f"{m['ROE']:.1f}%")
    c2.metric("Profit Margin", f"{m['Margin']:.1f}%")
    c3.metric("Div. Yield", f"{m['DivYield']:.2f}%")
    c4.metric("Cash/Debt (Ann)", f"{m['CashDebtAnn']:.2f}")
    c5.metric("Cash/Debt (Tri)", f"{m['CashDebtTri']:.2f}")

    # Grafici
    g1, g2 = st.columns(2)
    with g1:
        st.subheader("Valutazioni Intrinseche (Buffett 10%)")
        fig_v = go.Figure(go.Bar(x=['Market', 'Graham', 'DCF Std', 'Buffett 10%', 'MEDIA'], 
                                 y=[p, vg, vd, vb, vm], 
                                 marker_color=['#1e293b', '#3b82f6', '#f97316', '#10b981', '#8b5cf6']))
        fig_v.add_hline(y=tm, line_dash="dash", line_color="#FFD700", line_width=3, annotation_text="GOLDEN MoS")
        st.plotly_chart(fig_v, use_container_width=True)

    with g2:
        st.subheader("Fatturato Trimestrale (Ultimi 3 Anni)")
        if not asset["q_f"].empty and 'Total Revenue' in asset["q_f"].index:
            rev_q = asset["q_f"].loc['Total Revenue'].iloc[:12][::-1]
            # Logica colori barre (Verde se > precedente, Rosso se <)
            bar_colors = []
            for n in range(len(rev_q)):
                if n == 0: bar_colors.append('#334155')
                else: bar_colors.append('#10b981' if rev_q.values[n] >= rev_q.values[n-1] else '#ef4444')
            
            fig_r = go.Figure(go.Bar(x=rev_q.index.astype(str), y=rev_q.values, marker_color=bar_colors))
            st.plotly_chart(fig_r, use_container_width=True)

    # Insight Qualità
    st.subheader("💡 Executive Quality Insights")
    score = 0
    if m['ROE'] > 15: score += 1
    if m['Margin'] > 15: score += 1
    if m['CashDebtAnn'] > 0.45: score += 1
    qual = "ECCELLENTE" if score == 3 else "SOLIDA" if score == 2 else "DEBOLE"
    
    st.info(f"**Verdetto:** Qualità **{qual}**. Rapporto Cassa/Debito: **{m['CashDebtAnn']:.2f}** (Target Apple 0.49). "
            f"ROE: **{m['ROE']:.1f}%** con Owner Earnings di **${oe_bn:.2f}B**.")

    # Legenda Approfondita
    with st.expander("📖 LEGENDA ENCICLOPEDICA E LOGICA TECNICA"):
        st.markdown(f"""
        ### ⚖️ Modelli di Valutazione
        * **Buffett DCF (10% Discount):** Rappresenta il valore attuale dei flussi di cassa futuri proiettati a 10 anni, scontati ad un tasso del 10%. È il metodo più prudente per determinare quanto vale oggi un business.
        * **Golden MoS (Margin of Safety):** Rappresentata dalla **linea dorata**. Indica un prezzo d'ingresso con uno sconto del 25% rispetto al Fair Value medio. Serve a proteggere l'investitore da errori di stima.
        * **Modello Graham:** Valuta l'azienda in base agli utili attuali e un moltiplicatore di crescita razionale (EPS * (8.5 + 2g)).

        ### 📊 Metriche Pure di Performance
        * **ROE (Return on Equity):** Indica l'efficienza con cui l'azienda usa il capitale degli azionisti per generare utili. Valori > 15% indicano spesso un "Moat" (vantaggio competitivo).
        * **Profit Margin:** La percentuale di ricavi che diventa utile netto. Misura la capacità di resistere all'aumento dei costi (Pricing Power).
        * **Owner Earnings:** L'utile "reale" di Buffett. Si calcola come: *Utile Netto + Ammortamenti - Spese in conto capitale (CAPEX)*. È la cassa che può essere prelevata senza danneggiare il business.

        ### 🏦 Analisi Finanziaria
        * **Cash/Debt (Benchmark Apple 0.49):** Questo terminale somma Cassa e Investimenti a breve termine e li divide per il Debito Totale. Un valore di 0.49 (target storico di Apple) indica una solvibilità estrema. Se il dato **Trimestrale** è inferiore all'**Annuale**, l'azienda sta bruciando liquidità.
        * **Payout Ratio:** Percentuale degli utili pagata come dividendo. Sotto il 50-60% è considerato sostenibile.
        """)











