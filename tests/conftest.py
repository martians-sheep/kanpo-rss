"""Shared test fixtures."""

from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def top_page_html() -> str:
    return (FIXTURES_DIR / "top_page.html").read_text(encoding="utf-8")


@pytest.fixture
def issue_page_honshi_html() -> str:
    return (FIXTURES_DIR / "issue_page_honshi.html").read_text(encoding="utf-8")


@pytest.fixture
def issue_page_gougai_html() -> str:
    return (FIXTURES_DIR / "issue_page_gougai.html").read_text(encoding="utf-8")
