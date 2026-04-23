import asyncio
import logging
import time
from config.settings import Config
from infrastructure.exchange.upbit_client import UpbitClient
from domain.strategy.sniper_v2 import SniperStrategyV2
from domain.models.ticker import Ticker

logger = logging.getLogger(__name__)

class MarketMonitor:
    def __init__(self, upbit_client: UpbitClient):
        self.upbit_client = upbit_client
        self.top_3_symbols = []
        self.macro_switch_off = False

    async def check_macro_switch(self):
        """BTC 1시간 변동률 체크"""
        btc_ohlcv = await self.upbit_client.fetch_ohlcv('BTC/KRW', timeframe='1h', limit=2)
        if len(btc_ohlcv) < 2:
            return False
            
        # [timestamp, open, high, low, close, volume]
        prev_candle = btc_ohlcv[0]
        curr_candle = btc_ohlcv[-1]
        
        # open 대비 close 하락률 또는 전 캔들 close 대비 현 close 하락률 등 설정 기준 적용
        # 여기서는 최근 1시간의 시작가(open) 대비 현재가(close)의 변동을 기준
        open_price = curr_candle[1]
        close_price = curr_candle[4]
        
        drop_pct = (close_price - open_price) / open_price
        
        if drop_pct <= Config.MACRO_BTC_DROP_THRESHOLD:
            self.macro_switch_off = True
            logger.warning(f"Macro switch Triggered! BTC Drop: {drop_pct*100:.2f}%")
            return True
            
        self.macro_switch_off = False
        return False

    async def update_top_3(self):
        """24시간 거래대금 상위 15개 선별 -> 최근 1시간 실질 거래대금 Top 3 도출"""
        logger.info("🔍 [마켓 모니터링] 24시간 거래대금 상위 15개 코인 선별 및 실질 거래대금 기준 Top 3 추출을 시작합니다...")
        
        # 1. 모든 KRW 마켓 티커 조회 (24시간 거래대금순 정렬을 위해)
        krw_markets = await self.upbit_client.get_krw_markets()
        if not krw_markets:
            return
            
        tickers = await self.upbit_client.get_tickers(krw_markets)
        if not tickers:
            return
            
        # 24H 거래대금(quoteVolume) 으로 정렬하여 상위 15개 선별
        sorted_by_24h = sorted(tickers.values(), key=lambda t: t.get('quoteVolume', 0), reverse=True)
        top_15_candidates = sorted_by_24h[:15]
        
        ticker_models = []
        
        # 2. 상위 15개에 대해 최근 1시간 거래량(통상 1분봉 60개 합) 계산
        # 업비트 API rate limit 방지를 위해 asyncio.gather 로 동시 요청하되 제한 고려 필요 
        # (ccxt가 enableRateLimit 속성으로 어느정도 내장 제어함)
        ohlcv_results = []
        symbols = []
        
        for t in top_15_candidates:
            symbol = t['symbol']
            symbols.append(symbol)
            
            try:
                ohlcv = await self.upbit_client.fetch_ohlcv(symbol, timeframe='1m', limit=60)
                ohlcv_results.append(ohlcv)
            except Exception as e:
                logger.error(f"{symbol} 데이터 수집 에러: {e}")
                ohlcv_results.append([])
                
            # 봇 숨 고르기 (필수)
            await asyncio.sleep(0.2)
        
        for symbol, ohlcv_list, t_data in zip(symbols, ohlcv_results, top_15_candidates):
            # 1분봉 60개의 volume 컬럼(index 5) 합산
            if not ohlcv_list:
                vol_1h = 0
            else:
                vol_1h = sum([candle[5] for candle in ohlcv_list])
                
            ticker_obj = Ticker(
                symbol=symbol,
                current_price=t_data.get('last', 0),
                trade_value_24h=t_data.get('quoteVolume', 0),
                trade_volume_1h=vol_1h
            )
            ticker_models.append(ticker_obj)
            
        # 3. 전략 모델을 통한 Top 3 도출
        new_top_3 = SniperStrategyV2.select_top_3(ticker_models)
        
        # 변경사항 반환을 위함
        old_top_3 = self.top_3_symbols.copy()
        
        if new_top_3:
            self.top_3_symbols = new_top_3
            logger.info(f"✨ [종목 추출 완료] 실시간 주도주 Top 3 선정: {', '.join(self.top_3_symbols)}")
            
        # 변경되었는지 반환
        return old_top_3, self.top_3_symbols
