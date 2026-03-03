"""Tests for kanpo_rss.scraper."""

import time

import requests
import requests_mock as rm

from kanpo_rss.scraper import BASE_URL, KanpoScraper


class TestKanpoScraper:
    def test_fetch_top_page_success(self, requests_mock: rm.Mocker) -> None:
        html = "<html><body>test</body></html>"
        requests_mock.get(f"{BASE_URL}/", text=html)
        scraper = KanpoScraper()
        result = scraper.fetch_top_page()
        assert result == html

    def test_fetch_fullcontents_success(
        self, requests_mock: rm.Mocker
    ) -> None:
        html = "<html><body>fullcontents</body></html>"
        date_str = "20260303"
        url = f"{BASE_URL}/{date_str}/{date_str}.fullcontents.html"
        requests_mock.get(url, text=html)
        scraper = KanpoScraper()
        result = scraper.fetch_fullcontents(date_str)
        assert result == html

    def test_raises_on_server_error(self, requests_mock: rm.Mocker) -> None:
        """requests_mock bypasses urllib3 retry; verify raise_for_status works."""
        requests_mock.get(f"{BASE_URL}/", status_code=500)
        scraper = KanpoScraper()
        try:
            scraper.fetch_top_page()
            assert False, "Expected HTTPError"
        except requests.HTTPError as e:
            assert e.response.status_code == 500

    def test_raises_on_persistent_error(
        self, requests_mock: rm.Mocker
    ) -> None:
        requests_mock.get(f"{BASE_URL}/", status_code=404)
        scraper = KanpoScraper()
        try:
            scraper.fetch_top_page()
            assert False, "Expected HTTPError"
        except requests.HTTPError:
            pass

    def test_rate_limiting(self, requests_mock: rm.Mocker) -> None:
        requests_mock.get(f"{BASE_URL}/", text="<html></html>")
        scraper = KanpoScraper()
        start = time.monotonic()
        scraper.fetch_top_page()
        scraper.fetch_top_page()
        elapsed = time.monotonic() - start
        assert elapsed >= 1.0

    def test_custom_user_agent(self, requests_mock: rm.Mocker) -> None:
        requests_mock.get(f"{BASE_URL}/", text="ok")
        scraper = KanpoScraper(user_agent="test-agent/1.0")
        scraper.fetch_top_page()
        assert requests_mock.last_request.headers["User-Agent"] == "test-agent/1.0"
