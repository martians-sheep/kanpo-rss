"""JSON-based storage for accumulating gazette issue data."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

from kanpo_rss.models import GazetteIssue, GazetteType

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
            merged[issue.issue_id] = issue  # 新しいデータで上書き

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
    return {
        "date": issue.date.isoformat(),
        "gazette_type": issue.gazette_type.value,
        "issue_number": issue.issue_number,
        "issue_id": issue.issue_id,
        "url": issue.url,
        "title": issue.title,
    }


def _dict_to_issue(d: dict) -> GazetteIssue:
    from datetime import date as date_cls

    return GazetteIssue(
        date=date_cls.fromisoformat(d["date"]),
        gazette_type=GazetteType(d["gazette_type"]),
        issue_number=d["issue_number"],
        issue_id=d["issue_id"],
        url=d["url"],
        title=d["title"],
    )
