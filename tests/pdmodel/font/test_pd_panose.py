"""Hand-written tests for :class:`PDPanose` and :class:`PDPanoseClassification`.

Upstream Java has no checked-in unit tests for either class —
``PDFontDescriptor.getPanose()`` is exercised indirectly through
``FontMapperImpl``. These tests pin the direct surface (constructors,
accessors, byte-level slicing, value semantics) plus the pypdfbox
extensions (family-kind constants, ``is_*`` predicates,
``from_family_class_and_classification`` factory, ``CLASSIFICATION_OFFSET``).
"""

from __future__ import annotations

import pytest

from pypdfbox.pdmodel.font.pd_font_descriptor import (
    PDPanose,
    PDPanoseClassification,
)


# ---------------------------------------------------------------------------
# PDPanoseClassification — accessors
# ---------------------------------------------------------------------------


def _classification_bytes() -> bytes:
    # Distinct values per byte so accessor mistakes are obvious.
    return bytes([2, 11, 6, 3, 5, 4, 5, 2, 2, 4])


def test_classification_length_constant() -> None:
    assert PDPanoseClassification.LENGTH == 10


def test_classification_constructor_stores_bytes_verbatim() -> None:
    payload = _classification_bytes()
    cls_obj = PDPanoseClassification(payload)
    assert cls_obj.get_bytes() == payload


def test_classification_constructor_accepts_bytearray() -> None:
    payload = bytearray(_classification_bytes())
    cls_obj = PDPanoseClassification(payload)
    # Stored as immutable bytes regardless of input type.
    assert isinstance(cls_obj.get_bytes(), bytes)
    assert cls_obj.get_bytes() == bytes(payload)


def test_classification_per_byte_accessors() -> None:
    cls_obj = PDPanoseClassification(_classification_bytes())
    assert cls_obj.get_family_kind() == 2
    assert cls_obj.get_serif_style() == 11
    assert cls_obj.get_weight() == 6
    assert cls_obj.get_proportion() == 3
    assert cls_obj.get_contrast() == 5
    assert cls_obj.get_stroke_variation() == 4
    assert cls_obj.get_arm_style() == 5
    assert cls_obj.get_letterform() == 2
    assert cls_obj.get_midline() == 2
    assert cls_obj.get_x_height() == 4


def test_classification_short_buffer_raises_index_error_on_demand() -> None:
    """Upstream stores bytes verbatim — accessors past the end raise."""
    cls_obj = PDPanoseClassification(b"\x01\x02\x03")  # only 3 bytes
    assert cls_obj.get_family_kind() == 1
    assert cls_obj.get_serif_style() == 2
    assert cls_obj.get_weight() == 3
    with pytest.raises(IndexError):
        cls_obj.get_proportion()


# ---------------------------------------------------------------------------
# PDPanoseClassification — family-kind constants & predicates (pypdfbox ext)
# ---------------------------------------------------------------------------


def test_family_kind_constants_match_microsoft_os2_spec() -> None:
    """Microsoft OS/2 spec table — pin the values so a stray refactor
    cannot silently change them."""
    assert PDPanoseClassification.FAMILY_KIND_ANY == 0
    assert PDPanoseClassification.FAMILY_KIND_NO_FIT == 1
    assert PDPanoseClassification.FAMILY_KIND_LATIN_TEXT == 2
    assert PDPanoseClassification.FAMILY_KIND_LATIN_HAND_WRITTEN == 3
    assert PDPanoseClassification.FAMILY_KIND_LATIN_DECORATIVE == 4
    assert PDPanoseClassification.FAMILY_KIND_LATIN_SYMBOL == 5


def test_is_any_true_for_family_kind_zero() -> None:
    cls_obj = PDPanoseClassification(b"\x00" + b"\x00" * 9)
    assert cls_obj.is_any() is True
    assert cls_obj.is_no_fit() is False
    assert cls_obj.is_latin_text() is False


def test_is_no_fit_true_for_family_kind_one() -> None:
    cls_obj = PDPanoseClassification(b"\x01" + b"\x00" * 9)
    assert cls_obj.is_any() is False
    assert cls_obj.is_no_fit() is True
    assert cls_obj.is_latin_text() is False


def test_is_latin_text_true_for_family_kind_two() -> None:
    cls_obj = PDPanoseClassification(b"\x02" + b"\x00" * 9)
    assert cls_obj.is_any() is False
    assert cls_obj.is_no_fit() is False
    assert cls_obj.is_latin_text() is True


@pytest.mark.parametrize("family_kind", [3, 4, 5, 6, 99, 255])
def test_predicates_all_false_for_other_family_kinds(family_kind: int) -> None:
    cls_obj = PDPanoseClassification(bytes([family_kind]) + b"\x00" * 9)
    assert cls_obj.is_any() is False
    assert cls_obj.is_no_fit() is False
    assert cls_obj.is_latin_text() is False


