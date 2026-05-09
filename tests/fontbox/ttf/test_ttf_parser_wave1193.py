from __future__ import annotations

from pathlib import Path

import pytest

from tests.fontbox.ttf import test_ttf_parser as parser_tests


def test_wave1193_ttf_bytes_fixture_skips_when_font_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(parser_tests, "FIXTURE", Path("/missing/LiberationSans-Regular.ttf"))

    with pytest.raises(pytest.skip.Exception, match="Fixture font not present"):
        parser_tests.ttf_bytes.__wrapped__()
