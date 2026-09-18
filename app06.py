import streamlit as st
import requests
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="키움 모의투자 보유종목", page_icon="📊", layout="wide")

BASE_URL = "https://mockapi.kiwoom.com"
API_PATH = "/api/dostk/acnt"


def issue_token(app_key, app_secret):
    r = requests.post(
        f"{BASE_URL}/oauth2/token",
        json={"grant_type": "client_credentials", "appkey": app_key, "secretkey": app_secret},
        headers={"Content-Type": "application/json;charset=UTF-8"},
        timeout=15,
    )
    r.raise_for_status()
    data = r.json()
    if data.get("return_code") not in (None, 0):
        raise RuntimeError(data.get("return_msg", "토큰 발급 실패"))
    token = data.get("token")
    if not token:
        raise RuntimeError("접근토큰이 응답에 없습니다.")
    return token


def fetch_balance_pages(token, qry_tp="2", stex="KRX", max_pages=10):
    """kt00018을 연속조회하여 모든 보유종목을 합칩니다."""
    all_rows = []
    summary = {}
    cont_yn = "N"
    next_key = ""

    for _ in range(max_pages):
        headers = {
            "Content-Type": "application/json;charset=UTF-8",
            "authorization": f"Bearer {token}",
            "api-id": "kt00018",
            "cont-yn": cont_yn,
            "next-key": next_key,
        }
        body = {"qry_tp": qry_tp, "dmst_stex_tp": stex}
        r = requests.post(f"{BASE_URL}{API_PATH}", headers=headers, json=body, timeout=15)
        r.raise_for_status()
        data = r.json()

        if data.get("return_code") not in (None, 0):
            raise RuntimeError(f"kt00018: {data.get('return_msg', '조회 실패')}")

        # 합산 정보는 첫 응답에서 확보
        if not summary:
            summary = data

        rows = data.get("stk_acnt_evlt_prst", [])
        if isinstance(rows, list):
            all_rows.extend([x for x in rows if isinstance(x, dict)])

        # 연속조회 정보는 응답 BODY가 아니라 HTTP 헤더에 있음
        cont_yn = r.headers.get("cont-yn", "N")
        next_key = r.headers.get("next-key", "")
        if cont_yn != "Y" or not next_key:
            break

    return summary, all_rows


def fetch_deposit(token):
    headers = {
        "Content-Type": "application/json;charset=UTF-8",
        "authorization": f"Bearer {token}",
        "api-id": "kt00001",
        "cont-yn": "N",
        "next-key": "",
    }
    r = requests.post(
        f"{BASE_URL}{API_PATH}",
        headers=headers,
        json={"qry_tp": "2"},
        timeout=15,
    )
    r.raise_for_status()
    data = r.json()
    if data.get("return_code") not in (None, 0):
        raise RuntimeError(f"kt00001: {data.get('return_msg', '조회 실패')}")
    return data


def num(v):
    if v is None or v == "":
        return 0
    try:
        return int(str(v).replace(",", "").strip())
    except (ValueError, TypeError):
        return 0


def text(row, keys, default=""):
    for k in keys:
        if row.get(k) not in (None, ""):
            return row[k]
    return default


st.title("📊 키움증권 모의투자 보유종목 대시보드")
st.caption("계좌평가잔고(kt00018)의 연속조회까지 처리하여 보유종목을 조회합니다.")

with st.sidebar:
    st.header("🔐 키움 API")
    app_key = st.text_input("APP Key", type="password")
    app_secret = st.text_input("APP Secret", type="password")
    account_no = st.text_input("계좌번호", placeholder="예: 12345678-01")
    run = st.button("📥 보유종목 조회", type="primary", use_container_width=True)
    st.caption("인증정보는 GitHub에 저장하지 않습니다.")

if run:
    if not app_key or not app_secret:
        st.error("APP Key와 APP Secret을 입력해주세요.")
        st.stop()

    try:
        with st.spinner("키움증권 모의투자 계좌를 조회하는 중입니다..."):
            token = issue_token(app_key, app_secret)
            deposit = fetch_deposit(token)
            summary, rows = fetch_balance_pages(token, qry_tp="2", stex="KRX")

        # kt00018의 실제 종목 배열을 기준으로 표시
        holdings = []
        for row in rows:
            code = str(text(row, ["stk_cd", "종목코드"], "")).replace("A", "")
            holdings.append({
                "종목명": text(row, ["stk_nm", "종목명"]),
                "종목코드": code,
                "보유수량": num(text(row, ["rmnd_qty", "보유수량"])),
                "매입금액": num(text(row, ["pur_amt", "매입금액"])),
                "현재가": num(text(row, ["cur_prc", "현재가"])),
                "평가금액": num(text(row, ["evlt_amt", "평가금액"])),
                "평가손익": num(text(row, ["evlt_pl", "평가손익"])),
                "수익률(%)": text(row, ["prft_rt", "수익률"], "0"),
            })

        # 중복 제거
        unique = {}
        for item in holdings:
            key = item["종목코드"] or item["종목명"]
            unique[key] = item
        holdings = list(unique.values())

        today = datetime.now().strftime("%Y%m%d")
        display_account = account_no if account_no else "입력하지 않음"
        st.success(f"{display_account}의 보유종목 {len(holdings)}개를 조회했습니다. 조회일: {today}")

        c1, c2, c3 = st.columns(3)
        c1.metric("보유종목 수", f"{len(holdings)}개")
        c2.metric("예수금", f"{num(text(deposit, ['entr', '예수금'])):,}원")
        c3.metric("투자가능금액", f"{num(text(deposit, ['ord_alow_amt', '주문가능금액'])):,}원")

        st.subheader("📋 보유종목")
        if holdings:
            df = pd.DataFrame(holdings)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.warning(
                "API 응답에서 보유종목 배열이 비어 있습니다. "
                "아래 'API 원본 응답'에서 실제 응답 구조를 확인할 수 있습니다."
            )

        with st.expander("🔎 API 원본 응답 확인"):
            st.write("kt00018에서 받은 합산/원본 응답")
            st.json(summary)
            st.write("추출된 종목 배열")
            st.json(rows)

    except requests.RequestException as e:
        st.error(f"키움증권 API 통신 오류: {e}")
    except Exception as e:
        st.error(f"조회 중 오류가 발생했습니다: {e}")
else:
    st.info("APP Key, APP Secret, 계좌번호를 입력한 후 '보유종목 조회'를 눌러주세요.")
    st.markdown("""
    ### 이번 버전의 수정 내용
    - `kt00018`을 개별 종목 조회(`qry_tp=2`)로 호출합니다.
    - 응답 헤더의 `cont-yn` / `next-key`를 사용하여 연속조회합니다.
    - 여러 페이지의 종목을 하나로 합칩니다.
    - 동일 종목이 중복으로 들어오는 경우 제거합니다.
    - 실제 API 원본 응답을 화면에서 확인할 수 있습니다.
    """)
