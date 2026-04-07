import requests


class StockClient:
    """Fetches daily closing prices from Alpha Vantage and computes price change."""

    def __init__(self, api_key: str, endpoint: str, symbol: str, timeout: int = 20):
        self._api_key  = api_key
        self._endpoint = endpoint
        self._symbol   = symbol
        self._timeout  = timeout

    def get_daily_change(self) -> tuple[float, float]:
        """
        Return (perc_diff, abs_diff) for the two most recent trading days.

        perc_diff: signed percentage change (negative = drop)
        abs_diff:  absolute price difference in USD

        Raises RuntimeError on API errors or insufficient data.
        """
        params = {
            "function":   "TIME_SERIES_DAILY",
            "symbol":     self._symbol,
            "outputsize": "compact",
            "datatype":   "json",
            "apikey":     self._api_key,
        }
        response = requests.get(self._endpoint, params=params, timeout=self._timeout)
        response.raise_for_status()
        data = response.json()

        ts_key = "Time Series (Daily)"
        if ts_key not in data:
            msg = data.get("Note") or data.get("Information") or "Unexpected Alpha Vantage response."
            raise RuntimeError(f"Alpha Vantage error: {msg}")

        time_series  = data[ts_key]
        sorted_dates = sorted(time_series.keys(), reverse=True)
        if len(sorted_dates) < 2:
            raise RuntimeError("Not enough trading days in Alpha Vantage response.")

        yesterday  = sorted_dates[0]
        day_before = sorted_dates[1]
        close_y    = float(time_series[yesterday]["4. close"])
        close_db   = float(time_series[day_before]["4. close"])

        abs_diff  = round(abs(close_y - close_db), 2)
        perc_diff = round((close_y - close_db) / close_db * 100, 2)

        print(f"[StockClient] {self._symbol} — {yesterday}: ${close_y}  |  {day_before}: ${close_db}")
        print(f"[StockClient] Change: {perc_diff:+.2f}%  (${abs_diff})")

        return perc_diff, abs_diff
