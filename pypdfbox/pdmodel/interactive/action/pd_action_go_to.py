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

    def get_destination(self) -> PDDestination | str | None:
        """Return ``/D`` dispatched to its appropriate type:

        - ``PDDestination`` instance for explicit page-target arrays
          (``COSArray`` form);
        - ``str`` for named destinations (``COSString`` or ``COSName`` form);
        - ``None`` when ``/D`` is absent.
        """
        d = self._action.get_dictionary_object(_D)
        if d is None:
            return None
        if isinstance(d, COSArray):
            return PDDestination.create(d)
        if isinstance(d, COSString):
            return d.get_string()
        if isinstance(d, COSName):
            return d.get_name()
        return None

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


__all__ = ["PDActionGoTo"]
