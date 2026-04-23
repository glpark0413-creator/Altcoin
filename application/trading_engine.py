import asyncio
import logging
import pandas as pd
from typing import Optional

from config.settings import Config
from infrastructure.exchange.upbit_client import UpbitClient
from infrastructure.notification.telegram_notifier import TelegramNotifier
from application.market_monitor import MarketMonitor
from domain.models.position import Position
from domain.strategy.indicators import calculate_indicators, check_entry_conditions
from domain.strategy.sniper_v2 import SniperStrategyV2

logger = logging.getLogger(__name__)

class TradingEngine:
    def __init__(self, upbit: UpbitClient, telegram: TelegramNotifier, monitor: MarketMonitor):
        self.upbit = upbit
        self.telegram = telegram
        self.monitor = monitor
        
        # 현재 보유중인 포지션 모델 초기화 (1개 종목만 집중 매수하므로 단일 객체)
        self.position = Position(symbol="")
        self.is_running = False
        
        # 타이머 관리를 위한 속성
        self.last_top3_update = 0
        self.last_hourly_msg_time = 0
        
        # 누적 수수료 및 기간별 수익금 관리
        self.acc_buy_fee = 0.0
        self.daily_pnl = 0.0
        self.monthly_pnl = 0.0
        self.current_day = ""
        self.current_month = ""
        self.last_log_state = ""

    def _log_state(self, msg: str):
        if self.last_log_state != msg:
            logger.info(msg)
            self.last_log_state = msg

    def get_status_summary(self) -> str:
        """텔레그램에서 /status 명령어 입력 시 반환할 상태 요약 메세지"""
        if self.position.is_empty:
            top3 = getattr(self.monitor, 'top_3_symbols', [])
            return (
                f"🔎 [현재 봇 상태: 대기 중]\n"
                f"- 보유 종목: 없음\n"
                f"- 감시 중인 주도주 Top 3: {', '.join(top3) if top3 else '탐색 중'}\n"
                f"- 봇 가동 시 누적 수익금: {self.daily_pnl:,.0f} 원\n"
                f"- 이번 달 총 누적 수익: {self.monthly_pnl:,.0f} 원"
            )
        else:
            return (
                f"🛡️ [현재 봇 상태: 포지션 보유 중]\n"
                f"- 보유 종목: {self.position.symbol}\n"
                f"- 매수 평단가: {self.position.avg_price:,.2f} 원\n"
                f"- 총 매수 금액: {self.position.total_cost:,.0f} 원\n"
                f"- 물타기(DCA) 단계: {self.position.dca_step} 단계\n"
                f"- 단타 및 봇 누적 수익: {self.daily_pnl:,.0f} 원"
            )

    async def _wait_for_closed_order(self, order_id: str, symbol: str):
        """업비트 서버에서 체결 정보(수수료, 평균단가)가 완벽히 계산될 때까지 최대 1.5초 대기하며 조회"""
        for _ in range(3):
            await asyncio.sleep(0.5)
            fetched = await self.upbit.fetch_order(order_id, symbol)
            if fetched and fetched.get('status') == 'closed':
                return fetched
        return None

    async def run(self):
        self.is_running = True
        logger.info("Starting Trading Engine V2.2...")
        
        # 1차 메세지 (보유 시드머니 조회 및 봇 시작 알림)
        initial_balance = await self.upbit.get_balance('KRW')
        await self.telegram.notify_bot_start(balance=initial_balance)

        # 타이머 초기화 반영은 __init__에서 처리됨

        while self.is_running:
            try:
                now = asyncio.get_event_loop().time()
                
                # 매크로 감시 및 Top 3 갱신 (60초 주기)
                if now - self.last_top3_update > Config.MONITOR_UPDATE_INTERVAL_SEC:
                    self._log_state("⏳ [루틴 주기] 비트코인 일시 하락 감시 판별 및 주도주 Top 3 현행화 검사 중...")
                    is_macro_danger = await self.monitor.check_macro_switch()
                    if is_macro_danger:
                        await self.telegram.notify_macro_off(Config.MACRO_BTC_DROP_THRESHOLD)
                        self.is_running = False
                        break
                        
                    old_top3, new_top3 = await self.monitor.update_top_3()
                    
                    has_changed = (set(old_top3) != set(new_top3))
                    is_hourly = (now - self.last_hourly_msg_time > 3600)
                    
                    if has_changed or is_hourly:
                        if new_top3:
                            top3_info = []
                            for sym in new_top3:
                                price = await self.upbit.get_current_price(sym)
                                top3_info.append({"symbol": sym, "price": price or 0})
                            # 2차 메세지: 감시 코인 리스트 발송
                            await self.telegram.notify_tracking_coins(top3_info)
                        self.last_hourly_msg_time = now

                    if has_changed and old_top3:
                        await self.telegram.notify_top3_change(old_top3, new_top3)
                    
                    self.last_top3_update = now

                # 포지션이 비어있다면: [1, 2단계] Top 3 모니터링 및 진입 조건 체킹
                if self.position.is_empty:
                    top3_symbols = getattr(self.monitor, 'top_3_symbols', [])
                    self._log_state(f"🔎 [1단계: 타점 감시] 현재 1~3위 코인({', '.join(top3_symbols)})의 데이터(RSI/EMA)를 실시간 추적합니다.")
                    await self._handle_entry_monitoring()
                # 포지션이 존재한다면: [3, 4단계] DCA 추매 및 익절 조건 체킹
                else:
                    self._log_state(f"🛡️ [3단계: 포지션 방어 및 대기] {self.position.symbol} 보유 중(평단: {self.position.avg_price:,.2f}원). 물타기 {self.position.dca_step}단계 적용되었으며 익절/본절 방어 감시 중...")
                    await self._handle_position_management()

                # API 호출 제한 고려 (쿨다운)
                await asyncio.sleep(Config.POLL_INTERVAL_SEC)
                
            except Exception as e:
                logger.error(f"Error in main loop: {e}", exc_info=True)
                await asyncio.sleep(5)

    async def _handle_entry_monitoring(self):
        """Top 3 종목 중 조건에 맞는 첫 번째 종목에 진입"""
        if not self.monitor.top_3_symbols:
            return

        for symbol in self.monitor.top_3_symbols:
            # 1분봉 데이터 수집 (지표 계산을 위해 충분한 갯수 30 이상)
            ohlcv = await self.upbit.fetch_ohlcv(symbol, timeframe='1m', limit=30)
            if not ohlcv or len(ohlcv) < Config.EMA_PERIOD + 1:
                continue
                
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df = calculate_indicators(df)
            
            is_entry_signal = check_entry_conditions(df)
            
            if is_entry_signal:
                # 진입 조건 충족! -> 가용 현금 20% 진입
                krw_balance = await self.upbit.get_balance('KRW')
                invest_amount = krw_balance * Config.INITIAL_INVESTMENT_RATIO
                
                # 거래량이 너무 작으면 제한
                if invest_amount < 5000:
                    logger.warning(f"⚠️ 매수 실패: 가용 KRW({invest_amount})가 업비트 최소 주문 단위(5000원)보다 작습니다.")
                    return

                logger.info(f"🎯 [2단계: 스나이퍼 매수] {symbol} 종목의 정밀 타점 포착! 1차 시장가 매수를 진행합니다.")
                # 마켓 매수 주문 전송
                order = await self.upbit.create_market_buy_order(symbol, invest_amount)
                
                if order:
                    order_id = order.get('id')
                    closed_order = await self._wait_for_closed_order(order_id, symbol)
                    if closed_order:
                        order = closed_order
                        
                    # 체결 정보 널(None) 방어 로직
                    price = order.get('average') or order.get('price') or 0
                    amount = order.get('filled') or order.get('amount') or 0
                    fee_info = order.get('fee')
                    fee = fee_info.get('cost') if fee_info and 'cost' in fee_info else (invest_amount * Config.TRADE_FEE)
                    
                    # 현재가로 임시 기록
                    if not price or not amount:
                        price = await self.upbit.get_current_price(symbol)
                        amount = (invest_amount - fee) / price

                    self.position.symbol = symbol
                    self.position.add_buy(price, amount, fee)
                    self.acc_buy_fee = fee # 첫 매수 수수료 등록
                    
                    # 3차 메세지 발송을 위한 파라미터 준비
                    reason = "1분봉 RSI 45이하 반등 성공 및 20 EMA 상단 회복 (단기 눌림목 돌파)"
                    tp1_price = price * (1 + Config.TAKE_PROFIT_1_THRESHOLD)
                    tp2_price = price * (1 + Config.TAKE_PROFIT_2_THRESHOLD)
                    
                    await self.telegram.notify_buy(
                        symbol=symbol,
                        amount=amount,
                        price=price,
                        fee=fee,
                        reason=reason,
                        tp1=tp1_price,
                        tp2=tp2_price
                    )
                    
                    # 매수 직후 1시간 타이머 리셋
                    self.last_hourly_msg_time = asyncio.get_event_loop().time()
                    
                # 1개 종목 집중 매수 원칙이므로 반복문 종료
                break

    async def _handle_position_management(self):
        """현재 보유중인 종목의 가격을 모니터링하며 수익 실현 또는 물타기(DCA) 수행"""
        symbol = self.position.symbol
        current_price = await self.upbit.get_current_price(symbol)
        
        if not current_price:
            return

        # 1. 익절/본절 방어 조건 체크
        action, sell_ratio = SniperStrategyV2.check_tp_condition(self.position, current_price)
        
        if action:
            logger.info(f"💡 [4단계: 매도 발동] {symbol} {action} 조건 달성! 시장가 매도를 진행합니다.")
            sell_amount = self.position.total_amount * sell_ratio
            # 안전하게 남은 수량 보정
            if sell_amount > self.position.total_amount:
                sell_amount = self.position.total_amount

            # 마켓 매도 주문
            order = await self.upbit.create_market_sell_order(symbol, amount=sell_amount)
            if order:
                order_id = order.get('id')
                closed_order = await self._wait_for_closed_order(order_id, symbol)
                if closed_order:
                    order = closed_order
                    
                # 수익 계산용 파라미터 준비
                sell_price = order.get('average') or order.get('price') or current_price
                
                # 업비트 API가 확정한 순수 총 매도 원화(KRW) 가치 최우선 사용
                sell_amount_krw = order.get('cost') or (sell_amount * sell_price)
                
                sell_fee_info = order.get('fee')
                sell_fee = sell_fee_info.get('cost') if sell_fee_info and 'cost' in sell_fee_info else (sell_amount_krw * Config.TRADE_FEE)
                
                buy_ratio = sell_amount / self.position.total_amount
                
                # 순수 매수 금액 = (포지션 총 비용 - 누적 수수료) * 비율
                buy_cost_raw = (self.position.total_cost - self.acc_buy_fee) * buy_ratio
                acc_buy_fee_used = self.acc_buy_fee * buy_ratio
                
                profit = sell_amount_krw - (buy_cost_raw + sell_fee + acc_buy_fee_used)
                
                from datetime import datetime, timezone, timedelta
                kst = timezone(timedelta(hours=9))
                now_kst = datetime.now(kst)
                today_str = now_kst.strftime("%Y%m%d")
                month_str = now_kst.strftime("%Y%m")
                
                if self.current_day != today_str:
                    self.daily_pnl = 0.0
                    self.current_day = today_str
                if self.current_month != month_str:
                    self.monthly_pnl = 0.0
                    self.current_month = month_str
                    
                self.daily_pnl += profit
                self.monthly_pnl += profit
                
                prev_avg_price = self.position.avg_price
                
                # 내부 상태 관리 (매도량 반영 시 누적수수료도 함께 차감)
                self.position.subtract_sell(sell_amount, 0)
                self.acc_buy_fee -= acc_buy_fee_used
                if self.position.is_empty:
                    self.acc_buy_fee = 0.0

                # 5차 메세지 (매도 알림)
                await self.telegram.notify_sell(
                    sell_amount_krw=sell_amount_krw, 
                    prev_avg_price=prev_avg_price, 
                    sell_price=sell_price, 
                    profit=profit, 
                    buy_cost=buy_cost_raw, 
                    sell_fee=sell_fee, 
                    acc_buy_fee=acc_buy_fee_used, 
                    daily_pnl=self.daily_pnl, 
                    monthly_pnl=self.monthly_pnl
                )

                if action == 'tp1':
                    self.position.tp_1_executed = True

            # 익절 후 포지션이 비워졌다면 바로 리턴 (루프 1단계로 자동 이동됨)
            if self.position.is_empty:
                return

        # 2. 물타기(DCA) 조건 체크
        dca_next_step = SniperStrategyV2.check_dca_condition(self.position, current_price)
        
        if dca_next_step is not None:
            logger.info(f"📉 [3단계: 물타기 발동] {symbol} 수익률 하락 방어를 목적으로 {dca_next_step}단계 DCA 매수를 집행합니다.")
            krw_balance = await self.upbit.get_balance('KRW')
            dca_ratio = SniperStrategyV2.get_dca_amount_ratio(dca_next_step)
            
            invest_amount = krw_balance * dca_ratio
            if invest_amount >= 5000: # 업비트 최소 주문 금액
                order = await self.upbit.create_market_buy_order(symbol, invest_amount)
                if order:
                    order_id = order.get('id')
                    closed_order = await self._wait_for_closed_order(order_id, symbol)
                    if closed_order:
                        order = closed_order
                        
                    price = order.get('average') or order.get('price') or current_price
                    amount = order.get('filled') or order.get('amount') or ((invest_amount - invest_amount * Config.TRADE_FEE) / price)
                    fee_info = order.get('fee')
                    fee = fee_info.get('cost') if fee_info and 'cost' in fee_info else (invest_amount * Config.TRADE_FEE)
                    
                    self.position.add_buy(price, amount, fee)
                    self.position.dca_step = dca_next_step
                    self.acc_buy_fee += fee  # 누적 수수료 합산
                    
                    # 4차 메세지 발송
                    new_avg_price = self.position.avg_price
                    total_buy_krw = self.position.total_cost
                    tp1_price = new_avg_price * (1 + Config.TAKE_PROFIT_1_THRESHOLD)
                    tp2_price = new_avg_price * (1 + Config.TAKE_PROFIT_2_THRESHOLD)
                    
                    await self.telegram.notify_dca(
                        dca_amount=invest_amount,
                        total_buy_krw=total_buy_krw,
                        fee=fee,
                        new_avg_price=new_avg_price,
                        tp1=tp1_price,
                        tp2=tp2_price
                    )
