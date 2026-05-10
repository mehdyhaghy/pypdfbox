from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import TYPE_CHECKING

from pypdfbox.cos import COSBase, COSDictionary, COSName

_LOG = logging.getLogger(__name__)

_O: COSName = COSName.get_pdf_name("O")
_R: COSName = COSName.get_pdf_name("R")

if TYPE_CHECKING:
    from .pd_structure_element import PDStructureElement


class PDAttributeObject:
    """
    A structure-element attribute object (``/A`` entry value). Mirrors
    PDFBox ``PDAttributeObject``.

    The factory dispatches known ``/O`` owners to their typed attribute
    subclasses and falls back to the generic wrapper for unknown owner
    dictionaries. Structure-element back-pointer helpers mirror the PDFBox
    add/remove/notify maintenance surface while using quiet no-ops when an
    attribute object is inspected outside a parent element.
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
        from .pd_default_attribute_object import PDDefaultAttributeObject

        return PDDefaultAttributeObject(dictionary)

    def get_cos_object(self) -> COSDictionary:
        return self._dictionary

    # ---------- /O owner ----------

    def get_owner(self) -> str | None:
        return self._dictionary.get_name(_O)

    def set_owner(self, owner: str) -> None:
        self._dictionary.set_name(_O, owner)

    def has_owner(self) -> bool:
        """Return ``True`` when the ``/O`` owner key is explicitly present."""
        return self._dictionary.contains_key(_O)

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

    def has_revision_number(self) -> bool:
        """Return ``True`` when ``/R`` is explicitly present.

        ``get_revision_number()`` defaults to ``0`` when ``/R`` is absent;
        this predicate lets callers distinguish an omitted revision from an
        explicitly stored ``0``.
        """
        return self._dictionary.contains_key(_R)

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

        When :meth:`set_structure_element` has been called, delegates to
        ``PDStructureElement.add_attribute(self)``. With no structure
        element bound the call is a debug-logged no-op (matches the
        upstream behaviour of throwing only when the back-pointer is
        missing — pypdfbox prefers the soft no-op for callers exploring
        attribute objects out-of-tree)."""
        if self._structure_element is None:
            _LOG.debug(
                "PDAttributeObject.add_to_structure_element() called with "
                "no structure-element back-pointer; ignoring"
            )
            return
        self._structure_element.add_attribute(self)

    def remove_from_structure_element(self) -> None:
        """Remove this attribute object from the parent structure element's
        ``/A`` array.

        When :meth:`set_structure_element` has been called, delegates to
        ``PDStructureElement.remove_attribute(self)`` and clears the
        back-pointer. With no structure element bound the call is a
        debug-logged no-op."""
        if self._structure_element is None:
            _LOG.debug(
                "PDAttributeObject.remove_from_structure_element() called "
                "with no structure-element back-pointer; ignoring"
            )
            return
        owner = self._structure_element
        owner.remove_attribute(self)
        # remove_attribute already clears the back-pointer when it removes
        # the attribute; defensively clear here too in case the attribute
        # wasn't actually present.
        self._structure_element = None

    # ---------- change notification ----------

    def notify_changed(self) -> None:
        """Notify the owning structure element that this attribute object
        changed. Mirrors upstream ``notifyChanged()`` (PDAttributeObject.java
        L185-L191).

        When :meth:`set_structure_element` has been called, delegates to
        ``PDStructureElement.attribute_changed(self)`` so the parent can
        bump the attribute's revision. With no structure element bound
        the call is a debug-logged no-op."""
        if self._structure_element is None:
            _LOG.debug(
                "PDAttributeObject.notify_changed() called with no "
                "structure-element back-pointer; ignoring"
            )
            return
        self._structure_element.attribute_changed(self)

    def notify_change(self) -> None:
        """Compatibility alias for :meth:`notify_changed`.

        ``notify_change`` predates the upstream-faithful ``notify_changed``
        snake_case form (which mirrors Java ``notifyChanged``). Existing
        call sites use this spelling — both names route through the same
        delegation path."""
        if self._structure_element is None:
            _LOG.debug(
                "PDAttributeObject.notify_change() called with no "
                "structure-element back-pointer; ignoring"
            )
            return
        self._structure_element.attribute_changed(self)

    def potentially_notify_changed(
        self, old_base: COSBase | None, new_base: COSBase | None
    ) -> None:
        """Fire :meth:`notify_changed` only when ``old_base`` differs from
        ``new_base``. Mirrors upstream ``potentiallyNotifyChanged`` (
        PDAttributeObject.java L156-L162) — guards the structure-element
        notification behind an equality check so no-op writes don't trigger
        spurious revisions."""
        if self.is_value_changed(old_base, new_base):
            self.notify_changed()

    @staticmethod
    def is_value_changed(
        old_value: COSBase | None, new_value: COSBase | None
    ) -> bool:
        """Return ``True`` when ``old_value`` and ``new_value`` differ.
        Mirrors upstream private helper ``isValueChanged`` (
        PDAttributeObject.java L172-L179): when ``old_value`` is ``None``
        the result is ``new_value is not None``; otherwise compare via
        equality."""
        if old_value is None:
            return new_value is not None
        return old_value != new_value

    # ---------- string formatting helpers (PDFBox parity) ----------

    @staticmethod
    def array_to_string(array: object) -> str:
        """Format a sequence as ``"[a, b, c]"``. Mirrors upstream
        ``PDAttributeObject.arrayToString(Object[])`` /
        ``arrayToString(float[])`` which both delegate to
        ``StringJoiner(", ", "[", "]")``."""
        if array is None:
            raise TypeError("array_to_string requires a sequence, got None")
        if not isinstance(array, Iterable):
            raise TypeError(
                "array_to_string requires a sequence, got "
                f"{type(array).__name__}"
            )
        return "[" + ", ".join(str(item) for item in array) + "]"

    def to_string(self) -> str:
        """Return the upstream ``toString()`` representation. Mirrors
        ``PDAttributeObject.toString()`` (PDAttributeObject.java L194-L197)
        which returns ``"O=" + owner``. Subclasses override ``__str__``
        to extend this with their typed attribute payload."""
        return str(self)

    def __str__(self) -> str:
        """Mirror upstream ``PDAttributeObject.toString()`` which returns
        ``"O=" + owner``. Subclasses extend this by appending their typed
        attributes when ``is_specified()`` reports them."""
        return f"O={self.get_owner()}"

    def __repr__(self) -> str:
        return f"O={self.get_owner()}"


__all__ = ["PDAttributeObject"]
