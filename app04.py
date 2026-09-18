import streamlit as st
import requests
import pandas as pd

st.set_page_config(
    page_title="키움증권 모의투자 주식 대시보드",
    page_icon="📊",
    layout="wide",
)

BASE_URL = "https://mockapi.kiwoom.com"


def issue_token(app_key: str, app_secret: str) -> str:
    """키움증권 모의투자용 접근토큰 발급"""
    url = f"{BASE_URL}/oauth2/token"
    payload = {
        "grant_type": "client_credentials",
        "appkey": app_key,
        "secretkey": app_secret,
    }
    response = requests.post(
        url,
        json=payload,
        headers={"Content-Type": "application/json;charset=UTF-8"},
        timeout=15,
    )
    response.raise_for_status()
    data = response.json()
    if data.get("return_code") not in (None, 0):
        raise RuntimeError(data.get("return_msg", "접근토큰 발급에 실패했습니다."))
    token = data.get("token")
    if not token:
        raise RuntimeError("응답에 접근토큰(token)이 없습니다.")
    return token


def call_api(token: str, api_id: str, path: str, body: dict) -> dict:
    """키움 REST API 호출 공통 함수"""
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
        timeout=15,
    )
    response.raise_for_status()
    data = response.json()
    if data.get("return_code") not in (None, 0):
        raise RuntimeError(
            f"{api_id}: {data.get('return_msg', 'API 호출 실패')}"
        )
    return data


