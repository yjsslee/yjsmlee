# 나의 주식분석 대시보드

KRX Open API와 키움증권 REST API(모의투자)를 이용하는 Streamlit 기반 개인용 주식분석 대시보드입니다.

## 현재 기능

- KOSPI/KOSDAQ 최근 지수 조회
- KOSPI/KOSDAQ 최근 추이 차트
- 키움 모의투자 OAuth 인증
- 계좌번호 조회
- 예수금 및 투자가능금액 조회
- 계좌 평가금액/누적손익률 조회
- 보유종목 조회
- 종목코드 입력을 통한 종목 기본정보 조회
- 실제 주문 기능은 포함하지 않음

## API Key 보안

API Key와 App Secret은 GitHub에 저장하지 않습니다. Streamlit Community Cloud에서는 앱의 **Settings → Secrets**에 아래 TOML을 붙여 넣습니다.

```toml
KRX_API_KEY = "여기에_KRX_인증키"
KIWOOM_APP_KEY = "여기에_키움_모의투자_App_Key"
KIWOOM_APP_SECRET = "여기에_키움_모의투자_App_Secret"
```

로컬에서는 프로젝트 폴더의 `.streamlit/secrets.toml`에 같은 내용을 넣을 수 있습니다. `.streamlit/`은 `.gitignore`에 포함되어 있습니다.

## 실행

```bash
pip install -r requirements.txt
streamlit run app.py
```

키움 모의투자 App Key/App Secret은 실전투자용과 별도로 관리해야 합니다. KRX Open API도 발급·승인된 인증키가 필요합니다.
