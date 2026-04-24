import pandas as pd

class SniperStrategy:
    """V5.0 정밀 진입 및 익절/방어 로직 구현"""
    
    @staticmethod
    def is_sniper_entry(df: pd.DataFrame) -> bool:
        """3대 기술적 지표 동시 충족 여부 확인 (최근 1분봉 기준)"""
        current = df.iloc[-1]
        previous = df.iloc[-2]

        # 1. RSI(14) 45 이하에서 상승 반전
        rsi_condition = (previous['rsi'] <= 45) and (current['rsi'] > previous['rsi'])
        
        # 2. 가격이 1분봉 EMA 20선 상단 위치
        ema_condition = current['close'] > current['ema_20']
        
        # 3. 볼린저 밴드 상단선 미터치
        bb_condition = current['high'] < current['bb_upper']
        
        # (기존 4번째 MACD 조건은 유저 요청으로 제외됨)

        return rsi_condition and ema_condition and bb_condition

    @staticmethod
    def check_dca_level(current_drop_pct: float) -> int:
        """현재 하락률에 따른 물타기(DCA) 단계 반환"""
        if current_drop_pct <= -15.0: return 5 # 34% 투입
        if current_drop_pct <= -10.0: return 4 # 21% 투입
        if current_drop_pct <= -6.0:  return 3 # 13% 투입
        if current_drop_pct <= -4.0:  return 2 # 8% 투입
        if current_drop_pct <= -2.0:  return 1 # 4% 투입
        return 0

    @staticmethod
    def check_exit_condition(current_profit_pct: float) -> str:
        """수익률에 따른 익절 조건 반환"""
        if current_profit_pct >= 2.5: return "FULL_EXIT"  # 전량 매도
        if current_profit_pct >= 1.5: return "HALF_EXIT"  # 50% 매도
        return "HOLD"