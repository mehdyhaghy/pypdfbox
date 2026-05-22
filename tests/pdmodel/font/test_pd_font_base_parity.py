from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSInteger, COSName, COSStream
from pypdfbox.fontbox.cmap.cmap import CMap
from pypdfbox.pdmodel.font import PDFont, PDFontDescriptor
from pypdfbox.pdmodel.font.pd_font import _DEFAULT_SPACE_WIDTH


# PDFont is conceptually abstract — concrete subclasses set ``SUB_TYPE`` and
# add behaviour. For base-class parity we drive the methods through a thin
# concrete stand-in so we exercise *only* the inherited PDFont surface and
# never accidentally hit a subclass override.
class _BarePDFont(PDFont):
    """Bare concrete PDFont subclass for base-method parity tests."""

    SUB_TYPE = None


# ---------- defaults on a fresh empty font ----------


def test_bare_font_is_embedded_false_when_no_descriptor() -> None:
    font = _BarePDFont()
    assert font.is_embedded() is False


def test_bare_font_is_embedded_false_when_descriptor_has_no_font_file() -> None:
    font = _BarePDFont()
    fd = PDFontDescriptor()
    font.set_font_descriptor(fd)
    assert font.is_embedded() is False


def test_bare_font_is_damaged_default_false() -> None:
    assert _BarePDFont().is_damaged() is False


def test_bare_font_get_widths_default_empty() -> None:
    assert _BarePDFont().get_widths() == []


def test_bare_font_get_first_char_default_minus_one() -> None:
    assert _BarePDFont().get_first_char() == -1


def test_bare_font_get_last_char_default_minus_one() -> None:
    assert _BarePDFont().get_last_char() == -1


def test_bare_font_get_average_font_width_default_zero() -> None:
    assert _BarePDFont().get_average_font_width() == 0.0


def test_bare_font_get_space_width_defaults_to_250() -> None:
    assert _BarePDFont().get_space_width() == 250.0


def test_bare_font_is_subset_false_when_no_base_font() -> None:
    assert _BarePDFont().is_subset() is False


# ---------- /BaseFont subset prefix detection ----------


def test_is_subset_true_for_six_letter_prefix() -> None:
    font = _BarePDFont()
    font.get_cos_object().set_name(COSName.get_pdf_name("BaseFont"), "ABCDEF+Helvetica")
    assert font.is_subset() is True


def test_is_subset_false_for_plain_base_font() -> None:
    font = _BarePDFont()
    font.get_cos_object().set_name(COSName.get_pdf_name("BaseFont"), "Helvetica")
    assert font.is_subset() is False


def test_is_subset_false_for_non_uppercase_prefix() -> None:
    # Mixed-case prefix is not a valid PDF subset marker.
    font = _BarePDFont()
    font.get_cos_object().set_name(COSName.get_pdf_name("BaseFont"), "AbCdEf+Helvetica")
    assert font.is_subset() is False


def test_is_subset_false_for_short_prefix() -> None:
    # Five-letter prefix does not match the six-letter rule.
    font = _BarePDFont()
    font.get_cos_object().set_name(COSName.get_pdf_name("BaseFont"), "ABCDE+Helvetica")
    assert font.is_subset() is False


# ---------- is_embedded across each /FontFile* slot ----------


def _font_with_font_file_key(key_name: str) -> _BarePDFont:
    font = _BarePDFont()
    fd = PDFontDescriptor()
    fd.get_cos_object().set_item(COSName.get_pdf_name(key_name), COSStream())
    font.set_font_descriptor(fd)
    return font


def test_is_embedded_true_when_font_file_present() -> None:
    assert _font_with_font_file_key("FontFile").is_embedded() is True


def test_is_embedded_true_when_font_file2_present() -> None:
    assert _font_with_font_file_key("FontFile2").is_embedded() is True


def test_is_embedded_true_when_font_file3_present() -> None:
    assert _font_with_font_file_key("FontFile3").is_embedded() is True


# ---------- /Widths-driven accessors ----------


def test_get_widths_reads_int_and_float_entries() -> None:
    font = _BarePDFont()
    arr = COSArray([COSInteger.get(250), COSInteger.get(333), COSFloat(408.5)])
    font.get_cos_object().set_item(COSName.get_pdf_name("Widths"), arr)
    assert font.get_widths() == [250.0, 333.0, 408.5]


