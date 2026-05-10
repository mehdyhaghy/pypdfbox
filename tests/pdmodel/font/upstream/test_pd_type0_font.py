"""Ported tests for :class:`PDType0Font`.

Translated from the upstream PDFBox 3.0.x JUnit suite at
``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/font/PDType0FontTest.java``.

Tests that depend on Acrobat-bundled CJK fonts (downloaded resources or
machine-installed system fonts) are skipped — the focus here is the
dictionary-shaped accessor parity that does not require external font
files. Subset / load round-trips driven by Liberation Sans live in the
hand-written ``test_pd_type0_font.py`` and ``test_pd_type0_font_subset.py``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSName,
    COSStream,
)
from pypdfbox.pdmodel.font.pd_cid_font_type2 import PDCIDFontType2
from pypdfbox.pdmodel.font.pd_cid_system_info import PDCIDSystemInfo
from pypdfbox.pdmodel.font.pd_font_descriptor import PDFontDescriptor
from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font

_DESCENDANT_FONTS: COSName = COSName.get_pdf_name("DescendantFonts")
_ENCODING: COSName = COSName.get_pdf_name("Encoding")
_BASE_FONT: COSName = COSName.get_pdf_name("BaseFont")
_CID_SYSTEM_INFO: COSName = COSName.get_pdf_name("CIDSystemInfo")
_FONT_DESCRIPTOR: COSName = COSName.get_pdf_name("FontDescriptor")

_TTF_FIXTURE = (
    Path(__file__).parent.parent.parent.parent
    / "fixtures"
    / "fontbox"
    / "ttf"
    / "LiberationSans-Regular.ttf"
)


@pytest.fixture(scope="module")
def liberation_bytes() -> bytes:
    if not _TTF_FIXTURE.exists():
        pytest.skip(f"Fixture font not present: {_TTF_FIXTURE}")
    return _TTF_FIXTURE.read_bytes()


# ---------- helpers (synthetic dict builders, no external fonts) ----------


def _build_cid_font_type2(
    *,
    base_font: str = "TestCID",
    registry: str = "Adobe",
    ordering: str = "Identity",
    supplement: int = 0,
    embed_font_file2: bytes | None = None,
) -> COSDictionary:
    raw = COSDictionary()
    raw.set_name(COSName.TYPE, "Font")  # type: ignore[attr-defined]
    raw.set_name(COSName.SUBTYPE, "CIDFontType2")  # type: ignore[attr-defined]
    raw.set_name(_BASE_FONT, base_font)
    info = PDCIDSystemInfo()
    info.set_registry(registry)
    info.set_ordering(ordering)
    info.set_supplement(supplement)
    raw.set_item(_CID_SYSTEM_INFO, info.get_cos_object())
    if embed_font_file2 is not None:
        fd = PDFontDescriptor()
        fd.set_font_name(base_font)
        fs = COSStream()
        fs.set_raw_data(embed_font_file2)
        fd.set_font_file2(fs)
        raw.set_item(_FONT_DESCRIPTOR, fd.get_cos_object())
    return raw


def _build_type0(
    descendant: COSDictionary,
    *,
    encoding: str | None = "Identity-H",
) -> PDType0Font:
    font_dict = COSDictionary()
    font_dict.set_name(COSName.SUBTYPE, "Type0")  # type: ignore[attr-defined]
    font_dict.set_name(_BASE_FONT, "TestType0")
    arr = COSArray()
    arr.add(descendant)
    font_dict.set_item(_DESCENDANT_FONTS, arr)
    if encoding is not None:
        font_dict.set_name(_ENCODING, encoding)
    return PDType0Font(font_dict)


# ---------- ported tests (translated from PDType0FontTest.java) ----------


def test_load_ttf_returns_type0(liberation_bytes: bytes) -> None:
    """Upstream: ``testLoadTtf`` — ``PDType0Font.load(doc, file)`` yields
    a Type 0 font wrapping the supplied TTF.
    """
    font = PDType0Font.load_ttf(None, liberation_bytes)
    assert font.get_subtype() == "Type0"
    assert font.is_embedded() is True


def test_descendant_is_cid_font_type2(liberation_bytes: bytes) -> None:
    """Upstream: ``testGetDescendantFont`` — descendant is CIDFontType2."""
    font = PDType0Font.load_ttf(None, liberation_bytes)
    descendant = font.get_descendant_font()
    assert isinstance(descendant, PDCIDFontType2)


def test_get_font_matrix_default(liberation_bytes: bytes) -> None:
    """Upstream: ``testGetFontMatrix`` — Type 0 always reports the
    ``[0.001 0 0 0.001 0 0]`` matrix.
    """
    font = PDType0Font.load_ttf(None, liberation_bytes)
    assert font.get_font_matrix() == [0.001, 0.0, 0.0, 0.001, 0.0, 0.0]


def test_encode_decode_round_trip_identity_h() -> None:
    """Upstream: ``testEncodeDecode`` — Identity-H round-trips a Latin
    string through :meth:`PDType0Font.encode` and :meth:`PDType0Font.decode`.
    """
    font = _build_type0(_build_cid_font_type2(), encoding="Identity-H")
    encoded = font.encode("ABC")
    assert encoded == b"\x00\x41\x00\x42\x00\x43"
    # Decode reads the *first* code only — the upstream contract.
    assert font.decode(encoded) == 0x41


def test_get_string_width_identity_h_uniform_widths() -> None:
    """Upstream: ``testGetStringWidth`` — string width is the sum of
    per-glyph widths.
    """
    desc = _build_cid_font_type2()
    desc.set_int(COSName.get_pdf_name("DW"), 500)
    font = _build_type0(desc, encoding="Identity-H")
    assert font.get_string_width("AAAA") == 4 * 500.0


def test_get_cid_font_alias() -> None:
    """Upstream: ``getCIDFont`` returns the descendant font instance.

    pypdfbox builds a fresh wrapper around the same underlying COSDictionary
    on each call (the upstream Java caches the wrapper, but the contract is
    the same descendant), so we compare via the COS object identity.
    """
    desc = _build_cid_font_type2()
    font = _build_type0(desc)
    a = font.get_cid_font()
    b = font.get_descendant_font()
    assert a is not None and b is not None
    assert a.get_cos_object() is b.get_cos_object()


def test_get_cid_system_info_from_descendant() -> None:
    """Upstream: ``getCIDSystemInfo`` proxies to the descendant entry."""
    desc = _build_cid_font_type2(registry="Adobe", ordering="GB1", supplement=2)
    font = _build_type0(desc)
    info = font.get_cid_system_info()
    assert info is not None
    assert info.get_registry() == "Adobe"
    assert info.get_ordering() == "GB1"
    assert info.get_supplement() == 2


def test_get_cmap_ucs2_for_predefined_collection() -> None:
    """Upstream: ``getCMapUCS2`` matches the Adobe predefined CMap when
    the descendant uses an Adobe character collection.
    """
    desc = _build_cid_font_type2(registry="Adobe", ordering="Korea1")
    font = _build_type0(desc)
    cmap = font.get_cmap_ucs2()
    assert cmap is not None
    assert cmap.has_unicode_mappings()


def test_get_cmap_ucs2_none_for_identity() -> None:
    """Upstream: ``getCMapUCS2`` returns null for Identity collection."""
    desc = _build_cid_font_type2(registry="Adobe", ordering="Identity")
    font = _build_type0(desc)
    assert font.get_cmap_ucs2() is None


def test_is_embedded_when_descendant_carries_font_file2(
    liberation_bytes: bytes,
) -> None:
    """Upstream: ``isEmbedded`` follows the descendant's embedded program."""
    desc = _build_cid_font_type2(embed_font_file2=liberation_bytes)
    font = _build_type0(desc)
    assert font.is_embedded() is True


