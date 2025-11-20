import asyncio
import time
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from metaapi_cloud_sdk import MetaApi
from config import *
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('XAU_SMC_BOT')

# News filter (optional)
if USE_NEWS_FILTER:
    from news_filter import is_high_impact_news_soon

api = MetaApi(token=METAAPI_TOKEN)
account = None
terminal = None

daily_low = daily_high = None
last_trade_date = None
trades_today = 0

async def init():
    global account, terminal
    account = await api.metatrader_account_api.get_account(ACCOUNT_ID)
    await account.deploy()
    await account.wait_connected()
    terminal = account.get_streaming_terminal()
    logger.info("Connected to MetaApi account")

async def get_candles(symbol, timeframe, count=500):
    bars = await terminal.get_candles(symbol, timeframe, count)
    df = pd.DataFrame(bars)
    df['time'] = pd.to_datetime(df['time'])
    return df

def detect_liquidity_sweep(df_daily, df_m5):
    global daily_low, daily_high
    today = datetime.utcnow().date()
    if daily_low is None or datetime.utcnow().hour < 1:  # reset daily
        daily_low = df_daily['low'].min()
        daily_high = df_daily['high'].max()

    sweep_low = df_m5['low'].iloc[-2] < daily_low and df_m5['close'].iloc[-2] > daily_low
    sweep_high = df_m5['high'].iloc[-2] > daily_high and df_m5['close'].iloc[-2] < daily_high
    return sweep_low, sweep_high

def detect_fvg(df):
    fvg_up = (df['low'].shift(2) > df['high']) 
    fvg_down = (df['high'].shift(2) < df['low'])

    bullish_fvg = None
    bearish_fvg = None

    if fvg_up.any():
        idx = fvg_up[fvg_up].index[-1]
        # FVG: gap between candle 2 periods ago and current
        if idx >= 2:
            bullish_fvg = (df.loc[idx, 'low'], df.loc[idx-2, 'high'])  # bottom, top
    if fvg_down.any():
        idx = fvg_down[fvg_down].index[-1]
        # FVG: gap between candle 2 periods ago and current
        if idx >= 2:
            bearish_fvg = (df.loc[idx-2, 'low'], df.loc[idx, 'high'])

    return bullish_fvg, bearish_fvg

def detect_order_block(df, direction):
    # Simple OB: last opposite candle before impulsive move
    if direction == "buy":
        return df['low'].rolling(20).min().iloc[-1]
    else:
        return df['high'].rolling(20).max().iloc[-1]

def rsi_divergence(df, length=14):
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(length).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(length).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))

    price_lower_low = df['low'].iloc[-1] < df['low'].iloc[-10]
    rsi_higher_low = rsi.iloc[-1] > rsi.iloc[-10]
    bullish_div = price_lower_low and rsi_higher_low

    price_higher_high = df['high'].iloc[-1] > df['high'].iloc[-10]
    rsi_lower_high = rsi.iloc[-1] < rsi.iloc[-10]
    bearish_div = price_higher_high and rsi_lower_high

    return bullish_div, bearish_div

async def main_loop():
    global trades_today, last_trade_date

    while True:
        try:
            now = datetime.utcnow()
            if last_trade_date != now.date():
                trades_today = 0
                last_trade_date = now.date()

            if trades_today >= MAX_TRADES_PER_DAY:
                await asyncio.sleep(300)
                continue

            if USE_NEWS_FILTER and is_high_impact_news_soon():
                logger.info("High impact news soon - skipping")
                await asyncio.sleep(60)
                continue

            df_daily = await get_candles(SYMBOL, '1d', 10)
            df = await get_candles(SYMBOL, '5m', 200)
            if len(df) < 100:
                await asyncio.sleep(10)
                continue

            quotes = await terminal.get_quotes([SYMBOL])
            spread = quotes[0]['ask'] - quotes[0]['bid']
            if spread > MAX_SPREAD:
                await asyncio.sleep(10)
                continue

            sweep_low, sweep_high = detect_liquidity_sweep(df_daily, df)

            bullish_fvg, bearish_fvg = detect_fvg(df)
            bull_div, bear_div = rsi_divergence(df)

            # Get current price - use ask for buy, bid for sell
            current_ask = quotes[0]['ask']
            current_bid = quotes[0]['bid']

            # === BULLISH SETUP ===
            if (sweep_low and bullish_fvg and 
                bullish_fvg[0] <= current_ask <= bullish_fvg[1] and
                current_ask >= detect_order_block(df, "buy") and
                bull_div and trades_today < MAX_TRADES_PER_DAY):

                sl = daily_low - SL_BUFFER_PIPS * 0.1
                tp = current_ask + (current_ask - sl) * RR_RATIO
                await place_order("buy", current_ask, sl, tp)
                trades_today += 1

            # === BEARISH SETUP ===
            if (sweep_high and bearish_fvg and 
                bearish_fvg[0] <= current_bid <= bearish_fvg[1] and
                current_bid <= detect_order_block(df, "sell") and
                bear_div and trades_today < MAX_TRADES_PER_DAY):

                sl = daily_high + SL_BUFFER_PIPS * 0.1
                tp = current_bid - (sl - current_bid) * RR_RATIO
                await place_order("sell", current_bid, sl, tp)
                trades_today += 1

            await asyncio.sleep(15)

        except Exception as e:
            logger.error(f"Error: {e}")
            await asyncio.sleep(30)

async def place_order(side, price, sl, tp):
    account_data = await account.get()
    balance = account_data.get('balance', 10000)  # fallback to 10000 if balance not available
    risk_amount = balance * (RISK_PERCENT / 100)
    pip_value = 1 if SYMBOL.endswith("USD") else 0.1
    distance = abs(price - sl)
    lots = risk_amount / (distance * 100)  # rough calc for XAU

    trade = {
        'symbol': SYMBOL,
        'type': 'ORDER_TYPE_BUY' if side == 'buy' else 'ORDER_TYPE_SELL',
        'volume': round(lots, 2),
        'stopLoss': round(sl, 3 if 'JPY' in SYMBOL else 5),
        'takeProfit': round(tp, 3 if 'JPY' in SYMBOL else 5),
    }
    result = await terminal.create_market_order(trade)
    logger.info(f"Trade placed: {side.upper()} SL:{sl} TP:{tp}")

    # Optional Telegram alert
    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        try:
            from telegram import Bot
            bot = Bot(token=TELEGRAM_TOKEN)
            msg = f"🚀 {side.upper()} XAUUSD\nEntry: {price}\nSL: {sl}\nTP: {tp}\nRR: 1:3"
            await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg)
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")

async def main():
    await init()
    await main_loop()

if __name__ == "__main__":
    asyncio.run(main())