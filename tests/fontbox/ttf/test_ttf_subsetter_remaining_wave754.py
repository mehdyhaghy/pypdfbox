from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from pypdfbox.fontbox.ttf.ttf_subsetter import TTFSubsetter


class _TT(dict[str, Any]):
    def __init__(self, *args: Any, cmap: dict[int, str] | None = None) -> None:
        super().__init__(*args)
        self._cmap = cmap or {}

    def getBestCmap(self) -> dict[int, str]:
        return self._cmap


class _RaisingGlyf:
    def __setitem__(self, _name: str, _glyph: object) -> None:
        raise KeyError("missing glyph slot")


class _FakeSourceTTF:
    def __init__(self, tt: object) -> None:
        self._tt = tt

    def get_unicode_cmap_subtable(self) -> None:
        return None


class _NoGlyfSourceTable(dict[str, Any]):
    def getGlyphOrder(self) -> list[str]:
        return [".notdef"]


class _MissingGlyphTable(dict[str, Any]):
    def getGlyphOrder(self) -> list[str]:
        return [".notdef", "missing"]


class _CompositeTable(dict[str, Any]):
    def getGlyphOrder(self) -> list[str]:
        return [".notdef", "composite"]


class _CompositeGlyph:
    components = [SimpleNamespace(glyphName="absent-component")]

    def isComposite(self) -> bool:  # noqa: N802
        return True


class _NameRecord:
    def __init__(self, name_id: int, text: str) -> None:
        self.nameID = name_id
        self._text = text
        self.string: str | None = None

    def toUnicode(self) -> str:  # noqa: N802
        return self._text


def test_apply_invisible_returns_when_subset_has_no_glyf_table() -> None:
    TTFSubsetter._apply_invisible(_TT(cmap={65: "A"}), {65})


def test_apply_invisible_skips_glyf_assignment_errors() -> None:
    hmtx = SimpleNamespace(metrics={"A": (600, 7)})
    tt = _TT({"glyf": _RaisingGlyf(), "hmtx": hmtx}, cmap={65: "A"})

    TTFSubsetter._apply_invisible(tt, {65})

    assert hmtx.metrics["A"] == (600, 7)


def test_add_composite_components_returns_when_source_has_no_glyf() -> None:
    subsetter = TTFSubsetter(_FakeSourceTTF(_NoGlyfSourceTable()))  # type: ignore[arg-type]
    old_gids = {0}

    subsetter._add_composite_components(old_gids)

    assert old_gids == {0}


def test_add_composite_components_skips_invalid_and_missing_glyphs() -> None:
    source_table = _MissingGlyphTable(glyf={})
    subsetter = TTFSubsetter(_FakeSourceTTF(source_table))  # type: ignore[arg-type]
    old_gids = {1, 99}

    subsetter._add_composite_components(old_gids)

    assert old_gids == {1, 99}


def test_add_composite_components_skips_unknown_component_names() -> None:
    source_table = _CompositeTable(glyf={"composite": _CompositeGlyph()})
    subsetter = TTFSubsetter(_FakeSourceTTF(source_table))  # type: ignore[arg-type]
    old_gids = {1}

    subsetter._add_composite_components(old_gids)

    assert old_gids == {1}


def test_apply_prefix_returns_without_name_table() -> None:
    TTFSubsetter._apply_prefix(_TT(), "ABCDEF")


def test_apply_prefix_skips_empty_name_records() -> None:
    empty = _NameRecord(4, "")
    ignored = _NameRecord(1, "Family")
    tt = _TT({"name": SimpleNamespace(names=[empty, ignored])})

    TTFSubsetter._apply_prefix(tt, "ABCDEF")

    assert empty.string is None
    assert ignored.string is None
