"""HTML parser for kanpo.go.jp."""

from __future__ import annotations

import logging
import re
from datetime import date

from bs4 import BeautifulSoup, Tag

from kanpo_rss.models import GazetteArticle, GazetteIssue, GazetteType

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


    def parse_issue_page(
        self, html: str, issue: GazetteIssue
    ) -> list[GazetteArticle]:
        """号の目次ページHTMLから記事情報を抽出する。

        各号の目次ページ（0000f.html）にはセクション見出し付きで
        記事リンクが並んでおり、それを GazetteArticle として返す。
        """
        soup = BeautifulSoup(html, "html.parser")
        contents_box = soup.select_one("div.contentsBox")
        if contents_box is None:
            logger.warning("No contentsBox found for %s", issue.issue_id)
            return []

        articles: list[GazetteArticle] = []
        # ページ番号ごとのインデックスカウンター
        page_index: dict[int, int] = {}

        # issue_id のプレフィックスを取得（記事リンクの判定用）
        article_href_re = re.compile(
            re.escape(issue.issue_id) + r"(\d{4})f\.html"
        )

        # セクション階層の追跡
        current_h2 = ""
        current_h3 = ""
        current_h4 = ""

        date_str = issue.issue_id[:8]
        base_url = f"{BASE_URL}/{date_str}/{issue.issue_id}"

        for element in contents_box.descendants:
            if not isinstance(element, Tag):
                continue

            # セクション見出しの更新
            if element.name == "h2" and "title" in element.get("class", []):
                text_span = element.select_one("span.text")
                if text_span:
                    current_h2 = text_span.get_text(strip=True)
                    current_h3 = ""
                    current_h4 = ""
                    # h2 自体がリンクを含む場合（例: 国会事項）
                    link = element.select_one("a[href]")
                    if link:
                        article = self._parse_article_entry(
                            link, article_href_re, current_h2,
                            issue.issue_id, base_url, page_index,
                        )
                        if article:
                            articles.append(article)
                continue

            if element.name == "h3" and "title" in element.get("class", []):
                text_span = element.select_one("span.text")
                if text_span:
                    current_h3 = text_span.get_text(strip=True)
                    current_h4 = ""
                continue

            if element.name == "h4":
                text_span = element.select_one("span.text")
                if text_span:
                    current_h4 = text_span.get_text(strip=True)
                # h4 自体がリンクを含む場合（例: 会社その他）
                link = element.select_one("a[href]")
                if link:
                    section = _build_section(current_h2, current_h3, current_h4)
                    article = self._parse_article_entry(
                        link, article_href_re, section,
                        issue.issue_id, base_url, page_index,
                    )
                    if article:
                        articles.append(article)
                continue

            # iconList 内の記事リンク
            if (
                element.name == "a"
                and element.parent
                and element.parent.name == "li"
                and element.parent.parent
                and element.parent.parent.get("class") == ["iconList"]
            ):
                section = _build_section(current_h2, current_h3, current_h4)
                article = self._parse_article_entry(
                    element, article_href_re, section,
                    issue.issue_id, base_url, page_index,
                )
                if article:
                    articles.append(article)

        logger.info(
            "Parsed %d articles from issue %s", len(articles), issue.issue_id
        )
        return articles

    def _parse_article_entry(
        self,
        link: Tag,
        href_re: re.Pattern[str],
        section: str,
        parent_issue_id: str,
        base_url: str,
        page_index: dict[int, int],
    ) -> GazetteArticle | None:
        """記事リンクタグから GazetteArticle を生成する。"""
        href = link.get("href", "")
        if not isinstance(href, str):
            return None

        match = href_re.search(href)
        if match is None:
            return None

        page_number = int(match.group(1))
        text_span = link.select_one("span.text")
        title = text_span.get_text(strip=True) if text_span else link.get_text(strip=True)
        if not title:
            return None

        # 同一ページ内のインデックス
        idx = page_index.get(page_number, 0)
        page_index[page_number] = idx + 1

        article_id = f"{parent_issue_id}:{page_number:04d}:{idx}"
        url = f"{base_url}/{href}"

        return GazetteArticle(
            article_id=article_id,
            title=title,
            url=url,
            section=section,
            parent_issue_id=parent_issue_id,
            page_number=page_number,
        )


def _build_section(h2: str, h3: str, h4: str) -> str:
    """セクション階層を「/」区切りの文字列にする。"""
    parts = [p for p in (h2, h3, h4) if p]
    return " / ".join(parts) if parts else ""


def _build_title(
    pub_date: date, gazette_type: GazetteType, issue_number: int
) -> str:
    """RSS表示用のタイトルを生成する。

    例: "2026-03-03 本紙 第1657号"
    """
    return f"{pub_date.isoformat()} {gazette_type.label} 第{issue_number}号"
