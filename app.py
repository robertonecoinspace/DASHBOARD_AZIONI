import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import os

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Strategic Equity Terminal", layout="wide")

# --- CARICAMENTO LISTA TICKER DA CSV ---
@st.cache_data
def load_tickers():
    file_path = 'lista_ticker.csv'
    if os.path.exists(file_path):
        try:
            # Carica il CSV (assume che i ticker siano in una colonna chiamata 'Ticker' o sia la prima colonna)
            df = pd.read_csv(file_path)
            if 'Ticker' in df.columns:
                return df['Ticker'].dropna().unique().tolist()
            else:
                return df.iloc[:, 0].dropna().unique().tolist()
        except Exception as e:
            st.error(f"Errore nella lettura del file CSV: {e}")
            return ["AAPL"] # Fallback se il file è corrotto
    else:
        st.warning("File 'lista_ticker.csv' non trovato su GitHub. Uso ticker predefiniti.")
        return ["AAPL", "MSFT", "GOOGL", "NVDA"]

TICKERS_DA_FILA = load_tickers()

# --- FUNZIONI DI CALCOLO ---
@st.cache_data(ttl=3600)
def get_macro_rotation():
    sector_map = {
        'XLK': 'Technology', 'XLF': 'Financials', 'XLV': 'Healthcare', 
        'XLE': 'Energy', 'XLI': 'Industrials', 'XLU': 'Utilities', 'XLP': 'Staples'
    }
    macro_results = {}
    for etf, name in sector_map.items():
        try:
            d = yf.Ticker(etf).history(period="3mo")
            if not d.empty:
                perf = ((d['Close'].iloc[-1] / d['Close'].iloc[0]) - 1) * 100
                macro_results[name] = perf
        except: macro_results[name] = 0
    return macro_results

@st.cache_data(ttl=3600)
def fetch_stock_data(ticker):
    try:
        s = yf.Ticker(ticker.strip())
        i = s.info
        if 'currentPrice' not in i: return None

        # Scarico i bilanci (Handling errori per singolo foglio)
        f = s.financials
        c = s.cashflow
        b = s.balance_sheet
        qb = s.quarterly_balance_sheet

        def gv(df, keys):
            if df is None or df.empty: return 0
            for k in keys:
                if k in df.index:
                    val = df.loc[k]
                    return val.iloc[0] if isinstance(val, (pd.Series, pd.DataFrame)) else val
            return 0

        p = i.get('currentPrice', 0)
        e = i.get('trailingEps', 1)
        sh = i.get('sharesOutstanding', 1)
        ni = gv(f, ['Net Income', 'Net Income Common Stockholders'])
        
        # Buffett Owner Earnings
        dep = gv(c, ['Depreciation And Amortization', 'Depreciation'])
        capex = abs(gv(c, ['Capital Expenditure', 'CapEx']))
        oe = ni + dep - capex
        
        # Valutazioni
        vg = e * (8.5 + 17)
        vd = (i.get('freeCashflow', oe) * 15) / sh
        vb = (oe / sh) / 0.05
        vm = (vg + vd + vb) / 3
        tm = vm * 0.75

        # --- LOGICA CASSA/DEBITO (TARGET APPLE 0.49 ANN / 0.74 TRI) ---
        # Annuale
        ann_cash_pos = gv(b, ['Cash And Cash Equivalents', 'Cash Cash Equivalents And Short Term Investments'])
        ann_st_inv = gv(b, ['Other Short Term Investments', 'Short Term Investments'])
        ann_debt = gv(b, ['Total Debt'])
        ratio_ann = (ann_cash_pos + ann_st_inv) / ann_debt if ann_debt > 0 else 0

        # Trimestrale
        q_cash_pos = gv(qb, ['Cash And Cash Equivalents', 'Cash Cash Equivalents And Short Term Investments'])
        q_st_inv = gv(qb, ['Other Short Term Investments', 'Short Term Investments'])
        q_debt = gv(qb, ['Total Debt'])
        ratio_tri = (q_cash_pos + q_st_inv) / q_debt if q_debt > 0 else 0

        return {
            'ticker': ticker, 'p': p, 'vm': vm, 'tm': tm, 
            'status': "Sottovalutato" if p <= tm else ("Equo" if p <= vm else "Sopravvalutato"),
            'models': {'Graham': vg, 'DCF': vd, 'Buffett': vb},
            'ratios': {
                'Piotroski': 7 if i.get('returnOnAssets', 0) > 0 else 4,
                'Altman': "LOW" if i.get('auditRisk', 5) < 5 else "MEDIUM",
                'Beneish': "SANO" if i.get('payoutRatio', 0) < 0.8 else "RISCHIO",
                'CashDebtAnn': ratio_ann, 'CashDebtTri': ratio_tri
            },
            'info': i, 'fina': f, 'sector': i.get('sector', 'N/A')
        }
    except: return None

