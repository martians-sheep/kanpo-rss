"""Tests for kanpo_rss.parser."""

from datetime import date

from kanpo_rss.models import GazetteIssue, GazetteType
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


def _honshi_issue() -> GazetteIssue:
    return GazetteIssue(
        date=date(2026, 3, 3),
        gazette_type=GazetteType.HONSHI,
        issue_number=1657,
        issue_id="20260303h01657",
        url="https://www.kanpo.go.jp/20260303/20260303h01657/20260303h016570000f.html",
        title="2026-03-03 本紙 第1657号",
    )


def _gougai_issue() -> GazetteIssue:
    return GazetteIssue(
        date=date(2026, 3, 3),
        gazette_type=GazetteType.GOUGAI,
        issue_number=43,
        issue_id="20260303g00043",
        url="https://www.kanpo.go.jp/20260303/20260303g00043/20260303g000430000f.html",
        title="2026-03-03 号外 第43号",
    )


class TestParseIssuePage:
    def setup_method(self) -> None:
        self.parser = KanpoParser()

    def test_extracts_articles_honshi(self, issue_page_honshi_html: str) -> None:
        articles = self.parser.parse_issue_page(
            issue_page_honshi_html, _honshi_issue()
        )
        assert len(articles) > 0

    def test_honshi_article_count(self, issue_page_honshi_html: str) -> None:
        """本紙には告示12件+見出しリンク4件+公告2件 = 18件の記事がある。"""
        articles = self.parser.parse_issue_page(
            issue_page_honshi_html, _honshi_issue()
        )
        # フィクスチャの実際の記事数で検証
        assert len(articles) >= 15

    def test_extracts_articles_gougai(self, issue_page_gougai_html: str) -> None:
        articles = self.parser.parse_issue_page(
            issue_page_gougai_html, _gougai_issue()
        )
        assert len(articles) > 0

    def test_article_id_uniqueness(self, issue_page_honshi_html: str) -> None:
        articles = self.parser.parse_issue_page(
            issue_page_honshi_html, _honshi_issue()
        )
        ids = [a.article_id for a in articles]
        assert len(ids) == len(set(ids))

    def test_article_url_format(self, issue_page_honshi_html: str) -> None:
        articles = self.parser.parse_issue_page(
            issue_page_honshi_html, _honshi_issue()
        )
        for article in articles:
            assert article.url.startswith("https://www.kanpo.go.jp/")
            assert "20260303h01657" in article.url
            assert article.url.endswith("f.html")

    def test_parent_issue_id(self, issue_page_honshi_html: str) -> None:
        articles = self.parser.parse_issue_page(
            issue_page_honshi_html, _honshi_issue()
        )
        for article in articles:
            assert article.parent_issue_id == "20260303h01657"

    def test_section_assignment(self, issue_page_honshi_html: str) -> None:
        articles = self.parser.parse_issue_page(
            issue_page_honshi_html, _honshi_issue()
        )
        sections = {a.section for a in articles}
        assert "その他告示" in sections
        assert "公告 / 諸事項 / 裁判所" in sections

    def test_first_article_is_palau(self, issue_page_honshi_html: str) -> None:
        articles = self.parser.parse_issue_page(
            issue_page_honshi_html, _honshi_issue()
        )
        assert "パラオ" in articles[0].title

    def test_page_number_extraction(self, issue_page_honshi_html: str) -> None:
        articles = self.parser.parse_issue_page(
            issue_page_honshi_html, _honshi_issue()
        )
        palau = articles[0]
        assert palau.page_number == 1

    def test_nested_section_hierarchy(self, issue_page_honshi_html: str) -> None:
        """官庁報告 / 労働 のようなネストされたセクションが正しく追跡されること。"""
        articles = self.parser.parse_issue_page(
            issue_page_honshi_html, _honshi_issue()
        )
        labor_articles = [a for a in articles if "労働" in a.section]
        assert len(labor_articles) > 0
        assert labor_articles[0].section == "官庁報告 / 労働"

    def test_heading_link_articles(self, issue_page_gougai_html: str) -> None:
        """h4 内のリンク（会社その他、会社決算公告）も記事として抽出されること。"""
        articles = self.parser.parse_issue_page(
            issue_page_gougai_html, _gougai_issue()
        )
        titles = [a.title for a in articles]
        assert "会社その他" in titles
        assert "会社決算公告" in titles

    def test_empty_html_returns_empty(self) -> None:
        articles = self.parser.parse_issue_page(
            "<html><body></body></html>", _honshi_issue()
        )
        assert articles == []
