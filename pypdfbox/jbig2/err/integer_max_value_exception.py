from __future__ import annotations

from pypdfbox.jbig2.err.jbig2_exception import JBIG2Exception


class IntegerMaxValueException(JBIG2Exception):
    """
    Can be used if the maximum value limit of an integer is exceeded.

    Mirrors ``org.apache.pdfbox.jbig2.err.IntegerMaxValueException``, which
    extends :class:`JBIG2Exception`. The four upstream constructors collapse
    onto the same ``(message, cause)`` initializer inherited in spirit from
    :class:`JBIG2Exception`.
    """

    def __init__(
        self,
        message: str | None = None,
        cause: BaseException | None = None,
    ) -> None:
        super().__init__(message, cause)
