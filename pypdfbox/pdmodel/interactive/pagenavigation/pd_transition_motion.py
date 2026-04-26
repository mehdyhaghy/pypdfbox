from __future__ import annotations


class PDTransitionMotion:
    """Direction of motion for a page transition.

    Mirrors PDFBox ``PDTransitionMotion`` enum. Applies only to
    ``Split``, ``Blinds`` and ``Fly`` transition styles.
    """

    #: Inward from the edges of the page.
    I = "I"
    #: Outward from the center of the page.
    O = "O"


__all__ = ["PDTransitionMotion"]
