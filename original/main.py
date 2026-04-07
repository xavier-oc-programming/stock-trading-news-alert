# --------- Imports ---------
import os
import json
from pathlib import Path
from datetime import date
from dotenv import load_dotenv
import requests
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

# --------- Load .env robustly (from repo root) ---------
dotenv_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=dotenv_path)

# --------- Constants ---------
STOCK_NAME = "TSLA"
COMPANY_NAME = "Tesla Inc"
STOCK_ENDPOINT = "https://www.alphavantage.co/query"
NEWS_ENDPOINT  = "https://newsapi.org/v2/everything"

# --------- Required Environment Variables ---------
def require_env(varname: str) -> str:
    val = os.getenv(varname)
    if not val:
        raise RuntimeError(f"Missing required environment variable: {varname}")
    return val

API_KEY_ALPHA = require_env("API_KEY_ALPHA")
NEWS_API_KEY  = require_env("NEWS_API_KEY")
ACCOUNT_SID   = require_env("TWILIO_ACCOUNT_SID")
AUTH_TOKEN    = require_env("TWILIO_AUTH_TOKEN")
FROM_NUMBER   = require_env("TWILIO_FROM")
TO_NUMBER     = require_env("TWILIO_TO")

# --------- Twilio client (fast auth sanity) ---------
client = Client(ACCOUNT_SID, AUTH_TOKEN)
client.api.accounts(ACCOUNT_SID).fetch()
print("Twilio auth OK. From:", FROM_NUMBER, "To:", TO_NUMBER)

# --------- Local quota guard ---------
QUOTA_FILE = Path(__file__).parent / ".sms_quota.json"  # fixed: was Path(".sms_quota.json")
MAX_PER_DAY = 8  # stay below Twilio trial daily cap (you saw 9)

def _load_quota():
    if QUOTA_FILE.exists():
        try:
            return json.loads(QUOTA_FILE.read_text() or "{}")
        except Exception:
            return {}
    return {}

def can_send_today() -> bool:
    today = date.today().isoformat()
    data = _load_quota()
    if data.get("date") != today:
        data = {"date": today, "count": 0}
        QUOTA_FILE.write_text(json.dumps(data))
    return data["count"] < MAX_PER_DAY

def record_send():
    data = _load_quota()
    today = date.today().isoformat()
    if data.get("date") != today:
        data = {"date": today, "count": 0}
    data["count"] = data.get("count", 0) + 1
    data["date"] = today
    QUOTA_FILE.write_text(json.dumps(data))

# --------- Helpers for SMS body ---------
def sanitize(s: str) -> str:
    return (s or "").replace("\n", " ").strip()

def clamp_ucs2(text: str, limit: int = 65) -> str:
    """Ensure text fits in one UCS-2 SMS (~70 chars)."""
    t = sanitize(text)
    return (t[:max(0, limit - 1)] + "…") if len(t) > limit else t

def build_title_brief_sms(stock: str, direction_emoji: str, perc: float,
                          title: str, brief: str, limit: int = 65) -> str:
    header = f"{stock}: {direction_emoji}{abs(perc)}% | "
    combo = f"{sanitize(title)} - {sanitize(brief) or '(No description)'}"
    return clamp_ucs2(header + combo, limit=limit)

# --------- Stock API Request ---------
params_alpha = {
    "function": "TIME_SERIES_DAILY",
    "symbol": STOCK_NAME,
    "outputsize": "compact",
    "datatype": "json",
    "apikey": API_KEY_ALPHA,
}
response = requests.get(STOCK_ENDPOINT, params=params_alpha, timeout=20)
response.raise_for_status()
data = response.json()

ts_key = "Time Series (Daily)"
if ts_key not in data:
    msg = data.get("Note") or data.get("Information") or "Unexpected Alpha Vantage response."
    raise RuntimeError(f"Alpha Vantage error: {msg}")

time_series = data[ts_key]
sorted_dates = sorted(time_series.keys(), reverse=True)
if len(sorted_dates) < 2:
    raise RuntimeError("Not enough trading days in response.")

yesterday = sorted_dates[0]
day_before_yesterday = sorted_dates[1]
yesterday_close = float(time_series[yesterday]["4. close"])
day_before_close = float(time_series[day_before_yesterday]["4. close"])

pos_diff = round(abs(yesterday_close - day_before_close), 2)
raw_perc = (yesterday_close - day_before_close) / day_before_close * 100
perc_diff = round(raw_perc, 2)

print(f"Yesterday's Close ({yesterday}): ${yesterday_close}")
print(f"Day Before Yesterday's Close ({day_before_yesterday}): ${day_before_close}")
print(f"Absolute Difference: ${pos_diff}")
print(f"Percentage Difference: {perc_diff}%")

# --------- Threshold ---------
THRESHOLD_PCT = 0
if abs(perc_diff) >= THRESHOLD_PCT:
    print("Significant move detected; fetching news...")

    news_params = {
        "apiKey": NEWS_API_KEY,
        "q": f'"{COMPANY_NAME}" OR {STOCK_NAME}',
        "searchIn": "title,description",
        "sortBy": "publishedAt",
        "language": "en",
        "pageSize": 3,
    }
    news_response = requests.get(NEWS_ENDPOINT, params=news_params, timeout=20)
    news_response.raise_for_status()
    articles = (news_response.json().get("articles") or [])[:3]

    direction = "🔺" if raw_perc > 0 else "🔻"

    if not articles:
        body = build_title_brief_sms(STOCK_NAME, direction, perc_diff, "No recent articles", "", limit=65)
        print("\n--- SMS Preview ---\n" + body)
        if can_send_today():
            try:
                sms = client.messages.create(body=body, from_=FROM_NUMBER, to=TO_NUMBER)
                record_send()
                print(f"Message sent (SID: {sms.sid})")
            except TwilioRestException as e:
                print(f"Twilio error {getattr(e,'code','?')}: {e.msg}")
        else:
            print("Local quota reached; skipping send.")
    else:
        print("\n--- Article Details (Full printout) ---")
        for article in articles:
            full_title = article.get("title", "(No Title)")
            full_brief = article.get("description") or "(No description available)"
            print(f"\nTitle: {full_title}\nBrief: {full_brief}")

            msg = build_title_brief_sms(
                stock=STOCK_NAME,
                direction_emoji=direction,
                perc=perc_diff,
                title=full_title,
                brief=full_brief,
                limit=65
            )

            print("\n--- SMS Preview ---\n" + msg)
            if can_send_today():
                try:
                    sms = client.messages.create(body=msg, from_=FROM_NUMBER, to=TO_NUMBER)
                    record_send()
                    print(f"Message sent (SID: {sms.sid})")
                except TwilioRestException as e:
                    print(f"Twilio error {getattr(e,'code','?')}: {e.msg}")
            else:
                print("Local quota reached; skipping send.")
else:
    print(f"Move {abs(perc_diff)}% does not exceed threshold of {THRESHOLD_PCT}% — no news sent.")
