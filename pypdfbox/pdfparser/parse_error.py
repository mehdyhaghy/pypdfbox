from __future__ import annotations


class PDFParseError(ValueError):
    """Raised by parsers when malformed PDF input is encountered.

    Carries the byte offset where the problem was detected when
    available, so higher-level recovery can decide whether to retry,
    skip, or give up.
    """

    def __init__(self, message: str, *, position: int | None = None) -> None:
        if position is not None:
            message = f"{message} (at byte {position})"
        super().__init__(message)
        self.position = position
