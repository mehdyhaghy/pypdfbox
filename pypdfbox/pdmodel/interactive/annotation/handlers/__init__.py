"""Appearance handlers for the PDF interactive annotation classes.

Mirrors ``org.apache.pdfbox.pdmodel.interactive.annotation.handlers``.
Each ``PD*AppearanceHandler`` generates the ``/AP`` Form XObject content
stream for the corresponding annotation type. ``CloudyBorder`` is a
helper used by the polygon / circle / square handlers when the border
effect is ``/Cloudy``.
"""

from __future__ import annotations

from .annotation_border import AnnotationBorder
from .cloudy_border import CloudyBorder
from .pd_abstract_appearance_handler import PDAbstractAppearanceHandler
from .pd_appearance_handler import PDAppearanceHandler
from .pd_caret_appearance_handler import PDCaretAppearanceHandler
from .pd_circle_appearance_handler import PDCircleAppearanceHandler
from .pd_file_attachment_appearance_handler import (
    PDFileAttachmentAppearanceHandler,
)
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
