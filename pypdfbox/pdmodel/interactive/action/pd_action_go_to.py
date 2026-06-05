from __future__ import annotations

from pypdfbox.cos import COSArray, COSBase, COSDictionary, COSName, COSString
from pypdfbox.pdmodel.interactive.documentnavigation.destination import PDDestination
from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_page_destination import (
    PDPageDestination,
)

from .pd_action import PDAction

_D: COSName = COSName.D  # type: ignore[attr-defined]


class PDActionGoTo(PDAction):
    """GoTo action. Mirrors PDFBox ``PDActionGoTo``.

    Per PDF 32000-1 §12.6.4.2 Table 198 the action carries a single typed
    entry, ``/D``, which may be an explicit page-target ``COSArray`` or a
    named destination encoded as ``COSString`` or ``COSName``.
    """

    SUB_TYPE = "GoTo"

    def __init__(self, action: COSDictionary | None = None) -> None:
        super().__init__(action, None if action is not None else self.SUB_TYPE)

    def get_destination(self) -> PDDestination | None:
        """Return ``/D`` dispatched to its appropriate :class:`PDDestination`
        subclass:

        - a concrete :class:`PDPageDestination` subclass for explicit
          page-target arrays (``COSArray`` form);
        - a :class:`PDNamedDestination` for named destinations encoded as
          ``COSString`` or ``COSName``;
        - ``None`` when ``/D`` is absent.

        Mirrors upstream ``PDActionGoTo#getDestination`` (PDActionGoTo.java
        line 66-69): ``return PDDestination.create(getCOSObject()
        .getDictionaryObject(COSName.D));``. The named-destination name is
        then available via :meth:`PDNamedDestination.get_named_destination`.
        """
        return PDDestination.create(self._action.get_dictionary_object(_D))

    def set_destination(self, destination: PDDestination | str | COSBase | None) -> None:
        """Write ``/D`` from a typed destination, a named-destination
        string, a raw ``COSBase``, or ``None`` (which removes the entry).

        Mirrors upstream ``PDActionGoTo#setDestination`` validation: when a
        :class:`PDPageDestination` is supplied with a non-empty backing array
        whose first element is *not* a page ``COSDictionary``, raises
        :class:`ValueError` (Python equivalent of ``IllegalArgumentException``).
        Indirect-reference page targets are accepted because resolution may
        defer until write time."""
        if destination is None:
            self._action.remove_item(_D)
            return
        if isinstance(destination, PDPageDestination):
            dest_array = destination.get_cos_object()
            if isinstance(dest_array, COSArray) and dest_array.size() >= 1:
                page = dest_array.get_object(0)
                if not isinstance(page, COSDictionary):
                    raise ValueError(
                        "Destination of a GoTo action must be a page dictionary object"
                    )
            self._action.set_item(_D, dest_array)
            return
        if isinstance(destination, PDDestination):
            self._action.set_item(_D, destination.get_cos_object())
            return
        if isinstance(destination, str):
            self._action.set_string(_D, destination)
            return
        self._action.set_item(_D, destination)

    # Raw ``/D`` accessors mirroring the sibling actions
    # (``PDActionRemoteGoTo``, ``PDActionThread``) which expose ``get_d`` /
    # ``set_d`` as untyped passthroughs to the dictionary entry.
    def get_d(self) -> COSBase | None:
        """Return the raw ``/D`` entry as a :class:`COSBase`, or ``None``
        when absent. Untyped passthrough — use :meth:`get_destination`
        for the dispatched typed result."""
        return self._action.get_dictionary_object(_D)

    def set_d(self, destination: COSBase | None) -> None:
        """Write ``/D`` from a raw :class:`COSBase`, or remove the entry
        when ``destination`` is ``None``. Untyped passthrough — use
        :meth:`set_destination` for the dispatched typed setter."""
        if destination is None:
            self._action.remove_item(_D)
            return
        self._action.set_item(_D, destination)

    # Named-destination convenience accessors mirroring
    # :class:`PDActionRemoteGoTo`. ``/D`` may be a ``COSString`` naming an
    # entry in the document's ``/Names`` ``/Dests`` tree (PDF 32000-1
    # §12.3.2.3); these helpers narrow the typed dispatch to that case.
    def get_named_destination(self) -> str | None:
        """Return ``/D`` when it is a string-form named destination,
        otherwise ``None``. Mirrors :meth:`PDActionRemoteGoTo.get_named_destination`."""
        d = self._action.get_dictionary_object(_D)
        if isinstance(d, COSString):
            return d.get_string()
        return None

    def set_named_destination(self, name: str | None) -> None:
        """Write ``/D`` as a string-form named destination, or remove the
        entry when ``name`` is ``None``."""
        if name is None:
            self._action.remove_item(_D)
            return
        self._action.set_string(_D, name)

    # ---------- predicates / clear / is_empty ----------

    def has_destination(self) -> bool:
        """``True`` when ``/D`` is present on the underlying dictionary,
        regardless of whether it is an explicit page array, a named
        destination string, a name, or a malformed COS shape. Lets callers
        branch on destination-presence without constructing a typed
        :class:`PDDestination` wrapper. Parallels
        :class:`PDActionRemoteGoTo.has_destination`."""
        return self._action.get_dictionary_object(_D) is not None

    def clear_destination(self) -> None:
        """Remove ``/D`` from the action dictionary."""
        self._action.remove_item(_D)

    def is_empty(self) -> bool:
        """``True`` when ``/D`` is absent — i.e. the action carries no
        local go-to destination state."""
        return not self.has_destination()

    def is_valid(self) -> bool:
        """``True`` when this action's ``/S`` entry equals
        :attr:`SUB_TYPE` (``"GoTo"``). Useful as a sanity check after
        round-tripping through :meth:`PDAction.create` or when constructing
        the wrapper around a hand-built :class:`COSDictionary`."""
        return self.get_sub_type() == self.SUB_TYPE


__all__ = ["PDActionGoTo"]
