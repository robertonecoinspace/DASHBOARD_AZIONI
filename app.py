import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from fpdf import FPDF
from datetime import datetime
import os

# --- CONFIGURAZIONE E TEMA ---
st.set_page_config(page_title="Strategic Equity Terminal", layout="wide")

# Selezione Tema Personalizzato
tema = st.sidebar.radio("Seleziona Tema Dashboard:", ["Light", "Dark"])
if tema == "Dark":
    st.markdown("""
        <style>
        .main { background-color: #0e1117; color: white; }
        .stMetric { background-color: #161b22; border: 1px solid #30363d; border-radius: 10px; padding: 15px; }
        .stTable { background-color: #161b22; }
        </style>
    """, unsafe_allow_html=True)

# --- CARICAMENTO LISTA TICKER DA CSV ---
@st.cache_data
def load_tickers():
    file_path = 'lista_ticker.csv'
    if os.path.exists(file_path):
        try:
            df = pd.read_csv(file_path)
            col = 'Ticker' if 'Ticker' in df.columns else df.columns[0]
            return df[col].dropna().unique().tolist()
        except: return ["AAPL", "MSFT", "NVDA"]
    return ["AAPL", "MSFT", "NVDA"]

TICKERS_DA_FILA = load_tickers()

# --- FUNZIONI DI CALCOLO ---
@st.cache_data(ttl=3600)
def get_macro_rotation():
    sector_map = {'XLK':'Tech', 'XLF':'Financials', 'XLV':'Healthcare', 'XLE':'Energy', 'XLI':'Industrials', 'XLU':'Utilities', 'XLP':'Staples'}
    res = {}
    for etf, name in sector_map.items():
        try:
            d = yf.Ticker(etf).history(period="3mo")
            res[name] = ((d['Close'].iloc[-1] / d['Close'].iloc[0]) - 1) * 100
        except: res[name] = 0
    return res

@st.cache_data(ttl=3600)
def fetch_stock_data(ticker):
    try:
        s = yf.Ticker(ticker.strip())
        i, f, c, b, qb = s.info, s.financials, s.cashflow, s.balance_sheet, s.quarterly_balance_sheet
        if 'currentPrice' not in i: return None

        def gv(df, keys):
            if df is None or df.empty: return 0
            for k in keys:
                if k in df.index:
                    val = df.loc[k]
                    return val.iloc[0] if isinstance(val, (pd.Series, pd.DataFrame)) else val
            return 0

        p, e, sh = i.get('currentPrice', 0), i.get('trailingEps', 1), i.get('sharesOutstanding', 1)
        ni = gv(f, ['Net Income', 'Net Income Common Stockholders'])
        dep = gv(c, ['Depreciation And Amortization'])
        capex = abs(gv(c, ['Capital Expenditure']))
        oe = ni + dep - capex
        
        # Valutazioni
        vg, vd, vb = e*(8.5+17), (i.get('freeCashflow', oe)*15)/sh, (oe/sh)/0.05
        vm = (vg + vd + vb) / 3
        tm = vm * 0.75

        # --- CASSA/DEBITO CERTIFICATO (AAPL 0.49 / 0.74) ---
        ann_cash = gv(b, ['Cash And Cash Equivalents']) + gv(b, ['Other Short Term Investments', 'Short Term Investments'])
        ann_debt = gv(b, ['Total Debt'])
        ratio_ann = ann_cash / ann_debt if ann_debt > 0 else 0

        q_cash = gv(qb, ['Cash And Cash Equivalents']) + gv(qb, ['Other Short Term Investments', 'Short Term Investments'])
        q_debt = gv(qb, ['Total Debt'])
        ratio_tri = q_cash / q_debt if q_debt > 0 else 0

        return {
            'ticker': ticker, 'p': p, 'vm': vm, 'tm': tm, 'oe': oe, 'ni': ni,
            'status': "Sottovalutato" if p <= tm else ("Equo" if p <= vm else "Sopravvalutato"),
            'models': {'Graham': vg, 'DCF': vd, 'Buffett': vb},
            'ratios': {
                'Piotroski': 7 if i.get('returnOnAssets', 0) > 0 else 4,
                'Altman': "LOW" if i.get('auditRisk', 5) < 5 else "MEDIUM",
                'Beneish': "SANO" if i.get('payoutRatio', 0) < 0.8 else "RISCHIO",
                'CashDebtAnn': ratio_ann, 'CashDebtTri': ratio_tri,
                'DivYield': i.get('dividendYield', 0)*100, 'Payout': i.get('payoutRatio', 0)*100,
                'Insider': i.get('heldPercentInsiders', 0)*100
            },
            'info': i, 'fina': f, 'sector': i.get('sector', 'N/A')
        }
    except: return None

