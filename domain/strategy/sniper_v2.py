from typing import List, Tuple, Optional
from domain.models.ticker import Ticker
from domain.models.position import Position
from config.settings import Config

class SniperStrategyV2:
    @staticmethod
    def select_top_3(tickers_data: List[Ticker]) -> List[str]:
        """
        주어진 15개 가량의 티커 목록에서 현재 거래가 완전히 멈춘 코인 제외(예외 처리),
        그리고 '최근 1시간 실질 거래대금(현재가 * 1시간 거래량)'을 기준으로 정렬하여 Top 3 코인 명칭 도출.
        """
        valid_tickers = []
        for t in tickers_data:
            # 거래가 정지되거나 완전히 멈춘 코인 제외: 1시간 거래량이 0이거나 가격이 0인 경우 패스
            if t.current_price <= 0 or t.trade_volume_1h <= 0:
                continue
            valid_tickers.append(t)
            
        # 실질 거래대금 내림차순 정렬
        sorted_tickers = sorted(valid_tickers, key=lambda x: x.real_trade_value_1h, reverse=True)
        
        # 상위 3개 (Config.MAX_TRACKING_COINS) 추출
        top_n = sorted_tickers[:Config.MAX_TRACKING_COINS]
        return [t.symbol for t in top_n]

    @staticmethod
    def check_dca_condition(position: Position, current_price: float) -> Optional[int]:
        """
        현재 가격이 평단가 대비 하락하여 물타기 조건(-1% 씩)에 도달했는지 확인.
        진입해야 할 DCA 단계를 반환. 진입 조건이 아니면 None 반환.
        """
        if position.is_empty:
            return None
        
        # 평단가 대비 변동율 (예: 100원에서 99원이면 -0.01)
        drop_pct = (current_price - position.avg_price) / position.avg_price
        
        # 현재 스텝
        current_step = position.dca_step
        
        # 최대 6단계
        if current_step >= len(Config.DCA_STEPS):
            return None
            
        # 다음 단계 진입 기준은 매 번 평단가 대비 -1%
        target_drop = Config.DCA_DROP_THRESHOLD # -0.01
        
        if drop_pct <= target_drop:
            # 현재 스텝이 0이었으면 1로 넘어감. index로는 0이 첫번째 추매(5%)를 의미
            next_step = current_step + 1
            return next_step
        
        return None
        
    @staticmethod
    def get_dca_amount_ratio(step: int) -> float:
        """
        스텝 단위(1~6)를 받아 잔여 현금에서 사용할 비율을 반환
        """
        idx = step - 1
        if 0 <= idx < len(Config.DCA_STEPS):
            return Config.DCA_STEPS[idx]
        return 0.0

    @staticmethod
    def check_tp_condition(position: Position, current_price: float) -> Tuple[Optional[str], float]:
        """
        익절 및 본절 탈출 조건을 체크한다.
        반환: (액션 타입, 매도 비율)
        액션 타입: 'tp1' (1차 익절), 'tp2' (2차 익절), 'breakeven' (본절), None (유지)
        """
        if position.is_empty:
            return None, 0.0
            
        pnl_pct = (current_price - position.avg_price) / position.avg_price
        
        # 아직 1차 익절을 안 한 상태
        if not position.tp_1_executed:
            if pnl_pct >= Config.TAKE_PROFIT_1_THRESHOLD:  # +1.5%
                return 'tp1', Config.TAKE_PROFIT_1_RATIO
                
        # 1차 익절을 한 이후 상태
        else:
            if pnl_pct >= Config.TAKE_PROFIT_2_THRESHOLD:  # +2.5%
                return 'tp2', Config.TAKE_PROFIT_2_RATIO
                
            # 본절 방어: 1차 익절 후 가격이 떨어져서 본절 라인 근접 시 남은 전량 매도
            # (수수료 고려 살짝 높게 잡거나 0 선에서 방어. 여기서는 평단가 선 0% 이탈로 체크)
            if pnl_pct <= 0.0:
                return 'breakeven', 1.0 # 남은 물량 100% 매도
                
        return None, 0.0
