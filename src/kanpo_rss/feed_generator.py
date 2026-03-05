"""RSS feed generator for kanpo-rss."""

from __future__ import annotations

import datetime as dt_module
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


def _atom_path(rss_path: str) -> str:
    """Derive the Atom file path from an RSS file path.

    Example: 'docs/feed.xml' -> 'docs/feed-atom.xml'
    """
    p = Path(rss_path)
    return str(p.with_name(p.stem + "-atom" + p.suffix))


class KanpoFeedGenerator:
    """Generates RSS and Atom feeds from a list of GazetteIssue objects."""

    def __init__(self, self_url: str = "") -> None:
        self._self_url = self_url

    def _build_feed(self, title_suffix: str = "") -> FeedGenerator:
        fg = FeedGenerator()
        fg.id(KANPO_URL)
        fg.title(FEED_TITLE + title_suffix)
        fg.link(href=KANPO_URL, rel="alternate")
        if self._self_url:
            fg.link(href=self._self_url, rel="self")
        fg.description(FEED_DESCRIPTION)
        fg.language(FEED_LANGUAGE)
        fg.ttl(FEED_TTL)
        fg.generator("kanpo-rss")
        fg.author({"name": "kanpo-rss"})
        fg.lastBuildDate(datetime.now(tz=JST))
        return fg

    def _add_article_entry(
        self, fg: FeedGenerator, issue: GazetteIssue, article: GazetteArticle
    ) -> None:
        entry = fg.add_entry(order="append")
        entry.title(article.title)
        entry.link(href=article.url)
        entry.guid(article.article_id, permalink=False)
        summary_text = f"{issue.title} — {article.section}"
        entry.description(summary_text)
        entry.summary(summary_text)
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
        entry.updated(pub_dt)

    def generate_fullcontents_feed(
        self,
        issues: list[GazetteIssue],
        target_date: dt_module.date,
        output_dir: str,
        days: int = 7,
    ) -> None:
        """fullcontents ベースのフィードを生成する。

        直近 days 日分の全体目次ページをアイテムとして追加し、
        各記事も個別アイテムとして追加する。
        """
        import shutil

        cutoff = target_date - dt_module.timedelta(days=days - 1)
        title_suffix = " (全体目次)"
        fg = self._build_feed(title_suffix=title_suffix)

        # 対象期間の issues を日付降順で収集
        recent_issues = [
            i for i in issues
            if i.articles and cutoff <= i.date <= target_date
        ]
        recent_issues.sort(
            key=lambda i: (
                -i.date.toordinal(),
                GAZETTE_TYPE_ORDER.get(i.gazette_type, 99),
            ),
        )

        # 日付ごとに fullcontents ページアイテム + 記事アイテムを追加
        seen_dates: set[dt_module.date] = set()
        for issue in recent_issues:
            if issue.date not in seen_dates:
                seen_dates.add(issue.date)
                date_str = issue.date.strftime("%Y%m%d")
                fc_url = f"{KANPO_URL}{date_str}/{date_str}.fullcontents.html"
                fc_entry = fg.add_entry(order="append")
                fc_entry.title(f"官報 {issue.date.isoformat()} 全体目次")
                fc_entry.link(href=fc_url)
                fc_entry.guid(f"fullcontents-{date_str}", permalink=False)
                fc_entry.description(f"{issue.date.isoformat()} の官報全体目次")
                fc_entry.summary(f"{issue.date.isoformat()} の官報全体目次")
                pub_dt = datetime(
                    issue.date.year, issue.date.month, issue.date.day,
                    8, 30, 0, tzinfo=JST,
                )
                fc_entry.pubDate(pub_dt)
                fc_entry.updated(pub_dt)

            for article in issue.articles:
                self._add_article_entry(fg, issue, article)

        # 出力
        fc_dir = Path(output_dir) / "fullcontents"
        fc_dir.mkdir(parents=True, exist_ok=True)

        date_str = target_date.strftime("%Y%m%d")
        feed_path = str(fc_dir / f"feed-{date_str}.xml")
        fg.rss_file(feed_path, pretty=True)
        atom_path = _atom_path(feed_path)
        fg.atom_file(atom_path, pretty=True)

        # 最新版として docs 直下にもコピー
        default_rss = Path(output_dir) / "feed-fullcontents.xml"
        default_atom = Path(output_dir) / "feed-fullcontents-atom.xml"
        shutil.copy2(feed_path, str(default_rss))
        shutil.copy2(atom_path, str(default_atom))

        total_articles = sum(len(i.articles) for i in recent_issues)
        logger.info(
            "Generated fullcontents feed: %s (+atom) with %d articles (%d days, %d dates)",
            feed_path, total_articles, days, len(seen_dates),
        )

