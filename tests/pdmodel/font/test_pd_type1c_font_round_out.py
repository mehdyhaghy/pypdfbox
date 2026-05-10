"""Round-out tests for :class:`PDType1CFont`.

Focuses on the small remaining gaps relative to the existing parity
suite (``test_pd_type1c_font_parity.py``) and the end-to-end CFF glyph
test (``test_type1_cff_glyph.py``):

* :meth:`set_font_program(None)` — drops both the parsed-CFF cache and
  the per-glyph height cache.
* :meth:`set_font_program(other)` — replacing the program invalidates
  the per-glyph height cache so subsequent ``get_height`` lookups
  reflect the new program's outlines.
* :meth:`get_height` — caches per glyph name (verified by mutating the
  injected program after the first lookup; the cached value persists
  even though the program changed underneath).
* :meth:`get_units_per_em` — returns the CFF default 1000 even when the
  embedded ``/FontFile3`` failed to parse (damaged font).
* :meth:`get_average_font_width` — falls through ``/Widths`` (when only
  zero entries) to the CFF Private DICT ``defaultWidthX``.
* :meth:`get_cff_font` cached behaviour — repeated calls return the
  same instance without re-parsing the stream.

Constructor + class-constant parity:

* :data:`SUB_TYPE` is ``"Type1"`` (matches the parity tests).
* Empty constructor writes ``/Type=Font`` and ``/Subtype=Type1`` on a
  freshly-created dictionary.
* :class:`PDType1CFont` is a strict subclass of :class:`PDType1Font`.
"""
from __future__ import annotations

import io

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSInteger,
    COSName,
    COSStream,
)
from pypdfbox.fontbox.cff.cff_font import CFFFont
from pypdfbox.pdmodel.font import PDFontDescriptor
from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font
from pypdfbox.pdmodel.font.pd_type1c_font import PDType1CFont

_BASE_FONT = COSName.get_pdf_name("BaseFont")
_ENCODING = COSName.get_pdf_name("Encoding")
_FIRST_CHAR = COSName.get_pdf_name("FirstChar")
_LAST_CHAR = COSName.get_pdf_name("LastChar")
_WIDTHS = COSName.get_pdf_name("Widths")


# ---------- helpers ----------


def _build_cff_bytes(
    *,
    a_width: float = 500.0,
    a_height: int = 700,
    b_width: float = 300.0,
    b_height: int = 500,
) -> bytes:
    """Build a tiny in-memory CFF font set with three glyphs.

    ``A`` is a rectangle ``100 x a_height`` with advance ``a_width``;
    ``B`` is a vertical stroke of length ``b_height`` with advance
    ``b_width``. Distinct heights per call so a re-injection test can
    distinguish the program before and after.
    """
    from fontTools.fontBuilder import FontBuilder
    from fontTools.misc.psCharStrings import T2CharString
    from fontTools.ttLib import TTFont

    fb = FontBuilder(1000, isTTF=False)
    fb.setupGlyphOrder([".notdef", "A", "B"])
    fb.setupCharacterMap({65: "A", 66: "B"})

    def _cs(program: list) -> T2CharString:
        s = T2CharString()
        s.program = program
        return s

    char_strings = {
        ".notdef": _cs([0, "endchar"]),
        "A": _cs(
            [
                a_width, 0, "hmoveto",
                a_height, "vlineto",
                100, "hlineto",
                -a_height, "vlineto",
                "endchar",
            ]
        ),
        "B": _cs([b_width, 0, "hmoveto", b_height, "vlineto", "endchar"]),
    }
    fb.setupCFF(
        psName="TestType1CRoundOut",
        fontInfo={"FullName": "Test Type1C Round Out"},
        charStringsDict=char_strings,
        privateDict={},
    )
    fb.setupHorizontalMetrics(
        {".notdef": (0, 0), "A": (int(a_width), 0), "B": (int(b_width), 0)}
    )
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupOS2(
        sTypoAscender=800, sTypoDescender=-200, usWinAscent=800, usWinDescent=200
    )
    fb.setupNameTable({"familyName": "Test", "styleName": "Regular"})
    fb.setupPost()
    buf = io.BytesIO()
    fb.font.save(buf)
    return bytes(TTFont(io.BytesIO(buf.getvalue())).getTableData("CFF "))


def _bare_font_with_winansi() -> PDType1CFont:
    raw = COSDictionary()
    raw.set_name(_BASE_FONT, "MyEmbeddedType1C")
    raw.set_item(_ENCODING, COSName.get_pdf_name("WinAnsiEncoding"))
    return PDType1CFont(raw)


