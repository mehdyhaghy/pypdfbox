from __future__ import annotations

from enum import Enum


class TextAlign(Enum):
    """Text-alignment enum used by :class:`PlainTextFormatter`. Mirrors
    the inner enum
    ``org.apache.pdfbox.pdmodel.interactive.form.PlainTextFormatter.TextAlign``
    (upstream lines 38–65).

    The enum values match the integer codes used by PDF's ``/Q``
    field-quadding entry: ``LEFT = 0``, ``CENTER = 1``, ``RIGHT = 2``,
    ``JUSTIFY = 4``.
    """

    LEFT = 0
    CENTER = 1
    RIGHT = 2
    JUSTIFY = 4

    def get_text_align(self) -> int:
        """Return the integer alignment code."""
        return self.value

    @classmethod
    def value_of(cls, alignment: int) -> TextAlign:
        """Return the :class:`TextAlign` for ``alignment``, or
        :attr:`LEFT` if no member matches. Mirrors upstream's
        static factory of the same name."""
        for member in cls:
            if member.value == alignment:
                return member
        return cls.LEFT


__all__ = ["TextAlign"]
