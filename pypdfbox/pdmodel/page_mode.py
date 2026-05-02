"""Typed wrapper for the catalog's ``/PageMode`` name value.

Mirrors ``org.apache.pdfbox.pdmodel.PageMode`` from upstream PDFBox 3.0.
The PDF name strings (``UseNone``, ``UseOutlines``, ...) are written to the
PDF dictionary verbatim, so the enum is backed by ``StrEnum`` — instances
compare equal to their underlying string value, which keeps callers that
still pass plain strings working without changes.
"""

from __future__ import annotations

from enum import StrEnum

from pypdfbox.cos import COSName


class PageMode(StrEnum):
    """A name object specifying how the document shall be displayed when
    opened.

    See PDF 32000-1 §7.7.3.3 / Table 28.
    """

    #: Neither the outline nor the thumbnails are displayed.
    USE_NONE = "UseNone"

    #: Show bookmarks when pdf is opened.
    USE_OUTLINES = "UseOutlines"

    #: Show thumbnails when pdf is opened.
    USE_THUMBS = "UseThumbs"

    #: Full screen mode with no menu bar, window controls.
    FULL_SCREEN = "FullScreen"

    #: Optional content group panel is visible when opened.
    USE_OPTIONAL_CONTENT = "UseOC"

    #: Attachments panel is visible.
    USE_ATTACHMENTS = "UseAttachments"

    @classmethod
    def from_string(cls, value: str) -> PageMode:
        """Return the ``PageMode`` whose PDF string value matches ``value``.

        Mirrors upstream ``PageMode.fromString(String)`` — raises
        :class:`ValueError` (Python's analogue of ``IllegalArgumentException``)
        when no member matches.
        """
        for member in cls:
            if member.value == value:
                return member
        raise ValueError(value)

    @classmethod
    def values(cls) -> list[PageMode]:
        """Return all members in declaration order.

        Mirrors Java's auto-generated ``MyEnum.values()`` static method;
        equivalent to ``list(PageMode)``.
        """
        return list(cls)

    def string_value(self) -> str:
        """Return the string value, as used in a PDF file. Mirrors
        upstream ``stringValue()``."""
        return self.value

    def to_cos_name(self) -> COSName:
        """Return the underlying name as a :class:`COSName`, ready to be
        stored on a :class:`COSDictionary`."""
        return COSName.get_pdf_name(self.value)


__all__ = ["PageMode"]
