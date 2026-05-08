"""Hand-written tests for the round-out of :class:`PDCIDFontType2`.

Covers the embedded-program metric path (``get_height``,
``get_width_from_font``, ``get_average_font_width``,
``get_bounding_box``, ``get_font_matrix``), the ``/FontFile3`` and
legacy ``/FontFile`` fallbacks for :meth:`is_embedded` /
:meth:`get_true_type_font`, and the :meth:`is_damaged` semantics.

The fontTools-backed paths use a synthetic stand-in TTF (object with
the attributes / methods PDCIDFontType2 reads) to keep the tests
hermetic — exercising the true bytes-to-glyph chain belongs in the
fontbox/ttf cluster.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from pypdfbox.cos import COSArray, COSFloat, COSName, COSStream
from pypdfbox.pdmodel.font.pd_cid_font_type2 import PDCIDFontType2
from pypdfbox.pdmodel.font.pd_font_descriptor import PDFontDescriptor

# ---------- synthetic TTF stand-in ----------


class _StubGlyph:
    def __init__(self, y_min: int, y_max: int) -> None:
        self.yMin = y_min  # noqa: N815 — fontTools attribute name
        self.yMax = y_max  # noqa: N815 — fontTools attribute name


class _StubGlyfTable:
    def __init__(self, glyphs: dict[str, _StubGlyph]) -> None:
        self._glyphs = glyphs

    def __getitem__(self, name: str) -> _StubGlyph:
        return self._glyphs[name]


class _StubTTInner:
    """Minimal fontTools-shaped object — provides ``head``, ``glyf``,
    and ``getGlyphOrder`` exactly the way ``PDCIDFontType2`` reads them."""

    def __init__(
        self,
        glyph_order: list[str],
        glyphs: dict[str, _StubGlyph],
        head: SimpleNamespace,
    ) -> None:
        self._order = glyph_order
        self._tables = {"glyf": _StubGlyfTable(glyphs), "head": head}

    def __contains__(self, key: str) -> bool:
        return key in self._tables

    def __getitem__(self, key: str) -> Any:
        return self._tables[key]

    def getGlyphOrder(self) -> list[str]:  # noqa: N802 — fontTools name
        return self._order


class _StubTTF:
    """Stand-in for a parsed fontTools TrueTypeFont. Provides the
    upstream-shaped accessors PDCIDFontType2 calls into."""

    def __init__(
        self,
        units_per_em: int,
        advance_widths: list[int],
        glyph_order: list[str],
        glyphs: dict[str, _StubGlyph],
        head_bbox: tuple[float, float, float, float] | None = None,
    ) -> None:
        self._units_per_em = units_per_em
        self._advances = list(advance_widths)
        head_attrs: dict[str, float] = {}
        if head_bbox is not None:
            x_min, y_min, x_max, y_max = head_bbox
            head_attrs.update(xMin=x_min, yMin=y_min, xMax=x_max, yMax=y_max)
        self._tt = _StubTTInner(glyph_order, glyphs, SimpleNamespace(**head_attrs))

    def get_units_per_em(self) -> int:
        return self._units_per_em

    def get_advance_width(self, gid: int) -> int:
        if 0 <= gid < len(self._advances):
            return self._advances[gid]
        return self._advances[-1] if self._advances else 0

    @property
    def advance_widths(self) -> list[int]:
        return self._advances


def _make_font_with_stub_ttf(stub: _StubTTF) -> PDCIDFontType2:
    """Bypass the ``isinstance(TrueTypeFont)`` guard in
    ``get_true_type_font`` by patching the descriptor's ``/FontFile2``
    parse step to return the stub. The stub satisfies the duck-typed
    accessors PDCIDFontType2 invokes on the parsed program; using a
    real TrueTypeFont would force every metric test to ship a full
    SFNT fixture."""
    font = PDCIDFontType2()
    # ``get_true_type_font`` short-circuits when ``_ttf`` is already a
    # TrueTypeFont; we monkey-patch the cache slot via a thin shim that
    # returns the stub for the duration of the test instance.
    def get_stub_ttf() -> _StubTTF:
        return stub

    font.get_true_type_font = get_stub_ttf  # type: ignore[assignment,method-assign]
    return font


# ---------- get_width_from_font ----------


def test_get_width_from_font_zero_when_no_program() -> None:
    font = PDCIDFontType2()
    assert font.get_width_from_font(0) == 0.0


def test_get_width_from_font_uses_embedded_hmtx_scaled_to_1000() -> None:
    # 2048 upem (typical TrueType) → advance 1024 scales to 500.
    stub = _StubTTF(
        units_per_em=2048,
        advance_widths=[1024, 2048, 0, 4096],
        glyph_order=[".notdef", "A", "B", "C"],
        glyphs={},
    )
    font = _make_font_with_stub_ttf(stub)
    # Identity /CIDToGIDMap → cid == gid. CID 0 → 500, CID 1 → 1000, CID 3 → 2000.
    assert font.get_width_from_font(0) == pytest.approx(500.0)
    assert font.get_width_from_font(1) == pytest.approx(1000.0)
    assert font.get_width_from_font(3) == pytest.approx(2000.0)


def test_get_width_from_font_zero_for_zero_units_per_em() -> None:
    stub = _StubTTF(
        units_per_em=0,
        advance_widths=[500],
        glyph_order=[".notdef"],
        glyphs={},
    )
    font = _make_font_with_stub_ttf(stub)
    assert font.get_width_from_font(0) == 0.0


# ---------- get_height (embedded glyf yMax-yMin scaled) ----------


def test_get_height_uses_embedded_glyf_extent_scaled_to_1000() -> None:
    glyphs = {
        ".notdef": _StubGlyph(0, 0),
        "A": _StubGlyph(0, 1024),  # half upem -> 500 in 1000-space
        "B": _StubGlyph(-256, 1024),  # 1280 / 2048 * 1000 = 625.0
    }
    stub = _StubTTF(
        units_per_em=2048,
        advance_widths=[0, 0, 0],
        glyph_order=[".notdef", "A", "B"],
        glyphs=glyphs,
    )
    font = _make_font_with_stub_ttf(stub)
    assert font.get_height(1) == pytest.approx(500.0)
    assert font.get_height(2) == pytest.approx(625.0)


def test_get_height_zero_for_notdef_when_no_w2() -> None:
    glyphs = {".notdef": _StubGlyph(0, 0), "A": _StubGlyph(0, 700)}
    stub = _StubTTF(
        units_per_em=1000,
        advance_widths=[0, 0],
        glyph_order=[".notdef", "A"],
        glyphs=glyphs,
    )
    font = _make_font_with_stub_ttf(stub)
    # GID 0 -> falls back to /W2 (empty) -> 0.0.
    assert font.get_height(0) == 0.0


def test_get_height_falls_back_to_w2_when_no_program() -> None:
    font = PDCIDFontType2()
    # Construct a /W2 entry that the parent will surface for cid=5.
    arr = COSArray()
    arr.add(COSFloat(5))
    arr.add(COSFloat(5))
    arr.add(COSFloat(900))  # w1y -- the height.
    arr.add(COSFloat(500))  # v_x
    arr.add(COSFloat(880))  # v_y
    font.set_w2(arr)
    assert font.get_height(5) == pytest.approx(900.0)
    # Out-of-range -> 0.0 (parent default).
    assert font.get_height(99) == 0.0


# ---------- get_average_font_width ----------


def test_get_average_font_width_skips_zero_advances() -> None:
    stub = _StubTTF(
        units_per_em=1000,
        advance_widths=[0, 500, 0, 700, 1000],  # mean of {500, 700, 1000}
        glyph_order=[".notdef", "a", "b", "c", "d"],
        glyphs={},
    )
    font = _make_font_with_stub_ttf(stub)
    assert font.get_average_font_width() == pytest.approx((500 + 700 + 1000) / 3.0)


def test_get_average_font_width_falls_back_to_dw_when_no_program() -> None:
    font = PDCIDFontType2()
    font.set_dw(820)
    assert font.get_average_font_width() == pytest.approx(820.0)


# ---------- get_font_matrix ----------


def test_get_font_matrix_uses_embedded_units_per_em() -> None:
    stub = _StubTTF(
        units_per_em=2048,
        advance_widths=[0],
        glyph_order=[".notdef"],
        glyphs={},
    )
    font = _make_font_with_stub_ttf(stub)
    matrix = font.get_font_matrix()
    assert matrix[0] == pytest.approx(1.0 / 2048)
    assert matrix[3] == pytest.approx(1.0 / 2048)
    assert matrix[1] == 0.0 == matrix[2] == matrix[4] == matrix[5]


def test_get_font_matrix_defaults_to_1000_when_no_program() -> None:
    font = PDCIDFontType2()
    matrix = font.get_font_matrix()
    assert matrix == [0.001, 0.0, 0.0, 0.001, 0.0, 0.0]


def test_get_font_matrix_recovers_when_units_per_em_zero() -> None:
    stub = _StubTTF(
        units_per_em=0,
        advance_widths=[0],
        glyph_order=[".notdef"],
        glyphs={},
    )
    font = _make_font_with_stub_ttf(stub)
    matrix = font.get_font_matrix()
    # 0 upem from a stub -> fall back to 1000 (avoid div-by-zero).
    assert matrix[0] == pytest.approx(0.001)


# ---------- get_bounding_box ----------


def test_get_bounding_box_uses_embedded_head_when_program_present() -> None:
    stub = _StubTTF(
        units_per_em=1000,
        advance_widths=[0],
        glyph_order=[".notdef"],
        glyphs={},
        head_bbox=(-100.0, -200.0, 1100.0, 900.0),
    )
    font = _make_font_with_stub_ttf(stub)
    bbox = font.get_bounding_box()
    assert bbox is not None
    assert bbox.lower_left_x == pytest.approx(-100.0)
    assert bbox.lower_left_y == pytest.approx(-200.0)
    assert bbox.upper_right_x == pytest.approx(1100.0)
    assert bbox.upper_right_y == pytest.approx(900.0)


def test_get_bounding_box_falls_back_to_descriptor_when_no_program() -> None:
    font = PDCIDFontType2()
    fd = PDFontDescriptor()
    bbox_arr = COSArray()
    for v in (-50, -25, 1050, 950):
        bbox_arr.add(COSFloat(v))
    fd.set_font_b_box(bbox_arr)
    font.set_font_descriptor(fd)
    bbox = font.get_bounding_box()
    assert bbox is not None
    assert bbox.lower_left_x == pytest.approx(-50.0)
    assert bbox.upper_right_x == pytest.approx(1050.0)


def test_get_bounding_box_none_when_neither_source() -> None:
    font = PDCIDFontType2()
    assert font.get_bounding_box() is None


# ---------- embedded program stream fallbacks ----------


def test_is_embedded_true_for_font_file3_open_type() -> None:
    font = PDCIDFontType2()
    fd = PDFontDescriptor()
    stream = COSStream()
    stream.set_name(COSName.SUBTYPE, "OpenType")  # type: ignore[attr-defined]
    fd.set_font_file3(stream)
    font.set_font_descriptor(fd)
    assert font.is_embedded() is True


def test_is_embedded_true_for_font_file3_unknown_subtype() -> None:
    # Upstream probes FontFile3 as an embedded OTF candidate without
    # rejecting unknown /Subtype values up front.
    font = PDCIDFontType2()
    fd = PDFontDescriptor()
    stream = COSStream()
    stream.set_name(COSName.SUBTYPE, "CIDFontType0C")  # type: ignore[attr-defined]
    fd.set_font_file3(stream)
    font.set_font_descriptor(fd)
    assert font.is_embedded() is True


def test_is_embedded_true_for_legacy_font_file() -> None:
    # Acrobat/PDFBox tolerate legacy /FontFile here for malformed Type2
    # descendants (PDFBOX-2599).
    font = PDCIDFontType2()
    fd = PDFontDescriptor()
    fd.set_font_file(COSStream())
    font.set_font_descriptor(fd)
    assert font.is_embedded() is True


def test_get_true_type_font_falls_back_to_font_file3_open_type() -> None:
    # FontFile3 with /Subtype /OpenType but unparseable bytes -> None
    # (logged), confirming we *did* try the FontFile3 path.
    font = PDCIDFontType2()
    fd = PDFontDescriptor()
    stream = COSStream()
    stream.set_name(COSName.SUBTYPE, "OpenType")  # type: ignore[attr-defined]
    stream.set_data(b"not-a-real-otf")
    fd.set_font_file3(stream)
    font.set_font_descriptor(fd)
    assert font.get_true_type_font() is None
    # Sentinel set: "tried, parse failed".
    assert font._ttf is False  # noqa: SLF001


def test_get_true_type_font_tries_font_file3_without_open_type_subtype() -> None:
    font = PDCIDFontType2()
    fd = PDFontDescriptor()
    stream = COSStream()
    stream.set_name(COSName.SUBTYPE, "CIDFontType0C")  # type: ignore[attr-defined]
    stream.set_data(b"not-a-real-otf")
    fd.set_font_file3(stream)
    font.set_font_descriptor(fd)
    assert font.get_true_type_font() is None
    assert font._ttf is False  # noqa: SLF001


def test_get_true_type_font_falls_back_to_legacy_font_file() -> None:
    font = PDCIDFontType2()
    fd = PDFontDescriptor()
    stream = COSStream()
    stream.set_data(b"not-a-real-ttf")
    fd.set_font_file(stream)
    font.set_font_descriptor(fd)
    assert font.get_true_type_font() is None
    assert font._ttf is False  # noqa: SLF001


# ---------- is_damaged ----------


def test_is_damaged_false_when_not_embedded() -> None:
    font = PDCIDFontType2()
    assert font.is_damaged() is False


def test_is_damaged_false_for_descriptor_without_program() -> None:
    font = PDCIDFontType2()
    font.set_font_descriptor(PDFontDescriptor())
    assert font.is_damaged() is False


def test_is_damaged_true_when_font_file2_unparseable() -> None:
    font = PDCIDFontType2()
    fd = PDFontDescriptor()
    stream = COSStream()
    stream.set_data(b"definitely-not-a-ttf")
    fd.set_font_file2(stream)
    font.set_font_descriptor(fd)
    assert font.is_damaged() is True


def test_is_damaged_false_when_program_parses_ok() -> None:
    # Inject a stub TTF -- the lazy parse never runs and the cache
    # holds a real object, so is_damaged stays False.
    font = PDCIDFontType2()
    fd = PDFontDescriptor()
    fd.set_font_file2(COSStream())
    font.set_font_descriptor(fd)
    stub = _StubTTF(
        units_per_em=1000,
        advance_widths=[0],
        glyph_order=[".notdef"],
        glyphs={},
    )
    font.set_true_type_font(stub)  # type: ignore[arg-type]
    assert font.is_damaged() is False


# ---------- has_glyph (embedded path) ----------


def test_has_glyph_true_for_non_zero_gid_when_embedded() -> None:
    stub = _StubTTF(
        units_per_em=1000,
        advance_widths=[0, 500],
        glyph_order=[".notdef", "A"],
        glyphs={},
    )
    font = _make_font_with_stub_ttf(stub)
    # Identity map -> cid 1 -> gid 1 -> True; cid 0 -> gid 0 -> False.
    assert font.has_glyph(1) is True
    assert font.has_glyph(0) is False
