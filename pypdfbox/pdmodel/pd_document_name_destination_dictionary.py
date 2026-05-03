from __future__ import annotations

from collections.abc import Iterator
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

    def set_destination(
        self,
        name: str,
        destination: PDDestination | COSArray | COSDictionary | None,
    ) -> None:
        """Assign or clear the destination mapped to *name*.

        Accepts a :class:`PDDestination` wrapper (its ``COSArray`` payload
        is stored directly per the PDF 1.1 spec form), a raw ``COSArray``
        explicit destination, a ``COSDictionary`` already shaped as
        ``{/D <array>}``, or ``None`` to remove the entry. Mirrors the
        accepted forms returned by :meth:`get_destination`.

        Upstream PDFBox does not expose a setter on this wrapper — the
        original Java is read-only and callers mutate ``getCOSObject()``
        directly. pypdfbox surfaces a setter for symmetry with the other
        ``/Dests`` writer (``PDDestinationNameTreeNode.set_value``) and
        to keep the helper round-trippable with :meth:`get_destination`.
        """
        if destination is None:
            self._dict.remove_item(name)
            return
        if isinstance(destination, (COSArray, COSDictionary)):
            self._dict.set_item(name, destination)
            return
        # PDDestination wrapper — store its COS payload.
        cos = destination.get_cos_object()
        if not isinstance(cos, (COSArray, COSDictionary)):
            raise TypeError(
                "destination.get_cos_object() must yield a COSArray or COSDictionary; "
                f"got {type(cos).__name__}"
            )
        self._dict.set_item(name, cos)

    def remove_destination(self, name: str) -> None:
        """Drop the entry mapped to *name* if present; no-op otherwise.

        Equivalent to ``set_destination(name, None)``. Upstream PDFBox
        does not expose a removal helper on this wrapper; pypdfbox adds
        it for symmetry with :meth:`set_destination`.
        """
        self._dict.remove_item(name)

    # ---------- enumeration / membership (Python-friendly extension) ----------

    def is_empty(self) -> bool:
        """``True`` when the dictionary contains no name → destination entries.

        Upstream PDFBox does not expose ``isEmpty()`` on
        ``PDDocumentNameDestinationDictionary`` directly; callers reach
        through ``getCOSObject().isEmpty()``. pypdfbox surfaces it on the
        wrapper for symmetry with ``COSDictionary.is_empty()``.
        """
        return self._dict.is_empty()

    def __bool__(self) -> bool:
        """``False`` when the dictionary holds no entries.

        Mirrors :meth:`PDDocumentNameDictionary.__bool__` so the legacy
        ``/Dests`` wrapper falls into the same truthiness pattern as the
        ``/Names`` wrapper. ``bool(dd)`` is exactly ``not dd.is_empty()``.
        """
        return not self._dict.is_empty()

    def get_names(self) -> list[str]:
        """Return the destination name keys as a list of Python strings.

        Mirrors the enumeration capability that upstream callers reach by
        iterating ``getCOSObject().keySet()``. Names are returned in the
        underlying dictionary's insertion order.
        """
        return [key.get_name() for key in self._dict.key_set()]

    def keys(self) -> Iterator[str]:
        """Iterate the destination name keys lazily as Python strings.

        Like :meth:`get_names` but returns a fresh iterator rather than
        materializing a list — useful when callers only want to scan keys
        without paying the list-construction cost. Order matches the
        underlying ``COSDictionary`` insertion order.

        Pairs with :meth:`items` so ``for name in dd.keys()`` and
        ``for name, _ in dd.items()`` walk the same sequence. Upstream
        PDFBox does not expose this; callers there iterate
        ``getCOSObject().keySet()`` directly.
        """
        for key in self._dict.key_set():
            yield key.get_name()

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

    def __iter__(self) -> Iterator[tuple[str, PDDestination | None]]:
        """Yield ``(name, destination)`` pairs for every entry.

        Equivalent to iterating ``items()`` — provided so
        ``for name, dest in dd:`` works directly without needing the
        explicit ``items()`` call. The destination is the same object
        :meth:`get_destination` would return; entries whose value is
        not coercible into a ``PDDestination`` (e.g. a dict missing
        ``/D``) yield ``None`` so callers can distinguish "key present
        but malformed" from "key missing".

        Order matches the underlying ``COSDictionary`` insertion order.
        Upstream PDFBox does not expose iteration on this wrapper —
        callers reach through ``getCOSObject().keySet()`` and call
        ``getDestination`` per key. pypdfbox surfaces the convenience
        directly.
        """
        return self.items()

    def items(self) -> Iterator[tuple[str, PDDestination | None]]:
        """Iterate ``(name, destination)`` pairs in insertion order.

        Yields each name string paired with the resolved
        :class:`PDDestination` (or ``None`` when the value cannot be
        coerced). Mirrors :class:`dict.items` shape so callers can write
        ``dict(dd.items())`` to materialize the mapping eagerly.
        """
        for key in self._dict.key_set():
            name = key.get_name()
            yield name, self.get_destination(name)


__all__ = ["PDDocumentNameDestinationDictionary"]
