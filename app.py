import datetime as dt
import re
from typing import Any

import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="이유진의 주식분석 대시보드", page_icon="📈", layout="wide")

# ── 고급스러운 파스텔 테마 ──────────────────────────────────────────────
st.markdown("""
<style>
    .stApp {
        background: linear-gradient(135deg, #F8F5FF 0%, #F4FAF8 48%, #FFF8F0 100%);
        color: #303548;
    }
    .main .block-container {
        padding-top: 2.2rem;
        padding-bottom: 2rem;
        max-width: 1450px;
    }
    h1, h2, h3 {
        color: #303548 !important;
        letter-spacing: -0.03em;
    }
    h1 { font-weight: 750 !important; }
    h2, h3 { font-weight: 650 !important; }
    .stCaption, .stMarkdown p { color: #667085; }

    /* Metric 카드 */
    div[data-testid="stMetric"] {
        background: rgba(255, 255, 255, 0.78);
        border: 1px solid rgba(185, 178, 214, 0.42);
        border-radius: 18px;
        padding: 16px 18px;
        box-shadow: 0 6px 20px rgba(73, 67, 104, 0.07);
    }
    div[data-testid="stMetricLabel"] { color: #73788A !important; }
    div[data-testid="stMetricValue"] { color: #34394D !important; font-weight: 700; }

    /* 사이드바 */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #F0ECFA 0%, #EAF5F2 100%);
        border-right: 1px solid #DDD8EA;
    }
    section[data-testid="stSidebar"] h2,
    section[data-testid="stSidebar"] h3,
    section[data-testid="stSidebar"] p,
    section[data-testid="stSidebar"] label { color: #41465A !important; }

    /* 입력창 */
    div[data-baseweb="input"] > div,
    div[data-baseweb="select"] > div {
        background-color: rgba(255,255,255,0.86);
        border-color: #D5D0E2;
        border-radius: 12px;
    }

    /* 버튼 */
    .stButton > button {
        background: #DCCFF5;
        color: #38344A;
        border: 1px solid #C9B9EA;
        border-radius: 12px;
        font-weight: 650;
        transition: all 0.2s ease;
    }
    .stButton > button:hover {
        background: #CFC0EE;
        border-color: #B9A7E2;
        color: #29253A;
    }

    /* 표 */
    div[data-testid="stDataFrame"] {
        border: 1px solid #DDD8EA;
        border-radius: 14px;
        overflow: hidden;
        box-shadow: 0 5px 18px rgba(73, 67, 104, 0.05);
    }

    /* 알림 박스 */
    div[data-testid="stAlert"] { border-radius: 14px; }

    /* 구분선 */
    hr { border-color: #DDD8EA; }
</style>
""", unsafe_allow_html=True)

KIWOOM_MOCK_URL = "https://mockapi.kiwoom.com"
KRX_URL = "https://data-dbg.krx.co.kr/svc/apis"


def secret(name: str) -> str:
    try:
        value = st.secrets[name]
    except Exception:
        value = ""
    return str(value).strip() if value else ""

KRX_API_KEY = secret("KRX_API_KEY")
KIWOOM_APP_KEY = secret("KIWOOM_APP_KEY")
KIWOOM_APP_SECRET = secret("KIWOOM_APP_SECRET")


def clean_number(value: Any) -> float:
    if value is None:
        return 0.0
    text = str(value).strip().replace(",", "")
    if text in {"", "-", "--"}:
        return 0.0
    text = re.sub(r"[^0-9+\-.]", "", text)
    try:
        return float(text)
    except ValueError:
        return 0.0


def money(value: Any) -> str:
    return f"{clean_number(value):,.0f}원"


def pct(value: Any) -> str:
    return f"{clean_number(value):,.2f}%"


def require_secrets() -> bool:
    missing = []
    if not KRX_API_KEY:
        missing.append("KRX_API_KEY")
    if not KIWOOM_APP_KEY:
        missing.append("KIWOOM_APP_KEY")
    if not KIWOOM_APP_SECRET:
        missing.append("KIWOOM_APP_SECRET")
    if missing:
        st.error("API 인증정보가 없습니다: " + ", ".join(missing))
        st.markdown("**Streamlit Community Cloud → 앱 Settings → Secrets**에 API 인증정보를 입력하세요.")
        return False
    return True


@st.cache_data(ttl=60 * 60 * 23, show_spinner=False)
def kiwoom_token(app_key: str, app_secret: str) -> str:
    response = requests.post(
        f"{KIWOOM_MOCK_URL}/oauth2/token",
        headers={"Content-Type": "application/json;charset=UTF-8"},
        json={"grant_type": "client_credentials", "appkey": app_key, "secretkey": app_secret},
        timeout=15,
    )
    response.raise_for_status()
    data = response.json()
    if data.get("return_code") not in (None, 0):
        raise RuntimeError(data.get("return_msg", "키움 토큰 발급 실패"))
    token = data.get("token")
    if not token:
        raise RuntimeError("키움 API가 접근토큰을 반환하지 않았습니다.")
    return token


