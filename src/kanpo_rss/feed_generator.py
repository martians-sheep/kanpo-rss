"""RSS feed generator for kanpo-rss."""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

from feedgen.feed import FeedGenerator

from kanpo_rss.models import GazetteIssue

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))

# Feed metadata
FEED_TITLE = "官報 RSS / Japanese Government Gazette"
FEED_DESCRIPTION = "日本国官報の新着情報RSSフィード"
FEED_LANGUAGE = "ja"
KANPO_URL = "https://www.kanpo.go.jp/"
FEED_TTL = 60  # minutes


class KanpoFeedGenerator:
    """Generates an RSS feed from a list of GazetteIssue objects."""

    def __init__(self, self_url: str = "") -> None:
        self._self_url = self_url

    def generate(
        self,
        issues: list[GazetteIssue],
        output_path: str,
        max_items: int = 100,
    ) -> None:
        """Generate feed.xml from issues.

        Issues are sorted by date descending and truncated to max_items.
        """
        sorted_issues = sorted(issues, key=lambda i: i.date, reverse=True)
        truncated = sorted_issues[:max_items]

        fg = self._build_feed()
        for issue in truncated:
            self._add_entry(fg, issue)

        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        fg.rss_file(str(output), pretty=True)
        logger.info("Generated %s with %d items", output_path, len(truncated))

    def _build_feed(self) -> FeedGenerator:
        fg = FeedGenerator()
        fg.title(FEED_TITLE)
        fg.link(href=KANPO_URL, rel="alternate")
        if self._self_url:
            fg.link(href=self._self_url, rel="self")
        fg.description(FEED_DESCRIPTION)
        fg.language(FEED_LANGUAGE)
        fg.ttl(FEED_TTL)
        fg.generator("kanpo-rss")
        fg.lastBuildDate(datetime.now(tz=JST))
        return fg

    def _add_entry(self, fg: FeedGenerator, issue: GazetteIssue) -> None:
        entry = fg.add_entry(order="append")
        entry.title(issue.title)
        entry.link(href=issue.url)
        entry.guid(issue.issue_id, permalink=False)
        entry.description(issue.gazette_type.label)
        entry.category(term=issue.gazette_type.label)

        pub_dt = datetime(
            issue.date.year,
            issue.date.month,
            issue.date.day,
            8, 30, 0,
            tzinfo=JST,
        )
        entry.pubDate(pub_dt)
