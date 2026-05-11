from __future__ import annotations

from typing import Any

# Mirrors upstream ``COSObjectKey``:
#   numberAndGeneration packs ``num`` in the high bits and ``gen`` in the
#   low 16 bits. We keep the same encoding so ``getInternalHash`` /
#   ``compareTo`` produce identical orderings.
_NUMBER_OFFSET: int = 16
_GENERATION_MASK: int = (1 << _NUMBER_OFFSET) - 1


class COSObjectKey:
    """Value type identifying an indirect PDF object by ``(num, gen, index)``.

    Used as the key in ``COSDocument``'s object pool / xref table. Frozen
    so it can be a dict key; ordered so callers can sort objects by
    number for serialization. Mirrors
    ``org.apache.pdfbox.cos.COSObjectKey``.
    """

    __slots__ = ("_number_and_generation", "_stream_index", "__weakref__")

    def __init__(
        self,
        num: int,
        gen: int = 0,
        index: int = -1,
    ) -> None:
        if num < 0:
            raise ValueError("Object number must not be a negative value")
        if gen < 0:
            raise ValueError("Generation number must not be a negative value")
        # Match upstream Java (COSObjectKey.java) — no strict 16-bit guard
        # at construction time; the writer enforces it on serialization.
        object.__setattr__(self, "_number_and_generation", self.compute_internal_hash(num, gen))
        object.__setattr__(self, "_stream_index", index)

    # ------------------------------------------------------------------
    # Static helpers
    # ------------------------------------------------------------------

    @staticmethod
    def compute_internal_hash(num: int, gen: int) -> int:
        """Calculate the internal hash for the given ``(num, gen)`` pair.

        Mirrors upstream ``COSObjectKey.computeInternalHash`` (Java line 75).
        """
        return (num << _NUMBER_OFFSET) | (gen & _GENERATION_MASK)

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    def get_internal_hash(self) -> int:
        """Return the packed ``number << 16 | generation`` value.

        Mirrors upstream ``COSObjectKey.getInternalHash`` (Java line 85).
        """
        return self._number_and_generation

    def get_number(self) -> int:
        """Object number (the part before ``R`` in a PDF reference).

        Mirrors upstream ``COSObjectKey.getNumber`` (Java line 116).
        """
        # ``>>>`` in Java; our long is already unsigned so a plain shift works.
        return self._number_and_generation >> _NUMBER_OFFSET

    def get_generation(self) -> int:
        """Object generation number.

        Mirrors upstream ``COSObjectKey.getGeneration`` (Java line 106).
        """
        return self._number_and_generation & _GENERATION_MASK

    def get_stream_index(self) -> int:
        """Index within a compressed object stream, or ``-1`` if not in one.

        Mirrors upstream ``COSObjectKey.getStreamIndex`` (Java line 126).
        """
        return self._stream_index

    # ------------------------------------------------------------------
    # Backwards-compat aliases for the dataclass-style attributes that
    # earlier waves of pypdfbox exposed. Read-only; mutation goes through
    # the constructor.
    # ------------------------------------------------------------------

    @property
    def object_number(self) -> int:
        return self.get_number()

    @property
    def generation_number(self) -> int:
        return self.get_generation()

    @property
    def stream_index(self) -> int:
        return self.get_stream_index()

    # ------------------------------------------------------------------
    # Dunder methods — equality on (num, gen) only, matching upstream
    # ``equals`` which compares ``numberAndGeneration``.
    # ------------------------------------------------------------------

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, COSObjectKey):
            return NotImplemented
        return self._number_and_generation == other._number_and_generation

    def __ne__(self, other: object) -> bool:
        result = self.__eq__(other)
        if result is NotImplemented:
            return result
        return not result

    def __hash__(self) -> int:
        return hash(self._number_and_generation)

    def __lt__(self, other: Any) -> bool:
        if not isinstance(other, COSObjectKey):
            return NotImplemented
        return self._number_and_generation < other._number_and_generation

    def __le__(self, other: Any) -> bool:
        if not isinstance(other, COSObjectKey):
            return NotImplemented
        return self._number_and_generation <= other._number_and_generation

    def __gt__(self, other: Any) -> bool:
        if not isinstance(other, COSObjectKey):
            return NotImplemented
        return self._number_and_generation > other._number_and_generation

    def __ge__(self, other: Any) -> bool:
        if not isinstance(other, COSObjectKey):
            return NotImplemented
        return self._number_and_generation >= other._number_and_generation

    def __str__(self) -> str:
        return f"{self.get_number()} {self.get_generation()} R"

    def __repr__(self) -> str:
        return (
            f"COSObjectKey(num={self.get_number()}, gen={self.get_generation()}, "
            f"index={self._stream_index})"
        )

    def equals(self, other: object) -> bool:
        """Java-name parity alias for ``__eq__``.

        Mirrors upstream ``COSObjectKey.equals`` (Java line 94).
        """
        return self.__eq__(other) is True

    def hash_code(self) -> int:
        """Java-name parity alias for ``__hash__``.

        Mirrors upstream ``COSObjectKey.hashCode`` (Java line 135).
        """
        return hash(self)

    def to_string(self) -> str:
        """Java-name parity alias for ``__str__``.

        Mirrors upstream ``COSObjectKey.toString`` (Java line 141).
        """
        return str(self)

    def compare_to(self, other: COSObjectKey) -> int:
        """Compare two keys. Mirrors upstream
        ``COSObjectKey.compareTo`` (Java line 147)."""
        a = self._number_and_generation
        b = other._number_and_generation
        return (a > b) - (a < b)
