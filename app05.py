import streamlit as st
import requests
import pandas as pd
from datetime import datetime

st.set_page_config(
    page_title="키움증권 보유종목·오늘 수급 대시보드",
    page_icon="📈",
    layout="wide",
)

BASE_URL = "https://mockapi.kiwoom.com"


def issue_token(app_key: str, app_secret: str) -> str:
    response = requests.post(
        f"{BASE_URL}/oauth2/token",
        json={
            "grant_type": "client_credentials",
            "appkey": app_key,
            "secretkey": app_secret,
        },
        headers={"Content-Type": "application/json;charset=UTF-8"},
        timeout=20,
    )
    response.raise_for_status()
    data = response.json()
    if data.get("return_code") not in (None, 0):
        raise RuntimeError(data.get("return_msg", "접근토큰 발급 실패"))
    token = data.get("token")
    if not token:
        raise RuntimeError("접근토큰이 응답되지 않았습니다.")
    return token


def call_api(token: str, api_id: str, path: str, body: dict) -> dict:
    headers = {
        "Content-Type": "application/json;charset=UTF-8",
        "authorization": f"Bearer {token}",
        "api-id": api_id,
        "cont-yn": "N",
        "next-key": "",
    }
    response = requests.post(
        f"{BASE_URL}{path}",
        headers=headers,
        json=body,
        timeout=20,
    )
    response.raise_for_status()
    data = response.json()
    if data.get("return_code") not in (None, 0):
        raise RuntimeError(f"{api_id}: {data.get('return_msg', 'API 호출 실패')}")
    return data


def first_value(data: dict, keys, default=""):
    for key in keys:
        if key in data and data[key] not in (None, ""):
            return data[key]
    return default


def to_number(value):
    if value is None or value == "":
        return 0
    try:
        text = str(value).replace(",", "").strip()
        return float(text)
    except (TypeError, ValueError):
        return 0


def to_int(value):
    return int(to_number(value))


def clean_code(value):
    return str(value or "").strip().replace("A", "")


def find_list(data: dict, candidates):
    for key in candidates:
        value = data.get(key)
        if isinstance(value, list):
            return value
    return []


def get_flow_value(row, candidates):
    return to_number(first_value(row, candidates, 0))


st.title("📈 키움증권 모의투자 보유종목·오늘 수급 대시보드")
st.caption("내 모의투자 계좌의 보유종목을 조회하고, 각 보유종목의 오늘 투자자별 순매수 흐름을 표시합니다.")

with st.sidebar:
    st.header("🔐 키움증권 모의투자")
    app_key = st.text_input("APP Key", type="password")
    app_secret = st.text_input("APP Secret", type="password")
    account_no = st.text_input("계좌번호", placeholder="예: 1234567890")
    run = st.button("📊 보유종목·오늘 수급 조회", type="primary", use_container_width=True)
    st.caption("APP Key / APP Secret은 GitHub에 저장하지 않습니다.")

if not run:
    st.info("왼쪽에 APP Key, APP Secret, 계좌번호를 입력하고 조회 버튼을 눌러주세요.")
    st.markdown(
        """
        ### 이 프로그램이 보여주는 내용
        - **내 계좌 보유종목**: 종목명, 종목코드, 보유수량, 매입금액, 현재가, 평가금액, 평가손익, 수익률
        - **오늘 수급**: 보유종목별 개인·외국인·기관 순매수 흐름
        - **수급 금액/수량 전환**: 금액 기준 또는 수량 기준 선택
        - **조회일**: 오늘 날짜를 자동으로 사용
        """
    )
    st.stop()

if not app_key or not app_secret or not account_no:
    st.error("APP Key, APP Secret, 계좌번호를 모두 입력해주세요.")
    st.stop()

# 오늘 날짜: 키움 API는 YYYYMMDD 형식을 사용
trade_date = datetime.now().strftime("%Y%m%d")

