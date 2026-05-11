from __future__ import annotations

from typing import TYPE_CHECKING

from .xref_trailer_resolver import XrefType

if TYPE_CHECKING:
    from pypdfbox.cos.cos_dictionary import COSDictionary
    from pypdfbox.cos.cos_object_key import COSObjectKey


class XrefTrailerObj:
    """One xref/trailer fragment collected during parsing.

    Mirrors upstream
    ``org.apache.pdfbox.pdfparser.XrefTrailerResolver.XrefTrailerObj``
    (a private static nested class). Hoisted to a top-level class here
    so pypdfbox can be referenced by name from external callers; the
    upstream resolver keeps it inner.

    Each instance pairs the trailer dictionary that closes a section
    with the ``(object key → byte offset)`` map of the section's
    entries.
    """

    def __init__(self) -> None:
        self.trailer: COSDictionary | None = None
        self.xref_type: XrefType = XrefType.TABLE
        self.xref_table: dict[COSObjectKey, int] = {}

    def reset(self) -> None:
        """Clear the xref table entries.

        Mirrors upstream ``XrefTrailerObj.reset`` (Java line 77). Used
        when a parsing pass has to be retried after a recoverable
        error.
        """
        self.xref_table.clear()
