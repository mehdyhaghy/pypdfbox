"""Coverage-boost tests for
``pypdfbox.pdmodel.interactive.annotation.handlers.pd_polygon_appearance_handler``.

Closes the remaining gaps:

* Early returns: wrong annotation type (line 35), missing /Rect
  (line 39), missing /Path + /Vertices (line 42).
* Interior color branch — emits non-stroking color (line 74).
* ``_emit_polygon`` curve-segment branch (lines 109-110): a /Path
  entry of length 6 must produce a ``c`` operator.
* ``get_path_array`` priority: PDF 2.0 /Path wins (line 123); /Vertices
  None → return None (line 126).
* ``get_line_width`` branches: /BS, /Border-float, /Border-integer,
  default (lines 144, 150).
* ``_interior_components`` accepts all three input shapes + empty cases
  (lines 157-165).
* No-op rollover / down hooks.
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSFloat, COSInteger, COSName
from pypdfbox.pdmodel.interactive.annotation.handlers.pd_polygon_appearance_handler import (
    PDPolygonAppearanceHandler,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation import PDAnnotation
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_polygon import (
    PDAnnotationPolygon,
)
from pypdfbox.pdmodel.interactive.annotation.pd_border_style_dictionary import (
    PDBorderStyleDictionary,
)
from pypdfbox.pdmodel.pd_rectangle import PDRectangle

_RECT = (0.0, 0.0, 200.0, 200.0)


def _polygon_with_color() -> PDAnnotationPolygon:
    annotation = PDAnnotationPolygon()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_color([0.0, 0.5, 0.0])
    annotation.set_vertices([20.0, 20.0, 180.0, 20.0, 100.0, 180.0])
    return annotation


def _appearance_bytes(annotation) -> bytes:
    ap = annotation.get_appearance_dictionary()
    assert ap is not None
    stream = ap.get_normal_appearance().get_appearance_stream()
    return stream.get_stream().to_byte_array()


# ----------------------------------------------------------------------
# generate_normal_appearance — early-return branches
# ----------------------------------------------------------------------


def test_generate_normal_appearance_returns_when_not_polygon() -> None:
    """Line 35: wrong annotation type bails before writing /AP."""
    annotation = PDAnnotation()
    annotation.set_rectangle(PDRectangle(*_RECT))
    PDPolygonAppearanceHandler(annotation).generate_normal_appearance()
    assert annotation.get_appearance_dictionary() is None


def test_generate_normal_appearance_returns_when_rect_missing() -> None:
    """Line 39: /Rect missing → no /AP written."""
    annotation = PDAnnotationPolygon()
    annotation.set_color([0.0, 0.5, 0.0])
    annotation.set_vertices([20.0, 20.0, 180.0, 20.0, 100.0, 180.0])
    # No set_rectangle().
    PDPolygonAppearanceHandler(annotation).generate_normal_appearance()
    assert annotation.get_appearance_dictionary() is None


def test_generate_normal_appearance_returns_when_path_array_none() -> None:
    """Line 42: neither /Path nor /Vertices → bail."""
    annotation = PDAnnotationPolygon()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_color([0.0, 0.5, 0.0])
    # No vertices, no path.
    PDPolygonAppearanceHandler(annotation).generate_normal_appearance()
    assert annotation.get_appearance_dictionary() is None


# ----------------------------------------------------------------------
# generate_normal_appearance — interior color branch
# ----------------------------------------------------------------------


def test_generate_normal_appearance_with_interior_color_sets_non_stroking() -> None:
    """Line 74: when /IC is set the handler emits a non-stroking color
    (lowercase ``rg`` operator for DeviceRGB)."""
    annotation = _polygon_with_color()
    annotation.set_interior_color([1.0, 1.0, 0.0])
    PDPolygonAppearanceHandler(annotation).generate_normal_appearance()
    body = _appearance_bytes(annotation)
    assert b"rg" in body


def test_generate_normal_appearance_without_interior_color_skips_fill() -> None:
    """Negation of line 73: no /IC → no ``rg`` op."""
    annotation = _polygon_with_color()
    PDPolygonAppearanceHandler(annotation).generate_normal_appearance()
    body = _appearance_bytes(annotation)
    # Stroking RGB color (RG) is emitted, not non-stroking.
    assert b"RG" in body


# ----------------------------------------------------------------------
# _emit_polygon — curve-segment branch
# ----------------------------------------------------------------------


def test_emit_polygon_curve_segment_emits_curve_to() -> None:
    """Lines 109-110: a /Path entry of length 6 triggers ``cs.curve_to``
    (a ``c`` operator in the stream)."""
    annotation = PDAnnotationPolygon()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_color([0.0, 0.5, 0.0])
    # PDF 2.0 /Path: first entry move (length 2), second is a Bezier
    # (length 6).
    annotation.set_path(
        [[20.0, 20.0], [30.0, 40.0, 50.0, 60.0, 70.0, 80.0]]
    )
    PDPolygonAppearanceHandler(annotation).generate_normal_appearance()
    body = _appearance_bytes(annotation)
    assert b"c" in body
    assert b"m" in body


def test_emit_polygon_line_segments_emit_line_to() -> None:
    """First-vertex non-2 fallback + subsequent /Vertices line-to."""
    annotation = _polygon_with_color()
    PDPolygonAppearanceHandler(annotation).generate_normal_appearance()
    body = _appearance_bytes(annotation)
    assert b"m" in body
    assert b"l" in body
    assert b"h" in body  # close_path


# ----------------------------------------------------------------------
# get_path_array — /Path priority + /Vertices None branch
# ----------------------------------------------------------------------


def test_get_path_array_returns_path_when_present() -> None:
    """Line 123: PDF 2.0 /Path takes priority over /Vertices."""
    annotation = PDAnnotationPolygon()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_color([0.0, 0.5, 0.0])
    # Set both; /Path wins.
    annotation.set_vertices([1.0, 2.0, 3.0, 4.0])
    annotation.set_path([[10.0, 10.0], [20.0, 20.0]])
    handler = PDPolygonAppearanceHandler(annotation)
    arr = handler.get_path_array(annotation)
    assert arr == [[10.0, 10.0], [20.0, 20.0]]


def test_get_path_array_returns_none_when_vertices_none() -> None:
    """Line 126: no /Path and no /Vertices → return None."""
    annotation = PDAnnotationPolygon()
    annotation.set_rectangle(PDRectangle(*_RECT))
    handler = PDPolygonAppearanceHandler(annotation)
    assert handler.get_path_array(annotation) is None


def test_get_path_array_synthesises_from_vertices_when_path_absent() -> None:
    """No /Path → /Vertices is reshaped into a list of [x, y] pairs."""
    annotation = PDAnnotationPolygon()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_vertices([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
    handler = PDPolygonAppearanceHandler(annotation)
    arr = handler.get_path_array(annotation)
    assert arr == [[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]]


# ----------------------------------------------------------------------
# get_line_width — /BS, /Border, default
# ----------------------------------------------------------------------


def test_get_line_width_uses_border_style_width() -> None:
    """Line 144: /BS width wins."""
    annotation = _polygon_with_color()
    bs = PDBorderStyleDictionary()
    bs.set_width(3.5)
    annotation.set_border_style(bs)
    assert PDPolygonAppearanceHandler(annotation).get_line_width() == 3.5


def test_get_line_width_uses_border_array_float() -> None:
    annotation = _polygon_with_color()
    border = COSArray()
    border.add(COSInteger.get(0))
    border.add(COSInteger.get(0))
    border.add(COSFloat(2.5))
    annotation.set_border(border)
    assert PDPolygonAppearanceHandler(annotation).get_line_width() == 2.5


def test_get_line_width_uses_border_array_integer() -> None:
    annotation = _polygon_with_color()
    border = COSArray()
    border.add(COSInteger.get(0))
    border.add(COSInteger.get(0))
    border.add(COSInteger.get(5))
    annotation.set_border(border)
    assert PDPolygonAppearanceHandler(annotation).get_line_width() == 5.0


def test_get_line_width_default_when_border_third_element_unknown() -> None:
    """Line 150: third element is neither COSFloat nor COSInteger → 1.0."""
    annotation = _polygon_with_color()
    border = COSArray()
    border.add(COSInteger.get(0))
    border.add(COSInteger.get(0))
    border.add(COSName.get_pdf_name("Solid"))
    annotation.set_border(border)
    assert PDPolygonAppearanceHandler(annotation).get_line_width() == 1.0


def test_get_line_width_default_when_no_border_style() -> None:
    annotation = _polygon_with_color()
    assert PDPolygonAppearanceHandler(annotation).get_line_width() == 1.0


# ----------------------------------------------------------------------
# _interior_components — three accepted shapes + empty paths
# ----------------------------------------------------------------------


def test_interior_components_returns_none_when_unset() -> None:
    annotation = _polygon_with_color()
    assert PDPolygonAppearanceHandler._interior_components(annotation) is None


def test_interior_components_uses_to_float_array_on_cos_array() -> None:
    annotation = _polygon_with_color()
    annotation.set_interior_color([0.25, 0.5, 0.75])
    assert PDPolygonAppearanceHandler._interior_components(annotation) == [
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

    assert PDPolygonAppearanceHandler._interior_components(_Stub()) is None


def test_interior_components_size_branch_empty_returns_none() -> None:
    class _OnlySize:
        def size(self) -> int:
            return 0

    class _Stub:
        def get_interior_color(self) -> _OnlySize:
            return _OnlySize()

    assert PDPolygonAppearanceHandler._interior_components(_Stub()) is None


def test_interior_components_iterable_fallback() -> None:
    class _Iterable:
        def __iter__(self):
            return iter([0.4, 0.6, 0.8])

    class _Stub:
        def get_interior_color(self) -> _Iterable:
            return _Iterable()

    assert PDPolygonAppearanceHandler._interior_components(_Stub()) == [
        0.4,
        0.6,
        0.8,
    ]


def test_interior_components_iterable_empty_returns_none() -> None:
    class _EmptyIterable:
        def __iter__(self):
            return iter([])

    class _Stub:
        def get_interior_color(self) -> _EmptyIterable:
            return _EmptyIterable()

    assert PDPolygonAppearanceHandler._interior_components(_Stub()) is None


def test_interior_components_size_branch_non_empty_calls_to_float_array() -> None:
    """Lines 161-163: object exposes ``size`` (non-zero) but
    :func:`hasattr` for ``to_float_array`` returns False on probe — then
    direct call succeeds. Mirrors the equivalent square-handler test."""

    state = {"hasattr_probes": 0}

    class _LatchedTricky:
        def size(self) -> int:
            return 3

        def to_float_array(self) -> list[float]:
            return [0.11, 0.22, 0.33]

        def __getattribute__(self, name):
            if name == "to_float_array":
                state["hasattr_probes"] += 1
                if state["hasattr_probes"] == 1:
                    raise AttributeError(name)
            return object.__getattribute__(self, name)

    class _Stub:
        def get_interior_color(self):
            return _LatchedTricky()

    assert PDPolygonAppearanceHandler._interior_components(_Stub()) == [
        0.11,
        0.22,
        0.33,
    ]


# ----------------------------------------------------------------------
# rollover / down — no-op hooks
# ----------------------------------------------------------------------


def test_generate_rollover_appearance_is_noop() -> None:
    annotation = _polygon_with_color()
    handler = PDPolygonAppearanceHandler(annotation)
    assert handler.generate_rollover_appearance() is None


def test_generate_down_appearance_is_noop() -> None:
    annotation = _polygon_with_color()
    handler = PDPolygonAppearanceHandler(annotation)
    assert handler.generate_down_appearance() is None


# ----------------------------------------------------------------------
# constructor — single-arg vs document-arg overloads
# ----------------------------------------------------------------------


def test_constructor_with_document_argument() -> None:
    from pypdfbox.pdmodel.pd_document import PDDocument

    annotation = _polygon_with_color()
    document = PDDocument()
    handler = PDPolygonAppearanceHandler(annotation, document)
    assert handler.get_annotation() is annotation
    assert handler.get_document() is document


def test_constructor_with_document_argument_none() -> None:
    annotation = _polygon_with_color()
    handler = PDPolygonAppearanceHandler(annotation, None)
    assert handler.get_annotation() is annotation
    assert handler.get_document() is None


# ----------------------------------------------------------------------
# cloudy-border branch — lines 85-96 (CloudyBorder construction +
# bbox / matrix propagation onto the annotation + appearance stream)
# ----------------------------------------------------------------------


def _cloudy_border(intensity: float = 2.0):
    from pypdfbox.pdmodel.interactive.annotation.pd_border_effect_dictionary import (
        PDBorderEffectDictionary,
    )

    be = PDBorderEffectDictionary()
    be.set_style(PDBorderEffectDictionary.STYLE_CLOUDY)
    be.set_intensity(intensity)
    return be


def test_generate_normal_appearance_cloudy_border_updates_bbox_and_matrix() -> None:
    """Lines 85-96: with ``/BE /Style /C``, the cloudy-polygon path
    runs and the resulting bbox / matrix get written onto the
    appearance stream + the annotation's /Rect."""
    annotation = PDAnnotationPolygon()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_color([0.0, 0.5, 0.0])
    annotation.set_vertices([20.0, 20.0, 180.0, 20.0, 100.0, 180.0])
    annotation.set_border_effect(_cloudy_border(intensity=2.0))
    PDPolygonAppearanceHandler(annotation).generate_normal_appearance()
    body = _appearance_bytes(annotation)
    # Cloudy border emits many Bezier curves.
    assert b"c" in body
    appearance = annotation.get_normal_appearance_stream()
    assert appearance is not None
    bbox = appearance.get_bbox()
    assert bbox is not None
    assert bbox.get_width() > 0.0
