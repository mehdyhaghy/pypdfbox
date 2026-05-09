from __future__ import annotations

from pathlib import Path

import pytest

from tests.fontbox.ttf import test_ttf_subsetter_wave319 as wave319_tests


def test_wave1190_wave319_liberation_fixture_skip(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(wave319_tests, "FIXTURE", Path("/missing/LiberationSans-Regular.ttf"))

    with pytest.raises(pytest.skip.Exception, match="Fixture font not present"):
        wave319_tests.liberation_sans.__wrapped__()
