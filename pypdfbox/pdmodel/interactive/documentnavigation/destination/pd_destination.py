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
        if isinstance(base, COSArray):
            if base.size() < 2:
                raise OSError(f"Destination array too short: {base.size()}")
            type_entry = base.get_object(1)
            if not isinstance(type_entry, COSName):
                raise OSError(
                    f"Destination array entry [1] must be a name; got {type(type_entry).__name__}"
                )
            type_str = type_entry.get_name()
            if type_str == PDPageFitDestination.TYPE:
                return PDPageFitDestination(base)
            if type_str == PDPageFitDestination.TYPE_BOUNDED:
                from .pd_page_fit_bounding_box_destination import (
                    PDPageFitBoundingBoxDestination,
                )

                return PDPageFitBoundingBoxDestination(base)
            if type_str == PDPageFitWidthDestination.TYPE:
                return PDPageFitWidthDestination(base)
            if type_str == PDPageFitWidthDestination.TYPE_BOUNDED:
                from .pd_page_fit_bounding_box_width_destination import (
                    PDPageFitBoundingBoxWidthDestination,
                )

                return PDPageFitBoundingBoxWidthDestination(base)
            if type_str == PDPageFitHeightDestination.TYPE:
                return PDPageFitHeightDestination(base)
            if type_str == PDPageFitHeightDestination.TYPE_BOUNDED:
                from .pd_page_fit_bounding_box_height_destination import (
                    PDPageFitBoundingBoxHeightDestination,
                )

                return PDPageFitBoundingBoxHeightDestination(base)
            if type_str == PDPageFitRectangleDestination.TYPE:
                return PDPageFitRectangleDestination(base)
            if type_str == PDPageXYZDestination.TYPE:
                return PDPageXYZDestination(base)
            raise OSError(f"Unknown destination type: {type_str}")
        if isinstance(base, COSString):
            return PDNamedDestination(base)
        if isinstance(base, COSName):
            return PDNamedDestination(base)
        raise OSError(f"Cannot convert to PDDestination: {type(base).__name__}")

    def get_cos_object(self) -> Any:
        raise NotImplementedError


__all__ = ["PDDestination"]
