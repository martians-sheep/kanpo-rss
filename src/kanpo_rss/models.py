"""Data models for kanpo-rss."""

from __future__ import annotations

import datetime
from dataclasses import dataclass
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


@dataclass(frozen=True)
class GazetteIssue:
    """1号分の官報情報。"""

    date: datetime.date
    gazette_type: GazetteType
    issue_number: int
    issue_id: str  # e.g. "20260303h01657"
    url: str
    title: str  # e.g. "令和8年3月3日 本紙 第1657号"