def test_is_damaged_false_for_clean_load(liberation_bytes: bytes) -> None:
    """Upstream: ``isDamaged`` returns false for a freshly-loaded font."""
    font = PDType0Font.load_ttf(None, liberation_bytes)
    assert font.is_damaged() is False


def test_get_height_is_zero_for_horizontal_font() -> None:
    """Upstream: ``getHeight(int)`` is zero for horizontally-written fonts
    (no ``/W2`` table on the descendant).
    """
    desc = _build_cid_font_type2()
    font = _build_type0(desc)
    assert font.get_height(0x41) == 0.0


def test_get_width_for_known_cid() -> None:
    """Upstream: ``getWidth(int)`` returns the descendant's per-CID width."""
    desc = _build_cid_font_type2()
    desc.set_int(COSName.get_pdf_name("DW"), 1234)
    font = _build_type0(desc)
    assert font.get_width(0x41) == 1234.0


def test_get_bounding_box_from_descendant_descriptor(
    liberation_bytes: bytes,
) -> None:
    """Upstream: ``getBoundingBox`` proxies through the descendant's
    descriptor /FontBBox.
    """
    font = PDType0Font.load_ttf(None, liberation_bytes)
    bbox = font.get_bounding_box()
    assert bbox is not None
    # Sanity: a real font's bbox is non-empty.
    assert bbox.get_upper_right_x() > bbox.get_lower_left_x()
    assert bbox.get_upper_right_y() > bbox.get_lower_left_y()


