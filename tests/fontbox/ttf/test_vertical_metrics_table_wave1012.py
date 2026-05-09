from __future__ import annotations

from pathlib import Path

import pytest

from tests.fontbox.ttf import test_vertical_metrics_table as base


def test_synthesize_font_skips_when_fixture_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    missing_fixture = tmp_path / "missing.ttf"
    monkeypatch.setattr(base, "FIXTURE", missing_fixture)

    with pytest.raises(pytest.skip.Exception, match="Fixture font not present"):
        base._synthesize_font_with_vmtx()


def test_absent_vertical_metrics_test_skips_when_fixture_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    missing_fixture = tmp_path / "missing.ttf"
    monkeypatch.setattr(base, "FIXTURE", missing_fixture)

    with pytest.raises(pytest.skip.Exception, match="Fixture font not present"):
        base.test_get_vertical_metrics_returns_none_when_absent()
