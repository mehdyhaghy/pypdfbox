from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName

from .pd_outline_node import PDOutlineNode

_TYPE: COSName = COSName.TYPE  # type: ignore[attr-defined]
_OUTLINES: COSName = COSName.get_pdf_name("Outlines")


class PDDocumentOutline(PDOutlineNode):
    """
    Document-level outline root. Mirrors
    ``org.apache.pdfbox.pdmodel.interactive.documentnavigation.outline.PDDocumentOutline``.

    A blank outline carries ``/Type /Outlines``; existing dictionaries
    are wrapped in place.
    """

    def __init__(self, dictionary: COSDictionary | None = None) -> None:
        super().__init__(dictionary)
        if self._dictionary.get_dictionary_object(_TYPE) is None:
            self._dictionary.set_item(_TYPE, _OUTLINES)


__all__ = ["PDDocumentOutline"]
