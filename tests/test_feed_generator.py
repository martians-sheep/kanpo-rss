"""Tests for kanpo_rss.feed_generator."""

import tempfile
from datetime import date
from pathlib import Path
from xml.etree import ElementTree as ET

from kanpo_rss.feed_generator import KanpoFeedGenerator, _atom_path
from kanpo_rss.models import GazetteArticle, GazetteIssue, GazetteType

ATOM_NS = "http://www.w3.org/2005/Atom"


def _make_issue(
    pub_date: date = date(2026, 3, 3),
    gazette_type: GazetteType = GazetteType.HONSHI,
    issue_number: int = 1657,
) -> GazetteIssue:
    date_str = pub_date.strftime("%Y%m%d")
    prefix = gazette_type.value
    issue_id = f"{date_str}{prefix}{issue_number:05d}"
    return GazetteIssue(
        date=pub_date,
        gazette_type=gazette_type,
        issue_number=issue_number,
        issue_id=issue_id,
        url=f"https://www.kanpo.go.jp/{date_str}/{issue_id}/{issue_id}0000f.html",
        title=f"{pub_date.isoformat()} {gazette_type.label} 第{issue_number}号",
    )


def _make_issue_with_articles(
    pub_date: date = date(2026, 3, 3),
    gazette_type: GazetteType = GazetteType.HONSHI,
    issue_number: int = 1657,
) -> GazetteIssue:
    date_str = pub_date.strftime("%Y%m%d")
    prefix = gazette_type.value
    issue_id = f"{date_str}{prefix}{issue_number:05d}"
    articles = [
        GazetteArticle(
            article_id=f"{issue_id}:0001:0",
            title="テスト記事A",
            url=f"https://www.kanpo.go.jp/{date_str}/{issue_id}/{issue_id}0001f.html",
            section="その他告示",
            parent_issue_id=issue_id,
            page_number=1,
        ),
        GazetteArticle(
            article_id=f"{issue_id}:0001:1",
            title="テスト記事B",
            url=f"https://www.kanpo.go.jp/{date_str}/{issue_id}/{issue_id}0001f.html",
            section="その他告示",
            parent_issue_id=issue_id,
            page_number=1,
        ),
        GazetteArticle(
            article_id=f"{issue_id}:0008:0",
            title="国会事項",
            url=f"https://www.kanpo.go.jp/{date_str}/{issue_id}/{issue_id}0008f.html",
            section="国会事項",
            parent_issue_id=issue_id,
            page_number=8,
        ),
    ]
    return GazetteIssue(
        date=pub_date,
        gazette_type=gazette_type,
        issue_number=issue_number,
        issue_id=issue_id,
        url=f"https://www.kanpo.go.jp/{date_str}/{issue_id}/{issue_id}0000f.html",
        title=f"{pub_date.isoformat()} {gazette_type.label} 第{issue_number}号",
        articles=articles,
    )


class TestAtomPath:
    def test_basic(self) -> None:
        assert _atom_path("docs/feed.xml") == "docs/feed-atom.xml"

    def test_archive(self) -> None:
        assert _atom_path("docs/feed-archive.xml") == "docs/feed-archive-atom.xml"

    def test_nested(self) -> None:
        assert _atom_path("a/b/c.xml") == "a/b/c-atom.xml"


