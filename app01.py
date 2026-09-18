import streamlit as st
import requests
import pandas as pd

st.set_page_config(
    page_title="키움 주식 대시보드",
    page_icon="📊",
    layout="wide",
)

BASE_URL = "https://mockapi.kiwoom.com"
TOKEN_URL = f"{BASE_URL}/oauth2/token"
ACCOUNT_URL = f"{BASE_URL}/api/dostk/acnt"

st.title("📊 키움증권 모의투자 주식 대시보드")
st.caption("계좌의 자산·예수금·보유종목·수익률을 한 화면에서 확인합니다.")


def to_number(value):
    if value is None or value == "":
        return 0.0
    try:
        return float(str(value).replace(",", "").replace("+", "").replace("%", ""))
    except (ValueError, TypeError):
        return 0.0


def get_access_token(app_key, app_secret):
    response = requests.post(
        TOKEN_URL,
        headers={"Content-Type": "application/json;charset=UTF-8"},
        json={
            "grant_type": "client_credentials",
            "appkey": app_key,
            "secretkey": app_secret,
        },
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


def call_account_api(token, api_id, payload):
    response = requests.post(
        ACCOUNT_URL,
        headers={
            "Content-Type": "application/json;charset=UTF-8",
            "authorization": f"Bearer {token}",
            "api-id": api_id,
            "cont-yn": "N",
            "next-key": "",
        },
        json=payload,
        timeout=20,
    )
    response.raise_for_status()
    data = response.json()
    if data.get("return_code") not in (None, 0):
        raise RuntimeError(data.get("return_msg", f"{api_id} 조회 실패"))
    return data


def get_deposit(token):
    return call_account_api(token, "kt00001", {"qry_tp": "3"})


def get_account_evaluation(token):
    return call_account_api(
        token,
        "kt00004",
        {"qry_tp": "0", "dmst_stex_tp": "KRX"},
    )


def make_holdings_dataframe(data):
    holdings = data.get("stk_acnt_evlt_prst", [])
    if not holdings:
        holdings = data.get("acnt_evlt_remn_indv_tot", [])

    rows = []
    for item in holdings:
        rows.append(
            {
                "종목코드": item.get("stk_cd", ""),
                "종목명": item.get("stk_nm", ""),
                "보유수량": int(to_number(item.get("rmnd_qty", 0))),
                "매입단가": to_number(item.get("avg_prc", item.get("pur_pric", 0))),
                "현재가": to_number(item.get("cur_prc", 0)),
                "평가금액": to_number(item.get("evlt_amt", 0)),
                "평가손익": to_number(item.get("pl_amt", item.get("evltv_prft", 0))),
                "수익률(%)": to_number(item.get("pl_rt", item.get("prft_rt", 0))),
            }
        )

    return pd.DataFrame(rows)


# ------------------------------------------------------------
# 입력 영역
# ------------------------------------------------------------
st.sidebar.header("🔐 인증")
app_key = st.sidebar.text_input("App Key", type="password")
app_secret = st.sidebar.text_input("App Secret", type="password")
조회 = st.sidebar.button("🔄 대시보드 조회", type="primary", use_container_width=True)

if 조회:
    if not app_key or not app_secret:
        st.warning("App Key와 App Secret을 모두 입력해주세요.")
        st.stop()

    try:
        with st.spinner("키움증권 모의투자 계좌를 조회하고 있습니다..."):
            token = get_access_token(app_key.strip(), app_secret.strip())
            deposit_data = get_deposit(token)
            evaluation_data = get_account_evaluation(token)

        deposit = to_number(deposit_data.get("entr", 0))
        investable = to_number(deposit_data.get("ord_alow_amt", 0))
        withdrawable = to_number(deposit_data.get("pymn_alow_amt", 0))
        total_return = to_number(evaluation_data.get("tot_prft_rt", 0))
        holdings_df = make_holdings_dataframe(evaluation_data)

        # --------------------------------------------------------
        # 1. 핵심 계좌 지표
        # --------------------------------------------------------
        st.subheader("1️⃣ 계좌 핵심 지표")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("예수금", f"{deposit:,.0f}원")
        c2.metric("투자가능금액", f"{investable:,.0f}원")
        c3.metric("출금가능금액", f"{withdrawable:,.0f}원")
        c4.metric("전체 수익률", f"{total_return:+.2f}%")

        # --------------------------------------------------------
        # 2. 보유종목 현황
        # --------------------------------------------------------
        st.divider()
        st.subheader("2️⃣ 보유종목 현황")

        if holdings_df.empty:
            st.info("현재 보유종목이 없습니다.")
        else:
            display_df = holdings_df.copy()
            st.dataframe(
                display_df.style.format(
                    {
                        "보유수량": "{:,.0f}",
                        "매입단가": "{:,.0f}",
                        "현재가": "{:,.0f}",
                        "평가금액": "{:,.0f}",
                        "평가손익": "{:+,.0f}",
                        "수익률(%)": "{:+.2f}%",
                    }
                ),
                use_container_width=True,
                hide_index=True,
            )

            # ----------------------------------------------------
            # 3. 종목별 수익률
            # ----------------------------------------------------
            st.divider()
            st.subheader("3️⃣ 종목별 수익률")
            chart_df = holdings_df[["종목명", "수익률(%)"]].set_index("종목명")
            st.bar_chart(chart_df)

            # ----------------------------------------------------
            # 4. 종목별 평가금액 비중
            # ----------------------------------------------------
            st.divider()
            st.subheader("4️⃣ 보유종목 평가금액 비중")
            allocation_df = holdings_df[["종목명", "평가금액"]].copy()
            allocation_df = allocation_df.set_index("종목명")
            st.bar_chart(allocation_df)

            # ----------------------------------------------------
            # 5. 수익/손실 요약
            # ----------------------------------------------------
            st.divider()
            st.subheader("5️⃣ 수익·손실 요약")
            total_profit = holdings_df["평가손익"].sum()
            profitable = int((holdings_df["평가손익"] > 0).sum())
            losing = int((holdings_df["평가손익"] < 0).sum())
            flat = int((holdings_df["평가손익"] == 0).sum())

            s1, s2, s3, s4 = st.columns(4)
            s1.metric("평가손익 합계", f"{total_profit:+,.0f}원")
            s2.metric("수익 종목", f"{profitable}개")
            s3.metric("손실 종목", f"{losing}개")
            s4.metric("보합 종목", f"{flat}개")

            # ----------------------------------------------------
            # 6. 대시보드용 데이터 다운로드
            # ----------------------------------------------------
            st.divider()
            st.subheader("6️⃣ 데이터 다운로드")
            csv_data = holdings_df.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                "📥 보유종목 CSV 다운로드",
                data=csv_data,
                file_name="kiwoom_holdings.csv",
                mime="text/csv",
            )

        st.success("✅ 대시보드 조회가 완료되었습니다.")

    except requests.HTTPError as e:
        status = e.response.status_code if e.response is not None else "알 수 없음"
        st.error(f"키움 API HTTP 오류: {status}")
        if e.response is not None:
            try:
                st.json(e.response.json())
            except ValueError:
                st.code(e.response.text)

    except requests.RequestException as e:
        st.error(f"네트워크 오류가 발생했습니다: {e}")

    except Exception as e:
        st.error(f"조회 중 오류가 발생했습니다: {e}")

else:
    st.info("왼쪽에 키움증권 모의투자 App Key와 App Secret을 입력한 뒤 '대시보드 조회'를 누르세요.")

st.divider()
st.caption("※ App Key와 App Secret은 코드나 GitHub에 저장하지 않고 실행 화면에서만 입력합니다.")
st.caption("※ 현재 버전은 조회 전용 대시보드이며 주문 기능은 포함하지 않습니다.")