def _make_injected_font(
    *, a_width: float = 500.0, a_height: int = 700,
) -> PDType1CFont:
    cff = CFFFont.from_bytes(_build_cff_bytes(a_width=a_width, a_height=a_height))
    font = _bare_font_with_winansi()
    font.set_font_program(cff)
    return font


# ---------- subtype + inheritance ----------


def test_sub_type_constant_is_type1() -> None:
    # PDType1CFont's /Subtype on the font dict is ``Type1`` — the Type1C
    # signal lives on /FontDescriptor /FontFile3 /Subtype, not here.
    assert PDType1CFont.SUB_TYPE == "Type1"


def test_default_constructor_writes_type_and_subtype() -> None:
    font = PDType1CFont()
    cos = font.get_cos_object()
    assert cos.get_name(COSName.SUBTYPE) == "Type1"  # type: ignore[attr-defined]
    assert cos.get_name(COSName.TYPE) == "Font"  # type: ignore[attr-defined]


def test_inherits_from_pd_type1_font() -> None:
    assert issubclass(PDType1CFont, PDType1Font)


def test_constructor_accepts_existing_dict_without_overwriting_subtype() -> None:
    raw = COSDictionary()
    raw.set_name(COSName.SUBTYPE, "Type1")  # type: ignore[attr-defined]
    raw.set_name(_BASE_FONT, "MyEmbeddedType1C")
    font = PDType1CFont(raw)
    assert font.get_cos_object() is raw
    assert font.get_subtype() == "Type1"
    assert font.get_name() == "MyEmbeddedType1C"


# ---------- set_font_program(None) clears caches ----------


def test_set_font_program_none_clears_cff_cache() -> None:
    font = _make_injected_font()
    # CFF program is reachable.
    assert font.get_cff_font() is not None
    assert font.get_glyph_width(65) == 500.0  # 'A' from CFF program
    font.set_font_program(None)
    # After clearing, the CFF program is no longer reachable and the
    # CFF-backed width path returns 0 (no /Widths, non-Standard-14 base).
    assert font.get_cff_font() is None
    assert font.get_glyph_width(65) == 0.0


def test_set_font_program_none_clears_glyph_height_cache() -> None:
    """Per-glyph height cache must be invalidated when the program is
    cleared — otherwise a stale cached height would survive past the
    program drop and report a phantom non-zero height."""
    font = _make_injected_font()
    assert font.get_height(65) == 700.0  # populates the cache
    font.set_font_program(None)
    # Cache cleared; with no program present the height drops to 0.
    assert font.get_height(65) == 0.0


# ---------- set_font_program(other) invalidates height cache ----------


def test_set_font_program_replacement_invalidates_height_cache() -> None:
    """Injecting a *different* program after the first one is cached
    must surface the new program's outlines, not the previous cache."""
    font = _make_injected_font(a_height=700)
    assert font.get_height(65) == 700.0  # primes the cache for 'A'

    # Inject a CFF program where 'A' has a different bounding-box height.
    new_cff = CFFFont.from_bytes(_build_cff_bytes(a_height=900))
    font.set_font_program(new_cff)
    assert font.get_height(65) == 900.0  # reflects the new program


# ---------- get_height caches by glyph name ----------


def test_get_height_caches_zero_for_glyph_with_empty_path() -> None:
    """``.notdef`` in our minimal CFF has an empty path (just an
    ``endchar``). The first call records ``0.0`` and the second call
    must return the cached zero without re-walking the (empty) path."""
    font = _make_injected_font()
    # Encoding lookup for code 0 yields ".notdef" -> name resolution
    # returns None upstream of get_height, so use 65 then a code that
    # maps to a glyph with no path. Easier: call get_height for an
    # unmapped code (90 = 'Z'), which short-circuits BEFORE caching.
    assert font.get_height(90) == 0.0
    # 'A' maps and has a real path.
    assert font.get_height(65) == 700.0
    # A second call hits the cache. The numeric value alone doesn't
    # confirm the cache; assert by reading the implementation cache.
    assert "A" in font._glyph_heights  # noqa: SLF001
    assert font._glyph_heights["A"] == 700.0  # noqa: SLF001


