from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName, COSStream
from pypdfbox.pdmodel.interactive.annotation.pd_annotation import PDAnnotation
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_markup import (
    PDAnnotationMarkup,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_redact import (
    PDAnnotationRedact,
)


# ---------- subtype + construction ----------


def test_subtype_constant() -> None:
    assert PDAnnotationRedact.SUB_TYPE == "Redact"


def test_default_constructor_sets_subtype() -> None:
    ann = PDAnnotationRedact()
    assert ann.get_subtype() == "Redact"
    assert ann.get_cos_object().get_name(COSName.TYPE) == "Annot"  # type: ignore[attr-defined]


def test_extends_markup() -> None:
    ann = PDAnnotationRedact()
    assert isinstance(ann, PDAnnotationMarkup)
    assert isinstance(ann, PDAnnotation)


def test_constructor_with_dict_preserves_subtype() -> None:
    d = COSDictionary()
    d.set_name(COSName.SUBTYPE, "Redact")  # type: ignore[attr-defined]
    ann = PDAnnotationRedact(d)
    assert ann.get_subtype() == "Redact"
    assert ann.get_cos_object() is d


def test_constructor_with_dict_does_not_overwrite_existing_subtype() -> None:
    """Constructor with an existing dict should not stamp /Subtype again
    (the dict-form constructor only sets it when None is passed)."""
    d = COSDictionary()
    d.set_name(COSName.SUBTYPE, "Redact")  # type: ignore[attr-defined]
    d.set_string(COSName.get_pdf_name("OverlayText"), "REDACTED")
    ann = PDAnnotationRedact(d)
    assert ann.get_overlay_text() == "REDACTED"


# ---------- /Q quadding constants ----------


def test_quadding_constants_match_spec() -> None:
    assert PDAnnotationRedact.QUADDING_LEFT == 0
    assert PDAnnotationRedact.QUADDING_CENTERED == 1
    assert PDAnnotationRedact.QUADDING_RIGHT == 2


# ---------- /QuadPoints ----------


def test_quad_points_default_none() -> None:
    assert PDAnnotationRedact().get_quad_points() is None


def test_quad_points_round_trip() -> None:
    ann = PDAnnotationRedact()
    pts = [0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0]
    ann.set_quad_points(pts)
    assert ann.get_quad_points() == pts


def test_quad_points_round_trip_two_quads() -> None:
    ann = PDAnnotationRedact()
    pts = [
        0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0,
        10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0,
    ]
    ann.set_quad_points(pts)
    assert ann.get_quad_points() == pts


def test_quad_points_accepts_tuple() -> None:
    ann = PDAnnotationRedact()
    ann.set_quad_points((0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0))
    assert ann.get_quad_points() == [0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0]


def test_quad_points_clear() -> None:
    ann = PDAnnotationRedact()
    ann.set_quad_points([0.0] * 8)
    ann.set_quad_points(None)
    assert ann.get_quad_points() is None


def test_quad_points_invalid_length_raises() -> None:
    ann = PDAnnotationRedact()
    with pytest.raises(ValueError, match="multiple of 8"):
        ann.set_quad_points([1.0, 2.0, 3.0])


def test_quad_points_empty_list_is_valid_zero_quads() -> None:
    """Empty list has length 0 which is a multiple of 8 (zero quads)."""
    ann = PDAnnotationRedact()
    ann.set_quad_points([])
    assert ann.get_quad_points() == []


def test_quad_points_non_array_returns_none() -> None:
    ann = PDAnnotationRedact()
    ann.get_cos_object().set_string(COSName.get_pdf_name("QuadPoints"), "garbage")
    assert ann.get_quad_points() is None


# ---------- /IC interior color ----------


def test_interior_color_default_none() -> None:
    assert PDAnnotationRedact().get_interior_color() is None


def test_interior_color_round_trip_cosarray() -> None:
    ann = PDAnnotationRedact()
    ic = COSArray([COSFloat(1.0), COSFloat(0.5), COSFloat(0.0)])
    ann.set_interior_color(ic)
    assert ann.get_interior_color() is ic


def test_interior_color_accepts_list() -> None:
    ann = PDAnnotationRedact()
    ann.set_interior_color([0.0, 0.5, 1.0])
    resolved = ann.get_interior_color()
    assert resolved is not None
    assert resolved.to_float_array() == [0.0, 0.5, 1.0]


def test_interior_color_accepts_tuple() -> None:
    ann = PDAnnotationRedact()
    ann.set_interior_color((0.25, 0.5, 0.75))
    resolved = ann.get_interior_color()
    assert resolved is not None
    assert resolved.to_float_array() == [0.25, 0.5, 0.75]


def test_interior_color_clear() -> None:
    ann = PDAnnotationRedact()
    ann.set_interior_color([0.0, 0.0, 0.0])
    ann.set_interior_color(None)
    assert ann.get_interior_color() is None


def test_interior_color_non_array_returns_none() -> None:
    ann = PDAnnotationRedact()
    ann.get_cos_object().set_string(COSName.get_pdf_name("IC"), "not-array")
    assert ann.get_interior_color() is None


# ---------- /RO redaction appearance ----------


def test_redaction_appearance_default_none() -> None:
    assert PDAnnotationRedact().get_redaction_appearance() is None


def test_redaction_appearance_round_trip() -> None:
    ann = PDAnnotationRedact()
    stream = COSStream()
    stream.set_int(COSName.get_pdf_name("Length"), 0)
    ann.set_redaction_appearance(stream)
    assert ann.get_redaction_appearance() is stream


def test_redaction_appearance_clear() -> None:
    ann = PDAnnotationRedact()
    ann.set_redaction_appearance(COSStream())
    ann.set_redaction_appearance(None)
    assert ann.get_redaction_appearance() is None


def test_redaction_appearance_non_stream_returns_none() -> None:
    """When ``/RO`` exists but is not a stream, getter returns ``None``."""
    ann = PDAnnotationRedact()
    ann.get_cos_object().set_item(COSName.get_pdf_name("RO"), COSDictionary())
    assert ann.get_redaction_appearance() is None


def test_redaction_appearance_accepts_wrapper_with_get_cos_object() -> None:
    """A wrapper exposing ``get_cos_object()`` returning a stream is accepted."""

    class _Wrapper:
        def __init__(self, s: COSStream) -> None:
            self._s = s

        def get_cos_object(self) -> COSStream:
            return self._s

    ann = PDAnnotationRedact()
    inner = COSStream()
    ann.set_redaction_appearance(_Wrapper(inner))  # type: ignore[arg-type]
    assert ann.get_redaction_appearance() is inner


def test_redaction_appearance_rejects_wrapper_without_stream() -> None:
    class _BadWrapper:
        def get_cos_object(self) -> COSDictionary:
            return COSDictionary()

    ann = PDAnnotationRedact()
    with pytest.raises(TypeError, match="COSStream-backed"):
        ann.set_redaction_appearance(_BadWrapper())  # type: ignore[arg-type]


def test_redaction_appearance_rejects_garbage() -> None:
    ann = PDAnnotationRedact()
    with pytest.raises(TypeError, match="COSStream"):
        ann.set_redaction_appearance("not a stream")  # type: ignore[arg-type]


# ---------- /OverlayText ----------


def test_overlay_text_default_none() -> None:
    assert PDAnnotationRedact().get_overlay_text() is None


def test_overlay_text_round_trip() -> None:
    ann = PDAnnotationRedact()
    ann.set_overlay_text("REDACTED")
    assert ann.get_overlay_text() == "REDACTED"


def test_overlay_text_clear() -> None:
    ann = PDAnnotationRedact()
    ann.set_overlay_text("foo")
    ann.set_overlay_text(None)
    assert ann.get_overlay_text() is None


def test_overlay_text_empty_string() -> None:
    ann = PDAnnotationRedact()
    ann.set_overlay_text("")
    assert ann.get_overlay_text() == ""


# ---------- /Repeat ----------


def test_repeat_default_false() -> None:
    """Spec default: missing ``/Repeat`` means do not repeat overlay text."""
    assert PDAnnotationRedact().is_repeat() is False


def test_repeat_set_true() -> None:
    ann = PDAnnotationRedact()
    ann.set_repeat(True)
    assert ann.is_repeat() is True


def test_repeat_set_false() -> None:
    ann = PDAnnotationRedact()
    ann.set_repeat(True)
    ann.set_repeat(False)
    assert ann.is_repeat() is False


def test_repeat_truthy_value_coerced_to_bool() -> None:
    ann = PDAnnotationRedact()
    ann.set_repeat(1)  # type: ignore[arg-type]
    assert ann.is_repeat() is True


# ---------- /DA default appearance ----------


def test_default_appearance_default_none() -> None:
    assert PDAnnotationRedact().get_default_appearance() is None


def test_default_appearance_round_trip() -> None:
    ann = PDAnnotationRedact()
    ann.set_default_appearance("/Helv 12 Tf 0 g")
    assert ann.get_default_appearance() == "/Helv 12 Tf 0 g"


def test_default_appearance_clear() -> None:
    ann = PDAnnotationRedact()
    ann.set_default_appearance("/Helv 10 Tf")
    ann.set_default_appearance(None)
    assert ann.get_default_appearance() is None


# ---------- /Q quadding ----------


def test_q_default_left() -> None:
    """Spec default for ``/Q`` is 0 (left-justified)."""
    assert PDAnnotationRedact().get_q() == PDAnnotationRedact.QUADDING_LEFT


def test_q_round_trip_centered() -> None:
    ann = PDAnnotationRedact()
    ann.set_q(PDAnnotationRedact.QUADDING_CENTERED)
    assert ann.get_q() == 1


def test_q_round_trip_right() -> None:
    ann = PDAnnotationRedact()
    ann.set_q(PDAnnotationRedact.QUADDING_RIGHT)
    assert ann.get_q() == 2


def test_q_coerces_to_int() -> None:
    ann = PDAnnotationRedact()
    ann.set_q(2.7)  # type: ignore[arg-type]
    assert ann.get_q() == 2


# ---------- factory routing + markup inheritance ----------


def test_factory_routes_to_redact() -> None:
    d = COSDictionary()
    d.set_name(COSName.SUBTYPE, "Redact")  # type: ignore[attr-defined]
    ann = PDAnnotation.create(d)
    assert isinstance(ann, PDAnnotationRedact)


def test_markup_creation_date_inherited() -> None:
    ann = PDAnnotationRedact()
    ann.set_creation_date("D:20260427120000Z")
    assert ann.get_creation_date() == "D:20260427120000Z"


def test_markup_subject_inherited() -> None:
    ann = PDAnnotationRedact()
    ann.set_subject("Confidential redaction")
    assert ann.get_subject() == "Confidential redaction"


# ---------- coexistence: setting all entries together ----------


def test_full_round_trip_all_entries() -> None:
    ann = PDAnnotationRedact()
    ann.set_quad_points([0.0, 0.0, 10.0, 0.0, 10.0, 10.0, 0.0, 10.0])
    ann.set_interior_color([0.0, 0.0, 0.0])
    ann.set_overlay_text("[REDACTED]")
    ann.set_repeat(True)
    ann.set_default_appearance("/Helv 12 Tf 1 1 1 rg")
    ann.set_q(PDAnnotationRedact.QUADDING_CENTERED)

    assert ann.get_quad_points() == [0.0, 0.0, 10.0, 0.0, 10.0, 10.0, 0.0, 10.0]
    assert ann.get_interior_color() is not None
    assert ann.get_overlay_text() == "[REDACTED]"
    assert ann.is_repeat() is True
    assert ann.get_default_appearance() == "/Helv 12 Tf 1 1 1 rg"
    assert ann.get_q() == 1
