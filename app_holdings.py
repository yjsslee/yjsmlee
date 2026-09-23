import datetime as dt
import re
from typing import Any

import pandas as pd
import requests
import streamlit as st

st.set_page_config(
    page_title="이유진의 키움 모의투자 보유종목 분석",
    page_icon="📊",
    layout="wide",
)

KIWOOM_MOCK_URL = "https://mockapi.kiwoom.com"


def secret(name: str) -> str:
    try:
        value = st.secrets[name]
    except Exception:
        value = ""
    return str(value).strip() if value else ""


APP_KEY = secret("KIWOOM_APP_KEY")
APP_SECRET = secret("KIWOOM_APP_SECRET")


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


def fmt_money(value: Any) -> str:
    return f"{clean_number(value):,.0f}원"


def fmt_pct(value: Any) -> str:
    return f"{clean_number(value):,.2f}%"


@st.cache_data(ttl=60 * 60 * 23, show_spinner=False)
def get_token(app_key: str, app_secret: str) -> str:
    r = requests.post(
        f"{KIWOOM_MOCK_URL}/oauth2/token",
        headers={"Content-Type": "application/json;charset=UTF-8"},
        json={
            "grant_type": "client_credentials",
            "appkey": app_key,
            "secretkey": app_secret,
        },
        timeout=20,
    )
    r.raise_for_status()
    data = r.json()
    if data.get("return_code") not in (None, 0):
        raise RuntimeError(data.get("return_msg", "토큰 발급 실패"))
    token = data.get("token")
    if not token:
        raise RuntimeError("접근토큰이 응답되지 않았습니다.")
    return token


def kiwoom_post(token: str, api_id: str, path: str, payload: dict) -> tuple[dict, dict]:
    headers = {
        "Content-Type": "application/json;charset=UTF-8",
        "authorization": f"Bearer {token}",
        "api-id": api_id,
        "cont-yn": "N",
        "next-key": "",
    }
    r = requests.post(
        f"{KIWOOM_MOCK_URL}{path}",
        headers=headers,
        json=payload,
        timeout=20,
    )
    r.raise_for_status()
    return r.json(), dict(r.headers)


def kiwoom_post_pages(token: str, api_id: str, path: str, payload: dict, table_keys: tuple[str, ...]) -> dict:
    rows = {key: [] for key in table_keys}
    summaries = []
    first_response = None
    cont_yn = "N"
    next_key = ""

    for _ in range(10):
        headers = {
            "Content-Type": "application/json;charset=UTF-8",
            "authorization": f"Bearer {token}",
            "api-id": api_id,
            "cont-yn": cont_yn,
            "next-key": next_key,
        }
        r = requests.post(
            f"{KIWOOM_MOCK_URL}{path}",
            headers=headers,
            json=payload,
            timeout=20,
        )
        r.raise_for_status()
        data = r.json()
        if first_response is None:
            first_response = data
        if data.get("return_code") not in (None, 0):
            raise RuntimeError(f"{data.get('return_code')}: {data.get('return_msg', '키움 API 오류')}")

        for key in table_keys:
            records = data.get(key, [])
            if isinstance(records, list):
                rows[key].extend(records)
        summaries.append({k: v for k, v in data.items() if k not in table_keys})

        cont_yn = str(r.headers.get("cont-yn", "N")).upper()
        next_key = r.headers.get("next-key", "")
        if cont_yn != "Y":
            break

    result = dict(first_response or {})
    for key in table_keys:
        result[key] = rows[key]
    result["_summary_pages"] = summaries
    return result


def get_account_number(token: str) -> str:
    data, _ = kiwoom_post(token, "ka00001", "/api/dostk/acnt", {})
    return str(data.get("acctNo") or data.get("acct_no") or "")


def get_deposit(token: str) -> dict:
    data, _ = kiwoom_post(token, "kt00001", "/api/dostk/acnt", {"qry_tp": "2"})
    return data


def get_holdings(token: str) -> dict:
    return kiwoom_post_pages(
        token,
        "kt00018",
        "/api/dostk/acnt",
        {"qry_tp": "1", "dmst_stex_tp": "KRX"},
        ("acnt_evlt_remn_indv_tot",),
    )


