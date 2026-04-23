import asyncio
import logging
import sys
import os

# To allow executing from tests directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from infrastructure.exchange.upbit_client import UpbitClient
from infrastructure.notification.telegram_notifier import TelegramNotifier

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("InfraTest")

async def test_upbit():
    upbit = UpbitClient()
    logger.info("Testing Upbit API...")
    
    krw_balance = await upbit.get_balance('KRW')
    logger.info(f"KRW Balance: {krw_balance:,.0f} KRW" if krw_balance is not None else "KRW Balance: Fetch failed")
    
    btc_price = await upbit.get_current_price('KRW-BTC')
    if btc_price is not None:
        logger.info(f"BTC Current Price: {btc_price:,.0f} KRW")
    else:
        logger.info("BTC Current Price: Fetch failed (Check API keys)")
    
    await upbit.close()

async def test_telegram():
    logger.info("Testing Telegram Bot...")
    telegram = TelegramNotifier()
    await telegram.send_message("🛠️ 스나이퍼 봇(V2.2) 인프라 연동 테스트 메시지입니다.")

async def main():
    await test_upbit()
    await test_telegram()
    logger.info("Infra tests completed.")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
