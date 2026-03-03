"""Data models for kanpo-rss."""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from enum import Enum


class GazetteType(Enum):
    """官報の種別。値はURLプレフィックス文字。"""

    HONSHI = "h"  # 本紙
    GOUGAI = "g"  # 号外
    SEIFU_CHOUTATSU = "c"  # 政府調達
    TOKUBETSU_GOUGAI = "t"  # 特別号外

    @property
    def label(self) -> str:
        """日本語の種別名を返す。"""
        return _GAZETTE_TYPE_LABELS[self]


_GAZETTE_TYPE_LABELS: dict[GazetteType, str] = {
    GazetteType.HONSHI: "本紙",
    GazetteType.GOUGAI: "号外",
    GazetteType.SEIFU_CHOUTATSU: "政府調達",
    GazetteType.TOKUBETSU_GOUGAI: "特別号外",
}

# 官報サイトの掲載順に準拠した表示順序
GAZETTE_TYPE_ORDER: dict[GazetteType, int] = {
    GazetteType.HONSHI: 0,
    GazetteType.GOUGAI: 1,
    GazetteType.TOKUBETSU_GOUGAI: 2,
    GazetteType.SEIFU_CHOUTATSU: 3,
}


@dataclass(frozen=True)
class GazetteArticle:
    """1記事分の官報情報。号の目次ページから抽出される個別記事。"""

    article_id: str  # GUID用 e.g. "20260303h01657:0001:0"
    title: str  # e.g. "パラオ共和国政府に対する贈与に関する件（外務七六）"
    url: str  # 該当ページへの直リンク
    section: str  # セクション見出し e.g. "その他告示"
    parent_issue_id: str  # 親号の issue_id
    page_number: int  # 官報ページ番号（URL末尾4桁）


@dataclass(frozen=True)
class GazetteIssue:
    """1号分の官報情報。"""

    date: datetime.date
    gazette_type: GazetteType
    issue_number: int
    issue_id: str  # e.g. "20260303h01657"
    url: str
    title: str  # e.g. "令和8年3月3日 本紙 第1657号"
    articles: list[GazetteArticle] = field(default_factory=list)
