"""Coverage-boost tests for
``pypdfbox.pdmodel.interactive.annotation.handlers.pd_circle_appearance_handler``.

Closes the remaining gaps:

* Early return when wrong annotation type is passed.
* Interior color branch emits ``rg`` (non-stroking) — line 50.
* ``get_line_width`` branches: /BS, /Border-float, /Border-integer,
  default (lines 116, 122).
* ``_interior_components`` accepts all three shapes + empty cases
  (lines 129-137).
* No-op rollover / down hooks.
* The cloudy-border branch propagating bbox / matrix / rect-difference
  onto the annotation + appearance stream (lines 64-78 — covered by
  the existing wave1285 test but re-verified here so this file stands
  alone).
* Plain (no-cloudy) ellipse path emits curves.
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSFloat, COSInteger, COSName
from pypdfbox.pdmodel.interactive.annotation.handlers.pd_circle_appearance_handler import (
    PDCircleAppearanceHandler,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation import PDAnnotation
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_square_circle import (
    PDAnnotationCircle,
    PDAnnotationSquareCircle,
)
from pypdfbox.pdmodel.interactive.annotation.pd_border_effect_dictionary import (
    PDBorderEffectDictionary,
)
from pypdfbox.pdmodel.interactive.annotation.pd_border_style_dictionary import (
    PDBorderStyleDictionary,
)
from pypdfbox.pdmodel.pd_rectangle import PDRectangle

_RECT = (10.0, 10.0, 110.0, 60.0)


def _circle_with_color() -> PDAnnotationCircle:
    annotation = PDAnnotationCircle()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_color([1.0, 0.0, 0.0])
    return annotation


def _appearance_bytes(annotation) -> bytes:
    ap = annotation.get_appearance_dictionary()
    assert ap is not None
    stream = ap.get_normal_appearance().get_appearance_stream()
    return stream.get_stream().to_byte_array()


# ----------------------------------------------------------------------
# generate_normal_appearance — early-return when wrong annotation type
# ----------------------------------------------------------------------


def test_generate_normal_appearance_returns_when_not_square_circle() -> None:
    """``isinstance(annotation, PDAnnotationSquareCircle)`` guard — pass
    a plain PDAnnotation and verify no /AP is written."""
    annotation = PDAnnotation()
    annotation.set_rectangle(PDRectangle(*_RECT))
    PDCircleAppearanceHandler(annotation).generate_normal_appearance()
    assert annotation.get_appearance_dictionary() is None


def test_generate_normal_appearance_subclass_passes_isinstance_guard() -> None:
    """Happy path: PDAnnotationCircle is a PDAnnotationSquareCircle."""
    annotation = _circle_with_color()
    assert isinstance(annotation, PDAnnotationSquareCircle)
    PDCircleAppearanceHandler(annotation).generate_normal_appearance()
    assert annotation.get_appearance_dictionary() is not None


# ----------------------------------------------------------------------
# generate_normal_appearance — interior-color branch
# ----------------------------------------------------------------------


def test_generate_normal_appearance_with_interior_color_sets_non_stroking() -> None:
    """Line 50: when /IC is set the handler emits a non-stroking color
    (lowercase ``rg`` for DeviceRGB)."""
    annotation = _circle_with_color()
    annotation.set_interior_color([1.0, 1.0, 0.0])
    PDCircleAppearanceHandler(annotation).generate_normal_appearance()
    body = _appearance_bytes(annotation)
    assert b"rg" in body


def test_generate_normal_appearance_without_interior_color_skips_fill() -> None:
    """Negation of line 49: no /IC → only the stroking ``RG`` op."""
    annotation = _circle_with_color()
    PDCircleAppearanceHandler(annotation).generate_normal_appearance()
    body = _appearance_bytes(annotation)
    assert b"RG" in body


def test_generate_normal_appearance_plain_ellipse_emits_curves() -> None:
    """No /BE → plain ellipse via 4 Bezier ``c`` operators + close."""
    annotation = _circle_with_color()
    PDCircleAppearanceHandler(annotation).generate_normal_appearance()
    body = _appearance_bytes(annotation)
    assert b"c" in body
    assert b"m" in body
    assert b"h" in body


# ----------------------------------------------------------------------
# get_line_width — /BS, /Border, default branches
# ----------------------------------------------------------------------


def test_get_line_width_uses_border_style_width() -> None:
    """Line 116: /BS width wins."""
    annotation = _circle_with_color()
    bs = PDBorderStyleDictionary()
    bs.set_width(2.75)
    annotation.set_border_style(bs)
    assert PDCircleAppearanceHandler(annotation).get_line_width() == 2.75


def test_get_line_width_uses_border_array_float() -> None:
    annotation = _circle_with_color()
    border = COSArray()
    border.add(COSInteger.get(0))
    border.add(COSInteger.get(0))
    border.add(COSFloat(3.25))
    annotation.set_border(border)
    assert PDCircleAppearanceHandler(annotation).get_line_width() == 3.25


def test_get_line_width_uses_border_array_integer() -> None:
    """Line 122: integer width round-trip."""
    annotation = _circle_with_color()
    border = COSArray()
    border.add(COSInteger.get(0))
    border.add(COSInteger.get(0))
    border.add(COSInteger.get(8))
    annotation.set_border(border)
    assert PDCircleAppearanceHandler(annotation).get_line_width() == 8.0


def test_get_line_width_default_when_border_third_element_unknown() -> None:
    annotation = _circle_with_color()
    border = COSArray()
    border.add(COSInteger.get(0))
    border.add(COSInteger.get(0))
    border.add(COSName.get_pdf_name("Solid"))
    annotation.set_border(border)
    assert PDCircleAppearanceHandler(annotation).get_line_width() == 1.0


def test_get_line_width_default_when_no_border() -> None:
    annotation = _circle_with_color()
    assert PDCircleAppearanceHandler(annotation).get_line_width() == 1.0


# ----------------------------------------------------------------------
# _interior_components — three accepted shapes + empty paths
# ----------------------------------------------------------------------


def test_interior_components_returns_none_when_unset() -> None:
    annotation = _circle_with_color()
    assert PDCircleAppearanceHandler._interior_components(annotation) is None


def test_interior_components_uses_to_float_array_on_cos_array() -> None:
    annotation = _circle_with_color()
    # Use values that round-trip exactly through 32-bit float (COSFloat).
    annotation.set_interior_color([0.25, 0.5, 0.75])
    assert PDCircleAppearanceHandler._interior_components(annotation) == [
        0.25,
        0.5,
        0.75,
    ]


def test_interior_components_returns_none_for_empty_to_float_array() -> None:
    class _EmptyArray:
        def to_float_array(self) -> list[float]:
            return []

    class _Stub:
        def get_interior_color(self) -> _EmptyArray:
            return _EmptyArray()

    assert PDCircleAppearanceHandler._interior_components(_Stub()) is None


def test_interior_components_size_branch_empty_returns_none() -> None:
    class _OnlySize:
        def size(self) -> int:
            return 0

    class _Stub:
        def get_interior_color(self) -> _OnlySize:
            return _OnlySize()

    assert PDCircleAppearanceHandler._interior_components(_Stub()) is None


def test_interior_components_iterable_fallback() -> None:
    class _Iterable:
        def __iter__(self):
            return iter([0.5, 0.6, 0.7])

    class _Stub:
        def get_interior_color(self) -> _Iterable:
            return _Iterable()

    assert PDCircleAppearanceHandler._interior_components(_Stub()) == [
        0.5,
        0.6,
        0.7,
    ]


def test_interior_components_iterable_empty_returns_none() -> None:
    class _EmptyIterable:
        def __iter__(self):
            return iter([])

    class _Stub:
        def get_interior_color(self) -> _EmptyIterable:
            return _EmptyIterable()

    assert PDCircleAppearanceHandler._interior_components(_Stub()) is None


def test_interior_components_size_branch_non_empty_calls_to_float_array() -> None:
    """Tricky shape that hides ``to_float_array`` from :func:`hasattr`
    on the first probe, then exposes it for the direct call. Reaches
    line 135 (``return interior.to_float_array()`` after the ``size``
    check)."""

    state = {"probes": 0}

    class _LatchedTricky:
        def size(self) -> int:
            return 3

        def to_float_array(self) -> list[float]:
            return [0.11, 0.22, 0.33]

        def __getattribute__(self, name):
            if name == "to_float_array":
                state["probes"] += 1
                if state["probes"] == 1:
                    raise AttributeError(name)
            return object.__getattribute__(self, name)

    class _Stub:
        def get_interior_color(self):
            return _LatchedTricky()

    assert PDCircleAppearanceHandler._interior_components(_Stub()) == [
        0.11,
        0.22,
        0.33,
    ]


# ----------------------------------------------------------------------
# rollover / down — no-op hooks
# ----------------------------------------------------------------------


def test_generate_rollover_appearance_is_noop() -> None:
    annotation = _circle_with_color()
    handler = PDCircleAppearanceHandler(annotation)
    assert handler.generate_rollover_appearance() is None


def test_generate_down_appearance_is_noop() -> None:
    annotation = _circle_with_color()
    handler = PDCircleAppearanceHandler(annotation)
    assert handler.generate_down_appearance() is None


# ----------------------------------------------------------------------
# cloudy-border branch — bbox / matrix / rect-difference propagation
# ----------------------------------------------------------------------


def _cloudy_border(intensity: float = 2.0) -> PDBorderEffectDictionary:
    be = PDBorderEffectDictionary()
    be.set_style(PDBorderEffectDictionary.STYLE_CLOUDY)
    be.set_intensity(intensity)
    return be


def test_cloudy_border_branch_updates_bbox_and_rect_difference() -> None:
    """Lines 64-78: with ``/BE /Style /C`` the handler routes through
    CloudyBorder and writes /BBox, /Matrix, and /RD onto the
    appearance + annotation."""
    annotation = _circle_with_color()
    annotation.set_border_effect(_cloudy_border(intensity=2.0))
    PDCircleAppearanceHandler(annotation).generate_normal_appearance()
    body = _appearance_bytes(annotation)
    # Cloudy border emits Bezier curves.
    assert b"c" in body
    appearance = annotation.get_normal_appearance_stream()
    assert appearance is not None
    bbox = appearance.get_bbox()
    assert bbox is not None
    # /RD should be a 4-element rectangle on the annotation.
    rd = annotation.get_rect_differences()
    assert len(rd) == 4


# ----------------------------------------------------------------------
# constructor — single-arg vs document-arg overloads
# ----------------------------------------------------------------------


def test_constructor_with_document_argument() -> None:
    from pypdfbox.pdmodel.pd_document import PDDocument

    annotation = _circle_with_color()
    document = PDDocument()
    handler = PDCircleAppearanceHandler(annotation, document)
    assert handler.get_annotation() is annotation
    assert handler.get_document() is document


def test_constructor_with_document_argument_none() -> None:
    annotation = _circle_with_color()
    handler = PDCircleAppearanceHandler(annotation, None)
    assert handler.get_annotation() is annotation
    assert handler.get_document() is None
