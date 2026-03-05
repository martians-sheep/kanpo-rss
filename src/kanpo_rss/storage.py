"""JSON-based storage for accumulating gazette issue data."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

from dataclasses import replace

from kanpo_rss.models import GazetteArticle, GazetteIssue, GazetteType

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))

CURRENT_VERSION = 1


class IssueStorage:
    """JSON ファイルによる GazetteIssue の永続化。"""

    def load(self, path: str) -> list[GazetteIssue]:
        """data/issues.json を読み込み list[GazetteIssue] を返す。

        ファイルが存在しない or 空の場合は空リストを返す。
        """
        p = Path(path)
        if not p.exists():
            logger.debug("Storage file not found: %s", path)
            return []

        text = p.read_text(encoding="utf-8").strip()
        if not text:
            logger.debug("Storage file is empty: %s", path)
            return []

        data = json.loads(text)
        raw_issues = data.get("issues", [])
        issues: list[GazetteIssue] = []
        for item in raw_issues:
            try:
                issues.append(_dict_to_issue(item))
            except (KeyError, ValueError) as e:
                logger.warning("Skipping invalid issue entry: %s (%s)", item, e)
        return issues

    def save(self, path: str, issues: list[GazetteIssue]) -> None:
        """list[GazetteIssue] を JSON として書き出す。日付降順でソート。"""
        sorted_issues = sorted(
            issues, key=lambda i: (i.date, i.issue_id), reverse=True
        )
        data = {
            "version": CURRENT_VERSION,
            "last_updated": datetime.now(JST).isoformat(),
            "issues": [_issue_to_dict(i) for i in sorted_issues],
        }
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        logger.info("Saved %d issues to %s", len(sorted_issues), path)

    def merge(
        self,
        existing: list[GazetteIssue],
        new: list[GazetteIssue],
    ) -> list[GazetteIssue]:
        """issue_id をキーに重複排除してマージ。新しいデータが優先。"""
        merged: dict[str, GazetteIssue] = {}
        for issue in existing:
            merged[issue.issue_id] = issue
        for issue in new:
            existing_issue = merged.get(issue.issue_id)
            if existing_issue and existing_issue.articles and not issue.articles:
                # 既存の記事データを保持しつつメタデータは更新
                merged[issue.issue_id] = replace(
                    existing_issue, url=issue.url, title=issue.title
                )
            else:
                merged[issue.issue_id] = issue

        result = sorted(
            merged.values(), key=lambda i: (i.date, i.issue_id), reverse=True
        )
        logger.info(
            "Merged: %d existing + %d new → %d total (%d newly added)",
            len(existing),
            len(new),
            len(result),
            len(result) - len(existing),
        )
        return list(result)


def _issue_to_dict(issue: GazetteIssue) -> dict:
    d: dict = {
        "date": issue.date.isoformat(),
        "gazette_type": issue.gazette_type.value,
        "issue_number": issue.issue_number,
        "issue_id": issue.issue_id,
        "url": issue.url,
        "title": issue.title,
    }
    if issue.articles:
        d["articles"] = [_article_to_dict(a) for a in issue.articles]
    return d


def _dict_to_issue(d: dict) -> GazetteIssue:
    from datetime import date as date_cls

    url = _migrate_url(d["url"], d["issue_id"])
    articles = [
        _dict_to_article(a) for a in d.get("articles", [])
    ]
    return GazetteIssue(
        date=date_cls.fromisoformat(d["date"]),
        gazette_type=GazetteType(d["gazette_type"]),
        issue_number=d["issue_number"],
        issue_id=d["issue_id"],
        url=url,
        title=d["title"],
        articles=articles,
    )


def _article_to_dict(article: GazetteArticle) -> dict:
    return {
        "article_id": article.article_id,
        "title": article.title,
        "url": article.url,
        "section": article.section,
        "parent_issue_id": article.parent_issue_id,
        "page_number": article.page_number,
    }


def _dict_to_article(d: dict) -> GazetteArticle:
    return GazetteArticle(
        article_id=d["article_id"],
        title=d["title"],
        url=d["url"],
        section=d["section"],
        parent_issue_id=d["parent_issue_id"],
        page_number=d["page_number"],
    )


KANPO_BASE_URL = "https://www.kanpo.go.jp"


def _migrate_url(url: str, issue_id: str) -> str:
    """旧形式の fullcontents.html URL を号ごとの個別URLに変換する。

    旧: https://www.kanpo.go.jp/20260303/20260303.fullcontents.html
    新: https://www.kanpo.go.jp/20260303/20260303h01657/20260303h016570000f.html
    """
    if ".fullcontents.html" not in url:
        return url
    date_str = issue_id[:8]
    return f"{KANPO_BASE_URL}/{date_str}/{issue_id}/{issue_id}0000f.html"
