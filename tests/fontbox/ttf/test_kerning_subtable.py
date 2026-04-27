from __future__ import annotations

import pathlib
from typing import Any

from pypdfbox.fontbox.ttf.kerning_subtable import KerningSubtable
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
    """Stand-in for ``fontTools.ttLib.tables._k_e_r_n.KernTable_format_0``.

    fontTools stores the OpenType-style coverage as ``coverage`` (low 8
    bits of the upstream 16-bit coverage word) and ``format`` (high 8
    bits) on each subtable, plus a ``kernTable`` dict keyed by
    ``(glyph_name, glyph_name)``. We mimic that layout exactly so
    ``KerningSubtable`` can be exercised without round-tripping through a
    real font.
    """

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


class _FakeTTF:
    """Minimal stand-in that exposes the ``_tt.getGlyphOrder()`` method
    KerningSubtable uses to project glyph IDs back to fontTools' name keys."""

    def __init__(self, glyph_order: list[str]) -> None:
        class _Inner:
            def __init__(self, names: list[str]) -> None:
                self._names = names

            def getGlyphOrder(self) -> list[str]:  # noqa: N802
                return list(self._names)

        self._tt: Any = _Inner(glyph_order)


# ---------- coverage flags --------------------------------------------------


def test_horizontal_inline_subtable_flags() -> None:
    sub = KerningSubtable(_FakeFTSub(coverage=0x01))
    assert sub.is_horizontal() is True
    assert sub.is_minimum() is False
    assert sub.is_cross_stream() is False
    assert sub.is_horizontal_kerning() is True
    assert sub.is_horizontal_kerning(False) is True
    assert sub.is_horizontal_kerning(True) is False


def test_horizontal_cross_stream_subtable() -> None:
    sub = KerningSubtable(_FakeFTSub(coverage=0x05))
    assert sub.is_horizontal() is True
    assert sub.is_cross_stream() is True
    # cross-stream subtable: only matches when caller asks for cross
    assert sub.is_horizontal_kerning(False) is False
    assert sub.is_horizontal_kerning(True) is True


def test_minimum_subtable_excluded_from_horizontal_kerning() -> None:
    sub = KerningSubtable(_FakeFTSub(coverage=0x03))  # horizontal + minimums
    assert sub.is_horizontal() is True
    assert sub.is_minimum() is True
    # Upstream: minimum subtables never qualify as horizontal kerning.
    assert sub.is_horizontal_kerning(False) is False
    assert sub.is_horizontal_kerning(True) is False


def test_vertical_subtable_never_horizontal() -> None:
    sub = KerningSubtable(_FakeFTSub(coverage=0x00))
    assert sub.is_horizontal() is False
    assert sub.is_horizontal_kerning(False) is False
    assert sub.is_horizontal_kerning(True) is False


def test_format_extracted_from_high_byte() -> None:
    # Format 2 subtable, horizontal coverage flag set.
    sub = KerningSubtable(_FakeFTSub(coverage=0x01, fmt=2))
    assert sub.get_format() == 2
    # Coverage word reconstructs to 0x0201 (format 2 in high byte).
    assert sub.get_coverage() == 0x0201


def test_unsupported_format_returns_zero_for_pair_lookups() -> None:
    # Format 2 not yet supported upstream — pairs stays None.
    sub = KerningSubtable(_FakeFTSub(coverage=0x01, fmt=2))
    assert sub.get_kerning(0, 1) == 0


def test_constants_match_upstream() -> None:
    assert KerningSubtable.COVERAGE_HORIZONTAL == 0x0001
    assert KerningSubtable.COVERAGE_MINIMUMS == 0x0002
    assert KerningSubtable.COVERAGE_CROSS_STREAM == 0x0004
    assert KerningSubtable.COVERAGE_FORMAT == 0xFF00
    assert KerningSubtable.COVERAGE_FORMAT_SHIFT == 8


# ---------- pair lookup -----------------------------------------------------