# ---------------------------------------------------------------------------
# PDPanoseClassification — value semantics
# ---------------------------------------------------------------------------


def test_classification_eq_same_bytes() -> None:
    a = PDPanoseClassification(_classification_bytes())
    b = PDPanoseClassification(_classification_bytes())
    assert a == b
    # Distinct objects, same hash.
    assert hash(a) == hash(b)


def test_classification_eq_against_non_classification_returns_not_implemented() -> None:
    cls_obj = PDPanoseClassification(_classification_bytes())
    # Direct ``==`` returns False because Python falls back when both sides
    # return NotImplemented.
    assert (cls_obj == _classification_bytes()) is False
    assert (cls_obj == 42) is False


def test_classification_bytes_dunder() -> None:
    payload = _classification_bytes()
    cls_obj = PDPanoseClassification(payload)
    assert bytes(cls_obj) == payload


def test_classification_len_dunder_reflects_actual_buffer() -> None:
    assert len(PDPanoseClassification(b"\x00" * 10)) == 10
    # Short or over-long buffers report their actual length, not LENGTH.
    assert len(PDPanoseClassification(b"\x00" * 5)) == 5
    assert len(PDPanoseClassification(b"\x00" * 16)) == 16


def test_classification_str_format_matches_upstream_shape() -> None:
    cls_obj = PDPanoseClassification(_classification_bytes())
    assert str(cls_obj) == (
        "{ FamilyKind = 2, SerifStyle = 11, Weight = 6, Proportion = 3, "
        "Contrast = 5, StrokeVariation = 4, ArmStyle = 5, Letterform = 2, "
        "Midline = 2, XHeight = 4}"
    )


def test_classification_repr_includes_raw_bytes() -> None:
    cls_obj = PDPanoseClassification(b"\x00\x01")
    text = repr(cls_obj)
    assert text.startswith("PDPanoseClassification(")
    assert "b'\\x00\\x01'" in text


# ---------------------------------------------------------------------------
# PDPanose — basic surface
# ---------------------------------------------------------------------------


def _panose_bytes() -> bytes:
    # 12 bytes: 2-byte sFamilyClass (0x0008) + 10-byte PANOSE classification.
    return bytes([0x00, 0x08, 2, 11, 6, 3, 5, 4, 5, 2, 2, 4])


def test_panose_length_constant() -> None:
    assert PDPanose.LENGTH == 12


def test_panose_classification_offset_constant() -> None:
    """Pin the byte offset where the embedded PANOSE-10 starts."""
    assert PDPanose.CLASSIFICATION_OFFSET == 2


def test_panose_get_bytes_round_trip() -> None:
    payload = _panose_bytes()
    p = PDPanose(payload)
    assert p.get_bytes() == payload


def test_panose_get_family_class_signed_positive() -> None:
    p = PDPanose(_panose_bytes())
    assert p.get_family_class() == 8


def test_panose_get_family_class_signed_negative_round_trip() -> None:
    # bytes[0] = 0xFF, bytes[1] = 0x80 — Java would compute
    # ((-1) << 8) | (0x80 & 0xFF) = -128.
    p = PDPanose(b"\xff\x80" + b"\x00" * 10)
    assert p.get_family_class() == -128


def test_panose_get_panose_returns_classification_with_correct_slice() -> None:
    p = PDPanose(_panose_bytes())
    cls_obj = p.get_panose()
    assert isinstance(cls_obj, PDPanoseClassification)
    # Should equal the classification built directly from bytes 2..12.
    assert cls_obj == PDPanoseClassification(_classification_bytes())


def test_panose_get_panose_slice_uses_classification_offset_constant() -> None:
    """If CLASSIFICATION_OFFSET drifts, this test will catch it."""
    payload = b"\xff\xfe" + bytes(range(10))  # head + 10 bytes 0..9
    p = PDPanose(payload)
    classification = p.get_panose()
    # The 10 trailing bytes should be exactly bytes(range(10)).
    assert classification.get_bytes() == bytes(range(10))


# ---------------------------------------------------------------------------
# PDPanose — with_panose_classification (immutable update)
# ---------------------------------------------------------------------------


def test_with_panose_classification_replaces_trailing_ten_bytes() -> None:
    p = PDPanose(_panose_bytes())
    new_payload = bytes([9, 8, 7, 6, 5, 4, 3, 2, 1, 0])
    updated = p.with_panose_classification(new_payload)
    # Original is untouched (immutable value semantics).
    assert p.get_bytes() == _panose_bytes()
    # New wrapper has the head preserved + replaced tail.
    assert updated.get_bytes() == _panose_bytes()[:2] + new_payload


def test_with_panose_classification_accepts_classification_wrapper() -> None:
    p = PDPanose(_panose_bytes())
    c = PDPanoseClassification(b"\x09" * 10)
    updated = p.with_panose_classification(c)
    assert updated.get_panose() == c


