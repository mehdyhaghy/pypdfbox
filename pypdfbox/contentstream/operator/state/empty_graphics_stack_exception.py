from __future__ import annotations


class EmptyGraphicsStackException(OSError):
    """Raised when the ``Q`` (restore) operator is executed on an empty
    graphics-state stack.

    Mirrors
    ``org.apache.pdfbox.contentstream.operator.state.EmptyGraphicsStackException``.
    Upstream extends ``IOException``; per CLAUDE.md test-porting table we
    map ``IOException`` to ``OSError`` in pypdfbox.

    The message text mirrors upstream verbatim:
    ``Cannot execute restore, the graphics stack is empty``.
    """

    def __init__(self) -> None:
        super().__init__("Cannot execute restore, the graphics stack is empty")


__all__ = ["EmptyGraphicsStackException"]