def kiwoom_post(token: str, api_id: str, payload: dict) -> dict:
    response = requests.post(
        f"{KIWOOM_MOCK_URL}/api/dostk/acnt" if api_id.startswith(("ka000", "kt000")) else f"{KIWOOM_MOCK_URL}/api/dostk/stkinfo",
        headers={
            "Content-Type": "application/json;charset=UTF-8",
            "authorization": f"Bearer {token}",
            "api-id": api_id,
            "cont-yn": "N",
            "next-key": "",
        },
        json=payload,
        timeout=15,
    )
    response.raise_for_status()
    data = response.json()
    if data.get("return_code") not in (None, 0):
        raise RuntimeError(f"{data.get('return_code')}: {data.get('return_msg', '키움 API 오류')}")
    return data


def get_account_number(token: str) -> str:
    data = kiwoom_post(token, "ka00001", {})
    return str(data.get("acctNo") or data.get("acct_no") or "")


def get_deposit(token: str) -> dict:
    return kiwoom_post(token, "kt00001", {"qry_tp": "2"})


def get_account_eval(token: str) -> dict:
    return kiwoom_post(token, "kt00004", {"qry_tp": "0", "dmst_stex_tp": "KRX"})


def get_stock_info(token: str, code: str) -> dict:
    response = requests.post(
        f"{KIWOOM_MOCK_URL}/api/dostk/stkinfo",
        headers={
            "Content-Type": "application/json;charset=UTF-8",
            "authorization": f"Bearer {token}",
            "api-id": "ka10001",
            "cont-yn": "N",
            "next-key": "",
        },
        json={"stk_cd": code},
        timeout=15,
    )
    response.raise_for_status()
    data = response.json()
    if data.get("return_code") not in (None, 0):
        raise RuntimeError(f"{data.get('return_code')}: {data.get('return_msg', '종목 조회 실패')}")
    return data


@st.cache_data(ttl=60 * 30, show_spinner=False)
def krx_index(api_key: str, api_id: str, start_date: str, days: int = 15) -> pd.DataFrame:
    rows = []
    start = dt.datetime.strptime(start_date, "%Y%m%d").date()
    for offset in range(days):
        day = start - dt.timedelta(days=offset)
        if day.weekday() >= 5:
            continue
        response = requests.get(
            f"{KRX_URL}/idx/{api_id}",
            params={"basDd": day.strftime("%Y%m%d")},
            headers={"AUTH_KEY": api_key},
            timeout=15,
        )
        if response.status_code != 200:
            continue
        data = response.json().get("OutBlock_1", [])
        if data:
            rows.extend(data)
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["BAS_DD"], format="%Y%m%d", errors="coerce")
    df["close"] = df["CLSPRC_IDX"].map(clean_number)
    df["change_pct"] = df["FLUC_RT"].map(clean_number)
    return df.sort_values("date")


def latest_krx_row(df: pd.DataFrame, preferred_name: str) -> pd.Series | None:
    if df.empty:
        return None
    subset = df[df["IDX_NM"].astype(str).str.contains(preferred_name, na=False)]
    if subset.empty:
        subset = df
    return subset.sort_values("date").iloc[-1]


st.title("📈 이유진의 주식분석 대시보드")
st.caption("KRX 시장 데이터 + 키움증권 모의투자 계좌를 한 화면에서 확인합니다. 조회 전용 버전입니다.")

if not require_secrets():
    st.stop()

with st.sidebar:
    st.header("설정")
    stock_code = st.text_input("분석할 종목코드", value="005930", max_chars=6).strip()
    if stock_code and not stock_code.isdigit():
        st.warning("종목코드는 숫자 6자리로 입력하세요. 예: 005930")
    refresh = st.button("🔄 데이터 새로고침", use_container_width=True)
    if refresh:
        st.cache_data.clear()
        st.rerun()
    st.divider()
    st.write("**인증 환경:** 키움 모의투자")
    st.write("**주문 기능:** 비활성화")

try:
    token = kiwoom_token(KIWOOM_APP_KEY, KIWOOM_APP_SECRET)
except Exception as exc:
    st.error(f"키움 API 인증 실패: {exc}")
    st.stop()

