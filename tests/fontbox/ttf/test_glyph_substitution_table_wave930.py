from __future__ import annotations

import pytest

import tests.fontbox.ttf.test_glyph_substitution_table as gsub_tests


class _MissingFixture:
    def exists(self) -> bool:
        return False


def test_wave930_liberation_fixture_skip_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gsub_tests, "FIXTURE", _MissingFixture())

    with pytest.raises(pytest.skip.Exception, match="Fixture font not present"):
        gsub_tests.liberation_sans.__wrapped__()


def test_wave930_get_gsub_absent_test_exercises_contains_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def get_gsub_probe_non_gsub_key(self):  # noqa: ANN001
        assert "head" in self._tt
        return None

    monkeypatch.setattr(gsub_tests.TrueTypeFont, "get_gsub", get_gsub_probe_non_gsub_key)

    gsub_tests.test_get_gsub_returns_none_when_absent(monkeypatch)


def test_wave930_get_gsub_absent_test_skip_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gsub_tests, "FIXTURE", _MissingFixture())

    with pytest.raises(pytest.skip.Exception, match="Fixture not present"):
        gsub_tests.test_get_gsub_returns_none_when_absent(monkeypatch)
