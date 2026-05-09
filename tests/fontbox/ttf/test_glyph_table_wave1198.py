from __future__ import annotations

from pathlib import Path

import pytest

import tests.fontbox.ttf.test_glyph_table as target


def test_liberation_sans_fixture_skip_branch(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(target, "FIXTURE", tmp_path / "missing.ttf")

    with pytest.raises(pytest.skip.Exception, match="Fixture font not present"):
        target.liberation_sans.__wrapped__()
