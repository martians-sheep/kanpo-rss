"""Tests for kanpo_rss.storage."""

from __future__ import annotations

import json
import tempfile
from datetime import date
from pathlib import Path

import pytest

from kanpo_rss.models import GazetteIssue, GazetteType
from kanpo_rss.storage import CURRENT_VERSION, IssueStorage


def _make_issue(
    d: str = "2026-03-03",
    gazette_type: GazetteType = GazetteType.HONSHI,
    issue_number: int = 1657,
) -> GazetteIssue:
    dt = date.fromisoformat(d)
    type_prefix = gazette_type.value
    issue_id = f"{dt:%Y%m%d}{type_prefix}{issue_number:05d}"
    return GazetteIssue(
        date=dt,
        gazette_type=gazette_type,
        issue_number=issue_number,
        issue_id=issue_id,
        url=f"https://www.kanpo.go.jp/{dt:%Y%m%d}/{issue_id}.html",
        title=f"{d} {gazette_type.label} 第{issue_number}号",
    )


class TestLoad:
    def test_load_nonexistent_file(self) -> None:
        storage = IssueStorage()
        result = storage.load("/nonexistent/path/issues.json")
        assert result == []

    def test_load_empty_file(self) -> None:
        storage = IssueStorage()
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            f.write("")
            f.flush()
            result = storage.load(f.name)
        assert result == []

    def test_load_valid_json(self) -> None:
        storage = IssueStorage()
        data = {
            "version": 1,
            "last_updated": "2026-03-03T09:00:00+09:00",
            "issues": [
                {
                    "date": "2026-03-03",
                    "gazette_type": "h",
                    "issue_number": 1657,
                    "issue_id": "20260303h01657",
                    "url": "https://www.kanpo.go.jp/20260303/20260303h01657.html",
                    "title": "2026-03-03 本紙 第1657号",
                },
            ],
        }
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(data, f)
            f.flush()
            result = storage.load(f.name)

        assert len(result) == 1
        assert result[0].issue_id == "20260303h01657"
        assert result[0].gazette_type == GazetteType.HONSHI

    def test_load_skips_invalid_entries(self) -> None:
        storage = IssueStorage()
        data = {
            "version": 1,
            "issues": [
                {"date": "2026-03-03", "gazette_type": "INVALID"},
                {
                    "date": "2026-03-03",
                    "gazette_type": "h",
                    "issue_number": 1657,
                    "issue_id": "20260303h01657",
                    "url": "https://example.com",
                    "title": "Valid",
                },
            ],
        }
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(data, f)
            f.flush()
            result = storage.load(f.name)

        assert len(result) == 1
        assert result[0].issue_id == "20260303h01657"


class TestSave:
    def test_save_and_load_roundtrip(self) -> None:
        storage = IssueStorage()
        issues = [
            _make_issue("2026-03-01"),
            _make_issue("2026-03-03"),
            _make_issue("2026-03-02"),
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = str(Path(tmpdir) / "issues.json")
            storage.save(path, issues)
            loaded = storage.load(path)

        assert len(loaded) == 3
        # 日付降順でソートされている
        assert loaded[0].date == date(2026, 3, 3)
        assert loaded[1].date == date(2026, 3, 2)
        assert loaded[2].date == date(2026, 3, 1)

    def test_version_field(self) -> None:
        storage = IssueStorage()
        issues = [_make_issue()]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = str(Path(tmpdir) / "issues.json")
            storage.save(path, issues)
            data = json.loads(Path(path).read_text())

        assert data["version"] == CURRENT_VERSION
        assert "last_updated" in data

    def test_save_creates_parent_dirs(self) -> None:
        storage = IssueStorage()
        issues = [_make_issue()]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = str(Path(tmpdir) / "sub" / "dir" / "issues.json")
            storage.save(path, issues)
            assert Path(path).exists()


class TestMerge:
    def test_merge_deduplication(self) -> None:
        storage = IssueStorage()
        issue1 = _make_issue("2026-03-03")
        issue2 = _make_issue("2026-03-03")  # 同じissue_id
        result = storage.merge([issue1], [issue2])
        assert len(result) == 1

    def test_merge_new_data_priority(self) -> None:
        storage = IssueStorage()
        old = GazetteIssue(
            date=date(2026, 3, 3),
            gazette_type=GazetteType.HONSHI,
            issue_number=1657,
            issue_id="20260303h01657",
            url="https://old.example.com",
            title="Old title",
        )
        new = GazetteIssue(
            date=date(2026, 3, 3),
            gazette_type=GazetteType.HONSHI,
            issue_number=1657,
            issue_id="20260303h01657",
            url="https://new.example.com",
            title="New title",
        )
        result = storage.merge([old], [new])
        assert len(result) == 1
        assert result[0].url == "https://new.example.com"

    def test_merge_preserves_order(self) -> None:
        storage = IssueStorage()
        existing = [_make_issue("2026-03-01"), _make_issue("2026-03-03")]
        new = [_make_issue("2026-03-02")]
        result = storage.merge(existing, new)
        assert len(result) == 3
        dates = [i.date for i in result]
        assert dates == [date(2026, 3, 3), date(2026, 3, 2), date(2026, 3, 1)]

    def test_merge_new_data_added(self) -> None:
        storage = IssueStorage()
        existing = [_make_issue("2026-03-01")]
        new = [_make_issue("2026-03-02"), _make_issue("2026-03-03")]
        result = storage.merge(existing, new)
        assert len(result) == 3

    def test_merge_empty_existing(self) -> None:
        storage = IssueStorage()
        new = [_make_issue("2026-03-01"), _make_issue("2026-03-02")]
        result = storage.merge([], new)
        assert len(result) == 2

    def test_merge_empty_new(self) -> None:
        storage = IssueStorage()
        existing = [_make_issue("2026-03-01")]
        result = storage.merge(existing, [])
        assert len(result) == 1
