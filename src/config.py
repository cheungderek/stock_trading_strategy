"""
config.py - settings for the daily Donchian 20/10 breakout scanner.

Edit these to match your watchlist and CallMeBot account.
"""
from __future__ import annotations
import os

# ------------------------------------------------------------------ #
# Watchlist - 38 tickers (US + ADRs)
# ------------------------------------------------------------------ #
WATCHLIST = [
    "T", "TEM", "TSLA", "TSM", "TXN", "UBER", "UNH", "VZ", "WMT", "XIACF",
    "NOK", "MA", "META", "MRVL", "MSFT", "MU", "NVDA", "PDD", "PLTR", "RBLX",
    "SPCX", "SKHY", "INTC", "GOOGL", "GLD", "HSBC", "JD", "JPM", "KO", "CIEN",
    "COST", "BRK-B", "AMD", "AMZN", "ARM", "ASML", "BA", "BABA",
]

# ------------------------------------------------------------------ #
# Strategy parameters (best of 6 - S5 Donchian 20/10 breakout)
# ------------------------------------------------------------------ #
ENTRY_WINDOW = 20      # buy new 20-day high
EXIT_WINDOW  = 10      # exit on new 10-day low
RISK_PER_TRADE = 0.01  # 1% of equity risked per trade (for sizing)
ATR_WINDOW = 20        # for ATR-based position sizing
MAX_POSITIONS = 12     # cap concurrent long positions

# ------------------------------------------------------------------ #
# CallMeBot - Facebook Messenger alerts
# ------------------------------------------------------------------ #
# Get your API key by messaging the CallMeBot FB Messenger bot with:
#   I allow callmebot to send me messages
# The bot will reply with your API key.
CALLMEBOT_API_KEY = os.environ.get("CALLMEBOT_API_KEY", "")

# CallMeBot endpoint for Facebook Messenger
# See https://www.callmebot.com/blog/free-api-facebook-messenger/
CALLMEBOT_URL = "https://api.callmebot.com/facebook/send.php"

# Optional: per-user phone (some CallMeBot API setups need it; FB Messenger version
# usually only requires the API key tied to your FB account).
PHONE = ""  # leave blank if CallMeBot only needs the API key

# ------------------------------------------------------------------ #
# Scan behavior
# ------------------------------------------------------------------ #
LOOKBACK_BARS = 60      # days of history we download each scan (~3 months)
DATA_REFRESH_HOURS = 12
RESULTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results")
STATE_FILE = os.path.join(RESULTS_DIR, "scan_state.json")

# Set to True to send a test alert even if no signals fire
ALWAYS_SEND_TEST_ALERT = False

# Heartbeat: send a (short) FB Messenger message even on no-signal days so you
# know the scanner is alive. Set to False for silent no-signal runs.
SEND_HEARTBEAT = True
# ------------------------------------------------------------------ #
# Logging
# ------------------------------------------------------------------ #
LOG_FILE = os.path.join(RESULTS_DIR, "scanner.log")
