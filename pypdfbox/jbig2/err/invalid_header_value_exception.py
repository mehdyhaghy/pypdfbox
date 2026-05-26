from __future__ import annotations

from pypdfbox.jbig2.err.jbig2_exception import JBIG2Exception


class InvalidHeaderValueException(JBIG2Exception):
    """
    Can be used if a segment header value is invalid.

    Mirrors ``org.apache.pdfbox.jbig2.err.InvalidHeaderValueException``, which
    extends :class:`JBIG2Exception`. The four upstream constructors collapse
    onto the same ``(message, cause)`` initializer.
    """

    def __init__(
        self,
        message: str | None = None,
        cause: BaseException | None = None,
    ) -> None:
        super().__init__(message, cause)
