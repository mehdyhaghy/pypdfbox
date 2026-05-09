from __future__ import annotations

from pathlib import Path

import pytest

from tests.fontbox.ttf import test_glyph_data_wave328


def test_wave1199_liberation_sans_fixture_skips_when_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        test_glyph_data_wave328,
        "FIXTURE",
        tmp_path / "pypdfbox-missing-liberation-sans.ttf",
    )

    with pytest.raises(pytest.skip.Exception):
        test_glyph_data_wave328.liberation_sans_wave328.__wrapped__()
