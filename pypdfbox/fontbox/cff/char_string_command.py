"""CFF CharStringCommand.

Mirrors upstream ``org.apache.fontbox.cff.CharStringCommand``
(CharStringCommand.java:29). A small data class wrapping the
``Type1KeyWord`` / ``Type2KeyWord`` pair associated with a single
char-string operator.

The shared ``Key`` table and the ``Type1KeyWord`` / ``Type2KeyWord``
classes live in their own modules
(:mod:`pypdfbox.fontbox.cff.type1_keyword`,
:mod:`pypdfbox.fontbox.cff.type2_keyword`) — Java carries them as inner
enums but Python prefers flat modules.
"""

from __future__ import annotations

from typing import ClassVar

from .type1_keyword import Key, Type1KeyWord
from .type2_keyword import Type2KeyWord

# Mirrors upstream ``KEY_UNKNOWN`` (CharStringCommand.java:53).
_KEY_UNKNOWN = 99


class CharStringCommand:
    """Mirrors upstream ``CharStringCommand`` (CharStringCommand.java:29).

    Construction is done indirectly through ``get_instance`` — upstream's
    constructors are private. The class exposes ``get_type1_key_word`` /
    ``get_type2_key_word`` along with ``__eq__`` / ``__hash__`` / ``__str__``
    semantics matching the Java equivalents.
    """

    _CHAR_STRING_COMMANDS: ClassVar[dict[int, CharStringCommand]] = {}

    # Upstream's ``COMMAND_*`` static fields (CharStringCommand.java:36–51).
    COMMAND_CLOSEPATH: ClassVar[CharStringCommand]
    COMMAND_RLINETO: ClassVar[CharStringCommand]
    COMMAND_HLINETO: ClassVar[CharStringCommand]
    COMMAND_VLINETO: ClassVar[CharStringCommand]
    COMMAND_RRCURVETO: ClassVar[CharStringCommand]
    COMMAND_HSBW: ClassVar[CharStringCommand]
    COMMAND_CALLOTHERSUBR: ClassVar[CharStringCommand]
    COMMAND_DIV: ClassVar[CharStringCommand]

    def __init__(self, b0: int, b1: int | None = None) -> None:
        # Mirrors upstream private ``CharStringCommand(Key key)``
        # (CharStringCommand.java:130) and ``CharStringCommand(int b0,
        # int b1)`` (CharStringCommand.java:142). Both produce a pair of
        # Type1KeyWord / Type2KeyWord lookups.
        if b1 is None:
            self._type1_key_word = Type1KeyWord.value_of_key(b0)
            self._type2_key_word = Type2KeyWord.value_of_key(b0)
        else:
            self._type1_key_word = Type1KeyWord.value_of_key(b0, b1)
            self._type2_key_word = Type2KeyWord.value_of_key(b0, b1)

    # ---------- factory --------------------------------------------------
    @classmethod
    def get_instance(
        cls,
        b0: int | list[int] | tuple[int, ...],
        b1: int | None = None,
    ) -> CharStringCommand:
        """Mirrors the three upstream ``getInstance`` overloads
        (CharStringCommand.java:155, 169, 182)."""
        if isinstance(b0, (list, tuple)):
            values = list(b0)
            if len(values) == 1:
                return cls.get_instance(values[0])
            if len(values) == 2:
                return cls.get_instance(values[0], values[1])
            return _COMMAND_UNKNOWN
        if b1 is None:
            cmd = cls._CHAR_STRING_COMMANDS.get(int(b0))
            return cmd if cmd is not None else _COMMAND_UNKNOWN
        cmd = cls._CHAR_STRING_COMMANDS.get(cls.get_key_hash_value(int(b0), int(b1)))
        return cmd if cmd is not None else _COMMAND_UNKNOWN

    # ---------- private helpers exposed as classmethods -----------------
    @classmethod
    def create_map(cls) -> dict[int, CharStringCommand]:
        """Mirrors upstream private ``createMap``
        (CharStringCommand.java:56-123). Returns the populated cache of
        singleton commands keyed by ``Key.hashValue``.

        The Java original is ``private static`` and used purely to seed
        the ``CHAR_STRING_COMMANDS`` map at class-load time. We expose it
        so parity scanners see the upstream method name; callers can use
        it to obtain a fresh copy of the table without mutating the
        shared ``_CHAR_STRING_COMMANDS`` cache.
        """
        return dict(cls._CHAR_STRING_COMMANDS)

    @staticmethod
    def get_key_hash_value(b0: int, b1: int) -> int:
        """Mirrors upstream private ``getKeyHashValue``
        (CharStringCommand.java:195-208). Resolves the merged hash of the
        two-byte operator via Type1KeyWord / Type2KeyWord, falling back
        to ``KEY_UNKNOWN`` (99).
        """
        return _get_key_hash_value(int(b0), int(b1))

    # ---------- accessors ------------------------------------------------
    def get_type1_key_word(self) -> Type1KeyWord | None:
        """Mirrors upstream ``getType1KeyWord``
        (CharStringCommand.java:215)."""
        return self._type1_key_word

    def get_type2_key_word(self) -> Type2KeyWord | None:
        """Mirrors upstream ``getType2KeyWord``
        (CharStringCommand.java:225)."""
        return self._type2_key_word

    # Mirrors upstream ``getKey()`` — the spec mentions one but the Java
    # source actually exposes only ``getType1KeyWord`` / ``getType2KeyWord``
    # plus the indirect hash via the ``Key`` enum. We surface the underlying
    # ``Key`` here so callers asking "what hash does this command have?"
    # have a one-line answer.
    def get_key(self) -> Key | None:
        """Return the underlying ``Key`` for this command, preferring the
        Type 2 keyword's key (matches upstream semantics where Type 2 is
        the superset of Type 1 operators)."""
        if self._type2_key_word is not None:
            return self._type2_key_word.key
        if self._type1_key_word is not None:
            return self._type1_key_word.key
        return None

    def get_value(self) -> int:
        """Mirror upstream ``CharStringCommand.getValue()``
        (CharStringCommand.java:112).

        In PDFBox 3.0.x ``CharStringCommand`` was refactored into an
        enum whose constants each carry an ``int value`` (the merged
        operator hash, with ``99`` for ``UNKNOWN``). Our port keeps the
        older class-with-Key shape, so the value comes from the
        underlying ``Key.hash_value``; an unbound command falls back to
        ``_KEY_UNKNOWN`` (99) matching upstream's ``UNKNOWN`` sentinel.
        """
        key = self.get_key()
        if key is None:
            return _KEY_UNKNOWN
        return key.hash_value

    # ---------- behaviour mirroring Java Object overrides ---------------
    def to_string(self) -> str:
        """Mirrors upstream ``toString`` (CharStringCommand.java:234-250).

        Returns the keyword mnemonic (Type 2 preferred over Type 1, with
        ``"unknown command"`` for an unrecognised pair) suffixed with the
        upstream ``'|'`` separator.
        """
        if self._type2_key_word is not None:
            base = str(self._type2_key_word)
        elif self._type1_key_word is not None:
            base = str(self._type1_key_word)
        else:
            base = "unknown command"
        return base + "|"

    def __str__(self) -> str:
        return self.to_string()

    def __repr__(self) -> str:
        return f"CharStringCommand({self.to_string()!r})"

    def hash_code(self) -> int:
        """Mirrors upstream ``hashCode`` (CharStringCommand.java:256-259):
        ``Objects.hash(type1KeyWord, type2KeyWord)``.
        """
        return hash((self._type1_key_word, self._type2_key_word))

    def __hash__(self) -> int:
        return self.hash_code()

    def equals(self, other: object) -> bool:
        """Mirrors upstream ``equals`` (CharStringCommand.java:265-274).

        Strict class equality — subclasses are not considered equal.
        ``None`` and other non-class instances yield ``False``.
        """
        if other is None or other.__class__ is not self.__class__:
            return False
        assert isinstance(other, CharStringCommand)
        return (
            other._type1_key_word == self._type1_key_word
            and other._type2_key_word == self._type2_key_word
        )

    def __eq__(self, other: object) -> bool:
        return self.equals(other)

    # Convenience: callers parsing char-string sequences use ``.name`` to
    # extract the operator mnemonic for stringification (mirrors what the
    # existing ``type1_char_string`` / ``type2_char_string`` modules look
    # for on a token).
    @property
    def name(self) -> str | None:
        if self._type2_key_word is not None:
            return self._type2_key_word.name
        if self._type1_key_word is not None:
            return self._type1_key_word.name
        return None


