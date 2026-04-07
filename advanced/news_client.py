import requests


class NewsClient:
    """Fetches recent news articles from the News API."""

    def __init__(self, api_key: str, endpoint: str, timeout: int = 20):
        self._api_key  = api_key
        self._endpoint = endpoint
        self._timeout  = timeout

    def get_top_articles(self, company: str, symbol: str, count: int = 3) -> list[dict]:
        """
        Return up to `count` recent articles mentioning `company` or `symbol`.

        Each dict has at minimum: 'title' (str) and 'description' (str | None).

        Raises RuntimeError on HTTP errors.
        """
        params = {
            "apiKey":   self._api_key,
            "q":        f'"{company}" OR {symbol}',
            "searchIn": "title,description",
            "sortBy":   "publishedAt",
            "language": "en",
            "pageSize": count,
        }
        response = requests.get(self._endpoint, params=params, timeout=self._timeout)
        response.raise_for_status()
        articles = (response.json().get("articles") or [])[:count]
        print(f"[NewsClient] Retrieved {len(articles)} article(s) for '{company}'.")
        return articles
