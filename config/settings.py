import os
import sys
from dotenv import load_dotenv

# .env 파일 로드 (보안 유지를 위해 필수)
# 루트 디렉토리에 있는 .env 파일을 찾아서 로드합니다.
load_dotenv()

# ==========================================
# [1] API KEY 및 인프라 설정 (환경 변수에서 호출)
# ==========================================
UPBIT_ACCESS = os.getenv("UPBIT_ACCESS_KEY")
UPBIT_SECRET = os.getenv("UPBIT_SECRET_KEY")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# 필수 키 누락 방어 로직 (서버 실행 시점에 바로 에러를 뱉게 하여 실수를 방지)
if not all([UPBIT_ACCESS, UPBIT_SECRET, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]):
    print("❌ 환경 변수(.env)에 API 키 또는 텔레그램 정보가 누락되었습니다. 설정을 확인해주세요.")
    sys.exit(1)


# ==========================================
# [2] 매크로 생존 스위치 및 타겟 설정
# ==========================================
BTC_CRASH_THRESHOLD = -1.5  # 최근 1시간 BTC 변동률 임계치 (%)
MONITORING_LIMIT = 3        # 거래대금 상위 동시 감시 코인 수
TIME_INTERVAL = "minute1"   # 1분봉 기준 감시


# ==========================================
# [3] 진입 및 익절 설정 (V5.0 기준)
# ==========================================
INITIAL_ENTRY_PCT = 0.20    # 초기 진입 비중: 전체 시드의 20%

TAKE_PROFIT_1_PCT = 1.5     # 1차 목표 익절가: 평단가 대비 +1.5% (물량 50% 매도)
TAKE_PROFIT_2_PCT = 2.5     # 2차 목표 익절가: 평단가 대비 +2.5% (잔량 100% 매도)


# ==========================================
# [4] 전략적 DCA (물타기) 방어 설정
# ==========================================
# 기획서 3단계의 하락률(drop_pct)과 시드 투입 비중(seed_pct) 매핑
DCA_STRATEGY = {
    1: {"drop_pct": -2.0,  "seed_pct": 0.04}, # -2% 하락 시 전체 시드의 4% 투입
    2: {"drop_pct": -4.0,  "seed_pct": 0.08},
    3: {"drop_pct": -6.0,  "seed_pct": 0.13},
    4: {"drop_pct": -10.0, "seed_pct": 0.21},
    5: {"drop_pct": -15.0, "seed_pct": 0.34},
}