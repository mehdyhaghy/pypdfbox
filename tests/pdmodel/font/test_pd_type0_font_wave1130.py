from __future__ import annotations

import pytest

import tests.pdmodel.font.test_pd_type0_font as type0_tests


def test_wave1130_liberation_bytes_skip_branch(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(type0_tests, "_TTF_FIXTURE", tmp_path / "missing.ttf")

    with pytest.raises(pytest.skip.Exception, match="Fixture font not present"):
        type0_tests.liberation_bytes.__wrapped__()
