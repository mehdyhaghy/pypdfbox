from __future__ import annotations


class PDTransitionStyle:
    """Transition style names. Mirrors PDFBox ``PDTransitionStyle`` enum.

    See PDF 32000-1:2008 table 162.
    """

    SPLIT = "Split"
    BLINDS = "Blinds"
    BOX = "Box"
    WIPE = "Wipe"
    DISSOLVE = "Dissolve"
    GLITTER = "Glitter"
    R = "R"
    FLY = "Fly"
    PUSH = "Push"
    COVER = "Cover"
    UNCOVER = "Uncover"
    FADE = "Fade"


__all__ = ["PDTransitionStyle"]
