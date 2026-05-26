from __future__ import annotations

import datetime as _dt
import re as _re
from collections.abc import (
    Callable,
    Collection,
    ItemsView,
    Iterable,
    Iterator,
    KeysView,
    ValuesView,
)
from typing import Any

from .cos_array import COSArray
from .cos_base import COSBase
from .cos_boolean import COSBoolean
from .cos_float import COSFloat
from .cos_integer import COSInteger
from .cos_name import COSName
from .cos_null import COSNull
from .cos_object import COSObject
from .cos_object_key import COSObjectKey
from .cos_string import COSString
from .cos_update_state import COSUpdateState
from .i_cos_visitor import ICOSVisitor

# Sentinel for "no default supplied" — distinguishes from a caller-passed None.
_MISSING: Any = object()

# Lenient PDF-date string parser used by ``get_date`` / ``get_embedded_date``.
# Mirrors the subset accepted by ``org.apache.pdfbox.util.DateConverter``.
_PDF_DATE_RE = _re.compile(
    r"""
    ^D?:?
    (?P<year>\d{4})
    (?P<month>\d{2})?
    (?P<day>\d{2})?
    (?P<hour>\d{2})?
    (?P<minute>\d{2})?
    (?P<second>\d{2})?
    (?:
        (?P<offsign>Z|[+\-])
        (?P<offhour>\d{2})?
        '?
        (?P<offminute>\d{2})?
        '?
    )?
    $
    """,
    _re.VERBOSE,
)


def _as_name(key: COSName | str) -> COSName:
    """Normalize string keys to interned ``COSName`` for storage."""
    if isinstance(key, COSName):
        return key
    if isinstance(key, str):
        return COSName.get_pdf_name(key)
    raise TypeError(f"key must be COSName or str, got {type(key).__name__}")


def _parse_pdf_date(value: str) -> _dt.datetime | None:
    """Best-effort parse of a PDF date string ``D:YYYYMMDDHHmmSSOHH'mm'``.

    Returns ``None`` if the string is unparseable. Mirrors the lenient
    behavior of ``DateConverter.toCalendar`` for the common subset.
    """
    if not value:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    m = _PDF_DATE_RE.match(stripped)
    if m is None:
        return None
    year = int(m.group("year"))
    month = int(m.group("month") or 1)
    day = int(m.group("day") or 1)
    hour = int(m.group("hour") or 0)
    minute = int(m.group("minute") or 0)
    second = int(m.group("second") or 0)
    # Upstream ``DateConverter.toCalendar`` parses with
    # ``GregorianCalendar.setLenient(false)``, so an out-of-range field
    # (e.g. second 60 from a misencoded leap second, or hour 24) makes the
    # whole parse fail and the method returns ``null``. We mirror that: the
    # ``datetime(...)`` constructor below raises ``ValueError`` for any
    # out-of-range field, which we map to ``None`` — including second == 60
    # (Python's ``datetime`` has no leap-second slot). Do NOT clamp.
    sign = m.group("offsign")
    if sign is None or sign == "Z":
        tz: _dt.tzinfo = _dt.UTC
    else:
        off_hour = int(m.group("offhour") or 0)
        off_minute = int(m.group("offminute") or 0)
        # Upstream builds the zone via ``SimpleTimeZone`` from a raw
        # millisecond offset and lets ``Calendar.ZONE_OFFSET`` reduce it into
        # ``(-24h, +24h)``. An out-of-range designation like ``+24'00'`` or
        # ``+99'00'`` therefore does NOT fail the parse — it wraps modulo
        # 24 hours (truncating toward zero, Java ``%`` semantics) rather than
        # raising. Python's ``timezone`` rejects ``|offset| >= 24h``, so we
        # apply the same reduction before constructing it.
        total_minutes = off_hour * 60 + off_minute
        if sign == "-":
            total_minutes = -total_minutes
        # Java integer ``%`` truncates toward zero (``math.fmod`` for ints):
        # -5940 % 1440 == -180, +5940 % 1440 == +180, matching PDFBox's
        # GMT-zone reduction (e.g. -99'00' → -03:00, +99'00' → +03:00).
        reduced = total_minutes - 1440 * int(total_minutes / 1440)
        delta = _dt.timedelta(minutes=reduced)
        tz = _dt.timezone(delta)
    try:
        return _dt.datetime(year, month, day, hour, minute, second, tzinfo=tz)
    except ValueError:
        return None


