"""Typed wrapper for the catalog's ``/PageLayout`` name value.

Mirrors ``org.apache.pdfbox.pdmodel.PageLayout`` from upstream PDFBox 3.0.
The PDF name strings (``SinglePage``, ``OneColumn``, ...) are written to the
PDF dictionary verbatim, so the enum is backed by ``StrEnum`` — instances
compare equal to their underlying string value, which keeps callers that
still pass plain strings working without changes.
"""

from __future__ import annotations

from enum import StrEnum

from pypdfbox.cos import COSName


class PageLayout(StrEnum):
    """A name object specifying the page layout shall be used when the
    document is opened.

    See PDF 32000-1 §7.7.3.3 / Table 28.
    """

    #: Display one page at a time.
    SINGLE_PAGE = "SinglePage"

    #: Display the pages in one column.
    ONE_COLUMN = "OneColumn"

    #: Display the pages in two columns, with odd numbered pages on the left.
    TWO_COLUMN_LEFT = "TwoColumnLeft"

    #: Display the pages in two columns, with odd numbered pages on the right.
    TWO_COLUMN_RIGHT = "TwoColumnRight"

    #: Display the pages two at a time, with odd-numbered pages on the left.
    TWO_PAGE_LEFT = "TwoPageLeft"

    #: Display the pages two at a time, with odd-numbered pages on the right.
    TWO_PAGE_RIGHT = "TwoPageRight"

    @classmethod
    def from_string(cls, value: str) -> PageLayout:
        """Return the ``PageLayout`` whose PDF string value matches ``value``.

        Mirrors upstream ``PageLayout.fromString(String)`` — raises
        :class:`ValueError` (Python's analogue of ``IllegalArgumentException``)
        when no member matches.
        """
        for member in cls:
            if member.value == value:
                return member
        raise ValueError(value)

    def string_value(self) -> str:
        """Return the string value, as used in a PDF file. Mirrors
        upstream ``stringValue()``."""
        return self.value

    def to_cos_name(self) -> COSName:
        """Return the underlying name as a :class:`COSName`, ready to be
        stored on a :class:`COSDictionary`."""
        return COSName.get_pdf_name(self.value)


__all__ = ["PageLayout"]
