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


def _generate_and_parse(
    issues: list[GazetteIssue], max_items: int = 100
) -> ET.Element:
    gen = KanpoFeedGenerator()
    with tempfile.TemporaryDirectory() as tmpdir:
        output = str(Path(tmpdir) / "feed.xml")
        gen.generate(issues, output, max_items=max_items)
        tree = ET.parse(output)
    return tree.getroot()


def _generate_and_parse_atom(
    issues: list[GazetteIssue], max_items: int = 100
) -> ET.Element:
    gen = KanpoFeedGenerator()
    with tempfile.TemporaryDirectory() as tmpdir:
        output = str(Path(tmpdir) / "feed.xml")
        gen.generate(issues, output, max_items=max_items)
        atom_file = str(Path(tmpdir) / "feed-atom.xml")
        tree = ET.parse(atom_file)
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

    def test_article_order_within_issue(self) -> None:
        """同一号内の記事はページ出現順を維持する。"""
        issues = [_make_issue_with_articles()]
        gen = KanpoFeedGenerator()
        with tempfile.TemporaryDirectory() as tmpdir:
            output = str(Path(tmpdir) / "feed-articles.xml")
            gen.generate_article_feed(issues, output)
            root = ET.parse(output).getroot()
        titles = [item.findtext("title") for item in root.findall(".//item")]
        assert titles == ["テスト記事A", "テスト記事B", "国会事項"]

    def test_article_order_across_types_same_date(self) -> None:
        """同日の記事は本紙→号外→政府調達の順で並ぶ。"""
        d = date(2026, 3, 3)
        # 入力を逆順（政府調達→号外→本紙）にしても正しい順序になること
        issues = [
            _make_issue_with_articles(
                pub_date=d,
                gazette_type=GazetteType.SEIFU_CHOUTATSU,
                issue_number=39,
            ),
            _make_issue_with_articles(
                pub_date=d,
                gazette_type=GazetteType.GOUGAI,
                issue_number=43,
            ),
            _make_issue_with_articles(
                pub_date=d,
                gazette_type=GazetteType.HONSHI,
                issue_number=1657,
            ),
        ]
        gen = KanpoFeedGenerator()
        with tempfile.TemporaryDirectory() as tmpdir:
            output = str(Path(tmpdir) / "feed-articles.xml")
            gen.generate_article_feed(issues, output)
            root = ET.parse(output).getroot()
        items = root.findall(".//item")
        guids = [item.findtext("guid") or "" for item in items]
        # 本紙の記事が最初、政府調達の記事が最後
        assert "h01657" in guids[0]
        assert "c00039" in guids[-1]


class TestArticleFeedsByDate:
    def test_generates_per_date_feeds(self) -> None:
        issues = [
            _make_issue_with_articles(pub_date=date(2026, 3, 3)),
            _make_issue_with_articles(
                pub_date=date(2026, 3, 2), issue_number=1656
            ),
        ]
        gen = KanpoFeedGenerator()
        with tempfile.TemporaryDirectory() as tmpdir:
            dates = gen.generate_article_feeds_by_date(issues, tmpdir)
            assert len(dates) == 2
            assert (Path(tmpdir) / "articles" / "feed-20260303.xml").exists()
            assert (Path(tmpdir) / "articles" / "feed-20260302.xml").exists()

    def test_latest_date_copied_to_feed_articles(self) -> None:
        issues = [
            _make_issue_with_articles(pub_date=date(2026, 3, 3)),
            _make_issue_with_articles(
                pub_date=date(2026, 3, 2), issue_number=1656
            ),
        ]
        gen = KanpoFeedGenerator()
        with tempfile.TemporaryDirectory() as tmpdir:
            gen.generate_article_feeds_by_date(issues, tmpdir)
            default_feed = Path(tmpdir) / "feed-articles.xml"
            assert default_feed.exists()
            root = ET.parse(default_feed).getroot()
            title = root.findtext(".//channel/title") or ""
            assert "2026-03-03" in title

    def test_per_date_feed_contains_only_that_date(self) -> None:
        issues = [
            _make_issue_with_articles(pub_date=date(2026, 3, 3)),
            _make_issue_with_articles(
                pub_date=date(2026, 3, 2), issue_number=1656
            ),
        ]
        gen = KanpoFeedGenerator()
        with tempfile.TemporaryDirectory() as tmpdir:
            gen.generate_article_feeds_by_date(issues, tmpdir)
            root = ET.parse(
                Path(tmpdir) / "articles" / "feed-20260302.xml"
            ).getroot()
            items = root.findall(".//item")
            assert len(items) == 3  # _make_issue_with_articles creates 3
            for item in items:
                assert "h01656" in (item.findtext("guid") or "")

    def test_skips_issues_without_articles(self) -> None:
        issues = [
            _make_issue_with_articles(pub_date=date(2026, 3, 3)),
            _make_issue(pub_date=date(2026, 3, 2), issue_number=1656),
        ]
        gen = KanpoFeedGenerator()
        with tempfile.TemporaryDirectory() as tmpdir:
            dates = gen.generate_article_feeds_by_date(issues, tmpdir)
            assert len(dates) == 1
            assert dates[0] == date(2026, 3, 3)

    def test_generates_index_html(self) -> None:
        dates = [date(2026, 3, 3), date(2026, 3, 2)]
        with tempfile.TemporaryDirectory() as tmpdir:
            KanpoFeedGenerator.generate_article_index(dates, tmpdir)
            index = Path(tmpdir) / "articles" / "index.html"
            assert index.exists()
            content = index.read_text()
            assert "2026-03-03" in content
            assert "2026-03-02" in content
            assert "feed-20260303.xml" in content

    def test_empty_issues_no_crash(self) -> None:
        gen = KanpoFeedGenerator()
        with tempfile.TemporaryDirectory() as tmpdir:
            dates = gen.generate_article_feeds_by_date([], tmpdir)
            assert dates == []
            assert not (Path(tmpdir) / "feed-articles.xml").exists()


