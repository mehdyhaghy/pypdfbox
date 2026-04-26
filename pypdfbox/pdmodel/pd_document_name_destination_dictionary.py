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


__all__ = ["PDDocumentNameDestinationDictionary"]