def test_get_first_and_last_char_round_trip() -> None:
    font = _BarePDFont()
    cos = font.get_cos_object()
    cos.set_int(COSName.get_pdf_name("FirstChar"), 32)
    cos.set_int(COSName.get_pdf_name("LastChar"), 126)
    assert font.get_first_char() == 32
    assert font.get_last_char() == 126


def test_get_average_font_width_returns_mean_of_positive_widths() -> None:
    font = _BarePDFont()
    # Mean of positive entries (zero entries — typically .notdef — are skipped)
    arr = COSArray(
        [
            COSInteger.get(250),
            COSInteger.get(500),
            COSInteger.get(0),  # skipped
            COSInteger.get(750),
        ]
    )
    font.get_cos_object().set_item(COSName.get_pdf_name("Widths"), arr)
    assert font.get_average_font_width() == 500.0


def test_get_space_width_uses_widths_offset_by_first_char() -> None:
    font = _BarePDFont()
    cos = font.get_cos_object()
    cos.set_int(COSName.get_pdf_name("FirstChar"), 30)
    # Index 32 - 30 = 2 → expect 600.0
    arr = COSArray(
        [COSInteger.get(100), COSInteger.get(200), COSInteger.get(600), COSInteger.get(800)]
    )
    cos.set_item(COSName.get_pdf_name("Widths"), arr)
    assert font.get_space_width() == 600.0


def test_get_space_width_falls_back_to_average_when_index_out_of_range() -> None:
    # /FirstChar = 100 puts code 32 below the start of /Widths so the
    # direct lookup fails. Mirroring upstream PDFBox ``getSpaceWidth``,
    # the chain then reaches ``getAverageFontWidth`` (the only positive
    # entry is 500 → avg 500) before falling through to 250.
    font = _BarePDFont()
    cos = font.get_cos_object()
    cos.set_int(COSName.get_pdf_name("FirstChar"), 100)
    cos.set_item(COSName.get_pdf_name("Widths"), COSArray([COSInteger.get(500)]))
    assert font.get_space_width() == 500.0


def test_get_space_width_falls_back_to_250_with_no_signal() -> None:
    # Bare font with no /Widths, no /ToUnicode, no descriptor — every
    # upstream lookup path returns nothing usable, so the ultimate
    # PDFBox fallback (250 = 1/4 em) wins.
    assert _BarePDFont().get_space_width() == _DEFAULT_SPACE_WIDTH


# ---------- wrapping a pre-built dict preserves base behaviour ----------


def test_wrapping_existing_dict_with_subset_base_font() -> None:
    raw = COSDictionary()
    raw.set_name(COSName.get_pdf_name("BaseFont"), "ZZZZZZ+Times-Roman")
    font = _BarePDFont(raw)
    assert font.is_subset() is True
    assert font.get_name() == "ZZZZZZ+Times-Roman"


# ---------- get_type ----------


def test_get_type_returns_font_for_fresh_dict() -> None:
    # Fresh dict — the constructor writes /Type = Font.
    assert _BarePDFont().get_type() == "Font"


def test_get_type_returns_existing_value_when_wrapping() -> None:
    raw = COSDictionary()
    raw.set_name(COSName.TYPE, "Font")  # type: ignore[attr-defined]
    font = _BarePDFont(raw)
    assert font.get_type() == "Font"


def test_get_type_returns_none_when_type_missing() -> None:
    # Wrap a dict that already has *some* /Type entry so the constructor
    # doesn't overwrite it, then drop the entry to exercise the absent
    # path. (A naked empty dict gets /Type backfilled by __init__.)
    raw = COSDictionary()
    raw.set_name(COSName.TYPE, "Placeholder")  # type: ignore[attr-defined]
    font = _BarePDFont(raw)
    raw.remove_item(COSName.TYPE)  # type: ignore[attr-defined]
    assert font.get_type() is None


# ---------- is_standard14 (base PDFont) ----------


def test_is_standard14_true_for_canonical_base_font() -> None:
    font = _BarePDFont()
    font.get_cos_object().set_name(COSName.get_pdf_name("BaseFont"), "Helvetica")
    assert font.is_standard14() is True


