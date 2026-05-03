from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName

_MARKED: COSName = COSName.get_pdf_name("Marked")
_USER_PROPERTIES: COSName = COSName.get_pdf_name("UserProperties")
_SUSPECTS: COSName = COSName.get_pdf_name("Suspects")


class PDMarkInfo:
    """
    The MarkInfo dictionary referenced by the document catalog
    (``/MarkInfo``). Mirrors PDFBox ``PDMarkInfo``.
    """

    def __init__(self, dictionary: COSDictionary | None = None) -> None:
        self._dictionary: COSDictionary = (
            dictionary if dictionary is not None else COSDictionary()
        )

    def get_cos_object(self) -> COSDictionary:
        return self._dictionary

    def is_marked(self) -> bool:
        return self._dictionary.get_boolean(_MARKED, False)

    def set_marked(self, value: bool) -> None:
        self._dictionary.set_boolean(_MARKED, value)

    def is_user_properties(self) -> bool:
        return self._dictionary.get_boolean(_USER_PROPERTIES, False)

    def uses_user_properties(self) -> bool:
        # Upstream-named accessor (PDFBox: usesUserProperties()).
        return self.is_user_properties()

    def set_user_properties(self, value: bool) -> None:
        self._dictionary.set_boolean(_USER_PROPERTIES, value)

    def is_suspects(self) -> bool:
        return self._dictionary.get_boolean(_SUSPECTS, False)

    def is_suspect(self) -> bool:
        # Upstream-named accessor (PDFBox: isSuspect()); reads the same
        # ``/Suspects`` entry per PDF 32000-1 Table 321.
        return self.is_suspects()

    def set_suspects(self, value: bool) -> None:
        self._dictionary.set_boolean(_SUSPECTS, value)

    def set_suspect(self, value: bool) -> None:
        # Upstream-named mutator (PDFBox: setSuspect()). Upstream's
        # implementation always writes ``false`` regardless of the argument
        # (a longstanding bug); we write the actual value.
        self.set_suspects(value)

    # ---------- pypdfbox enrichments ----------
    # The PDFBox 3.0 surface only exposes the three boolean getter/setter
    # pairs above. The helpers below distinguish "key absent (default)"
    # from "key explicitly set" and let callers express intent without
    # spelling out boolean literals — useful when round-tripping a
    # ``/MarkInfo`` dictionary that was written by another producer.

    # ---------- presence predicates ----------

    def has_marked(self) -> bool:
        """``True`` when ``/Marked`` is explicitly present in the
        dictionary (regardless of value). PDF 32000-1 Table 321 makes
        ``/Marked`` optional with default ``false``; this predicate lets
        callers tell "explicitly false" apart from "absent → default false"
        without grovelling through the underlying ``COSDictionary``."""
        return self._dictionary.contains_key(_MARKED)

    def has_user_properties(self) -> bool:
        """``True`` when ``/UserProperties`` is explicitly present
        (regardless of value)."""
        return self._dictionary.contains_key(_USER_PROPERTIES)

    def has_suspects(self) -> bool:
        """``True`` when ``/Suspects`` is explicitly present
        (regardless of value)."""
        return self._dictionary.contains_key(_SUSPECTS)

    # ---------- clear helpers ----------

    def clear_marked(self) -> None:
        """Remove the ``/Marked`` entry. Effectively reverts the entry to
        its spec default (``false``) without writing an explicit ``false``
        back to the file."""
        self._dictionary.remove_item(_MARKED)

    def clear_user_properties(self) -> None:
        """Remove the ``/UserProperties`` entry, reverting to its spec
        default (``false``)."""
        self._dictionary.remove_item(_USER_PROPERTIES)

    def clear_suspects(self) -> None:
        """Remove the ``/Suspects`` entry, reverting to its spec default
        (``false``)."""
        self._dictionary.remove_item(_SUSPECTS)

    # ---------- aggregate / convenience ----------

    def is_tagged(self) -> bool:
        """Convenience alias for :meth:`is_marked`. PDF 32000-1 §14.7
        introduces the term *Tagged PDF* for documents that set
        ``/Marked = true``; many call-sites read better with the broader
        spec terminology, so we surface both names against the same
        underlying entry."""
        return self.is_marked()

    def is_empty(self) -> bool:
        """Return ``True`` when the underlying ``/MarkInfo`` dictionary
        holds no entries (none of ``/Marked``, ``/UserProperties``, or
        ``/Suspects`` were written). A useful gate for serializers that
        elide empty optional dictionaries from the document catalog."""
        return self._dictionary.is_empty()

    def __repr__(self) -> str:
        return (
            f"PDMarkInfo(marked={self.is_marked()}, "
            f"user_properties={self.is_user_properties()}, "
            f"suspects={self.is_suspects()})"
        )


__all__ = ["PDMarkInfo"]
