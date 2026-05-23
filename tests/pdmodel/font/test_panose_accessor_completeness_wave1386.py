"""Wave 1386 — round-out the per-byte PANOSE accessors to the full
upstream classifier surface (agent D).

Wave 1379 closed the read/write per-byte accessors on
:class:`PDPanoseClassification` plus the universal ``is_any`` /
``is_no_fit`` / ``is_latin_text`` predicates. Wave 1386 closes the
remaining audited gaps:

- The three missing Latin family-kind predicates
  (``is_latin_hand_written`` / ``is_latin_decorative`` /
  ``is_latin_symbol``) so callers don't have to repeat
  ``get_family_kind() == FAMILY_KIND_LATIN_*`` literals;
- :meth:`PDFontDescriptor.get_font_family_class` — surfaces the PANOSE
  family-kind byte through the descriptor wrapper (distinct from
  :meth:`PDFontDescriptor.get_font_family`, which returns the
  ``/FontFamily`` *string*);
- :meth:`PDFontDescriptor.is_panose_symbolic_consistent` —
  cross-checks the PANOSE family classifier against the ``/Flags``
  SYMBOLIC bit so callers can flag malformed descriptors;
- ``get_panose()`` wrapper round-trip + the ``__str__`` / ``__repr__``
  shape parity invariants the wave brief calls out.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSName, COSString
from pypdfbox.pdmodel.font.pd_font_descriptor import (
    FLAG_NON_SYMBOLIC,
    FLAG_SYMBOLIC,
    PDFontDescriptor,
    PDPanose,
    PDPanoseClassification,
)

_STYLE = COSName.get_pdf_name("Style")
_PANOSE = COSName.get_pdf_name("Panose")


# ---------------------------------------------------------------------------
# Helper — build a PDFontDescriptor whose /Style/Panose carries a known
# 10-byte PANOSE block at the conventional 2-byte offset (sFamilyClass
# prefix is zeroed; we don't exercise it here).
# ---------------------------------------------------------------------------


def _descriptor_with_panose_bytes(panose_bytes: bytes) -> PDFontDescriptor:
    assert len(panose_bytes) == PDPanoseClassification.LENGTH
    fd = PDFontDescriptor()
    style = COSDictionary()
    style.set_item(_PANOSE, COSString(b"\x00\x00" + panose_bytes))
    fd.get_cos_object().set_item(_STYLE, style)
    return fd


# ---------------------------------------------------------------------------
# PDFontDescriptor.get_panose() returns the typed wrapper
# ---------------------------------------------------------------------------


def test_get_panose_returns_pd_panose_wrapping_known_bytes() -> None:
    panose_bytes = bytes(range(2, 12))  # bytes 2..11 = 10 distinct values
    fd = _descriptor_with_panose_bytes(panose_bytes)

    panose = fd.get_panose()
    assert isinstance(panose, PDPanose)
    classification = panose.get_panose()
    assert isinstance(classification, PDPanoseClassification)
    # Verify each per-byte value round-trips through the wrapper.
    for index in range(PDPanoseClassification.LENGTH):
        assert classification.get_byte(index) == 2 + index


def test_get_panose_none_when_no_style_entry() -> None:
    fd = PDFontDescriptor()
    assert fd.get_panose() is None
    assert fd.has_panose() is False


def test_get_panose_none_for_short_buffer() -> None:
    """A /Style/Panose entry that's < 12 bytes long does not yield a wrapper
    (matches upstream length-guard in PDFontDescriptor.getPanose).
    """
    fd = PDFontDescriptor()
    style = COSDictionary()
    style.set_item(_PANOSE, COSString(b"\x00" * 5))  # too short
    fd.get_cos_object().set_item(_STYLE, style)
    assert fd.get_panose() is None
    # ...but presence-check still reports True (the entry exists, it's
    # just malformed — exactly what `has_panose` is for).
    assert fd.has_panose() is True


# ---------------------------------------------------------------------------
# Family-kind predicates — all six (Any / NoFit / LatinText /
# LatinHandWritten / LatinDecorative / LatinSymbol)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("family_kind", "predicate_name"),
    [
        (PDPanoseClassification.FAMILY_KIND_ANY, "is_any"),
        (PDPanoseClassification.FAMILY_KIND_NO_FIT, "is_no_fit"),
        (PDPanoseClassification.FAMILY_KIND_LATIN_TEXT, "is_latin_text"),
        (
            PDPanoseClassification.FAMILY_KIND_LATIN_HAND_WRITTEN,
            "is_latin_hand_written",
        ),
        (
            PDPanoseClassification.FAMILY_KIND_LATIN_DECORATIVE,
            "is_latin_decorative",
        ),
        (PDPanoseClassification.FAMILY_KIND_LATIN_SYMBOL, "is_latin_symbol"),
    ],
    ids=[
        "family_kind_any",
        "family_kind_no_fit",
        "family_kind_latin_text",
        "family_kind_latin_hand_written",
        "family_kind_latin_decorative",
        "family_kind_latin_symbol",
    ],
)
def test_family_kind_predicate_true_for_matching_value(
    family_kind: int, predicate_name: str
) -> None:
    cls_obj = PDPanoseClassification(bytes([family_kind] + [0] * 9))
    assert getattr(cls_obj, predicate_name)() is True
    # And every OTHER family predicate is False (mutual exclusivity).
    for other in (
        "is_any",
        "is_no_fit",
        "is_latin_text",
        "is_latin_hand_written",
        "is_latin_decorative",
        "is_latin_symbol",
    ):
        if other == predicate_name:
            continue
        assert getattr(cls_obj, other)() is False


def test_is_latin_hand_written_constant_value() -> None:
    """Pin the spec-defined integer value (PANOSE 2.0 family kind 3)."""
    assert PDPanoseClassification.FAMILY_KIND_LATIN_HAND_WRITTEN == 3


def test_is_latin_decorative_constant_value() -> None:
    """PANOSE 2.0 family kind 4."""
    assert PDPanoseClassification.FAMILY_KIND_LATIN_DECORATIVE == 4


def test_is_latin_symbol_constant_value() -> None:
    """PANOSE 2.0 family kind 5."""
    assert PDPanoseClassification.FAMILY_KIND_LATIN_SYMBOL == 5


# ---------------------------------------------------------------------------
# PDFontDescriptor.get_font_family_class() — reads PANOSE byte 0
# ---------------------------------------------------------------------------


def test_get_font_family_class_returns_panose_byte_zero() -> None:
    fd = _descriptor_with_panose_bytes(
        bytes(
            [PDPanoseClassification.FAMILY_KIND_LATIN_TEXT, 0, 0, 0, 0, 0, 0, 0, 0, 0]
        )
    )
    assert fd.get_font_family_class() == 2


def test_get_font_family_class_none_when_no_panose() -> None:
    """No /Style/Panose entry → returns None (distinguishes "absent" from
    "family_kind == 0", which is the spec-defined "Any" classifier)."""
    fd = PDFontDescriptor()
    assert fd.get_font_family_class() is None


def test_get_font_family_class_zero_for_family_kind_any() -> None:
    """A descriptor with PANOSE byte 0 = 0 (FAMILY_KIND_ANY) returns 0
    — distinct from the "no PANOSE" None case."""
    fd = _descriptor_with_panose_bytes(b"\x00" * 10)
    assert fd.get_font_family_class() == 0


def test_get_font_family_class_distinct_from_get_font_family() -> None:
    """Upstream PDFontDescriptor.getFontFamily() returns /FontFamily
    *string*; pypdfbox's get_font_family_class() returns the PANOSE
    family-kind *int*. Both can be set independently on the same
    descriptor without interfering."""
    fd = _descriptor_with_panose_bytes(
        bytes(
            [
                PDPanoseClassification.FAMILY_KIND_LATIN_DECORATIVE,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
            ]
        )
    )
    fd.set_font_family("Times")
    assert fd.get_font_family() == "Times"
    assert fd.get_font_family_class() == 4
    # The two accessors don't shadow each other.
    assert fd.get_font_family_class() != fd.get_font_family()


# ---------------------------------------------------------------------------
# Flags-consistency check (PANOSE family kind vs /Flags SYMBOLIC bit)
# ---------------------------------------------------------------------------


def test_is_panose_symbolic_consistent_none_when_no_panose() -> None:
    fd = PDFontDescriptor()
    fd.set_symbolic(True)
    assert fd.is_panose_symbolic_consistent() is None


def test_is_panose_symbolic_consistent_true_when_both_say_symbolic() -> None:
    fd = _descriptor_with_panose_bytes(
        bytes(
            [
                PDPanoseClassification.FAMILY_KIND_LATIN_SYMBOL,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
            ]
        )
    )
    fd.set_flag_bit(FLAG_SYMBOLIC, True)
    assert fd.is_panose_symbolic_consistent() is True


def test_is_panose_symbolic_consistent_true_when_both_say_non_symbolic() -> None:
    fd = _descriptor_with_panose_bytes(
        bytes(
            [
                PDPanoseClassification.FAMILY_KIND_LATIN_TEXT,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
            ]
        )
    )
    fd.set_flag_bit(FLAG_NON_SYMBOLIC, True)
    # /Flags SYMBOLIC bit stays off.
    assert fd.is_panose_symbolic_consistent() is True


def test_is_panose_symbolic_consistent_false_when_disagree() -> None:
    """PANOSE says Latin Symbol (symbolic) but /Flags doesn't have the
    SYMBOLIC bit set — descriptor is malformed."""
    fd = _descriptor_with_panose_bytes(
        bytes(
            [
                PDPanoseClassification.FAMILY_KIND_LATIN_SYMBOL,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
            ]
        )
    )
    # SYMBOLIC bit OFF — disagreement with the PANOSE Latin Symbol kind.
    assert fd.is_panose_symbolic_consistent() is False


def test_is_panose_symbolic_consistent_false_when_flags_symbolic_but_panose_latin_text() -> None:
    fd = _descriptor_with_panose_bytes(
        bytes(
            [
                PDPanoseClassification.FAMILY_KIND_LATIN_TEXT,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
            ]
        )
    )
    fd.set_flag_bit(FLAG_SYMBOLIC, True)
    assert fd.is_panose_symbolic_consistent() is False


@pytest.mark.parametrize(
    "family_kind",
    [
        PDPanoseClassification.FAMILY_KIND_ANY,
        PDPanoseClassification.FAMILY_KIND_NO_FIT,
    ],
    ids=["family_kind_any", "family_kind_no_fit"],
)
def test_is_panose_symbolic_consistent_true_for_unclassified_family_kinds(
    family_kind: int,
) -> None:
    """ANY / NO_FIT carry no opinion — consistency check defers to
    /Flags and reports True regardless of the SYMBOLIC bit value."""
    fd = _descriptor_with_panose_bytes(
        bytes([family_kind, 0, 0, 0, 0, 0, 0, 0, 0, 0])
    )
    # With SYMBOLIC on.
    fd.set_flag_bit(FLAG_SYMBOLIC, True)
    assert fd.is_panose_symbolic_consistent() is True
    # And with SYMBOLIC off.
    fd.set_flag_bit(FLAG_SYMBOLIC, False)
    assert fd.is_panose_symbolic_consistent() is True


# ---------------------------------------------------------------------------
# __str__ / __repr__ shape parity (PDPanoseClassification)
# ---------------------------------------------------------------------------


def test_str_matches_upstream_format() -> None:
    """Mirrors upstream PDPanoseClassification.toString() (Java lines
    96-108): comma-delimited per-category key=value list inside
    ``{ ... }``."""
    cls_obj = PDPanoseClassification(bytes(range(2, 12)))
    rendered = str(cls_obj)
    assert rendered == (
        "{ FamilyKind = 2"
        ", SerifStyle = 3"
        ", Weight = 4"
        ", Proportion = 5"
        ", Contrast = 6"
        ", StrokeVariation = 7"
        ", ArmStyle = 8"
        ", Letterform = 9"
        ", Midline = 10"
        ", XHeight = 11"
        "}"
    )


def test_str_lists_each_category_name_exactly_once() -> None:
    """Defence against accidental key-name typos / duplicates in the
    template."""
    rendered = str(PDPanoseClassification(b"\x00" * 10))
    for key in (
        "FamilyKind",
        "SerifStyle",
        "Weight",
        "Proportion",
        "Contrast",
        "StrokeVariation",
        "ArmStyle",
        "Letterform",
        "Midline",
        "XHeight",
    ):
        assert rendered.count(key) == 1


def test_repr_round_trips_through_byte_buffer() -> None:
    """``repr`` should be eval-friendly when the bytes literal is."""
    data = bytes(range(10))
    cls_obj = PDPanoseClassification(data)
    rendered = repr(cls_obj)
    assert rendered.startswith("PDPanoseClassification(")
    assert rendered.endswith(")")
    # The repr should embed the underlying buffer's repr verbatim.
    assert repr(data) in rendered


def test_to_string_method_returns_same_as_str() -> None:
    """``to_string`` and ``__str__`` are aliases — both call the same
    template."""
    cls_obj = PDPanoseClassification(bytes(range(10)))
    assert cls_obj.to_string() == str(cls_obj)


# ---------------------------------------------------------------------------
# End-to-end round-trip — every setter writes a byte that get_panose
# subsequently reads back through the descriptor wrapper.
# ---------------------------------------------------------------------------


def test_full_round_trip_through_descriptor_wrapper() -> None:
    """Build a PDPanose from a known classification, write it into a
    descriptor's /Style/Panose, then read it back through
    PDFontDescriptor.get_panose() — every byte preserved."""
    classification = PDPanoseClassification(b"\x00" * 10)
    classification.set_family_kind(PDPanoseClassification.FAMILY_KIND_LATIN_TEXT)
    classification.set_serif_style(PDPanoseClassification.SERIF_STYLE_COVE)
    classification.set_weight(PDPanoseClassification.WEIGHT_MEDIUM)
    classification.set_proportion(PDPanoseClassification.PROPORTION_MODERN)
    classification.set_contrast(PDPanoseClassification.CONTRAST_LOW)
    classification.set_stroke_variation(
        PDPanoseClassification.STROKE_VARIATION_NO_VARIATION
    )
    classification.set_arm_style(
        PDPanoseClassification.ARM_STYLE_STRAIGHT_ARMS_HORZ
    )
    classification.set_letterform(
        PDPanoseClassification.LETTERFORM_NORMAL_CONTACT
    )
    classification.set_midline(PDPanoseClassification.MIDLINE_STANDARD_TRIMMED)
    classification.set_x_height(PDPanoseClassification.X_HEIGHT_CONSTANT_STANDARD)

    panose = PDPanose.from_family_class_and_classification(0, classification)
    fd = PDFontDescriptor()
    fd.set_panose(panose)

    # Read back through the typed wrapper.
    round_tripped = fd.get_panose()
    assert round_tripped is not None
    round_tripped_classification = round_tripped.get_panose()
    assert round_tripped_classification == classification
    assert round_tripped_classification.is_latin_text() is True

    # And cross-check via the family-class helper on the descriptor.
    assert (
        fd.get_font_family_class()
        == PDPanoseClassification.FAMILY_KIND_LATIN_TEXT
    )
