from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from pypdfbox.cos import COSDictionary, COSName

_LOG = logging.getLogger(__name__)

_O: COSName = COSName.get_pdf_name("O")
_R: COSName = COSName.get_pdf_name("R")

if TYPE_CHECKING:
    from .pd_structure_element import PDStructureElement


class PDAttributeObject:
    """
    A structure-element attribute object (``/A`` entry value). Mirrors
    PDFBox ``PDAttributeObject``.

    Lite surface: typed owner subclasses (``PDLayoutAttributeObject``,
    ``PDListAttributeObject``, ``PDPrintFieldAttributeObject``,
    ``PDTableAttributeObject``, ``PDExportFormatAttributeObject``,
    ``PDUserAttributeObject``, ``PDDefaultAttributeObject``) and the
    structure-element change-notification plumbing are deferred. The
    factory currently wraps every dictionary as a generic
    ``PDAttributeObject``.
    """

    def __init__(self, dictionary: COSDictionary | None = None) -> None:
        self._dictionary: COSDictionary = (
            dictionary if dictionary is not None else COSDictionary()
        )
        # Lite back-pointer to the owning structure element. Upstream
        # PDFBox carries this through the constructor + add/remove helpers
        # so notify_change() can locate the parent. We expose set/get
        # accessors and default to None.
        self._structure_element: PDStructureElement | None = None

    @staticmethod
    def create(dictionary: COSDictionary) -> PDAttributeObject:
        if not isinstance(dictionary, COSDictionary):
            raise TypeError(
                f"PDAttributeObject.create expects COSDictionary, got "
                f"{type(dictionary).__name__}"
            )
        # Local imports avoid a circular import (taggedpdf -> logicalstructure).
        from pypdfbox.pdmodel.documentinterchange.taggedpdf import (
            PDExportFormatAttributeObject,
            PDLayoutAttributeObject,
            PDListAttributeObject,
            PDPrintFieldAttributeObject,
            PDTableAttributeObject,
            PDUserAttributeObject,
        )

        owner = dictionary.get_name(_O)
        if owner == PDLayoutAttributeObject.OWNER:
            return PDLayoutAttributeObject(dictionary)
        if owner == PDListAttributeObject.OWNER:
            return PDListAttributeObject(dictionary)
        if owner == PDPrintFieldAttributeObject.OWNER:
            return PDPrintFieldAttributeObject(dictionary)
        if owner == PDTableAttributeObject.OWNER:
            return PDTableAttributeObject(dictionary)
        if owner in PDExportFormatAttributeObject._VALID_OWNERS:
            return PDExportFormatAttributeObject(dictionary)
        if owner == PDUserAttributeObject.OWNER:
            return PDUserAttributeObject(dictionary)
        return PDAttributeObject(dictionary)

    def get_cos_object(self) -> COSDictionary:
        return self._dictionary

    # ---------- /O owner ----------

    def get_owner(self) -> str | None:
        return self._dictionary.get_name(_O)

    def set_owner(self, owner: str) -> None:
        self._dictionary.set_name(_O, owner)

    def is_empty(self) -> bool:
        return self._dictionary.size() == 1 and self.get_owner() is not None

    # ---------- /R revision number ----------

    def get_revision_number(self) -> int:
        """Return the ``/R`` revision number; defaults to ``0`` when absent.

        Mirrors upstream ``PDAttributeObject.getRevisionNumber()``."""
        return self._dictionary.get_int(_R, 0)

    def set_revision_number(self, revision_number: int) -> None:
        """Write ``/R``. Upstream rejects negative values with
        ``IllegalArgumentException``; we mirror that as ``ValueError``."""
        if revision_number < 0:
            raise ValueError("The revision number shall be > -1")
        self._dictionary.set_int(_R, revision_number)

    # ---------- structure-element back-pointer ----------

    def get_structure_element(self) -> PDStructureElement | None:
        """Return the owning structure element, or ``None`` if unset.

        Lite surface: upstream wires this through constructors + add/remove
        helpers so ``notify_change()`` can locate the parent. Here we just
        expose a stored back-pointer."""
        return self._structure_element

    def set_structure_element(self, structure_element: PDStructureElement | None) -> None:
        """Store the owning structure element back-pointer."""
        self._structure_element = structure_element

    # ---------- structure-element /A maintenance helpers ----------

    def add_to_structure_element(self) -> None:
        """Add this attribute object to the parent structure element's
        ``/A`` array.

        Lite stub: upstream rebuilds the parent's ``Revisions[PDAttributeObject]``
        and writes ``/A`` back. We log + no-op until the typed parent-chain
        machinery lands (see ``CHANGES.md``)."""
        _LOG.debug(
            "PDAttributeObject.add_to_structure_element() is a no-op stub "
            "(structure-element /A maintenance deferred)"
        )

    def remove_from_structure_element(self) -> None:
        """Remove this attribute object from the parent structure element's
        ``/A`` array.

        Lite stub: see ``add_to_structure_element``."""
        _LOG.debug(
            "PDAttributeObject.remove_from_structure_element() is a no-op "
            "stub (structure-element /A maintenance deferred)"
        )

    # ---------- change notification ----------

    def notify_change(self) -> None:
        """Notify the owning structure element that this attribute object
        changed.

        Lite stub: upstream calls back into the parent so the structure
        element can record an attribute revision. Deferred per
        ``CHANGES.md`` — this no-ops + logs at debug level."""
        _LOG.debug(
            "PDAttributeObject.notify_change() is a no-op stub (structure-"
            "element change notification deferred)"
        )

    def __repr__(self) -> str:
        return f"O={self.get_owner()}"


__all__ = ["PDAttributeObject"]
