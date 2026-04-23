import asyncio
import logging
import sys
from infrastructure.exchange.upbit_client import UpbitClient
from infrastructure.notification.telegram_notifier import TelegramNotifier
from application.market_monitor import MarketMonitor
from application.trading_engine import TradingEngine

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger("Main")

async def main():
    logger.info("Initializing components...")
    
    # 의존성 주입 (DI)
    upbit = UpbitClient()
    telegram = TelegramNotifier()
    monitor = MarketMonitor(upbit_client=upbit)
    
    engine = TradingEngine(upbit=upbit, telegram=telegram, monitor=monitor)
    telegram.set_engine(engine) # 콜백 함수용 엔진 주입
    
    try:
        # 텔레그램 명령어 대기열 접속
        await telegram.start_polling()
        
        # 메인 자동매매 루프 시작
        await engine.run()
    except KeyboardInterrupt:
        logger.info("Bot manually stopped.")
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
    finally:
        await telegram.stop_polling()
        await upbit.close()
        logger.info("Shutdown complete.")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
