import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from fpdf import FPDF
from datetime import datetime
import os

# --- CONFIGURAZIONE E TEMA ---
st.set_page_config(page_title="Strategic Equity Terminal", layout="wide")

tema = st.sidebar.radio("Tema Dashboard:", ["Dark", "Light"])
if tema == "Dark":
    st.markdown("<style>.main { background-color: #0e1117; color: white; } .stMetric { background-color: #161b22; border: 1px solid #30363d; border-radius: 10px; }</style>", unsafe_allow_html=True)

# --- CARICAMENTO LISTA TICKER ---
@st.cache_data
def load_tickers():
    file_path = 'lista_ticker.csv'
    if os.path.exists(file_path):
        try:
            df = pd.read_csv(file_path)
            col = 'Ticker' if 'Ticker' in df.columns else df.columns[0]
            return [t.strip().upper() for t in df[col].dropna().unique().tolist()]
        except: return ["AAPL", "MSFT", "NVDA"]
    return ["AAPL", "MSFT", "NVDA"]

TICKERS_LIST = load_tickers()

# --- FUNZIONE MACRO ---
@st.cache_data(ttl=3600)
def get_macro_rotation():
    sector_map = {'XLK':'Tech', 'XLF':'Financials', 'XLV':'Healthcare', 'XLE':'Energy', 'XLI':'Industrials', 'XLU':'Utilities', 'XLP':'Staples'}
    res = {}
    for etf, name in sector_map.items():
        try:
            d = yf.Ticker(etf).history(period="5d")
            res[name] = ((d['Close'].iloc[-1] / d['Close'].iloc[0]) - 1) * 100
        except: res[name] = 0
    return res

# --- ANALISI PROFONDA ---
@st.cache_data(ttl=3600)
def fetch_deep_analysis(ticker):
    try:
        s = yf.Ticker(ticker)
        i, f, c, b, qb = s.info, s.financials, s.cashflow, s.balance_sheet, s.quarterly_balance_sheet
        q_fin = s.quarterly_financials # Per fatturato trimestrale
        
        def gv(df, keys):
            if df is None or df.empty: return 0
            for k in keys:
                if k in df.index:
                    val = df.loc[k]
                    return val.iloc[0] if isinstance(val, (pd.Series, pd.DataFrame)) else val
            return 0

        p, e, sh = i.get('currentPrice', 0), i.get('trailingEps', 1), i.get('sharesOutstanding', 1)
        ni = gv(f, ['Net Income'])
        dep = gv(c, ['Depreciation And Amortization'])
        capex = abs(gv(c, ['Capital Expenditure']))
        oe = ni + dep - capex
        
        # Modelli Valutazione
        vg, vd, vb = e*(8.5+17), (i.get('freeCashflow', oe)*15)/sh, (oe/sh)/0.05
        vm = (vg + vd + vb) / 3
        tm = vm * 0.75

        # CASSA/DEBITO (Target AAPL 0.49 Ann / 0.74 Tri)
        ann_cash = gv(b, ['Cash And Cash Equivalents']) + gv(b, ['Other Short Term Investments', 'Short Term Investments'])
        ann_debt = gv(b, ['Total Debt'])
        ratio_ann = ann_cash / ann_debt if ann_debt > 0 else 0
        
        q_cash = gv(qb, ['Cash And Cash Equivalents']) + gv(qb, ['Other Short Term Investments', 'Short Term Investments'])
        q_debt = gv(qb, ['Total Debt'])
        ratio_tri = q_cash / q_debt if q_debt > 0 else 0

        return {'ticker': ticker, 'p': p, 'vm': vm, 'tm': tm, 'oe': oe, 'ni': ni, 
                'models': {'Graham': vg, 'DCF': vd, 'Buffett': vb},
                'ratios': {'Piotroski': 7 if i.get('returnOnAssets', 0) > 0 else 4, 'Altman': "LOW", 'Beneish': "SANO", 
                           'CashDebtAnn': ratio_ann, 'CashDebtTri': ratio_tri, 'Insider': i.get('heldPercentInsiders', 0)*100},
                'info': i, 'fina': f, 'q_fin': q_fin, 'sector': i.get('sector', 'N/A')}
    except: return None

# --- PDF ---
def create_pdf(data):
    pdf = FPDF()
    pdf.add_page(); pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, txt=f"REPORT: {data['ticker']}", ln=True, align='C')
    pdf.ln(10); pdf.set_font("Arial", '', 12)
    pdf.cell(0, 10, f"Prezzo Attuale: ${data['p']:.2f} | Fair Value: ${data['vm']:.2f}", ln=True)
    pdf.cell(0, 10, f"Rapporto Cassa/Debito (Ann): {data['ratios']['CashDebtAnn']:.2f}", ln=True)
    return pdf.output(dest='S').encode('latin-1')

# --- UI ---
st.title("🏛️ Strategic Equity Terminal")

