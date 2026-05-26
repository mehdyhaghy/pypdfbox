"""Exception raised when XMP serialization cannot be performed.

Mirrors ``org.apache.xmpbox.xml.XmpSerializationException`` (PDFBox 3.0,
``xmpbox/src/main/java/org/apache/xmpbox/xml/XmpSerializationException.java``).

Upstream extends ``java.lang.Exception`` with a message-only constructor and a
message-plus-cause constructor. The Python mirror subclasses the built-in
:class:`Exception` and accepts an optional ``cause`` that is wired up as the
exception's ``__cause__`` so ``raise ... from cause`` semantics are preserved.
"""

from __future__ import annotations


class XmpSerializationException(Exception):
    """Raised when XMP serialization fails."""

    def __init__(self, message: str, cause: BaseException | None = None) -> None:
        """Create an instance with a description and an optional cause."""
        super().__init__(message)
        if cause is not None:
            self.__cause__ = cause


__all__ = ["XmpSerializationException"]
