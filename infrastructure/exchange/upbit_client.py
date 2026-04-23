import ccxt.async_support as ccxt
import time
from config.settings import Config
import logging

logger = logging.getLogger(__name__)

class UpbitClient:
    def __init__(self):
        self.exchange = ccxt.upbit({
            'apiKey': Config.UPBIT_ACCESS_KEY,
            'secret': Config.UPBIT_SECRET_KEY,
            'enableRateLimit': True,
        })

    async def get_balance(self, currency="KRW"):
        try:
            balance = await self.exchange.fetch_balance()
            if currency in balance:
                return balance[currency]['free']
            return 0.0
        except Exception as e:
            logger.error(f"Failed to fetch balance: {e}")
            return 0.0

    async def get_current_price(self, symbol: str):
        try:
            ticker = await self.exchange.fetch_ticker(symbol)
            return ticker['last']
        except Exception as e:
            logger.error(f"Failed to fetch ticker for {symbol}: {e}")
            return None

    async def fetch_ohlcv(self, symbol: str, timeframe='1m', limit=50):
        try:
            ohlcv = await self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            return ohlcv
        except Exception as e:
            logger.error(f"Failed to fetch OHLCV for {symbol}: {e}")
            return []

    async def get_tickers(self, symbols: list):
        try:
            tickers = await self.exchange.fetch_tickers(symbols)
            return tickers
        except Exception as e:
            logger.error(f"Failed to fetch tickers: {e}")
            return {}
            
    async def get_krw_markets(self):
        try:
            markets = await self.exchange.load_markets()
            krw_markets = [m['symbol'] for m in markets.values() if m['symbol'].endswith('/KRW')]
            return krw_markets
        except Exception as e:
            logger.error(f"Failed to load markets: {e}")
            return []

    async def create_market_buy_order(self, symbol: str, cost: float):
        try:
            # 업비트는 시장가 매수(지정가 대신 cost 옵션)
            order = await self.exchange.create_order(symbol, 'market', 'buy', amount=None, price=None, params={'cost': cost})
            return order
        except Exception as e:
            logger.error(f"Failed to create buy order for {symbol}: {e}")
            return None

    async def create_market_sell_order(self, symbol: str, amount: float):
        try:
            order = await self.exchange.create_order(symbol, 'market', 'sell', amount=amount, price=None)
            return order
        except Exception as e:
            logger.error(f"Failed to create sell order for {symbol}: {e}")
            return None

    async def close(self):
        await self.exchange.close()
