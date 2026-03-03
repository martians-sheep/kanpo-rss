"""HTTP scraper for kanpo.go.jp."""

from __future__ import annotations

import logging
import time

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

BASE_URL = "https://www.kanpo.go.jp"
DEFAULT_USER_AGENT = "kanpo-rss/0.1.0 (+https://github.com/kanpo-rss/kanpo-rss)"
MIN_REQUEST_INTERVAL = 1.0  # seconds


class KanpoScraper:
    """Fetches HTML pages from kanpo.go.jp with retry and rate limiting."""

    def __init__(self, user_agent: str = DEFAULT_USER_AGENT) -> None:
        self._session = self._build_session(user_agent)
        self._last_request_time: float = 0.0

    def fetch_top_page(self) -> str:
        """Fetch the kanpo.go.jp top page HTML."""
        url = f"{BASE_URL}/"
        return self._fetch(url)

    def fetch_issue_page(self, url: str) -> str:
        """Fetch an issue's table of contents page (0000f.html)."""
        return self._fetch(url)

    def _fetch(self, url: str) -> str:
        """Fetch a URL with rate limiting."""
        self._rate_limit()
        logger.info("Fetching %s", url)
        response = self._session.get(url, timeout=(10, 30))
        response.raise_for_status()
        response.encoding = response.apparent_encoding
        return response.text

    def _rate_limit(self) -> None:
        """Ensure minimum interval between requests."""
        elapsed = time.monotonic() - self._last_request_time
        if elapsed < MIN_REQUEST_INTERVAL:
            time.sleep(MIN_REQUEST_INTERVAL - elapsed)
        self._last_request_time = time.monotonic()

    @staticmethod
    def _build_session(user_agent: str) -> requests.Session:
        retry_strategy = Retry(
            total=3,
            backoff_factor=1.0,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session = requests.Session()
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        session.headers.update({"User-Agent": user_agent})
        return session