def test_get_kerning_pair_returns_design_unit_value() -> None:
    pairs = {("A", "V"): -100, ("A", "T"): -50}
    sub = KerningSubtable(
        _FakeFTSub(coverage=0x01, pairs=pairs),
        _FakeTTF([".notdef", "A", "V", "T"]),
    )
    assert sub.get_kerning(1, 2) == -100  # A -> V
    assert sub.get_kerning(1, 3) == -50  # A -> T


def test_get_kerning_missing_pair_returns_zero() -> None:
    pairs = {("A", "V"): -100}
    sub = KerningSubtable(
        _FakeFTSub(coverage=0x01, pairs=pairs),
        _FakeTTF([".notdef", "A", "V", "T"]),
    )
    assert sub.get_kerning(2, 1) == 0  # V -> A absent


def test_get_kerning_negative_glyph_id_returns_zero() -> None:
    pairs = {("A", "V"): -100}
    sub = KerningSubtable(
        _FakeFTSub(coverage=0x01, pairs=pairs),
        _FakeTTF([".notdef", "A", "V"]),
    )
    assert sub.get_kerning(-1, 1) == 0
    assert sub.get_kerning(1, -1) == 0


def test_get_kerning_out_of_range_glyph_id_returns_zero() -> None:
    pairs = {("A", "V"): -100}
    sub = KerningSubtable(
        _FakeFTSub(coverage=0x01, pairs=pairs),
        _FakeTTF([".notdef", "A", "V"]),
    )
    assert sub.get_kerning(99, 1) == 0


def test_get_kerning_sequence_returns_per_glyph_adjustments() -> None:
    pairs = {("A", "V"): -100, ("V", "A"): -80}
    sub = KerningSubtable(
        _FakeFTSub(coverage=0x01, pairs=pairs),
        _FakeTTF([".notdef", "A", "V"]),
    )
    # [A, V, A]: A->V, V->A, A->none
    assert sub.get_kerning([1, 2, 1]) == [-100, -80, 0]


def test_get_kerning_sequence_skips_negative_glyphs() -> None:
    pairs = {("A", "V"): -100}
    sub = KerningSubtable(
        _FakeFTSub(coverage=0x01, pairs=pairs),
        _FakeTTF([".notdef", "A", "V"]),
    )
    # [A, -1, V]: A pairs with the next non-negative glyph (V).
    out = sub.get_kerning([1, -1, 2])
    assert out[0] == -100
    assert out[2] == 0


def test_get_kerning_invalid_arity_raises() -> None:
    sub = KerningSubtable(_FakeFTSub(coverage=0x01))
    try:
        sub.get_kerning(1, 2, 3)  # type: ignore[call-arg]
    except TypeError:
        return
    raise AssertionError("expected TypeError for 3-arg get_kerning()")


# ---------- real-font sanity check -----------------------------------------


def test_liberation_sans_subtable_parsable() -> None:
    ttf = TrueTypeFont.from_bytes(FIXTURE.read_bytes())
    kt = ttf.get_kerning_table()
    assert kt is not None
    sub = kt.get_horizontal_kerning_subtable()
    assert sub is not None
    assert sub.is_horizontal()
    assert not sub.is_minimum()
    assert not sub.is_cross_stream()
    assert sub.get_format() == 0


def test_liberation_sans_kerning_av_pair_is_negative() -> None:
    ttf = TrueTypeFont.from_bytes(FIXTURE.read_bytes())
    kt = ttf.get_kerning_table()
    assert kt is not None
    sub = kt.get_horizontal_kerning_subtable()
    assert sub is not None
    glyph_order = ttf._tt.getGlyphOrder()  # noqa: SLF001
    gid_a = glyph_order.index("A")
    gid_v = glyph_order.index("V")
    # A and V kern toward each other in virtually every Latin font.
    assert sub.get_kerning(gid_a, gid_v) < 0


def test_liberation_sans_unrelated_pair_returns_zero() -> None:
    ttf = TrueTypeFont.from_bytes(FIXTURE.read_bytes())
    kt = ttf.get_kerning_table()
    assert kt is not None
    sub = kt.get_horizontal_kerning_subtable()
    assert sub is not None
    # .notdef vs anything is never in the pair table.
    assert sub.get_kerning(0, 1) == 0