def test_is_standard14_true_for_alias_base_font() -> None:
    font = _BarePDFont()
    font.get_cos_object().set_name(COSName.get_pdf_name("BaseFont"), "ArialMT")
    assert font.is_standard14() is True


def test_is_standard14_false_for_non_standard_base_font() -> None:
    font = _BarePDFont()
    font.get_cos_object().set_name(COSName.get_pdf_name("BaseFont"), "MyCustomFont")
    assert font.is_standard14() is False


def test_is_standard14_false_when_base_font_absent() -> None:
    assert _BarePDFont().is_standard14() is False


def test_is_standard14_false_when_font_program_embedded() -> None:
    # Acrobat treats embedded fonts as never being Standard 14, even when
    # /BaseFont says Helvetica — see PDFBOX-2372.
    font = _BarePDFont()
    font.get_cos_object().set_name(COSName.get_pdf_name("BaseFont"), "Helvetica")
    fd = PDFontDescriptor()
    fd.get_cos_object().set_item(COSName.get_pdf_name("FontFile"), COSStream())
    font.set_font_descriptor(fd)
    assert font.is_standard14() is False


# ---------- equality / hashing (COS-identity-based) ----------


def test_equality_compares_underlying_cos_dict_identity() -> None:
    raw = COSDictionary()
    raw.set_name(COSName.get_pdf_name("BaseFont"), "Helvetica")
    a = _BarePDFont(raw)
    b = _BarePDFont(raw)
    # Same underlying dict -> equal.
    assert a == b
    # Distinct dicts with identical content -> not equal (mirrors PDFBox).
    other_raw = COSDictionary()
    other_raw.set_name(COSName.get_pdf_name("BaseFont"), "Helvetica")
    assert _BarePDFont(other_raw) != a


def test_equality_against_non_pdfont_returns_false() -> None:
    assert _BarePDFont() != COSDictionary()
    assert _BarePDFont() != "not a font"
    assert _BarePDFont() != None  # noqa: E711 — explicit None compare under test


def test_hash_matches_equality_contract() -> None:
    raw = COSDictionary()
    a = _BarePDFont(raw)
    b = _BarePDFont(raw)
    # equal -> identical hash
    assert hash(a) == hash(b)
    # usable as a dict key
    seen = {a: "first"}
    seen[b] = "second"
    assert len(seen) == 1


# ---------- repr / str ----------


def test_repr_includes_class_name_and_base_font() -> None:
    font = _BarePDFont()
    font.get_cos_object().set_name(COSName.get_pdf_name("BaseFont"), "Times-Roman")
    assert repr(font) == "_BarePDFont Times-Roman"
    # str() shares the same formatter.
    assert str(font) == "_BarePDFont Times-Roman"


def test_repr_falls_back_to_class_name_when_base_font_missing() -> None:
    assert repr(_BarePDFont()) == "_BarePDFont"


# ---------- get_font_matrix / DEFAULT_FONT_MATRIX ----------


def test_get_font_matrix_defaults_to_simple_font_transform() -> None:
    # The base default mirrors PDF 32000-1 §9.2.4 — 1/1000-em scaling.
    assert _BarePDFont().get_font_matrix() == [0.001, 0.0, 0.0, 0.001, 0.0, 0.0]


def test_get_font_matrix_returns_a_fresh_list_each_call() -> None:
    # Mutating the returned list must not corrupt the class default.
    font = _BarePDFont()
    first = font.get_font_matrix()
    first[0] = 99.0
    assert font.get_font_matrix() == [0.001, 0.0, 0.0, 0.001, 0.0, 0.0]


def test_default_font_matrix_class_constant_exposed() -> None:
    # Upstream callers reach for the class attribute by name; mirror that.
    assert PDFont.DEFAULT_FONT_MATRIX == (0.001, 0.0, 0.0, 0.001, 0.0, 0.0)


# ---------- has_to_unicode / get_to_unicode_cmap ----------


def test_has_to_unicode_false_when_absent() -> None:
    assert _BarePDFont().has_to_unicode() is False


def test_has_to_unicode_true_when_stream_present() -> None:
    font = _BarePDFont()
    font.get_cos_object().set_item(COSName.get_pdf_name("ToUnicode"), COSStream())
    assert font.has_to_unicode() is True


