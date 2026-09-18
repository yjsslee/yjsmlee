import streamlit as st
import requests
from datetime import datetime, timedelta

st.set_page_config(page_title="오늘의 KOSPI", page_icon="📈")

st.title("📈 오늘의 KOSPI 지수")
st.write("KRX Open API를 이용하여 KOSPI 지수를 조회합니다.")

api_key = st.text_input("KRX Open API 인증키를 입력하세요", type="password")

if st.button("KOSPI 조회"):
    if not api_key:
        st.warning("먼저 KRX Open API 인증키를 입력하세요.")
        st.stop()

    # KRX Open API의 KOSPI 시리즈 일별시세정보
    # 실제 엔드포인트/파라미터는 KRX Open API 서비스 신청 후
    # 제공되는 API 명세에 맞게 확인해야 합니다.
    url = "https://data-dam.krx.co.kr/apiservice/market/index/krx"

    today = datetime.now()
    found = False
    last_error = None

    # 오늘이 휴장일인 경우 최근 거래일을 찾기 위해 최대 10일 조회
    for i in range(10):
        date = (today - timedelta(days=i)).strftime("%Y%m%d")
        params = {
            "AUTH_KEY": api_key,
            "basDd": date,
        }

        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            # KRX API 응답 구조에 따라 데이터 목록 탐색
            rows = data.get("OutBlock_1") or data.get("data") or data.get("result") or []
            if isinstance(rows, dict):
                rows = [rows]

            kospi = None
            for row in rows:
                name = str(row.get("IDX_NM", row.get("idxNm", row.get("ISU_NM", ""))))
                if "KOSPI" in name.upper():
                    kospi = row
                    break

            if kospi:
                value = kospi.get("CLSPRC_IDX") or kospi.get("clpr") or kospi.get("CLOSE") or kospi.get("close")
                st.success(f"기준일: {date}")
                st.metric("KOSPI", value if value is not None else "조회된 값 없음")
                found = True
                break

        except Exception as e:
            last_error = e

    if not found:
        st.error("KOSPI 지수를 가져오지 못했습니다.")
        if last_error:
            st.caption(f"오류: {last_error}")
        st.info("KRX Open API에서 'KOSPI 시리즈 일별시세정보' 서비스 이용 신청 및 승인이 되어 있는지 확인하세요.")