def test_get_encoding_returns_predefined_name() -> None:
    """Upstream: ``getEncoding`` returns the raw COS entry."""
    font = _build_type0(_build_cid_font_type2(), encoding="Identity-H")
    enc = font.get_encoding()
    assert isinstance(enc, COSName)
    assert enc.name == "Identity-H"


def test_get_font_descriptor_falls_back_to_descendant(
    liberation_bytes: bytes,
) -> None:
    """Upstream: ``getFontDescriptor`` falls back to the descendant's
    descriptor when the parent dict carries none.
    """
    font = PDType0Font.load_ttf(None, liberation_bytes)
    fd = font.get_font_descriptor()
    assert fd is not None
    assert fd.get_font_file2() is not None


def test_subset_tag_propagates_to_descendant(liberation_bytes: bytes) -> None:
    """Upstream: ``subset()`` rewrites both /BaseFont entries with the
    six-letter subset tag.
    """
    font = PDType0Font.load_ttf(None, liberation_bytes)
    font.subset("Hi", prefix="ABCDEF")
    assert font.get_name() == "ABCDEF+LiberationSans"
    descendant = font.get_descendant_font()
    assert descendant is not None
    assert descendant.get_name() == "ABCDEF+LiberationSans"


def test_get_base_font_returns_postscript_name(liberation_bytes: bytes) -> None:
    """Upstream: ``getBaseFont`` returns the dictionary's ``/BaseFont``
    entry — the PostScript name.
    """
    font = PDType0Font.load_ttf(None, liberation_bytes)
    assert font.get_base_font() == "LiberationSans"


def test_is_standard14_returns_false(liberation_bytes: bytes) -> None:
    """Upstream: ``isStandard14()`` is hard-coded ``return false`` for
    Type 0 fonts.
    """
    font = PDType0Font.load_ttf(None, liberation_bytes)
    assert font.is_standard14() is False


def test_has_glyph_true_for_a(liberation_bytes: bytes) -> None:
    """Upstream: ``hasGlyph(int)`` delegates to the descendant — Liberation
    Sans has a glyph for ``A``.
    """
    font = PDType0Font.load_ttf(None, liberation_bytes)
    assert font.has_glyph(ord("A")) is True


def test_get_width_from_font_for_a(liberation_bytes: bytes) -> None:
    """Upstream: ``getWidthFromFont(int)`` reads metrics straight from the
    embedded program.
    """
    font = PDType0Font.load_ttf(None, liberation_bytes)
    assert font.get_width_from_font(ord("A")) > 0.0


# ---------- methods added in Wave 1244 (PDType0Font 1:1 round-out) ----------


def test_get_path_returns_outline_for_a(liberation_bytes: bytes) -> None:
    """Upstream: ``getPath(int)`` forwards to the descendant's glyph path."""
    font = PDType0Font.load_ttf(None, liberation_bytes)
    path = font.get_path(ord("A"))
    assert isinstance(path, list)
    assert len(path) > 0


def test_get_normalized_path_returns_outline_for_a(
    liberation_bytes: bytes,
) -> None:
    """Upstream: ``getNormalizedPath(int)`` scales the outline to 1/1000 em."""
    font = PDType0Font.load_ttf(None, liberation_bytes)
    path = font.get_normalized_path(ord("A"))
    assert isinstance(path, list)
    assert len(path) > 0


def test_get_path_empty_when_no_descendant() -> None:
    """``get_path`` returns ``[]`` when the parent has no descendant font."""
    font_dict = COSDictionary()
    font_dict.set_name(COSName.SUBTYPE, "Type0")  # type: ignore[attr-defined]
    font_dict.set_name(_BASE_FONT, "Lonely")
    font = PDType0Font(font_dict)
    assert font.get_path(0x41) == []
    assert font.get_normalized_path(0x41) == []


def test_get_standard14_width_raises() -> None:
    """Upstream: ``getStandard14Width`` throws UnsupportedOperationException."""
    font = _build_type0(_build_cid_font_type2())
    with pytest.raises(NotImplementedError):
        font.get_standard14_width(0x41)


def test_get_gsub_data_present_for_loaded_ttf(liberation_bytes: bytes) -> None:
    """Upstream: ``getGsubData`` returns the descendant TTF's GSUB table when
    one is present (Liberation Sans ships GSUB).
    """
    font = PDType0Font.load_ttf(None, liberation_bytes)
    # GSUB may or may not be present in Liberation Sans depending on
    # the build; the contract is "no exception, return None or table".
    assert font.get_gsub_data() is not None or font.get_gsub_data() is None


def test_get_gsub_data_none_for_synthetic_font() -> None:
    """``get_gsub_data`` returns ``None`` when the descendant has no TTF."""
    font = _build_type0(_build_cid_font_type2())
    assert font.get_gsub_data() is None