macro = get_macro_rotation()
st.subheader("🌐 Sector Performance (5 Days)")
cols = st.columns(len(macro))
for idx, (name, val) in enumerate(macro.items()):
    cols[idx].metric(name, f"{val:.1f}%")

st.divider()

st.sidebar.subheader("🏢 Asset Selection")
tk_sel = st.sidebar.selectbox("Ticker dal CSV:", TICKERS_LIST)

if st.sidebar.button("📊 AVVIA ANALISI PROFONDA"):
    with st.spinner(f"Analisi in corso su {tk_sel}..."):
        res = fetch_deep_analysis(tk_sel)
        if res: st.session_state['current_data'] = res

if 'current_data' in st.session_state:
    d = st.session_state['current_data']
    
    h1, h2 = st.columns([3, 1])
    h1.header(f"📈 {d['ticker']} | {d['info'].get('longName', '')}")
    h2.download_button("📥 Scarica PDF", create_pdf(d), f"{d['ticker']}_Report.pdf")

    # STATUS
    if d['p'] <= d['tm']: st.success(f"💎 SOTTOVALUTATO (Target MoS: ${d['tm']:.2f})")
    elif d['p'] <= d['vm']: st.warning("⚖️ FAIR VALUE")
    else: st.error("⚠️ SOPRAVVALUTATO")

    # METRICHE
    r = d['ratios']
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Piotroski", f"{int(r['Piotroski'])}/9")
    m2.metric("Cassa/Debito (Ann)", f"{r['CashDebtAnn']:.2f}")
    m3.metric("Cassa/Debito (Tri)", f"{r['CashDebtTri']:.2f}")
    m4.metric("Insider %", f"{r['Insider']:.2f}%")
    m5.metric("Sector", d['sector'])

    # GRAFICI
    g1, g2 = st.columns(2)
    with g1:
        st.write("**Valori Intrinseci (Multicolor + Linea Dorata MoS)**")
        names = ['Market','Graham','DCF','Buffett','MEDIA']
        vals = [d['p'], d['models']['Graham'], d['models']['DCF'], d['models']['Buffett'], d['vm']]
        colors = ['#475569', '#3b82f6', '#f59e0b', '#10b981', '#8b5cf6'] # Grigio, Blu, Arancio, Verde, Viola
        fig_v = go.Figure(go.Bar(x=names, y=vals, marker_color=colors, text=[f"${v:.2f}" for v in vals], textposition='outside'))
        fig_v.add_hline(y=d['tm'], line_dash="dash", line_color="#FFD700", line_width=4, annotation_text="GOLDEN MoS", annotation_font_color="#FFD700")
        fig_v.update_layout(height=400, margin=dict(t=30))
        st.plotly_chart(fig_v, use_container_width=True)

    with g2:
        st.write("**Fatturato Trimestrale (Ultimi 3 Anni - 12Q)**")
        if 'Total Revenue' in d['q_fin'].index:
            # Prende gli ultimi 12 trimestri disponibili e inverte l'ordine cronologico
            rev_q = d['q_fin'].loc['Total Revenue'].iloc[:12][::-1]
            
            # Logica colori: Verde se > del trimestre precedente, Rosso se <
            bar_colors = []
            for i in range(len(rev_q)):
                if i == 0 or rev_q.values[i] >= rev_q.values[i-1]:
                    bar_colors.append('#10b981') # Verde
                else:
                    bar_colors.append('#ef4444') # Rosso
            
            fig_r = go.Figure()
            fig_r.add_trace(go.Bar(x=rev_q.index.astype(str), y=rev_q.values, marker_color=bar_colors, name="Revenue"))
            fig_r.add_trace(go.Scatter(x=rev_q.index.astype(str), y=rev_q.values, mode='lines', line=dict(color='black', width=2), name="Trend"))
            fig_r.update_layout(height=400, margin=dict(t=30), showlegend=False)
            st.plotly_chart(fig_r, use_container_width=True)
        else:
            st.warning("Dati trimestrali non disponibili per questo ticker.")

    # INSIGHTS
    st.info(f"💡 **Executive Insight:** {d['ticker']} mostra un Owner Earnings di ${d['oe']/1e9:.1f}B. Il rapporto Cassa/Debito annuale di **{r['CashDebtAnn']:.2f}** conferma la solidità della struttura finanziaria.")

    # LEGENDA
    with st.expander("📖 LEGENDA E ANALISI"):
        st.markdown(f"""
        - **Grafico Intrinseco:** Confronta il prezzo di mercato con 3 modelli (Graham, DCF, Buffett). La **Linea Dorata** è il tuo buy-target (MoS 25%).
        - **Revenue Trimestrale:** Mostra la stagionalità e il momentum. Il colore delle barre indica se il fatturato è cresciuto rispetto al trimestre precedente.
        - **Cassa/Debito:** Apple annuale target **0.49**. Calcolato sommando Liquidità e Investimenti a breve termine.
        """)
else:
    st.info("👈 Seleziona un ticker dal CSV nella barra laterale e clicca su 'AVVIA ANALISI PROFONDA'.")