def _format_pdf_date(value: _dt.date | _dt.datetime | str | None) -> str | None:
    if value is None or isinstance(value, str):
        return value
    if isinstance(value, _dt.datetime):
        base = value.strftime("D:%Y%m%d%H%M%S")
        if value.tzinfo is None or value.utcoffset() is None:
            return base
        offset = value.utcoffset() or _dt.timedelta()
        if offset == _dt.timedelta():
            return base + "Z"
        sign = "+" if offset >= _dt.timedelta() else "-"
        offset = abs(offset)
        total_minutes = int(offset.total_seconds() // 60)
        hours, minutes = divmod(total_minutes, 60)
        return f"{base}{sign}{hours:02d}'{minutes:02d}'"
    if isinstance(value, _dt.date):
        return value.strftime("D:%Y%m%d000000")
    if hasattr(value, "strftime"):
        return value.strftime("D:%Y%m%d%H%M%S")
    raise TypeError(f"date must be date, datetime, str, or None, got {type(value).__name__}")


def _add_to_collection(collection: Collection[Any], item: Any) -> None:
    """Append ``item`` to ``collection`` using whichever mutator is
    available (``add`` for sets, ``append`` for lists). Mirrors
    upstream's ``Collection.add`` polymorphism."""
    add = getattr(collection, "add", None)
    if add is not None:
        add(item)
        return
    append = getattr(collection, "append", None)
    if append is not None:
        append(item)


def _array_get_indirect_object_keys(
    array: COSArray, indirect_objects: Collection[COSObjectKey]
) -> None:
    """Inline traversal of a ``COSArray`` for ``get_indirect_object_keys``.

    Lives here (not on ``COSArray``) because ``cos_array.py`` is
    wave-locked and we cannot extend it in this slice.
    """
    for value in array:
        child: COSBase | None = value
        indirect_key: COSObjectKey | None = None
        if isinstance(child, COSObject):
            indirect_key = COSObjectKey(child.object_number, child.generation_number)
            if indirect_key in indirect_objects:
                continue
            child = child.get_object()
        if isinstance(child, COSDictionary):
            child.get_indirect_object_keys(indirect_objects)
        elif isinstance(child, COSArray):
            _array_get_indirect_object_keys(child, indirect_objects)
        elif indirect_key is not None:
            _add_to_collection(indirect_objects, indirect_key)


def _array_reset_object_keys(
    array: COSArray, indirect_objects: Collection[COSObjectKey]
) -> None:
    """Inline traversal of a ``COSArray`` for ``reset_object_keys``."""
    for value in array:
        child: COSBase | None = value
        indirect_key: COSObjectKey | None = None
        if isinstance(child, COSObject):
            indirect_key = COSObjectKey(child.object_number, child.generation_number)
            if indirect_key in indirect_objects:
                continue
            child = child.get_object()
        if isinstance(child, COSDictionary):
            child.reset_object_keys(indirect_objects)
        elif isinstance(child, COSArray):
            _array_reset_object_keys(child, indirect_objects)
        elif indirect_key is not None:
            _add_to_collection(indirect_objects, indirect_key)


def _get_dictionary_string(base: COSBase | None, objs: list[COSBase]) -> str:
    """Format ``base`` for ``COSDictionary.to_string``.

    Mirrors the upstream private static helper of the same name (Java
    line 1361). Tracks visited bases in ``objs`` to break cycles.
    """
    # Local import to avoid a hard cos_dictionary→cos_stream cycle at
    # module load (COSStream subclasses COSDictionary).
    from .cos_stream import COSStream  # noqa: PLC0415

    if base is None:
        return "null"
    if any(b is base for b in objs):
        return f"hash:{id(base)}"
    if isinstance(base, COSDictionary):
        objs.append(base)
        parts = ["COSDictionary{"]
        for k, v in base.entry_set():
            parts.append(f"{k!s}:{_get_dictionary_string(v, objs)};")
        parts.append("}")
        if isinstance(base, COSStream):
            try:
                with base.create_raw_input_stream() as raw:
                    data = raw.read()
                parts.append(f"COSStream{{{hash(bytes(data))}}}")
            except Exception:  # pragma: no cover - defensive parity
                pass
        return "".join(parts)
    if isinstance(base, COSArray):
        objs.append(base)
        parts = ["COSArray{"]
        for v in base:
            parts.append(f"{_get_dictionary_string(v, objs)};")
        parts.append("}")
        return "".join(parts)
    if isinstance(base, COSObject):
        objs.append(base)
        inner: COSBase | None = COSNull.NULL if base.is_object_null() else base.get_object()
        return f"COSObject{{{_get_dictionary_string(inner, objs)}}}"
    return repr(base)


class COSDictionary(COSBase):
    """
    PDF dictionary — ordered ``COSName → COSBase`` map. Insertion order is
    preserved (Python 3.7+ ``dict`` semantics) so the writer can round-trip
    keys in their original sequence.

    String keys are accepted everywhere a ``COSName`` is expected and are
    normalized to interned ``COSName`` instances internally.
    """

    def __init__(self, items: Iterable[tuple[COSName | str, COSBase]] | None = None) -> None:
        super().__init__()
        self._items: dict[COSName, COSBase] = {}
        self._update_state = COSUpdateState(self)
        if items is not None:
            for k, v in items:
                self.set_item(k, v)

    # ---------- core map operations ----------

    def set_item(self, key: COSName | str, value: COSBase | None) -> None:
        if value is None:
            self.remove_item(key)
        else:
            self._items[_as_name(key)] = value
            self._update_state.update(child=value)

    def _set_item_quiet(self, key: COSName | str, value: COSBase) -> None:
        """Set an internal/cache-created entry without marking it dirty."""
        self._items[_as_name(key)] = value
        self._update_state.dereference_child(value)

    def remove_item(self, key: COSName | str) -> COSBase | None:
        item = self._items.pop(_as_name(key), None)
        if item is not None:
            self._update_state.update()
        return item

    def get_item(
        self, key: COSName | str, default: COSBase | COSName | str | None = None
    ) -> COSBase | None:
        """Raw entry — may be a ``COSObject`` indirect reference.

        When ``default`` is a ``COSName`` or ``str``, it is treated as PDFBox's
        second-key overload and returns that raw item only if the first key is
        absent.
        """
        item = self._items.get(_as_name(key))
        if item is not None:
            return item
        if isinstance(default, (COSName, str)):
            return self._items.get(_as_name(default))
        return default

    def _resolve_item(self, key: COSName | str) -> COSBase | None:
        item = self._items.get(_as_name(key))
        if item is None:
            return None
        if isinstance(item, COSObject):
            item = item.get_object()
        if item is COSNull.NULL:
            return None
        return item

    def get_dictionary_object(
        self, key: COSName | str, default: COSBase | COSName | str | None = None
    ) -> COSBase | None:
        """Resolved entry — dereferences ``COSObject`` if needed.

        When ``default`` is a ``COSName`` or ``str``, it is treated as PDFBox's
        second-key overload and is resolved only if the first key is absent or
        resolves to ``COSNull``.
        """
        item = self._resolve_item(key)
        if item is not None:
            return item
        if isinstance(default, (COSName, str)):
            return self._resolve_item(default)
        return default

    def contains_key(self, key: COSName | str) -> bool:
        return _as_name(key) in self._items

    def contains_value(self, value: object) -> bool:
        """Return true if any entry stores ``value``.

        Mirrors PDFBox ``COSDictionary.containsValue`` and uses normal
        value equality, just like Java's ``Map.containsValue``.
        """
        return value in self._items.values()

    def get_key_for_value(self, value: object) -> COSName | None:
        """Return the first key whose value equals ``value``, if any.

        Dictionary insertion order is preserved, so "first" is deterministic
        and matches the order used when writing or iterating the dictionary.
        """
        for key, item in self._items.items():
            if item == value:
                return key
        return None

    def clear_item(self, key: COSName | str) -> None:
        """Remove ``key`` if present."""
        self.remove_item(key)

    def size(self) -> int:
        return len(self._items)

    def is_empty(self) -> bool:
        return not self._items

    def clear(self) -> None:
        if self._items:
            self._items.clear()
            self._update_state.update()

    def key_set(self) -> KeysView[COSName]:
        return self._items.keys()

    def values(self) -> ValuesView[COSBase]:
        return self._items.values()

    def entry_set(self) -> ItemsView[COSName, COSBase]:
        return self._items.items()

    def add_all(self, other: COSDictionary) -> None:
        """Merge ``other`` into self, overwriting keys present in both."""
        if other._items:
            self._items.update(other._items)
            self._update_state.update(children=other._items.values())

    def get_update_state(self) -> COSUpdateState:
        return self._update_state

    def is_needs_to_be_updated(self) -> bool:
        return self._update_state.is_updated()

    def set_needs_to_be_updated(self, value: bool) -> None:
        self._update_state.update(value)

    # ---------- typed convenience setters ----------

    def set_name(self, key: COSName | str, value: str | None) -> None:
        if value is None:
            self.remove_item(key)
        else:
            self.set_item(key, COSName.get_pdf_name(value))

    def set_string(self, key: COSName | str, value: str | bytes | None) -> None:
        if value is None:
            self.remove_item(key)
        else:
            self.set_item(key, COSString(value))

    def set_int(self, key: COSName | str, value: int) -> None:
        self.set_item(key, COSInteger.get(value))

    def set_long(self, key: COSName | str, value: int) -> None:
        """Store an integer value under ``key``. Mirrors PDFBox ``setLong``."""
        self.set_item(key, COSInteger.get(value))

    def set_float(self, key: COSName | str, value: float) -> None:
        self.set_item(key, COSFloat(value))

    def set_boolean(self, key: COSName | str, value: bool) -> None:
        self.set_item(key, COSBoolean.get(value))

    def set_date(
        self,
        key: COSName | str,
        value: _dt.date | _dt.datetime | str | None,
    ) -> None:
        self.set_string(key, _format_pdf_date(value))

    def set_embedded_date(
        self,
        embedded: COSName | str,
        key: COSName | str,
        value: _dt.date | _dt.datetime | str | None,
    ) -> None:
        self.set_embedded_string(embedded, key, _format_pdf_date(value))

    def set_embedded_string(
        self,
        embedded: COSName | str,
        key: COSName | str,
        value: str | bytes | None,
    ) -> None:
        dictionary = self.get_cos_dictionary(embedded)
        if dictionary is None and value is not None:
            dictionary = COSDictionary()
            self.set_item(embedded, dictionary)
        if dictionary is not None:
            dictionary.set_string(key, value)

    def set_embedded_int(self, embedded: COSName | str, key: COSName | str, value: int) -> None:
        dictionary = self.get_cos_dictionary(embedded)
        if dictionary is None:
            dictionary = COSDictionary()
            self.set_item(embedded, dictionary)
        dictionary.set_int(key, value)

    def set_flag(self, key: COSName | str, bit_flag: int, value: bool) -> None:
        flags = self.get_int(key, 0)
        if value:
            flags |= bit_flag
        else:
            flags &= ~bit_flag
        self.set_int(key, flags)

    def get_flag(self, key: COSName | str, bit_flag: int) -> bool:
        return (self.get_int(key, 0) & bit_flag) == bit_flag

    # ---------- typed convenience getters ----------

    def get_string(self, key: COSName | str, default: str | None = None) -> str | None:
        v = self.get_dictionary_object(key)
        if isinstance(v, COSString):
            return v.get_string()
        if isinstance(v, COSName):
            return v.name
        return default

    def has_string(self, key: COSName | str) -> bool:
        """Return true when ``key`` resolves to a string-like COS value."""
        return isinstance(self.get_dictionary_object(key), (COSString, COSName))

    def clear_string(self, key: COSName | str) -> None:
        self.clear_item(key)

    def get_name(self, key: COSName | str, default: str | None = None) -> str | None:
        v = self.get_dictionary_object(key)
        if isinstance(v, COSName):
            return v.name
        return default

    def get_name_as_string(
        self, key: COSName | str, default: str | None = None
    ) -> str | None:
        """Return a name-like value as text.

        Mirrors PDFBox ``COSDictionary.getNameAsString``: names return their
        PDF name, strings return their decoded string, and other shapes fall
        back to ``default``.
        """
        return self.get_string(key, default)

    def has_name(self, key: COSName | str) -> bool:
        return isinstance(self.get_dictionary_object(key), COSName)

    def clear_name(self, key: COSName | str) -> None:
        self.clear_item(key)

    def get_int(
        self, key: COSName | str, default: int | COSName | str = -1, fallback: int = -1
    ) -> int:
        if isinstance(default, (COSName, str)):
            v = self.get_dictionary_object(key, default)
            default_value = fallback
        else:
            v = self.get_dictionary_object(key)
            default_value = default
        if isinstance(v, COSInteger):
            return v.value
        if isinstance(v, COSFloat):
            return int(v.value)
        return default_value

    def has_int(self, key: COSName | str) -> bool:
        return isinstance(self.get_dictionary_object(key), (COSInteger, COSFloat))

    def clear_int(self, key: COSName | str) -> None:
        self.clear_item(key)

    def get_long(
        self, key: COSName | str, default: int | COSName | str = -1, fallback: int = -1
    ) -> int:
        """Return a numeric value as an integer, or ``default`` if absent.

        Python has a single unbounded ``int`` type, so this mirrors PDFBox's
        ``getLong`` contract while sharing the same COS storage as integers.
        """
        if isinstance(default, (COSName, str)):
            v = self.get_dictionary_object(key, default)
            default_value = fallback
        else:
            v = self.get_dictionary_object(key)
            default_value = default
        if isinstance(v, (COSInteger, COSFloat)):
            return v.long_value()
        return default_value

    def has_long(self, key: COSName | str) -> bool:
        return isinstance(self.get_dictionary_object(key), (COSInteger, COSFloat))

    def clear_long(self, key: COSName | str) -> None:
        self.clear_item(key)

    def get_float(
        self, key: COSName | str, default: float | COSName | str = -1.0, fallback: float = -1.0
    ) -> float:
        if isinstance(default, (COSName, str)):
            v = self.get_dictionary_object(key, default)
            default_value = fallback
        else:
            v = self.get_dictionary_object(key)
            default_value = default
        if isinstance(v, (COSInteger, COSFloat)):
            return float(v.value)
        return default_value

    def has_float(self, key: COSName | str) -> bool:
        return isinstance(self.get_dictionary_object(key), (COSInteger, COSFloat))

    def clear_float(self, key: COSName | str) -> None:
        self.clear_item(key)

    def get_boolean(
        self, key: COSName | str, default: bool | COSName | str = False, fallback: bool = False
    ) -> bool:
        if isinstance(default, (COSName, str)):
            v = self.get_dictionary_object(key, default)
            default_value = fallback
        else:
            v = self.get_dictionary_object(key)
            default_value = default
        if isinstance(v, COSBoolean):
            return v.value
        return default_value

    def has_boolean(self, key: COSName | str) -> bool:
        return isinstance(self.get_dictionary_object(key), COSBoolean)

    def clear_boolean(self, key: COSName | str) -> None:
        self.clear_item(key)

    def get_cos_dictionary(self, key: COSName | str) -> COSDictionary | None:
        """Return the resolved value as a ``COSDictionary`` when present.

        Mirrors PDFBox ``COSDictionary.getCOSDictionary`` while keeping the
        local snake_case API style.
        """
        v = self.get_dictionary_object(key)
        if isinstance(v, COSDictionary):
            return v
        return None

    def has_cos_dictionary(self, key: COSName | str) -> bool:
        return isinstance(self.get_dictionary_object(key), COSDictionary)

    def clear_cos_dictionary(self, key: COSName | str) -> None:
        self.clear_item(key)

    def get_cos_array(self, key: COSName | str) -> COSArray | None:
        """Return the resolved value as a ``COSArray`` when present.

        Mirrors PDFBox ``COSDictionary.getCOSArray`` while keeping the local
        snake_case API style.
        """
        v = self.get_dictionary_object(key)
        if isinstance(v, COSArray):
            return v
        return None

    def has_cos_array(self, key: COSName | str) -> bool:
        return isinstance(self.get_dictionary_object(key), COSArray)

    def clear_cos_array(self, key: COSName | str) -> None:
        self.clear_item(key)

    def as_unmodifiable_dictionary(self) -> COSDictionary:
        """Return a live, read-only view of this dictionary.

        Mirrors PDFBox ``asUnmodifiableDictionary``: the view shares the
        backing entries with the source dictionary, so later source mutations
        are visible through the view, while mutating the view raises.
        """
        return UnmodifiableCOSDictionary(self)

    # ---------- typed COS-object accessors ----------

    def get_cos_name(
        self, key: COSName | str, default: COSName | None = None
    ) -> COSName | None:
        """Return the resolved value as a ``COSName`` when present.

        Mirrors PDFBox ``COSDictionary.getCOSName`` (Java lines 522, 626):
        the two-arg overload returns ``default`` when the entry is absent
        or not a name.
        """
        v = self.get_dictionary_object(key)
        if isinstance(v, COSName):
            return v
        return default

    def get_cos_object(
        self, key: COSName | str | None = None
    ) -> COSObject | COSDictionary | None:
        """Two-mode accessor (Java overload collapse).

        * ``get_cos_object()`` — return ``self``, satisfying the
          ``COSObjectable`` contract (Java's inherited
          ``COSObjectable.getCOSObject()``).
        * ``get_cos_object(key)`` — return the raw entry as a
          ``COSObject`` indirect reference (Java line 539). Unlike
          ``get_dictionary_object``, this does **not** dereference — it
          exposes the indirect-reference holder itself.
        """
        if key is None:
            return self
        item = self.get_item(key)
        if isinstance(item, COSObject):
            return item
        return None

    def get_cos_stream(self, key: COSName | str) -> Any:
        """Return the resolved value as a ``COSStream`` when present.

        Mirrors PDFBox ``COSDictionary.getCOSStream`` (Java line 591).
        """
        # Local import to avoid a hard cos_dictionary→cos_stream cycle at
        # module load (COSStream subclasses COSDictionary).
        from .cos_stream import COSStream  # noqa: PLC0415

        v = self.get_dictionary_object(key)
        if isinstance(v, COSStream):
            return v
        return None

    # ---------- date / embedded helpers ----------

    def get_date(
        self,
        key: COSName | str,
        default: _dt.datetime | None = None,
    ) -> _dt.datetime | None:
        """Return the entry parsed as a ``datetime`` or ``default``.

        Mirrors PDFBox ``COSDictionary.getDate`` (Java lines 797, 826).
        Returns ``default`` if the entry is absent, not a ``COSString``,
        or is not a parseable PDF date.
        """
        v = self.get_dictionary_object(key)
        if isinstance(v, COSString):
            parsed = _parse_pdf_date(v.get_string())
            if parsed is not None:
                return parsed
        return default

    def get_embedded_string(
        self,
        embedded: COSName | str,
        key: COSName | str,
        default: str | None = None,
    ) -> str | None:
        """Lookup ``key`` inside the dictionary stored under ``embedded``.

        Mirrors PDFBox ``COSDictionary.getEmbeddedString`` (Java lines
        770, 784).
        """
        dictionary = self.get_cos_dictionary(embedded)
        return dictionary.get_string(key, default) if dictionary is not None else default

    def get_embedded_int(
        self,
        embedded: COSName | str,
        key: COSName | str,
        default: int = -1,
    ) -> int:
        """Lookup ``key`` inside the dictionary stored under ``embedded``.

        Mirrors PDFBox ``COSDictionary.getEmbeddedInt`` (Java lines 933,
        947).
        """
        dictionary = self.get_cos_dictionary(embedded)
        return dictionary.get_int(key, default) if dictionary is not None else default

    def get_embedded_date(
        self,
        embedded: COSName | str,
        key: COSName | str,
        default: _dt.datetime | None = None,
    ) -> _dt.datetime | None:
        """Lookup a date entry inside the dictionary stored under
        ``embedded``. Mirrors PDFBox ``COSDictionary.getEmbeddedDate``
        (Java lines 856, 870).
        """
        dictionary = self.get_cos_dictionary(embedded)
        return dictionary.get_date(key, default) if dictionary is not None else default

    # ---------- iteration / paths / indirect-key bookkeeping ----------

    def for_each(
        self, action: Callable[[COSName, COSBase], None]
    ) -> None:
        """Apply ``action(name, value)`` to each entry in insertion order.

        Mirrors PDFBox ``COSDictionary.forEach`` (Java line 1248).
        """
        for k, v in self._items.items():
            action(k, v)

    def get_values(self) -> ValuesView[COSBase]:
        """Return all values in this dictionary.

        Mirrors PDFBox ``COSDictionary.getValues`` (Java line 1258).
        """
        return self._items.values()

    def get_object_from_path(self, obj_path: str) -> COSBase | None:
        """Walk a ``/``-separated path through nested dictionaries and
        arrays. Array indices appear as bare ``[k]`` segments where ``k``
        is the integer index. Mirrors PDFBox
        ``COSDictionary.getObjectFromPath`` (Java line 1315).
        """
        retval: COSBase | None = self
        for segment in obj_path.split("/"):
            if isinstance(retval, COSArray):
                idx = int(segment.replace("[", "").replace("]", ""))
                retval = retval.get_object(idx)
            elif isinstance(retval, COSDictionary):
                retval = retval.get_dictionary_object(segment)
            else:
                return None
        return retval

    def get_indirect_object_keys(
        self, indirect_objects: Collection[COSObjectKey] | None
    ) -> None:
        """Collect ``COSObjectKey``s for every indirect object reachable
        from this dictionary into ``indirect_objects``. Mirrors PDFBox
        ``COSDictionary.getIndirectObjectKeys`` (Java line 1454). Pass an
        already-populated collection to short-circuit on revisits.

        ``indirect_objects`` must support both ``__contains__`` and an
        ``add`` method (e.g. a ``set`` or PDFBox-compatible
        ``Collection`` proxy). ``None`` is a no-op for parity with
        upstream.
        """
        if indirect_objects is None:
            return
        # ``COSDictionary`` itself does not carry an indirect-object key
        # in pypdfbox (only ``COSObject`` does); the upstream short-circuit
        # on ``getKey() != null`` therefore reduces to the per-entry walk.
        parent_skip = (COSName.PARENT, COSName.get_pdf_name("P"))
        for entry_key, value in self._items.items():
            child: COSBase | None = value
            indirect_key: COSObjectKey | None = None
            if isinstance(child, COSObject):
                indirect_key = COSObjectKey(child.object_number, child.generation_number)
                if indirect_key in indirect_objects:
                    continue
                child = child.get_object()
            if isinstance(child, COSDictionary):
                # Skip /Parent and /P references to avoid infinite recursion.
                if entry_key not in parent_skip:
                    child.get_indirect_object_keys(indirect_objects)
            elif isinstance(child, COSArray):
                _array_get_indirect_object_keys(child, indirect_objects)
            elif indirect_key is not None:
                _add_to_collection(indirect_objects, indirect_key)

    def reset_imported_object_keys(self) -> None:
        """Reset all indirect-object keys reachable from this dictionary.

        Mirrors PDFBox ``COSDictionary.resetImportedObjectKeys`` (Java
        line 1514). Used when importing a page into another document to
        avoid colliding object numbers.
        """
        seen: set[COSObjectKey] = set()
        self.reset_object_keys(seen)
        seen.clear()

    def reset_object_keys(
        self, indirect_objects: Collection[COSObjectKey] | None
    ) -> Collection[COSObjectKey] | None:
        """Walk the dictionary graph clearing indirect-object keys.

        Mirrors PDFBox ``COSDictionary.resetObjectKeys`` (Java line 1529).
        Returns ``indirect_objects`` (the same collection that was passed
        in) so callers can chain ``.clear()``.

        Note: pypdfbox's ``COSObject`` does not currently expose a public
        ``set_key(None)`` mutator (its identity is constructor-set), so
        this implementation walks the graph and records each visited
        ``COSObjectKey`` for accounting, but the underlying
        ``object_number/generation_number`` pairs are not cleared. See
        ``CHANGES.md`` for the divergence note.
        """
        if indirect_objects is None:
            return None
        parent_skip = (COSName.PARENT, COSName.get_pdf_name("P"))
        for entry_key, value in self._items.items():
            child: COSBase | None = value
            indirect_key: COSObjectKey | None = None
            if isinstance(child, COSObject):
                indirect_key = COSObjectKey(child.object_number, child.generation_number)
                if indirect_key in indirect_objects:
                    continue
                child = child.get_object()
            if isinstance(child, COSDictionary):
                if entry_key not in parent_skip:
                    child.reset_object_keys(indirect_objects)
            elif isinstance(child, COSArray):
                _array_reset_object_keys(child, indirect_objects)
            elif indirect_key is not None:
                _add_to_collection(indirect_objects, indirect_key)
        return indirect_objects

    def to_string(self) -> str:
        """Return a deterministic structural string of this dictionary.

        Mirrors PDFBox ``COSDictionary.toString`` (Java line 1348).
        Detects cycles via the ``hash:`` placeholder. Aliased to
        ``__str__``.
        """
        try:
            return COSDictionary.get_dictionary_string(self, [])
        except Exception as exc:  # pragma: no cover - defensive parity
            return f"COSDictionary{{{exc!s}}}"

    @staticmethod
    def get_dictionary_string(base: COSBase | None, objs: list[COSBase]) -> str:
        """Internal helper used by :meth:`to_string` (mirrors the upstream
        ``private static getDictionaryString`` at Java line 1361). Tracks
        visited bases in ``objs`` to break cycles.
        """
        return _get_dictionary_string(base, objs)

    def __str__(self) -> str:
        return self.to_string()

    # ---------- visitor / Python protocols ----------

    def accept(self, visitor: ICOSVisitor) -> Any:
        return visitor.visit_from_dictionary(self)

    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self) -> Iterator[COSName]:
        return iter(self._items)

    def __getitem__(self, key: COSName | str) -> COSBase:
        name = _as_name(key)
        if name not in self._items:
            raise KeyError(key)
        return self._items[name]

    def __setitem__(self, key: COSName | str, value: COSBase) -> None:
        self.set_item(key, value)

    def __delitem__(self, key: COSName | str) -> None:
        name = _as_name(key)
        if name not in self._items:
            raise KeyError(key)
        del self._items[name]
        self._update_state.update()

    def __contains__(self, key: object) -> bool:
        if isinstance(key, (COSName, str)):
            return _as_name(key) in self._items
        return False

    def __repr__(self) -> str:
        body = ", ".join(f"{k!s}: {v!r}" for k, v in self._items.items())
        return f"COSDictionary({{{body}}})"


