from __future__ import annotations

import pytest

from tests.fontbox.ttf import test_ttf_subsetter as subsetter_tests


def test_liberation_bytes_fixture_skips_when_fixture_is_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(subsetter_tests, "FIXTURE", tmp_path / "missing.ttf")

    with pytest.raises(pytest.skip.Exception, match="Fixture font not present"):
        subsetter_tests.liberation_bytes.__wrapped__()
