from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pypdfbox.cos import COSArray, COSDictionary, COSName

if TYPE_CHECKING:
    from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_destination import (
        PDDestination,
    )

_D: COSName = COSName.get_pdf_name("D")


class PDDocumentNameDestinationDictionary:
    """
    Catalog ``/Dests`` flat name→destination dictionary. Mirrors PDFBox
    ``PDDocumentNameDestinationDictionary``.

    This is the *legacy* simple-dict form of named destinations (PDF 1.1)
    that lives directly under the catalog or under the /Names dictionary
    as ``/Dests``. Contrast with ``PDDestinationNameTreeNode`` which is
    the proper name-tree form.
    """

    def __init__(
        self,
        dictionary: COSDictionary | None = None,
        document: Any | None = None,
    ) -> None:
        self._dict: COSDictionary = dictionary if dictionary is not None else COSDictionary()
        self._document = document

    # ---------- COS plumbing ----------

    def get_cos_object(self) -> COSDictionary:
        return self._dict

    def get_cos_dictionary(self) -> COSDictionary:
        return self._dict

    # ---------- destination lookup ----------

    def get_destination(self, name: str) -> PDDestination | None:
        from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_destination import (
            PDDestination,
        )

        item = self._dict.get_dictionary_object(name)
        if isinstance(item, COSArray):
            return PDDestination.create(item)
        if isinstance(item, COSDictionary):
            if item.get_dictionary_object(_D) is not None:
                return PDDestination.create(item.get_dictionary_object(_D))
        return None

    # ---------- enumeration / membership (Python-friendly extension) ----------

    def is_empty(self) -> bool:
        """``True`` when the dictionary contains no name → destination entries.

        Upstream PDFBox does not expose ``isEmpty()`` on
        ``PDDocumentNameDestinationDictionary`` directly; callers reach
        through ``getCOSObject().isEmpty()``. pypdfbox surfaces it on the
        wrapper for symmetry with ``COSDictionary.is_empty()``.
        """
        return self._dict.is_empty()

    def get_names(self) -> list[str]:
        """Return the destination name keys as a list of Python strings.

        Mirrors the enumeration capability that upstream callers reach by
        iterating ``getCOSObject().keySet()``. Names are returned in the
        underlying dictionary's insertion order.
        """
        return [key.get_name() for key in self._dict.key_set()]

    def __contains__(self, name: object) -> bool:
        """``True`` when a name → destination mapping exists for *name*.

        Faster than ``get_destination(name) is not None`` because no
        destination object is constructed; also distinguishes "key missing"
        from "key present but value is malformed" (the latter still returns
        ``None`` from ``get_destination``).
        """
        if not isinstance(name, (str, COSName)):
            return False
        return self._dict.contains_key(name)

    def __len__(self) -> int:
        """Number of name → destination entries in the dictionary."""
        return self._dict.size()


__all__ = ["PDDocumentNameDestinationDictionary"]