# --- Atom feed tests ---


class TestAtomPath:
    def test_basic(self) -> None:
        assert _atom_path("docs/feed.xml") == "docs/feed-atom.xml"

    def test_archive(self) -> None:
        assert _atom_path("docs/feed-archive.xml") == "docs/feed-archive-atom.xml"

    def test_nested(self) -> None:
        assert _atom_path("a/b/c.xml") == "a/b/c-atom.xml"


class TestAtomFeedGenerator:
    def test_generates_valid_atom(self) -> None:
        root = _generate_and_parse_atom([_make_issue()])
        assert root.tag == f"{{{ATOM_NS}}}feed"

    def test_feed_metadata(self) -> None:
        root = _generate_and_parse_atom([_make_issue()])
        assert "官報" in (root.findtext(f"{{{ATOM_NS}}}title") or "")
        assert root.findtext(f"{{{ATOM_NS}}}id") is not None
        assert root.findtext(f"{{{ATOM_NS}}}updated") is not None
        author = root.find(f"{{{ATOM_NS}}}author")
        assert author is not None
        assert author.findtext(f"{{{ATOM_NS}}}name") == "kanpo-rss"

    def test_entry_structure(self) -> None:
        root = _generate_and_parse_atom([_make_issue()])
        entries = root.findall(f"{{{ATOM_NS}}}entry")
        assert len(entries) == 1
        entry = entries[0]
        assert entry.findtext(f"{{{ATOM_NS}}}title") is not None
        assert entry.find(f"{{{ATOM_NS}}}link") is not None
        assert entry.findtext(f"{{{ATOM_NS}}}id") is not None
        assert entry.findtext(f"{{{ATOM_NS}}}updated") is not None
        assert entry.findtext(f"{{{ATOM_NS}}}summary") is not None

    def test_entry_id_content(self) -> None:
        root = _generate_and_parse_atom([_make_issue()])
        entry_id = root.findtext(f"{{{ATOM_NS}}}entry/{{{ATOM_NS}}}id")
        assert entry_id is not None
        assert "20260303h01657" in entry_id

    def test_entry_ordering(self) -> None:
        issues = [
            _make_issue(pub_date=date(2026, 3, 1), issue_number=1655),
            _make_issue(pub_date=date(2026, 3, 3), issue_number=1657),
            _make_issue(pub_date=date(2026, 3, 2), issue_number=1656),
        ]
        root = _generate_and_parse_atom(issues)
        entries = root.findall(f"{{{ATOM_NS}}}entry")
        titles = [e.findtext(f"{{{ATOM_NS}}}title") or "" for e in entries]
        assert "2026-03-03" in titles[0]
        assert "2026-03-02" in titles[1]
        assert "2026-03-01" in titles[2]

    def test_max_items_truncation(self) -> None:
        issues = [
            _make_issue(pub_date=date(2026, 1, i + 6), issue_number=1600 + i)
            for i in range(20)
        ]
        root = _generate_and_parse_atom(issues, max_items=10)
        entries = root.findall(f"{{{ATOM_NS}}}entry")
        assert len(entries) == 10

    def test_empty_issues_generates_valid_atom(self) -> None:
        root = _generate_and_parse_atom([])
        assert root.tag == f"{{{ATOM_NS}}}feed"
        entries = root.findall(f"{{{ATOM_NS}}}entry")
        assert len(entries) == 0

    def test_atom_file_created_alongside_rss(self) -> None:
        gen = KanpoFeedGenerator()
        with tempfile.TemporaryDirectory() as tmpdir:
            output = str(Path(tmpdir) / "feed.xml")
            gen.generate([_make_issue()], output)
            assert Path(tmpdir, "feed.xml").exists()
            assert Path(tmpdir, "feed-atom.xml").exists()

    def test_atom_file_creates_parent_dirs(self) -> None:
        gen = KanpoFeedGenerator()
        with tempfile.TemporaryDirectory() as tmpdir:
            output = str(Path(tmpdir) / "nested" / "dir" / "feed.xml")
            gen.generate([_make_issue()], output)
            assert Path(tmpdir, "nested", "dir", "feed-atom.xml").exists()