class UnmodifiableCOSDictionary(COSDictionary):
    """Live read-only ``COSDictionary`` view, matching PDFBox's wrapper."""

    def __init__(self, source: COSDictionary) -> None:
        super().__init__()
        self._items = source._items

    @staticmethod
    def _raise_read_only() -> None:
        raise TypeError("COSDictionary is unmodifiable")

    def set_item(self, key: COSName | str, value: COSBase | None) -> None:
        self._raise_read_only()

    def remove_item(self, key: COSName | str) -> COSBase | None:
        self._raise_read_only()

    def clear_item(self, key: COSName | str) -> None:
        self._raise_read_only()

    def clear(self) -> None:
        self._raise_read_only()

    def add_all(self, other: COSDictionary) -> None:
        self._raise_read_only()

    def set_name(self, key: COSName | str, value: str | None) -> None:
        self._raise_read_only()

    def set_string(self, key: COSName | str, value: str | bytes | None) -> None:
        self._raise_read_only()

    def set_int(self, key: COSName | str, value: int) -> None:
        self._raise_read_only()

    def set_long(self, key: COSName | str, value: int) -> None:
        self._raise_read_only()

    def set_float(self, key: COSName | str, value: float) -> None:
        self._raise_read_only()

    def set_boolean(self, key: COSName | str, value: bool) -> None:
        self._raise_read_only()

    def set_date(
        self,
        key: COSName | str,
        value: _dt.date | _dt.datetime | str | None,
    ) -> None:
        self._raise_read_only()

    def set_embedded_date(
        self,
        embedded: COSName | str,
        key: COSName | str,
        value: _dt.date | _dt.datetime | str | None,
    ) -> None:
        self._raise_read_only()

    def set_embedded_string(
        self,
        embedded: COSName | str,
        key: COSName | str,
        value: str | bytes | None,
    ) -> None:
        self._raise_read_only()

    def set_embedded_int(self, embedded: COSName | str, key: COSName | str, value: int) -> None:
        self._raise_read_only()

    def set_flag(self, key: COSName | str, bit_flag: int, value: bool) -> None:
        self._raise_read_only()

    def set_needs_to_be_updated(self, value: bool) -> None:
        self._raise_read_only()

    def __setitem__(self, key: COSName | str, value: COSBase) -> None:
        self._raise_read_only()

    def __delitem__(self, key: COSName | str) -> None:
        self._raise_read_only()
