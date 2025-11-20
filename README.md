# XAU SMC Bot

An automated trading bot for XAUUSD (Gold) using Smart Money Concepts (SMC) strategies, integrated with MetaAPI.

## Features

- **Liquidity Sweep Detection**: Identifies liquidity sweeps on daily highs/lows
- **Fair Value Gap (FVG) Detection**: Finds bullish and bearish FVGs
- **Order Block Detection**: Identifies potential order blocks
- **RSI Divergence**: Detects bullish and bearish divergences
- **News Filter**: Avoids trading during high-impact news events
- **Risk Management**: Configurable risk percentage and position sizing
- **Telegram Alerts**: Optional Telegram notifications for trades

## Setup

1. Install dependencies:
```bash
pip install -r xau_smc_bot/requirements.txt
```

2. Configure your settings in `xau_smc_bot/config.py`:
   - Add your MetaAPI token and account ID
   - Adjust risk parameters, spread limits, and other settings
   - Optionally configure Telegram for alerts

3. Run the bot:
```bash
python xau_smc_bot/main.py
```

## Configuration

Edit `xau_smc_bot/config.py` to customize:
- `METAAPI_TOKEN`: Your MetaAPI token
- `ACCOUNT_ID`: Your MetaAPI account ID
- `RISK_PERCENT`: Risk per trade (default: 1.0%)
- `MAX_TRADES_PER_DAY`: Maximum trades per day
- `RR_RATIO`: Risk-reward ratio (default: 1:3)
- `USE_NEWS_FILTER`: Enable/disable news filtering

## Strategy

The bot looks for:
1. **Liquidity sweeps** on daily highs/lows
2. **Fair Value Gaps** (FVGs) for entry zones
3. **Order blocks** for additional confirmation
4. **RSI divergences** for momentum confirmation

When all conditions align, it places trades with a 1:3 risk-reward ratio.

## Disclaimer

This bot is for educational purposes. Trading involves risk. Always test thoroughly before using real money.