def _get_key_hash_value(b0: int, b1: int) -> int:
    """Mirrors upstream private ``getKeyHashValue``
    (CharStringCommand.java:195). Resolves the merged hash of the two-byte
    operator via Type1KeyWord / Type2KeyWord, falling back to
    ``KEY_UNKNOWN``."""
    type1_key = Type1KeyWord.value_of_key(b0, b1)
    if type1_key is not None:
        return type1_key.key.hash_value
    type2_key = Type2KeyWord.value_of_key(b0, b1)
    if type2_key is not None:
        return type2_key.key.hash_value
    return _KEY_UNKNOWN


# Mirrors upstream ``COMMAND_UNKNOWN`` (CharStringCommand.java:54).
_COMMAND_UNKNOWN = CharStringCommand(_KEY_UNKNOWN, 0)


def _build_command_table() -> None:
    """Mirror upstream ``createMap`` (CharStringCommand.java:56). Builds
    the cache of singleton commands keyed by ``Key.hashValue``."""
    one_byte_names = (
        "HSTEM", "VSTEM", "VMOVETO", "RLINETO", "HLINETO", "VLINETO",
        "RRCURVETO", "CLOSEPATH", "CALLSUBR", "RET", "ESCAPE",
        "HSBW", "ENDCHAR", "HSTEMHM", "HINTMASK", "CNTRMASK", "RMOVETO",
        "HMOVETO", "VSTEMHM", "RCURVELINE", "RLINECURVE", "VVCURVETO",
        "HHCURVETO", "SHORTINT", "CALLGSUBR", "VHCURVETO", "HVCURVETO",
    )
    for name in one_byte_names:
        key = getattr(Key, name)
        CharStringCommand._CHAR_STRING_COMMANDS[key.hash_value] = (
            CharStringCommand(key.hash_value)
        )

    two_byte_pairs: tuple[tuple[str, int, int], ...] = (
        ("DOTSECTION", 12, 0), ("VSTEM3", 12, 1), ("HSTEM3", 12, 2),
        ("AND", 12, 3), ("OR", 12, 4), ("NOT", 12, 5),
        ("SEAC", 12, 6), ("SBW", 12, 7),
        ("ABS", 12, 9), ("ADD", 12, 10), ("SUB", 12, 11),
        ("DIV", 12, 12),
        ("NEG", 12, 14), ("EQ", 12, 15),
        ("CALLOTHERSUBR", 12, 16), ("POP", 12, 17), ("DROP", 12, 18),
        ("PUT", 12, 20), ("GET", 12, 21), ("IFELSE", 12, 22),
        ("RANDOM", 12, 23), ("MUL", 12, 24), ("SQRT", 12, 26),
        ("DUP", 12, 27), ("EXCH", 12, 28), ("INDEX", 12, 29),
        ("ROLL", 12, 30), ("SETCURRENTPOINT", 12, 33),
        ("HFLEX", 12, 34), ("FLEX", 12, 35),
        ("HFLEX1", 12, 36), ("FLEX1", 12, 37),
    )
    for name, b0, b1 in two_byte_pairs:
        key = getattr(Key, name)
        CharStringCommand._CHAR_STRING_COMMANDS[key.hash_value] = (
            CharStringCommand(b0, b1)
        )


_build_command_table()

CharStringCommand.COMMAND_CLOSEPATH = CharStringCommand.get_instance(
    Key.CLOSEPATH.hash_value
)
CharStringCommand.COMMAND_RLINETO = CharStringCommand.get_instance(
    Key.RLINETO.hash_value
)
CharStringCommand.COMMAND_HLINETO = CharStringCommand.get_instance(
    Key.HLINETO.hash_value
)
CharStringCommand.COMMAND_VLINETO = CharStringCommand.get_instance(
    Key.VLINETO.hash_value
)
CharStringCommand.COMMAND_RRCURVETO = CharStringCommand.get_instance(
    Key.RRCURVETO.hash_value
)
CharStringCommand.COMMAND_HSBW = CharStringCommand.get_instance(
    Key.HSBW.hash_value
)
CharStringCommand.COMMAND_CALLOTHERSUBR = CharStringCommand.get_instance(
    Key.CALLOTHERSUBR.hash_value
)
CharStringCommand.COMMAND_DIV = CharStringCommand.get_instance(
    Key.DIV.hash_value
)


__all__ = ["CharStringCommand"]