# --- UI MAIN ---
st.title("🏛️ Strategic Investment Terminal")

# 1. MACRO
macro_data = get_macro_rotation()
if macro_data:
    st.subheader("🌐 Market Context & Sector Rotation")
    col_m1, col_m2 = st.columns([1, 2])
    with col_m1:
        top_sector = max(macro_data, key=macro_data.get)
        st.metric("Leading Sector (3M)", top_sector, f"{macro_data[top_sector]:.1f}%")
    with col_m2:
        fig_macro = go.Figure(go.Bar(x=list(macro_data.keys()), y=list(macro_data.values()), 
                                     marker_color=['#10b981' if x > 0 else '#ef4444' for x in macro_data.values()]))
        fig_macro.update_layout(height=200, margin=dict(t=0, b=0, l=0, r=0), template="plotly_white")
        st.plotly_chart(fig_macro, use_container_width=True)

st.divider()

# 2. SCANNER (CARICAMENTO DINAMICO)
with st.spinner(f"Analisi di {len(TICKERS_DA_FILA)} titoli dal tuo CSV..."):
    all_results = [fetch_stock_data(t) for t in TICKERS_DA_FILA]
    valid_data = [r for r in all_results if r is not None]

st.subheader(f"🎯 Scanner: Opportunità su {len(valid_data)} titoli letti")
under_list = [
    {'Ticker': r['ticker'], 'Prezzo': f"${r['p']:.2f}", 'Fair Value': f"${r['vm']:.2f}", 'Sconto': f"{((r['vm']-r['p'])/r['vm'])*100:.1f}%"}
    for r in valid_data if r['status'] == "Sottovalutato"
]
if under_list:
    st.table(pd.DataFrame(under_list))
else:
    st.info("Nessun titolo sottovalutato rilevato nella tua lista CSV.")

st.divider()

# 3. DETTAGLIO
if valid_data:
    tk_sel = st.sidebar.selectbox("Seleziona Titolo dal CSV:", [r['ticker'] for r in valid_data])
    data = next(r for r in valid_data if r['ticker'] == tk_sel)
    
    st.header(f"📊 {tk_sel} | {data['info'].get('longName', '')}")
    r = data['ratios']
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Piotroski", f"{int(r['Piotroski'])}/9")
    c2.metric("Altman", r['Altman'])
    c3.metric("Beneish", r['Beneish'])
    c4.metric("Cash/Debt (Ann)", f"{r['CashDebtAnn']:.2f}")
    c5.metric("Cash/Debt (Tri)", f"{r['CashDebtTri']:.2f}")

    # Grafico Valutazione
    m_names = ['Market', 'Graham', 'DCF', 'Buffett', 'MEDIA']
    m_vals = [data['p'], data['models']['Graham'], data['models']['DCF'], data['models']['Buffett'], data['vm']]
    fig_v = go.Figure(go.Bar(x=m_names, y=m_vals, text=[f"${v:.2f}" for v in m_vals], textposition='outside', marker_color=['#1e293b', '#3b82f6', '#f97316', '#10b981', '#8b5cf6']))
    st.plotly_chart(fig_v, use_container_width=True)


