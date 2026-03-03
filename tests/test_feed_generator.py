"""Tests for kanpo_rss.feed_generator."""

import tempfile
from datetime import date
from pathlib import Path
from xml.etree import ElementTree as ET

from kanpo_rss.feed_generator import KanpoFeedGenerator
from kanpo_rss.models import GazetteArticle, GazetteIssue, GazetteType


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


def _generate_and_parse(
    issues: list[GazetteIssue], max_items: int = 100
) -> ET.Element:
    gen = KanpoFeedGenerator()
    with tempfile.TemporaryDirectory() as tmpdir:
        output = str(Path(tmpdir) / "feed.xml")
        gen.generate(issues, output, max_items=max_items)
        tree = ET.parse(output)
    return tree.getroot()


class TestFeedGenerator:
    def test_generates_valid_rss(self) -> None:
        issues = [_make_issue()]
        root = _generate_and_parse(issues)
        assert root.tag == "rss"
        assert root.attrib["version"] == "2.0"

    def test_feed_metadata(self) -> None:
        root = _generate_and_parse([_make_issue()])
        channel = root.find("channel")
        assert channel is not None
        assert "官報" in (channel.findtext("title") or "")
        assert channel.findtext("language") == "ja"
        assert channel.findtext("description") is not None

    def test_item_structure(self) -> None:
        root = _generate_and_parse([_make_issue()])
        items = root.findall(".//item")
        assert len(items) == 1
        item = items[0]
        assert item.findtext("title") is not None
        assert item.findtext("link") is not None
        assert item.find("guid") is not None
        assert item.findtext("pubDate") is not None
        assert item.findtext("description") is not None

    def test_item_guid_content(self) -> None:
        root = _generate_and_parse([_make_issue()])
        guid = root.find(".//item/guid")
        assert guid is not None
        assert guid.text == "20260303h01657"
        assert guid.attrib.get("isPermaLink") == "false"

    def test_item_ordering(self) -> None:
        issues = [
            _make_issue(pub_date=date(2026, 3, 1), issue_number=1655),
            _make_issue(pub_date=date(2026, 3, 3), issue_number=1657),
            _make_issue(pub_date=date(2026, 3, 2), issue_number=1656),
        ]
        root = _generate_and_parse(issues)
        items = root.findall(".//item")
        titles = [item.findtext("title") or "" for item in items]
        assert "2026-03-03" in titles[0]
        assert "2026-03-02" in titles[1]
        assert "2026-03-01" in titles[2]

    def test_max_items_truncation(self) -> None:
        issues = [
            _make_issue(pub_date=date(2026, 1, i + 6), issue_number=1600 + i)
            for i in range(20)
        ]
        root = _generate_and_parse(issues, max_items=10)
        items = root.findall(".//item")
        assert len(items) == 10

    def test_guid_uniqueness(self) -> None:
        issues = [
            _make_issue(pub_date=date(2026, 3, 3), gazette_type=GazetteType.HONSHI, issue_number=1657),
            _make_issue(pub_date=date(2026, 3, 3), gazette_type=GazetteType.GOUGAI, issue_number=43),
            _make_issue(pub_date=date(2026, 3, 3), gazette_type=GazetteType.SEIFU_CHOUTATSU, issue_number=39),
        ]
        root = _generate_and_parse(issues)
        guids = [item.findtext("guid") for item in root.findall(".//item")]
        assert len(guids) == len(set(guids))

    def test_empty_issues_generates_valid_feed(self) -> None:
        root = _generate_and_parse([])
        assert root.tag == "rss"
        items = root.findall(".//item")
        assert len(items) == 0

    def test_output_creates_parent_dirs(self) -> None:
        gen = KanpoFeedGenerator()
        with tempfile.TemporaryDirectory() as tmpdir:
            output = str(Path(tmpdir) / "nested" / "dir" / "feed.xml")
            gen.generate([_make_issue()], output)
            assert Path(output).exists()

    def test_pubdate_contains_jst(self) -> None:
        root = _generate_and_parse([_make_issue()])
        pubdate = root.findtext(".//item/pubDate") or ""
        assert "+0900" in pubdate

    def test_generate_with_title_suffix(self) -> None:
        gen = KanpoFeedGenerator()
        with tempfile.TemporaryDirectory() as tmpdir:
            output = str(Path(tmpdir) / "feed-archive.xml")
            gen.generate([_make_issue()], output, title_suffix=" (アーカイブ)")
            tree = ET.parse(output)
            root = tree.getroot()
        title = root.findtext(".//channel/title") or ""
        assert "アーカイブ" in title

    def test_generate_max_items_zero_outputs_all(self) -> None:
        issues = [
            _make_issue(pub_date=date(2026, 1, i + 6), issue_number=1600 + i)
            for i in range(20)
        ]
        gen = KanpoFeedGenerator()
        with tempfile.TemporaryDirectory() as tmpdir:
            output = str(Path(tmpdir) / "feed-archive.xml")
            gen.generate(issues, output, max_items=0)
            tree = ET.parse(output)
            root = tree.getroot()
        items = root.findall(".//item")
        assert len(items) == 20


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


