"""Tests ported from upstream ``PDCIDFontType2Test``.

Upstream Java path:
``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/font/PDCIDFontType2Test.java``.

Upstream coverage focuses on three loading paths:
* identity ``/CIDToGIDMap`` round-trip via ``codeToGID`` / ``codeToCID``,
* descriptor-driven embedding via ``/FontFile2`` (``isEmbedded`` /
  ``getTrueTypeFont``), and
* metric retrieval (``getHeight``, ``getWidthFromFont``,
  ``getAverageFontWidth``, ``getFontMatrix``, ``getBoundingBox``)
  with and without an embedded program.

The two SFNT-byte-driven tests at the bottom of this file
(``test_horizontal_metrics_via_cmap`` and
``test_cid_to_gid_map_with_glyphs_through_load``) exercise the same
upstream code paths using the bundled ``LiberationSans-Regular.ttf``
fixture rather than the on-demand downloads upstream pulls into
``target/fonts`` — they cover the cmap-driven ``/W``/``getHeight``
fallback and the ``/CIDToGIDMap`` -> ``cid_to_gid`` round-trip,
respectively.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.cos import COSArray, COSFloat, COSName, COSStream
from pypdfbox.fontbox.ttf import OTFParser, TrueTypeFont, TTFParser
from pypdfbox.pdmodel.font.pd_cid_font_type2 import PDCIDFontType2
from pypdfbox.pdmodel.font.pd_font_descriptor import PDFontDescriptor

_TTF_FIXTURE = (
    Path(__file__).parent.parent.parent.parent
    / "tests"
    / "fixtures"
    / "fontbox"
    / "ttf"
    / "LiberationSans-Regular.ttf"
)
# The path above resolves from .../tests/pdmodel/font/upstream/ — climb
# four parents to the project root, then re-descend into tests/fixtures.
if not _TTF_FIXTURE.exists():  # pragma: no cover - defensive
    _TTF_FIXTURE = (
        Path(__file__).resolve().parents[3]
        / "fixtures"
        / "fontbox"
        / "ttf"
        / "LiberationSans-Regular.ttf"
    )


def _load_liberation_bytes() -> bytes:
    return _TTF_FIXTURE.read_bytes()


def _build_embedded_font(
    *, cid_to_gid_map: COSStream | str | None = None
) -> PDCIDFontType2:
    """Build a PDCIDFontType2 whose ``/FontFile2`` carries the bundled
    Liberation Sans Regular fixture. Pre-parses the SFNT once and
    injects it so :meth:`get_true_type_font` returns immediately.
    """
    raw = _load_liberation_bytes()
    font = PDCIDFontType2()
    fd = PDFontDescriptor()
    program_stream = COSStream()
    program_stream.set_data(raw)
    fd.set_font_file2(program_stream)
    font.set_font_descriptor(fd)
    font.set_true_type_font(TrueTypeFont.from_bytes(raw))
    if cid_to_gid_map is not None:
        font.set_cid_to_gid_map(cid_to_gid_map)
    return font


# ---------- /CIDToGIDMap ----------


def test_identity_cid_to_gid_when_absent() -> None:
    font = PDCIDFontType2()
    assert font.is_identity_cid_to_gid_map() is True
    assert font.get_cid_to_gid_map_bytes() is None


def test_identity_cid_to_gid_when_named_identity() -> None:
    font = PDCIDFontType2()
    font.set_cid_to_gid_map("Identity")
    assert font.is_identity_cid_to_gid_map() is True
    # Upstream collapses /Identity to null bytes — callers fall back
    # to identity CID->GID mapping.
    assert font.get_cid_to_gid_map_bytes() is None


def test_explicit_cid_to_gid_map_bytes_roundtrip() -> None:
    font = PDCIDFontType2()
    stream = COSStream()
    payload = b"\x00\x00\x00\x10\x00\x20\x00\x30"
    stream.set_data(payload)
    font.set_cid_to_gid_map(stream)
    assert font.is_identity_cid_to_gid_map() is False
    assert font.get_cid_to_gid_map_bytes() == payload
    # CID 0 -> GID 0, CID 1 -> 16, CID 2 -> 32, CID 3 -> 48.
    assert font.code_to_gid(0) == 0
    assert font.code_to_gid(1) == 16
    assert font.code_to_gid(2) == 32
    assert font.code_to_gid(3) == 48


def test_code_to_cid_is_identity() -> None:
    # PDCIDFontType2.codeToCID is identity — the parent Type 0 font's
    # /Encoding CMap has already converted the byte to a CID.
    font = PDCIDFontType2()
    for code in (0, 1, 65, 256, 0xFFFF):
        assert font.code_to_cid(code) == code


# ---------- isEmbedded ----------


def test_is_embedded_false_when_no_descriptor() -> None:
    font = PDCIDFontType2()
    assert font.is_embedded() is False


def test_is_embedded_false_with_empty_descriptor() -> None:
    font = PDCIDFontType2()
    font.set_font_descriptor(PDFontDescriptor())
    assert font.is_embedded() is False


def test_is_embedded_true_when_font_file2_present() -> None:
    font = PDCIDFontType2()
    fd = PDFontDescriptor()
    fd.set_font_file2(COSStream())
    font.set_font_descriptor(fd)
    assert font.is_embedded() is True


def test_is_embedded_true_for_open_type_font_file3() -> None:
    # PDFBox 3.0 added /FontFile3 /OpenType acceptance for CIDFontType2
    # so OpenType-flavoured TrueType programs can ride along.
    font = PDCIDFontType2()
    fd = PDFontDescriptor()
    stream = COSStream()
    stream.set_name(COSName.SUBTYPE, "OpenType")  # type: ignore[attr-defined]
    fd.set_font_file3(stream)
    font.set_font_descriptor(fd)
    assert font.is_embedded() is True


# ---------- getTrueTypeFont (lazy parse) ----------


def test_get_true_type_font_none_without_descriptor() -> None:
    font = PDCIDFontType2()
    assert font.get_true_type_font() is None


def test_get_true_type_font_none_when_unparseable() -> None:
    font = PDCIDFontType2()
    fd = PDFontDescriptor()
    stream = COSStream()
    stream.set_data(b"not-a-real-ttf")
    fd.set_font_file2(stream)
    font.set_font_descriptor(fd)
    assert font.get_true_type_font() is None


# ---------- isDamaged ----------


def test_is_damaged_false_when_not_embedded() -> None:
    font = PDCIDFontType2()
    assert font.is_damaged() is False


def test_is_damaged_true_when_embedded_program_unparseable() -> None:
    font = PDCIDFontType2()
    fd = PDFontDescriptor()
    stream = COSStream()
    stream.set_data(b"definitely-not-a-ttf")
    fd.set_font_file2(stream)
    font.set_font_descriptor(fd)
    assert font.is_damaged() is True


# ---------- getFontMatrix (default 1/1000 when no program) ----------


def test_get_font_matrix_default_when_no_program() -> None:
    font = PDCIDFontType2()
    assert font.get_font_matrix() == [0.001, 0.0, 0.0, 0.001, 0.0, 0.0]


# ---------- getBoundingBox / getHeight / getAverageFontWidth fall-throughs ----------


def test_get_bounding_box_none_when_neither_program_nor_descriptor() -> None:
    font = PDCIDFontType2()
    assert font.get_bounding_box() is None


def test_get_height_zero_when_no_program_no_w2() -> None:
    font = PDCIDFontType2()
    assert font.get_height(65) == 0.0


def test_get_average_font_width_falls_through_to_dw() -> None:
    font = PDCIDFontType2()
    font.set_dw(750)
    assert font.get_average_font_width() == pytest.approx(750.0)


def test_get_width_from_font_zero_when_no_program() -> None:
    font = PDCIDFontType2()
    assert font.get_width_from_font(65) == 0.0


# ---------- glyph-path entry points (no embedded program) ----------


def test_get_path_empty_when_no_program() -> None:
    # Upstream getPath() returns an empty GeneralPath when the embedded
    # program cannot be located — pypdfbox returns the equivalent empty
    # command list.
    font = PDCIDFontType2()
    assert font.get_path(65) == []


def test_get_path_from_outlines_none_when_not_open_type_post_script() -> None:
    # The CFF charstring branch only fires when otf != null && isPostScript().
    # No embedded program → no OTF → guard returns None.
    font = PDCIDFontType2()
    assert font.get_path_from_outlines(65) is None


# ---------- find_font_or_substitute ----------


def test_find_font_or_substitute_falls_through_when_no_mapper_override() -> None:
    # Upstream consults FontMappers.instance().getCIDFont(...). pypdfbox's
    # bundled DefaultFontMapper has no on-disk CID font scanner so the
    # default response is a None CIDFontMapping — we surface that without
    # raising. (Real CID-aware mappers override get_cid_font.)
    font = PDCIDFontType2()
    # With no FontMapper override registered the call should not raise
    # and should return either None or a CIDFontMapping object — the
    # exact class depends on whether a host-system mapper is wired up.
    result = font.find_font_or_substitute()
    assert result is None or hasattr(result, "is_cid_font")


# ---------- encode (unicode -> bytes) ----------


def test_encode_raises_when_no_glyph_available() -> None:
    # Upstream throws IllegalArgumentException("No glyph for U+%04X ...");
    # pypdfbox surfaces ValueError. Here the font has no embedded program
    # and no parent / cmap, so no glyph can be located for any codepoint.
    font = PDCIDFontType2()
    with pytest.raises(ValueError, match=r"No glyph for U\+0041"):
        font.encode(0x41)


# ---------- get_parser (TTF vs OTF SFNT-magic dispatch) ----------


def test_get_parser_returns_otf_for_otto_magic() -> None:
    # Upstream sniffs the first four bytes of the embedded program for
    # the OpenType OTTO sfnt-version tag and dispatches to OTFParser.
    parser = PDCIDFontType2.get_parser(b"OTTO\x00\x10\x00\x00")
    assert isinstance(parser, OTFParser)


def test_get_parser_returns_ttf_for_truetype_magic() -> None:
    # TrueType programs use \x00\x01\x00\x00 (alongside legacy 'true' /
    # 'typ1' tags) — anything that isn't OTTO falls through to TTFParser.
    parser = PDCIDFontType2.get_parser(b"\x00\x01\x00\x00")
    assert isinstance(parser, TTFParser)
    # OTFParser inherits TTFParser so the identity check matters.
    assert not isinstance(parser, OTFParser)


def test_get_parser_returns_ttf_for_short_or_empty_data() -> None:
    parser = PDCIDFontType2.get_parser(b"")
    assert isinstance(parser, TTFParser)
    assert not isinstance(parser, OTFParser)


def test_get_parser_propagates_is_embedded_flag() -> None:
    embedded = PDCIDFontType2.get_parser(b"\x00\x01\x00\x00", is_embedded=True)
    standalone = PDCIDFontType2.get_parser(
        b"\x00\x01\x00\x00", is_embedded=False
    )
    assert embedded.is_embedded is True
    assert standalone.is_embedded is False


# ---------- generate_bounding_box (descriptor-first, non-zero only) ----------


def test_generate_bounding_box_uses_descriptor_when_non_zero() -> None:
    font = PDCIDFontType2()
    fd = PDFontDescriptor()
    bbox_arr = COSArray()
    for v in (-50, -25, 1050, 950):
        bbox_arr.add(COSFloat(v))
    fd.set_font_b_box(bbox_arr)
    font.set_font_descriptor(fd)
    bbox = font.generate_bounding_box()
    assert bbox is not None
    assert bbox.lower_left_x == pytest.approx(-50.0)
    assert bbox.upper_right_y == pytest.approx(950.0)


def test_generate_bounding_box_none_when_no_sources() -> None:
    font = PDCIDFontType2()
    assert font.generate_bounding_box() is None


# ---------- SFNT-fixture-bound tests (bundled LiberationSans) ----------


def test_horizontal_metrics_via_cmap() -> None:
    """Glyph advances and heights come from the embedded TTF when no
    ``/W`` array overrides them.

    Mirrors the upstream coverage of ``getWidthFromFont``,
    ``getHeight`` and ``getAverageFontWidth`` against a real SFNT
    program. We use the bundled ``LiberationSans-Regular.ttf`` fixture
    (Liberation Sans, SIL OFL — already bundled under
    ``tests/fixtures/fontbox/ttf/`` for other tests) so the same code
    path runs against a real ``hmtx`` / ``glyf`` table instead of a
    stub.
    """
    font = _build_embedded_font()

    # Identity /CIDToGIDMap is the default — so CID == GID for the
    # cmap-resolved glyph IDs below.
    cmap = font.get_true_type_font().get_unicode_cmap_lookup()
    gid_a = cmap.get_glyph_id(ord("A"))
    gid_lower_a = cmap.get_glyph_id(ord("a"))
    assert gid_a > 0
    assert gid_lower_a > 0
    assert gid_a != gid_lower_a

    # Liberation Sans Regular ships at 2048 units/em; the scale factor
    # is therefore 1000 / 2048 ~= 0.488. We assert the actual hmtx
    # advances ride through that scaling.
    upem = font.get_true_type_font().get_units_per_em()
    raw_advance_a = font.get_true_type_font().get_advance_width(gid_a)
    expected_a = raw_advance_a * 1000.0 / upem
    assert font.get_width_from_font(gid_a) == pytest.approx(expected_a)

    # /A/ is a capital letter — its glyph yMax must exceed yMin.
    assert font.get_height(gid_a) > 0.0

    # Average width pulls from the embedded program (positive advances
    # only); for Liberation Sans Regular this is well above zero.
    avg = font.get_average_font_width()
    assert avg > 0.0

    # Font matrix derives from upem, not the /CIDFont default 1/1000.
    matrix = font.get_font_matrix()
    assert matrix[0] == pytest.approx(1.0 / upem)
    assert matrix[3] == pytest.approx(1.0 / upem)


def test_cid_to_gid_map_with_glyphs_through_load() -> None:
    """An explicit ``/CIDToGIDMap`` stream overrides the identity
    mapping; advances flow through the rewired GIDs.

    Mirrors the upstream check that constructor-side ``readCIDToGIDMap``
    populates the ``cid2gid`` table and that downstream metric calls
    consult it. We build a small map (``CID 0 -> GID 0``,
    ``CID 1 -> GID 'A'``, ``CID 2 -> GID 'a'``) and verify both
    ``cid_to_gid`` and ``get_width_from_font`` honour it.
    """
    raw = _load_liberation_bytes()
    ttf = TrueTypeFont.from_bytes(raw)
    cmap = ttf.get_unicode_cmap_lookup()
    gid_upper = cmap.get_glyph_id(ord("A"))
    gid_lower = cmap.get_glyph_id(ord("a"))

    # Big-endian uint16 per CID slot.
    payload = (
        (0).to_bytes(2, "big")
        + gid_upper.to_bytes(2, "big")
        + gid_lower.to_bytes(2, "big")
    )
    map_stream = COSStream()
    map_stream.set_data(payload)

    font = _build_embedded_font(cid_to_gid_map=map_stream)

    # The identity check flips off and the parsed values come back.
    assert font.is_identity_cid_to_gid_map() is False
    assert font.get_cid_to_gid_map_bytes() == payload
    assert font.cid_to_gid(0) == 0
    assert font.cid_to_gid(1) == gid_upper
    assert font.cid_to_gid(2) == gid_lower

    # Metric calls run the CID through /CIDToGIDMap before consulting
    # hmtx — the result must match the advance we'd read for the
    # cmap-resolved GID directly.
    expected_advance = (
        ttf.get_advance_width(gid_upper) * 1000.0 / ttf.get_units_per_em()
    )
    assert font.get_width_from_font(1) == pytest.approx(expected_advance)


# ---------- noMapping field (warning-dedup set) ----------


def test_no_mapping_set_initialised_empty() -> None:
    # Upstream PDCIDFontType2.java line 61 initialises ``noMapping`` to
    # ``new HashSet<>()`` so the codeToGID warning path can dedupe.
    font = PDCIDFontType2()
    assert font.get_no_mapping() == set()


# ---------- otf accessor (private upstream field) ----------


def test_get_open_type_font_none_without_embedded_program() -> None:
    # Upstream's ``otf`` field stays null when no embedded program is
    # available — pypdfbox's accessor surfaces the same.
    font = PDCIDFontType2()
    assert font.get_open_type_font() is None


# ---------- read_cid_to_gid_map (constructor-equivalent) ----------


def test_read_cid_to_gid_map_round_trips_explicit_stream() -> None:
    # Upstream constructor (line 153) calls readCIDToGIDMap() and
    # stashes the resulting int[] in cid2gid; pypdfbox inherits the
    # implementation from PDCIDFont and exposes the same parsed list.
    font = PDCIDFontType2()
    stream = COSStream()
    stream.set_data(b"\x00\x05\x00\x06\x00\x07")
    font.set_cid_to_gid_map(stream)
    assert font.read_cid_to_gid_map() == [5, 6, 7]
