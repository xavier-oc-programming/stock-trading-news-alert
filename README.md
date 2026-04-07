# Stock Trading News Alert

Monitors a stock's daily price change and sends SMS alerts with top news articles via Twilio when a threshold is crossed.

---

## Table of Contents

1. [Quick start](#1-quick-start)
2. [Builds comparison](#2-builds-comparison)
3. [Usage](#3-usage)
4. [Data flow](#4-data-flow)
5. [Features](#5-features)
6. [Navigation flow](#6-navigation-flow)
7. [Architecture](#7-architecture)
8. [Module reference](#8-module-reference)
9. [Configuration reference](#9-configuration-reference)
10. [Data schema](#10-data-schema)
11. [Environment variables](#11-environment-variables)
12. [Design decisions](#12-design-decisions)
13. [Course context](#13-course-context)
14. [Dependencies](#14-dependencies)

---

## 1. Quick start

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in your API keys and Twilio credentials
python menu.py         # select 1 (original) or 2 (advanced), or run directly:
python original/main.py
python advanced/main.py
```

---

## 2. Builds comparison

| Feature | Original | Advanced |
|---------|----------|----------|
| Alpha Vantage stock fetch | Yes | Yes |
| NewsAPI top 3 articles | Yes | Yes |
| Twilio SMS per article | Yes | Yes |
| Configurable threshold | Hardcoded `THRESHOLD_PCT = 0` | `config.py` — default 5% |
| UCS-2 SMS truncation | Yes (`clamp_ucs2`) | Yes (`SmsSender.clamp_ucs2`) |
| Local daily quota guard | Yes (inline functions) | Yes (`SmsSender`) |
| Alpha Vantage error detection | Yes | Yes |
| Object-oriented design | No | Yes — `StockClient`, `NewsClient`, `SmsSender` |
| Centralised config | No | Yes — `advanced/config.py` |
| Persistent quota file | `original/.sms_quota.json` | `advanced/data/sms_quota.json` |
| GitHub Actions (daily schedule) | No | Yes |

---

## 3. Usage

Both builds are single-run scripts — they execute once and exit.

**Original:**
```bash
python original/main.py
# or via menu: python menu.py → 1
```

**Advanced:**
```bash
python advanced/main.py
# or via menu: python menu.py → 2
```

**Example terminal output (advanced):**
```
[SmsSender] Auth OK — from +15204927666 to +34665151440
[StockClient] TSLA — 2025-09-19: $248.23  |  2025-09-18: $235.72
[StockClient] Change: +5.31%  ($12.51)
Significant move detected (+5.31%) — fetching news…
[NewsClient] Retrieved 3 article(s) for 'Tesla Inc'.

Title: Tesla Surges After Robotaxi Reveal — Analysts Raise Targets
Brief: Shares jumped over 5% on Thursday following Elon Musk's presentation...

--- SMS Preview ---
TSLA: 🔺5.31% | Tesla Surges After Robotaxi Reveal — Ana…
[SmsSender] Sent SID: SMxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

---

## 4. Data flow

**One full execution (advanced build):**

```
Input
  └── Environment variables (.env): API keys, Twilio credentials

Fetch — StockClient
  └── GET https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol=TSLA
  └── JSON response → extract two most recent closing prices
  └── Returns: (perc_diff: float, abs_diff: float)

Decision
  └── abs(perc_diff) < THRESHOLD_PCT (5.0%) → exit with no alert
  └── abs(perc_diff) ≥ THRESHOLD_PCT → continue

Fetch — NewsClient
  └── GET https://newsapi.org/v2/everything?q="Tesla Inc" OR TSLA&pageSize=3
  └── JSON response → list of article dicts
  └── Returns: list[dict] with 'title' and 'description'

Output — SmsSender (per article, up to 3)
  └── Check quota: advanced/data/sms_quota.json (daily count)
  └── Build SMS body: "TSLA: 🔺5.31% | {title} - {brief}" (truncated to 65 chars)
  └── POST to Twilio Messages API
  └── Update quota file
  └── Returns: Twilio SID or None (quota exhausted)
```

---

## 5. Features

**Both builds**

**Stock price comparison.** Fetches the two most recent trading day closing prices from Alpha Vantage and calculates the signed percentage change between them.

**Threshold guard.** Only sends alerts when the absolute percentage change meets or exceeds the configured threshold. In the original build this is hardcoded to 0 (always triggers); in the advanced build it defaults to 5%.

**Top 3 news articles.** When the threshold is crossed, queries NewsAPI for the three most recent articles mentioning the company name or ticker symbol.

**Per-article SMS.** Sends one Twilio SMS per article with a formatted header (`TSLA: 🔺5.31% | headline - brief`) truncated to fit a single UCS-2 SMS segment (~65 characters safe).

**Alpha Vantage error detection.** Detects rate-limit and quota responses (`Note`, `Information` keys) and raises a descriptive error rather than silently failing.

**Local daily quota guard.** Tracks the number of SMS messages sent today in a local JSON file. Stops sending once the daily cap is reached, preventing Twilio trial account overages across multiple script invocations in the same day.

**Advanced build only**

**Configurable threshold via config.py.** All constants — URLs, thresholds, limits, paths — live in a single file. No magic numbers anywhere else.

**OOP module separation.** `StockClient`, `NewsClient`, and `SmsSender` each own exactly one concern. They can be tested and swapped independently.

**GitHub Actions daily schedule.** Runs automatically at 06:00 UTC on weekdays (07:00 CET winter). Includes `workflow_dispatch` for manual runs.

---

## 6. Navigation flow

### a) Terminal menu tree

```
python menu.py
│
├── 1 → python original/main.py (cwd: original/)
│         [press Enter]
│         → redraw menu
│
├── 2 → python advanced/main.py (cwd: advanced/)
│         [press Enter]
│         → redraw menu
│
├── q → exit
│
└── other → "Invalid choice. Try again." (no clear — error stays visible)
```

### b) Execution flow (advanced build)

```
START
  │
  ├─ Load .env → require all 6 env vars → RuntimeError if any missing
  │
  ├─ SmsSender.verify_auth()
  │     └─ Twilio API reachable? → No → TwilioRestException → abort
  │
  ├─ StockClient.get_daily_change()
  │     └─ Alpha Vantage responds with "Note"/"Information"? → RuntimeError → abort
  │     └─ Fewer than 2 trading days in response? → RuntimeError → abort
  │     └─ Returns (perc_diff, abs_diff)
  │
  ├─ abs(perc_diff) < THRESHOLD_PCT?
  │     └─ Yes → print "below threshold" → EXIT (no SMS)
  │
  ├─ NewsClient.get_top_articles()
  │     └─ HTTP error? → requests.HTTPError → abort
  │     └─ Returns list (may be empty)
  │
  ├─ articles empty?
  │     └─ Yes → send one "No recent articles" SMS → EXIT
  │
  └─ For each article (up to 3):
        ├─ SmsSender.can_send() == False? → print "quota exhausted" → BREAK
        └─ SmsSender.send(body)
              └─ TwilioRestException → print error → raise
              └─ Success → record send → print SID
END
```

---

## 7. Architecture

```
stock-trading-news-alert/
│
├── menu.py                  # Terminal menu — launches original or advanced
├── art.py                   # LOGO ascii art printed by menu.py
├── requirements.txt         # pip dependencies + Python version note
├── .env.example             # Template for required environment variables
├── .gitignore
│
├── original/
│   └── main.py              # Verbatim course script (path fix only)
│
├── advanced/
│   ├── config.py            # All constants and pure helper functions
│   ├── stock_client.py      # StockClient — Alpha Vantage data fetch
│   ├── news_client.py       # NewsClient — NewsAPI article fetch
│   ├── sms_sender.py        # SmsSender — Twilio send + quota guard
│   ├── main.py              # Orchestrator — wires modules together
│   └── data/
│       ├── .gitkeep
│       └── example.json     # Sample quota file format (committed)
│
├── docs/
│   └── COURSE_NOTES.md      # Original exercise description and variant notes
│
└── .github/
    └── workflows/
        └── stock-trading-news-alert.yml  # Daily GitHub Actions run
```

---

## 8. Module reference

### `StockClient` — `advanced/stock_client.py`

| Method | Returns | Description |
|--------|---------|-------------|
| `__init__(api_key, endpoint, symbol, timeout)` | `None` | Stores connection parameters. |
| `get_daily_change()` | `tuple[float, float]` | Fetches daily time series from Alpha Vantage; returns `(perc_diff, abs_diff)` for the two most recent trading days. Raises `RuntimeError` on API errors or insufficient data. |

### `NewsClient` — `advanced/news_client.py`

| Method | Returns | Description |
|--------|---------|-------------|
| `__init__(api_key, endpoint, timeout)` | `None` | Stores connection parameters. |
| `get_top_articles(company, symbol, count)` | `list[dict]` | Queries NewsAPI for articles matching `company` or `symbol`. Returns up to `count` dicts, each with at minimum `title` and `description`. Raises `requests.HTTPError` on failure. |

### `SmsSender` — `advanced/sms_sender.py`

| Method | Returns | Description |
|--------|---------|-------------|
| `__init__(account_sid, auth_token, from_number, to_number, quota_file, max_per_day)` | `None` | Initialises Twilio client and quota parameters. |
| `verify_auth()` | `None` | Performs a lightweight Twilio account fetch. Raises `TwilioRestException` if credentials are invalid. |
| `can_send()` | `bool` | Returns `True` if the daily send count is below `max_per_day`. Resets count at midnight. |
| `send(body)` | `str \| None` | Sends `body` as an SMS. Returns Twilio SID on success, `None` if quota exhausted. Raises `TwilioRestException` on send failure. |
| `sanitize(text)` *(static)* | `str` | Strips newlines and leading/trailing whitespace. |
| `clamp_ucs2(text, limit)` *(static)* | `str` | Truncates to `limit` characters and appends `…` if over limit. |
| `build_body(stock, emoji, perc, title, brief, limit)` *(classmethod)* | `str` | Builds the formatted SMS body: `"TSLA: 🔺5.31% | title - brief"`, clamped to `limit`. |

---

## 9. Configuration reference

All constants live in `advanced/config.py`.

| Constant | Default | Description |
|----------|---------|-------------|
| `STOCK_NAME` | `"TSLA"` | Ticker symbol to monitor |
| `COMPANY_NAME` | `"Tesla Inc"` | Company name used in NewsAPI query |
| `STOCK_ENDPOINT` | Alpha Vantage URL | Base URL for stock price API |
| `NEWS_ENDPOINT` | NewsAPI URL | Base URL for news API |
| `THRESHOLD_PCT` | `5.0` | Minimum absolute % move to trigger an alert |
| `MAX_SMS_PER_DAY` | `8` | Daily send cap (Twilio trial accounts are capped at ~9) |
| `NEWS_PAGE_SIZE` | `3` | Number of articles to fetch and send |
| `FETCH_TIMEOUT` | `20` | HTTP request timeout in seconds |
| `SMS_CHAR_LIMIT` | `65` | Maximum characters per SMS body (UCS-2 safe) |
| `DATA_DIR` | `advanced/data/` | Directory for runtime-persisted files |
| `QUOTA_FILE` | `advanced/data/sms_quota.json` | Daily SMS count tracker |

---

## 10. Data schema

### Alpha Vantage response (relevant excerpt)

```json
{
  "Time Series (Daily)": {
    "2025-09-19": { "4. close": "248.23" },
    "2025-09-18": { "4. close": "235.72" }
  }
}
```

### NewsAPI response (relevant excerpt)

```json
{
  "articles": [
    {
      "title": "Tesla Surges After Robotaxi Reveal",
      "description": "Shares jumped over 5% on Thursday..."
    }
  ]
}
```

### Quota file — `advanced/data/sms_quota.json`

```json
{"date": "2025-09-19", "count": 3}
```

`date`: ISO 8601 date string (`YYYY-MM-DD`). Resets count to 0 when today's date differs.  
`count`: number of SMS messages sent today.

### SMS body format

```
TSLA: 🔺5.31% | Tesla Surges After Robotaxi Reveal — Ana…
```

Max 65 characters. Trailing `…` added when truncated.

---

## 11. Environment variables

Copy `.env.example` to `.env` and fill in values before running.

| Variable | Required | Description |
|----------|----------|-------------|
| `API_KEY_ALPHA` | Yes | Alpha Vantage API key — free tier at alphavantage.co |
| `NEWS_API_KEY` | Yes | NewsAPI key — free tier at newsapi.org |
| `TWILIO_ACCOUNT_SID` | Yes | Twilio Account SID (starts with `AC`) |
| `TWILIO_AUTH_TOKEN` | Yes | Twilio Auth Token |
| `TWILIO_FROM` | Yes | Twilio phone number to send from (E.164 format, e.g. `+15204927666`) |
| `TWILIO_TO` | Yes | Destination phone number (E.164 format) |

---

## 12. Design decisions

**`config.py` — zero magic numbers.** Every constant — URL, threshold, limit, path — is defined once in `config.py`. Changing the stock symbol, threshold, or SMS cap requires editing one line in one file. No hunting through logic code.

**Separate `StockClient`, `NewsClient`, `SmsSender` modules.** Each module has a single responsibility: fetch stock data, fetch news, or send messages. This means each class can be tested and replaced independently. Swapping NewsAPI for another provider only requires rewriting `news_client.py`; nothing else changes.

**Credentials via `.env`, never hardcoded.** API keys and phone numbers in source code are a security and rotation risk. `.env` keeps them out of version control. `load_dotenv()` is a no-op when `.env` is absent (e.g. in GitHub Actions), so the same code works locally and in CI without modification.

**`.env.example` committed, `.env` gitignored.** Anyone cloning the repo sees exactly which variables are needed without any credentials being leaked. The `.gitignore` entry for `.env` was added before the first commit, so it was never accidentally staged.

**`Path(__file__).parent` for all file paths.** Relative paths like `Path(".sms_quota.json")` break when the script is launched from a different working directory (e.g. via `menu.py`). Using `Path(__file__).parent` anchors every path to the script's own directory regardless of where it is called from.

**Pure-logic modules raise exceptions instead of `sys.exit()`.** `StockClient` and `NewsClient` raise `RuntimeError` or `requests.HTTPError` on failure. This lets `main.py` decide whether to retry, log, or abort — rather than forcing an immediate hard exit from inside a library class.

**`sys.path.insert` pattern in `advanced/main.py`.** Inserting the script's own directory at the front of `sys.path` ensures that sibling modules (`stock_client`, `news_client`, `sms_sender`, `config`) are found regardless of whether the script is run directly (`python advanced/main.py`) or via `menu.py`'s `subprocess.run(..., cwd=advanced/)`.

**`subprocess.run` + `cwd=` in `menu.py`.** Setting `cwd` to the script's parent directory means the child process has the same working directory it would have if run directly. This eliminates an entire class of path bugs without requiring any special handling in the sub-scripts.

**`while True` in `menu.py` vs recursion.** Re-calling `main()` from within itself would grow the call stack unboundedly over a long session. A `while True` loop with a `clear` flag costs nothing per iteration.

**Console cleared before every menu render (except invalid input).** Clearing after invalid input would erase the error message before the user reads it. The `clear = False` path after invalid input solves this.

**`advanced/data/` gitignored, `.gitkeep` committed.** The quota file changes every run and must not be tracked. But the directory itself must exist for the script to write into it. `.gitkeep` preserves the directory in git without tracking its contents. `SmsSender._save_quota()` also calls `mkdir(parents=True, exist_ok=True)` as a safety net.

**GitHub Actions — weekdays only, `workflow_dispatch` always included.** Markets are closed on weekends so there is no meaningful stock movement to alert on. `workflow_dispatch` allows manual runs during testing or after a holiday without modifying the schedule.

**`verify_auth()` called before hitting stock/news APIs.** A Twilio credential failure would otherwise only surface at the end of the script — after spending two API quota calls. Verifying Twilio first fails fast with a clear error.

---

## 13. Course context

Built as Day 36 of [100 Days of Code](https://www.udemy.com/course/100-days-of-code/) by Dr. Angela Yu.

**Concepts covered in the original build:**
- REST API consumption with `requests` (GET with query parameters, JSON parsing)
- Chained API calls (stock price → conditionally fetch news → send SMS)
- Environment variable management with `python-dotenv`
- Conditional logic based on computed data (percentage threshold)
- String manipulation and truncation for SMS length constraints
- Twilio SMS API integration

**The advanced build extends into:**
- Object-oriented design (single-responsibility classes)
- Dependency injection (clients receive credentials at construction time)
- Centralised configuration (`config.py` as the single source of truth)
- Persistent runtime state (`data/sms_quota.json`)
- GitHub Actions for automated daily execution with secrets management

See [docs/COURSE_NOTES.md](docs/COURSE_NOTES.md) for the full concept breakdown and notes on the different script variants.

---

## 14. Dependencies

| Module | Used in | Purpose |
|--------|---------|---------|
| `requests` | `stock_client.py`, `news_client.py`, `original/main.py` | HTTP requests to Alpha Vantage and NewsAPI |
| `twilio` | `sms_sender.py`, `original/main.py` | Twilio REST API client for SMS sending |
| `python-dotenv` | `advanced/main.py`, `original/main.py` | Loads `.env` into environment variables |
| `json` | `sms_sender.py`, `original/main.py` | Read/write quota state file |
| `pathlib` | All modules | Platform-safe file path construction |
| `os` | `advanced/main.py`, `original/main.py`, `menu.py` | `os.getenv`, `os.system` for console clear |
| `datetime` | `sms_sender.py`, `original/main.py` | Today's date for quota reset logic |
| `sys` | `menu.py`, `advanced/main.py` | `sys.executable`, `sys.path` manipulation |
| `subprocess` | `menu.py` | Launch builds as child processes |
