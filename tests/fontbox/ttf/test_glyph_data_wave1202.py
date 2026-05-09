from __future__ import annotations

from pathlib import Path

import pytest

from tests.fontbox.ttf import test_glyph_data


def test_wave1202_liberation_sans_fixture_skips_when_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        test_glyph_data,
        "FIXTURE",
        tmp_path / "missing-liberation-sans.ttf",
    )

    with pytest.raises(pytest.skip.Exception):
        test_glyph_data.liberation_sans.__wrapped__()
