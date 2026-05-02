"""Hand-written tests for the rounded-out :class:`PDType0Font` accessors.

Covers methods added in the round-out pass:

* upstream-named aliases (``get_cid_font``, ``get_width``, ``get_height``,
  ``get_string_width``, ``read``, ``decode``);
* new accessors (``get_cmap_ucs2``, ``get_encoding``, ``get_bounding_box``,
  ``get_font_descriptor``, ``get_cid_system_info``, ``is_damaged``,
  ``get_font_matrix``, ``get_average_font_width``);
* string ``encode`` round-tripping for Identity-H;
* ``load_ttf`` / ``load_otf`` factories driven by the bundled
  Liberation Sans fixture.

These complement ``test_pd_type0_font_parity.py`` (raw dictionary
behaviour) and ``test_pd_type0_font_subset.py`` (subset workflow).
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSName,
    COSStream,
)
from pypdfbox.fontbox.ttf import TrueTypeFont
from pypdfbox.pdmodel.font.pd_cid_font_type2 import PDCIDFontType2
from pypdfbox.pdmodel.font.pd_cid_system_info import PDCIDSystemInfo
from pypdfbox.pdmodel.font.pd_font_descriptor import PDFontDescriptor
from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font
from pypdfbox.pdmodel.pd_rectangle import PDRectangle

_DESCENDANT_FONTS: COSName = COSName.get_pdf_name("DescendantFonts")
_ENCODING: COSName = COSName.get_pdf_name("Encoding")
_TO_UNICODE: COSName = COSName.get_pdf_name("ToUnicode")
_BASE_FONT: COSName = COSName.get_pdf_name("BaseFont")
_DW: COSName = COSName.get_pdf_name("DW")
_W: COSName = COSName.get_pdf_name("W")
_FONT_DESCRIPTOR: COSName = COSName.get_pdf_name("FontDescriptor")
_FONT_BBOX: COSName = COSName.get_pdf_name("FontBBox")
_CID_SYSTEM_INFO: COSName = COSName.get_pdf_name("CIDSystemInfo")

_TTF_FIXTURE = (
    Path(__file__).parent.parent.parent
    / "fixtures"
    / "fontbox"
    / "ttf"
    / "LiberationSans-Regular.ttf"
)


# ---------- shared builders ----------


def _build_descendant(
    *,
    registry: str = "Adobe",
    ordering: str = "Identity",
    supplement: int = 0,
    dw: int = 1000,
    bbox: tuple[float, float, float, float] | None = None,
    embedded: bool = False,
) -> COSDictionary:
    raw = COSDictionary()
    raw.set_name(COSName.TYPE, "Font")  # type: ignore[attr-defined]
    raw.set_name(COSName.SUBTYPE, "CIDFontType2")  # type: ignore[attr-defined]
    raw.set_name(_BASE_FONT, "TestCID")
    raw.set_int(_DW, dw)
    sys_info = PDCIDSystemInfo()
    sys_info.set_registry(registry)
    sys_info.set_ordering(ordering)
    sys_info.set_supplement(supplement)
    raw.set_item(_CID_SYSTEM_INFO, sys_info.get_cos_object())
    if bbox is not None or embedded:
        fd = PDFontDescriptor()
        if bbox is not None:
            arr = COSArray()
            for v in bbox:
                arr.add(_make_number(v))
            fd.set_font_b_box(arr)
        if embedded:
            fd.set_font_file2(COSStream())
        raw.set_item(_FONT_DESCRIPTOR, fd.get_cos_object())
    return raw


def _make_number(value: float):
    from pypdfbox.cos import COSFloat, COSInteger

    return COSInteger.get(int(value)) if value == int(value) else COSFloat(value)


def _build_type0(
    descendant: COSDictionary | None,
    *,
    encoding_name: str | None = "Identity-H",
) -> PDType0Font:
    font_dict = COSDictionary()
    font_dict.set_name(COSName.SUBTYPE, "Type0")  # type: ignore[attr-defined]
    font_dict.set_name(_BASE_FONT, "TestType0")
    if descendant is not None:
        arr = COSArray()
        arr.add(descendant)
        font_dict.set_item(_DESCENDANT_FONTS, arr)
    if encoding_name is not None:
        font_dict.set_name(_ENCODING, encoding_name)
    return PDType0Font(font_dict)


# ---------- get_cid_font alias ----------


def test_get_cid_font_alias_returns_descendant() -> None:
    font = _build_type0(_build_descendant())
    assert font.get_cid_font() is not None
    # Same wrapper class as get_descendant_font.
    assert isinstance(font.get_cid_font(), PDCIDFontType2)


def test_get_cid_font_returns_none_without_descendant() -> None:
    font = _build_type0(None)
    assert font.get_cid_font() is None


# ---------- get_encoding (raw entry) ----------


def test_get_encoding_returns_cos_name_for_predefined() -> None:
    font = _build_type0(_build_descendant(), encoding_name="Identity-H")
    enc = font.get_encoding()
    assert isinstance(enc, COSName)
    assert enc.name == "Identity-H"


def test_get_encoding_returns_none_when_absent() -> None:
    font = _build_type0(_build_descendant(), encoding_name=None)
    assert font.get_encoding() is None


# ---------- get_cid_system_info (descendant fallback) ----------


def test_get_cid_system_info_returns_descendant_info() -> None:
    font = _build_type0(_build_descendant(registry="Adobe", ordering="Japan1"))
    info = font.get_cid_system_info()
    assert info is not None
    assert info.get_registry() == "Adobe"
    assert info.get_ordering() == "Japan1"


def test_get_cid_system_info_none_without_descendant() -> None:
    font = _build_type0(None)
    assert font.get_cid_system_info() is None


# ---------- get_font_descriptor (descendant fallback) ----------


def test_get_font_descriptor_falls_back_to_descendant() -> None:
    desc = _build_descendant(embedded=True)
    font = _build_type0(desc)
    fd = font.get_font_descriptor()
    assert fd is not None
    assert fd.get_font_file2() is not None


def test_get_font_descriptor_uses_own_when_present() -> None:
    desc = _build_descendant()
    own_fd = PDFontDescriptor()
    own_fd.set_font_name("OverrideName")
    font = _build_type0(desc)
    font.get_cos_object().set_item(_FONT_DESCRIPTOR, own_fd.get_cos_object())
    fd = font.get_font_descriptor()
    assert fd is not None
    assert fd.get_font_name() == "OverrideName"


# ---------- get_bounding_box ----------


def test_get_bounding_box_from_descendant() -> None:
    desc = _build_descendant(bbox=(0.0, -200.0, 1000.0, 800.0))
    font = _build_type0(desc)
    bbox = font.get_bounding_box()
    assert isinstance(bbox, PDRectangle)
    assert bbox.get_lower_left_x() == 0.0
    assert bbox.get_lower_left_y() == -200.0
    assert bbox.get_upper_right_x() == 1000.0
    assert bbox.get_upper_right_y() == 800.0


def test_get_bounding_box_none_without_descendant() -> None:
    font = _build_type0(None)
    assert font.get_bounding_box() is None


def test_get_bounding_box_none_without_descriptor_bbox() -> None:
    font = _build_type0(_build_descendant())
    assert font.get_bounding_box() is None


# ---------- get_font_matrix ----------


def test_get_font_matrix_returns_default() -> None:
    font = _build_type0(_build_descendant())
    assert font.get_font_matrix() == [0.001, 0.0, 0.0, 0.001, 0.0, 0.0]


def test_get_font_matrix_independent_per_call() -> None:
    font = _build_type0(_build_descendant())
    a = font.get_font_matrix()
    a[0] = 99.0
    assert font.get_font_matrix()[0] == 0.001


# ---------- get_width / get_height aliases ----------


def test_get_width_alias_uses_descendant_dw() -> None:
    font = _build_type0(_build_descendant(dw=765))
    assert font.get_width(0x41) == 765.0


def test_get_height_zero_for_horizontal_font() -> None:
    font = _build_type0(_build_descendant())
    assert font.get_height(0x41) == 0.0


def test_get_height_zero_without_descendant() -> None:
    font = _build_type0(None)
    assert font.get_height(0x41) == 0.0


# ---------- get_average_font_width ----------


def test_get_average_font_width_falls_back_to_dw() -> None:
    font = _build_type0(_build_descendant(dw=600))
    # No /W -> falls back to /DW (per PDCIDFont.get_average_font_width).
    assert font.get_average_font_width() == 600.0


def test_get_average_font_width_zero_without_descendant() -> None:
    font = _build_type0(None)
    assert font.get_average_font_width() == 0.0


# ---------- is_damaged ----------


def test_is_damaged_false_without_descendant() -> None:
    font = _build_type0(None)
    assert font.is_damaged() is False


def test_is_damaged_false_for_unembedded_descendant() -> None:
    font = _build_type0(_build_descendant())
    assert font.is_damaged() is False


# ---------- encode / decode ----------


def test_encode_identity_h_writes_two_byte_be() -> None:
    font = _build_type0(_build_descendant(), encoding_name="Identity-H")
    out = font.encode("AB")
    assert out == b"\x00\x41\x00\x42"


def test_encode_supplementary_codepoint_truncates_to_bmp() -> None:
    # Identity-H is a 16-bit codespace; codepoints above 0xFFFF are
    # masked to their low 16 bits per the BMP-only Identity contract.
    font = _build_type0(_build_descendant(), encoding_name="Identity-H")
    out = font.encode("\U00010041")  # U+10041 -> low 16 bits = 0x0041
    assert out == b"\x00\x41"


def test_decode_returns_first_code_only() -> None:
    font = _build_type0(_build_descendant(), encoding_name="Identity-H")
    assert font.decode(b"\x00\x42\x00\x43") == 0x42


def test_decode_empty_bytes_returns_zero() -> None:
    font = _build_type0(_build_descendant(), encoding_name="Identity-H")
    assert font.decode(b"") == 0


def test_encode_with_no_cmap_falls_back_to_two_byte_be() -> None:
    font = _build_type0(_build_descendant(), encoding_name=None)
    assert font.encode("A") == b"\x00\x41"


# ---------- read (InputStream-shaped) ----------


def test_read_consumes_two_bytes_from_stream() -> None:
    font = _build_type0(_build_descendant(), encoding_name="Identity-H")
    stream = io.BytesIO(b"\x00\x41\x00\x42")
    assert font.read(stream) == 0x41
    # Second call returns next code; stream advanced exactly 2 bytes.
    assert font.read(stream) == 0x42
    assert stream.read() == b""


def test_read_accepts_bytes() -> None:
    font = _build_type0(_build_descendant(), encoding_name="Identity-H")
    assert font.read(b"\x00\x41\x00\x42") == 0x41


def test_read_returns_zero_on_empty_stream() -> None:
    font = _build_type0(_build_descendant(), encoding_name="Identity-H")
    assert font.read(io.BytesIO(b"")) == 0


# ---------- get_string_width ----------


def test_get_string_width_sums_per_code_widths() -> None:
    font = _build_type0(_build_descendant(dw=500), encoding_name="Identity-H")
    # Three Identity-H codes -> 3 * 500.
    assert font.get_string_width("ABC") == 1500.0


def test_get_string_width_empty_string() -> None:
    font = _build_type0(_build_descendant(dw=500), encoding_name="Identity-H")
    assert font.get_string_width("") == 0.0


# ---------- get_cmap_ucs2 ----------


def test_get_cmap_ucs2_none_for_identity_collection() -> None:
    font = _build_type0(_build_descendant(registry="Adobe", ordering="Identity"))
    assert font.get_cmap_ucs2() is None


def test_get_cmap_ucs2_resolves_for_adobe_japan1() -> None:
    font = _build_type0(_build_descendant(registry="Adobe", ordering="Japan1"))
    cmap = font.get_cmap_ucs2()
    assert cmap is not None
    assert cmap.has_unicode_mappings()


def test_get_cmap_ucs2_none_for_unknown_collection() -> None:
    font = _build_type0(_build_descendant(registry="Custom", ordering="Foo"))
    assert font.get_cmap_ucs2() is None


def test_get_cmap_ucs2_caches_result() -> None:
    font = _build_type0(_build_descendant(registry="Adobe", ordering="GB1"))
    first = font.get_cmap_ucs2()
    second = font.get_cmap_ucs2()
    assert first is second


def test_get_cmap_ucs2_none_without_descendant() -> None:
    font = _build_type0(None)
    assert font.get_cmap_ucs2() is None


# ---------- load_ttf / load_otf ----------


@pytest.fixture(scope="module")
def liberation_bytes() -> bytes:
    if not _TTF_FIXTURE.exists():
        pytest.skip(f"Fixture font not present: {_TTF_FIXTURE}")
    return _TTF_FIXTURE.read_bytes()


def test_load_ttf_from_path_returns_type0(liberation_bytes: bytes) -> None:
    font = PDType0Font.load_ttf(None, _TTF_FIXTURE)
    assert isinstance(font, PDType0Font)
    assert font.get_subtype() == "Type0"
    # /Encoding wired to Identity-H.
    enc = font.get_encoding()
    assert isinstance(enc, COSName) and enc.name == "Identity-H"


def test_load_ttf_from_bytes(liberation_bytes: bytes) -> None:
    font = PDType0Font.load_ttf(None, liberation_bytes)
    assert font.get_subtype() == "Type0"


def test_load_ttf_from_file_like(liberation_bytes: bytes) -> None:
    font = PDType0Font.load_ttf(None, io.BytesIO(liberation_bytes))
    assert font.get_subtype() == "Type0"


def test_load_ttf_descendant_is_cidfonttype2(liberation_bytes: bytes) -> None:
    font = PDType0Font.load_ttf(None, liberation_bytes)
    descendant = font.get_descendant_font()
    assert isinstance(descendant, PDCIDFontType2)


def test_load_ttf_embeds_font_file2(liberation_bytes: bytes) -> None:
    font = PDType0Font.load_ttf(None, liberation_bytes)
    assert font.is_embedded() is True
    descendant = font.get_descendant_font()
    assert descendant is not None
    fd = descendant.get_font_descriptor()
    assert fd is not None
    embedded = fd.get_font_file2()
    assert embedded is not None
    assert embedded.to_byte_array() == liberation_bytes


def test_load_ttf_sets_identity_cid_system_info(liberation_bytes: bytes) -> None:
    font = PDType0Font.load_ttf(None, liberation_bytes)
    info = font.get_cid_system_info()
    assert info is not None
    assert info.get_registry() == "Adobe"
    assert info.get_ordering() == "Identity"
    assert info.get_supplement() == 0


def test_load_ttf_populates_w_array(liberation_bytes: bytes) -> None:
    font = PDType0Font.load_ttf(None, liberation_bytes)
    descendant = font.get_descendant_font()
    assert descendant is not None
    # /W array exists and yields a positive width for the 'A' glyph.
    assert descendant.get_w() is not None
    width_a = font.get_width(ord("A"))
    assert width_a > 0


def test_load_ttf_uses_postscript_name(liberation_bytes: bytes) -> None:
    font = PDType0Font.load_ttf(None, liberation_bytes)
    name = font.get_name()
    assert name == "LiberationSans"
    descendant = font.get_descendant_font()
    assert descendant is not None
    assert descendant.get_name() == "LiberationSans"


def test_load_ttf_round_trip_through_subset(liberation_bytes: bytes) -> None:
    font = PDType0Font.load_ttf(None, liberation_bytes)
    out = font.subset("Hi", prefix="ABCDEF")
    assert font.get_name() == "ABCDEF+LiberationSans"
    assert isinstance(out, bytes)
    assert len(out) < len(liberation_bytes)


def test_load_otf_dispatches_through_same_path(liberation_bytes: bytes) -> None:
    # Liberation Sans is TrueType-flavoured; load_otf should return an
    # equivalent Type 0 wrapper (it accepts any SFNT input — the parsed
    # /Subtype is /CIDFontType2 in both cases).
    font = PDType0Font.load_otf(None, liberation_bytes)
    assert isinstance(font, PDType0Font)
    descendant = font.get_descendant_font()
    assert isinstance(descendant, PDCIDFontType2)


def test_load_ttf_rejects_text_stream() -> None:
    with pytest.raises(TypeError, match="binary mode"):
        PDType0Font.load_ttf(None, io.StringIO("not a font"))


def test_load_ttf_string_path_works(liberation_bytes: bytes) -> None:
    font = PDType0Font.load_ttf(None, str(_TTF_FIXTURE))
    assert font.get_subtype() == "Type0"


def test_loaded_font_is_truetype_round_trip(liberation_bytes: bytes) -> None:
    font = PDType0Font.load_ttf(None, liberation_bytes)
    descendant = font.get_descendant_font()
    assert descendant is not None
    fd = descendant.get_font_descriptor()
    assert fd is not None
    embedded = fd.get_font_file2()
    assert embedded is not None
    # Re-parse the embedded program — should round-trip without error.
    ttf = TrueTypeFont.from_bytes(embedded.to_byte_array())
    assert ttf.get_units_per_em() > 0


# ---------- get_base_font / is_standard14 ----------


def test_get_base_font_returns_postscript_name() -> None:
    font = _build_type0(_build_descendant())
    assert font.get_base_font() == "TestType0"


def test_get_base_font_matches_get_name() -> None:
    font = _build_type0(_build_descendant())
    assert font.get_base_font() == font.get_name()


def test_is_standard14_always_false() -> None:
    # Mirrors upstream — Type 0 fonts are never one of the 14 standard fonts.
    font = _build_type0(_build_descendant())
    assert font.is_standard14() is False


def test_is_standard14_false_without_descendant() -> None:
    font = _build_type0(None)
    assert font.is_standard14() is False


# ---------- has_glyph ----------


def test_has_glyph_true_when_descendant_has_default_width() -> None:
    font = _build_type0(_build_descendant(dw=500), encoding_name="Identity-H")
    assert font.has_glyph(0x41) is True


def test_has_glyph_false_when_descendant_has_zero_default_width() -> None:
    font = _build_type0(_build_descendant(dw=0), encoding_name="Identity-H")
    assert font.has_glyph(0x41) is False


def test_has_glyph_false_without_descendant() -> None:
    font = _build_type0(None)
    assert font.has_glyph(0x41) is False


# ---------- get_width_from_font ----------


def test_get_width_from_font_zero_without_descendant() -> None:
    font = _build_type0(None)
    assert font.get_width_from_font(0x41) == 0.0


def test_get_width_from_font_zero_without_embedded_program() -> None:
    # PDCIDFontType2 with no /FontFile2 returns 0.0.
    font = _build_type0(_build_descendant())
    assert font.get_width_from_font(0x41) == 0.0


def test_get_width_from_font_uses_descendant_embedded(
    liberation_bytes: bytes,
) -> None:
    font = PDType0Font.load_ttf(None, liberation_bytes)
    # Identity-H means CID == codepoint for ASCII; 'A' has a positive
    # advance in Liberation Sans.
    assert font.get_width_from_font(ord("A")) > 0.0


# ---------- get_displacement ----------


def test_get_displacement_horizontal_returns_width_over_1000() -> None:
    font = _build_type0(_build_descendant(dw=600), encoding_name="Identity-H")
    dx, dy = font.get_displacement(0x41)
    assert dx == 0.6
    assert dy == 0.0


def test_get_displacement_without_descendant_horizontal() -> None:
    font = _build_type0(None, encoding_name="Identity-H")
    dx, dy = font.get_displacement(0x41)
    assert dx == 0.0
    assert dy == 0.0


# ---------- get_position_vector ----------


def test_get_position_vector_returns_zero_without_descendant() -> None:
    font = _build_type0(None)
    assert font.get_position_vector(0x41) == (0.0, 0.0)


def test_get_position_vector_negates_and_scales_by_1000() -> None:
    """Upstream's ``getPositionVector`` calls ``descendant.getPositionVector(code).scale(-1/1000f)``.

    PDCIDFont's default position vector (when ``/W2`` has no entry) is
    ``(width(cid)/2, dw2[0])`` per upstream
    ``PDCIDFont.getDefaultPositionVector``. With ``/DW = 1000`` (the
    default) and the spec's ``dw2[0] = 880`` the descendant vector is
    ``(500, 880)``; after ``scale(-1/1000)`` the result is
    ``(-0.5, -0.88)``.
    """
    font = _build_type0(_build_descendant(), encoding_name="Identity-H")
    v_x, v_y = font.get_position_vector(0x41)
    assert v_x == -0.5
    assert v_y == -0.88


# ---------- encode_glyph_id ----------


def test_encode_glyph_id_two_byte_be_fallback() -> None:
    # No descendant, or a descendant without an encode_glyph_id method,
    # falls back to the 2-byte big-endian form used by Identity-H.
    font = _build_type0(None)
    assert font.encode_glyph_id(0x41) == b"\x00\x41"
    assert font.encode_glyph_id(0x1234) == b"\x12\x34"


def test_encode_glyph_id_truncates_to_16_bits() -> None:
    font = _build_type0(None)
    # GID 0x1_0042 -> low 16 bits = 0x0042.
    assert font.encode_glyph_id(0x10042) == b"\x00\x42"


def test_encode_glyph_id_with_descendant() -> None:
    font = _build_type0(_build_descendant(), encoding_name="Identity-H")
    # PDCIDFont has no overridden encode_glyph_id, so we still hit the
    # 2-byte BE fallback path.
    assert font.encode_glyph_id(7) == b"\x00\x07"


# ---------- is_cmap_predefined ----------


def test_is_cmap_predefined_true_for_identity_h() -> None:
    font = _build_type0(_build_descendant(), encoding_name="Identity-H")
    assert font.is_cmap_predefined() is True


def test_is_cmap_predefined_true_for_identity_v() -> None:
    font = _build_type0(_build_descendant(), encoding_name="Identity-V")
    assert font.is_cmap_predefined() is True


def test_is_cmap_predefined_true_for_predefined_cjk_name() -> None:
    font = _build_type0(_build_descendant(), encoding_name="GBK-EUC-H")
    assert font.is_cmap_predefined() is True


def test_is_cmap_predefined_false_when_encoding_absent() -> None:
    font = _build_type0(_build_descendant(), encoding_name=None)
    assert font.is_cmap_predefined() is False


def test_is_cmap_predefined_false_for_embedded_cmap_stream() -> None:
    font = _build_type0(_build_descendant(), encoding_name=None)
    cmap_stream = COSStream()
    cmap_stream.set_data(b"%!PS-Adobe-3.0 Resource-CMap\n")
    font.get_cos_object().set_item(_ENCODING, cmap_stream)
    assert font.is_cmap_predefined() is False


# ---------- is_descendant_cjk ----------


def test_is_descendant_cjk_true_for_adobe_japan1() -> None:
    font = _build_type0(_build_descendant(registry="Adobe", ordering="Japan1"))
    assert font.is_descendant_cjk() is True


def test_is_descendant_cjk_true_for_adobe_gb1() -> None:
    font = _build_type0(_build_descendant(registry="Adobe", ordering="GB1"))
    assert font.is_descendant_cjk() is True


def test_is_descendant_cjk_true_for_adobe_cns1() -> None:
    font = _build_type0(_build_descendant(registry="Adobe", ordering="CNS1"))
    assert font.is_descendant_cjk() is True


def test_is_descendant_cjk_true_for_adobe_korea1() -> None:
    font = _build_type0(_build_descendant(registry="Adobe", ordering="Korea1"))
    assert font.is_descendant_cjk() is True


def test_is_descendant_cjk_false_for_identity_collection() -> None:
    font = _build_type0(_build_descendant(registry="Adobe", ordering="Identity"))
    assert font.is_descendant_cjk() is False


def test_is_descendant_cjk_false_for_adobe_kr() -> None:
    # Adobe-KR is NOT in the upstream CJK trigger set despite being an
    # Adobe character collection — only GB1/CNS1/Japan1/Korea1 set
    # ``isDescendantCJK`` in PDFBox.
    font = _build_type0(_build_descendant(registry="Adobe", ordering="KR"))
    assert font.is_descendant_cjk() is False


def test_is_descendant_cjk_false_for_non_adobe_registry() -> None:
    font = _build_type0(_build_descendant(registry="Custom", ordering="Japan1"))
    assert font.is_descendant_cjk() is False


def test_is_descendant_cjk_false_without_descendant() -> None:
    font = _build_type0(None)
    assert font.is_descendant_cjk() is False


# ---------- __repr__ (upstream toString format) ----------


def test_repr_includes_descendant_class_and_postscript_name() -> None:
    font = _build_type0(_build_descendant())
    text = repr(font)
    assert text.startswith("PDType0Font/PDCIDFontType2,")
    assert "PostScript name: TestType0" in text


def test_repr_descendant_none_when_descendant_absent() -> None:
    font = _build_type0(None)
    text = repr(font)
    assert "PDType0Font/None," in text


# ---------- Identity-H / Identity-V module constants ----------


def test_identity_h_constant_value() -> None:
    from pypdfbox.pdmodel.font.pd_type0_font import IDENTITY_H, IDENTITY_V

    assert IDENTITY_H == "Identity-H"
    assert IDENTITY_V == "Identity-V"


def test_identity_h_constant_round_trips_through_get_encoding() -> None:
    from pypdfbox.pdmodel.font.pd_type0_font import IDENTITY_H

    font = _build_type0(_build_descendant(), encoding_name=IDENTITY_H)
    enc = font.get_encoding()
    assert isinstance(enc, COSName)
    assert enc.name == IDENTITY_H


def test_identity_v_constant_drives_vertical_writing() -> None:
    from pypdfbox.pdmodel.font.pd_type0_font import IDENTITY_V

    font = _build_type0(_build_descendant(), encoding_name=IDENTITY_V)
    assert font.is_vertical() is True
    assert font.is_vertical_writing() is True
    assert font.is_cmap_predefined() is True


# ---------- PDCIDFont default position vector formula ----------


def test_position_vector_default_uses_width_over_two() -> None:
    """Upstream's ``PDCIDFont.getDefaultPositionVector`` is
    ``Vector(widthForCID(cid)/2, dw2[0])``. With ``/DW = 600`` and the
    spec's default ``dw2[0] = 880`` this yields ``(300, 880)``; the
    Type0 wrapper then negates+scales to ``(-0.3, -0.88)``.
    """
    font = _build_type0(_build_descendant(dw=600), encoding_name="Identity-H")
    v_x, v_y = font.get_position_vector(0x41)
    assert v_x == pytest.approx(-0.3)
    assert v_y == pytest.approx(-0.88)


def test_position_vector_default_honors_explicit_dw2_array() -> None:
    """When ``/DW2`` is set on the descendant, ``dw2[0]`` is the
    *position-vector-y* default — we should consume the first entry,
    not the second. Build a descendant with ``/DW2 [500 -800]`` and
    expect the y-component to be ``500`` before the Type0 scaling.
    """
    desc = _build_descendant(dw=400)
    dw2_arr = COSArray()
    dw2_arr.add(_make_number(500))
    dw2_arr.add(_make_number(-800))
    desc.set_item(COSName.get_pdf_name("DW2"), dw2_arr)
    font = _build_type0(desc, encoding_name="Identity-H")
    # Descendant default: (width/2, dw2[0]) = (200, 500); Type0 scales by -1/1000.
    v_x, v_y = font.get_position_vector(0x41)
    assert v_x == pytest.approx(-0.2)
    assert v_y == pytest.approx(-0.5)


def test_position_vector_w2_entry_overrides_default() -> None:
    """When ``/W2`` carries a triple for the CID, the explicit entry
    wins over the default formula entirely.
    """
    desc = _build_descendant(dw=1000)
    # Form 2: c1 c2 w1y v_x v_y => CID 0..0 gets (w1y=900, v_x=-50, v_y=-700)
    w2 = COSArray()
    for v in (0, 0, 900, -50, -700):
        w2.add(_make_number(v))
    desc.set_item(COSName.get_pdf_name("W2"), w2)
    font = _build_type0(desc, encoding_name="Identity-H")
    # Type0 scales by -1/1000 -> (0.05, 0.7).
    v_x, v_y = font.get_position_vector(0x00)
    assert v_x == pytest.approx(0.05)
    assert v_y == pytest.approx(0.7)
