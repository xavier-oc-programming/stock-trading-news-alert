import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import os
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

from config import (
    STOCK_NAME, COMPANY_NAME,
    STOCK_ENDPOINT, NEWS_ENDPOINT,
    THRESHOLD_PCT, MAX_SMS_PER_DAY,
    NEWS_PAGE_SIZE, FETCH_TIMEOUT,
    SMS_CHAR_LIMIT, WA_CHAR_LIMIT, QUOTA_FILE,
    CHANNEL, direction_emoji,
)
from stock_client import StockClient
from news_client import NewsClient
from sms_sender import SmsSender


def require_env(name: str) -> str:
    val = os.getenv(name)
    if not val:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return val


def main() -> None:
    # Load credentials
    alpha_key   = require_env("API_KEY_ALPHA")
    news_key    = require_env("NEWS_API_KEY")
    account_sid = require_env("TWILIO_ACCOUNT_SID")
    auth_token  = require_env("TWILIO_AUTH_TOKEN")
    if CHANNEL == "whatsapp":
        from_number = require_env("TWILIO_WHATSAPP_FROM")
        to_number   = require_env("TWILIO_WHATSAPP_TO")
        char_limit  = WA_CHAR_LIMIT
    else:
        from_number = require_env("TWILIO_FROM")
        to_number   = require_env("TWILIO_TO")
        char_limit  = SMS_CHAR_LIMIT

    # Instantiate modules
    stock  = StockClient(alpha_key, STOCK_ENDPOINT, STOCK_NAME, FETCH_TIMEOUT)
    news   = NewsClient(news_key, NEWS_ENDPOINT, FETCH_TIMEOUT)
    sender = SmsSender(account_sid, auth_token, from_number, to_number,
                       QUOTA_FILE, MAX_SMS_PER_DAY)

    # Verify Twilio credentials before hitting stock/news APIs
    sender.verify_auth()

    # Fetch stock change
    perc_diff, abs_diff = stock.get_daily_change()

    if abs(perc_diff) < THRESHOLD_PCT:
        print(f"Move {abs(perc_diff)}% is below threshold {THRESHOLD_PCT}% — no alert sent.")
        return

    print(f"Significant move detected ({perc_diff:+.2f}%) — fetching news…")
    emoji    = direction_emoji(perc_diff)
    articles = news.get_top_articles(COMPANY_NAME, STOCK_NAME, NEWS_PAGE_SIZE)

    if not articles:
        body = sender.build_body(STOCK_NAME, emoji, perc_diff,
                                 "No recent articles", "", char_limit)
        print(f"\n--- Message Preview ---\n{body}")
        sender.send(body)
        return

    for article in articles:
        title = article.get("title", "(No Title)")
        brief = article.get("description") or ""
        body  = sender.build_body(STOCK_NAME, emoji, perc_diff,
                                  title, brief, char_limit)
        print(f"\nTitle: {title}\nBrief: {brief}")
        print(f"\n--- Message Preview ---\n{body}")
        sid = sender.send(body)
        if sid is None:
            print("Quota exhausted — stopping early.")
            break


if __name__ == "__main__":
    main()
