class Position:
    def __init__(self, ticker: str, volume: float, avg_price: float, current_price: float):
        self.ticker = ticker
        self.volume = volume                  # 현재 보유 수량
        self.avg_price = avg_price            # 매수 평균가
        self.current_price = current_price    # 현재가
        
        # 내부 상태 관리용 플래그
        self.half_sold = False                # 1차 익절(50%) 완료 여부
        self.current_dca_level = 0            # 현재 진행된 물타기(DCA) 단계 (0~5)

    def get_profit_percentage(self) -> float:
        """현재 수익률(%) 계산"""
        if self.avg_price == 0:
            return 0.0
            
        profit_ratio = (self.current_price - self.avg_price) / self.avg_price
        return profit_ratio * 100.0