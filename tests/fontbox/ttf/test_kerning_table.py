from __future__ import annotations

import pathlib
from typing import Any

from pypdfbox.fontbox.ttf.kerning_subtable import KerningSubtable
from pypdfbox.fontbox.ttf.kerning_table import KerningTable
from pypdfbox.fontbox.ttf.true_type_font import TrueTypeFont

FIXTURE = (
    pathlib.Path(__file__).resolve().parents[2]
    / "fixtures"
    / "fontbox"
    / "ttf"
    / "LiberationSans-Regular.ttf"
)


# ---------- helpers ---------------------------------------------------------


class _FakeFTSub:
    def __init__(
        self,
        coverage: int,
        fmt: int = 0,
        pairs: dict[tuple[str, str], int] | None = None,
        apple: bool = False,
    ) -> None:
        self.coverage = coverage
        self.format = fmt
        self.kernTable = pairs if pairs is not None else {}
        self.apple = apple


class _FakeFTKern:
    def __init__(self, version: float | int, subs: list[_FakeFTSub]) -> None:
        self.version = version
        self.kernTables = subs


class _FakeTTF:
    def __init__(self, glyph_order: list[str]) -> None:
        class _Inner:
            def __init__(self, names: list[str]) -> None:
                self._names = names

            def getGlyphOrder(self) -> list[str]:  # noqa: N802
                return list(self._names)

        self._tt: Any = _Inner(glyph_order)


# ---------- defaults --------------------------------------------------------


def test_tag_constant() -> None:
    assert KerningTable.TAG == "kern"


def test_defaults_before_population() -> None:
    table = KerningTable()
    assert table.get_initialized() is False
    assert table.get_subtables() == []
    assert table.get_horizontal_kerning_subtable() is None
    assert table.get_version() == 0


# ---------- from_fonttools wrapping ----------------------------------------


def test_from_fonttools_marks_initialized() -> None:
    ft_kern = _FakeFTKern(version=0, subs=[])
    ttf = _FakeTTF([".notdef"])
    table = KerningTable.from_fonttools(ft_kern, ttf)  # type: ignore[arg-type]
    assert table.get_initialized() is True
    assert table.get_version() == 0
    assert table.get_subtables() == []


def test_from_fonttools_wraps_each_subtable() -> None:
    subs = [
        _FakeFTSub(coverage=0x01, pairs={("A", "V"): -120}),
        _FakeFTSub(coverage=0x05),  # cross-stream horizontal
    ]
    ft_kern = _FakeFTKern(version=0, subs=subs)
    ttf = _FakeTTF([".notdef", "A", "V"])
    table = KerningTable.from_fonttools(ft_kern, ttf)  # type: ignore[arg-type]
    wrapped = table.get_subtables()
    assert len(wrapped) == 2
    assert all(isinstance(s, KerningSubtable) for s in wrapped)
    assert wrapped[0].is_horizontal_kerning(False) is True
    assert wrapped[1].is_horizontal_kerning(True) is True


def test_get_subtables_returns_copy_not_internal_list() -> None:
    ft_kern = _FakeFTKern(version=0, subs=[_FakeFTSub(coverage=0x01)])
    ttf = _FakeTTF([".notdef"])
    table = KerningTable.from_fonttools(ft_kern, ttf)  # type: ignore[arg-type]
    out = table.get_subtables()
    out.clear()
    # Mutating the returned list must not drain the table itself.
    assert len(table.get_subtables()) == 1


# ---------- get_horizontal_kerning_subtable selection ----------------------


def test_horizontal_kerning_subtable_default_is_inline() -> None:
    inline = _FakeFTSub(coverage=0x01)
    cross = _FakeFTSub(coverage=0x05)
    ft_kern = _FakeFTKern(version=0, subs=[cross, inline])
    ttf = _FakeTTF([".notdef"])
    table = KerningTable.from_fonttools(ft_kern, ttf)  # type: ignore[arg-type]
    sub = table.get_horizontal_kerning_subtable()
    assert sub is not None
    # Default cross=False → must NOT pick the cross-stream subtable, even
    # though it appears first in the table directory.
    assert sub.is_cross_stream() is False