def test_with_panose_classification_preserves_family_class_signedness() -> None:
    p = PDPanose(b"\xff\x80" + b"\x00" * 10)
    updated = p.with_panose_classification(b"\x01" * 10)
    # Family class round-trips as signed -128.
    assert updated.get_family_class() == -128


# ---------------------------------------------------------------------------
# PDPanose.from_family_class_and_classification (pypdfbox extension)
# ---------------------------------------------------------------------------


def test_from_family_class_factory_round_trips_positive() -> None:
    payload = bytes(range(10))
    p = PDPanose.from_family_class_and_classification(0x1234, payload)
    assert p.get_family_class() == 0x1234
    assert p.get_panose().get_bytes() == payload
    assert len(p) == PDPanose.LENGTH


def test_from_family_class_factory_round_trips_negative() -> None:
    payload = bytes(10)
    p = PDPanose.from_family_class_and_classification(-1, payload)
    assert p.get_family_class() == -1
    # Encoded as 0xFFFF when re-read raw.
    assert p.get_bytes()[:2] == b"\xff\xff"


def test_from_family_class_factory_accepts_classification_wrapper() -> None:
    classification = PDPanoseClassification(_classification_bytes())
    p = PDPanose.from_family_class_and_classification(8, classification)
    assert p.get_family_class() == 8
    assert p.get_panose() == classification


def test_from_family_class_factory_accepts_bytearray() -> None:
    p = PDPanose.from_family_class_and_classification(0, bytearray(b"\x00" * 10))
    assert p.get_family_class() == 0
    assert p.get_panose().get_bytes() == b"\x00" * 10


@pytest.mark.parametrize("oob", [0x8000, -0x8001, 0x10000, -0x10000])
def test_from_family_class_factory_rejects_out_of_range(oob: int) -> None:
    with pytest.raises(ValueError, match="signed 16-bit"):
        PDPanose.from_family_class_and_classification(oob, b"\x00" * 10)


def test_from_family_class_factory_boundary_values_pass() -> None:
    # Min and max of signed 16-bit.
    p_min = PDPanose.from_family_class_and_classification(-0x8000, b"\x00" * 10)
    p_max = PDPanose.from_family_class_and_classification(0x7FFF, b"\x00" * 10)
    assert p_min.get_family_class() == -0x8000
    assert p_max.get_family_class() == 0x7FFF


# ---------------------------------------------------------------------------
# PDPanose — value semantics & dunder methods
# ---------------------------------------------------------------------------


def test_panose_eq_same_bytes() -> None:
    a = PDPanose(_panose_bytes())
    b = PDPanose(_panose_bytes())
    assert a == b
    assert hash(a) == hash(b)


def test_panose_eq_against_non_panose() -> None:
    p = PDPanose(_panose_bytes())
    assert (p == _panose_bytes()) is False
    assert (p == "PDPanose") is False


def test_panose_bytes_dunder() -> None:
    payload = _panose_bytes()
    p = PDPanose(payload)
    assert bytes(p) == payload


def test_panose_len_dunder_reflects_actual_buffer() -> None:
    # Nominal — 12 bytes.
    assert len(PDPanose(_panose_bytes())) == 12
    # Short and over-long — actual length, not LENGTH.
    assert len(PDPanose(b"\x00" * 5)) == 5
    assert len(PDPanose(b"\x00" * 24)) == 24


def test_panose_repr_includes_raw_bytes() -> None:
    p = PDPanose(b"\x00\x08")
    text = repr(p)
    assert text.startswith("PDPanose(")
    assert "\\x00\\x08" in text


def test_panose_constructor_accepts_any_length() -> None:
    """Upstream stores bytes verbatim — mirror that for parity."""
    PDPanose(bytes(12))  # nominal
    PDPanose(bytes(24))  # over-long, ok
    short = PDPanose(bytes(5))  # short, ok
    # Accessors past the end raise IndexError on demand.
    with pytest.raises(IndexError):
        # bytes 2..12 — slicing past-end yields a short buffer; the
        # resulting classification's accessors fail when reached.
        short.get_panose().get_x_height()


# ---------------------------------------------------------------------------
# Round-trip: PDPanose → classification → with_panose_classification
# ---------------------------------------------------------------------------


def test_round_trip_through_classification_preserves_family_class() -> None:
    p = PDPanose(_panose_bytes())
    classification = p.get_panose()
    rebuilt = p.with_panose_classification(classification)
    assert rebuilt == p


def test_round_trip_factory_then_get_panose_matches_input() -> None:
    classification = PDPanoseClassification(_classification_bytes())
    p = PDPanose.from_family_class_and_classification(-1234, classification)
    assert p.get_panose() == classification
    assert p.get_family_class() == -1234
