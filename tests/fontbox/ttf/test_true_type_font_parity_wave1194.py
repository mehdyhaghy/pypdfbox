from __future__ import annotations

from pathlib import Path

import pytest

from tests.fontbox.ttf import test_true_type_font_parity as parity_tests


def test_wave1194_liberation_sans_fixture_skips_when_font_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(parity_tests, "FIXTURE", Path("/missing/LiberationSans-Regular.ttf"))

    with pytest.raises(pytest.skip.Exception, match="Fixture font not present"):
        parity_tests.liberation_sans.__wrapped__()