def get_stock_info(token: str, code: str) -> dict:
    data, _ = kiwoom_post(token, "ka10001", "/api/dostk/stkinfo", {"stk_cd": code})
    return data


def get_daily_chart(token: str, code: str, base_dt: str, pages: int = 5) -> dict:
    rows = []
    cont_yn = "N"
    next_key = ""
    first = {}

    for _ in range(pages):
        headers = {
            "Content-Type": "application/json;charset=UTF-8",
            "authorization": f"Bearer {token}",
            "api-id": "ka10081",
            "cont-yn": cont_yn,
            "next-key": next_key,
        }
        payload = {
            "stk_cd": code,
            "base_dt": base_dt,
            "upd_stkpc_tp": "1",
        }
        r = requests.post(
            f"{KIWOOM_MOCK_URL}/api/dostk/chart",
            headers=headers,
            json=payload,
            timeout=20,
        )
        r.raise_for_status()
        data = r.json()
        if not first:
            first = data
        if data.get("return_code") not in (None, 0):
            raise RuntimeError(f"{data.get('return_code')}: {data.get('return_msg', '차트 조회 오류')}")
        records = data.get("stk_dt_pole_chart_qry", [])
        if isinstance(records, list):
            rows.extend(records)
        cont_yn = str(r.headers.get("cont-yn", "N")).upper()
        next_key = r.headers.get("next-key", "")
        if cont_yn != "Y":
            break

    result = dict(first)
    result["stk_dt_pole_chart_qry"] = rows
    return result


def holdings_dataframe(raw: dict) -> pd.DataFrame:
    records = raw.get("acnt_evlt_remn_indv_tot", [])
    if not isinstance(records, list):
        return pd.DataFrame()
    return pd.DataFrame(records)


def chart_dataframe(raw: dict) -> pd.DataFrame:
    records = raw.get("stk_dt_pole_chart_qry", [])
    if not isinstance(records, list):
        return pd.DataFrame()
    df = pd.DataFrame(records)
    if df.empty:
        return df
    rename = {
        "cur_prc": "현재가",
        "trde_qty": "거래량",
        "trde_prica": "거래대금",
        "dt": "일자",
        "open_pric": "시가",
        "high_pric": "고가",
        "low_pric": "저가",
        "pred_pre": "전일대비",
        "pred_pre_sig": "전일대비기호",
        "trde_tern_rt": "거래회전율",
    }
    df = df.rename(columns=rename)
    if "일자" in df.columns:
        df["일자"] = pd.to_datetime(df["일자"].astype(str), format="%Y%m%d", errors="coerce")
        df = df.sort_values("일자")
    for col in ["현재가", "거래량", "거래대금", "시가", "고가", "저가", "전일대비", "거래회전율"]:
        if col in df.columns:
            df[col] = df[col].map(clean_number)
    return df


st.markdown("""
<style>
.stApp { background: linear-gradient(135deg,#F8F5FF 0%,#F4FAF8 50%,#FFF8F0 100%); }
h1,h2,h3 { color:#303548 !important; }
div[data-testid="stMetric"] { background:rgba(255,255,255,.8); border:1px solid #DDD8EA; border-radius:16px; padding:14px; }
section[data-testid="stSidebar"] { background:linear-gradient(180deg,#F0ECFA 0%,#EAF5F2 100%); }
</style>
""", unsafe_allow_html=True)

st.title("📊 키움 모의투자 보유종목 상세조회")
st.caption("보유종목의 계좌정보·종목정보·일봉차트를 키움 REST API에서 조회합니다. 조회 전용 프로그램이며 주문 기능은 포함하지 않습니다.")

if not APP_KEY or not APP_SECRET:
    st.error("KIWOOM_APP_KEY 또는 KIWOOM_APP_SECRET이 없습니다.")
    st.info("Streamlit의 Secrets에 KIWOOM_APP_KEY와 KIWOOM_APP_SECRET을 입력하세요. 두 값은 GitHub 저장소에 절대 저장하지 않습니다.")
    st.stop()