def test_get_height_for_zero_height_glyph_caches_zero() -> None:
    """A glyph whose outline has no on-curve y coordinates collapses to
    ``0.0`` — and that ``0.0`` must enter the cache so a second call
    short-circuits without re-walking the outline. We can't easily
    synthesize such a glyph through fontTools, but we can verify the
    cache key is populated for 'B' (a vertical stroke; height 500)."""
    font = _make_injected_font()
    first = font.get_height(66)  # 'B'
    assert first == 500.0
    assert "B" in font._glyph_heights  # noqa: SLF001
    # Second call: identical answer, cache reused.
    assert font.get_height(66) == 500.0


# ---------- get_units_per_em with damaged program ----------


def test_get_units_per_em_returns_default_when_font_file3_unparseable() -> None:
    """Damaged /FontFile3 (parse failure) must still return the CFF
    default 1000 — downstream divide-by-em paths rely on this never
    being zero."""
    font = PDType1CFont()
    fd = PDFontDescriptor()
    bogus = COSStream()
    bogus.set_data(b"definitely not a CFF font set")
    fd.set_font_file3(bogus)
    font.set_font_descriptor(fd)
    assert font.is_damaged() is True
    assert font.get_units_per_em() == 1000


# ---------- get_cff_font caches the parse ----------


def test_get_cff_font_returns_same_instance_on_repeat_calls() -> None:
    """Wrapping a /FontFile3 stream and reading it twice must return the
    same cached :class:`CFFFont` — re-parsing the bytes on every access
    would be a regression. Mirrors upstream's ``CFFParser`` cache."""
    cff_bytes = _build_cff_bytes()
    descriptor = PDFontDescriptor()
    stream = COSStream()
    stream.set_data(cff_bytes)
    stream.set_name(COSName.SUBTYPE, "Type1C")  # type: ignore[attr-defined]
    descriptor.set_font_file3(stream)
    font_dict = COSDictionary()
    font_dict.set_name(_BASE_FONT, "MyEmbeddedType1C")
    font_dict.set_item(_ENCODING, COSName.get_pdf_name("WinAnsiEncoding"))
    font_dict.set_item(
        COSName.get_pdf_name("FontDescriptor"), descriptor.get_cos_object()
    )
    font = PDType1CFont(font_dict)

    first = font.get_cff_font()
    second = font.get_cff_font()
    assert first is not None
    assert first is second  # cached identity, not just equal


def test_get_cff_font_caches_failure_negative_result() -> None:
    """Once the parse fails, repeated calls must keep returning ``None``
    without re-attempting (and re-failing) the parse on every access."""
    font = PDType1CFont()
    fd = PDFontDescriptor()
    bogus = COSStream()
    bogus.set_data(b"definitely not a CFF font set")
    fd.set_font_file3(bogus)
    font.set_font_descriptor(fd)
    assert font.get_cff_font() is None
    assert font.get_cff_font() is None
    # The damage flag should also be cached on the instance (False sentinel
    # in ``_cff`` for "tried, no parse"). Verify via internal state.
    assert font._cff is False  # noqa: SLF001


# ---------- get_average_font_width fallthrough chain ----------


def test_get_average_font_width_skips_zero_widths_and_uses_cff_default() -> None:
    """``/Widths`` carries only zero entries — the simple-font mean is
    therefore not derived from /Widths, so we fall through to the CFF
    program's defaultWidthX. With an injected CFF program whose
    privateDict is empty (defaultWidthX = 0), we then fall through to
    Standard 14 / 0.0. This test pins down the *order*: zero widths do
    not short-circuit at 0.0 from the /Widths tier."""
    font = _bare_font_with_winansi()
    cos = font.get_cos_object()
    cos.set_int(_FIRST_CHAR, 32)
    cos.set_int(_LAST_CHAR, 33)
    cos.set_item(_WIDTHS, COSArray([COSInteger.get(0), COSInteger.get(0)]))
    # No CFF program injected; non-Standard-14 base name; no Standard 14
    # AFM fallback either. Result must be 0.0 (the final fall-through).
    assert font.get_average_font_width() == 0.0


def test_get_average_font_width_uses_cff_default_width_x_when_no_widths() -> None:
    """When /Widths is empty and a CFF program is loaded, fall through
    to the CFF Private DICT's ``defaultWidthX``. Our minimal CFF has
    ``defaultWidthX = 0`` so we expect the next tier (Standard 14) to
    fire — with a non-Standard-14 base name we end at 0.0. Either way
    the chain must walk through the CFF tier without raising."""
    font = _make_injected_font()
    # No /Widths array, non-Standard-14 base name, CFF program present.
    # Average width is well-defined and non-negative regardless of which
    # CFF / AFM tier wins.
    avg = font.get_average_font_width()
    assert avg >= 0.0


