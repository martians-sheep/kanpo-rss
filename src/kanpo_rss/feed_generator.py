"""RSS feed generator for kanpo-rss."""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

from feedgen.feed import FeedGenerator

from kanpo_rss.models import GAZETTE_TYPE_ORDER, GazetteArticle, GazetteIssue

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
        title_suffix: str = "",
    ) -> None:
        """Generate feed.xml from issues.

        Issues are sorted by date descending and truncated to max_items.
        If max_items is 0, all issues are included.
        """
        sorted_issues = sorted(issues, key=lambda i: i.date, reverse=True)
        truncated = sorted_issues[:max_items] if max_items > 0 else sorted_issues

        fg = self._build_feed(title_suffix=title_suffix)
        for issue in truncated:
            self._add_entry(fg, issue)

        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        fg.rss_file(str(output), pretty=True)
        logger.info("Generated %s with %d items", output_path, len(truncated))

    def _build_feed(self, title_suffix: str = "") -> FeedGenerator:
        fg = FeedGenerator()
        fg.title(FEED_TITLE + title_suffix)
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

    def generate_article_feed(
        self,
        issues: list[GazetteIssue],
        output_path: str,
        max_items: int = 500,
        title_suffix: str = " (記事)",
    ) -> None:
        """Generate article-level feed from issues with articles.

        All articles from all issues are flattened, sorted by date descending,
        and written as individual RSS entries.
        """
        # issue_id → issue のマップ（日付・種別の参照用）
        issue_map: dict[str, GazetteIssue] = {i.issue_id: i for i in issues}

        # 全記事をフラット化し、号内の出現順を保持してソート
        # (issue, article, 号内の出現位置)
        article_entries: list[tuple[GazetteIssue, GazetteArticle, int]] = []
        for issue in issues:
            for pos, article in enumerate(issue.articles):
                article_entries.append((issue, article, pos))
        article_entries.sort(
            key=lambda x: (
                -x[0].date.toordinal(),  # 日付降順
                GAZETTE_TYPE_ORDER.get(x[0].gazette_type, 99),  # 種別順
                x[2],  # 号内の出現順
            ),
        )

        truncated = (
            article_entries[:max_items]
            if max_items > 0
            else article_entries
        )

        fg = self._build_feed(title_suffix=title_suffix)
        for issue, article, _pos in truncated:
            self._add_article_entry(fg, issue, article)

        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        fg.rss_file(str(output), pretty=True)
        logger.info(
            "Generated %s with %d article items", output_path, len(truncated)
        )

    def _add_article_entry(
        self, fg: FeedGenerator, issue: GazetteIssue, article: GazetteArticle
    ) -> None:
        entry = fg.add_entry(order="append")
        entry.title(article.title)
        entry.link(href=article.url)
        entry.guid(article.article_id, permalink=False)
        entry.description(
            f"{issue.title} — {article.section}"
        )
        entry.category(term=issue.gazette_type.label)
        if article.section:
            entry.category(term=article.section)

        pub_dt = datetime(
            issue.date.year,
            issue.date.month,
            issue.date.day,
            8, 30, 0,
            tzinfo=JST,
        )
        entry.pubDate(pub_dt)
