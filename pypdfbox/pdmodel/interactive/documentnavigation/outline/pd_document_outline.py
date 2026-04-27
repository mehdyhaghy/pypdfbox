from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName

from .pd_outline_node import PDOutlineNode

_TYPE: COSName = COSName.TYPE  # type: ignore[attr-defined]
_OUTLINES: COSName = COSName.get_pdf_name("Outlines")
_COUNT: COSName = COSName.COUNT  # type: ignore[attr-defined]


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

    # ---------- open / closed (root defaults to open) ----------

    def is_open(self) -> bool:
        """Return ``True`` when the outline root is open. Per PDF
        32000-1:2008 the root is open when ``/Count`` is absent or
        non-negative; closed only when ``/Count`` is negative.

        Mirrors upstream ``PDDocumentOutline#isOpen``."""
        if self._dictionary.get_dictionary_object(_COUNT) is None:
            return True
        return self.get_open_count() >= 0

    def open_node(self) -> None:
        """Open the outline root. No-op when already open."""
        if self.is_open():
            return
        # /Count is negative here — flip its sign.
        self.set_open_count(-self.get_open_count())

    def close_node(self) -> None:
        """Close the outline root. No-op when already closed."""
        if not self.is_open():
            return
        # /Count is >= 0 (or absent). Negate; absent / 0 ⇒ store 0
        # (no descendants). Mirrors upstream behavior of toggling sign.
        self.set_open_count(-self.get_open_count())


__all__ = ["PDDocumentOutline"]