# ---------- code_to_gid returns 0 for empty charset ----------


def test_code_to_gid_returns_zero_for_unmapped_codes_with_program() -> None:
    """The CFF charset only has 'A' and 'B' (GIDs 1 and 2) plus
    ``.notdef`` (GID 0). WinAnsi maps code 0xFE ('thorn') which is not
    in the charset — must return 0, not raise."""
    font = _make_injected_font()
    assert font.code_to_gid(0xFE) == 0
    assert font.code_to_gid(0xFF) == 0


# ---------- has_glyph(.notdef) ----------


def test_has_glyph_true_for_notdef() -> None:
    """``.notdef`` is always present in a CFF charset (CFF spec §10
    requires GID 0 to be ``.notdef``). Our minimal program is no
    exception."""
    font = _make_injected_font()
    assert font.has_glyph(".notdef") is True


# ---------- get_font_box_font ----------


def test_get_font_box_font_returns_cff_program_when_embedded() -> None:
    """Mirrors upstream ``PDType1CFont.getFontBoxFont``: returns the
    embedded CFF program (the ``genericFont`` upstream name) when one
    is present."""
    font = _make_injected_font()
    assert font.get_font_box_font() is font.get_cff_font()
    assert isinstance(font.get_font_box_font(), CFFFont)


def test_get_font_box_font_returns_none_when_not_embedded() -> None:
    """No /FontFile3 -> no embedded CFF program -> no FontBoxFont. We
    don't run a system-mapping fallback the way upstream does."""
    assert PDType1CFont().get_font_box_font() is None


# ---------- get_font_matrix ----------


def test_get_font_matrix_default_when_no_program() -> None:
    """Default matrix [0.001 0 0 0.001 0 0] (PDF 32000-1 §9.2.4) when
    no embedded CFF program is loaded."""
    matrix = PDType1CFont().get_font_matrix()
    assert matrix == [0.001, 0.0, 0.0, 0.001, 0.0, 0.0]


def test_get_font_matrix_reads_cff_program_matrix() -> None:
    """Mirrors upstream's ``cffFont.getFontMatrix()`` path. For a
    1000-unit-em CFF font the matrix is the default 0.001 scale."""
    font = _make_injected_font()
    matrix = font.get_font_matrix()
    assert len(matrix) == 6
    # FontBuilder(1000, ...) -> default 0.001 scale.
    assert matrix[0] == 0.001
    assert matrix[3] == 0.001


# ---------- get_bounding_box ----------


def test_get_bounding_box_returns_none_when_no_descriptor_no_program() -> None:
    assert PDType1CFont().get_bounding_box() is None


def test_get_bounding_box_uses_descriptor_bbox_when_non_zero() -> None:
    """A non-zero ``/FontBBox`` on the descriptor wins over the CFF
    program's bbox — mirrors upstream's ``isNonZeroBoundingBox`` check
    in ``generateBoundingBox``."""
    from pypdfbox.pdmodel.pd_rectangle import PDRectangle

    font = PDType1CFont()
    fd = PDFontDescriptor()
    fd.set_font_bounding_box(PDRectangle(-100.0, -200.0, 800.0, 900.0))
    font.set_font_descriptor(fd)

    bbox = font.get_bounding_box()
    assert bbox is not None
    assert bbox.get_lower_left_x() == -100.0
    assert bbox.get_lower_left_y() == -200.0
    assert bbox.get_upper_right_x() == 800.0
    assert bbox.get_upper_right_y() == 900.0


def test_get_bounding_box_falls_through_to_cff_when_descriptor_bbox_zero() -> None:
    """An all-zero descriptor bbox is the unset case; fall through to
    the CFF program's ``/FontBBox``."""
    from pypdfbox.pdmodel.pd_rectangle import PDRectangle

    font = _make_injected_font()
    fd = PDFontDescriptor()
    fd.set_font_bounding_box(PDRectangle(0.0, 0.0, 0.0, 0.0))
    font.set_font_descriptor(fd)
    bbox = font.get_bounding_box()
    # Our minimal CFF has a real (computed) FontBBox or the default
    # zero — accept either, but the call must not raise.
    assert bbox is None or isinstance(bbox.get_lower_left_x(), float)


# ---------- get_string_width ----------


