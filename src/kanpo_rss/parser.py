"""HTML parser for kanpo.go.jp."""

from __future__ import annotations

import logging
import re
from datetime import date

from bs4 import BeautifulSoup, Tag

from kanpo_rss.models import GazetteIssue, GazetteType

logger = logging.getLogger(__name__)

BASE_URL = "https://www.kanpo.go.jp"

# Maps the type prefix character to GazetteType
_PREFIX_TO_TYPE: dict[str, GazetteType] = {t.value: t for t in GazetteType}

# Regex to extract date, type prefix, and issue number from href
# e.g. "./20260303/20260303h01657/20260303h016570000f.html"
_ISSUE_HREF_RE = re.compile(
    r"\.?/?(\d{8})([hgct])(\d{5})/\1\2\3\d{4}f\.html"
)


class KanpoParser:
    """Parser for kanpo.go.jp HTML pages."""

    def parse_top_page(self, html: str) -> list[GazetteIssue]:
        """トップページHTMLから全号の情報を抽出する。

        トップページには直近90日分の全号が掲載されており、
        Phase 1ではこれだけで十分な情報が得られる。
        """
        soup = BeautifulSoup(html, "html.parser")
        issues: list[GazetteIssue] = []

        for article_link in soup.select("a.articleTop"):
            issue = self._parse_article_link(article_link)
            if issue is not None:
                issues.append(issue)

        logger.info("Parsed %d issues from top page", len(issues))
        return issues

    def _parse_article_link(self, tag: Tag) -> GazetteIssue | None:
        """<a class="articleTop"> タグから GazetteIssue を生成する。

        タグ例:
          <a href="./20260303/20260303h01657/20260303h016570000f.html"
             class="articleTop">本紙<br>(第1657号)</a>
        """
        href = tag.get("href", "")
        if not isinstance(href, str):
            return None

        match = _ISSUE_HREF_RE.search(href)
        if match is None:
            logger.warning("Could not parse href: %s", href)
            return None

        date_str, type_prefix, issue_num_str = match.groups()
        gazette_type = _PREFIX_TO_TYPE.get(type_prefix)
        if gazette_type is None:
            logger.warning("Unknown gazette type prefix: %s", type_prefix)
            return None

        try:
            pub_date = date(
                int(date_str[:4]), int(date_str[4:6]), int(date_str[6:8])
            )
        except ValueError:
            logger.warning("Invalid date: %s", date_str)
            return None

        issue_number = int(issue_num_str)
        issue_id = f"{date_str}{type_prefix}{issue_num_str}"
        issue_url = f"{BASE_URL}/{date_str}/{issue_id}/{issue_id}0000f.html"
        title = _build_title(pub_date, gazette_type, issue_number)

        return GazetteIssue(
            date=pub_date,
            gazette_type=gazette_type,
            issue_number=issue_number,
            issue_id=issue_id,
            url=issue_url,
            title=title,
        )


def _build_title(
    pub_date: date, gazette_type: GazetteType, issue_number: int
) -> str:
    """RSS表示用のタイトルを生成する。

    例: "2026-03-03 本紙 第1657号"
    """
    return f"{pub_date.isoformat()} {gazette_type.label} 第{issue_number}号"