def test_has_to_unicode_true_when_predefined_name_present() -> None:
    # ``/ToUnicode /Identity-H`` is a legal PDF 32000-1 §9.10.3 shortcut.
    font = _BarePDFont()
    font.get_cos_object().set_item(
        COSName.get_pdf_name("ToUnicode"), COSName.get_pdf_name("Identity-H")
    )
    assert font.has_to_unicode() is True


def test_get_to_unicode_cmap_returns_none_when_absent() -> None:
    assert _BarePDFont().get_to_unicode_cmap() is None


def test_get_to_unicode_cmap_parses_predefined_name() -> None:
    font = _BarePDFont()
    font.get_cos_object().set_item(
        COSName.get_pdf_name("ToUnicode"), COSName.get_pdf_name("Identity-H")
    )
    cmap = font.get_to_unicode_cmap()
    assert isinstance(cmap, CMap)


def test_get_to_unicode_cmap_caches_result() -> None:
    # Second call must return the *same* object — we must not reparse.
    font = _BarePDFont()
    font.get_cos_object().set_item(
        COSName.get_pdf_name("ToUnicode"), COSName.get_pdf_name("Identity-H")
    )
    cmap = font.get_to_unicode_cmap()
    assert font.get_to_unicode_cmap() is cmap


def test_get_to_unicode_cmap_returns_none_for_non_name_non_stream_entry() -> None:
    # /ToUnicode must be a stream or a predefined name — anything else
    # (bool/int/array/dict) yields a None result instead of raising.
    font = _BarePDFont()
    font.get_cos_object().set_item(COSName.get_pdf_name("ToUnicode"), COSArray())
    assert font.get_to_unicode_cmap() is None


def test_get_to_unicode_cmap_caches_negative_result() -> None:
    # Even when parsing fails we must not retry — the loaded flag
    # latches to True after the first attempt.
    font = _BarePDFont()
    font.get_cos_object().set_item(
        COSName.get_pdf_name("ToUnicode"), COSName.get_pdf_name("NoSuchPredefinedCMap")
    )
    assert font.get_to_unicode_cmap() is None
    # Mutate the dict to a now-valid value; the cache must keep returning None.
    font.get_cos_object().set_item(
        COSName.get_pdf_name("ToUnicode"), COSName.get_pdf_name("Identity-H")
    )
    assert font.get_to_unicode_cmap() is None


# ---------- get_width / get_widths-driven cache (new in this round) ----------


def test_get_width_uses_dict_widths_offset_by_first_char() -> None:
    # /FirstChar = 32, /LastChar = 34 → code 33 is widths[1] = 333.
    font = _BarePDFont()
    cos = font.get_cos_object()
    cos.set_int(COSName.get_pdf_name("FirstChar"), 32)
    cos.set_int(COSName.get_pdf_name("LastChar"), 34)
    cos.set_item(
        COSName.get_pdf_name("Widths"),
        COSArray([COSInteger.get(250), COSInteger.get(333), COSInteger.get(408)]),
    )
    assert font.get_width(32) == 250.0
    assert font.get_width(33) == 333.0
    assert font.get_width(34) == 408.0


def test_get_width_falls_back_to_missing_width_when_outside_range() -> None:
    font = _BarePDFont()
    cos = font.get_cos_object()
    cos.set_int(COSName.get_pdf_name("FirstChar"), 32)
    cos.set_int(COSName.get_pdf_name("LastChar"), 34)
    cos.set_item(
        COSName.get_pdf_name("Widths"),
        COSArray([COSInteger.get(250), COSInteger.get(333), COSInteger.get(408)]),
    )
    fd = PDFontDescriptor()
    fd.set_missing_width(777.0)
    font.set_font_descriptor(fd)
    # Code 50 is outside [32..34] so the widths array is skipped — the
    # descriptor's /MissingWidth wins.
    assert font.get_width(50) == 777.0


def test_get_width_caches_per_code_lookup() -> None:
    font = _BarePDFont()
    cos = font.get_cos_object()
    cos.set_int(COSName.get_pdf_name("FirstChar"), 32)
    cos.set_int(COSName.get_pdf_name("LastChar"), 32)
    cos.set_item(COSName.get_pdf_name("Widths"), COSArray([COSInteger.get(250)]))
    # First lookup populates cache; mutate the array — cached value wins.
    assert font.get_width(32) == 250.0
    cos.set_item(COSName.get_pdf_name("Widths"), COSArray([COSInteger.get(999)]))
    assert font.get_width(32) == 250.0


