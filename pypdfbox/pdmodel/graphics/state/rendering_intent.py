from __future__ import annotations

from enum import Enum


class RenderingIntent(Enum):
    """Rendering intent. Mirrors PDFBox ``RenderingIntent``.

    The four PDF 32000-1 §8.6.5.8 / §11.3.5 rendering intents. Each
    member's value is the spec name as stored in the ``/RI`` entry of an
    ExtGState dictionary or as the operand of the ``ri`` content-stream
    operator.
    """

    ABSOLUTE_COLORIMETRIC = "AbsoluteColorimetric"
    RELATIVE_COLORIMETRIC = "RelativeColorimetric"
    SATURATION = "Saturation"
    PERCEPTUAL = "Perceptual"

    @classmethod
    def from_string(cls, value: str | None) -> RenderingIntent:
        """Return the enum constant matching ``value``.

        Mirrors upstream's "If a conforming reader does not recognize the
        specified name, it shall use the RelativeColorimetric intent by
        default." Returns :attr:`RELATIVE_COLORIMETRIC` for any unknown
        (or ``None``) input.
        """
        if value is not None:
            for instance in cls:
                if instance.value == value:
                    return instance
        return cls.RELATIVE_COLORIMETRIC

    def string_value(self) -> str:
        """Return the spec string used in the PDF file."""
        return self.value


__all__ = ["RenderingIntent"]
