"""Tests for kanpo_rss.parser."""

from datetime import date

from kanpo_rss.models import GazetteType
from kanpo_rss.parser import KanpoParser


class TestParseTopPage:
    def setup_method(self) -> None:
        self.parser = KanpoParser()

    def test_extracts_issues(self, top_page_html: str) -> None:
        issues = self.parser.parse_top_page(top_page_html)
        assert len(issues) > 0

    def test_most_recent_date(self, top_page_html: str) -> None:
        issues = self.parser.parse_top_page(top_page_html)
        dates = sorted({i.date for i in issues}, reverse=True)
        assert dates[0] == date(2026, 3, 3)

    def test_contains_all_gazette_types(self, top_page_html: str) -> None:
        issues = self.parser.parse_top_page(top_page_html)
        types_found = {i.gazette_type for i in issues}
        assert GazetteType.HONSHI in types_found
        assert GazetteType.GOUGAI in types_found
        assert GazetteType.SEIFU_CHOUTATSU in types_found
        assert GazetteType.TOKUBETSU_GOUGAI in types_found

    def test_issue_id_format(self, top_page_html: str) -> None:
        issues = self.parser.parse_top_page(top_page_html)
        for issue in issues:
            assert len(issue.issue_id) == 14  # 8 date + 1 type + 5 number
            assert issue.issue_id[8] in "hgct"

    def test_url_is_per_issue(self, top_page_html: str) -> None:
        issues = self.parser.parse_top_page(top_page_html)
        for issue in issues:
            assert issue.issue_id in issue.url
            assert issue.url.startswith("https://www.kanpo.go.jp/")
            assert issue.url.endswith("0000f.html")

    def test_title_format(self, top_page_html: str) -> None:
        issues = self.parser.parse_top_page(top_page_html)
        honshi = [i for i in issues if i.gazette_type == GazetteType.HONSHI]
        assert len(honshi) > 0
        assert "本紙" in honshi[0].title
        assert "第" in honshi[0].title
        assert "号" in honshi[0].title

    def test_guid_uniqueness(self, top_page_html: str) -> None:
        issues = self.parser.parse_top_page(top_page_html)
        ids = [i.issue_id for i in issues]
        assert len(ids) == len(set(ids))

    def test_specific_issue_20260303_honshi(self, top_page_html: str) -> None:
        issues = self.parser.parse_top_page(top_page_html)
        honshi_0303 = [
            i
            for i in issues
            if i.date == date(2026, 3, 3)
            and i.gazette_type == GazetteType.HONSHI
        ]
        assert len(honshi_0303) == 1
        issue = honshi_0303[0]
        assert issue.issue_number == 1657
        assert issue.issue_id == "20260303h01657"

    def test_empty_html_returns_empty(self) -> None:
        issues = self.parser.parse_top_page("<html><body></body></html>")
        assert issues == []

    def test_multiple_gougai_same_date(self, top_page_html: str) -> None:
        """2026-02-27 has two 号外 issues (40, 41)."""
        issues = self.parser.parse_top_page(top_page_html)
        gougai_0227 = [
            i
            for i in issues
            if i.date == date(2026, 2, 27)
            and i.gazette_type == GazetteType.GOUGAI
        ]
        assert len(gougai_0227) == 2
        numbers = sorted(i.issue_number for i in gougai_0227)
        assert numbers == [40, 41]
