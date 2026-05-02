from __future__ import annotations

from pypdfbox.cos import COSBase, COSDictionary, COSName

from .pd_action import PDAction

_DP: COSName = COSName.get_pdf_name("Dp")


class PDActionGoToDp(PDAction):
    """Go-To Document Part action. Mirrors the PDF 2.0 ``GoToDp`` action
    type from ISO 32000-2 §12.6.4.4 / Table 200.

    The action carries a single typed entry, ``/Dp``, which is an indirect
    reference to a document part dictionary inside the catalog's
    ``/DPartRoot`` document-part tree. The viewer scrolls to the first
    page of the referenced document part on activation.

    Note: not present in upstream Apache PDFBox 3.0.x; added here for
    PDF 2.0 parity. Recorded in ``CHANGES.md``.
    """

    SUB_TYPE = "GoToDp"

    def __init__(self, action: COSDictionary | None = None) -> None:
        super().__init__(action, None if action is not None else self.SUB_TYPE)

    # ---------- /Dp ----------

    def get_document_part(self) -> COSBase | None:
        """Return the raw ``/Dp`` document-part dictionary entry, or
        ``None`` when absent."""
        return self._action.get_dictionary_object(_DP)

    def set_document_part(self, document_part: COSBase | None) -> None:
        """Write the ``/Dp`` entry. ``None`` removes the entry; otherwise
        the value is stored as-is (typically an indirect reference to a
        document part dictionary in ``/DPartRoot``)."""
        if document_part is None:
            self._action.remove_item(_DP)
            return
        self._action.set_item(_DP, document_part)

    # PDFBox-style raw aliases — `/Dp` is referenced by its raw key name
    # in some upstream patches and downstream tooling. Provide both for
    # convenience.
    def get_dp(self) -> COSBase | None:
        """Raw alias of :meth:`get_document_part`. Mirrors the entry key."""
        return self.get_document_part()

    def set_dp(self, document_part: COSBase | None) -> None:
        """Raw alias of :meth:`set_document_part`. Mirrors the entry key."""
        self.set_document_part(document_part)

    def get_document_part_dictionary(self) -> COSDictionary | None:
        """Typed accessor for the ``/Dp`` document-part dictionary. Returns
        the entry as a :class:`COSDictionary` when present and of that
        type, otherwise ``None`` (including when the entry is absent or is
        another COS object that did not resolve to a dictionary)."""
        entry = self._action.get_dictionary_object(_DP)
        if isinstance(entry, COSDictionary):
            return entry
        return None


__all__ = ["PDActionGoToDp"]
