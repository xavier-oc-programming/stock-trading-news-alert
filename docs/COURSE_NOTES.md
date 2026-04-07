# Course Notes — Day 36: Stock Trading News Alert

## Original exercise description

Build a script that:
1. Fetches the last two days of closing prices for a stock (TSLA) from the Alpha Vantage API.
2. Calculates the percentage change between the two days.
3. If the change exceeds a threshold (e.g. 5%), queries NewsAPI for the top 3 articles about that company.
4. Sends one SMS per article via Twilio, formatted as:
   `TSLA: 🔺5.0% | Headline - Brief description`

## Concepts covered in the original build

- Consuming REST APIs with `requests` (Alpha Vantage, NewsAPI, Twilio)
- Parsing JSON responses and extracting nested values
- Environment variables via `python-dotenv` for credential management
- Conditional logic: only alert when a threshold is crossed
- String formatting and truncation for SMS length constraints

## Variants in the repo

| File | Description | Chosen for original/? |
|------|-------------|----------------------|
| `main.py` | Full version with per-article SMS, UCS-2 clamping, and local quota guard | **Yes** |
| `main2.py` | Simpler version — single combined SMS, Twilio status polling loop | No — moved to old_files/ |
| `twilio_check.py` | Utility to verify Twilio credentials; not part of the exercise | No — moved to old_files/ |

## Key differences between main.py and main2.py

- `main.py` sends one SMS per article (up to 3); `main2.py` sends a single combined message.
- `main.py` uses UCS-2-safe truncation (`clamp_ucs2`) and emoji direction indicators (🔺/🔻).
- `main.py` includes a local quota guard (`.sms_quota.json`) to avoid exceeding Twilio trial limits.
- `main2.py` polls Twilio for delivery status after sending.

## The advanced build extends into

- Object-oriented design: `StockClient`, `NewsClient`, `SmsSender` classes
- Single-responsibility principle: each module handles exactly one concern
- Centralised configuration via `config.py` (zero magic numbers elsewhere)
- GitHub Actions workflow for automated daily execution (weekdays, 06:00 UTC)
- Persistent quota state in `advanced/data/sms_quota.json`
