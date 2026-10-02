
import datetime as dt
import numpy as np
import pandas as pd
import streamlit as st
from pykrx import stock

st.set_page_config(page_title="주가 스캐너", page_icon="📈", layout="wide")

st.markdown("""
<style>
.block-container {max-width: 1100px; padding-top: 1.2rem;}
h1 {letter-spacing:-1px;}
div[data-testid="stMetricValue"] {font-size: 1.35rem;}
.stButton button {border-radius: 12px; height: 3rem; font-weight: 700;}
</style>
""", unsafe_allow_html=True)

st.title("📈 주가 스캐너")
st.caption("KOSPI / KOSDAQ 조건검색 · 휴대폰 브라우저 사용 가능")

@st.cache_data(ttl=900)
def get_market(date, market):
    return stock.get_market_ohlcv_by_ticker(date, market=market)

@st.cache_data(ttl=3600)
def get_history(ticker, start, end):
    return stock.get_market_ohlcv_by_date(start, end, ticker)

@st.cache_data(ttl=3600)
def get_name(ticker):
    return stock.get_market_ticker_name(ticker)

def scan(date, market, min_change, min_value, volume_ratio, ma_period,
         rsi_enabled, rsi_min, rsi_max):
    df = get_market(date, market)
    if df.empty:
        return pd.DataFrame()

    end = pd.Timestamp(date)
    start = (end - pd.Timedelta(days=max(180, ma_period * 6))).strftime("%Y%m%d")
    rows = []

    for ticker, r in df.iterrows():
        close = float(r["종가"])
        change = float(r["등락률"])
        value = float(r["거래대금"])

        if close <= 0 or change < min_change or value < min_value * 1e8:
            continue

        try:
            h = get_history(str(ticker), start, date)
            if len(h) < max(ma_period, 20):
                continue

            close_s = h["종가"].astype(float)
            vol_s = h["거래량"].astype(float)

            ma = close_s.rolling(ma_period).mean().iloc[-1]
            avg_vol = vol_s.iloc[-min(60, len(vol_s)):-1].mean()
            vol_mult = float(vol_s.iloc[-1] / avg_vol) if avg_vol > 0 else np.nan

            # RSI(14)
            delta = close_s.diff()
            gain = delta.clip(lower=0).rolling(14).mean()
            loss = (-delta.clip(upper=0)).rolling(14).mean()
            rs = gain / loss.replace(0, np.nan)
            rsi = float((100 - (100 / (1 + rs))).iloc[-1])

            if close <= ma or np.isnan(vol_mult) or vol_mult < volume_ratio:
                continue
            if rsi_enabled and not (rsi_min <= rsi <= rsi_max):
                continue

            rows.append({
                "종목코드": str(ticker).zfill(6),
                "종목명": get_name(str(ticker)),
                "현재가": int(close),
                "등락률(%)": round(change, 2),
                "거래대금(억원)": round(value / 1e8, 1),
                "거래량배수": round(vol_mult, 2),
                f"MA{ma_period}": round(float(ma), 0),
                "RSI": round(rsi, 1),
            })
        except Exception:
            continue

    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(
        ["등락률(%)", "거래량배수"], ascending=False
    ).reset_index(drop=True)

with st.sidebar:
    st.header("검색 조건")
    date = st.date_input("기준일", dt.date.today())
    market = st.selectbox("시장", ["KOSPI", "KOSDAQ"])
    min_change = st.number_input("최소 등락률 (%)", 0.0, 30.0, 3.0, 0.5)
    min_value = st.number_input("최소 거래대금 (억원)", 0.0, 10000.0, 50.0, 10.0)
    volume_ratio = st.number_input("최소 거래량 배수", 0.5, 20.0, 2.0, 0.5)
    ma_period = st.selectbox("이동평균선", [5, 10, 20, 60], index=2)

    st.divider()
    rsi_enabled = st.checkbox("RSI 조건 사용", False)
    rsi_min = st.number_input("RSI 최소", 0.0, 100.0, 50.0, 5.0)
    rsi_max = st.number_input("RSI 최대", 0.0, 100.0, 80.0, 5.0)

    scan_button = st.button("🔎 종목 스캔", type="primary", use_container_width=True)

if scan_button:
    if rsi_min > rsi_max:
        st.error("RSI 최소값은 최대값보다 클 수 없습니다.")
        st.stop()

    with st.spinner("시장 데이터를 가져와 조건을 검사하고 있습니다..."):
        result = scan(
            date.strftime("%Y%m%d"), market, min_change, min_value,
            volume_ratio, ma_period, rsi_enabled, rsi_min, rsi_max
        )

    c1, c2, c3 = st.columns(3)
    c1.metric("검색 종목", f"{len(result)}개")
    c2.metric("시장", market)
    c3.metric("기준일", date.strftime("%Y-%m-%d"))

    if result.empty:
        st.warning("조건에 맞는 종목이 없습니다. 조건을 조금 완화해 보세요.")
    else:
        st.subheader("검색 결과")
        st.dataframe(result, use_container_width=True, hide_index=True)
        csv = result.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
        st.download_button(
            "📥 검색 결과 CSV 저장",
            csv,
            "stock_scanner_result.csv",
            "text/csv",
            use_container_width=True,
        )
else:
    st.subheader("빠른 시작")
    st.info("기본 조건은 '등락률 +3% / 거래대금 50억원 / 거래량 2배 / 이동평균선 위'입니다.")
    st.markdown("""
    **휴대폰에서 사용하는 방법**
    1. 웹앱을 인터넷에 배포합니다.
    2. 발급된 URL을 휴대폰에서 엽니다.
    3. 조건을 선택하고 **종목 스캔**을 누릅니다.
    """)

st.divider()
st.caption("⚠️ 투자 참고용 스캐너입니다. 매매 추천이나 수익을 보장하지 않습니다.")
