import streamlit as st
import requests
import pandas as pd

st.set_page_config(page_title="키움 주식 대시보드", page_icon="📊", layout="wide")

BASE_URL = "https://mockapi.kiwoom.com"
TOKEN_URL = f"{BASE_URL}/oauth2/token"
ACCOUNT_URL = f"{BASE_URL}/api/dostk/acnt"

st.title("📊 키움증권 모의투자 주식 대시보드")
st.caption("계좌의 자산, 보유종목, 수익률을 한 화면에서 확인합니다.")


def num(v):
    try:
        return float(str(v or 0).replace(",", "").replace("+", "").replace("%", ""))
    except (ValueError, TypeError):
        return 0.0


def api(token, api_id, payload):
    r = requests.post(
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
    r.raise_for_status()
    data = r.json()
    if data.get("return_code") not in (None, 0):
        raise RuntimeError(data.get("return_msg", f"{api_id} 조회 실패"))
    return data


def token(app_key, app_secret):
    r = requests.post(
        TOKEN_URL,
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
        raise RuntimeError(data.get("return_msg", "접근토큰 발급 실패"))
    if not data.get("token"):
        raise RuntimeError("접근토큰이 응답되지 않았습니다.")
    return data["token"]


def holdings_df(data):
    items = data.get("stk_acnt_evlt_prst", []) or data.get("acnt_evlt_remn_indv_tot", [])
    rows = []
    for x in items:
        rows.append({
            "종목코드": x.get("stk_cd", ""),
            "종목명": x.get("stk_nm", ""),
            "보유수량": int(num(x.get("rmnd_qty"))),
            "매입단가": num(x.get("avg_prc", x.get("pur_pric"))),
            "현재가": num(x.get("cur_prc")),
            "평가금액": num(x.get("evlt_amt")),
            "평가손익": num(x.get("pl_amt", x.get("evltv_prft"))),
            "수익률(%)": num(x.get("pl_rt", x.get("prft_rt"))),
        })
    return pd.DataFrame(rows)


st.sidebar.header("🔐 키움증권 모의투자")
app_key = st.sidebar.text_input("App Key", type="password")
app_secret = st.sidebar.text_input("App Secret", type="password")
run = st.sidebar.button("📊 대시보드 조회", type="primary", use_container_width=True)

if run:
    if not app_key or not app_secret:
        st.warning("App Key와 App Secret을 모두 입력해주세요.")
        st.stop()

    try:
        with st.spinner("키움증권 계좌를 조회하고 있습니다..."):
            access_token = token(app_key.strip(), app_secret.strip())
            deposit = api(access_token, "kt00001", {"qry_tp": "3"})
            evaluation = api(access_token, "kt00004", {"qry_tp": "0", "dmst_stex_tp": "KRX"})

        df = holdings_df(evaluation)
        cash = num(deposit.get("entr"))
        investable = num(deposit.get("ord_alow_amt"))
        withdrawable = num(deposit.get("pymn_alow_amt"))
        total_return = num(evaluation.get("tot_prft_rt"))

        st.subheader("1️⃣ 계좌 핵심 지표")
        a, b, c, d = st.columns(4)
        a.metric("예수금", f"{cash:,.0f}원")
        b.metric("투자가능금액", f"{investable:,.0f}원")
        c.metric("출금가능금액", f"{withdrawable:,.0f}원")
        d.metric("전체 수익률", f"{total_return:+.2f}%")

        st.divider()
        st.subheader("2️⃣ 보유종목 현황")
        if df.empty:
            st.info("현재 보유종목이 없습니다.")
        else:
            st.dataframe(df.style.format({
                "보유수량": "{:,.0f}", "매입단가": "{:,.0f}", "현재가": "{:,.0f}",
                "평가금액": "{:,.0f}", "평가손익": "{:+,.0f}", "수익률(%)": "{:+.2f}%"
            }), use_container_width=True, hide_index=True)

            st.divider()
            st.subheader("3️⃣ 종목별 수익률")
            st.bar_chart(df[["종목명", "수익률(%)"]].set_index("종목명"))

            st.divider()
            st.subheader("4️⃣ 종목별 평가금액")
            st.bar_chart(df[["종목명", "평가금액"]].set_index("종목명"))

            st.divider()
            st.subheader("5️⃣ 수익·손실 요약")
            profit = df["평가손익"].sum()
            p, q, r, s = st.columns(4)
            p.metric("평가손익 합계", f"{profit:+,.0f}원")
            q.metric("수익 종목", f"{(df['평가손익'] > 0).sum()}개")
            r.metric("손실 종목", f"{(df['평가손익'] < 0).sum()}개")
            s.metric("보합 종목", f"{(df['평가손익'] == 0).sum()}개")

            st.divider()
            st.subheader("6️⃣ 데이터 다운로드")
            st.download_button(
                "📥 보유종목 CSV 다운로드",
                df.to_csv(index=False).encode("utf-8-sig"),
                "kiwoom_holdings.csv",
                "text/csv",
            )

        st.success("✅ 대시보드 조회가 완료되었습니다.")

    except requests.HTTPError as e:
        status = e.response.status_code if e.response is not None else "알 수 없음"
        st.error(f"키움 API HTTP 오류: {status}")
    except requests.RequestException as e:
        st.error(f"네트워크 오류: {e}")
    except Exception as e:
        st.error(f"조회 중 오류: {e}")
else:
    st.info("왼쪽에 App Key와 App Secret을 입력한 후 '대시보드 조회'를 누르세요.")
    st.subheader("📋 대시보드 구성 주제")
    topics = pd.DataFrame({
        "번호": [1, 2, 3, 4, 5, 6],
        "주제": ["계좌 핵심 지표", "보유종목 현황", "종목별 수익률", "종목별 평가금액", "수익·손실 요약", "데이터 다운로드"],
        "내용": [
            "예수금 · 투자가능금액 · 출금가능금액 · 전체 수익률",
            "종목코드 · 종목명 · 보유수량 · 매입단가 · 현재가 · 평가금액 · 평가손익 · 수익률",
            "보유종목별 수익률 비교 그래프",
            "보유종목별 평가금액 비교 그래프",
            "평가손익 합계 · 수익 종목 · 손실 종목 · 보합 종목",
            "보유종목 데이터를 CSV로 저장",
        ],
    })
    st.dataframe(topics, use_container_width=True, hide_index=True)

st.divider()
st.caption("※ App Key와 App Secret은 코드나 GitHub에 저장하지 않고 실행 화면에서만 입력합니다.")
st.caption("※ 현재 버전은 조회 전용이며 주문 기능은 포함하지 않습니다.")
