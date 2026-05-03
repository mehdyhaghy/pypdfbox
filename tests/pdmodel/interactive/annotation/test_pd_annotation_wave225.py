"""Wave 225 — pdmodel/interactive/annotation small parity gaps.

Covers:
- ``PDAnnotationTextMarkup`` ``SUB_TYPE_*`` discoverability constants,
  empty-``/QuadPoints`` initialisation in default constructor (matches
  upstream ``PDAnnotationTextMarkup(String subType)`` ctor), and
  ``has_quad_points`` / ``quad_point_count`` predicates.
- ``PDAnnotationRubberStamp`` ``STANDARD_NAMES`` set + ``is_standard_name``
  predicate (parity with ``PDAnnotationStamp``).
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_highlight import (
    PDAnnotationHighlight,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_rubber_stamp import (
    PDAnnotationRubberStamp,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_squiggly import (
    PDAnnotationSquiggly,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_strikeout import (
    PDAnnotationStrikeout,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_text_markup import (
    PDAnnotationTextMarkup,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_underline import (
    PDAnnotationUnderline,
)

# ---------- PDAnnotationTextMarkup SUB_TYPE_* constants ----------


def test_text_markup_subtype_constants_match_subclasses() -> None:
    """The discoverability constants on the abstract base must match the
    concrete subclasses' ``SUB_TYPE`` values exactly — this is the whole
    point of exposing them on the parent."""
    assert PDAnnotationTextMarkup.SUB_TYPE_HIGHLIGHT == PDAnnotationHighlight.SUB_TYPE
    assert PDAnnotationTextMarkup.SUB_TYPE_UNDERLINE == PDAnnotationUnderline.SUB_TYPE
    assert PDAnnotationTextMarkup.SUB_TYPE_STRIKEOUT == PDAnnotationStrikeout.SUB_TYPE
    assert PDAnnotationTextMarkup.SUB_TYPE_SQUIGGLY == PDAnnotationSquiggly.SUB_TYPE


def test_text_markup_strikeout_subtype_uses_pdf_spec_capitalisation() -> None:
    """PDF spec writes the subtype as ``StrikeOut`` (mid-string capital);
    the constant on the base must preserve that."""
    assert PDAnnotationTextMarkup.SUB_TYPE_STRIKEOUT == "StrikeOut"


# ---------- PDAnnotationTextMarkup empty-quad-points initialisation ----------


def test_text_markup_default_ctor_seeds_empty_quad_points_for_each_subtype() -> None:
    """Upstream's ``PDAnnotationTextMarkup(String subType)`` ctor calls
    ``setQuadPoints(new float[0])`` so the dictionary is spec-conformant
    out of the gate (``/QuadPoints`` is required by §12.5.6.10). All four
    text-markup subtypes inherit this behaviour."""
    for cls in (
        PDAnnotationHighlight,
        PDAnnotationUnderline,
        PDAnnotationStrikeout,
        PDAnnotationSquiggly,
    ):
        ann = cls()
        # /QuadPoints is present (not None) and round-trips to an empty list.
        assert ann.has_quad_points() is True, f"{cls.__name__} should seed /QuadPoints"
        assert ann.get_quad_points() == [], (
            f"{cls.__name__} default /QuadPoints must be empty"
        )


def test_text_markup_quad_points_initialisation_does_not_overwrite_existing() -> None:
    """When constructing from a dict that already carries ``/QuadPoints``,
    the value must be preserved (no clobber by the auto-init)."""
    d = COSDictionary()
    d.set_name(COSName.SUBTYPE, "Highlight")  # type: ignore[attr-defined]
    qp = COSArray([COSFloat(1.0), COSFloat(2.0), COSFloat(3.0), COSFloat(4.0)])
    d.set_item(COSName.get_pdf_name("QuadPoints"), qp)

    ann = PDAnnotationHighlight(d)
    assert ann.get_quad_points() == [1.0, 2.0, 3.0, 4.0]
    # Same COSArray instance, not a copy.
    assert ann.get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("QuadPoints")
    ) is qp


def test_text_markup_quad_points_initialisation_does_not_run_for_parsed_dict() -> None:
    """A parsed-in dict without ``/QuadPoints`` should NOT have one
    synthesised (we only seed for default-constructed instances). This
    matches upstream's split between
    ``PDAnnotationTextMarkup(String)`` and ``PDAnnotationTextMarkup(COSDictionary)``."""
    d = COSDictionary()
    d.set_name(COSName.SUBTYPE, "Underline")  # type: ignore[attr-defined]

    ann = PDAnnotationUnderline(d)
    assert ann.has_quad_points() is False
    assert ann.get_quad_points() is None


# ---------- PDAnnotationTextMarkup.has_quad_points / quad_point_count ----------


def test_text_markup_has_quad_points_default_true() -> None:
    """Default-constructed instances have an empty ``/QuadPoints`` array,
    which still counts as "present" — distinct from missing entirely."""
    assert PDAnnotationHighlight().has_quad_points() is True


def test_text_markup_has_quad_points_after_clear_returns_false() -> None:
    ann = PDAnnotationHighlight()
    ann.set_quad_points([0.0, 0.0, 1.0, 1.0, 2.0, 2.0, 3.0, 3.0])
    ann.set_quad_points(None)
    assert ann.has_quad_points() is False


def test_text_markup_has_quad_points_ignores_non_array_value() -> None:
    """A stray non-array ``/QuadPoints`` value (corrupt PDF) is treated
    as absent rather than raising."""
    ann = PDAnnotationHighlight()
    ann.get_cos_object().set_item(
        COSName.get_pdf_name("QuadPoints"), COSFloat(0.0)
    )
    assert ann.has_quad_points() is False


def test_text_markup_quad_point_count_default_zero() -> None:
    """A default-constructed instance has an empty ``/QuadPoints`` array,
    so the quadrilateral count is 0."""
    assert PDAnnotationHighlight().quad_point_count() == 0


def test_text_markup_quad_point_count_one_quadrilateral() -> None:
    ann = PDAnnotationHighlight()
    ann.set_quad_points([0.0, 0.0, 10.0, 0.0, 10.0, 10.0, 0.0, 10.0])
    assert ann.quad_point_count() == 1


def test_text_markup_quad_point_count_multiple_quadrilaterals() -> None:
    ann = PDAnnotationHighlight()
    ann.set_quad_points(
        [
            0.0, 0.0, 10.0, 0.0, 10.0, 10.0, 0.0, 10.0,
            20.0, 0.0, 30.0, 0.0, 30.0, 10.0, 20.0, 10.0,
            40.0, 0.0, 50.0, 0.0, 50.0, 10.0, 40.0, 10.0,
        ]
    )
    assert ann.quad_point_count() == 3


def test_text_markup_quad_point_count_rounds_down_partial() -> None:
    """A trailing partial quadrilateral (length not a multiple of 8) is
    rounded down — matching what upstream readers do at render time."""
    ann = PDAnnotationHighlight()
    # 10 floats — one full quadrilateral + 2 stray floats.
    ann.set_quad_points([1.0] * 10)
    assert ann.quad_point_count() == 1


def test_text_markup_quad_point_count_after_clear_returns_zero() -> None:
    ann = PDAnnotationHighlight()
    ann.set_quad_points([0.0] * 16)  # two quadrilaterals
    ann.set_quad_points(None)
    assert ann.quad_point_count() == 0


def test_text_markup_quad_point_count_ignores_non_array_value() -> None:
    """A stray non-array ``/QuadPoints`` value yields 0, not an exception."""
    ann = PDAnnotationHighlight()
    ann.get_cos_object().set_item(
        COSName.get_pdf_name("QuadPoints"), COSFloat(0.0)
    )
    assert ann.quad_point_count() == 0


# ---------- PDAnnotationRubberStamp.STANDARD_NAMES + is_standard_name ----------


def test_rubber_stamp_standard_names_set_size_and_contents() -> None:
    """PDF 32000-1:2008 Table 183 enumerates exactly 14 standard icons."""
    assert len(PDAnnotationRubberStamp.STANDARD_NAMES) == 14
    expected = {
        "Approved",
        "AsIs",
        "Confidential",
        "Departmental",
        "Draft",
        "Experimental",
        "Expired",
        "Final",
        "ForComment",
        "ForPublicRelease",
        "NotApproved",
        "NotForPublicRelease",
        "Sold",
        "TopSecret",
    }
    assert PDAnnotationRubberStamp.STANDARD_NAMES == expected


def test_rubber_stamp_standard_names_is_frozenset() -> None:
    """Frozenset, not set — STANDARD_NAMES is a class-level constant; we
    don't want callers to mutate it accidentally."""
    assert isinstance(PDAnnotationRubberStamp.STANDARD_NAMES, frozenset)