def test_horizontal_kerning_subtable_cross_picks_cross_stream() -> None:
    inline = _FakeFTSub(coverage=0x01)
    cross = _FakeFTSub(coverage=0x05)
    ft_kern = _FakeFTKern(version=0, subs=[inline, cross])
    ttf = _FakeTTF([".notdef"])
    table = KerningTable.from_fonttools(ft_kern, ttf)  # type: ignore[arg-type]
    sub = table.get_horizontal_kerning_subtable(cross=True)
    assert sub is not None
    assert sub.is_cross_stream() is True


def test_horizontal_kerning_subtable_skips_minimum_subtable() -> None:
    minimum = _FakeFTSub(coverage=0x03)  # horizontal + minimums
    ft_kern = _FakeFTKern(version=0, subs=[minimum])
    ttf = _FakeTTF([".notdef"])
    table = KerningTable.from_fonttools(ft_kern, ttf)  # type: ignore[arg-type]
    assert table.get_horizontal_kerning_subtable() is None


def test_horizontal_kerning_subtable_returns_none_when_only_vertical() -> None:
    vertical = _FakeFTSub(coverage=0x00)
    ft_kern = _FakeFTKern(version=0, subs=[vertical])
    ttf = _FakeTTF([".notdef"])
    table = KerningTable.from_fonttools(ft_kern, ttf)  # type: ignore[arg-type]
    assert table.get_horizontal_kerning_subtable() is None


def test_horizontal_kerning_subtable_returns_first_match_in_order() -> None:
    a = _FakeFTSub(coverage=0x01, pairs={("A", "V"): -100})
    b = _FakeFTSub(coverage=0x01, pairs={("A", "V"): -200})
    ft_kern = _FakeFTKern(version=0, subs=[a, b])
    ttf = _FakeTTF([".notdef", "A", "V"])
    table = KerningTable.from_fonttools(ft_kern, ttf)  # type: ignore[arg-type]
    sub = table.get_horizontal_kerning_subtable()
    assert sub is not None
    # Matches upstream: first subtable in table directory order.
    assert sub.get_kerning(1, 2) == -100


# ---------- real-font integration via TrueTypeFont -------------------------


def test_truetypefont_get_kerning_table_returns_view() -> None:
    ttf = TrueTypeFont.from_bytes(FIXTURE.read_bytes())
    kt = ttf.get_kerning_table()
    assert kt is not None
    assert kt.get_initialized() is True
    assert len(kt.get_subtables()) >= 1


def test_truetypefont_get_kerning_table_caches_result() -> None:
    ttf = TrueTypeFont.from_bytes(FIXTURE.read_bytes())
    a = ttf.get_kerning_table()
    b = ttf.get_kerning_table()
    assert a is b


def test_get_kerning_table_returns_none_when_kern_absent() -> None:
    """Strip the kern entry from the SFNT directory so ``"kern" in self._tt``
    reports False, then verify the negative case is cached as ``None``."""
    ttf = TrueTypeFont.from_bytes(FIXTURE.read_bytes())
    # Drop kern from both the lazy reader directory and any already-loaded
    # cache slot so fontTools' ``__contains__`` reports False.
    ttf._tt.reader.tables.pop("kern", None)  # noqa: SLF001
    ttf._tt.tables.pop("kern", None)  # noqa: SLF001
    assert "kern" not in ttf._tt  # noqa: SLF001
    # Reset cached resolution so the lookup re-walks the directory.
    ttf._kern = None  # noqa: SLF001
    ttf._kern_resolved = False  # noqa: SLF001
    assert ttf.get_kerning_table() is None
    # Cached negative — second call returns the same None without re-probing.
    assert ttf.get_kerning_table() is None


def test_horizontal_kerning_subtable_from_real_font() -> None:
    ttf = TrueTypeFont.from_bytes(FIXTURE.read_bytes())
    kt = ttf.get_kerning_table()
    assert kt is not None
    sub = kt.get_horizontal_kerning_subtable()
    assert sub is not None
    glyph_order = ttf._tt.getGlyphOrder()  # noqa: SLF001
    gid_a = glyph_order.index("A")
    gid_v = glyph_order.index("V")
    # A,V is a textbook kerning pair — must be a non-zero adjustment.
    assert sub.get_kerning(gid_a, gid_v) != 0
