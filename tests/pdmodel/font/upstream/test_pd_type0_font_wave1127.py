from __future__ import annotations

from pathlib import Path

import pytest

from tests.pdmodel.font.upstream import test_pd_type0_font as type0_tests


def test_wave1127_liberation_fixture_skip_branch(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    missing_fixture = tmp_path / "missing.ttf"
    monkeypatch.setattr(type0_tests, "_TTF_FIXTURE", missing_fixture)

    with pytest.raises(pytest.skip.Exception, match="Fixture font not present"):
        type0_tests.liberation_bytes.__wrapped__()
