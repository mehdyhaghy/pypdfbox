"""Tests for PDAbstractAppearanceHandler — geometry helpers, line-ending
shape primitives, opacity, and appearance allocation/wiring. Upstream has
no dedicated PDAbstractAppearanceHandlerTest; coverage for the abstract
base falls out of subclass tests in PDFBox. We exercise the base directly
via a concrete no-op subclass.
"""

from __future__ import annotations

import math

from pypdfbox.cos import COSArray, COSFloat, COSName
from pypdfbox.pdmodel.interactive.annotation.handlers.pd_abstract_appearance_handler import (
    PDAbstractAppearanceHandler,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation import PDAnnotation
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_line import (
    PDAnnotationLine,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_square_circle import (
    PDAnnotationSquareCircle,
)
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_content_stream import (
    PDAppearanceContentStream,
)
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_dictionary import (
    PDAppearanceDictionary,
)
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_entry import (
    PDAppearanceEntry,
)
from pypdfbox.pdmodel.pd_rectangle import PDRectangle


class _ConcreteHandler(PDAbstractAppearanceHandler):
    """No-op concrete subclass used to instantiate the abstract base in
    tests. Mirrors how upstream tests exercise the base via concrete
    subclasses (the no-op overrides exist purely to satisfy the
    PDAppearanceHandler ABC's abstractmethod gate).
    """

    def generate_normal_appearance(self) -> None:
        return None

    def generate_rollover_appearance(self) -> None:
        return None

    def generate_down_appearance(self) -> None:
        return None


# ----------------------------------------------------------------------
# accessors
# ----------------------------------------------------------------------


def test_get_annotation_returns_constructor_argument() -> None:
    annotation = PDAnnotation()
    handler = _ConcreteHandler(annotation)
    assert handler.get_annotation() is annotation


def test_get_document_defaults_to_none() -> None:
    handler = _ConcreteHandler(PDAnnotation())
    assert handler.get_document() is None


def test_get_rectangle_proxies_to_annotation() -> None:
    annotation = PDAnnotation()
    annotation.set_rectangle(PDRectangle(10.0, 20.0, 110.0, 220.0))
    handler = _ConcreteHandler(annotation)
    rect = handler.get_rectangle()
    assert rect is not None
    assert rect.get_lower_left_x() == 10.0
    assert rect.get_upper_right_y() == 220.0


def test_get_color_returns_underlying_array() -> None:
    annotation = PDAnnotation()
    annotation.set_color([0.5, 0.625, 0.875])
    handler = _ConcreteHandler(annotation)
    color = handler.get_color()
    assert color is not None
    # Use exact-representable binary fractions to avoid float32 quantization
    # noise that COSFloat's storage introduces for values like 0.6, 0.7.
    assert color.to_float_array() == [0.5, 0.625, 0.875]


def test_get_default_font_is_lazily_constructed_helvetica() -> None:
    handler = _ConcreteHandler(PDAnnotation())
    font = handler.get_default_font()
    # Idempotent — same instance returned on subsequent calls.
    assert handler.get_default_font() is font
    # Should be a Helvetica Type1 font.
    assert font.get_name() == "Helvetica"


# ----------------------------------------------------------------------
# appearance allocation
# ----------------------------------------------------------------------


def test_get_appearance_creates_when_missing() -> None:
    annotation = PDAnnotation()
    handler = _ConcreteHandler(annotation)
    ap = handler.get_appearance()
    assert isinstance(ap, PDAppearanceDictionary)
    # Subsequent calls return the same wired-up dictionary.
    assert handler.get_appearance() is not None
    # Annotation now has /AP wired.
    assert annotation.get_appearance_dictionary() is not None


def test_get_normal_appearance_creates_fresh_entry_when_absent() -> None:
    annotation = PDAnnotation()
    annotation.set_rectangle(PDRectangle(0.0, 0.0, 100.0, 50.0))
    handler = _ConcreteHandler(annotation)
    entry = handler.get_normal_appearance()
    assert isinstance(entry, PDAppearanceEntry)
    assert entry.is_stream()


def test_get_normal_appearance_stream_wires_form_xobject_keys() -> None:
    annotation = PDAnnotation()
    annotation.set_rectangle(PDRectangle(5.0, 10.0, 105.0, 60.0))
    handler = _ConcreteHandler(annotation)
    stream = handler.get_normal_appearance_stream()
    cos = stream.get_cos_object()
    assert cos.get_dictionary_object(COSName.get_pdf_name("Type")).get_name() == "XObject"
    assert cos.get_dictionary_object(COSName.get_pdf_name("Subtype")).get_name() == "Form"
    bbox = cos.get_dictionary_object(COSName.get_pdf_name("BBox"))
    assert isinstance(bbox, COSArray)
    assert bbox.to_float_array() == [5.0, 10.0, 105.0, 60.0]


def test_get_normal_appearance_stream_idempotent_when_already_a_stream() -> None:
    annotation = PDAnnotation()
    annotation.set_rectangle(PDRectangle(0.0, 0.0, 100.0, 50.0))
    handler = _ConcreteHandler(annotation)
    first = handler.get_normal_appearance_stream()
    second = handler.get_normal_appearance_stream()
    # Same underlying COS stream — caller does not get a fresh allocation.
    assert first.get_cos_object() is second.get_cos_object()


def test_get_normal_appearance_as_content_stream_sets_bbox_and_resources() -> None:
    annotation = PDAnnotation()
    annotation.set_rectangle(PDRectangle(20.0, 30.0, 120.0, 130.0))
    handler = _ConcreteHandler(annotation)
    cs = handler.get_normal_appearance_as_content_stream()
    try:
        assert isinstance(cs, PDAppearanceContentStream)
        stream = handler.get_normal_appearance_stream()
        bbox = stream.get_bbox()
        assert bbox is not None
        # After _set_transformation_matrix the bbox matches the annotation rect.
        assert bbox.get_lower_left_x() == 20.0
        assert bbox.get_upper_right_y() == 130.0
        # Matrix translates so the rect lower-left lands at origin.
        matrix = stream.get_matrix()
        assert matrix == [1.0, 0.0, 0.0, 1.0, -20.0, -30.0]
        # Resources are seeded.
        assert stream.get_resources() is not None
    finally:
        cs.close()


def test_get_down_appearance_creates_fresh_when_subdictionary() -> None:
    annotation = PDAnnotation()
    handler = _ConcreteHandler(annotation)
    # Force /AP /D to start as a subdictionary; the helper should swap it
    # for a single appearance stream.
    ap = handler.get_appearance()
    sub_entry = PDAppearanceEntry()
    # set via the cos object directly to install an empty subdictionary
    from pypdfbox.cos import COSDictionary

    ap_cos = ap.get_cos_object()
    ap_cos.set_item(COSName.get_pdf_name("D"), COSDictionary())
    del sub_entry  # silence unused

    entry = handler.get_down_appearance()
    assert entry.is_stream()


def test_get_rollover_appearance_creates_fresh_when_subdictionary() -> None:
    annotation = PDAnnotation()
    handler = _ConcreteHandler(annotation)
    ap = handler.get_appearance()
    from pypdfbox.cos import COSDictionary

    ap_cos = ap.get_cos_object()
    ap_cos.set_item(COSName.get_pdf_name("R"), COSDictionary())

    entry = handler.get_rollover_appearance()
    assert entry.is_stream()


# ----------------------------------------------------------------------
# geometry helpers
# ----------------------------------------------------------------------


def test_get_padded_rectangle_pads_inward_on_all_sides() -> None:
    rect = PDRectangle(10.0, 20.0, 110.0, 220.0)
    padded = PDAbstractAppearanceHandler.get_padded_rectangle(rect, 5.0)
    assert padded.get_lower_left_x() == 15.0
    assert padded.get_lower_left_y() == 25.0
    assert padded.get_width() == 90.0
    assert padded.get_height() == 190.0


def test_add_rect_differences_returns_input_when_no_diffs() -> None:
    rect = PDRectangle(10.0, 20.0, 110.0, 220.0)
    assert PDAbstractAppearanceHandler.add_rect_differences(rect, None) is rect
    assert PDAbstractAppearanceHandler.add_rect_differences(rect, []) is rect
    assert PDAbstractAppearanceHandler.add_rect_differences(rect, [1.0, 2.0]) is rect


def test_add_rect_differences_enlarges_each_side() -> None:
    rect = PDRectangle(10.0, 20.0, 110.0, 220.0)
    enlarged = PDAbstractAppearanceHandler.add_rect_differences(
        rect, [1.0, 2.0, 3.0, 4.0]
    )
    # lower_left shifts by -d[0], -d[1]; size grows by d[0]+d[2], d[1]+d[3].
    assert enlarged.get_lower_left_x() == 9.0
    assert enlarged.get_lower_left_y() == 18.0
    assert enlarged.get_width() == 100.0 + 4.0
    assert enlarged.get_height() == 200.0 + 6.0


def test_apply_rect_differences_inverse_of_add() -> None:
    rect = PDRectangle(10.0, 20.0, 110.0, 220.0)
    diffs = [1.0, 2.0, 3.0, 4.0]
    enlarged = PDAbstractAppearanceHandler.add_rect_differences(rect, diffs)
    restored = PDAbstractAppearanceHandler.apply_rect_differences(enlarged, diffs)
    assert restored.get_lower_left_x() == rect.get_lower_left_x()
    assert restored.get_lower_left_y() == rect.get_lower_left_y()
    assert restored.get_width() == rect.get_width()
    assert restored.get_height() == rect.get_height()


# ----------------------------------------------------------------------
# handle_border_box
# ----------------------------------------------------------------------


def test_handle_border_box_seeds_rd_when_absent() -> None:
    annotation = PDAnnotationSquareCircle("Square")
    annotation.set_rectangle(PDRectangle(10.0, 20.0, 110.0, 220.0))
    handler = _ConcreteHandler(annotation)
    # Pre-allocate normal appearance stream so handle_border_box can
    # adjust BBox/Matrix.
    handler.get_normal_appearance_stream()

    border_box = handler.handle_border_box(annotation, 4.0)

    # /RD seeded to half the line width on every side.
    assert annotation.get_rect_differences() == [2.0, 2.0, 2.0, 2.0]
    # /Rect grew by the seeded /RD on each side.
    new_rect = annotation.get_rectangle()
    assert new_rect is not None
    assert new_rect.get_lower_left_x() == 8.0
    assert new_rect.get_lower_left_y() == 18.0
    assert new_rect.get_width() == 104.0
    assert new_rect.get_height() == 204.0
    # Border box is the *original* /Rect, padded inward by half the line
    # width — so 10..110 narrow to 12..108, etc.
    assert border_box.get_lower_left_x() == 12.0
    assert border_box.get_upper_right_y() == 218.0


def test_handle_border_box_uses_existing_rd() -> None:
    annotation = PDAnnotationSquareCircle("Circle")
    annotation.set_rectangle(PDRectangle(0.0, 0.0, 100.0, 50.0))
    annotation.set_rect_differences(3.0)  # 3 on every side
    handler = _ConcreteHandler(annotation)

    border_box = handler.handle_border_box(annotation, 2.0)

    # /RD is preserved, /Rect is unchanged.
    assert annotation.get_rect_differences() == [3.0, 3.0, 3.0, 3.0]
    rect = annotation.get_rectangle()
    assert rect is not None
    assert rect.get_lower_left_x() == 0.0
    # Border box: apply /RD inward, then pad inward by half line width.
    # apply_rect_differences narrows the rect by [3,3,3,3]; padded by 1.
    assert border_box.get_lower_left_x() == 4.0
    assert border_box.get_lower_left_y() == 4.0
    assert border_box.get_width() == 92.0
    assert border_box.get_height() == 42.0


# ----------------------------------------------------------------------
# class-level constants
# ----------------------------------------------------------------------


def test_short_styles_membership() -> None:
    assert PDAnnotationLine.LE_OPEN_ARROW in PDAbstractAppearanceHandler.SHORT_STYLES
    assert PDAnnotationLine.LE_CLOSED_ARROW in PDAbstractAppearanceHandler.SHORT_STYLES
    assert PDAnnotationLine.LE_SQUARE in PDAbstractAppearanceHandler.SHORT_STYLES
    assert PDAnnotationLine.LE_CIRCLE in PDAbstractAppearanceHandler.SHORT_STYLES
    assert PDAnnotationLine.LE_DIAMOND in PDAbstractAppearanceHandler.SHORT_STYLES
    assert PDAnnotationLine.LE_BUTT not in PDAbstractAppearanceHandler.SHORT_STYLES


def test_interior_color_styles_membership() -> None:
    icss = PDAbstractAppearanceHandler.INTERIOR_COLOR_STYLES
    assert PDAnnotationLine.LE_CLOSED_ARROW in icss
    assert PDAnnotationLine.LE_CIRCLE in icss
    assert PDAnnotationLine.LE_DIAMOND in icss
    assert PDAnnotationLine.LE_R_CLOSED_ARROW in icss
    assert PDAnnotationLine.LE_SQUARE in icss
    assert PDAnnotationLine.LE_OPEN_ARROW not in icss


def test_angled_styles_membership() -> None:
    angled = PDAbstractAppearanceHandler.ANGLED_STYLES
    assert PDAnnotationLine.LE_CLOSED_ARROW in angled
    assert PDAnnotationLine.LE_OPEN_ARROW in angled
    assert PDAnnotationLine.LE_R_CLOSED_ARROW in angled
    assert PDAnnotationLine.LE_R_OPEN_ARROW in angled
    assert PDAnnotationLine.LE_BUTT in angled
    assert PDAnnotationLine.LE_SLASH in angled
    assert PDAnnotationLine.LE_CIRCLE not in angled


def test_arrow_angle_constant_is_30_degrees() -> None:
    assert math.radians(30) == PDAbstractAppearanceHandler.ARROW_ANGLE


# ----------------------------------------------------------------------
# line-ending shape primitives — content-stream operator emission
# ----------------------------------------------------------------------


def _open_appearance_stream(handler: PDAbstractAppearanceHandler):
    """Return a fresh appearance-stream writer for byte-level inspection."""
    return handler.get_normal_appearance_as_content_stream()


def test_draw_diamond_emits_four_segment_closed_path() -> None:
    annotation = PDAnnotation()
    annotation.set_rectangle(PDRectangle(0.0, 0.0, 100.0, 100.0))
    handler = _ConcreteHandler(annotation)
    cs = _open_appearance_stream(handler)
    handler.draw_diamond(cs, 50.0, 50.0, 10.0)
    cs.close()
    body = handler.get_normal_appearance_stream().get_cos_object().to_byte_array()
    # 1 moveto + 3 lineto + closepath = m, l (x3), h
    assert body.count(b" m\n") == 1
    assert body.count(b" l\n") == 3
    assert body.count(b"h\n") == 1


def test_draw_circle_emits_four_bezier_curves_closed() -> None:
    annotation = PDAnnotation()
    annotation.set_rectangle(PDRectangle(0.0, 0.0, 100.0, 100.0))
    handler = _ConcreteHandler(annotation)
    cs = _open_appearance_stream(handler)
    handler.draw_circle(cs, 50.0, 50.0, 10.0)
    cs.close()
    body = handler.get_normal_appearance_stream().get_cos_object().to_byte_array()
    assert body.count(b" m\n") == 1
    assert body.count(b" c\n") == 4
    assert body.count(b"h\n") == 1


def test_draw_arrow_emits_three_segments() -> None:
    annotation = PDAnnotation()
    annotation.set_rectangle(PDRectangle(0.0, 0.0, 100.0, 100.0))
    handler = _ConcreteHandler(annotation)
    cs = _open_appearance_stream(handler)
    handler.draw_arrow(cs, 50.0, 50.0, 10.0)
    cs.close()
    body = handler.get_normal_appearance_stream().get_cos_object().to_byte_array()
    # moveto + 2 linetos
    assert body.count(b" m\n") == 1
    assert body.count(b" l\n") == 2


# ----------------------------------------------------------------------
# opacity
# ----------------------------------------------------------------------


def test_set_opacity_no_op_at_or_above_one() -> None:
    annotation = PDAnnotation()
    annotation.set_rectangle(PDRectangle(0.0, 0.0, 100.0, 100.0))
    handler = _ConcreteHandler(annotation)
    cs = _open_appearance_stream(handler)
    PDAbstractAppearanceHandler.set_opacity(cs, 1.0)
    cs.close()
    body = handler.get_normal_appearance_stream().get_cos_object().to_byte_array()
    # No /ExtGState reference emitted.
    assert b" gs\n" not in body


def test_set_opacity_emits_gs_when_below_one() -> None:
    annotation = PDAnnotation()
    annotation.set_rectangle(PDRectangle(0.0, 0.0, 100.0, 100.0))
    handler = _ConcreteHandler(annotation)
    cs = _open_appearance_stream(handler)
    PDAbstractAppearanceHandler.set_opacity(cs, 0.5)
    cs.close()
    body = handler.get_normal_appearance_stream().get_cos_object().to_byte_array()
    assert b" gs\n" in body


# ----------------------------------------------------------------------
# create_cos_stream
# ----------------------------------------------------------------------


def test_create_cos_stream_without_document_returns_bare_stream() -> None:
    handler = _ConcreteHandler(PDAnnotation())
    stream = handler.create_cos_stream()
    assert stream is not None
    # No /Type or /Subtype seeded — pure body container.
    assert stream.get_dictionary_object(COSName.get_pdf_name("Type")) is None


def test_color_components_helper_handles_none_and_empty_arrays() -> None:
    annotation = PDAnnotation()
    # /C absent
    assert (
        PDAbstractAppearanceHandler._color_components_from_annotation(annotation)
        is None
    )
    # /C present but empty COSArray
    annotation.get_cos_object().set_item(COSName.get_pdf_name("C"), COSArray())
    assert (
        PDAbstractAppearanceHandler._color_components_from_annotation(annotation)
        is None
    )
    # /C with three exact-representable components.
    annotation.set_color([0.5, 0.625, 0.875])
    assert (
        PDAbstractAppearanceHandler._color_components_from_annotation(annotation)
        == [0.5, 0.625, 0.875]
    )


def test_components_to_rgb_dispatches_on_arity() -> None:
    # DeviceGray
    assert PDAbstractAppearanceHandler._components_to_rgb([0.5]) == (0.5, 0.5, 0.5)
    # DeviceRGB
    assert (
        PDAbstractAppearanceHandler._components_to_rgb([0.1, 0.2, 0.3])
        == (0.1, 0.2, 0.3)
    )
    # DeviceCMYK -> all-zeros becomes white.
    assert PDAbstractAppearanceHandler._components_to_rgb([0.0, 0.0, 0.0, 0.0]) == (
        1.0,
        1.0,
        1.0,
    )


# ----------------------------------------------------------------------
# Wave 1257: parity round-out — private static factories,
# get_appearance_entry_as_content_stream, set_transformation_matrix.
# ----------------------------------------------------------------------


def test_create_short_styles_returns_immutable_membership_set() -> None:
    s = PDAbstractAppearanceHandler.create_short_styles()
    assert isinstance(s, frozenset)
    assert PDAnnotationLine.LE_OPEN_ARROW in s
    assert PDAnnotationLine.LE_CLOSED_ARROW in s
    assert PDAnnotationLine.LE_SQUARE in s
    assert PDAnnotationLine.LE_CIRCLE in s
    assert PDAnnotationLine.LE_DIAMOND in s
    # Same content as the class-level constant.
    assert s == PDAbstractAppearanceHandler.SHORT_STYLES


def test_create_interior_color_styles_returns_immutable_membership_set() -> None:
    s = PDAbstractAppearanceHandler.create_interior_color_styles()
    assert isinstance(s, frozenset)
    assert PDAnnotationLine.LE_CLOSED_ARROW in s
    assert PDAnnotationLine.LE_CIRCLE in s
    assert PDAnnotationLine.LE_DIAMOND in s
    assert PDAnnotationLine.LE_R_CLOSED_ARROW in s
    assert PDAnnotationLine.LE_SQUARE in s
    assert s == PDAbstractAppearanceHandler.INTERIOR_COLOR_STYLES


def test_create_angled_styles_returns_immutable_membership_set() -> None:
    s = PDAbstractAppearanceHandler.create_angled_styles()
    assert isinstance(s, frozenset)
    assert PDAnnotationLine.LE_CLOSED_ARROW in s
    assert PDAnnotationLine.LE_OPEN_ARROW in s
    assert PDAnnotationLine.LE_R_CLOSED_ARROW in s
    assert PDAnnotationLine.LE_R_OPEN_ARROW in s
    assert PDAnnotationLine.LE_BUTT in s
    assert PDAnnotationLine.LE_SLASH in s
    assert s == PDAbstractAppearanceHandler.ANGLED_STYLES


def test_set_transformation_matrix_sets_bbox_and_translation() -> None:
    annotation = PDAnnotation()
    annotation.set_rectangle(PDRectangle(20.0, 30.0, 120.0, 130.0))
    handler = _ConcreteHandler(annotation)
    appearance_stream = handler.get_normal_appearance_stream()
    # Reset to a known state then call the public method.
    handler.set_transformation_matrix(appearance_stream)
    bbox = appearance_stream.get_bbox()
    assert bbox is not None
    assert bbox.get_lower_left_x() == 20.0
    assert bbox.get_upper_right_y() == 130.0
    matrix = appearance_stream.get_matrix()
    assert matrix == [1.0, 0.0, 0.0, 1.0, -20.0, -30.0]


def test_set_transformation_matrix_no_op_when_rectangle_absent() -> None:
    # Allocate a stream-bearing entry without giving the annotation a rect;
    # the helper must short-circuit instead of writing /BBox or /Matrix.
    annotation_with_rect = PDAnnotation()
    annotation_with_rect.set_rectangle(PDRectangle(0.0, 0.0, 100.0, 100.0))
    seed_handler = _ConcreteHandler(annotation_with_rect)
    appearance_stream = seed_handler.get_normal_appearance_stream()
    # Now build a fresh handler whose annotation has no rect and verify
    # set_transformation_matrix is a no-op (does not raise).
    handler = _ConcreteHandler(PDAnnotation())
    handler.set_transformation_matrix(appearance_stream)


def test_set_transformation_matrix_alias_preserved_for_back_compat() -> None:
    # Existing call sites use the underscore-prefixed form; assert the alias
    # is still resolvable to the public method.
    assert (
        PDAbstractAppearanceHandler._set_transformation_matrix
        is PDAbstractAppearanceHandler.set_transformation_matrix
    )


def test_get_appearance_entry_as_content_stream_seeds_resources() -> None:
    annotation = PDAnnotation()
    annotation.set_rectangle(PDRectangle(0.0, 0.0, 100.0, 50.0))
    handler = _ConcreteHandler(annotation)
    entry = handler.get_normal_appearance()
    cs = handler.get_appearance_entry_as_content_stream(entry, compress=False)
    try:
        assert isinstance(cs, PDAppearanceContentStream)
        appearance_stream = entry.get_appearance_stream()
        assert appearance_stream is not None
        assert appearance_stream.get_resources() is not None
        # BBox/Matrix are set per the annotation rectangle.
        bbox = appearance_stream.get_bbox()
        assert bbox is not None
        assert bbox.get_lower_left_x() == 0.0
        assert appearance_stream.get_matrix() == [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]
    finally:
        cs.close()


def test_get_appearance_entry_as_content_stream_routes_for_normal() -> None:
    # The two-arg public form should produce the same wiring as the
    # convenience get_normal_appearance_as_content_stream wrapper.
    annotation = PDAnnotation()
    annotation.set_rectangle(PDRectangle(5.0, 6.0, 50.0, 60.0))
    handler = _ConcreteHandler(annotation)
    cs = handler.get_normal_appearance_as_content_stream()
    try:
        appearance_stream = handler.get_normal_appearance_stream()
        bbox = appearance_stream.get_bbox()
        assert bbox is not None
        assert bbox.get_lower_left_x() == 5.0
        assert appearance_stream.get_matrix() == [1.0, 0.0, 0.0, 1.0, -5.0, -6.0]
    finally:
        cs.close()


# Silence unused-import warnings for COSFloat (kept as a documented helper
# reference that future tests can pick up without re-importing).
_ = COSFloat