try:
    with st.spinner("키움증권 모의투자 계좌와 오늘 수급 데이터를 조회하고 있습니다..."):
        token = issue_token(app_key, app_secret)

        # 계좌평가잔고: 연결된 계좌의 보유종목 조회
        balance = call_api(
            token,
            "kt00018",
            "/api/dostk/acnt",
            {"qry_tp": "1", "dmst_stex_tp": "KRX"},
        )

    # 계좌평가잔고의 보유종목 배열
    rows = find_list(
        balance,
        ["stk_acnt_evlt_prst", "stk_acnt_evlt_prst_list", "output1", "list"],
    )

    holdings = []
    for row in rows:
        code = clean_code(first_value(row, ["stk_cd", "종목코드"]))
        if not code:
            continue
        holdings.append(
            {
                "종목명": first_value(row, ["stk_nm", "종목명"], code),
                "종목코드": code,
                "보유수량": to_int(first_value(row, ["rmnd_qty", "보유수량"])),
                "매입금액": to_int(first_value(row, ["pur_amt", "매입금액"])),
                "현재가": to_int(first_value(row, ["cur_prc", "현재가"])),
                "평가금액": to_int(first_value(row, ["evlt_amt", "평가금액"])),
                "평가손익": to_int(first_value(row, ["evlt_pl", "평가손익"])),
                "수익률(%)": to_number(first_value(row, ["prft_rt", "수익률"], 0)),
            }
        )

    st.success(f"계좌 {account_no}의 보유종목 {len(holdings)}개를 조회했습니다. 조회일: {trade_date}")

    # -------------------------
    # 보유종목 표
    # -------------------------
    st.subheader("📋 1. 내 계좌 보유종목")
    if holdings:
        holding_df = pd.DataFrame(holdings)
        st.dataframe(holding_df, use_container_width=True, hide_index=True)
    else:
        st.info("현재 보유종목이 없습니다.")

    if not holdings:
        st.stop()

    # -------------------------
    # 오늘 투자자별 수급
    # ka10059: 종목별 투자자기관별요청
    # 금액 기준(amt_qty_tp=1), 순매수(trde_tp=0), 단주(unit_tp=1)
    # -------------------------
    st.subheader("💰 2. 오늘의 보유종목 수급")
    st.caption("개인·외국인·기관의 순매수 흐름입니다. API가 제공하는 오늘 데이터가 없는 경우 해당 종목은 빈 값으로 표시됩니다.")

    basis = st.radio(
        "수급 표시 기준",
        ["금액", "수량"],
        horizontal=True,
        index=0,
    )

    amt_qty_tp = "1" if basis == "금액" else "2"
    unit_tp = "1" if basis == "금액" else "1"

    supply_rows = []
    progress = st.progress(0, text="보유종목별 오늘 수급을 조회하는 중입니다...")

    for idx, holding in enumerate(holdings):
        code = holding["종목코드"]
        try:
            flow = call_api(
                token,
                "ka10059",
                "/api/dostk/stkinfo",
                {
                    "dt": trade_date,
                    "stk_cd": code,
                    "amt_qty_tp": amt_qty_tp,
                    "trde_tp": "0",
                    "unit_tp": unit_tp,
                },
            )

            # API 버전에 따라 배열 키가 다를 수 있어 여러 후보를 지원
            flow_list = find_list(
                flow,
                [
                    "stk_invsr_orgn",
                    "stk_invsr_orgn_list",
                    "invsr_orgn",
                    "output1",
                    "list",
                ],
            )

            # 당일 데이터가 여러 건이면 가장 최근 날짜의 레코드를 사용
            row = flow_list[0] if flow_list else flow
            if flow_list:
                for candidate in flow_list:
                    candidate_date = str(first_value(candidate, ["dt", "date", "일자"], ""))
                    if candidate_date.replace("-", "") == trade_date:
                        row = candidate
                        break

            supply_rows.append(
                {
                    "종목명": holding["종목명"],
                    "종목코드": code,
                    "개인 순매수": get_flow_value(row, ["prsn", "prsn_net", "prsnr", "개인순매수"]),
                    "외국인 순매수": get_flow_value(row, ["frgnr", "frgnr_net", "frgn", "외국인순매수"]),
                    "기관 순매수": get_flow_value(row, ["orgn", "orgn_net", "기관순매수"]),
                    "수급조회상태": "조회됨" if flow_list else "당일 데이터 없음",
                }
            )
        except Exception as exc:
            supply_rows.append(
                {
                    "종목명": holding["종목명"],
                    "종목코드": code,
                    "개인 순매수": 0,
                    "외국인 순매수": 0,
                    "기관 순매수": 0,
                    "수급조회상태": f"오류: {exc}",
                }
            )

        progress.progress((idx + 1) / len(holdings), text=f"{idx + 1}/{len(holdings)} 종목 조회 완료")

    progress.empty()

    supply_df = pd.DataFrame(supply_rows)
    if basis == "금액":
        supply_df["개인 순매수"] = supply_df["개인 순매수"].round(0).astype("int64")
        supply_df["외국인 순매수"] = supply_df["외국인 순매수"].round(0).astype("int64")
        supply_df["기관 순매수"] = supply_df["기관 순매수"].round(0).astype("int64")
        st.dataframe(
            supply_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "개인 순매수": st.column_config.NumberColumn(format="%d원"),
                "외국인 순매수": st.column_config.NumberColumn(format="%d원"),
                "기관 순매수": st.column_config.NumberColumn(format="%d원"),
            },
        )
    else:
        supply_df["개인 순매수"] = supply_df["개인 순매수"].round(0).astype("int64")
        supply_df["외국인 순매수"] = supply_df["외국인 순매수"].round(0).astype("int64")
        supply_df["기관 순매수"] = supply_df["기관 순매수"].round(0).astype("int64")
        st.dataframe(
            supply_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "개인 순매수": st.column_config.NumberColumn(format="%d주"),
                "외국인 순매수": st.column_config.NumberColumn(format="%d주"),
                "기관 순매수": st.column_config.NumberColumn(format="%d주"),
            },
        )

    st.subheader("📊 3. 보유종목별 오늘 수급 요약")
    if not supply_df.empty:
        summary = supply_df.copy()
        summary["순매수 합계"] = summary["개인 순매수"] + summary["외국인 순매수"] + summary["기관 순매수"]
        st.dataframe(summary, use_container_width=True, hide_index=True)

    st.caption("※ 수급은 키움 REST API의 종목별 투자자/기관 데이터 기준입니다. 장중 데이터는 시점에 따라 아직 집계되지 않았거나 변경될 수 있습니다.")

except requests.RequestException as exc:
    st.error(f"키움증권 API 통신 오류: {exc}")
except Exception as exc:
    st.error(f"조회 중 오류가 발생했습니다: {exc}")

with st.expander("ℹ️ API 구성"):
    st.write("- 인증: 모의투자 OAuth / au10001")
    st.write("- 보유종목: 계좌평가잔고 / kt00018")
    st.write("- 오늘 수급: 종목별 투자자·기관 수급 / ka10059")
    st.write("- 모의투자 서버: https://mockapi.kiwoom.com")
    st.warning("APP Key와 APP Secret을 코드에 직접 입력하거나 GitHub에 저장하지 마세요.")