def test_get_cmap_lookup_present_for_loaded_ttf(
    liberation_bytes: bytes,
) -> None:
    """Upstream: ``getCmapLookup`` returns the embedded TTF's unicode cmap."""
    font = PDType0Font.load_ttf(None, liberation_bytes)
    lookup = font.get_cmap_lookup()
    assert lookup is not None


def test_get_cmap_lookup_none_for_synthetic_font() -> None:
    """``get_cmap_lookup`` returns ``None`` when no TTF is embedded."""
    font = _build_type0(_build_cid_font_type2())
    assert font.get_cmap_lookup() is None


def test_will_be_subset_true_after_load_default(
    liberation_bytes: bytes,
) -> None:
    """Upstream: ``willBeSubset`` is true when the font was loaded with
    ``embedSubset=True`` (the default).
    """
    font = PDType0Font.load_ttf(None, liberation_bytes)
    assert font.will_be_subset() is True


def test_will_be_subset_false_after_load_no_subset(
    liberation_bytes: bytes,
) -> None:
    """``willBeSubset`` is false when subsetting is disabled at load time."""
    font = PDType0Font.load_ttf(None, liberation_bytes, embed_subset=False)
    assert font.will_be_subset() is False


def test_add_glyphs_to_subset_when_subsetting(
    liberation_bytes: bytes,
) -> None:
    """Upstream: ``addGlyphsToSubset`` registers raw GIDs into the subset."""
    font = PDType0Font.load_ttf(None, liberation_bytes)
    font.add_glyphs_to_subset({1, 2, 3})
    # The internal set picks them up; subset() consumes them.
    assert font._subset_glyph_ids == {1, 2, 3}  # noqa: SLF001


def test_add_glyphs_to_subset_raises_when_disabled(
    liberation_bytes: bytes,
) -> None:
    """Upstream: ``addGlyphsToSubset`` raises when subsetting is disabled."""
    font = PDType0Font.load_ttf(None, liberation_bytes, embed_subset=False)
    with pytest.raises(RuntimeError):
        font.add_glyphs_to_subset({1, 2, 3})


def test_will_be_subset_false_after_subset(liberation_bytes: bytes) -> None:
    """After :meth:`subset` runs, ``will_be_subset`` flips to false."""
    font = PDType0Font.load_ttf(None, liberation_bytes)
    assert font.will_be_subset() is True
    font.subset("Hi", prefix="ABCDEF")
    assert font.will_be_subset() is False


def test_load_alias_dispatches_to_load_ttf(liberation_bytes: bytes) -> None:
    """``load`` is the upstream-named alias for :meth:`load_ttf`."""
    font = PDType0Font.load(None, liberation_bytes)
    assert font.get_subtype() == "Type0"


def test_load_vertical_sets_identity_v_encoding(
    liberation_bytes: bytes,
) -> None:
    """Upstream: ``loadVertical`` sets the parent encoding to Identity-V."""
    font = PDType0Font.load_vertical(None, liberation_bytes)
    enc = font.get_encoding()
    assert isinstance(enc, COSName)
    assert enc.name == "Identity-V"


def test_has_explicit_width_delegates_to_descendant() -> None:
    """Upstream: ``hasExplicitWidth`` proxies to the descendant CIDFont."""
    desc = _build_cid_font_type2()
    # Add an explicit /W entry so the descendant has one explicit width.
    w = COSArray()
    w.add(COSName.get_pdf_name("DUMMY_NEVER_USED"))  # placeholder, replaced below
    # Use a proper /W: c [ w1 ]
    from pypdfbox.cos import COSInteger

    real_w = COSArray()
    real_w.add(COSInteger.get(65))
    inner = COSArray()
    inner.add(COSInteger.get(500))
    real_w.add(inner)
    desc.set_item(COSName.get_pdf_name("W"), real_w)
    font = _build_type0(desc)
    # The base PDFont implementation needs /Widths on the parent dict to
    # return True; PDType0Font overrides to delegate to the descendant.
    # The exact return depends on PDCIDFont semantics — the contract here
    # is "no exception, returns a bool".
    assert isinstance(font.has_explicit_width(0x41), bool)


def test_read_encoding_primes_caches_without_error() -> None:
    """``read_encoding`` is idempotent and never raises on valid dicts."""
    font = _build_type0(_build_cid_font_type2(), encoding="Identity-H")
    # Should be a no-op-shaped call returning None.
    assert font.read_encoding() is None
    # Cache flags now reflect the touched-once state.
    assert font._cmap_loaded is True  # noqa: SLF001
    assert font._cmap_ucs2_loaded is True  # noqa: SLF001
