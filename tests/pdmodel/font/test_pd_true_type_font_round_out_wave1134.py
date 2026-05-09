from __future__ import annotations

from pathlib import Path

import pytest

import tests.pdmodel.font.test_pd_true_type_font_round_out as round_out_tests


def test_wave1134_liberation_bytes_skip_branch(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(round_out_tests, "_TTF_FIXTURE", tmp_path / "missing.ttf")

    with pytest.raises(pytest.skip.Exception, match="Fixture font not present"):
        round_out_tests.liberation_bytes.__wrapped__()
