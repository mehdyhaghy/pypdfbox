from __future__ import annotations

import pytest

import tests.fontbox.ttf.test_glyph_positioning_table as gpos_tests


class _MissingFixture:
    def exists(self) -> bool:
        return False


def test_wave929_liberation_fixture_skip_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gpos_tests, "FIXTURE", _MissingFixture())

    with pytest.raises(pytest.skip.Exception, match="Fixture font not present"):
        gpos_tests.liberation_sans.__wrapped__()


def test_wave929_get_gpos_absent_test_exercises_contains_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def get_gpos_probe_non_gpos_key(self):  # noqa: ANN001
        assert "head" in self._tt
        return None

    monkeypatch.setattr(gpos_tests.TrueTypeFont, "get_gpos", get_gpos_probe_non_gpos_key)

    gpos_tests.test_get_gpos_returns_none_when_absent(monkeypatch)


def test_wave929_get_gpos_absent_test_skip_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gpos_tests, "FIXTURE", _MissingFixture())

    with pytest.raises(pytest.skip.Exception, match="Fixture not present"):
        gpos_tests.test_get_gpos_returns_none_when_absent(monkeypatch)
