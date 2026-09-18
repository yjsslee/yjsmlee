import streamlit as st

st.set_page_config(page_title="키움증권 주식 대시보드 주제", page_icon="📊", layout="wide")

st.title("📊 키움증권 모의투자 주식 대시보드")
st.caption("APP Key / APP Secret를 이용해 향후 키움증권 API와 연결할 대시보드 구성입니다.")

st.header("대시보드에 넣을 주요 주제")

topics = [
    ("1. 계좌 정보", "계좌번호, 예수금, 출금가능금액, 투자가능금액 등을 표시합니다."),
    ("2. 보유 종목", "종목명, 종목코드, 보유수량, 평균매입가, 현재가, 평가금액을 표시합니다."),
    ("3. 수익률", "종목별 평가손익과 수익률, 전체 계좌의 평가손익을 표시합니다."),
    ("4. 오늘의 시장", "코스피·코스닥 지수와 등락률 등 시장 현황을 표시합니다."),
    ("5. 관심 종목", "관심 종목의 현재가, 등락률, 거래량 등을 확인합니다."),
    ("6. 종목 상세 정보", "선택한 종목의 현재가, 시가, 고가, 저가, 거래량 등을 표시합니다."),
    ("7. 주가 차트", "선택한 종목의 기간별 주가 흐름을 차트로 표시합니다."),
    ("8. 주문/체결 현황", "주문내역, 미체결 주문, 체결내역 등을 확인합니다."),
    ("9. 투자 요약", "총 평가금액, 총 손익, 수익률 등 계좌의 핵심 지표를 한눈에 보여줍니다."),
    ("10. 데이터 다운로드", "보유 종목과 계좌 데이터를 CSV 파일로 내려받을 수 있도록 구성합니다."),
]

for title, description in topics:
    with st.container(border=True):
        st.subheader(title)
        st.write(description)

st.divider()
st.info("다음 단계에서는 이 화면의 각 항목에 실제 키움증권 모의투자 API 데이터를 연결할 수 있습니다.")

st.sidebar.header("🔐 키움증권 API 인증")
st.sidebar.text_input("APP Key", type="password", placeholder="APP Key 입력")
st.sidebar.text_input("APP Secret", type="password", placeholder="APP Secret 입력")
st.sidebar.button("API 연결 테스트")

st.sidebar.caption("※ APP Key와 APP Secret은 코드에 직접 저장하지 마세요.")