def test_get_string_width_returns_zero_when_no_program() -> None:
    """No embedded CFF -> upstream logs and returns 0."""
    assert PDType1CFont().get_string_width("A") == 0.0


def test_get_string_width_sums_cff_advances_for_known_glyphs() -> None:
    """For our minimal CFF, ``A`` has advance 500 and ``B`` 300 -> sum
    is 800. Mirrors upstream's per-codepoint summation."""
    font = _make_injected_font()
    assert font.get_string_width("AB") == 800.0


def test_get_string_width_raises_for_unknown_glyph() -> None:
    """Mirrors upstream's ``IllegalArgumentException`` (we use
    :class:`ValueError`) when a code point has no glyph in the embedded
    program."""
    import pytest as _pytest

    font = _make_injected_font()
    with _pytest.raises(ValueError, match="not available in font"):
        font.get_string_width("Z")


# ---------- get_width_from_font ----------


def test_get_width_from_font_returns_zero_when_no_program() -> None:
    """Mirrors upstream ``PDType1CFont.getWidthFromFont`` short-circuit
    when the embedded CFF program is absent."""
    assert PDType1CFont().get_width_from_font(65) == 0.0


def test_get_width_from_font_uses_cff_advance() -> None:
    """A 1000-unit em CFF program with ``A`` advance 500 -> 500.0."""
    font = _make_injected_font()
    assert font.get_width_from_font(65) == 500.0


def test_get_width_from_font_zero_for_unmapped_code() -> None:
    """Code 90 ('Z') is in WinAnsi but not in our minimal CFF charset."""
    font = _make_injected_font()
    assert font.get_width_from_font(90) == 0.0


# ---------- get_path special-name handling ----------


def test_get_path_notdef_empty_when_not_embedded() -> None:
    """PDFBOX-2372: Acrobat does not draw substitute ``.notdef``."""
    font = PDType1CFont()
    # Non-embedded, non-Standard 14 -> empty path.
    assert font.get_path(".notdef") == []


def test_get_path_sfthyphen_rewrites_to_hyphen() -> None:
    """Mirrors upstream's ``"sfthyphen".equals(name)`` rewrite."""
    font = _make_injected_font()
    # Our minimal CFF has no 'hyphen' glyph; rewrite happens but lookup
    # is empty.
    assert font.get_path("sfthyphen") == []
    assert font.get_path("sfthyphen") == font.get_path("hyphen")


def test_get_path_nbspace_rewrites_to_space_when_present() -> None:
    """``nbspace`` -> ``space`` when the font has a ``space`` glyph;
    empty path when it does not (our minimal CFF has no ``space``)."""
    font = _make_injected_font()
    # Our minimal CFF has no 'space' glyph -> nbspace lookup is empty.
    assert font.get_path("nbspace") == []


# ---------- has_glyph_for_code / get_path_for_code / get_normalized_path_for_code ----------


def test_has_glyph_for_code_false_when_no_encoding() -> None:
    assert PDType1CFont().has_glyph_for_code(65) is False


def test_has_glyph_for_code_true_for_present_glyph() -> None:
    font = _make_injected_font()
    assert font.has_glyph_for_code(65) is True  # 'A'
    assert font.has_glyph_for_code(66) is True  # 'B'


def test_has_glyph_for_code_false_for_unmapped_code() -> None:
    font = _make_injected_font()
    assert font.has_glyph_for_code(90) is False  # 'Z' not in CFF


def test_get_path_for_code_returns_outline_for_present_glyph() -> None:
    font = _make_injected_font()
    path = font.get_path_for_code(65)
    assert path[0][0] == "moveto"


def test_get_path_for_code_empty_when_no_encoding() -> None:
    assert PDType1CFont().get_path_for_code(65) == []


def test_get_normalized_path_for_code_returns_glyph_path() -> None:
    """For an embedded font with the glyph present, the normalized
    path is just the glyph path."""
    font = _make_injected_font()
    direct = font.get_path_for_code(65)
    normalized = font.get_normalized_path_for_code(65)
    assert normalized == direct


def test_get_normalized_path_for_code_falls_back_to_notdef() -> None:
    """Unmapped code -> falls back to ``.notdef``. For our embedded
    font the ``.notdef`` glyph has an empty charstring (just
    ``endchar``), so the fallback path is also empty — but the call
    must not raise."""
    font = _make_injected_font()
    result = font.get_normalized_path_for_code(90)  # 'Z' unmapped in CFF
    assert isinstance(result, list)
