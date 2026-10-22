"""Appearance handlers for the PDF interactive annotation classes.

Mirrors ``org.apache.pdfbox.pdmodel.interactive.annotation.handlers``.
Each ``PD*AppearanceHandler`` generates the ``/AP`` Form XObject content
stream for the corresponding annotation type. ``CloudyBorder`` is a
helper used by the polygon / circle / square handlers when the border
effect is ``/Cloudy``.
"""

from typing import TYPE_CHECKING

from pypdfbox._lazy_exports import attach as _attach

if TYPE_CHECKING:
    from .annotation_border import AnnotationBorder
    from .cloudy_border import CloudyBorder
    from .pd_abstract_appearance_handler import PDAbstractAppearanceHandler
    from .pd_appearance_handler import PDAppearanceHandler
    from .pd_caret_appearance_handler import PDCaretAppearanceHandler
    from .pd_circle_appearance_handler import PDCircleAppearanceHandler
    from .pd_file_attachment_appearance_handler import PDFileAttachmentAppearanceHandler
    from .pd_free_text_appearance_handler import PDFreeTextAppearanceHandler
    from .pd_highlight_appearance_handler import PDHighlightAppearanceHandler
    from .pd_ink_appearance_handler import PDInkAppearanceHandler
    from .pd_line_appearance_handler import PDLineAppearanceHandler
    from .pd_link_appearance_handler import PDLinkAppearanceHandler
    from .pd_polygon_appearance_handler import PDPolygonAppearanceHandler
    from .pd_polyline_appearance_handler import PDPolylineAppearanceHandler
    from .pd_sound_appearance_handler import PDSoundAppearanceHandler
    from .pd_square_appearance_handler import PDSquareAppearanceHandler
    from .pd_squiggly_appearance_handler import PDSquigglyAppearanceHandler
    from .pd_strikeout_appearance_handler import PDStrikeoutAppearanceHandler
    from .pd_text_appearance_handler import PDTextAppearanceHandler
    from .pd_underline_appearance_handler import PDUnderlineAppearanceHandler

__getattr__, __dir__ = _attach(
    __name__,
    {
        "AnnotationBorder": ".annotation_border",
        "CloudyBorder": ".cloudy_border",
        "PDAbstractAppearanceHandler": ".pd_abstract_appearance_handler",
        "PDAppearanceHandler": ".pd_appearance_handler",
        "PDCaretAppearanceHandler": ".pd_caret_appearance_handler",
        "PDCircleAppearanceHandler": ".pd_circle_appearance_handler",
        "PDFileAttachmentAppearanceHandler": ".pd_file_attachment_appearance_handler",
        "PDFreeTextAppearanceHandler": ".pd_free_text_appearance_handler",
        "PDHighlightAppearanceHandler": ".pd_highlight_appearance_handler",
        "PDInkAppearanceHandler": ".pd_ink_appearance_handler",
        "PDLineAppearanceHandler": ".pd_line_appearance_handler",
        "PDLinkAppearanceHandler": ".pd_link_appearance_handler",
        "PDPolygonAppearanceHandler": ".pd_polygon_appearance_handler",
        "PDPolylineAppearanceHandler": ".pd_polyline_appearance_handler",
        "PDSoundAppearanceHandler": ".pd_sound_appearance_handler",
        "PDSquareAppearanceHandler": ".pd_square_appearance_handler",
        "PDSquigglyAppearanceHandler": ".pd_squiggly_appearance_handler",
        "PDStrikeoutAppearanceHandler": ".pd_strikeout_appearance_handler",
        "PDTextAppearanceHandler": ".pd_text_appearance_handler",
        "PDUnderlineAppearanceHandler": ".pd_underline_appearance_handler",
    },
)

__all__ = [
    "AnnotationBorder",
    "CloudyBorder",
    "PDAbstractAppearanceHandler",
    "PDAppearanceHandler",
    "PDCaretAppearanceHandler",
    "PDCircleAppearanceHandler",
    "PDFileAttachmentAppearanceHandler",
    "PDFreeTextAppearanceHandler",
    "PDHighlightAppearanceHandler",
    "PDInkAppearanceHandler",
    "PDLineAppearanceHandler",
    "PDLinkAppearanceHandler",
    "PDPolygonAppearanceHandler",
    "PDPolylineAppearanceHandler",
    "PDSoundAppearanceHandler",
    "PDSquareAppearanceHandler",
    "PDSquigglyAppearanceHandler",
    "PDStrikeoutAppearanceHandler",
    "PDTextAppearanceHandler",
    "PDUnderlineAppearanceHandler",
]
