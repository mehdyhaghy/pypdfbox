from __future__ import annotations


class PDFParseError(ValueError):
    """Raised by parsers when malformed PDF input is encountered.

    Carries the byte offset where the problem was detected when
    available, so higher-level recovery can decide whether to retry,
    skip, or give up.
    """

    def __init__(
        self,
        message: str,
        *,
        position: int | None = None,
        cause: BaseException | None = None,
    ) -> None:
        # Keep the raw message separately so callers can recover it without
        # the ``(at byte N)`` suffix that ``__str__`` exposes.
        self._raw_message: str = message
        if position is not None:
            message = f"{message} (at byte {position})"
        super().__init__(message)
        self.position = position
        # Mirror Java ``Throwable.getCause()`` semantics — the original
        # exception that triggered this parse error, if any. We also wire
        # it into ``__cause__`` so ``raise ... from cause`` style chaining
        # is preserved when the helper constructor is used directly.
        self.cause = cause
        if cause is not None and self.__cause__ is None:
            self.__cause__ = cause

    @property
    def message(self) -> str:
        """The raw error message without any ``(at byte N)`` suffix."""
        return self._raw_message

    def get_message(self) -> str:
        """Snake_case accessor mirroring Java ``Throwable.getMessage()``."""
        return self._raw_message

    def get_position(self) -> int | None:
        """Snake_case accessor for the byte offset, or ``None`` if unknown."""
        return self.position

    def get_cause(self) -> BaseException | None:
        """Snake_case accessor mirroring Java ``Throwable.getCause()``."""
        return self.cause

    def with_position(self, position: int) -> PDFParseError:
        """Return a new ``PDFParseError`` carrying the same message and
        cause but tagged with ``position``.

        Useful when an inner helper raises a position-less error and the
        outer parser knows the offset where recovery should resume.
        """
        return PDFParseError(self._raw_message, position=position, cause=self.cause)
