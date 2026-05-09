from __future__ import annotations

from pathlib import Path

import pytest

from tests.fontbox.ttf.upstream import test_glyph_substitution_table as gsub_tests


def test_wave1189_get_gsub_data_missing_fixture_skip(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(gsub_tests, "FIXTURE", Path("/missing/LiberationSans-Regular.ttf"))

    with pytest.raises(pytest.skip.Exception, match="Fixture font not present"):
        gsub_tests.test_get_gsub_data()
