import streamlit as st
import requests
import pandas as pd

st.set_page_config(page_title="키움 모의투자 보유종목 수익률", page_icon="📈")

st.title("📈 키움증권 모의투자 보유종목 수익률")
st.caption("키움 REST API 모의투자 계좌의 보유종목별 수익률을 조회합니다.")

# 키움 REST API 모의투자 서버
BASE_URL = "https://mockapi.kiwoom.com"
TOKEN_URL = f"{BASE_URL}/oauth2/token"
ACCOUNT_URL = f"{BASE_URL}/api/dostk/acnt"


def get_access_token(app_key: str, app_secret: str) -> str:
    """App Key / App Secret으로 모의투자용 접근토큰을 발급받습니다."""
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
        raise RuntimeError(data.get("return_msg", "접근토큰 발급에 실패했습니다."))

    token = data.get("token")
    if not token:
        raise RuntimeError(data.get("return_msg", "접근토큰이 응답되지 않았습니다."))

    return token


def get_account_evaluation(token: str) -> dict:
    """계좌평가현황요청(kt00004)으로 보유종목 정보를 조회합니다."""
    headers = {
        "Content-Type": "application/json;charset=UTF-8",
        "authorization": f"Bearer {token}",
        "api-id": "kt00004",
        "cont-yn": "N",
        "next-key": "",
    }

    payload = {
        "qry_tp": "0",          # 0: 전체
        "dmst_stex_tp": "KRX",  # 모의투자는 KRX 기준
    }

    response = requests.post(
        ACCOUNT_URL,
        headers=headers,
        json=payload,
        timeout=20,
    )
    response.raise_for_status()
    data = response.json()

    if data.get("return_code") not in (None, 0):
        raise RuntimeError(data.get("return_msg", "계좌평가 조회에 실패했습니다."))

    return data


def to_number(value):
    """키움 API가 반환하는 문자열 숫자를 숫자로 변환합니다."""
    if value is None or value == "":
        return 0.0
    try:
        return float(str(value).replace(",", "").replace("+", ""))
    except (ValueError, TypeError):
        return 0.0


with st.form("kiwoom_form"):
    app_key = st.text_input(
        "모의투자 App Key",
        type="password",
        placeholder="App Key를 입력하세요",
    )
    app_secret = st.text_input(
        "모의투자 App Secret",
        type="password",
        placeholder="App Secret을 입력하세요",
    )
    submitted = st.form_submit_button("보유종목 수익률 조회", type="primary")


if submitted:
    if not app_key or not app_secret:
        st.warning("App Key와 App Secret을 모두 입력해주세요.")
        st.stop()

    try:
        with st.spinner("키움증권 모의투자 계좌를 조회하고 있습니다..."):
            token = get_access_token(app_key.strip(), app_secret.strip())
            data = get_account_evaluation(token)

        # kt00004의 보유종목 목록
        holdings = data.get("stk_acnt_evlt_prst", [])

        # 일부 API 응답 형식에서 사용할 수 있는 대체 목록
        if not holdings:
            holdings = data.get("acnt_evlt_remn_indv_tot", [])

        if not holdings:
            st.info("현재 보유종목이 없습니다.")
        else:
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

            df = pd.DataFrame(rows)

            st.subheader("보유종목")
            st.dataframe(
                df.style.format(
                    {
                        "매입단가": "{:,.0f}",
                        "현재가": "{:,.0f}",
                        "평가금액": "{:,.0f}",
                        "평가손익": "{:,.0f}",
                        "수익률(%)": "{:.2f}%",
                    }
                ),
                use_container_width=True,
                hide_index=True,
            )

            # 전체 계좌 수익률도 응답에 있으면 표시
            total_return = data.get("tot_prft_rt")
            if total_return not in (None, ""):
                st.metric("전체 계좌 수익률", f"{to_number(total_return):.2f}%")

            st.success(f"총 {len(df)}개 보유종목을 조회했습니다.")

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

st.divider()
st.caption("※ App Key와 App Secret은 GitHub에 저장되지 않으며, 실행 중 화면에서만 입력합니다.")
