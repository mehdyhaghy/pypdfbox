from __future__ import annotations

from collections.abc import Iterator, Sequence

from .bf_char_entry import BFCharEntry


def _to_int(data: bytes) -> int:
    code = 0
    for b in data:
        code = (code << 8) | (b & 0xFF)
    return code


def _bytes_for_code(code: int, length: int) -> bytes:
    out = bytearray(length)
    for i in range(length - 1, -1, -1):
        out[i] = code & 0xFF
        code >>= 8
    return bytes(out)


def _increment_string(value: str) -> str:
    """Increment the last code unit of a Unicode string by one.

    Mirrors the Adobe ToUnicode CMap behaviour where a ``bfrange`` whose
    target is a single string maps consecutive input codes to consecutive
    Unicode strings (only the last code unit is bumped).
    """
    if not value:
        return value
    head = value[:-1]
    tail = ord(value[-1]) + 1
    return head + chr(tail)


class BFCharRange:
    """
    A ``bfrange`` entry from a ToUnicode CMap.

    Upstream Apache PDFBox does not expose a ``BFCharRange`` class — the
    parser inlines ``bfrange`` triples directly into a series of
    ``CMap.addCharMapping`` calls (see
    ``CMapParser.addMappingFrombfrange``). pypdfbox adds this typed value
    object so callers building or analysing CMaps can carry a whole
    range without first expanding it.

    Two flavours, matching upstream parser logic:

    * **Single target string**: ``bfrange <0000> <0010> <0041>`` — every
      code in ``[start, end]`` maps to a Unicode string formed by
      bumping the last code unit of the target. ``targets`` is then
      ``None``.
    * **Explicit array of targets**: ``bfrange <0000> <0010> [<0041>
      <0042> ...]`` — ``targets`` lists one Unicode string per code.

    Iterating a ``BFCharRange`` yields the contained ``BFCharEntry``
    objects in order — convenient when feeding ``CMap.add_char_mapping``.
    """

    __slots__ = ("_start", "_end", "_target", "_targets", "_code_length")

    def __init__(
        self,
        start: bytes | bytearray | memoryview,
        end: bytes | bytearray | memoryview,
        target: str | None = None,
        targets: Sequence[str] | None = None,
    ) -> None:
        """
        :param start: raw start-code bytes.
        :param end: raw end-code bytes (must be the same length as ``start``).
        :param target: single Unicode target string; ``None`` if
            ``targets`` is supplied.
        :param targets: explicit per-code target strings; mutually
            exclusive with ``target``.
        :raises ValueError: when ``start``/``end`` lengths differ, the
            range is empty, or both/neither of ``target``/``targets`` is
            supplied.
        """
        s = bytes(start)
        e = bytes(end)
        if len(s) != len(e):
            raise ValueError(
                "bfrange start and end must have equal byte length"
            )
        if not 1 <= len(s) <= 4:
            raise ValueError(
                f"bfrange code length must be 1-4 bytes, got {len(s)}"
            )
        if (target is None) == (targets is None):
            raise ValueError(
                "bfrange requires exactly one of `target` or `targets`"
            )
        if _to_int(e) < _to_int(s):
            raise ValueError("bfrange end must be >= start")

        self._start = s
        self._end = e
        self._code_length = len(s)
        self._target = target
        self._targets = tuple(targets) if targets is not None else None

        if self._targets is not None:
            expected = _to_int(e) - _to_int(s) + 1
            if len(self._targets) < expected:
                raise ValueError(
                    f"bfrange target list too short: need {expected}, "
                    f"got {len(self._targets)}"
                )

    # ---------- accessors ----------

    def get_start(self) -> bytes:
        """Raw start-code bytes."""
        return self._start

    def get_end(self) -> bytes:
        """Raw end-code bytes."""
        return self._end

    def get_target(self) -> str | None:
        """Single Unicode target, or ``None`` for explicit-array form."""
        return self._target

    def get_targets(self) -> tuple[str, ...] | None:
        """Explicit per-code target list, or ``None`` for single-target form."""
        return self._targets

    def get_code_length(self) -> int:
        """Byte length of the input codes."""
        return self._code_length

    def size(self) -> int:
        """Number of code -> Unicode mappings represented by this range."""
        return _to_int(self._end) - _to_int(self._start) + 1

    # ---------- expansion ----------

    def entries(self) -> list[BFCharEntry]:
        """Materialise this range into a list of ``BFCharEntry`` objects."""
        return list(self)

    def __iter__(self) -> Iterator[BFCharEntry]:
        start = _to_int(self._start)
        end = _to_int(self._end)
        length = self._code_length
        if self._targets is not None:
            for i, code in enumerate(range(start, end + 1)):
                yield BFCharEntry(
                    _bytes_for_code(code, length), self._targets[i]
                )
        else:
            current_target = self._target
            assert current_target is not None  # narrowed by __init__
            for code in range(start, end + 1):
                yield BFCharEntry(_bytes_for_code(code, length), current_target)
                current_target = _increment_string(current_target)

    # ---------- equality ----------

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, BFCharRange):
            return NotImplemented
        return (
            self._start == other._start
            and self._end == other._end
            and self._target == other._target
            and self._targets == other._targets
        )

    def __hash__(self) -> int:
        return hash((self._start, self._end, self._target, self._targets))

    def __repr__(self) -> str:
        if self._target is not None:
            return (
                f"BFCharRange(<{self._start.hex().upper()}>"
                f"-<{self._end.hex().upper()}> -> {self._target!r})"
            )
        return (
            f"BFCharRange(<{self._start.hex().upper()}>"
            f"-<{self._end.hex().upper()}> -> {list(self._targets or ())!r})"
        )
