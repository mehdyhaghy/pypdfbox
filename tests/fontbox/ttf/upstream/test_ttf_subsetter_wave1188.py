from __future__ import annotations

from pathlib import Path

import pytest

from tests.fontbox.ttf.upstream import test_ttf_subsetter as subsetter_tests


def test_wave1188_liberation_sans_fixture_skip_branch(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(subsetter_tests, "FIXTURE", tmp_path / "missing.ttf")

    with pytest.raises(pytest.skip.Exception, match="Fixture font not present"):
        subsetter_tests.liberation_sans.__wrapped__()
