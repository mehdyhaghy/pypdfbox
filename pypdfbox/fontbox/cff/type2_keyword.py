"""Type 2 char-string keyword table.

Mirrors the inner enum ``CharStringCommand.Type2KeyWord`` from upstream
``org.apache.fontbox.cff.CharStringCommand`` (CharStringCommand.java:328).

The shared ``Key`` enum lives in :mod:`pypdfbox.fontbox.cff.type1_keyword`
to avoid duplication; we re-export it from here so callers can still
reach ``Key`` through ``CharStringCommand``-style lookups.
"""

from __future__ import annotations

from typing import ClassVar

from .type1_keyword import Key


class Type2KeyWord:
    """Mirrors ``CharStringCommand.Type2KeyWord``
    (CharStringCommand.java:328).

    One class-level instance per Type 2 operator, each carrying its
    associated ``Key`` — same shape as ``Type1KeyWord``.
    """

    _BY_KEY: ClassVar[dict[Key, Type2KeyWord]] = {}
    _MEMBERS: ClassVar[list[Type2KeyWord]] = []

    def __init__(self, name: str, key: Key) -> None:
        self.name = name
        self.key = key

    def __repr__(self) -> str:
        return f"Type2KeyWord.{self.name}"

    def __str__(self) -> str:
        return self.name

    def __hash__(self) -> int:
        return hash(("Type2KeyWord", self.name))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Type2KeyWord):
            return NotImplemented
        return self.name == other.name

    @classmethod
    def value_of_key(
        cls, b0: int | Key, b1: int | None = None
    ) -> Type2KeyWord | None:
        """Mirrors upstream's three overloads:
        ``valueOfKey(int)`` (CharStringCommand.java:362),
        ``valueOfKey(int, int)`` (CharStringCommand.java:367),
        ``valueOfKey(Key)`` (CharStringCommand.java:372)."""
        if isinstance(b0, Key):
            return cls._BY_KEY.get(b0)
        key = Key.value_of_key(b0, b1)
        if key is None:
            return None
        return cls._BY_KEY.get(key)

    @classmethod
    def values(cls) -> list[Type2KeyWord]:
        return list(cls._MEMBERS)


def _register_type2_keywords() -> None:
    """Populate ``Type2KeyWord`` constants. Mirrors upstream enum literal
    list at CharStringCommand.java:330–343."""
    names = (
        "HSTEM", "VSTEM", "VMOVETO", "RLINETO",
        "HLINETO", "VLINETO", "RRCURVETO", "CALLSUBR",
        "RET", "ESCAPE", "AND", "OR",
        "NOT", "ABS", "ADD", "SUB",
        "DIV", "NEG", "EQ", "DROP",
        "PUT", "GET", "IFELSE",
        "RANDOM", "MUL", "SQRT", "DUP",
        "EXCH", "INDEX", "ROLL",
        "HFLEX", "FLEX", "HFLEX1",
        "FLEX1", "ENDCHAR", "HSTEMHM", "HINTMASK",
        "CNTRMASK", "RMOVETO", "HMOVETO", "VSTEMHM",
        "RCURVELINE", "RLINECURVE", "VVCURVETO",
        "HHCURVETO", "SHORTINT", "CALLGSUBR",
        "VHCURVETO", "HVCURVETO",
    )
    for name in names:
        key = getattr(Key, name)
        kw = Type2KeyWord(name, key)
        setattr(Type2KeyWord, name, kw)
        Type2KeyWord._BY_KEY[key] = kw
        Type2KeyWord._MEMBERS.append(kw)


_register_type2_keywords()


__all__ = ["Type2KeyWord"]
