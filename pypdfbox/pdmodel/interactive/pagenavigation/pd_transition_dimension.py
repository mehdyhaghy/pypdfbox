from __future__ import annotations


class PDTransitionDimension:
    """Dimension in which a page transition shall occur.

    Mirrors PDFBox ``PDTransitionDimension`` enum. Applies only to
    ``Split`` and ``Blinds`` transition styles.
    """

    #: Horizontal.
    H = "H"
    #: Vertical.
    V = "V"


__all__ = ["PDTransitionDimension"]
