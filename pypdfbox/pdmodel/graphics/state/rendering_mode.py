from __future__ import annotations

from enum import Enum


class RenderingMode(Enum):
    """Text Rendering Mode. Mirrors PDFBox ``RenderingMode``.

    Each member corresponds to a PDF 32000-1 §9.3.6 text rendering mode
    integer (operand of the ``Tr`` content-stream operator). The
    ``int_value()`` getter returns the numeric value used in the PDF file.

    The :meth:`is_fill` / :meth:`is_stroke` / :meth:`is_clip` predicates
    classify a mode by which path-painting actions it triggers when
    showing text.
    """

    FILL = 0
    STROKE = 1
    FILL_STROKE = 2
    NEITHER = 3
    FILL_CLIP = 4
    STROKE_CLIP = 5
    FILL_STROKE_CLIP = 6
    NEITHER_CLIP = 7

    @classmethod
    def from_int(cls, value: int) -> RenderingMode:
        """Return the enum member whose integer value equals ``value``.

        Mirrors upstream's ``RenderingMode.fromInt(int)`` — raises
        :class:`IndexError` (matching upstream's array indexing behaviour
        when ``value`` is out of range).
        """
        for member in cls:
            if member.value == value:
                return member
        raise IndexError(value)

    def int_value(self) -> int:
        """Return the integer value of this mode, as used in a PDF file."""
        return self.value

    def is_fill(self) -> bool:
        """Return ``True`` if this mode fills text."""
        return self in (
            RenderingMode.FILL,
            RenderingMode.FILL_STROKE,
            RenderingMode.FILL_CLIP,
            RenderingMode.FILL_STROKE_CLIP,
        )

    def is_stroke(self) -> bool:
        """Return ``True`` if this mode strokes text."""
        return self in (
            RenderingMode.STROKE,
            RenderingMode.FILL_STROKE,
            RenderingMode.STROKE_CLIP,
            RenderingMode.FILL_STROKE_CLIP,
        )

    def is_clip(self) -> bool:
        """Return ``True`` if this mode clips text."""
        return self in (
            RenderingMode.FILL_CLIP,
            RenderingMode.STROKE_CLIP,
            RenderingMode.FILL_STROKE_CLIP,
            RenderingMode.NEITHER_CLIP,
        )


__all__ = ["RenderingMode"]
