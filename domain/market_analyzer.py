import pandas as pd
import pandas_ta_classic as ta  # 기술적 지표 계산 라이브러리
import pyupbit
import requests

class MarketAnalyzer:
    def __init__(self):
        self.btc_ticker = "KRW-BTC"

    def get_indicators(self, ticker: str) -> pd.DataFrame:
        """1분봉 데이터를 가져와서 V5.0 4대 지표를 계산합니다."""
        # 1. 데이터 로드 (최근 200개의 1분봉)
        df = pyupbit.get_ohlcv(ticker, interval="minute1", count=200)
        
        if df is None or df.empty:
            return pd.DataFrame()

        # 2. RSI (14) 계산
        df['rsi'] = ta.rsi(df['close'], length=14)

        # 3. EMA (20) 계산 - 단기 추세 생명선
        df['ema_20'] = ta.ema(df['close'], length=20)

        # 4. 볼린저 밴드 (20, 2) 계산
        bb = ta.bbands(df['close'], length=20, std=2)
        df['bb_upper'] = bb['BBU_20_2.0']
        df['bb_lower'] = bb['BBL_20_2.0']

        # 5. MACD (12, 26, 9) 계산
        macd = ta.macd(df['close'], fast=12, slow=26, signal=9)
        df['macd'] = macd['MACD_12_26_9']
        df['macd_signal'] = macd['MACDs_12_26_9']

        return df

    def is_btc_crashing(self) -> bool:
        """[매크로 생존 스위치] 최근 1시간 BTC 변동률 -1.5% 확인"""
        df_btc = pyupbit.get_ohlcv(self.btc_ticker, interval="minute60", count=2)
        if df_btc is None or len(df_btc) < 2:
            return False
            
        prev_close = df_btc['close'].iloc[-2]
        curr_price = pyupbit.get_current_price(self.btc_ticker)
        
        change_pct = ((curr_price - prev_close) / prev_close) * 100
        return change_pct <= -1.5

    def get_best_target_coins(self) -> list:
        """
        [매 5분 스캔용] 
        1차 필터: 24시간 거래대금 상위 10개 추출
        2차 필터: 10개 중 최근 4시간 고점 대비 저점 변동폭이 가장 큰 3개 종목 선택
        """
        import time
        tickers = pyupbit.get_tickers(fiat="KRW")
        
        # 비트코인 및 변동성 없는 스테이블 코인 제외
        exclude_list = ["KRW-BTC", "KRW-USDT", "KRW-USDC", "KRW-BUSD"]
        target_tickers = [t for t in tickers if t not in exclude_list]

        # 업비트 Ticker API를 통해 모든 타겟 코인의 거래대금 정보 한 번에 조회
        url = "https://api.upbit.com/v1/ticker"
        headers = {"accept": "application/json"}
        markets_str = ",".join(target_tickers)
        
        try:
            response = requests.get(f"{url}?markets={markets_str}", headers=headers)
            if response.status_code == 200:
                data = response.json()
                # acc_trade_price_24h 기준으로 내림차순 정렬 후 상위 10개
                sorted_data = sorted(data, key=lambda x: x['acc_trade_price_24h'], reverse=True)
                top_10_coins = [item['market'] for item in sorted_data][:10]
            else:
                top_10_coins = target_tickers[:10]
        except Exception:
            top_10_coins = target_tickers[:10]

        volatility_list = []

        # 2차 필터: 10개 코인 대상 4시간 변동폭 분석
        for coin in top_10_coins:
            # 60분봉 4개 (최근 4시간)
            df = pyupbit.get_ohlcv(coin, interval="minute60", count=4)
            if df is not None and not df.empty:
                highest = df['high'].max()
                lowest = df['low'].min()
                if lowest > 0:
                    volatility = ((highest - lowest) / lowest) * 100
                    volatility_list.append({"coin": coin, "volatility": volatility})
            time.sleep(0.1) # API Rate Limit 방지용 휴식

        # 변동폭 기준으로 내림차순 정렬 후 상위 3개 추출
        sorted_by_vol = sorted(volatility_list, key=lambda x: x['volatility'], reverse=True)
        best_3_coins = [item['coin'] for item in sorted_by_vol][:3]
        
        if best_3_coins:
            return best_3_coins
        return top_10_coins[:3] # 데이터 조회에 실패한 경우 거래대금 최상위 코인 3개 반환