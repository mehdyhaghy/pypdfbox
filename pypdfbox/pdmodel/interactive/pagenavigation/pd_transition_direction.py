from __future__ import annotations


class PDTransitionDirection:
    """Direction in which a page transition effect shall move.

    Mirrors PDFBox ``PDTransitionDirection`` enum. Values are degrees
    counterclockwise from a left-to-right direction. Applies to ``Wipe``,
    ``Glitter``, ``Fly``, ``Cover``, ``Uncover`` and ``Push``.

    The ``NONE`` sentinel corresponds to upstream's ``/None`` name value
    (only relevant for ``Fly`` when ``SS`` is not 1.0). It is exposed here
    as the integer ``-1`` so that get/set on ``PDTransition`` can stay int
    typed; ``PDTransition.set_direction(-1)`` writes ``/None`` and
    ``PDTransition.get_direction()`` returns ``-1`` when ``/Di`` is the
    name ``/None``.
    """

    LEFT_TO_RIGHT = 0
    BOTTOM_TO_TOP = 90
    RIGHT_TO_LEFT = 180
    TOP_TO_BOTTOM = 270
    TOP_LEFT_TO_BOTTOM_RIGHT = 315
    NONE = -1

    @classmethod
    def values(cls) -> tuple[int, ...]:
        """Mirror Java enum ``values()`` — return all defined directions
        in declaration order, including the ``NONE`` sentinel."""
        return (
            cls.LEFT_TO_RIGHT,
            cls.BOTTOM_TO_TOP,
            cls.RIGHT_TO_LEFT,
            cls.TOP_TO_BOTTOM,
            cls.TOP_LEFT_TO_BOTTOM_RIGHT,
            cls.NONE,
        )

    @classmethod
    def get_cos_base(cls, direction: int):
        """Mirror upstream ``getCOSBase()``.

        Returns ``COSName.NONE`` for the ``NONE`` sentinel and a
        ``COSInteger`` carrying the direction value otherwise.
        """
        from pypdfbox.cos.cos_integer import COSInteger
        from pypdfbox.cos.cos_name import COSName

        if direction == cls.NONE:
            return COSName.get_pdf_name("None")
        return COSInteger.get(direction)


__all__ = ["PDTransitionDirection"]
