"""Smoke tests for the wave-1280 batch of ``PD*AppearanceHandler``
classes ported from ``org.apache.pdfbox.pdmodel.interactive.annotation.handlers``.

Each handler is exercised through:

* the ``__init__`` constructor (single-arg + document-arg overloads)
* a happy-path :meth:`generate_normal_appearance` against an annotation
  with the minimum fields populated
* the rollover / down hooks (which are no-ops or TODOs in upstream as
  well — we just verify they return ``None`` rather than raise)
"""

from __future__ import annotations

from pypdfbox.pdmodel.interactive.annotation.handlers import (
    PDAbstractAppearanceHandler,
    PDCircleAppearanceHandler,
    PDFileAttachmentAppearanceHandler,
    PDFreeTextAppearanceHandler,
    PDHighlightAppearanceHandler,
    PDInkAppearanceHandler,
    PDLineAppearanceHandler,
    PDLinkAppearanceHandler,
    PDPolygonAppearanceHandler,
    PDPolylineAppearanceHandler,
    PDSoundAppearanceHandler,
    PDSquareAppearanceHandler,
    PDSquigglyAppearanceHandler,
    PDStrikeoutAppearanceHandler,
    PDTextAppearanceHandler,
    PDUnderlineAppearanceHandler,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation import PDAnnotation
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_file_attachment import (
    PDAnnotationFileAttachment,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_free_text import (
    PDAnnotationFreeText,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_highlight import (
    PDAnnotationHighlight,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_ink import (
    PDAnnotationInk,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_line import (
    PDAnnotationLine,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_link import (
    PDAnnotationLink,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_polygon import (
    PDAnnotationPolygon,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_polyline import (
    PDAnnotationPolyline,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_sound import (
    PDAnnotationSound,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_square_circle import (
    PDAnnotationSquare,
    PDAnnotationSquareCircle,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_squiggly import (
    PDAnnotationSquiggly,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_strikeout import (
    PDAnnotationStrikeout,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_text import (
    PDAnnotationText,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_underline import (
    PDAnnotationUnderline,
)
from pypdfbox.pdmodel.pd_rectangle import PDRectangle

_RECT = (0.0, 0.0, 100.0, 50.0)


def _square() -> PDAnnotationSquareCircle:
    annotation = PDAnnotationSquare()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_color([0.0, 0.0, 1.0])
    return annotation


# ----------------------------------------------------------------------
# subclass relationship
# ----------------------------------------------------------------------


def test_every_handler_extends_abstract_base() -> None:
    for cls in (
        PDCircleAppearanceHandler,
        PDFileAttachmentAppearanceHandler,
        PDFreeTextAppearanceHandler,
        PDHighlightAppearanceHandler,
        PDInkAppearanceHandler,
        PDLineAppearanceHandler,
        PDLinkAppearanceHandler,
        PDPolygonAppearanceHandler,
        PDPolylineAppearanceHandler,
        PDSoundAppearanceHandler,
        PDSquareAppearanceHandler,
        PDSquigglyAppearanceHandler,
        PDStrikeoutAppearanceHandler,
        PDTextAppearanceHandler,
        PDUnderlineAppearanceHandler,
    ):
        assert issubclass(cls, PDAbstractAppearanceHandler)


# ----------------------------------------------------------------------
# square / circle / polygon
# ----------------------------------------------------------------------


def test_square_handler_generate_normal_appearance_writes_stream() -> None:
    annotation = _square()
    handler = PDSquareAppearanceHandler(annotation)
    handler.generate_normal_appearance()
    ap = annotation.get_appearance_dictionary()
    assert ap is not None
    assert ap.get_normal_appearance() is not None


def test_circle_handler_generate_normal_appearance_writes_stream() -> None:
    annotation = _square()
    handler = PDCircleAppearanceHandler(annotation)
    handler.generate_normal_appearance()
    assert annotation.get_appearance_dictionary() is not None


def test_polygon_handler_generate_normal_appearance_writes_stream() -> None:
    annotation = PDAnnotationPolygon()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_color([1.0, 0.0, 0.0])
    annotation.set_vertices([0.0, 0.0, 50.0, 50.0, 100.0, 0.0])
    handler = PDPolygonAppearanceHandler(annotation)
    handler.generate_normal_appearance()
    assert annotation.get_appearance_dictionary() is not None


def test_polyline_handler_generate_normal_appearance_writes_stream() -> None:
    annotation = PDAnnotationPolyline()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_color([1.0, 0.0, 0.0])
    annotation.set_vertices([0.0, 0.0, 50.0, 50.0, 100.0, 0.0])
    handler = PDPolylineAppearanceHandler(annotation)
    handler.generate_normal_appearance()
    assert annotation.get_appearance_dictionary() is not None


def test_polyline_handler_skips_when_no_vertices() -> None:
    annotation = PDAnnotationPolyline()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_color([1.0, 0.0, 0.0])
    handler = PDPolylineAppearanceHandler(annotation)
    handler.generate_normal_appearance()
    assert annotation.get_appearance_dictionary() is None


# ----------------------------------------------------------------------
# line / link
# ----------------------------------------------------------------------


def test_line_handler_generate_normal_appearance_writes_stream() -> None:
    annotation = PDAnnotationLine()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_color([0.0, 0.0, 0.0])
    annotation.set_line([0.0, 0.0, 100.0, 50.0])
    handler = PDLineAppearanceHandler(annotation)
    handler.generate_normal_appearance()
    assert annotation.get_appearance_dictionary() is not None


def test_link_handler_generate_normal_appearance_writes_stream() -> None:
    annotation = PDAnnotationLink()
    annotation.set_rectangle(PDRectangle(*_RECT))
    handler = PDLinkAppearanceHandler(annotation)
    handler.generate_normal_appearance()
    assert annotation.get_appearance_dictionary() is not None


def test_link_handler_skips_when_no_rect() -> None:
    annotation = PDAnnotationLink()
    handler = PDLinkAppearanceHandler(annotation)
    handler.generate_normal_appearance()
    assert annotation.get_appearance_dictionary() is None


# ----------------------------------------------------------------------
# ink / sound / file_attachment
# ----------------------------------------------------------------------


def test_ink_handler_skips_when_no_color() -> None:
    annotation = PDAnnotationInk()
    annotation.set_rectangle(PDRectangle(*_RECT))
    handler = PDInkAppearanceHandler(annotation)
    handler.generate_normal_appearance()
    assert annotation.get_appearance_dictionary() is None


def test_sound_handler_is_complete_noop() -> None:
    handler = PDSoundAppearanceHandler(PDAnnotationSound())
    # Upstream is "TODO to be implemented" for all three methods; we
    # mirror that. None returned means the annotation is left untouched.
    handler.generate_normal_appearance()
    handler.generate_rollover_appearance()
    handler.generate_down_appearance()


def test_file_attachment_handler_paperclip_writes_stream() -> None:
    annotation = PDAnnotationFileAttachment()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_attachment_name("Paperclip")
    handler = PDFileAttachmentAppearanceHandler(annotation)
    handler.generate_normal_appearance()
    assert annotation.get_appearance_dictionary() is not None


# ----------------------------------------------------------------------
# text markup family
# ----------------------------------------------------------------------


def test_strikeout_handler_generate_normal_appearance_writes_stream() -> None:
    annotation = PDAnnotationStrikeout()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_color([1.0, 0.0, 0.0])
    annotation.set_quad_points(
        [0.0, 0.0, 100.0, 0.0, 100.0, 20.0, 0.0, 20.0]
    )
    handler = PDStrikeoutAppearanceHandler(annotation)
    handler.generate_normal_appearance()
    assert annotation.get_appearance_dictionary() is not None


def test_underline_handler_generate_normal_appearance_writes_stream() -> None:
    annotation = PDAnnotationUnderline()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_color([1.0, 0.0, 0.0])
    annotation.set_quad_points(
        [0.0, 0.0, 100.0, 0.0, 100.0, 20.0, 0.0, 20.0]
    )
    handler = PDUnderlineAppearanceHandler(annotation)
    handler.generate_normal_appearance()
    assert annotation.get_appearance_dictionary() is not None


def test_squiggly_handler_generate_normal_appearance_writes_stream() -> None:
    annotation = PDAnnotationSquiggly()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_color([1.0, 0.0, 0.0])
    annotation.set_quad_points(
        [0.0, 0.0, 100.0, 0.0, 100.0, 20.0, 0.0, 20.0]
    )
    handler = PDSquigglyAppearanceHandler(annotation)
    handler.generate_normal_appearance()
    assert annotation.get_appearance_dictionary() is not None


def test_highlight_handler_generate_normal_appearance_writes_stream() -> None:
    annotation = PDAnnotationHighlight()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_color([1.0, 1.0, 0.0])
    annotation.set_quad_points(
        [0.0, 0.0, 100.0, 0.0, 100.0, 20.0, 0.0, 20.0]
    )
    handler = PDHighlightAppearanceHandler(annotation)
    handler.generate_normal_appearance()
    assert annotation.get_appearance_dictionary() is not None


# ----------------------------------------------------------------------
# free text / text
# ----------------------------------------------------------------------


def test_free_text_handler_generate_normal_appearance_writes_stream() -> None:
    annotation = PDAnnotationFreeText()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_color([0.0, 0.0, 0.0])
    handler = PDFreeTextAppearanceHandler(annotation)
    handler.generate_normal_appearance()
    assert annotation.get_appearance_dictionary() is not None


def test_text_handler_dispatches_on_supported_name() -> None:
    annotation = PDAnnotationText()
    annotation.set_rectangle(PDRectangle(0.0, 0.0, 18.0, 20.0))
    annotation.set_color([1.0, 1.0, 0.0])
    annotation.set_name(PDAnnotationText.NAME_NOTE)
    handler = PDTextAppearanceHandler(annotation)
    handler.generate_normal_appearance()
    assert annotation.get_appearance_dictionary() is not None


def test_text_handler_skips_unsupported_name() -> None:
    annotation = PDAnnotationText()
    annotation.set_rectangle(PDRectangle(0.0, 0.0, 18.0, 20.0))
    annotation.set_name("Bogus")
    handler = PDTextAppearanceHandler(annotation)
    handler.generate_normal_appearance()
    assert annotation.get_appearance_dictionary() is None


def test_text_handler_supported_names_contains_note() -> None:
    assert "Note" in PDTextAppearanceHandler.SUPPORTED_NAMES


# ----------------------------------------------------------------------
# rollover / down hooks
# ----------------------------------------------------------------------


def test_rollover_and_down_hooks_return_none_everywhere() -> None:
    for cls, annotation in (
        (PDCircleAppearanceHandler, _square()),
        (PDSquareAppearanceHandler, _square()),
        (PDPolygonAppearanceHandler, PDAnnotationPolygon()),
        (PDPolylineAppearanceHandler, PDAnnotationPolyline()),
        (PDLineAppearanceHandler, PDAnnotationLine()),
        (PDLinkAppearanceHandler, PDAnnotationLink()),
        (PDInkAppearanceHandler, PDAnnotationInk()),
        (PDFileAttachmentAppearanceHandler, PDAnnotationFileAttachment()),
        (PDFreeTextAppearanceHandler, PDAnnotationFreeText()),
        (PDHighlightAppearanceHandler, PDAnnotationHighlight()),
        (PDStrikeoutAppearanceHandler, PDAnnotationStrikeout()),
        (PDUnderlineAppearanceHandler, PDAnnotationUnderline()),
        (PDSquigglyAppearanceHandler, PDAnnotationSquiggly()),
        (PDTextAppearanceHandler, PDAnnotationText()),
        (PDSoundAppearanceHandler, PDAnnotationSound()),
    ):
        handler = cls(annotation)
        assert handler.generate_rollover_appearance() is None
        assert handler.generate_down_appearance() is None


# ----------------------------------------------------------------------
# constructor parity — document arg accepted
# ----------------------------------------------------------------------


def test_handlers_accept_document_arg() -> None:
    handler = PDCircleAppearanceHandler(_square(), document=None)
    assert handler.get_document() is None


def test_handlers_reject_wrong_annotation_type_silently() -> None:
    # generate_normal_appearance should no-op when the annotation isn't
    # the expected subtype.
    PDCircleAppearanceHandler(PDAnnotation()).generate_normal_appearance()
    PDLineAppearanceHandler(PDAnnotation()).generate_normal_appearance()
