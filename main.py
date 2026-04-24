from infrastructure.upbit_client import UpbitClient
from infrastructure.telegram_bot import TelegramReporter
from application.bot_service import BotService
from config import settings

if __name__ == "__main__":
    print("🟢 스나이퍼 봇 시스템 초기화 중...")
    
    # 1. 인프라 객체 초기화 (의존성 주입)
    upbit_client = UpbitClient(settings.UPBIT_ACCESS, settings.UPBIT_SECRET)
    telegram = TelegramReporter(settings.TELEGRAM_TOKEN, settings.TELEGRAM_CHAT_ID)
    
    # 2. 어플리케이션 서비스에 인프라 객체 주입
    bot = BotService(upbit_client, telegram)
    
    print("🚀 24시간 무한 루프 감시를 시작합니다!")
    # 3. 무한 루프 시작 (이 함수 안에 while True가 들어있습니다)
    bot.run_infinite_loop()