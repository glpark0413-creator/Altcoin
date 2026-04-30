import time
from datetime import datetime
import logging
from domain.market_analyzer import MarketAnalyzer
from domain.strategy import SniperStrategy
from infrastructure.upbit_client import UpbitClient
from infrastructure.telegram_bot import TelegramReporter

# 로거 설정
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)
logger.addHandler(stream_handler)

class BotService:
    def __init__(self, upbit: UpbitClient, telegram: TelegramReporter):
        self.upbit = upbit
        self.telegram = telegram
        self.market = MarketAnalyzer()
        self.total_seed = self.upbit.get_krw_balance()
        self.current_target = None  # 현재 매매 중인 코인
        self.current_target_dca_level = 0     # 타겟의 물타기 단계 기억
        self.current_target_half_sold = False # 타겟의 절반 익절 여부 기억
        self.daily_profit = 0.0
        self.monthly_profit = 0.0
        
        import pytz
        kst = pytz.timezone('Asia/Seoul')
        now = datetime.now(kst)
        self.current_day = now.day
        self.current_month = now.month
        
        self.last_reported_top_coins = [] # 텔레그램 스팸 방지용 (이전 Top 3 기억)
        self.last_scan_time = 0 # 5분 주기 스캔을 위한 타임스탬프
        self.cached_target_coins = [] # 5분 동안 유지할 타겟 코인


    def run_infinite_loop(self):
        self.telegram.send_message("🚀 스나이퍼 매매 알고리즘 V5.0 가동 시작")
        self.telegram.send_message(f"💰 현재 보유 현금(KRW): {self.total_seed:,.0f}원")
        print("\n🚀 스나이퍼 봇 시스템 감시 루프 시작")
        
        while True:
            try:
                import pytz
                kst = pytz.timezone('Asia/Seoul')
                now_kst = datetime.now(kst)
                
                # [초기화 로직] 매일 자정(KST)이 넘어가면 당일 수익 초기화, 1일이면 당월 수익 초기화
                if now_kst.day != self.current_day:
                    self.daily_profit = 0.0
                    self.current_day = now_kst.day
                if now_kst.month != self.current_month:
                    self.monthly_profit = 0.0
                    self.current_month = now_kst.month

                now_str = now_kst.strftime('%Y-%m-%d %H:%M:%S')
                print(f"\n[{now_str}] 🔄 새로운 감시 사이클 시작")
                
                # 텔레그램 명령어 확인
                commands = self.telegram.get_new_commands()
                for cmd in commands:
                    if cmd == "/status":
                        self.telegram.send_message(
                            f"📊 <b>[현재 로봇 동작 상태]</b>\n"
                            f"📈 당일 누적 수익: {self.daily_profit:,.0f} KRW\n"
                            f"📅 당월 누적 수익: {self.monthly_profit:,.0f} KRW\n"
                            f"💰 현재 보유 현금: {self.upbit.get_krw_balance():,.0f} KRW"
                        )
                    elif cmd.strip().lower() in ["sell", "/sell"]:
                        if self.current_target:
                            self.telegram.send_message(f"⚠️ <b>[수동 개입]</b> 사용자의 매도 명령에 따라 <b>{self.current_target}</b> 전량 매도를 실행합니다.")
                            self._execute_manual_sell()
                        else:
                            self.telegram.send_message("⚠️ 현재 진입 중인 종목이 없어 매도할 수 없습니다.")

                # [매크로 생존 스위치] BTC -1.5% 폭락 시 대기
                if self.market.is_btc_crashing():
                    print("⚠️ BTC 급락 감지. 매매 일시 중지")
                    self.telegram.send_message("⚠️ BTC 급락 감지. 매매를 일시 중지합니다.")
                    time.sleep(60)
                    continue

                print("[STEP 1] 📊 업비트에서 코인 가격 데이터 수집 중...")
                
                if not self.current_target:
                    print("[STEP 2] 🧠 기술적 지표 계산 및 타점 분석 중...")
                    print("[STEP 3] 💰 매수 조건 검토 및 주문 대기...")
                    self._search_and_entry()
                else:
                    print(f"[STEP 2] 🧠 보유 종목({self.current_target}) 수익률 및 지표 분석 중...")
                    print("[STEP 3] 💰 매도/물타기 조건 검토 및 주문 대기...")
                    self._manage_position()

                print("[STEP 4] ✅ 1주기 완료. 10초 대기합니다. 💤")
                time.sleep(10) # 10초 간격 대기
                
            except Exception as e:
                self.telegram.send_message(f"❌ 시스템 에러: {e}")
                time.sleep(10)

    def _search_and_entry(self):
        """[1단계 & 2단계] 종목 필터링 및 진입"""
        current_time = time.time()
        
        # --- 300초(5분) 주기 스캔 로직 ---
        if current_time - self.last_scan_time >= 300 or not self.cached_target_coins:
            print("🔍 [5분 주기] 거래대금 Top10 중 최고 변동성(4H) 코인 Top 3 스캔 중...")
            self.cached_target_coins = self.market.get_best_target_coins()
            self.last_scan_time = current_time
            
            # 타겟 종목이 변경되었을 때만 텔레그램 발송
            if self.cached_target_coins != self.last_reported_top_coins:
                coins_str = ", ".join(self.cached_target_coins)
                self.telegram.send_message(f"🏆 [Top3 타겟 갱신] 4H 변동성 분석 완료\n👉 {coins_str} 집중 감시 중!")
                print(f"📲 [텔레그램 발송] 🏆 새로운 타겟 감시 리스트: {coins_str}")
                self.last_reported_top_coins = self.cached_target_coins
        # ---------------------------------

        for coin in self.cached_target_coins:
            df_1m = self.market.get_indicators(coin)
            
            if SniperStrategy.is_sniper_entry(df_1m):
                # 타점 발생! 최신 계좌 잔고를 다시 가져와 복리(늘어난 시드) 적용
                self.total_seed = self.upbit.get_krw_balance()
                
                # 최신 시드의 30% 진입
                entry_amount = self.total_seed * 0.30
                buy_result = self.upbit.buy_market_order(coin, entry_amount)
                
                self.current_target = coin
                self.current_target_dca_level = 0     # 진입 시 물타기 상태 초기화
                self.current_target_half_sold = False # 진입 시 익절 상태 초기화
                self.telegram.send_buy_report(buy_result)
                break # 다중 감시 중 하나 걸리면 집중

    def _manage_position(self):
        """[3단계 & 4단계] 방어(DCA) 및 익절 처리"""
        position = self.upbit.get_position(self.current_target)
        profit_pct = position.get_profit_percentage()

        # 1. 익절 검사
        exit_signal = SniperStrategy.check_exit_condition(profit_pct)
        if exit_signal == "FULL_EXIT":
            sell_result = self.upbit.sell_market_order(self.current_target, volume=position.volume)
            buy_amount = position.avg_price * position.volume
            buy_fee = buy_amount * 0.0005 # 업비트 기본 수수료율 0.05%
            
            profit = sell_result['total_price'] - (buy_amount + sell_result['fee'] + buy_fee)
            self.daily_profit += profit
            self.monthly_profit += profit
            self.telegram.send_sell_report(sell_result, buy_amount, buy_fee, self.daily_profit, self.monthly_profit)
            
            self.current_target = None # 무한 루프 초기화 (1단계 복귀)
            self.current_target_dca_level = 0
            self.current_target_half_sold = False
            return
            
        elif exit_signal == "HALF_EXIT" and not self.current_target_half_sold:
            sell_volume = position.volume * 0.5
            sell_result = self.upbit.sell_market_order(self.current_target, volume=sell_volume)
            self.current_target_half_sold = True # 스팸/무한 매도 방지용 로컬 저장
            
            buy_amount = position.avg_price * sell_volume
            buy_fee = buy_amount * 0.0005
            
            profit = sell_result['total_price'] - (buy_amount + sell_result['fee'] + buy_fee)
            self.daily_profit += profit
            self.monthly_profit += profit
            self.telegram.send_sell_report(sell_result, buy_amount, buy_fee, self.daily_profit, self.monthly_profit)

        # 2. 물타기(DCA) 검사
        dca_level = SniperStrategy.check_dca_level(profit_pct)
        if dca_level > self.current_target_dca_level:
            # 설정된 시드 비율만큼 추가 매수 로직 실행
            self._execute_dca(dca_level, position)

    def _execute_dca(self, dca_level: int, position):
        """[방어] 지정된 단계의 비중만큼 물타기 추가 매수 실행"""
        # 단계별 시드 투입 비율 (총 70% 비중, 피보나치 기반 조정)
        dca_rates = {
            1: 0.04,  # -2.0% 하락 시 4% 투입
            2: 0.07,  # -4.0% 하락 시 7% 투입
            3: 0.11,  # -6.0% 하락 시 11% 투입
            4: 0.18,  # -10.0% 하락 시 18% 투입
            5: 0.30   # -15.0% 하락 시 30% 투입
        }
        
        rate = dca_rates.get(dca_level, 0)
        if rate == 0:
            return

        # 포지션 객체 상태 업데이트 (내부 보존용)
        self.current_target_dca_level = dca_level
        
        buy_amount = self.total_seed * rate
        buy_result = self.upbit.buy_market_order(self.current_target, buy_amount)
        
        # 텔레그램 보고
        self.telegram.send_message(
            f"🚨 <b>[방어 시스템: 물타기 {dca_level}단계 발동]</b>\n"
            f"종목: {self.current_target}\n"
            f"추가 투입 금액: ₩{buy_amount:,.0f}\n"
            f"체결 단가: ₩{buy_result['avg_price']:,.2f}"
        )

    def _execute_manual_sell(self):
        """[수동 개입] 텔레그램 명령에 의한 즉시 전량 매도 실행"""
        position = self.upbit.get_position(self.current_target)
        if not position or position.volume <= 0:
            return

        # 전량 시장가 매도
        sell_result = self.upbit.sell_market_order(self.current_target, volume=position.volume)
        buy_amount = position.avg_price * position.volume
        buy_fee = buy_amount * 0.0005 # 업비트 기본 수수료율 0.05%
        
        # 수익금 계산
        profit = sell_result['total_price'] - (buy_amount + sell_result['fee'] + buy_fee)
        self.daily_profit += profit
        self.monthly_profit += profit
        
        # 기존 자동 매도와 동일한 포맷으로 수익금 및 누적 수익 현황 보고
        self.telegram.send_sell_report(sell_result, buy_amount, buy_fee, self.daily_profit, self.monthly_profit)
        
        # 내부 상태 1단계로 완전 초기화
        self.current_target = None
        self.current_target_dca_level = 0
        self.current_target_half_sold = False
        
        # 수동 전량 매도 직후, 기존 타겟 리스트를 비우고 스캔 타이머를 초기화하여 
        # 알고리즘이 즉시 새로운 타겟 코인 3대장을 다시 찾으러 가도록 강제합니다.
        self.cached_target_coins = []
        self.last_scan_time = 0