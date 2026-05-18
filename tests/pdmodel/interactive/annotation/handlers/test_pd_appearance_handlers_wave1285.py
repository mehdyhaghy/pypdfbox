"""Tests for the wave-1285 expansions to the annotation appearance
handlers — exercises the newly-implemented icon paths
(``PDFileAttachmentAppearanceHandler``), caption support
(``PDLineAppearanceHandler``), cloudy-border integration
(``PDSquareAppearanceHandler`` / ``PDCircleAppearanceHandler``), and
the Multiply blend mode ExtGState
(``PDHighlightAppearanceHandler``).

Each test verifies the appearance stream is populated with non-empty
content after the relevant handler runs.
"""

from __future__ import annotations

from pypdfbox.pdmodel.interactive.annotation.handlers import (
    PDCircleAppearanceHandler,
    PDFileAttachmentAppearanceHandler,
    PDHighlightAppearanceHandler,
    PDLineAppearanceHandler,
    PDSquareAppearanceHandler,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_file_attachment import (
    PDAnnotationFileAttachment,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_highlight import (
    PDAnnotationHighlight,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_line import (
    PDAnnotationLine,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_square_circle import (
    PDAnnotationCircle,
    PDAnnotationSquare,
)
from pypdfbox.pdmodel.interactive.annotation.pd_border_effect_dictionary import (
    PDBorderEffectDictionary,
)
from pypdfbox.pdmodel.pd_rectangle import PDRectangle

_RECT = (10.0, 10.0, 110.0, 60.0)


def _appearance_bytes(annotation) -> bytes:
    ap = annotation.get_appearance_dictionary()
    assert ap is not None
    stream = ap.get_normal_appearance().get_appearance_stream()
    return stream.get_stream().to_byte_array()


# ----------------------------------------------------------------------
# file attachment icon paths
# ----------------------------------------------------------------------


def test_file_attachment_paperclip_emits_path_operators() -> None:
    annotation = PDAnnotationFileAttachment()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_attachment_name("Paperclip")
    PDFileAttachmentAppearanceHandler(annotation).generate_normal_appearance()
    body = _appearance_bytes(annotation)
    # The paperclip path draws curves + a stroke.
    assert b"c" in body or b"l" in body
    assert b"S" in body or b"f" in body


def test_file_attachment_push_pin_emits_path_operators() -> None:
    annotation = PDAnnotationFileAttachment()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_attachment_name("PushPin")
    PDFileAttachmentAppearanceHandler(annotation).generate_normal_appearance()
    body = _appearance_bytes(annotation)
    assert len(body) > 0
    assert b"m" in body  # move_to operator
    assert b"l" in body  # line_to operator


def test_file_attachment_graph_emits_rectangles() -> None:
    annotation = PDAnnotationFileAttachment()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_attachment_name("Graph")
    PDFileAttachmentAppearanceHandler(annotation).generate_normal_appearance()
    body = _appearance_bytes(annotation)
    # The graph draws four bars via add_rect (re operator).
    assert body.count(b"re") >= 4


def test_file_attachment_tag_emits_curves() -> None:
    annotation = PDAnnotationFileAttachment()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_attachment_name("Tag")
    PDFileAttachmentAppearanceHandler(annotation).generate_normal_appearance()
    body = _appearance_bytes(annotation)
    # Tag draws the polygon (lines) + the eyelet (curves).
    assert b"c" in body
    assert b"l" in body


def test_file_attachment_handler_noops_for_wrong_annotation_type() -> None:
    """When the annotation isn't a :class:`PDAnnotationFileAttachment`, the
    handler returns silently without creating an appearance stream."""
    from pypdfbox.pdmodel.interactive.annotation.pd_annotation import PDAnnotation

    annotation = PDAnnotation()
    handler = PDFileAttachmentAppearanceHandler(annotation)
    # Should not raise and should not populate an appearance dictionary.
    assert handler.generate_normal_appearance() is None
    assert annotation.get_appearance_dictionary() is None


def test_file_attachment_handler_noops_when_rect_is_none() -> None:
    """When the annotation has no rectangle, the handler returns silently
    without creating an appearance stream."""
    annotation = PDAnnotationFileAttachment()
    # Explicitly clear any default rectangle.
    annotation.get_cos_object().remove_item("Rect")
    handler = PDFileAttachmentAppearanceHandler(annotation)
    assert handler.generate_normal_appearance() is None
    assert annotation.get_appearance_dictionary() is None


# ----------------------------------------------------------------------
# line caption
# ----------------------------------------------------------------------


def test_line_handler_with_inline_caption_emits_text_block() -> None:
    annotation = PDAnnotationLine()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_color([0.0, 0.0, 0.0])
    annotation.set_line([20.0, 30.0, 80.0, 30.0])
    annotation.set_caption(True)
    annotation.set_contents("Hello")
    PDLineAppearanceHandler(annotation).generate_normal_appearance()
    body = _appearance_bytes(annotation)
    # Caption emit produces a BT / ET text block.
    assert b"BT" in body
    assert b"ET" in body


def test_line_handler_without_caption_skips_text_block() -> None:
    annotation = PDAnnotationLine()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_color([0.0, 0.0, 0.0])
    annotation.set_line([20.0, 30.0, 80.0, 30.0])
    PDLineAppearanceHandler(annotation).generate_normal_appearance()
    body = _appearance_bytes(annotation)
    assert b"BT" not in body


# ----------------------------------------------------------------------
# square / circle cloudy border
# ----------------------------------------------------------------------


def _border_effect_cloudy(intensity: float = 1.0) -> PDBorderEffectDictionary:
    be = PDBorderEffectDictionary()
    be.set_style(PDBorderEffectDictionary.STYLE_CLOUDY)
    be.set_intensity(intensity)
    return be


def test_square_handler_with_cloudy_border_emits_curves() -> None:
    annotation = PDAnnotationSquare()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_color([0.0, 0.0, 1.0])
    annotation.set_border_effect(_border_effect_cloudy(intensity=2.0))
    PDSquareAppearanceHandler(annotation).generate_normal_appearance()
    body = _appearance_bytes(annotation)
    # Cloudy border emits many Bezier curves.
    assert b"c" in body


def test_circle_handler_with_cloudy_border_emits_curves() -> None:
    annotation = PDAnnotationCircle()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_color([1.0, 0.0, 0.0])
    annotation.set_border_effect(_border_effect_cloudy(intensity=2.0))
    PDCircleAppearanceHandler(annotation).generate_normal_appearance()
    body = _appearance_bytes(annotation)
    assert b"c" in body


def test_square_handler_cloudy_zero_intensity_still_works() -> None:
    annotation = PDAnnotationSquare()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_color([0.0, 1.0, 0.0])
    annotation.set_border_effect(_border_effect_cloudy(intensity=0.0))
    PDSquareAppearanceHandler(annotation).generate_normal_appearance()
    body = _appearance_bytes(annotation)
    # Intensity 0 falls back to addRect.
    assert b"re" in body


# ----------------------------------------------------------------------
# highlight multiply blend
# ----------------------------------------------------------------------


def test_highlight_handler_emits_extgstate_for_multiply_blend() -> None:
    annotation = PDAnnotationHighlight()
    annotation.set_rectangle(PDRectangle(0.0, 0.0, 200.0, 50.0))
    annotation.set_color([1.0, 1.0, 0.0])
    annotation.set_quad_points([0.0, 0.0, 100.0, 0.0, 100.0, 20.0, 0.0, 20.0])
    PDHighlightAppearanceHandler(annotation).generate_normal_appearance()
    body = _appearance_bytes(annotation)
    # The extgstate dictionary application produces a /Name gs operator.
    assert b"gs" in body
    # A path is filled (curves + lines for the rounded quad).
    assert b"f" in body


def test_polygon_handler_with_cloudy_border_emits_curves() -> None:
    """Polygon + ``/BE /Style /C`` should run the cloudy-polygon path."""
    from pypdfbox.pdmodel.interactive.annotation.handlers import (
        PDPolygonAppearanceHandler,
    )
    from pypdfbox.pdmodel.interactive.annotation.pd_annotation_polygon import (
        PDAnnotationPolygon,
    )

    annotation = PDAnnotationPolygon()
    annotation.set_rectangle(PDRectangle(0.0, 0.0, 200.0, 200.0))
    annotation.set_color([0.0, 0.5, 0.0])
    # Triangle.
    annotation.set_vertices([20.0, 20.0, 180.0, 20.0, 100.0, 180.0])
    annotation.set_border_effect(_border_effect_cloudy(intensity=2.0))
    PDPolygonAppearanceHandler(annotation).generate_normal_appearance()
    body = _appearance_bytes(annotation)
    assert b"c" in body


def test_polygon_handler_without_cloudy_uses_plain_path() -> None:
    from pypdfbox.pdmodel.interactive.annotation.handlers import (
        PDPolygonAppearanceHandler,
    )
    from pypdfbox.pdmodel.interactive.annotation.pd_annotation_polygon import (
        PDAnnotationPolygon,
    )

    annotation = PDAnnotationPolygon()
    annotation.set_rectangle(PDRectangle(0.0, 0.0, 200.0, 200.0))
    annotation.set_color([0.0, 0.5, 0.0])
    annotation.set_vertices([20.0, 20.0, 180.0, 20.0, 100.0, 180.0])
    PDPolygonAppearanceHandler(annotation).generate_normal_appearance()
    body = _appearance_bytes(annotation)
    # Plain polygon emits moveto + lineto, no cloudy curves.
    assert b"m" in body
    assert b"l" in body


def test_highlight_handler_horizontal_quad_emits_curves() -> None:
    annotation = PDAnnotationHighlight()
    annotation.set_rectangle(PDRectangle(0.0, 0.0, 200.0, 50.0))
    annotation.set_color([1.0, 1.0, 0.0])
    # Upstream's horizontal-quad branch requires: x0==x4, y1==y3, x2==x6,
    # y5==y7 (left edge vertical, right edge vertical). PDF Reader's
    # actual quadpoint order is (x0,y0)=top-left, (x1,y1)=top-right,
    # (x2,y2)=bottom-left, (x3,y3)=bottom-right.
    annotation.set_quad_points(
        [0.0, 20.0, 100.0, 20.0, 0.0, 0.0, 100.0, 0.0]
    )
    PDHighlightAppearanceHandler(annotation).generate_normal_appearance()
    body = _appearance_bytes(annotation)
    assert b"c" in body
