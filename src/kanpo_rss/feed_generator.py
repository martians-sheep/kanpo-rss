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
        entry.description(_build_issue_description(issue))
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

    def generate_article_feeds_by_date(
        self,
        issues: list[GazetteIssue],
        output_dir: str,
    ) -> list[dt_module.date]:
        """日付ごとに個別の記事フィードファイルを生成する。

        output_dir/articles/feed-YYYYMMDD.xml を日付ごとに生成し、
        output_dir/feed-articles.xml には最新日のフィードをコピーする。
        生成された日付のリスト（降順）を返す。
        """
        import shutil

        # 日付ごとにissuesをグループ化
        date_issues: dict[dt_module.date, list[GazetteIssue]] = {}
        for issue in issues:
            if issue.articles:
                date_issues.setdefault(issue.date, []).append(issue)

        sorted_dates = sorted(date_issues.keys(), reverse=True)

        articles_dir = Path(output_dir) / "articles"
        articles_dir.mkdir(parents=True, exist_ok=True)

        for pub_date in sorted_dates:
            date_str = pub_date.strftime("%Y%m%d")
            feed_path = str(articles_dir / f"feed-{date_str}.xml")
            title_suffix = f" (記事 {pub_date.isoformat()})"
            self.generate_article_feed(
                date_issues[pub_date], feed_path,
                max_items=0, title_suffix=title_suffix,
            )

        # 最新日のフィードを feed-articles.xml としてもコピー
        if sorted_dates:
            latest_date_str = sorted_dates[0].strftime("%Y%m%d")
            latest_feed = articles_dir / f"feed-{latest_date_str}.xml"
            default_feed = Path(output_dir) / "feed-articles.xml"
            shutil.copy2(str(latest_feed), str(default_feed))

        logger.info(
            "Generated article feeds for %d dates in %s",
            len(sorted_dates), articles_dir,
        )
        return sorted_dates

    @staticmethod
    def generate_article_index(
        dates: list[dt_module.date],
        output_dir: str,
    ) -> None:
        """日付選択用のHTMLインデックスページを生成する。"""
        articles_dir = Path(output_dir) / "articles"
        articles_dir.mkdir(parents=True, exist_ok=True)

        rows = []
        for pub_date in dates:
            date_str = pub_date.strftime("%Y%m%d")
            iso = pub_date.isoformat()
            weekday = ["月", "火", "水", "木", "金", "土", "日"][pub_date.weekday()]
            feed_file = f"feed-{date_str}.xml"
            rows.append(
                f'      <tr>'
                f'<td>{iso} ({weekday})</td>'
                f'<td><a href="{feed_file}">{feed_file}</a></td>'
                f'</tr>'
            )

        rows_html = "\n".join(rows)
        html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>官報 記事フィード 日付別一覧</title>
<style>
  body {{ font-family: -apple-system, sans-serif; max-width: 700px; margin: 2rem auto; padding: 0 1rem; }}
  h1 {{ font-size: 1.3rem; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th, td {{ border: 1px solid #ccc; padding: 0.4rem 0.8rem; text-align: left; }}
  th {{ background: #f5f5f5; }}
  a {{ color: #0366d6; }}
  p {{ color: #555; font-size: 0.9rem; }}
</style>
</head>
<body>
<h1>官報 記事フィード 日付別一覧</h1>
<p>各日付のRSSフィードリンクです。RSSリーダーに登録してください。</p>
<table>
  <thead><tr><th>日付</th><th>フィード</th></tr></thead>
  <tbody>
{rows_html}
  </tbody>
</table>
<p><a href="../feed-articles.xml">feed-articles.xml</a> は最新日のフィードです。</p>
</body>
</html>"""

        index_path = articles_dir / "index.html"
        index_path.write_text(html, encoding="utf-8")
        logger.info("Generated article index: %s (%d dates)", index_path, len(dates))


def _build_issue_description(issue: GazetteIssue) -> str:
    """号のRSS description を組み立てる。

    例（記事データあり）:
      本紙 (32頁, 5MB)
      告示, 国会事項, 人事異動, 叙位・叙勲（全28件）

    例（記事データなし）:
      本紙 (32頁, 5MB)

    例（ページ数・サイズも不明）:
      本紙
    """
    # 1行目: 種別 + ページ数・サイズ
    line1 = issue.gazette_type.label
    meta_parts: list[str] = []
    if issue.page_count is not None:
        meta_parts.append(f"{issue.page_count}頁")
    if issue.pdf_size is not None:
        meta_parts.append(issue.pdf_size)
    if meta_parts:
        line1 += f" ({', '.join(meta_parts)})"

    # 2行目: 記事セクション要約
    if not issue.articles:
        return line1

    # トップレベルセクション（h2相当 = section の最初の要素）を集約
    top_sections: list[str] = []
    seen: set[str] = set()
    for article in issue.articles:
        top = article.section.split(" / ")[0] if article.section else ""
        if top and top not in seen:
            seen.add(top)
            top_sections.append(top)

    if not top_sections:
        return line1

    total = len(issue.articles)
    sections_str = ", ".join(top_sections)
    return f"{line1}\n{sections_str}（全{total}件）"
