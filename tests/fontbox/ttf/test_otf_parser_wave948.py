from __future__ import annotations

import pytest

from . import test_otf_parser as otf_tests


class _MissingFixture:
    def exists(self) -> bool:
        return False


def test_wave948_lenient_truetype_magic_skips_when_ttf_fixture_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(otf_tests, "FIXTURE_TTF", _MissingFixture())

    with pytest.raises(pytest.skip.Exception, match="TTF fixture not present"):
        otf_tests.test_parse_lenient_accepts_truetype_magic()