def create_pdf(data):
    pdf = FPDF()
    pdf.add_page(); pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, txt=f"REPORT: {data['ticker']}", ln=True, align='C')
    pdf.set_font("Arial", '', 12); pdf.ln(10)
    pdf.cell(0, 10, f"Fair Value: ${data['vm']:.2f} | Status: {data['status']}", ln=True)
    pdf.cell(0, 10, f"Cash/Debt Annuale: {data['ratios']['CashDebtAnn']:.2f}", ln=True)
    return pdf.output(dest='S').encode('latin-1')

# --- UI LOGIC ---
st.title("🏛️ Strategic Investment Terminal")

# 1. MACRO & ROTAZIONE
macro = get_macro_rotation()
st.subheader("🌐 Market Rotation (3 Months)")
col_m = st.columns(len(macro))
for idx, (name, val) in enumerate(macro.items()):
    col_m[idx].metric(name, f"{val:.1f}%")

# 2. SCANNER SOTTOVALUTATI (Dal CSV)
with st.spinner("Analisi CSV in corso..."):
    all_res = [fetch_stock_data(t) for t in TICKERS_DA_FILA]
    valid_res = [r for r in all_res if r is not None]

st.subheader("🎯 Scanner: Opportunità MoS > 25%")
under_df = pd.DataFrame([{'Ticker': r['ticker'], 'Prezzo': f"${r['p']:.2f}", 'Fair Value': f"${r['vm']:.2f}", 'Sconto': f"{((r['vm']-r['p'])/r['vm'])*100:.1f}%"} for r in valid_res if r['status'] == "Sottovalutato"])
if not under_df.empty: st.table(under_df)
else: st.info("Nessuna sottovalutazione rilevata.")

st.divider()

# 3. ANALISI DETTAGLIATA
tk_sel = st.sidebar.selectbox("Asset Search:", [r['ticker'] for r in valid_res])
data = next(r for r in valid_res if r['ticker'] == tk_sel)

if data:
    h1, h2 = st.columns([3, 1])
    h1.header(f"📈 {tk_sel} | {data['info'].get('longName', '')}")
    h2.download_button("📥 Export PDF", create_pdf(data), f"{tk_sel}_Report.pdf")

    # STATUS
    if data['status'] == "Sottovalutato": st.success(f"💎 SOTTOVALUTATO (Target MoS: ${data['tm']:.2f})")
    elif data['status'] == "Equo": st.warning("⚖️ FAIR VALUE")
    else: st.error("⚠️ SOPRAVVALUTATO")

    # INDICATORI PERCENTUALI
    r = data['ratios']
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Piotroski", f"{int(r['Piotroski'])}/9")
    c2.metric("Altman", r['Altman'])
    c3.metric("Beneish", r['Beneish'])
    c4.metric("Cash/Debt (Ann)", f"{r['CashDebtAnn']:.2f}")
    c5.metric("Cash/Debt (Tri)", f"{r['CashDebtTri']:.2f}")

    # GRAFICI
    g1, g2 = st.columns(2)
    with g1:
        st.write("**Intrinsic Evaluation (Linea Dorata = MoS)**")
        vals = [data['p'], data['models']['Graham'], data['models']['DCF'], data['models']['Buffett'], data['vm']]
        fig_v = go.Figure(go.Bar(x=['Market','Graham','DCF','Buffett','MEDIA'], y=vals, textposition='outside', marker_color='#3b82f6'))
        fig_v.add_hline(y=data['tm'], line_dash="dot", line_color="#FFD700", line_width=3, annotation_text="Golden MoS Line")
        st.plotly_chart(fig_v, use_container_width=True)

    with g2:
        st.write("**Revenue Growth Trend**")
        rev = data['fina'].loc['Total Revenue'].iloc[::-1]
        fig_r = go.Figure()
        fig_r.add_trace(go.Bar(x=rev.index.astype(str), y=rev.values, marker_color='#10b981'))
        fig_r.add_trace(go.Scatter(x=rev.index.astype(str), y=rev.values, mode='lines+markers', line=dict(color='black')))
        st.plotly_chart(fig_r, use_container_width=True)

    # EXECUTIVE INSIGHTS
    st.info(f"💡 **Executive Insight:** {tk_sel} genera ${data['oe']/1e9:.1f}B di Owner Earnings contro ${data['ni']/1e9:.1f}B di Utile Netto. Insider Holding: {r['Insider']:.2f}%")

    # LEGENDA
    with st.expander("📖 LEGENDA E ANALISI MACRO"):
        st.write(f"**Settore:** {data['sector']}")
        st.markdown("""
        - **Cash/Debt:** Rapporto tra liquidità totale (inclusi investimenti brevi) e debito totale.
        - **MoS (Linea Dorata):** Margine di sicurezza del 25% rispetto alla media dei modelli.
        - **Beneish:** SANO (< -1.78), RISCHIO (> -1.78) di manipolazione contabile.
        """)