def to_int(value) -> int:
    """키움 API의 부호/콤마/공백이 포함된 숫자 문자열을 정수로 변환"""
    if value is None or value == "":
        return 0
    try:
        return int(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return 0


def fmt_won(value: int) -> str:
    return f"{value:,}원"


def fmt_pct(value: float) -> str:
    return f"{value:,.2f}%"


def first_value(data: dict, keys, default=""):
    for key in keys:
        if key in data and data[key] not in (None, ""):
            return data[key]
    return default


st.title("📊 키움증권 모의투자 주식 대시보드")
st.caption("모의투자 REST API에서 계좌 데이터를 조회하여 10개 항목으로 표시합니다.")

with st.sidebar:
    st.header("🔐 키움 API 인증")
    app_key = st.text_input("APP Key", type="password")
    app_secret = st.text_input("APP Secret", type="password")
    refresh = st.button("🔄 계좌 데이터 조회", type="primary", use_container_width=True)
    st.caption("APP Key와 APP Secret은 GitHub 코드에 저장하지 않습니다.")

if refresh:
    if not app_key or not app_secret:
        st.error("APP Key와 APP Secret을 입력해주세요.")
        st.stop()

    try:
        with st.spinner("키움증권 모의투자 계좌를 조회하고 있습니다..."):
            token = issue_token(app_key, app_secret)

            # 1) 예수금 상세 현황
            deposit = call_api(
                token,
                "kt00001",
                "/api/dostk/acnt",
                {"qry_tp": "2"},
            )

            # 2) 계좌평가잔고 내역
            balance = call_api(
                token,
                "kt00018",
                "/api/dostk/acnt",
                {"qry_tp": "1", "dmst_stex_tp": "KRX"},
            )

        # API 응답 필드명은 키움 REST API의 실제 응답을 우선 사용합니다.
        account_no = first_value(
            deposit,
            ["acnt_no", "account_no", "acct_no", "cano"],
            "API 응답에 계좌번호가 없습니다.",
        )
        cash = to_int(first_value(deposit, ["entr", "예수금"]))
        orderable = to_int(first_value(deposit, ["ord_alow_amt", "주문가능금액"]))
        d1 = to_int(first_value(deposit, ["d1_entra", "D+1추정예수금"]))
        d2 = to_int(first_value(deposit, ["d2_entra", "D+2추정예수금"]))

        total_purchase = to_int(
            first_value(
                balance,
                ["tot_pur_amt", "tot_prc", "총매입금액"],
            )
        )
        total_eval = to_int(
            first_value(
                balance,
                ["tot_evlt_amt", "tot_evlt_amt", "총평가금액"],
            )
        )
        total_profit = to_int(
            first_value(
                balance,
                ["tot_evlt_pl", "tot_evlt_pl_amt", "총평가손익"],
            )
        )
        total_return = float(
            str(
                first_value(
                    balance,
                    ["tot_prft_rt", "tot_evlt_prft_rt", "총수익률"],
                    "0",
                )
            ).replace(",", "")
        )

        # 계좌평가잔고 API는 계좌 전체 합산값과 개별 종목 배열을 함께 반환합니다.
        rows = balance.get("stk_acnt_evlt_prst", [])
        if not isinstance(rows, list):
            rows = []

        holdings = []
        for row in rows:
            holdings.append(
                {
                    "종목명": first_value(row, ["stk_nm", "종목명"], ""),
                    "종목코드": first_value(row, ["stk_cd", "종목코드"], "").replace("A", ""),
                    "보유수량": to_int(first_value(row, ["rmnd_qty", "보유수량"])),
                    "매입금액": to_int(first_value(row, ["pur_amt", "매입금액"])),
                    "현재가": to_int(first_value(row, ["cur_prc", "현재가"])),
                    "평가금액": to_int(first_value(row, ["evlt_amt", "평가금액"])),
                    "평가손익": to_int(first_value(row, ["evlt_pl", "평가손익"])),
                    "수익률(%)": first_value(row, ["prft_rt", "수익률"], "0"),
                }
            )

        st.success("키움증권 모의투자 계좌 조회가 완료되었습니다.")

        # 10개 대시보드 주제
        st.subheader("① 계좌 정보")
        st.metric("계좌번호", account_no)

        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("② 예수금", fmt_won(cash))
        with c2:
            st.metric("③ 투자가능금액", fmt_won(orderable))
        with c3:
            st.metric("④ D+2 추정예수금", fmt_won(d2))

        c4, c5, c6 = st.columns(3)
        with c4:
            st.metric("⑤ 총 매입금액", fmt_won(total_purchase))
        with c5:
            st.metric("⑥ 총 평가금액", fmt_won(total_eval))
        with c6:
            st.metric("⑦ 총 평가손익", fmt_won(total_profit))

        c7, c8, c9 = st.columns(3)
        with c7:
            st.metric("⑧ 전체 수익률", fmt_pct(total_return))
        with c8:
            st.metric("⑨ 보유 종목 수", f"{len(holdings):,}종목")
        with c9:
            st.metric("⑩ D+1 추정예수금", fmt_won(d1))

        st.divider()
        st.subheader("📋 보유 종목 상세")
        if holdings:
            df = pd.DataFrame(holdings)
            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "매입금액": st.column_config.NumberColumn(format="%d원"),
                    "현재가": st.column_config.NumberColumn(format="%d원"),
                    "평가금액": st.column_config.NumberColumn(format="%d원"),
                    "평가손익": st.column_config.NumberColumn(format="%d원"),
                },
            )
        else:
            st.info("현재 조회된 보유 종목이 없습니다.")

        with st.expander("🔎 API 원본 응답 확인"):
            st.write("예수금 API (kt00001)")
            st.json(deposit)
            st.write("평가잔고 API (kt00018)")
            st.json(balance)

    except requests.RequestException as e:
        st.error(f"키움증권 API 통신 오류: {e}")
    except Exception as e:
        st.error(f"조회 중 오류가 발생했습니다: {e}")

else:
    st.info("왼쪽에 APP Key와 APP Secret을 입력한 후 **계좌 데이터 조회** 버튼을 눌러주세요.")
    st.markdown(
        """
        ### 대시보드 10개 주제
        1. 계좌 정보
        2. 예수금
        3. 투자가능금액
        4. D+2 추정예수금
        5. 총 매입금액
        6. 총 평가금액
        7. 총 평가손익
        8. 전체 수익률
        9. 보유 종목 수
        10. D+1 추정예수금

        아래에는 조회된 **보유 종목별 수량·매입금액·현재가·평가금액·평가손익·수익률**을 표로 표시합니다.
        """
    )
