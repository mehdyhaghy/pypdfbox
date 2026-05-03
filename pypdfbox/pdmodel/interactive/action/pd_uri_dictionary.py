from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName, COSString

__all__ = ["PDURIDictionary"]

_BASE: COSName = COSName.get_pdf_name("Base")


class PDURIDictionary:
    """Document-level ``/URI`` dictionary (PDF 32000-1 §12.6.4.7).

    Mirrors ``org.apache.pdfbox.pdmodel.interactive.action.PDURIDictionary``.
    Holds the ``/Base`` entry — a string used as the base URI when
    resolving relative URIs in URI actions.
    """

    # Dictionary key constant — upstream-parity public static for the
    # single defined entry of the URI dictionary (PDF 32000-1 §12.6.4.7
    # Table 207).
    BASE: str = "Base"

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
            self._dict.remove_item(_BASE)
            return
        self._dict.set_string("Base", base)

    # ---------- Predicate / typed-accessor helpers ----------

    def has_base(self) -> bool:
        """Return ``True`` iff a ``/Base`` entry is present (regardless of
        whether it decodes to an empty string). Lets callers distinguish
        "absent" from "explicitly empty" without re-fetching the entry."""
        return self._dict.contains_key(_BASE)

    def get_base_as_cos_string(self) -> COSString | None:
        """Return the raw ``/Base`` :class:`COSString`, or ``None`` when
        the entry is absent or not a ``COSString``. Useful for inspecting
        the underlying bytes / encoding without going through the string
        decode in :meth:`get_base`."""
        value = self._dict.get_dictionary_object(_BASE)
        if isinstance(value, COSString):
            return value
        return None

    def is_empty(self) -> bool:
        """Return ``True`` when the URI dictionary holds no entries.
        Producers that find an empty URI dictionary can elide the
        ``/URI`` entry from the catalog entirely."""
        return self._dict.size() == 0

    def __repr__(self) -> str:
        base = self.get_base()
        if base is None:
            return "PDURIDictionary(Base=<unset>)"
        return f"PDURIDictionary(Base={base!r})"