with st.sidebar:
    st.header("조회 설정")
    chart_pages = st.slider("차트 조회 페이지", 1, 10, 3)
    if st.button("🔄 전체 새로고침", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

try:
    token = get_token(APP_KEY, APP_SECRET)
except Exception as exc:
    st.error(f"키움 모의투자 인증 실패: {exc}")
    st.stop()

조회시각 = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

try:
    account_no = get_account_number(token)
    deposit = get_deposit(token)
    holdings_raw = get_holdings(token)
except Exception as exc:
    st.error(f"계좌 조회 실패: {exc}")
    st.stop()

holdings = holdings_dataframe(holdings_raw)

st.subheader("계좌 요약")
c1, c2, c3, c4 = st.columns(4)
c1.metric("계좌번호", account_no or "조회됨")
c2.metric("예수금", fmt_money(deposit.get("entr")))
c3.metric("투자가능금액", fmt_money(deposit.get("ord_alow_amt") or deposit.get("ord_alowa")))
c4.metric("조회시각", 조회시각)

if holdings.empty:
    st.warning("현재 보유종목이 없습니다.")
    st.stop()

st.subheader("보유종목")
summary_cols = {
    "stk_cd": "종목코드",
    "stk_nm": "종목명",
    "rmnd_qty": "보유수량",
    "trde_able_qty": "매매가능수량",
    "pur_pric": "매입가",
    "cur_prc": "현재가",
    "evltv_prft": "평가손익",
    "prft_rt": "수익률(%)",
    "pur_amt": "매입금액",
    "evlt_amt": "평가금액",
    "poss_rt": "보유비중(%)",
}
summary = holdings[[c for c in summary_cols if c in holdings.columns]].rename(columns=summary_cols).copy()
st.dataframe(summary, use_container_width=True, hide_index=True)

st.divider()
st.subheader("종목별 상세조회")

codes = holdings.get("stk_cd", pd.Series(dtype=str)).astype(str).str.replace("^A", "", regex=True).str.zfill(6).tolist()
names = holdings.get("stk_nm", pd.Series(dtype=str)).astype(str).tolist()
options = [f"{code} | {name}" for code, name in zip(codes, names)]
selected = st.selectbox("조회할 보유종목", options)
selected_code = selected.split(" | ", 1)[0]

selected_row = holdings.iloc[codes.index(selected_code)] if selected_code in codes else pd.Series(dtype=object)

try:
    stock_info_raw = get_stock_info(token, selected_code)
except Exception as exc:
    stock_info_raw = {"조회오류": str(exc)}

try:
    chart_raw = get_daily_chart(token, selected_code, dt.date.today().strftime("%Y%m%d"), chart_pages)
    chart = chart_dataframe(chart_raw)
except Exception as exc:
    chart_raw = {"조회오류": str(exc)}
    chart = pd.DataFrame()

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("현재가", fmt_money(selected_row.get("cur_prc")))
m2.metric("매입가", fmt_money(selected_row.get("pur_pric")))
m3.metric("보유수량", f"{clean_number(selected_row.get('rmnd_qty')):,.0f}주")
m4.metric("평가손익", fmt_money(selected_row.get("evltv_prft")))
m5.metric("수익률", fmt_pct(selected_row.get("prft_rt")))

st.markdown("### 📈 일봉 차트")
if not chart.empty and "일자" in chart.columns and "현재가" in chart.columns:
    chart_for_view = chart[["일자", "현재가"]].dropna().set_index("일자")
    st.line_chart(chart_for_view, y="현재가", height=420)
    st.caption(f"기준일: {dt.date.today().strftime('%Y-%m-%d')} / 수정주가 적용 / 차트 페이지: {chart_pages}")
else:
    st.warning("일봉 차트를 가져오지 못했습니다.")

with st.expander("📋 보유종목 API의 모든 원본 정보"):
    st.json(selected_row.to_dict())

with st.expander("🔎 종목정보 API의 모든 원본 정보"):
    st.json(stock_info_raw)

with st.expander("🕯️ 차트 API 원본 데이터"):
    st.json(chart_raw)

with st.expander("📦 전체 계좌평가 API 원본 응답"):
    st.json(holdings_raw)

st.caption("※ App Key/App Secret은 소스코드와 GitHub에 저장하지 않고 Streamlit Secrets에서만 읽습니다. 키움 REST API의 모의투자 서버와 국내주식 KRX 기준 조회입니다.")
