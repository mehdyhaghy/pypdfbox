"""Exception raised when the TrueType bytecode interpreter meets a malformed program."""

from __future__ import annotations


class HintingException(RuntimeError):
    """Thrown when the interpreter encounters a malformed or unsupported program.

    It is unchecked upstream (a ``RuntimeException``) so that opcode handlers
    stay terse; the caller catches it per glyph and falls back to raw,
    unhinted coordinates rather than letting one bad glyph disable hinting for
    the whole font.
    """

    def __init__(self, message: str, cause: BaseException | None = None) -> None:
        super().__init__(message)
        self.message = message
        if cause is not None:
            self.__cause__ = cause

    def get_message(self) -> str:
        """Returns the failure description (Java ``getMessage()``)."""
        return self.message


__all__ = ["HintingException"]
