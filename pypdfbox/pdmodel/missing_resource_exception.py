from __future__ import annotations


class MissingResourceException(OSError):
    """
    Raised when a named resource is missing from a resources dictionary.

    Mirrors ``org.apache.pdfbox.pdmodel.MissingResourceException``. Upstream
    extends ``IOException``; per the project's test-porting conventions we
    map ``IOException`` to ``OSError`` in pypdfbox.

    Used by code paths such as :class:`PDColorSpace.create` (when a named
    color-space lookup fails) and the ``Do`` operator (when an XObject name
    does not resolve in the current resources stack). The single-argument
    constructor mirrors upstream verbatim — the ``message`` becomes the
    standard exception text and is recoverable via ``str(exc)`` /
    ``exc.args``.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)
