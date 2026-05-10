"""Type 1 char-string keyword table.

Mirrors the inner enum ``CharStringCommand.Type1KeyWord`` from upstream
``org.apache.fontbox.cff.CharStringCommand`` (CharStringCommand.java:280).

Upstream nests this enum inside ``CharStringCommand``; we lift it into
its own module so the lookup tables stay private to the keyword module
and ``CharStringCommand`` itself can stay small. The ``Key`` enum
(CharStringCommand.java:378) lives here as well as a private helper —
upstream stores Key on the enum as a field, but the only public surface
exercised through ``Type1KeyWord`` is ``key`` (carrying the hash value)
and ``name``.
"""

from __future__ import annotations

from typing import ClassVar


class Key:
    """Mirrors ``CharStringCommand.Key`` (CharStringCommand.java:378).

    Each operator carries a single integer ``hash_value`` derived from
    its byte sequence: one-byte commands store ``b0`` directly; two-byte
    commands store ``(b0 << 4) + b1`` (matches upstream's
    ``Key(int b0, int b1)`` constructor at CharStringCommand.java:403).
    """

    _BY_KEY: ClassVar[dict[int, Key]] = {}

    def __init__(self, name: str, b0: int, b1: int | None = None) -> None:
        self.name = name
        if b1 is None:
            self.hash_value = b0
        else:
            self.hash_value = (b0 << 4) + b1

    def get_hash_value(self) -> int:
        """Mirrors upstream package-private ``Key.getHashValue()``
        (CharStringCommand.java:428)."""
        return self.hash_value

    def __repr__(self) -> str:
        return f"Key.{self.name}"

    def __hash__(self) -> int:
        return hash(("Key", self.hash_value))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Key):
            return NotImplemented
        return self.hash_value == other.hash_value

    @classmethod
    def value_of_key(cls, b0: int, b1: int | None = None) -> Key | None:
        """Mirrors upstream static ``Key.valueOfKey(int)`` /
        ``valueOfKey(int, int)`` (CharStringCommand.java:418, 423)."""
        if b1 is None:
            return cls._BY_KEY.get(b0)
        return cls._BY_KEY.get((b0 << 4) + b1)


def _register_keys() -> None:
    """Populate ``Key`` constants. Mirrors upstream enum literal list
    (CharStringCommand.java:380)."""
    entries: tuple[tuple[str, int, int | None], ...] = (
        ("HSTEM", 1, None),
        ("VSTEM", 3, None),
        ("VMOVETO", 4, None),
        ("RLINETO", 5, None),
        ("HLINETO", 6, None),
        ("VLINETO", 7, None),
        ("RRCURVETO", 8, None),
        ("CLOSEPATH", 9, None),
        ("CALLSUBR", 10, None),
        ("RET", 11, None),
        ("ESCAPE", 12, None),
        ("DOTSECTION", 12, 0),
        ("VSTEM3", 12, 1),
        ("HSTEM3", 12, 2),
        ("AND", 12, 3),
        ("OR", 12, 4),
        ("NOT", 12, 5),
        ("SEAC", 12, 6),
        ("SBW", 12, 7),
        ("ABS", 12, 9),
        ("ADD", 12, 10),
        ("SUB", 12, 11),
        ("DIV", 12, 12),
        ("NEG", 12, 14),
        ("EQ", 12, 15),
        ("CALLOTHERSUBR", 12, 16),
        ("POP", 12, 17),
        ("DROP", 12, 18),
        ("PUT", 12, 20),
        ("GET", 12, 21),
        ("IFELSE", 12, 22),
        ("RANDOM", 12, 23),
        ("MUL", 12, 24),
        ("SQRT", 12, 26),
        ("DUP", 12, 27),
        ("EXCH", 12, 28),
        ("INDEX", 12, 29),
        ("ROLL", 12, 30),
        ("SETCURRENTPOINT", 12, 33),
        ("HFLEX", 12, 34),
        ("FLEX", 12, 35),
        ("HFLEX1", 12, 36),
        ("FLEX1", 12, 37),
        ("HSBW", 13, None),
        ("ENDCHAR", 14, None),
        ("HSTEMHM", 18, None),
        ("HINTMASK", 19, None),
        ("CNTRMASK", 20, None),
        ("RMOVETO", 21, None),
        ("HMOVETO", 22, None),
        ("VSTEMHM", 23, None),
        ("RCURVELINE", 24, None),
        ("RLINECURVE", 25, None),
        ("VVCURVETO", 26, None),
        ("HHCURVETO", 27, None),
        ("SHORTINT", 28, None),
        ("CALLGSUBR", 29, None),
        ("VHCURVETO", 30, None),
        ("HVCURVETO", 31, None),
    )
    for name, b0, b1 in entries:
        key = Key(name, b0, b1)
        setattr(Key, name, key)
        Key._BY_KEY[key.hash_value] = key


_register_keys()


class Type1KeyWord:
    """Mirrors ``CharStringCommand.Type1KeyWord``
    (CharStringCommand.java:279).

    Upstream is a Java enum with one constant per Type 1 operator,
    carrying its associated ``Key``. We port as a plain class with one
    class-level instance per operator — mirroring "enum-as-data" shape
    while keeping the Python surface lookup-friendly.
    """

    _BY_KEY: ClassVar[dict[Key, Type1KeyWord]] = {}
    _MEMBERS: ClassVar[list[Type1KeyWord]] = []

    def __init__(self, name: str, key: Key) -> None:
        self.name = name
        self.key = key

    def __repr__(self) -> str:
        return f"Type1KeyWord.{self.name}"

    def __str__(self) -> str:
        # Upstream's ``Enum.toString()`` returns the name.
        return self.name

    def __hash__(self) -> int:
        return hash(("Type1KeyWord", self.name))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Type1KeyWord):
            return NotImplemented
        return self.name == other.name

    @classmethod
    def value_of_key(
        cls, b0: int | Key, b1: int | None = None
    ) -> Type1KeyWord | None:
        """Mirrors upstream's three overloads:
        ``valueOfKey(int)`` (CharStringCommand.java:308),
        ``valueOfKey(int, int)`` (CharStringCommand.java:313),
        ``valueOfKey(Key)`` (CharStringCommand.java:318)."""
        if isinstance(b0, Key):
            return cls._BY_KEY.get(b0)
        key = Key.value_of_key(b0, b1)
        if key is None:
            return None
        return cls._BY_KEY.get(key)

    @classmethod
    def values(cls) -> list[Type1KeyWord]:
        """Mirrors Java enum's ``values()``."""
        return list(cls._MEMBERS)


def _register_type1_keywords() -> None:
    """Populate ``Type1KeyWord`` constants. Mirrors upstream enum literal
    list at CharStringCommand.java:281–289."""
    names = (
        "HSTEM", "VSTEM", "VMOVETO", "RLINETO",
        "HLINETO", "VLINETO", "RRCURVETO",
        "CLOSEPATH", "CALLSUBR", "RET",
        "ESCAPE", "DOTSECTION",
        "VSTEM3", "HSTEM3", "SEAC", "SBW",
        "DIV", "CALLOTHERSUBR", "POP",
        "SETCURRENTPOINT", "HSBW", "ENDCHAR",
        "RMOVETO", "HMOVETO", "VHCURVETO",
        "HVCURVETO",
    )
    for name in names:
        key = getattr(Key, name)
        kw = Type1KeyWord(name, key)
        setattr(Type1KeyWord, name, kw)
        Type1KeyWord._BY_KEY[key] = kw
        Type1KeyWord._MEMBERS.append(kw)


_register_type1_keywords()


__all__ = ["Key", "Type1KeyWord"]