class TestArticleFeedGenerator:
    def test_generates_valid_rss(self) -> None:
        issues = [_make_issue_with_articles()]
        gen = KanpoFeedGenerator()
        with tempfile.TemporaryDirectory() as tmpdir:
            output = str(Path(tmpdir) / "feed-articles.xml")
            gen.generate_article_feed(issues, output)
            root = ET.parse(output).getroot()
        assert root.tag == "rss"
        assert root.attrib["version"] == "2.0"

    def test_article_count(self) -> None:
        issues = [_make_issue_with_articles()]
        gen = KanpoFeedGenerator()
        with tempfile.TemporaryDirectory() as tmpdir:
            output = str(Path(tmpdir) / "feed-articles.xml")
            gen.generate_article_feed(issues, output)
            root = ET.parse(output).getroot()
        items = root.findall(".//item")
        assert len(items) == 3

    def test_article_guid_uniqueness(self) -> None:
        issues = [_make_issue_with_articles()]
        gen = KanpoFeedGenerator()
        with tempfile.TemporaryDirectory() as tmpdir:
            output = str(Path(tmpdir) / "feed-articles.xml")
            gen.generate_article_feed(issues, output)
            root = ET.parse(output).getroot()
        guids = [item.findtext("guid") for item in root.findall(".//item")]
        assert len(guids) == len(set(guids))

    def test_article_has_categories(self) -> None:
        issues = [_make_issue_with_articles()]
        gen = KanpoFeedGenerator()
        with tempfile.TemporaryDirectory() as tmpdir:
            output = str(Path(tmpdir) / "feed-articles.xml")
            gen.generate_article_feed(issues, output)
            root = ET.parse(output).getroot()
        first_item = root.findall(".//item")[0]
        categories = [c.text for c in first_item.findall("category")]
        assert "本紙" in categories
        assert "その他告示" in categories

    def test_empty_articles_generates_valid_feed(self) -> None:
        issues = [_make_issue()]  # no articles
        gen = KanpoFeedGenerator()
        with tempfile.TemporaryDirectory() as tmpdir:
            output = str(Path(tmpdir) / "feed-articles.xml")
            gen.generate_article_feed(issues, output)
            root = ET.parse(output).getroot()
        assert root.tag == "rss"
        items = root.findall(".//item")
        assert len(items) == 0

    def test_title_suffix(self) -> None:
        issues = [_make_issue_with_articles()]
        gen = KanpoFeedGenerator()
        with tempfile.TemporaryDirectory() as tmpdir:
            output = str(Path(tmpdir) / "feed-articles.xml")
            gen.generate_article_feed(issues, output)
            root = ET.parse(output).getroot()
        title = root.findtext(".//channel/title") or ""
        assert "記事" in title
