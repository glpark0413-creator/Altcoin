import os
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

class Config:
    # API Keys
    UPBIT_ACCESS_KEY = os.getenv("UPBIT_ACCESS_KEY", "")
    UPBIT_SECRET_KEY = os.getenv("UPBIT_SECRET_KEY", "")
    
    # Telegram
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

    # Trading Parameters
    TRADE_FEE = 0.0005  # 업비트 원화마켓 수수료 0.05%
    INITIAL_INVESTMENT_RATIO = 0.20  # 1차 진입: 남은 원화의 20%
    MAX_TRACKING_COINS = 3  # 실시간 감시할 Top 3 코인 수
    MACRO_BTC_DROP_THRESHOLD = -0.015  # 1시간 비트코인 변동률 -1.5% 이상 하락 시 스위치 오프

    # DCA Parameters (하락폭 기준)
    DCA_DROP_THRESHOLD = -0.01  # -1% 하락할 때마다 물타기
    
    # DCA Ratios (보유 현금 총액 기준)
    DCA_STEPS = [
        0.05,  # 1차 추매: 잔여 현금 5%
        0.10,  # 2차 추매: 잔여 현금 10%
        0.15,  # 3차 추매: 잔여 현금 15%
        0.20,  # 4차 추매: 잔여 현금 20%
        0.40,  # 5차 추매: 잔여 현금 40%
        1.00   # 6차 추매: 남은 현금 올인
    ]

    # Take-Profit Parameters (평단가 대비)
    TAKE_PROFIT_1_THRESHOLD = 0.015  # 1차 익절: +1.5%
    TAKE_PROFIT_1_RATIO = 0.50       # 1차 익절: 물량 50% 매도
    
    TAKE_PROFIT_2_THRESHOLD = 0.025  # 2차 익절: +2.5%
    TAKE_PROFIT_2_RATIO = 1.00       # 2차 익절: 남은 물량 100% 매도 (전체 대비 50%)

    # Strategy Parameters (1분봉 기준)
    RSI_PERIOD = 14
    RSI_OVERSOLD_THRESHOLD = 45
    VOLUME_MA_PERIOD = 10
    VOLUME_SPIKE_RATIO = 2.0  # 평균의 200% 이상 폭발
    EMA_PERIOD = 20

    # Polling & System Delays
    POLL_INTERVAL_SEC = 2.0  # 메인 루프 감시 주기 (초)
    MONITOR_UPDATE_INTERVAL_SEC = 60  # Top 3 탐색 주기 (초)
