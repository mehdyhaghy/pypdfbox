from __future__ import annotations

from pathlib import Path

import pytest

from tests.fontbox.ttf import test_vertical_header_table as target


def test_synthesize_font_skips_when_fixture_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(target, "FIXTURE", Path("/missing/LiberationSans-Regular.ttf"))

    with pytest.raises(pytest.skip.Exception):
        target._synthesize_font_with_vhea()


def test_absent_vertical_header_skips_when_fixture_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(target, "FIXTURE", Path("/missing/LiberationSans-Regular.ttf"))

    with pytest.raises(pytest.skip.Exception):
        target.test_get_vertical_header_returns_none_when_absent()
