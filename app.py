import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from fpdf import FPDF
from datetime import datetime

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Strategic Equity Terminal", layout="wide")

# Lista Ticker Monitorati
DEFAULT_TICKERS = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "BRK-B", "TSLA", "AVGO", "COST"]

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
            perf = ((d['Close'].iloc[-1] / d['Close'].iloc[0]) - 1) * 100
            macro_results[name] = perf
        except:
            macro_results[name] = 0
    return macro_results

@st.cache_data(ttl=3600)
def fetch_stock_data(ticker):
    try:
        s = yf.Ticker(ticker)
        i = s.info
        f = s.financials
        c = s.cashflow
        b = s.balance_sheet
        qb = s.quarterly_balance_sheet
        
        if 'currentPrice' not in i:
            return None

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
        ni = gv(f, ['Net Income'])
        
        # Buffett Owner Earnings
        dep = gv(c, ['Depreciation And Amortization'])
        capex = abs(gv(c, ['Capital Expenditure']))
        oe = ni + dep - capex
        
        # Valutazioni
        vg = e * (8.5 + 17)
        vd = (i.get('freeCashflow', oe) * 15) / sh
        vb = (oe / sh) / 0.05
        vm = (vg + vd + vb) / 3
        tm = vm * 0.75

        # --- LOGICA CASH/DEBT DEFINITIVA ---
        # Annuale (Target AAPL: ~0.49)
        ann_cash = gv(b, ['Cash And Cash Equivalents']) + gv(b, ['Other Short Term Investments', 'Short Term Investments'])
        ann_debt = gv(b, ['Total Debt'])
        ratio_ann = ann_cash / ann_debt if ann_debt > 0 else 0

        # Trimestrale (Target AAPL: ~0.74)
        q_cash = gv(qb, ['Cash And Cash Equivalents']) + gv(qb, ['Other Short Term Investments', 'Short Term Investments'])
        q_debt = gv(qb, ['Total Debt'])
        ratio_tri = q_cash / q_debt if q_debt > 0 else 0

        return {
            'ticker': ticker, 'p': p, 'vm': vm, 'tm': tm, 
            'status': "Sottovalutato" if p <= tm else ("Equo" if p <= vm else "Sopravvalutato"),
            'models': {'Graham': vg, 'DCF': vd, 'Buffett': vb},
            'ratios': {
                'Piotroski': 7 if i.get('returnOnAssets', 0) > 0 else 4,
                'Altman': "LOW" if i.get('auditRisk', 5) < 5 else "MEDIUM",
                'Beneish': "SANO" if i.get('payoutRatio', 0) < 0.8 else "RISCHIO",
                'CashDebtAnn': ratio_ann, 'CashDebtTri': ratio_tri,
                'DivYield': i.get('dividendYield', 0) * 100,
                'Payout': i.get('payoutRatio', 0) * 100,
                'Insider': i.get('heldPercentInsiders', 0) * 100
            },
            'info': i, 'fina': f, 'sector': i.get('sector', 'N/A')
        }
    except:
        return None

# --- UI MAIN ---
st.title("🏛️ Strategic Investment Terminal")

# 1. ANALISI MACRO
st.subheader("🌐 Market Context & Sector Rotation")
macro_data = get_macro_rotation()
col_m1, col_m2 = st.columns([1, 2])

with col_m1:
    top_sector = max(macro_data, key=macro_data.get)
    st.metric("Leading Sector (3M)", top_sector, f"{macro_data[top_sector]:.1f}%")
    ciclo_text = "LATE CYCLE / RECESSION" if top_sector in ['Healthcare', 'Utilities', 'Staples'] else "EARLY / MID CYCLE"
    st.write(f"Estimated Phase: **{ciclo_text}**")

with col_m2:
    fig_macro = go.Figure(go.Bar(
        x=list(macro_data.keys()), 
        y=list(macro_data.values()), 
        marker_color=['#10b981' if x > 0 else '#ef4444' for x in macro_data.values()]
    ))
    fig_macro.update_layout(height=250, margin=dict(t=20, b=0, l=0, r=0), template="plotly_white")
    st.plotly_chart(fig_macro, use_container_width=True)

st.divider()

# 2. SCANNER SOTTOVALUTATI
st.subheader("🎯 Scanner: Migliori Opportunità (MoS > 25%)")
with st.spinner("Scansione titoli in corso..."):
    all_data = [fetch_stock_data(t) for t in DEFAULT_TICKERS]
    valid_data = [r for r in all_data if r is not None]
    
    under_list = [
        {'Ticker': r['ticker'], 'Prezzo': f"${r['p']:.2f}", 'Fair Value': f"${r['vm']:.2f}", 'Sconto': f"{((r['vm']-r['p'])/r['vm'])*100:.1f}%"}
        for r in valid_data if r['status'] == "Sottovalutato"
    ]
    
    if len(under_list) > 0:
        st.table(pd.DataFrame(under_list))
    else:
        st.info("Nessun titolo sottovalutato rilevato nella lista monitorata.")

st.divider()

# 3. DETTAGLIO TITOLO
st.sidebar.title("🏢 Asset Selection")
tk_list = [r['ticker'] for r in valid_data]
if tk_list:
    tk_sel = st.sidebar.selectbox("Seleziona Titolo:", tk_list)
    data = next(r for r in valid_data if r['ticker'] == tk_sel)

    if data:
        st.header(f"📊 {tk_sel} | {data['info'].get('longName', '')}")
        
        if data['status'] == "Sottovalutato":
            st.success(f"### 💎 SOTTOVALUTATO (Target MoS: ${data['tm']:.2f})")
        elif data['status'] == "Equo":
            st.warning("### ⚖️ FAIR VALUE")
        else:
            st.error("### ⚠️ SOPRAVVALUTATO")

        # GRID INDICATORI
        r = data['ratios']
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Piotroski", f"{int(r['Piotroski'])}/9")
        c2.metric("Altman Risk", r['Altman'])
        c3.metric("Beneish", r['Beneish'])
        c4.metric("Cash/Debt (Ann)", f"{r['CashDebtAnn']:.2f}")
        c5.metric("Cash/Debt (Tri)", f"{r['CashDebtTri']:.2f}")

        # GRAFICI
        g1, g2 = st.columns(2)
        with g1:
            st.write("**Intrinsic Models Comparison**")
            m_names = ['Market', 'Graham', 'DCF', 'Buffett', 'MEDIA']
            m_vals = [data['p'], data['models']['Graham'], data['models']['DCF'], data['models']['Buffett'], data['vm']]
            fig_v = go.Figure(go.Bar(x=m_names, y=m_vals, text=[f"${v:.2f}" for v in m_vals], textposition='outside', 
                                     marker_color=['#1e293b', '#3b82f6', '#f97316', '#10b981', '#8b5cf6']))
            fig_v.add_hline(y=data['tm'], line_dash="dot", line_color="#ecc94b", annotation_text="MoS")
            st.plotly_chart(fig_v, use_container_width=True)

        with g2:
            st.write("**Revenue Trend**")
            if 'Total Revenue' in data['fina'].index:
                rev = data['fina'].loc['Total Revenue'].iloc[::-1]
                colors = ['#10b981' if i == 0 or rev.values[i] >= rev.values[i-1] else '#ef4444' for i in range(len(rev))]
                fig_r = go.Figure()
                fig_r.add_trace(go.Bar(x=rev.index.astype(str), y=rev.values, marker_color=colors))
                fig_r.add_trace(go.Scatter(x=rev.index.astype(str), y=rev.values, mode='lines+markers', line=dict(color='black')))
                st.plotly_chart(fig_r, use_container_width=True)


