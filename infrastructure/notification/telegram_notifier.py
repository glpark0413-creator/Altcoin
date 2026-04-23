from telegram import Update, Bot
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import aiohttp
import asyncio
import socket
from config.settings import Config
import logging

logger = logging.getLogger(__name__)

class TelegramNotifier:
    def __init__(self):
        self.bot_token = Config.TELEGRAM_BOT_TOKEN
        self.chat_id = Config.TELEGRAM_CHAT_ID
        self.bot = Bot(token=self.bot_token) if self.bot_token else None
        self.engine = None
        self.app = None

    def set_engine(self, engine):
        self.engine = engine

    async def start_polling(self):
        """텔레그램 명령어(/status) 수신을 위한 백그라운드 리스너 구동"""
        if not self.bot_token:
            return
        logger.info("텔레그램 명령어(/status) 대기 모듈을 시작합니다...")
        logging.getLogger('httpx').setLevel(logging.WARNING) # httpx 로그 무시
        
        self.app = ApplicationBuilder().token(self.bot_token).build()
        self.app.add_handler(CommandHandler("status", self._status_command))
        self.app.add_handler(CommandHandler("profit", self._profit_command))
        
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling(drop_pending_updates=True)

    async def _status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """사용자가 /status 입력 시 봇 매매 현황 반환"""
        if not self.engine:
            await update.message.reply_text("봇 엔진이 아직 준비되지 않았습니다.")
            return
            
        status_msg = self.engine.get_status_summary()
        await update.message.reply_text(status_msg)
        
    async def _profit_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """사용자가 /profit 입력 시 당일/당월 수익금 요약 응답"""
        if not self.engine:
            await update.message.reply_text("봇 엔진이 아직 준비되지 않았습니다.")
            return
            
        profit_msg = (
            f"📊 [수익률 결산 (KST 기준)]\n"
            f"- 당일 누적 수익 : {self.engine.daily_pnl:,.0f} 원\n"
            f"- 당월 누적 수익 : {self.engine.monthly_pnl:,.0f} 원"
        )
        await update.message.reply_text(profit_msg)

    async def stop_polling(self):
        """명령어 수신 종료"""
        if self.app:
            await self.app.updater.stop()
            await self.app.stop()
            await self.app.shutdown()

    async def send_message(self, message: str):
        if not self.bot_token or not self.chat_id:
            logger.warning(f"Telegram not configured. Mute msg: {message}")
            return
            
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": message
        }
        
        # httpx 이벤트루프 충돌로 인한 텔레그램 서버 타임아웃 오류를 근본적으로 우회하기 위해
        # 안정성이 검증된 ccxt 공용 aiohttp 스택을 빌려 로우레벨(REST API)로 직접 쏩니다.
        # [핵심] Windows 환경의 고질적인 IPv6 파싱/라우팅 행 누수 현상을 막기 위해 IPv4 강제망 접속 지정
        for attempt in range(3):
            try:
                # 15초 타임아웃 설정
                timeout = aiohttp.ClientTimeout(total=15)
                # IPv4 전용 소켓 커넥터
                conn = aiohttp.TCPConnector(family=socket.AF_INET)
                
                async with aiohttp.ClientSession(connector=conn, timeout=timeout) as session:
                    async with session.post(url, json=payload) as response:
                        if response.status == 200:
                            return  # 전송 성공 시 즉각 리턴
                        else:
                            resp_text = await response.text()
                            logger.error(f"텔레그램 전송 실패 HTTP {response.status}: {resp_text}")
            except Exception as e:
                logger.error(f"텔레그램 전송 실패 (네트워크/타임아웃 재시도 {attempt+1}/3회): {e}")
                await asyncio.sleep(2)

    async def notify_bot_start(self, balance: float, status: str = "정상 작동 중"):
        msg = f"🚀 [봇 가동 시작]\n1. 보유 시드머니 : {balance:,.0f} KRW\n2. 봇 작동 여부 : {status}"
        await self.send_message(msg)

    async def notify_tracking_coins(self, coins_info: list):
        msg = "1. 감시 중인 코인 List - 실시간 감시 중\n"
        for i, info in enumerate(coins_info, 1):
            msg += f"- {i}번 코인 {info['symbol']} ({info['price']:,.2f}원)\n"
        await self.send_message(msg.strip())

    async def notify_buy(self, symbol: str, amount: float, price: float, fee: float, reason: str, tp1: float, tp2: float):
        msg = (
            f"🛒 [신규 매수 체결]\n"
            f"1. 매수 코인 : {symbol}\n"
            f"2. 매수 금액 : {price * amount:,.0f} 원\n"
            f"3. 매수 평단가 : {price:,.2f} 원\n"
            f"4. 매수 수수료 : {fee:,.0f} 원\n"
            f"5. 매수 근거 : {reason}\n"
            f"6. 1차 익절가 : {tp1:,.2f} 원\n"
            f"7. 2차 익절가 : {tp2:,.2f} 원"
        )
        await self.send_message(msg)

    async def notify_dca(self, dca_amount: float, total_buy_krw: float, fee: float, new_avg_price: float, tp1: float, tp2: float):
        msg = (
            f"📉 [물타기 체결]\n"
            f"1. 물타기 금액 : {dca_amount:,.0f} 원\n"
            f"2. 총 매수 금액 : {total_buy_krw:,.0f} 원\n"
            f"3. 매수 수수료 : {fee:,.0f} 원\n"
            f"4. 신규 평단가 : {new_avg_price:,.2f} 원\n"
            f"5. 1차 익절가 : {tp1:,.2f} 원\n"
            f"6. 2차 익절가 : {tp2:,.2f} 원"
        )
        await self.send_message(msg)

    async def notify_sell(self, sell_amount_krw: float, prev_avg_price: float, sell_price: float, profit: float, buy_cost: float, sell_fee: float, acc_buy_fee: float, daily_pnl: float, monthly_pnl: float):
        msg = (
            f"💰 [매도 완료]\n"
            f"1. 총 매도 금액 : {sell_amount_krw:,.0f} 원\n"
            f"2. 이전 평단가 : {prev_avg_price:,.2f} 원\n"
            f"3. 매도 평단가 : {sell_price:,.2f} 원\n"
            f"4. 수익금 : {profit:,.0f} 원\n"
            f"  (매도금액 {sell_amount_krw:,.0f} - (매수 {buy_cost:,.0f} + 매도수수료 {sell_fee:,.0f} + 누적매수수수료 {acc_buy_fee:,.0f}))\n"
            f"5. 당일 수익 : {daily_pnl:,.0f} 원\n"
            f"6. 당월 누적 수익 : {monthly_pnl:,.0f} 원"
        )
        await self.send_message(msg)

    async def notify_top3_change(self, old_top3: list, new_top3: list):
        msg = f"🔄 [주도주 Top 3 갱신]\n이전: {', '.join(old_top3)}\n현재: {', '.join(new_top3)}"
        await self.send_message(msg)
        
    async def notify_macro_off(self, btc_drop: float):
        msg = f"🚨 [매크로 생존 스위치 발동]\n사유: BTC 최근 1시간 변동률이 {btc_drop*100:.2f}% 로 하락.\n봇 가동을 즉각 중지합니다."
        await self.send_message(msg)
