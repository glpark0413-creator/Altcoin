import pyupbit
import time
from domain.position import Position

class UpbitClient:
    def __init__(self, access_key: str, secret_key: str):
        self.upbit = pyupbit.Upbit(access_key, secret_key)

    def get_krw_balance(self) -> float:
        """현재 보유 중인 원화(KRW) 잔고 조회"""
        balance = self.upbit.get_balance("KRW")
        return float(balance) if balance is not None else 0.0

    def get_position(self, ticker: str) -> Position:
        """특정 코인의 현재 보유 상태, 평단가, 수익률을 Domain 객체로 반환"""
        balance = self.upbit.get_balance(ticker)
        avg_buy_price = self.upbit.get_avg_buy_price(ticker)
        current_price = pyupbit.get_current_price(ticker)
        
        # 잔고가 없으면 빈 포지션 반환
        if balance == 0 or balance is None:
            return Position(ticker=ticker, volume=0, avg_price=0, current_price=current_price)
            
        return Position(
            ticker=ticker, 
            volume=float(balance), 
            avg_price=float(avg_buy_price), 
            current_price=float(current_price)
        )

    def buy_market_order(self, ticker: str, amount: float) -> dict:
        """시장가 매수 실행 및 결과 데이터 파싱"""
        # 업비트 최소 주문 금액(5,000원) 확인 로직 등 추가 가능
        result = self.upbit.buy_market_order(ticker, amount)
        
        # API 호출 제한 등에 걸려 실패했을 경우의 예외 처리
        if result is None or 'error' in result:
            raise Exception(f"매수 주문 실패: {result}")
            
        # 체결 완료 대기 (시장가 주문이 완전히 체결될 때까지 약간의 딜레이 필요)
        time.sleep(1)
        
        # 주문 UUID로 상세 체결 정보 조회
        order_info = self.upbit.get_order(result['uuid'])
        
        # 리포팅을 위한 데이터 정제
        trade_data = {
            'coin': ticker,
            'total_price': float(order_info.get('price', amount)), # 체결 금액
            'fee': float(order_info.get('paid_fee', 0)),           # 지불 수수료
            'avg_price': self.upbit.get_avg_buy_price(ticker),     # 매수 후 갱신된 평단가
            'remain_krw': self.get_krw_balance()                   # 매수 후 잔여 현금
        }
        return trade_data

    def sell_market_order(self, ticker: str, volume: float) -> dict:
        """시장가 매도 실행 및 결과 데이터 파싱"""
        result = self.upbit.sell_market_order(ticker, volume)
        
        if result is None or 'error' in result:
            raise Exception(f"매도 주문 실패: {result}")
            
        time.sleep(1)
        order_info = self.upbit.get_order(result['uuid'])
        
        trade_data = {
            'coin': ticker,
            'total_price': float(order_info.get('price', 0)),   # 매도 체결 금액
            'fee': float(order_info.get('paid_fee', 0)),        # 매도 수수료
            'avg_price': float(order_info.get('price', 0)) / volume if volume > 0 else 0, # 체결 평단가
            'remain_krw': self.get_krw_balance()                # 매도 후 잔여 현금
        }
        return trade_data