class TestFullcontentsFeedGenerator:
    def test_generates_valid_rss(self) -> None:
        issues = [_make_issue_with_articles()]
        gen = KanpoFeedGenerator()
        with tempfile.TemporaryDirectory() as tmpdir:
            gen.generate_fullcontents_feed(issues, date(2026, 3, 3), tmpdir)
            rss = Path(tmpdir) / "feed-fullcontents.xml"
            assert rss.exists()
            root = ET.parse(rss).getroot()
        assert root.tag == "rss"
        assert root.attrib["version"] == "2.0"

    def test_generates_atom(self) -> None:
        issues = [_make_issue_with_articles()]
        gen = KanpoFeedGenerator()
        with tempfile.TemporaryDirectory() as tmpdir:
            gen.generate_fullcontents_feed(issues, date(2026, 3, 3), tmpdir)
            atom = Path(tmpdir) / "feed-fullcontents-atom.xml"
            assert atom.exists()
            root = ET.parse(atom).getroot()
        assert root.tag == f"{{{ATOM_NS}}}feed"

    def test_generates_dated_feed(self) -> None:
        issues = [_make_issue_with_articles()]
        gen = KanpoFeedGenerator()
        with tempfile.TemporaryDirectory() as tmpdir:
            gen.generate_fullcontents_feed(issues, date(2026, 3, 3), tmpdir)
            dated = Path(tmpdir) / "fullcontents" / "feed-20260303.xml"
            assert dated.exists()

    def test_fullcontents_entry_plus_articles(self) -> None:
        """1日分 = fullcontents目次エントリー + 記事エントリー。"""
        issues = [_make_issue_with_articles()]
        gen = KanpoFeedGenerator()
        with tempfile.TemporaryDirectory() as tmpdir:
            gen.generate_fullcontents_feed(issues, date(2026, 3, 3), tmpdir)
            root = ET.parse(
                Path(tmpdir) / "feed-fullcontents.xml"
            ).getroot()
        items = root.findall(".//item")
        # 1 fullcontents entry + 3 articles
        assert len(items) == 4
        # First item is fullcontents page
        assert "全体目次" in (items[0].findtext("title") or "")

    def test_title_contains_suffix(self) -> None:
        issues = [_make_issue_with_articles()]
        gen = KanpoFeedGenerator()
        with tempfile.TemporaryDirectory() as tmpdir:
            gen.generate_fullcontents_feed(issues, date(2026, 3, 3), tmpdir)
            root = ET.parse(
                Path(tmpdir) / "feed-fullcontents.xml"
            ).getroot()
        title = root.findtext(".//channel/title") or ""
        assert "全体目次" in title

    def test_rolling_window_filters_by_date(self) -> None:
        """7日間のローリングウィンドウで古いデータは除外される。"""
        issues = [
            _make_issue_with_articles(pub_date=date(2026, 3, 3)),
            _make_issue_with_articles(
                pub_date=date(2026, 2, 20), issue_number=1650
            ),
        ]
        gen = KanpoFeedGenerator()
        with tempfile.TemporaryDirectory() as tmpdir:
            gen.generate_fullcontents_feed(
                issues, date(2026, 3, 3), tmpdir, days=7
            )
            root = ET.parse(
                Path(tmpdir) / "feed-fullcontents.xml"
            ).getroot()
        items = root.findall(".//item")
        # Only 3/3 data: 1 fullcontents + 3 articles = 4
        assert len(items) == 4

    def test_multiple_dates_in_window(self) -> None:
        """複数日のデータが含まれる場合、日付ごとにfullcontentsエントリーが追加される。"""
        issues = [
            _make_issue_with_articles(pub_date=date(2026, 3, 3)),
            _make_issue_with_articles(
                pub_date=date(2026, 3, 2), issue_number=1656
            ),
        ]
        gen = KanpoFeedGenerator()
        with tempfile.TemporaryDirectory() as tmpdir:
            gen.generate_fullcontents_feed(
                issues, date(2026, 3, 3), tmpdir, days=7
            )
            root = ET.parse(
                Path(tmpdir) / "feed-fullcontents.xml"
            ).getroot()
        items = root.findall(".//item")
        # 2 fullcontents entries + 3+3 articles = 8
        assert len(items) == 8
        # Both dates have fullcontents entries
        fc_titles = [
            item.findtext("title") or ""
            for item in items
            if "全体目次" in (item.findtext("title") or "")
        ]
        assert len(fc_titles) == 2

    def test_issues_without_articles_excluded(self) -> None:
        """記事のないissueはフィードに含まれない。"""
        issues = [
            _make_issue_with_articles(pub_date=date(2026, 3, 3)),
            _make_issue(pub_date=date(2026, 3, 2), issue_number=1656),
        ]
        gen = KanpoFeedGenerator()
        with tempfile.TemporaryDirectory() as tmpdir:
            gen.generate_fullcontents_feed(
                issues, date(2026, 3, 3), tmpdir, days=7
            )
            root = ET.parse(
                Path(tmpdir) / "feed-fullcontents.xml"
            ).getroot()
        items = root.findall(".//item")
        # Only 3/3: 1 fullcontents + 3 articles = 4
        assert len(items) == 4

    def test_empty_issues_generates_valid_feed(self) -> None:
        gen = KanpoFeedGenerator()
        with tempfile.TemporaryDirectory() as tmpdir:
            gen.generate_fullcontents_feed([], date(2026, 3, 3), tmpdir)
            root = ET.parse(
                Path(tmpdir) / "feed-fullcontents.xml"
            ).getroot()
        assert root.tag == "rss"
        items = root.findall(".//item")
        assert len(items) == 0

    def test_article_guid_uniqueness(self) -> None:
        issues = [
            _make_issue_with_articles(pub_date=date(2026, 3, 3)),
            _make_issue_with_articles(
                pub_date=date(2026, 3, 3),
                gazette_type=GazetteType.GOUGAI,
                issue_number=43,
            ),
        ]
        gen = KanpoFeedGenerator()
        with tempfile.TemporaryDirectory() as tmpdir:
            gen.generate_fullcontents_feed(
                issues, date(2026, 3, 3), tmpdir
            )
            root = ET.parse(
                Path(tmpdir) / "feed-fullcontents.xml"
            ).getroot()
        guids = [item.findtext("guid") for item in root.findall(".//item")]
        assert len(guids) == len(set(guids))

    def test_article_has_categories(self) -> None:
        issues = [_make_issue_with_articles()]
        gen = KanpoFeedGenerator()
        with tempfile.TemporaryDirectory() as tmpdir:
            gen.generate_fullcontents_feed(
                issues, date(2026, 3, 3), tmpdir
            )
            root = ET.parse(
                Path(tmpdir) / "feed-fullcontents.xml"
            ).getroot()
        # Skip fullcontents entry, check first article
        article_item = root.findall(".//item")[1]
        categories = [c.text for c in article_item.findall("category")]
        assert "本紙" in categories
        assert "その他告示" in categories