def test_get_width_raises_when_no_dict_widths_and_no_font_program() -> None:
    # No /Widths, no /MissingWidth, not Standard 14 → falls through to the
    # abstract get_width_from_font hook which the bare base raises.
    import pytest

    font = _BarePDFont()
    with pytest.raises(NotImplementedError):
        font.get_width(65)


def test_has_explicit_width_true_inside_range() -> None:
    font = _BarePDFont()
    cos = font.get_cos_object()
    cos.set_int(COSName.get_pdf_name("FirstChar"), 32)
    cos.set_item(
        COSName.get_pdf_name("Widths"),
        COSArray([COSInteger.get(250), COSInteger.get(333)]),
    )
    assert font.has_explicit_width(32) is True
    assert font.has_explicit_width(33) is True
    # Outside the array — no explicit width.
    assert font.has_explicit_width(34) is False
    # Below /FirstChar — no explicit width.
    assert font.has_explicit_width(31) is False


def test_has_explicit_width_false_when_widths_missing() -> None:
    assert _BarePDFont().has_explicit_width(32) is False


# ---------- abstract method placeholders raise on bare base ----------


def test_encode_codepoint_raises_not_implemented_on_bare_base() -> None:
    import pytest

    with pytest.raises(NotImplementedError):
        _BarePDFont().encode_codepoint(65)


def test_encode_string_raises_via_encode_codepoint_on_bare_base() -> None:
    # encode(text) walks codepoints and asks encode_codepoint per char,
    # so a non-empty string also raises.
    import pytest

    with pytest.raises(NotImplementedError):
        _BarePDFont().encode("A")


def test_encode_empty_string_returns_empty_bytes_on_bare_base() -> None:
    # Empty string never visits encode_codepoint, so it must succeed.
    assert _BarePDFont().encode("") == b""


def test_read_code_raises_not_implemented_on_bare_base() -> None:
    import pytest

    with pytest.raises(NotImplementedError):
        _BarePDFont().read_code(b"\x41")


def test_get_width_from_font_raises_not_implemented_on_bare_base() -> None:
    import pytest

    with pytest.raises(NotImplementedError):
        _BarePDFont().get_width_from_font(65)


def test_get_height_raises_not_implemented_on_bare_base() -> None:
    import pytest

    with pytest.raises(NotImplementedError):
        _BarePDFont().get_height(65)


def test_get_string_width_propagates_when_subclass_unimplemented() -> None:
    import pytest

    with pytest.raises(NotImplementedError):
        _BarePDFont().get_string_width("Hi")


def test_get_string_width_empty_string_is_zero() -> None:
    # Empty input never reaches encode_codepoint/read_code so it must
    # succeed and return 0.0 even on the bare base.
    assert _BarePDFont().get_string_width("") == 0.0


def test_get_standard14_width_raises_on_bare_base() -> None:
    import pytest

    with pytest.raises(NotImplementedError):
        _BarePDFont().get_standard14_width(65)


def test_subset_methods_raise_not_implemented_on_bare_base() -> None:
    import pytest

    font = _BarePDFont()
    with pytest.raises(NotImplementedError):
        font.add_to_subset(65)
    with pytest.raises(NotImplementedError):
        font.subset()


def test_will_be_subset_default_false() -> None:
    assert _BarePDFont().will_be_subset() is False


def test_is_vertical_default_false() -> None:
    assert _BarePDFont().is_vertical() is False


# ---------- get_position_vector / get_displacement ----------


def test_get_position_vector_raises_for_horizontal_default() -> None:
    # Mirrors upstream: base PDFont rejects position-vector lookups
    # because horizontal-only fonts have no such concept.
    import pytest

    with pytest.raises(NotImplementedError):
        _BarePDFont().get_position_vector(65)


def test_get_displacement_returns_width_over_1000_x_zero_y() -> None:
    # Code 65 → width 500 → displacement (0.5, 0.0).
    font = _BarePDFont()
    cos = font.get_cos_object()
    cos.set_int(COSName.get_pdf_name("FirstChar"), 65)
    cos.set_int(COSName.get_pdf_name("LastChar"), 65)
    cos.set_item(COSName.get_pdf_name("Widths"), COSArray([COSInteger.get(500)]))
    assert font.get_displacement(65) == (0.5, 0.0)


