from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Key:
    """Stable lookup key for a :class:`DictData` entry.

    Upstream's ``DictData`` keys its ``HashMap`` directly by
    ``operatorName : String``. There is no separate ``Key.java``; the
    "key" is just the operator's mnemonic. We add a thin wrapper so
    callers that want a value-typed lookup record (e.g. for parity with
    code that builds DICT entries from raw ``(b0, b1)`` byte pairs)
    have one. Pure string lookups still work: :meth:`DictData.get_entry`
    accepts either a ``str`` or a :class:`Key`.

    Upstream Java ref: the inner-class ``DictData`` (``CFFParser.java``
    lines 1308-1430) — there's no dedicated ``Key`` type, so this is a
    cosmetic addition kept compatible with upstream behaviour.
    """

    name: str

    def equals(self, other: object) -> bool:
        """PDFBox-style ``Object.equals`` parity helper."""
        return isinstance(other, Key) and other.name == self.name

    def hash_code(self) -> int:
        """PDFBox-style ``Object.hashCode`` parity helper."""
        return hash(self.name)

    def to_string(self) -> str:
        """PDFBox-style ``Object.toString`` parity helper."""
        return f"{type(self).__name__}[{self.name}]"

    def __str__(self) -> str:
        return self.name


@dataclass
class Entry:
    """A single CFF DICT entry: a list of operands followed by an
    operator (the operator's mnemonic, set when ``readEntry`` finishes
    consuming the operand stack).

    Mirrors upstream ``DictData.Entry`` (``CFFParser.java`` lines
    1361-1429). Method names are snake_cased per project rules.
    """

    operands: list[Any] = field(default_factory=list)
    operator_name: str | None = None

    def add_operand(self, operand: Any) -> None:
        """PDFBox: ``Entry.addOperand(Number)``
        (``CFFParser.java`` line 1395)."""
        self.operands.append(operand)

    def has_operands(self) -> bool:
        """PDFBox: ``Entry.hasOperands()``
        (``CFFParser.java`` line 1400)."""
        return len(self.operands) > 0

    def get_operands(self) -> list[Any]:
        """PDFBox: ``Entry.getOperands()``
        (``CFFParser.java`` line 1405). Live reference, not a copy
        (upstream returns the field directly)."""
        return self.operands

    def size(self) -> int:
        """PDFBox: ``Entry.size()``
        (``CFFParser.java`` line 1371)."""
        return len(self.operands)

    def get_number(self, index: int) -> Any:
        """PDFBox: ``Entry.getNumber(int)``
        (``CFFParser.java`` line 1366). Returns the operand at the
        given position; raises ``IndexError`` for out-of-range
        (upstream raises ``IndexOutOfBoundsException``)."""
        return self.operands[index]

    def get_boolean(self, index: int, default_value: bool | None) -> bool | None:
        """PDFBox: ``Entry.getBoolean(int, Boolean)``
        (``CFFParser.java`` lines 1376-1393).

        CFF integers used as booleans are 0 / 1; any other value (or a
        non-int) is reported via ``logger.warning`` and the supplied
        default returned.
        """
        operand = self.operands[index]
        if isinstance(operand, int) and not isinstance(operand, bool):
            if operand == 0:
                return False
            if operand == 1:
                return True
        logger.warning(
            "Expected boolean, got %r, returning default %r",
            operand,
            default_value,
        )
        return default_value

    def get_delta(self) -> list[Any]:
        """PDFBox: ``Entry.getDelta()``
        (``CFFParser.java`` lines 1410-1421). Materialise the delta-
        encoded operand list back into running-sum form.
        """
        result = list(self.operands)
        for i in range(1, len(result)):
            previous = result[i - 1]
            current = result[i]
            result[i] = int(previous) + int(current)
        return result

    def to_string(self) -> str:
        """PDFBox: ``Entry.toString()``
        (``CFFParser.java`` line 1423)."""
        return (
            f"{type(self).__name__}[operands={self.operands},"
            f" operator={self.operator_name}]"
        )


class DictData:
    """A parsed CFF Top DICT or Private DICT, keyed by operator name.

    Mirrors upstream ``DictData`` (``CFFParser.java`` lines 1308-1357).
    Method names are snake_cased; semantics — including the
    "skip entries with no operator name" guard in :meth:`add` — are
    preserved verbatim.
    """

    def __init__(self) -> None:
        # Upstream uses ``HashMap``; insertion order is unspecified. We
        # use a plain ``dict`` (insertion-ordered since Python 3.7),
        # which is a strict refinement: any code relying on upstream's
        # unordered behaviour stays correct.
        self._entries: dict[str, Entry] = {}

    def add(self, entry: Entry) -> None:
        """PDFBox: ``DictData.add(Entry)``
        (``CFFParser.java`` lines 1312-1318). Entries without an
        operator name are silently dropped (matches upstream)."""
        if entry.operator_name is not None:
            self._entries[entry.operator_name] = entry

    def get_entry(self, name: str | Key) -> Entry | None:
        """PDFBox: ``DictData.getEntry(String)``
        (``CFFParser.java`` lines 1320-1323). Accepts either a raw
        operator-name string (upstream form) or a :class:`Key`."""
        if isinstance(name, Key):
            name = name.name
        return self._entries.get(name)

    def get_boolean(self, name: str, default_value: bool) -> bool | None:
        """PDFBox: ``DictData.getBoolean(String, boolean)``
        (``CFFParser.java`` lines 1325-1329)."""
        entry = self.get_entry(name)
        if entry is not None and entry.has_operands():
            return entry.get_boolean(0, default_value)
        return default_value

    def get_array(
        self, name: str, default_value: list[Any] | None
    ) -> list[Any] | None:
        """PDFBox: ``DictData.getArray(String, List<Number>)``
        (``CFFParser.java`` lines 1331-1335)."""
        entry = self.get_entry(name)
        if entry is not None and entry.has_operands():
            return entry.get_operands()
        return default_value

    def get_number(self, name: str, default_value: Any) -> Any:
        """PDFBox: ``DictData.getNumber(String, Number)``
        (``CFFParser.java`` lines 1337-1341)."""
        entry = self.get_entry(name)
        if entry is not None and entry.has_operands():
            return entry.get_number(0)
        return default_value

    def get_delta(
        self, name: str, default_value: list[Any] | None
    ) -> list[Any] | None:
        """PDFBox: ``DictData.getDelta(String, List<Number>)``
        (``CFFParser.java`` lines 1343-1347)."""
        entry = self.get_entry(name)
        if entry is not None and entry.has_operands():
            return entry.get_delta()
        return default_value

    @property
    def entries(self) -> dict[str, Entry]:
        """Live entry map view. Not present upstream (the field is
        package-private), but exposed for parity tests / debugging."""
        return self._entries

    def to_string(self) -> str:
        """PDFBox: ``DictData.toString()``
        (``CFFParser.java`` line 1352)."""
        return f"{type(self).__name__}[entries={self._entries}]"

    def __repr__(self) -> str:
        return self.to_string()


__all__ = ["DictData", "Entry", "Key"]
