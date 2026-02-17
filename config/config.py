import os
from dotenv import load_dotenv

load_dotenv()

# Trading Settings
SYMBOLS = ["EURUSD=X", "GBPUSD=X", "NZDUSD=X", "USDJPY=X", "AUDUSD=X", "GBPJPY=X", "GC=F", "CL=F", "BTC-USD"] # Alpha Core Plus (V16.0)
DXY_SYMBOL = "DX-Y.NYB"
TNX_SYMBOL = "^TNX"
NARRATIVE_TF = "1h"
INSTITUTIONAL_TF = "4h"
STRUCTURE_TF = "15m"
ENTRY_TF = "5m" # Switched to 5m for better intraday consistency
SCALP_TF = "1m"

# CRT settings (OBSOLETE - REMOVED)

# INDICATORS
EMA_TREND = 100 # Optimized from 200
EMA_FAST = 20
EMA_SLOW = 50
RSI_PERIOD = 14
ATR_PERIOD = 14
ATR_AVG_PERIOD = 50
ATR_MULTIPLIER = 1.8 # Optimized from 1.5 for better manipulation clearance
ADR_PERIOD = 20 # Standard 20-day Average Daily Range
ADR_THRESHOLD_PERCENT = 0.95 # Rebalanced from 0.90 for V5.0
POC_LOOKBACK = 200 # Bars for Volume Profile POC calculation
# LIQUIDITY (OBSOLETE - REMOVED)

# ENTRY & EXIT TUNING (V13.0)
BE_TRIGGER_ATR = 1.8 # Widened from 1.5 (Alpha Remediation v19.3)
PARTIAL_TP_ATR = 0.75 # Widened from 0.5
PARTIAL_SIZE = 0.5 # Close 50% at partial TP

# DISPLACEMENT (OBSOLETE - REMOVED)

# RSI THRESHOLDS
RSI_BUY_LOW = 25
RSI_BUY_HIGH = 40
RSI_SELL_LOW = 60
RSI_SELL_HIGH = 75

# TELEGRAM
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# SESSION TIMES (UTC)
# London: 08:00 - 16:00
# NY: 13:00 - 21:00
LONDON_OPEN = 8
LONDON_CLOSE = 16
NY_OPEN = 13
NY_CLOSE = 21
ASIAN_RANGE_MIN_PIPS = 15 # Minimum range for sweep validity (Reserved for filtering)

# NEWS FILTER
NEWS_WASH_ZONE = 30 # Minutes before/after high-impact news
NEWS_IMPACT_LEVELS = ["High", "Medium"] # Impact levels to track

# MULTI-CLIENT SETTINGS (V11.0)
MULTI_CLIENT_MODE = os.getenv("MULTI_CLIENT_MODE", "true").lower() == "true"

# SCORING (V15.0 Golden Threshold)
MIN_CONFIDENCE_SCORE = 8.0
GOLD_CONFIDENCE_THRESHOLD = 5.5  # V15.5 Extreme Volume (Alpha Core)

# RISK MANAGEMENT V4.0 (Scalable Account Sizing)
ACCOUNT_BALANCE = float(os.getenv("ACCOUNT_BALANCE", "200.0"))  # Configurable via env (V10.1: Increased for Gold trading)
RISK_PER_TRADE_PERCENT = float(os.getenv("RISK_PER_TRADE_PERCENT", "2.0"))  # Standard 2% risk
MAX_CONCURRENT_TRADES = int(os.getenv("MAX_CONCURRENT_TRADES", "4"))  # Increased from 2
MAX_CURRENCY_EXPOSURE = int(os.getenv("MAX_CURRENCY_EXPOSURE", "2"))  # Increased from 1
MIN_LOT_SIZE = 0.01
USE_KELLY_SIZING = os.getenv("USE_KELLY_SIZING", "false").lower() == "true"  # Dynamic sizing
MIN_QUALITY_SCORE = float(os.getenv("MIN_QUALITY_SCORE", "5.0"))  # Signal quality threshold
MIN_QUALITY_SCORE_INTRADAY = float(os.getenv("MIN_QUALITY_SCORE_INTRADAY", "5.0"))  # Same as global; 5.5 was tested, hurt PF

# EXECUTION REALISM (V18.1 Audit)
SPREAD_PIPS = 0.8 # Average Retail Spread
SLIPPAGE_PIPS = 0.2 # Expected Scalp Slippage

# DATABASE PATHS (V22.7.5)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_CLIENTS = os.path.join(BASE_DIR, "database/clients.db")
DB_SIGNALS = os.path.join(BASE_DIR, "database/signals.db")
