from __future__ import annotations

from pypdfbox.cos import COSDictionary

__all__ = ["PDURIDictionary"]


class PDURIDictionary:
    """Document-level ``/URI`` dictionary (PDF 32000-1 §12.6.4.7).

    Mirrors ``org.apache.pdfbox.pdmodel.interactive.action.PDURIDictionary``.
    Holds the ``/Base`` entry — a string used as the base URI when
    resolving relative URIs in URI actions.
    """

    def __init__(self, dictionary: COSDictionary | None = None) -> None:
        self._dict: COSDictionary = (
            dictionary if dictionary is not None else COSDictionary()
        )

    # ---------- COS plumbing ----------

    def get_cos_object(self) -> COSDictionary:
        return self._dict

    # ---------- /Base ----------

    def get_base(self) -> str | None:
        """Return the base URI string from ``/Base`` or ``None`` when absent."""
        return self._dict.get_string("Base")

    def set_base(self, base: str | None) -> None:
        """Write ``/Base``. ``None`` removes the entry."""
        if base is None:
            from pypdfbox.cos import COSName

            self._dict.remove_item(COSName.get_pdf_name("Base"))
            return
        self._dict.set_string("Base", base)
