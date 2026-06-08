from __future__ import annotations

from typing import Any

from pypdfbox.cos import COSArray, COSBase, COSName, COSString


class PDDestination:
    """
    Abstract base for ``/Dest`` destinations. Mirrors
    ``org.apache.pdfbox.pdmodel.interactive.documentnavigation.destination.PDDestination``.

    Use :meth:`create` to build a concrete subclass from a raw COS value
    (a ``COSArray`` for explicit page destinations, a ``COSName`` or
    ``COSString`` for named destinations).
    """

    @staticmethod
    def create(base: COSBase | None) -> PDDestination | None:
        """Factory — dispatches to the right concrete subclass.

        ``COSArray`` whose item[1] is a recognized type name → page
        destination subclass; ``COSString``/``COSName`` → named
        destination; ``None`` → ``None``."""
        # Local imports avoid circular wiring through the package init.
        from .pd_named_destination import PDNamedDestination
        from .pd_page_fit_destination import PDPageFitDestination
        from .pd_page_fit_height_destination import PDPageFitHeightDestination
        from .pd_page_fit_rectangle_destination import PDPageFitRectangleDestination
        from .pd_page_fit_width_destination import PDPageFitWidthDestination
        from .pd_page_xyz_destination import PDPageXYZDestination

        if base is None:
            return None
        # Upstream's array branch is gated on size() > 1 AND item[1] being a
        # COSName; a COSArray that fails either test falls through the else-if
        # chain to the final "can't convert" error (it is neither COSString nor
        # COSName). Mirror that fall-through exactly so a malformed destination
        # array raises the same OSError as upstream rather than a bespoke
        # "too short"/"not a name" message.
        if (
            isinstance(base, COSArray)
            and base.size() > 1
            and isinstance(base.get_object(1), COSName)
        ):
            type_entry = base.get_object(1)
            type_str = type_entry.get_name()
            if type_str == PDPageFitDestination.TYPE:
                return PDPageFitDestination(base)
            if type_str == PDPageFitDestination.TYPE_BOUNDED:
                return PDPageFitDestination(base)
            if type_str == PDPageFitWidthDestination.TYPE:
                return PDPageFitWidthDestination(base)
            if type_str == PDPageFitWidthDestination.TYPE_BOUNDED:
                return PDPageFitWidthDestination(base)
            if type_str == PDPageFitHeightDestination.TYPE:
                return PDPageFitHeightDestination(base)
            if type_str == PDPageFitHeightDestination.TYPE_BOUNDED:
                return PDPageFitHeightDestination(base)
            if type_str == PDPageFitRectangleDestination.TYPE:
                return PDPageFitRectangleDestination(base)
            if type_str == PDPageXYZDestination.TYPE:
                return PDPageXYZDestination(base)
            raise OSError(f"Unknown destination type: {type_str}")
        if isinstance(base, COSString):
            return PDNamedDestination(base)
        if isinstance(base, COSName):
            return PDNamedDestination(base)
        # Mirrors upstream's final ``else`` — a malformed destination array
        # (size <= 1 or item[1] not a name) lands here too.
        raise OSError(f"Error: can't convert to Destination {base}")

    def get_cos_object(self) -> Any:
        raise NotImplementedError


__all__ = ["PDDestination"]
