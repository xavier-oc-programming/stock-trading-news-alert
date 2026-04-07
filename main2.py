# --------- Imports ---------
import os
from pathlib import Path
from dotenv import load_dotenv
import requests
from twilio.rest import Client
from time import sleep

# --------- Load .env robustly (from script's directory) ---------
dotenv_path = Path(__file__).with_name(".env")
load_dotenv(dotenv_path=dotenv_path)

# --------- Constants ---------
STOCK_NAME = "TSLA"
COMPANY_NAME = "Tesla Inc"

# --------- Required Environment Variables ---------
def require_env(varname: str) -> str:
    val = os.getenv(varname)
    if not val:
        raise RuntimeError(f"Missing required environment variable: {varname}")
    return val

API_KEY_ALPHA = require_env("API_KEY_ALPHA")
NEWS_API_KEY  = require_env("NEWS_API_KEY")
ACCOUNT_SID   = require_env("TWILIO_ACCOUNT_SID")   # validate Twilio too
AUTH_TOKEN    = require_env("TWILIO_AUTH_TOKEN")
FROM_NUMBER   = require_env("TWILIO_FROM")
TO_NUMBER     = require_env("TWILIO_TO")

STOCK_ENDPOINT = "https://www.alphavantage.co/query"
NEWS_ENDPOINT  = "https://newsapi.org/v2/everything"

# --------- Optional: fast Twilio auth smoke test ---------
client = Client(ACCOUNT_SID, AUTH_TOKEN)
client.api.accounts(ACCOUNT_SID).fetch()
print("Twilio auth OK. From:", FROM_NUMBER, "To:", TO_NUMBER)

# --------- Stock API Request ---------
params_alpha = {
    "function": "TIME_SERIES_DAILY",
    "symbol": STOCK_NAME,
    "outputsize": "compact",
    "datatype": "json",
    "apikey": API_KEY_ALPHA
}

response = requests.get(STOCK_ENDPOINT, params=params_alpha, timeout=20)
response.raise_for_status()
data = response.json()

# Alpha Vantage rate-limit check
ts_key = "Time Series (Daily)"
if ts_key not in data:
    msg = data.get("Note") or data.get("Information") or "Unexpected Alpha Vantage response."
    raise RuntimeError(f"Alpha Vantage error: {msg}")

time_series = data[ts_key]

# --------- Get the 2 Most Recent Trading Days ---------
sorted_dates = sorted(time_series.keys(), reverse=True)
if len(sorted_dates) < 2:
    raise RuntimeError("Not enough trading days in response.")

yesterday = sorted_dates[0]
day_before_yesterday = sorted_dates[1]

# --------- Get Closing Prices ---------
yesterday_close = float(time_series[yesterday]["4. close"])
day_before_close = float(time_series[day_before_yesterday]["4. close"])

# --------- Calculate Price Differences ---------
pos_diff = round(abs(yesterday_close - day_before_close), 2)
raw_perc = (yesterday_close - day_before_close) / day_before_close * 100
perc_diff = round(raw_perc, 2)

print(f"Yesterday's Close ({yesterday}): ${yesterday_close}")
print(f"Day Before Yesterday's Close ({day_before_yesterday}): ${day_before_close}")
print(f"Absolute Difference: ${pos_diff}")
print(f"Percentage Difference: {perc_diff}%")

# --------- Threshold (use >= so 0.00 still triggers when testing) ---------
THRESHOLD_PCT = 0
if abs(perc_diff) >= THRESHOLD_PCT:
    print("Significant move detected; fetching news...")

    # --------- News API Request ---------
    news_params = {
        "apiKey": NEWS_API_KEY,
        "q": f'"{COMPANY_NAME}" OR {STOCK_NAME}',
        "searchIn": "title,description",
        "sortBy": "publishedAt",
        "language": "en",
        "pageSize": 3
    }

    news_response = requests.get(NEWS_ENDPOINT, params=news_params, timeout=20)
    news_response.raise_for_status()
    articles = (news_response.json().get("articles") or [])[:3]

    # --------- Build a short, ASCII-safe body (reduces filtering risk) ---------
    direction = "UP" if raw_perc > 0 else "DOWN" if raw_perc < 0 else "FLAT"
    if articles:
        titles = "\n".join(f"- {a.get('title','(No Title)')}" for a in articles)
        body = f"{STOCK_NAME} {direction} {abs(perc_diff)}%\n{titles}"
    else:
        body = f"{STOCK_NAME} {direction} {abs(perc_diff)}% | No recent articles."

    print("\n--- SMS Body Preview ---\n" + body)

    # --------- Send via Twilio (single SMS) + status polling ---------
    sms = client.messages.create(body=body, from_=FROM_NUMBER, to=TO_NUMBER)
    print("Created:", sms.sid, "initial status:", sms.status)

    for _ in range(10):
        sms = client.messages(sid=sms.sid).fetch()
        print("Status:", sms.status)
        if sms.status in {"delivered", "failed", "undelivered"}:
            print("Final status:", sms.status, "error_code:", sms.error_code, "error_message:", sms.error_message)
            break
        sleep(2)
else:
    print(f"Move {abs(perc_diff)}% does not meet threshold {THRESHOLD_PCT}% — no news sent.")
