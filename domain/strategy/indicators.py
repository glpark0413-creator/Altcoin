import pandas as pd
import talib
from config.settings import Config

def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    1분봉 DataFrame(OHLCV)을 받아 RSI, EMA, 거래량 이동평균 등을 계산
    df 컬럼은 ['timestamp', 'open', 'high', 'low', 'close', 'volume']를 가정함
    """
    if len(df) < max(Config.RSI_PERIOD, Config.EMA_PERIOD, Config.VOLUME_MA_PERIOD) + 1:
        return df
    
    # RSI 계산
    df['rsi'] = talib.RSI(df['close'].values, timeperiod=Config.RSI_PERIOD)
    
    # 지수이동평균(EMA) 계산
    df['ema_20'] = talib.EMA(df['close'].values, timeperiod=Config.EMA_PERIOD)
    
    # 직전 거래량 평균 계산
    # 보통 현재 캔들은 형성 중이므로 (shift) 이전 N개의 평균을 사용함
    df['vol_ma'] = df['volume'].shift(1).rolling(window=Config.VOLUME_MA_PERIOD).mean()
    
    return df

def check_entry_conditions(df: pd.DataFrame) -> bool:
    """
    최종 매매 종목 낙점을 위한 3가지 동시 만족 조건 확인:
    조건 1: 1분봉 RSI 45 이하에서 상승 반전
    조건 2: 거래량이 직전 10개 캔들 평균의 200% 이상 폭발
    조건 3: 현재 가격이 EMA 20 상단에 위치
    """
    if len(df) < 3:
        return False
    
    # df의 가장 마지막 row는 현재 (형성 중인) 캔들
    current_idx = df.index[-1]
    prev_idx = df.index[-2]
    
    current_rsi = df.at[current_idx, 'rsi']
    prev_rsi = df.at[prev_idx, 'rsi']
    
    current_close = df.at[current_idx, 'close']
    current_ema = df.at[current_idx, 'ema_20']
    
    current_vol = df.at[current_idx, 'volume']
    prev_vol_ma = df.at[current_idx, 'vol_ma']
    
    if pd.isna(current_rsi) or pd.isna(prev_rsi) or pd.isna(current_ema) or pd.isna(prev_vol_ma):
        return False

    # 조건 1: RSI 45 이하에서 "위로 꺾여 올라감" (이전 RSI <= 45 이고 현재 RSI > 이전 RSI)
    # 조금 더 확실한 반전을 보려면, 현재 RSI가 45를 막 상향 돌파하거나, 45 밑에서 바닥을 찍고 올라오는 모양
    cond_1_rsi = (prev_rsi <= Config.RSI_OVERSOLD_THRESHOLD) and (current_rsi > prev_rsi)
    
    # 조건 2: 거래량 폭발
    cond_2_vol = current_vol >= (prev_vol_ma * Config.VOLUME_SPIKE_RATIO)
    
    # 조건 3: 20 EMA 상단
    cond_3_ema = current_close > current_ema
    
    return cond_1_rsi and cond_2_vol and cond_3_ema