# ---------- get_bounding_box ----------


def test_get_bounding_box_returns_none_when_no_descriptor() -> None:
    assert _BarePDFont().get_bounding_box() is None


def test_get_bounding_box_reads_descriptor_font_bbox() -> None:
    from pypdfbox.pdmodel.pd_rectangle import PDRectangle

    font = _BarePDFont()
    fd = PDFontDescriptor()
    bbox = COSArray(
        [
            COSInteger.get(-170),
            COSInteger.get(-228),
            COSInteger.get(1003),
            COSInteger.get(962),
        ]
    )
    fd.set_font_b_box(bbox)
    font.set_font_descriptor(fd)
    out = font.get_bounding_box()
    assert isinstance(out, PDRectangle)
    assert out.get_lower_left_x() == -170.0
    assert out.get_upper_right_y() == 962.0


# ---------- to_unicode (base impl) ----------


def test_to_unicode_returns_none_when_no_to_unicode_cmap() -> None:
    # Base impl deliberately returns None so subclasses can plug in
    # encoding-based glyph-list resolution.
    assert _BarePDFont().to_unicode(65) is None


def test_to_unicode_returns_chr_for_identity_named_to_unicode() -> None:
    # Mirrors PDFBOX-3123: when /ToUnicode is the literal name
    # /Identity-H, the code is returned as ``chr(code)`` even though
    # Identity-H has no real unicode mappings.
    font = _BarePDFont()
    font.get_cos_object().set_item(
        COSName.get_pdf_name("ToUnicode"), COSName.get_pdf_name("Identity-H")
    )
    assert font.to_unicode(0x41) == "A"
    assert font.to_unicode(0x4E2D) == "中"


# ---------- get_standard14_afm ----------


def test_get_standard14_afm_returns_afm_for_canonical_name() -> None:
    from pypdfbox.pdmodel.font.afm_loader import AfmMetrics

    font = _BarePDFont()
    font.get_cos_object().set_name(COSName.get_pdf_name("BaseFont"), "Helvetica")
    afm = font.get_standard14_afm()
    assert isinstance(afm, AfmMetrics)
    assert afm.get_font_name() == "Helvetica"


def test_get_standard14_afm_returns_none_for_unknown_name() -> None:
    font = _BarePDFont()
    font.get_cos_object().set_name(COSName.get_pdf_name("BaseFont"), "MyCustomFont")
    assert font.get_standard14_afm() is None


def test_get_standard14_afm_returns_none_when_base_font_missing() -> None:
    assert _BarePDFont().get_standard14_afm() is None


def test_get_standard14_afm_caches_lookup() -> None:
    font = _BarePDFont()
    font.get_cos_object().set_name(COSName.get_pdf_name("BaseFont"), "Times-Roman")
    first = font.get_standard14_afm()
    assert first is not None
    # Same instance on second access — no re-parse.
    assert font.get_standard14_afm() is first


# ---------- get_average_font_width / get_space_width memoisation ----------


def test_get_average_font_width_cached_after_first_call() -> None:
    font = _BarePDFont()
    cos = font.get_cos_object()
    cos.set_item(
        COSName.get_pdf_name("Widths"),
        COSArray([COSInteger.get(250), COSInteger.get(750)]),
    )
    assert font.get_average_font_width() == 500.0
    # Mutate /Widths — cached value must hold.
    cos.set_item(
        COSName.get_pdf_name("Widths"),
        COSArray([COSInteger.get(100)]),
    )
    assert font.get_average_font_width() == 500.0


def test_get_space_width_cached_after_first_call() -> None:
    font = _BarePDFont()
    cos = font.get_cos_object()
    cos.set_int(COSName.get_pdf_name("FirstChar"), 32)
    cos.set_item(COSName.get_pdf_name("Widths"), COSArray([COSInteger.get(600)]))
    assert font.get_space_width() == 600.0
    # Drop /Widths — cached value still wins.
    cos.remove_item(COSName.get_pdf_name("Widths"))
    assert font.get_space_width() == 600.0
