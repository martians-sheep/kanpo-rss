"""CLI entry point for kanpo-rss."""

from __future__ import annotations

import argparse
import logging
import shutil
import sys
from pathlib import Path

from kanpo_rss.feed_generator import KanpoFeedGenerator
from kanpo_rss.parser import KanpoParser
from kanpo_rss.scraper import KanpoScraper
from kanpo_rss.storage import IssueStorage

logger = logging.getLogger(__name__)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="kanpo-rss",
        description="Generate RSS feed from kanpo.go.jp",
    )
    parser.add_argument(
        "--output-dir",
        default="docs",
        help="Output directory for feed.xml (default: docs)",
    )
    parser.add_argument(
        "--max-items",
        type=int,
        default=100,
        help="Maximum number of RSS items (default: 100)",
    )
    parser.add_argument(
        "--self-url",
        default="",
        help="Self URL for the feed (rel=self link)",
    )
    parser.add_argument(
        "--data-dir",
        default="data",
        help="Directory for accumulated data (default: data). Empty string disables accumulation.",
    )
    parser.add_argument(
        "--no-articles",
        action="store_true",
        help="Skip fetching article-level data from issue pages",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    scraper = KanpoScraper()
    parser = KanpoParser()
    generator = KanpoFeedGenerator(self_url=args.self_url)
    storage = IssueStorage()

    use_storage = bool(args.data_dir)
    data_path = str(Path(args.data_dir) / "issues.json") if use_storage else ""

    # Load existing accumulated data
    existing_issues = []
    if use_storage:
        existing_issues = storage.load(data_path)
        logger.info("Loaded %d existing issues from %s", len(existing_issues), data_path)

    # Fetch and parse top page
    logger.info("Fetching kanpo.go.jp top page...")
    try:
        top_html = scraper.fetch_top_page()
    except Exception:
        logger.exception("Failed to fetch top page")
        return 1

    new_issues = parser.parse_top_page(top_html)
    if not new_issues and not existing_issues:
        logger.error("No issues found on top page and no existing data")
        return 1

    logger.info(
        "Found %d issues across %d dates from top page",
        len(new_issues),
        len({i.date for i in new_issues}),
    )

    # Merge and save
    if use_storage:
        issues = storage.merge(existing_issues, new_issues)
    else:
        issues = new_issues

    # Fetch article-level data from issue pages
    if not args.no_articles:
        issues = _fetch_articles(scraper, parser, issues)

    # Save after article enrichment
    if use_storage:
        storage.save(data_path, issues)

    # Generate feed
    output_path = str(Path(args.output_dir) / "feed.xml")
    generator.generate(issues, output_path, max_items=args.max_items)

    # Generate per-date article feeds + index
    if not args.no_articles:
        dates = generator.generate_article_feeds_by_date(issues, args.output_dir)
        if dates:
            generator.generate_article_index(dates, args.output_dir)

    # Generate archive feed and copy issues.json for public access
    if use_storage:
        archive_path = str(Path(args.output_dir) / "feed-archive.xml")
        generator.generate(
            issues, archive_path, max_items=0, title_suffix=" (アーカイブ)",
        )
        logger.info("Generated archive feed: %s (+atom) (%d items)", archive_path, len(issues))

        public_json = Path(args.output_dir) / "issues.json"
        public_json.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(data_path, str(public_json))
        logger.info("Copied %s to %s", data_path, public_json)

    logger.info("Done! Feed written to %s", output_path)

    return 0


def _fetch_articles(
    scraper: KanpoScraper,
    parser: KanpoParser,
    issues: list,
) -> list:
    """記事未取得の号について、目次ページから記事を取得する。"""
    from dataclasses import replace

    enriched = []
    for issue in issues:
        if issue.articles:
            enriched.append(issue)
            continue

        try:
            html = scraper.fetch_issue_page(issue.url)
        except Exception:
            logger.warning(
                "Failed to fetch issue page: %s", issue.url
            )
            enriched.append(issue)
            continue

        articles = parser.parse_issue_page(html, issue)
        enriched.append(replace(issue, articles=articles))

    total = sum(len(i.articles) for i in enriched)
    logger.info("Fetched articles: %d total from %d issues", total, len(enriched))
    return enriched


if __name__ == "__main__":
    sys.exit(main())
