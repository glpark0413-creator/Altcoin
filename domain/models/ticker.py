from dataclasses import dataclass

@dataclass
class Ticker:
    symbol: str
    current_price: float
    trade_value_24h: float  # 24시간 거래대금
    trade_volume_1h: float = 0.0 # 1시간 거래량 (1분봉 60개 합 등으로 계산됨)
    
    @property
    def real_trade_value_1h(self) -> float:
        """1시간 실질 거래대금 (현재가 * 1시간 거래량)"""
        return self.current_price * self.trade_volume_1h
