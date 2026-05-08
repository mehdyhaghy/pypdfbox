from __future__ import annotations


class PDTransitionMotion:
    """Direction of motion for a page transition.

    Mirrors PDFBox ``PDTransitionMotion`` enum. Applies only to
    ``Split``, ``Blinds`` and ``Fly`` transition styles.
    """

    #: Inward from the edges of the page.
    I = "I"  # noqa: E741 - PDFBox/API name
    #: Outward from the center of the page.
    O = "O"  # noqa: E741 - PDFBox/API name


__all__ = ["PDTransitionMotion"]
