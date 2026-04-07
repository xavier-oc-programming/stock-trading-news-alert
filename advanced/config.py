from pathlib import Path

# Paths
DATA_DIR   = Path(__file__).parent / "data"
QUOTA_FILE = DATA_DIR / "sms_quota.json"

# Stock
STOCK_NAME    = "TSLA"
COMPANY_NAME  = "Tesla Inc"

# API / URLs
STOCK_ENDPOINT = "https://www.alphavantage.co/query"
NEWS_ENDPOINT  = "https://newsapi.org/v2/everything"

# Thresholds
THRESHOLD_PCT  = 1.0  # minimum % move (absolute) to trigger news alert
MAX_SMS_PER_DAY = 8   # daily cap; Twilio trial accounts are capped at ~9

# Fetch
NEWS_PAGE_SIZE = 3    # number of articles to retrieve and send
FETCH_TIMEOUT  = 20   # seconds before HTTP request is aborted

# Notification channel — "sms" or "whatsapp"
CHANNEL = "whatsapp"

# Output / formatting
SMS_CHAR_LIMIT = 65    # UCS-2 safe length per SMS segment
WA_CHAR_LIMIT  = 300   # comfortable WhatsApp message length


def direction_emoji(pct: float) -> str:
    """Return 🔺 for gains, 🔻 for losses."""
    return "🔺" if pct > 0 else "🔻"