today = dt.date.today().strftime("%Y%m%d")
try:
    kospi_df = krx_index(KRX_API_KEY, "kospi_dd_trd", today, 20)
    kosdaq_df = krx_index(KRX_API_KEY, "kosdaq_dd_trd", today, 20)
    kospi = latest_krx_row(kospi_df, "KOSPI")
    kosdaq = latest_krx_row(kosdaq_df, "KOSDAQ")
except Exception as exc:
    kospi_df = kosdaq_df = pd.DataFrame()
    kospi = kosdaq = None
    st.warning(f"KRX 데이터 조회 중 오류가 발생했습니다: {exc}")

st.subheader("시장")
c1, c2, c3, c4 = st.columns(4)
if kospi is not None:
    c1.metric("KOSPI", f"{kospi['close']:,.2f}", f"{kospi['change_pct']:.2f}%")
else:
    c1.metric("KOSPI", "조회 실패")
if kosdaq is not None:
    c2.metric("KOSDAQ", f"{kosdaq['close']:,.2f}", f"{kosdaq['change_pct']:.2f}%")
else:
    c2.metric("KOSDAQ", "조회 실패")
if kospi is not None:
    c3.metric("KOSPI 거래대금", money(kospi["ACC_TRDVAL"]))
if kosdaq is not None:
    c4.metric("KOSDAQ 거래대금", money(kosdaq["ACC_TRDVAL"]))

st.subheader("내 모의투자 계좌")
try:
    account_no = get_account_number(token)
    deposit = get_deposit(token)
    evaluation = get_account_eval(token)

    deposit_amt = clean_number(deposit.get("entr"))
    orderable_amt = clean_number(deposit.get("ord_alow_amt") or deposit.get("ord_alowa"))
    total_assets = clean_number(evaluation.get("prsm_dpst_aset_amt") or evaluation.get("aset_evlt_amt"))
    eval_amt = clean_number(evaluation.get("tot_est_amt"))
    profit_rt = clean_number(evaluation.get("lspft_rt"))

    a1, a2, a3, a4, a5 = st.columns(5)
    a1.metric("계좌번호", account_no or "조회됨")
    a2.metric("예수금", money(deposit_amt))
    a3.metric("투자가능금액", money(orderable_amt))
    a4.metric("평가금액", money(eval_amt if eval_amt else total_assets))
    a5.metric("누적손익률", pct(profit_rt))

    holdings = evaluation.get("stk_acnt_evlt_prst", [])
    if holdings:
        rows = []
        for item in holdings:
            qty = clean_number(item.get("rmnd_qty"))
            if qty <= 0:
                continue
            rows.append({
                "종목코드": str(item.get("stk_cd", "")).lstrip("AJQ"),
                "종목명": item.get("stk_nm", ""),
                "보유수량": int(qty),
                "평균단가": clean_number(item.get("avg_prc")),
                "현재가": clean_number(item.get("cur_prc")),
                "평가금액": clean_number(item.get("evlt_amt")),
                "평가손익": clean_number(item.get("pl_amt")),
                "수익률(%)": clean_number(item.get("pl_rt")),
            })
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.info("현재 보유종목이 없습니다.")
    else:
        st.info("현재 보유종목이 없습니다.")
except Exception as exc:
    st.error(f"키움 계좌 조회 실패: {exc}")

st.subheader("종목 분석")
if stock_code and len(stock_code) == 6 and stock_code.isdigit():
    try:
        info = get_stock_info(token, stock_code)
        name = info.get("stk_nm", stock_code)
        current = clean_number(info.get("cur_prc"))
        change_pct = clean_number(info.get("flu_rt") or info.get("base_comp_chgr"))
        volume = clean_number(info.get("trde_qty"))

        s1, s2, s3, s4 = st.columns(4)
        s1.metric("종목", f"{name} ({stock_code})")
        s2.metric("현재가", money(current))
        s3.metric("등락률", pct(change_pct))
        s4.metric("거래량", f"{volume:,.0f}")

        with st.expander("키움 API 원본 응답 보기"):
            st.json(info)
    except Exception as exc:
        st.warning(f"종목 조회 실패: {exc}")
else:
    st.info("사이드바에 6자리 종목코드를 입력하세요.")

left, right = st.columns(2)
with left:
    st.markdown("**KOSPI 최근 데이터**")
    if not kospi_df.empty:
        chart = kospi_df[["date", "close"]].drop_duplicates("date").set_index("date")
        st.line_chart(chart)
with right:
    st.markdown("**KOSDAQ 최근 데이터**")
    if not kosdaq_df.empty:
        chart = kosdaq_df[["date", "close"]].drop_duplicates("date").set_index("date")
        st.line_chart(chart)

st.caption("※ 이 앱은 현재 조회 기능만 제공합니다. 실제 주문 API는 포함하지 않았습니다.")
