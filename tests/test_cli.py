"""Tests for kanpo_rss.cli."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch
from xml.etree import ElementTree as ET

import pytest

from kanpo_rss.cli import main, parse_args


class TestParseArgs:
    def test_defaults(self) -> None:
        args = parse_args([])
        assert args.output_dir == "docs"
        assert args.max_items == 100
        assert args.self_url == ""
        assert args.data_dir == "data"
        assert args.verbose is False

    def test_custom_args(self) -> None:
        args = parse_args([
            "--output-dir", "out",
            "--max-items", "50",
            "--self-url", "https://example.com/feed.xml",
            "--data-dir", "mydata",
            "-v",
        ])
        assert args.output_dir == "out"
        assert args.max_items == 50
        assert args.self_url == "https://example.com/feed.xml"
        assert args.data_dir == "mydata"
        assert args.verbose is True

    def test_data_dir_empty_disables_storage(self) -> None:
        args = parse_args(["--data-dir", ""])
        assert args.data_dir == ""


class TestMain:
    def test_full_pipeline_with_fixture(self, top_page_html: str) -> None:
        """Mock the scraper to return fixture HTML, verify feed.xml is created."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch(
                "kanpo_rss.cli.KanpoScraper"
            ) as mock_scraper_cls:
                mock_scraper = mock_scraper_cls.return_value
                mock_scraper.fetch_top_page.return_value = top_page_html
                mock_scraper.fetch_issue_page.return_value = "<html><body></body></html>"

                data_dir = str(Path(tmpdir) / "data")
                result = main([
                    "--output-dir", tmpdir,
                    "--max-items", "10",
                    "--data-dir", data_dir,
                ])

            assert result == 0
            feed_path = Path(tmpdir) / "feed.xml"
            assert feed_path.exists()

            tree = ET.parse(feed_path)
            root = tree.getroot()
            assert root.tag == "rss"
            items = root.findall(".//item")
            assert 0 < len(items) <= 10

            # Verify data file was created
            data_path = Path(data_dir) / "issues.json"
            assert data_path.exists()
            data = json.loads(data_path.read_text())
            assert data["version"] == 1
            assert len(data["issues"]) > 0

    def test_pipeline_with_storage_accumulation(self, top_page_html: str) -> None:
        """Run pipeline twice and verify data accumulates."""
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = str(Path(tmpdir) / "data")

            # First run
            with patch(
                "kanpo_rss.cli.KanpoScraper"
            ) as mock_scraper_cls:
                mock_scraper = mock_scraper_cls.return_value
                mock_scraper.fetch_top_page.return_value = top_page_html
                mock_scraper.fetch_issue_page.return_value = "<html><body></body></html>"
                result = main([
                    "--output-dir", tmpdir,
                    "--data-dir", data_dir,
                ])
            assert result == 0

            data_path = Path(data_dir) / "issues.json"
            first_run_data = json.loads(data_path.read_text())
            first_count = len(first_run_data["issues"])

            # Second run (same data — count should stay the same)
            with patch(
                "kanpo_rss.cli.KanpoScraper"
            ) as mock_scraper_cls:
                mock_scraper = mock_scraper_cls.return_value
                mock_scraper.fetch_top_page.return_value = top_page_html
                mock_scraper.fetch_issue_page.return_value = "<html><body></body></html>"
                result = main([
                    "--output-dir", tmpdir,
                    "--data-dir", data_dir,
                ])
            assert result == 0

            second_run_data = json.loads(data_path.read_text())
            assert len(second_run_data["issues"]) == first_count

    def test_pipeline_without_data_dir(self, top_page_html: str) -> None:
        """--data-dir '' disables accumulation (no data file created)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch(
                "kanpo_rss.cli.KanpoScraper"
            ) as mock_scraper_cls:
                mock_scraper = mock_scraper_cls.return_value
                mock_scraper.fetch_top_page.return_value = top_page_html
                mock_scraper.fetch_issue_page.return_value = "<html><body></body></html>"

                result = main([
                    "--output-dir", tmpdir,
                    "--max-items", "10",
                    "--data-dir", "",
                ])

            assert result == 0
            feed_path = Path(tmpdir) / "feed.xml"
            assert feed_path.exists()

            # No data directory should have been created
            assert not (Path(tmpdir) / "data").exists()

    def test_pipeline_generates_archive_feed(self, top_page_html: str) -> None:
        """With storage enabled, feed-archive.xml is generated with all items."""
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = str(Path(tmpdir) / "data")
            with patch(
                "kanpo_rss.cli.KanpoScraper"
            ) as mock_scraper_cls:
                mock_scraper = mock_scraper_cls.return_value
                mock_scraper.fetch_top_page.return_value = top_page_html
                mock_scraper.fetch_issue_page.return_value = "<html><body></body></html>"

                result = main([
                    "--output-dir", tmpdir,
                    "--max-items", "5",
                    "--data-dir", data_dir,
                ])

            assert result == 0

            # Regular feed should be truncated
            feed_path = Path(tmpdir) / "feed.xml"
            assert feed_path.exists()
            feed_items = ET.parse(feed_path).getroot().findall(".//item")
            assert len(feed_items) == 5

            # Archive feed should contain all items
            archive_path = Path(tmpdir) / "feed-archive.xml"
            assert archive_path.exists()
            archive_root = ET.parse(archive_path).getroot()
            archive_items = archive_root.findall(".//item")
            assert len(archive_items) > 5
            title = archive_root.findtext(".//channel/title") or ""
            assert "アーカイブ" in title

    def test_pipeline_copies_issues_json(self, top_page_html: str) -> None:
        """With storage enabled, issues.json is copied to output dir."""
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = str(Path(tmpdir) / "data")
            with patch(
                "kanpo_rss.cli.KanpoScraper"
            ) as mock_scraper_cls:
                mock_scraper = mock_scraper_cls.return_value
                mock_scraper.fetch_top_page.return_value = top_page_html
                mock_scraper.fetch_issue_page.return_value = "<html><body></body></html>"

                result = main([
                    "--output-dir", tmpdir,
                    "--data-dir", data_dir,
                ])

            assert result == 0

            public_json = Path(tmpdir) / "issues.json"
            assert public_json.exists()
            data = json.loads(public_json.read_text())
            assert data["version"] == 1
            assert len(data["issues"]) > 0

    def test_pipeline_no_archive_without_data_dir(self, top_page_html: str) -> None:
        """--data-dir '' skips archive feed and issues.json copy."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch(
                "kanpo_rss.cli.KanpoScraper"
            ) as mock_scraper_cls:
                mock_scraper = mock_scraper_cls.return_value
                mock_scraper.fetch_top_page.return_value = top_page_html
                mock_scraper.fetch_issue_page.return_value = "<html><body></body></html>"

                result = main([
                    "--output-dir", tmpdir,
                    "--data-dir", "",
                ])

            assert result == 0
            assert not (Path(tmpdir) / "feed-archive.xml").exists()
            assert not (Path(tmpdir) / "issues.json").exists()

    def test_pipeline_generates_article_feed(
        self, top_page_html: str, issue_page_honshi_html: str
    ) -> None:
        """Article feed is generated when issue pages return content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch(
                "kanpo_rss.cli.KanpoScraper"
            ) as mock_scraper_cls:
                mock_scraper = mock_scraper_cls.return_value
                mock_scraper.fetch_top_page.return_value = top_page_html
                mock_scraper.fetch_issue_page.return_value = issue_page_honshi_html

                result = main([
                    "--output-dir", tmpdir,
                    "--data-dir", "",
                ])

            assert result == 0
            articles_path = Path(tmpdir) / "feed-articles.xml"
            assert articles_path.exists()
            root = ET.parse(articles_path).getroot()
            items = root.findall(".//item")
            assert len(items) > 0
            # Check article has category tags
            first_item = items[0]
            categories = first_item.findall("category")
            assert len(categories) >= 1

    def test_no_articles_flag_skips_article_feed(self, top_page_html: str) -> None:
        """--no-articles skips article fetching and feed generation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch(
                "kanpo_rss.cli.KanpoScraper"
            ) as mock_scraper_cls:
                mock_scraper = mock_scraper_cls.return_value
                mock_scraper.fetch_top_page.return_value = top_page_html

                result = main([
                    "--output-dir", tmpdir,
                    "--data-dir", "",
                    "--no-articles",
                ])

            assert result == 0
            assert (Path(tmpdir) / "feed.xml").exists()
            assert not (Path(tmpdir) / "feed-articles.xml").exists()
            # fetch_issue_page should not be called
            mock_scraper.fetch_issue_page.assert_not_called()

    def test_returns_1_on_fetch_failure(self) -> None:
        with patch(
            "kanpo_rss.cli.KanpoScraper"
        ) as mock_scraper_cls:
            mock_scraper = mock_scraper_cls.return_value
            mock_scraper.fetch_top_page.side_effect = ConnectionError("fail")

            result = main(["--output-dir", "/tmp/test", "--data-dir", ""])

        assert result == 1

    def test_returns_1_on_empty_page(self) -> None:
        with patch(
            "kanpo_rss.cli.KanpoScraper"
        ) as mock_scraper_cls:
            mock_scraper = mock_scraper_cls.return_value
            mock_scraper.fetch_top_page.return_value = "<html></html>"

            result = main(["--output-dir", "/tmp/test", "--data-dir", ""])

        assert result == 1
