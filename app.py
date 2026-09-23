import datetime as dt
import re
from typing import Any

import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="이유진의 주식분석 대시보드", page_icon="📈", layout="wide")

# 고급스러운 파스텔 테마
st.markdown("""
<style>
.stApp { background: linear-gradient(135deg,#F8F5FF 0%,#F4FAF8 48%,#FFF8F0 100%); color:#303548; }
.main .block-container { max-width:1450px; padding-top:2.2rem; }
h1,h2,h3 { color:#303548 !important; letter-spacing:-.03em; }
div[data-testid="stMetric"] { background:rgba(255,255,255,.8); border:1px solid rgba(185,178,214,.42); border-radius:18px; padding:16px 18px; box-shadow:0 6px 20px rgba(73,67,104,.07); }
div[data-testid="stMetricLabel"] { color:#73788A !important; }
div[data-testid="stMetricValue"] { color:#34394D !important; font-weight:700; }
section[data-testid="stSidebar"] { background:linear-gradient(180deg,#F0ECFA 0%,#EAF5F2 100%); border-right:1px solid #DDD8EA; }
.stButton>button { background:#DCCFF5; color:#38344A; border:1px solid #C9B9EA; border-radius:12px; font-weight:650; }
div[data-testid="stDataFrame"] { border:1px solid #DDD8EA; border-radius:14px; overflow:hidden; }
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
    text = re.sub(r"[^0-9+\-.]", "", str(value).replace(",", "").strip())
    try:
        return float(text) if text not in ("", "-") else 0.0
    except ValueError:
        return 0.0


def money(value: Any) -> str:
    return f"{clean_number(value):,.0f}원"


def pct(value: Any) -> str:
    return f"{clean_number(value):,.2f}%"


def require_secrets() -> bool:
    missing = [x for x in ("KRX_API_KEY", "KIWOOM_APP_KEY", "KIWOOM_APP_SECRET") if not secret(x)]
    if missing:
        st.error("API 인증정보가 없습니다: " + ", ".join(missing))
        st.info("Streamlit Community Cloud → Settings → Secrets에 인증정보를 입력하세요.")
        return False
    return True


@st.cache_data(ttl=60 * 60 * 23, show_spinner=False)
def kiwoom_token(app_key: str, app_secret: str) -> str:
    r = requests.post(
        f"{KIWOOM_MOCK_URL}/oauth2/token",
        headers={"Content-Type": "application/json;charset=UTF-8"},
        json={"grant_type": "client_credentials", "appkey": app_key, "secretkey": app_secret},
        timeout=15,
    )
    r.raise_for_status()
    data = r.json()
    if data.get("return_code") not in (None, 0):
        raise RuntimeError(data.get("return_msg", "키움 토큰 발급 실패"))
    if not data.get("token"):
        raise RuntimeError("키움 API가 접근토큰을 반환하지 않았습니다.")
    return data["token"]


def kiwoom_post(token: str, api_id: str, payload: dict) -> dict:
    url = f"{KIWOOM_MOCK_URL}/api/dostk/acnt" if api_id.startswith(("ka000", "kt000")) else f"{KIWOOM_MOCK_URL}/api/dostk/stkinfo"
    r = requests.post(url, headers={"Content-Type":"application/json;charset=UTF-8", "authorization":f"Bearer {token}", "api-id":api_id, "cont-yn":"N", "next-key":""}, json=payload, timeout=15)
    r.raise_for_status()
    data = r.json()
    if data.get("return_code") not in (None, 0):
        raise RuntimeError(f"{data.get('return_code')}: {data.get('return_msg','키움 API 오류')}")
    return data


def get_account_number(token: str) -> str:
    d = kiwoom_post(token, "ka00001", {})
    return str(d.get("acctNo") or d.get("acct_no") or "")


def get_deposit(token: str) -> dict:
    return kiwoom_post(token, "kt00001", {"qry_tp":"2"})


def get_account_eval(token: str) -> dict:
    return kiwoom_post(token, "kt00004", {"qry_tp":"0", "dmst_stex_tp":"KRX"})


def get_stock_info(token: str, code: str) -> dict:
    return kiwoom_post(token, "ka10001", {"stk_cd":code})


@st.cache_data(ttl=60 * 30, show_spinner=False)
def krx_index(api_key: str, api_id: str, days: int = 15):
    """최근 거래일 데이터를 찾고 실패 원인을 반환한다."""
    errors = []
    rows = []
    today = dt.date.today()

    for n in range(days):
        day = today - dt.timedelta(days=n)
        if day.weekday() >= 5:
            continue
        ymd = day.strftime("%Y%m%d")
        url = f"{KRX_URL}/idx/{api_id}"
        try:
            r = requests.get(url, params={"basDd": ymd}, headers={"AUTH_KEY": api_key}, timeout=15)
            if r.status_code != 200:
                detail = r.text[:500].replace("\n", " ")
                errors.append(f"{ymd}: HTTP {r.status_code} / {detail}")
                continue
            try:
                data = r.json()
            except ValueError:
                errors.append(f"{ymd}: JSON 응답이 아닙니다. / {r.text[:300]}")
                continue
            day_rows = data.get("OutBlock_1", [])
            if isinstance(day_rows, list) and day_rows:
                rows.extend(day_rows)
        except requests.RequestException as e:
            errors.append(f"{ymd}: 네트워크 오류 / {e}")

    df = pd.DataFrame(rows)
    if df.empty:
        return df, "\n".join(errors[-5:]) or "최근 거래일의 KRX 데이터가 없습니다."

    required = {"BAS_DD", "CLSPRC_IDX", "FLUC_RT"}
    missing = required - set(df.columns)
    if missing:
        return pd.DataFrame(), f"KRX 응답 필드 누락: {', '.join(sorted(missing))}"

    df["date"] = pd.to_datetime(df["BAS_DD"], format="%Y%m%d", errors="coerce")
    df["close"] = df["CLSPRC_IDX"].map(clean_number)
    df["change_pct"] = df["FLUC_RT"].map(clean_number)
    df = df.dropna(subset=["date"]).sort_values("date")
    return df, ""


def latest_row(df: pd.DataFrame, keyword: str):
    if df.empty:
        return None
    if "IDX_NM" in df.columns:
        x = df[df["IDX_NM"].astype(str).str.contains(keyword, case=False, na=False)]
        if not x.empty:
            return x.iloc[-1]
    return df.iloc[-1]


st.title("📈 이유진의 주식분석 대시보드")
st.caption("KRX 시장 데이터 + 키움증권 모의투자 계좌 | 조회 전용")

if not require_secrets():
    st.stop()

with st.sidebar:
    st.header("설정")
    stock_code = st.text_input("분석할 종목코드", "005930", max_chars=6).strip()
    if st.button("🔄 데이터 새로고침", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    st.divider()
    st.write("인증 환경: **키움 모의투자**")
    st.write("주문 기능: **비활성화**")

# 키움 인증
try:
    token = kiwoom_token(KIWOOM_APP_KEY, KIWOOM_APP_SECRET)
except Exception as e:
    st.error(f"키움 API 인증 실패: {e}")
    st.stop()

# KRX 조회
kospi_df, kospi_error = krx_index(KRX_API_KEY, "kospi_dd_trd")
kosdaq_df, kosdaq_error = krx_index(KRX_API_KEY, "kosdaq_dd_trd")
kospi = latest_row(kospi_df, "KOSPI")
kosdaq = latest_row(kosdaq_df, "KOSDAQ")

st.subheader("시장")
c1, c2, c3, c4 = st.columns(4)
c1.metric("KOSPI", f"{kospi['close']:,.2f}" if kospi is not None else "조회 실패", f"{kospi['change_pct']:.2f}%" if kospi is not None else None)
c2.metric("KOSDAQ", f"{kosdaq['close']:,.2f}" if kosdaq is not None else "조회 실패", f"{kosdaq['change_pct']:.2f}%" if kosdaq is not None else None)
if kospi is not None:
    c3.metric("KOSPI 거래대금", money(kospi.get("ACC_TRDVAL", 0)))
if kosdaq is not None:
    c4.metric("KOSDAQ 거래대금", money(kosdaq.get("ACC_TRDVAL", 0)))

if kospi is None or kosdaq is None:
    with st.expander("🔎 KRX 조회 오류 상세정보", expanded=True):
        if kospi is None:
            st.error("KOSPI\n" + (kospi_error or "응답 데이터가 없습니다."))
        if kosdaq is None:
            st.error("KOSDAQ\n" + (kosdaq_error or "응답 데이터가 없습니다."))
        st.caption("KRX는 인증키 신청 후에도 API별 이용 신청과 관리자 승인이 필요할 수 있습니다. 공식 안내를 확인하세요.")

st.subheader("내 모의투자 계좌")
try:
    account_no = get_account_number(token)
    deposit = get_deposit(token)
    evaluation = get_account_eval(token)
    deposit_amt = clean_number(deposit.get("entr"))
    orderable_amt = clean_number(deposit.get("ord_alow_amt") or deposit.get("ord_alowa"))
    eval_amt = clean_number(evaluation.get("tot_est_amt") or evaluation.get("aset_evlt_amt"))
    profit_rt = clean_number(evaluation.get("lspft_rt"))
    a1,a2,a3,a4,a5 = st.columns(5)
    a1.metric("계좌번호", account_no or "조회됨")
    a2.metric("예수금", money(deposit_amt))
    a3.metric("투자가능금액", money(orderable_amt))
    a4.metric("평가금액", money(eval_amt))
    a5.metric("누적손익률", pct(profit_rt))

    holdings = evaluation.get("stk_acnt_evlt_prst", [])
    rows = []
    for item in holdings:
        qty = clean_number(item.get("rmnd_qty"))
        if qty > 0:
            rows.append({"종목코드":str(item.get("stk_cd","")).lstrip("AJQ"),"종목명":item.get("stk_nm",""),"보유수량":int(qty),"평균단가":clean_number(item.get("avg_prc")),"현재가":clean_number(item.get("cur_prc")),"평가금액":clean_number(item.get("evlt_amt")),"평가손익":clean_number(item.get("pl_amt")),"수익률(%)":clean_number(item.get("pl_rt"))})
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True) if rows else st.info("현재 보유종목이 없습니다.")
except Exception as e:
    st.error(f"키움 계좌 조회 실패: {e}")

st.subheader("종목 분석")
if len(stock_code) == 6 and stock_code.isdigit():
    try:
        info = get_stock_info(token, stock_code)
        name = info.get("stk_nm", stock_code)
        s1,s2,s3,s4 = st.columns(4)
        s1.metric("종목", f"{name} ({stock_code})")
        s2.metric("현재가", money(info.get("cur_prc")))
        s3.metric("등락률", pct(info.get("flu_rt") or info.get("base_comp_chgr")))
        s4.metric("거래량", f"{clean_number(info.get('trde_qty')):,.0f}")
    except Exception as e:
        st.warning(f"종목 조회 실패: {e}")
else:
    st.info("사이드바에 6자리 종목코드를 입력하세요. 예: 005930")

left,right = st.columns(2)
with left:
    st.markdown("**KOSPI 최근 데이터**")
    if not kospi_df.empty:
        st.line_chart(kospi_df[["date","close"]].drop_duplicates("date").set_index("date"))
with right:
    st.markdown("**KOSDAQ 최근 데이터**")
    if not kosdaq_df.empty:
        st.line_chart(kosdaq_df[["date","close"]].drop_duplicates("date").set_index("date"))

st.caption("※ KRX 통계정보를 사용한 화면입니다. 이 앱은 현재 조회 기능만 제공합니다.")
