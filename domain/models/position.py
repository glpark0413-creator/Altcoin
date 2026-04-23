from dataclasses import dataclass, field
from typing import Optional

@dataclass
class Position:
    symbol: str
    total_amount: float = 0.0          # 보유 총 수량
    total_cost: float = 0.0            # 총 매수 대금 (수수료 포함)
    dca_step: int = 0                  # 현재 물타기 단계 (0이면 1차 진입 상태)
    
    # 1차 익절(50%)이 나갔는지 여부
    tp_1_executed: bool = False
    
    @property
    def avg_price(self) -> float:
        if self.total_amount <= 0:
            return 0.0
        return self.total_cost / self.total_amount
    
    @property
    def is_empty(self) -> bool:
        return self.total_amount <= 1e-8 # 매우 작은 수량이 남는 float 오차 처리
        
    def add_buy(self, price: float, amount: float, fee: float):
        """매수 체결 시 평단가 및 수량 갱신 (비용 = 체결가*수량 + 수수료)"""
        cost = (price * amount) + fee
        self.total_cost += cost
        self.total_amount += amount

    def subtract_sell(self, amount: float, fee: float):
        """매도 체결 시 수량 및 매수대금 갱신. (총매수대금에서 매도비율만큼 차감)"""
        if self.is_empty:
            return
        
        ratio = amount / self.total_amount
        if ratio > 1.0:
            ratio = 1.0 # 보정
            
        self.total_cost -= (self.total_cost * ratio)
        self.total_amount -= amount
        
        if self.total_amount <= 1e-8:
            self.total_amount = 0.0
            self.total_cost = 0.0
            self.dca_step = 0
            self.tp_1_executed = False

    def reset(self):
        """초기 상태로 리셋"""
        self.total_amount = 0.0
        self.total_cost = 0.0
        self.dca_step = 0
        self.tp_1_executed = False