class TestAtomArticleFeedGenerator:
    def test_generates_valid_atom(self) -> None:
        issues = [_make_issue_with_articles()]
        gen = KanpoFeedGenerator()
        with tempfile.TemporaryDirectory() as tmpdir:
            output = str(Path(tmpdir) / "feed-articles.xml")
            gen.generate_article_feed(issues, output)
            atom_file = str(Path(tmpdir) / "feed-articles-atom.xml")
            root = ET.parse(atom_file).getroot()
        assert root.tag == f"{{{ATOM_NS}}}feed"

    def test_article_count(self) -> None:
        issues = [_make_issue_with_articles()]
        gen = KanpoFeedGenerator()
        with tempfile.TemporaryDirectory() as tmpdir:
            output = str(Path(tmpdir) / "feed-articles.xml")
            gen.generate_article_feed(issues, output)
            atom_file = str(Path(tmpdir) / "feed-articles-atom.xml")
            root = ET.parse(atom_file).getroot()
        entries = root.findall(f"{{{ATOM_NS}}}entry")
        assert len(entries) == 3

    def test_article_id_uniqueness(self) -> None:
        issues = [_make_issue_with_articles()]
        gen = KanpoFeedGenerator()
        with tempfile.TemporaryDirectory() as tmpdir:
            output = str(Path(tmpdir) / "feed-articles.xml")
            gen.generate_article_feed(issues, output)
            atom_file = str(Path(tmpdir) / "feed-articles-atom.xml")
            root = ET.parse(atom_file).getroot()
        ids = [e.findtext(f"{{{ATOM_NS}}}id") for e in root.findall(f"{{{ATOM_NS}}}entry")]
        assert len(ids) == len(set(ids))


class TestAtomArticleFeedsByDate:
    def test_generates_per_date_atom_feeds(self) -> None:
        issues = [
            _make_issue_with_articles(pub_date=date(2026, 3, 3)),
            _make_issue_with_articles(pub_date=date(2026, 3, 2), issue_number=1656),
        ]
        gen = KanpoFeedGenerator()
        with tempfile.TemporaryDirectory() as tmpdir:
            gen.generate_article_feeds_by_date(issues, tmpdir)
            assert (Path(tmpdir) / "articles" / "feed-20260303-atom.xml").exists()
            assert (Path(tmpdir) / "articles" / "feed-20260302-atom.xml").exists()

    def test_latest_atom_copied_to_feed_articles_atom(self) -> None:
        issues = [
            _make_issue_with_articles(pub_date=date(2026, 3, 3)),
            _make_issue_with_articles(pub_date=date(2026, 3, 2), issue_number=1656),
        ]
        gen = KanpoFeedGenerator()
        with tempfile.TemporaryDirectory() as tmpdir:
            gen.generate_article_feeds_by_date(issues, tmpdir)
            default_atom = Path(tmpdir) / "feed-articles-atom.xml"
            assert default_atom.exists()
            root = ET.parse(default_atom).getroot()
            assert root.tag == f"{{{ATOM_NS}}}feed"
            title = root.findtext(f"{{{ATOM_NS}}}title") or ""
            assert "2026-03-03" in title

    def test_index_html_has_atom_links(self) -> None:
        dates = [date(2026, 3, 3), date(2026, 3, 2)]
        with tempfile.TemporaryDirectory() as tmpdir:
            KanpoFeedGenerator.generate_article_index(dates, tmpdir)
            content = (Path(tmpdir) / "articles" / "index.html").read_text()
            assert "feed-20260303-atom.xml" in content
            assert "feed-20260302-atom.xml" in content
            assert "Atom" in content