def test_rubber_stamp_is_standard_name_default_draft() -> None:
    """Spec default (no ``/Name`` entry) is ``Draft`` — a standard icon."""
    ann = PDAnnotationRubberStamp()
    assert ann.is_standard_name() is True


def test_rubber_stamp_is_standard_name_each_constant() -> None:
    ann = PDAnnotationRubberStamp()
    for name in PDAnnotationRubberStamp.STANDARD_NAMES:
        ann.set_name(name)
        assert ann.is_standard_name() is True, f"{name} should be standard"


def test_rubber_stamp_is_standard_name_rejects_custom() -> None:
    ann = PDAnnotationRubberStamp()
    ann.set_name("CompanyLogo")
    assert ann.is_standard_name() is False


def test_rubber_stamp_is_standard_name_is_case_sensitive() -> None:
    ann = PDAnnotationRubberStamp()
    ann.set_name("approved")  # lower-case 'a'
    assert ann.is_standard_name() is False
    ann.set_name("APPROVED")  # all upper
    assert ann.is_standard_name() is False


def test_rubber_stamp_is_standard_name_after_clear_returns_true() -> None:
    """``set_name(None)`` removes the entry, falling back to ``Draft`` —
    which is itself standard."""
    ann = PDAnnotationRubberStamp()
    ann.set_name("Custom")
    assert ann.is_standard_name() is False
    ann.set_name(None)
    assert ann.is_standard_name() is True


def test_rubber_stamp_standard_names_matches_pd_annotation_stamp() -> None:
    """Legacy ``PDAnnotationRubberStamp`` and modern ``PDAnnotationStamp``
    should agree on the spec's 14 standard icons."""
    from pypdfbox.pdmodel.interactive.annotation.pd_annotation_stamp import (
        PDAnnotationStamp,
    )

    assert (
        PDAnnotationRubberStamp.STANDARD_NAMES == PDAnnotationStamp.STANDARD_NAMES
    )
