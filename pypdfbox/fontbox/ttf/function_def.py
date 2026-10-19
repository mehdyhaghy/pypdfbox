"""A function defined by an ``FDEF`` (or an instruction defined by ``IDEF``)."""

from __future__ import annotations


class FunctionDef:
    """The bytecode program a function lives in and the span of its body.

    The program is normally the ``fpgm``; ``entry_point`` is the offset of the
    first body instruction, just past the ``FDEF``. ``CALL`` and ``LOOPCALL``
    run the body from this offset until the matching ``ENDF``.
    """

    __slots__ = ("_end", "_entry_point", "_program")

    def __init__(self, program: bytes, entry_point: int, end: int) -> None:
        self._program = program
        self._entry_point = entry_point
        self._end = end

    def get_program(self) -> bytes:
        """Returns the bytecode the function body lives in."""
        return self._program

    def get_entry_point(self) -> int:
        """Returns the offset of the first body instruction."""
        return self._entry_point

    def get_end(self) -> int:
        """Returns the offset of the body's ``ENDF``; execution never passes it."""
        return self._end


__all__ = ["FunctionDef"]
