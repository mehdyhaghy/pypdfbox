"""Compressed object stream emitter.

Mirrors ``org.apache.pdfbox.pdfwriter.compress.COSWriterObjectStream``
(PDFBox 3.0, ``pdfbox/src/main/java/org/apache/pdfbox/pdfwriter/compress/
COSWriterObjectStream.java``).

The class collects ``(COSObjectKey, COSBase)`` pairs via
:meth:`prepare_stream_object` and then writes them into a single deflated
``/ObjStm`` stream when :meth:`write_objects_to_stream` is invoked.
"""

import logging
from io import BytesIO
from typing import TYPE_CHECKING, BinaryIO

from pypdfbox.cos.cos_array import COSArray
from pypdfbox.cos.cos_base import COSBase
from pypdfbox.cos.cos_boolean import COSBoolean
from pypdfbox.cos.cos_dictionary import COSDictionary
from pypdfbox.cos.cos_float import COSFloat
from pypdfbox.cos.cos_integer import COSInteger
from pypdfbox.cos.cos_name import COSName
from pypdfbox.cos.cos_null import COSNull
from pypdfbox.cos.cos_object import COSObject
from pypdfbox.cos.cos_object_key import COSObjectKey
from pypdfbox.cos.cos_stream import COSStream
from pypdfbox.cos.cos_string import COSString
from pypdfbox.pdfwriter._name_token import name_token as _name_token
from pypdfbox.pdfwriter.compress.direct_access_byte_array_output_stream import (
    DirectAccessByteArrayOutputStream,
)

if TYPE_CHECKING:
    from pypdfbox.pdfwriter.compress.cos_writer_compression_pool import (
        COSWriterCompressionPool,
    )

_LOG = logging.getLogger(__name__)
_SPACE = b" "


# Dispatch kinds for :meth:`COSWriterObjectStream.write_object`, resolved
# once per concrete type with the same ``issubclass`` order as the original
# ``isinstance`` chain. ``COSBase`` is an ABC, so each *missed* ``isinstance``
# goes through the slow ``ABCMeta.__instancecheck__``; caching the kind per
# type keeps the dispatch identical without paying that per value.
_K_STRING = 0
_K_FLOAT = 1
_K_INTEGER = 2
_K_BOOLEAN = 3
_K_NAME = 4
_K_ARRAY = 5
_K_DICTIONARY = 6
_K_NULL = 7
_K_UNKNOWN = 8
_KIND_ORDER: tuple[tuple[type, int], ...] = (
    (COSString, _K_STRING),
    (COSFloat, _K_FLOAT),
    (COSInteger, _K_INTEGER),
    (COSBoolean, _K_BOOLEAN),
    (COSName, _K_NAME),
    (COSArray, _K_ARRAY),
    (COSDictionary, _K_DICTIONARY),
    (COSNull, _K_NULL),
)
_KIND_CACHE: dict[type, int] = {}
# Whether a type is a ``COSObject`` (indirect wrapper), cached per type.
_IS_COS_OBJECT: dict[type, bool] = {}


def _kind_of(tp: type) -> int:
    kind = _KIND_CACHE.get(tp)
    if kind is None:
        kind = _K_UNKNOWN
        for cls, k in _KIND_ORDER:
            if issubclass(tp, cls):
                kind = k
                break
        _KIND_CACHE[tp] = kind
    return kind


def _write_pdf(base: COSBase, output: BinaryIO) -> None:
    """Delegate to the value's ``write_pdf`` (snake_case mirror)."""
    # COSFloat, COSInteger, COSBoolean and COSName all expose write_pdf.
    method = getattr(base, "write_pdf", None)
    if method is None:
        raise OSError(f"No write_pdf for {type(base).__name__}")
    method(output)


class COSWriterObjectStream:
    """Streams a batch of compressible COS objects into one ``/ObjStm``."""

    def __init__(self, compression_pool: COSWriterCompressionPool) -> None:
        self._compression_pool = compression_pool
        self._prepared_keys: list[COSObjectKey] = []
        self._prepared_objects: list[COSBase] = []

    def prepare_stream_object(
        self, key: COSObjectKey | None, obj: COSBase | None
    ) -> None:
        """Stage ``obj`` (under ``key``) for the next stream write."""
        if key is None or obj is None:
            return
        self._prepared_keys.append(key)
        self._prepared_objects.append(
            obj.get_object() if isinstance(obj, COSObject) and obj.get_object() is not None else obj
        )

    def get_prepared_keys(self) -> list[COSObjectKey]:
        """Return an immutable view of the staged keys."""
        return list(self._prepared_keys)

    def write_objects_to_stream(self, stream: COSStream) -> COSStream:
        """Write all staged objects into ``stream`` using ``/FlateDecode``."""
        object_count = len(self._prepared_keys)
        stream.set_item(COSName.TYPE, COSName.OBJ_STM)
        stream.set_int(COSName.N, object_count)

        object_numbers: list[int] = []
        objects_buffer: list[DirectAccessByteArrayOutputStream] = []
        for i in range(object_count):
            partial_output = DirectAccessByteArrayOutputStream()
            object_numbers.append(self._prepared_keys[i].get_number())
            self.write_object(partial_output, self._prepared_objects[i], top_level=True)
            objects_buffer.append(partial_output)

        # Build the (objNum, offset) header.
        offsets_buf = BytesIO()
        next_object_offset = 0
        for i, n in enumerate(object_numbers):
            offsets_buf.write(str(n).encode("iso-8859-1"))
            offsets_buf.write(_SPACE)
            offsets_buf.write(str(next_object_offset).encode("iso-8859-1"))
            offsets_buf.write(_SPACE)
            next_object_offset += objects_buffer[i].size()
        offsets_map_buffer = offsets_buf.getvalue()

        with stream.create_output_stream(COSName.FLATE_DECODE) as output:
            output.write(offsets_map_buffer)
            stream.set_int(COSName.FIRST, len(offsets_map_buffer))
            for raw_object in objects_buffer:
                output.write(raw_object.get_raw_data())
        return stream

    # ------------------------------------------------------------------
    # Internal writers (mirror the private writeCOSX methods upstream)
    # ------------------------------------------------------------------
    def write_object(self, output: BinaryIO, obj: COSBase | None, top_level: bool) -> None:
        """Mirrors upstream ``writeObject`` (private). Dispatches on the
        concrete COS type and recurses into containers."""
        if obj is None:
            return
        base: COSBase
        tp = type(obj)
        is_cos_object = _IS_COS_OBJECT.get(tp)
        if is_cos_object is None:
            is_cos_object = _IS_COS_OBJECT[tp] = issubclass(tp, COSObject)
        if is_cos_object:
            if not top_level:
                actual_key = obj.get_key()
                if actual_key is not None:
                    self.write_object_reference(output, actual_key)
                    return
            inner = obj.get_object()
            if inner is None:
                _LOG.debug("Can't dereference indirect object, writing COSNull instead %s", obj)
                self.write_cos_null(output)
                return
            base = inner
        else:
            base = obj

        if not top_level and self._compression_pool.contains(base):
            key = self._compression_pool.get_key(base)
            if key is None:
                raise OSError(
                    f"Error: Adding unknown object reference to object stream:{obj}"
                )
            self.write_object_reference(output, key)
            return

        kind = _KIND_CACHE.get(type(base))
        if kind is None:
            kind = _kind_of(type(base))
        if kind == _K_NAME:
            self.write_cos_name(output, base)
        elif kind == _K_INTEGER:
            self.write_cos_integer(output, base)
        elif kind == _K_DICTIONARY:
            self.write_cos_dictionary(output, base)
        elif kind == _K_ARRAY:
            self.write_cos_array(output, base)
        elif kind == _K_STRING:
            self.write_cos_string(output, base)
        elif kind == _K_FLOAT:
            self.write_cos_float(output, base)
        elif kind == _K_BOOLEAN:
            self.write_cos_boolean(output, base)
        elif kind == _K_NULL:
            self.write_cos_null(output)
        else:
            raise OSError(f"Error: Unknown type in object stream:{obj}")

    # Back-compat alias for callers using the leading-underscore spelling.
    _write_object = write_object

    def write_cos_string(self, output: BinaryIO, cos_string: COSString) -> None:
        """Emit a ``COSString`` token. Mirrors upstream ``writeCOSString``."""
        from pypdfbox.pdfwriter.cos_writer import COSWriter as _Writer

        _Writer.write_string(cos_string, output)
        output.write(_SPACE)

    _write_cos_string = write_cos_string

    def write_cos_float(self, output: BinaryIO, cos_float: COSFloat) -> None:
        """Emit a ``COSFloat`` token. Mirrors upstream ``writeCOSFloat``."""
        _write_pdf(cos_float, output)
        output.write(_SPACE)

    _write_cos_float = write_cos_float

    def write_cos_integer(self, output: BinaryIO, cos_integer: COSInteger) -> None:
        """Emit a ``COSInteger`` token. Mirrors upstream ``writeCOSInteger``."""
        if type(cos_integer) is COSInteger:
            # Same bytes as ``COSInteger.write_pdf`` + the separator, in one
            # write.
            output.write(b"%d " % cos_integer.value)
            return
        _write_pdf(cos_integer, output)
        output.write(_SPACE)

    _write_cos_integer = write_cos_integer

    def write_cos_boolean(self, output: BinaryIO, cos_boolean: COSBoolean) -> None:
        """Emit a ``COSBoolean`` token. Mirrors upstream ``writeCOSBoolean``."""
        _write_pdf(cos_boolean, output)
        output.write(_SPACE)

    _write_cos_boolean = write_cos_boolean

    def write_cos_name(self, output: BinaryIO, cos_name: COSName) -> None:
        """Emit a ``COSName`` token. Mirrors upstream ``writeCOSName``."""
        if type(cos_name) is COSName:
            # Same bytes as ``COSName.write_pdf`` (shared escaped-token memo)
            # + the separator, in one write.
            output.write(_name_token(cos_name.get_bytes()) + _SPACE)
            return
        _write_pdf(cos_name, output)
        output.write(_SPACE)

    _write_cos_name = write_cos_name

    def write_cos_array(self, output: BinaryIO, cos_array: COSArray) -> None:
        """Emit a ``COSArray`` token. Mirrors upstream ``writeCOSArray``."""
        output.write(b"[")
        for value in cos_array:
            if value is None:
                self.write_cos_null(output)
            else:
                self.write_object(output, value, top_level=False)
        output.write(b"]")
        output.write(_SPACE)

    _write_cos_array = write_cos_array

    def write_cos_dictionary(self, output: BinaryIO, cos_dict: COSDictionary) -> None:
        """Emit a ``COSDictionary`` token. Mirrors upstream ``writeCOSDictionary``."""
        output.write(b"<<")
        for key, value in cos_dict.entry_set():
            if value is None:
                continue
            # PDFBOX-5927: keys are written as top-level to avoid an indirect rewrite.
            self.write_object(output, key, top_level=True)
            self.write_object(output, value, top_level=False)
        output.write(b">>")
        output.write(_SPACE)

    _write_cos_dictionary = write_cos_dictionary

    def write_object_reference(self, output: BinaryIO, ref: COSObjectKey) -> None:
        """Emit an indirect-object reference (``N G R``). Mirrors upstream
        ``writeObjectReference``."""
        output.write(b"%d %d R " % (ref.get_number(), ref.get_generation()))

    _write_object_reference = write_object_reference

    def write_cos_null(self, output: BinaryIO) -> None:
        """Emit a ``null`` token. Mirrors upstream ``writeCOSNull``."""
        output.write(b"null")
        output.write(_SPACE)

    _write_cos_null = write_cos_null


class _ListSink:
    """``write(bytes)`` sink that appends to a list (for ``write_pdf``)."""

    __slots__ = ("write",)

    def __init__(self, parts: list[bytes]) -> None:
        self.write = parts.append


# The value-hashed scalar kinds. Their ``__eq__`` only matches within the
# kind's own class hierarchy, so a value-pool lookup can be skipped when the
# pool holds no member of that kind.
_VALUE_KINDS: frozenset[int] = frozenset(
    (_K_STRING, _K_FLOAT, _K_INTEGER, _K_BOOLEAN, _K_NAME)
)
_END = object()
# Container nesting depth past which the recursive fast path hands the
# subtree to the explicit-stack walker (keeps clear of the recursion limit).
_FAST_PATH_MAX_DEPTH = 64


def serialize_packed_objects(
    objects: list[COSBase],
    object_keys: dict[int, COSObjectKey],
    value_pool: dict[COSBase, COSObjectKey],
    ref_cache: dict[int, tuple[COSObjectKey, bytes]] | None = None,
) -> list[bytes]:
    """Serialize each of ``objects`` exactly as
    ``COSWriterObjectStream.write_object(out, obj, top_level=True)`` does
    when its pool answers ``contains`` / ``get_key`` from ``object_keys``
    (identity, ``id()``-keyed) and then ``value_pool`` (value equality, for
    the scalar types), as ``COSWriter``'s ``_ObjStmPoolShim`` does. Returns
    one ``bytes`` body per object.

    This is the hot path of object-stream packing. Shallow structures take a
    recursive path specialised for the common exact types; containers nested
    deeper than ``_FAST_PATH_MAX_DEPTH`` are walked with an explicit stack,
    so arbitrarily deep nesting never hits the recursion limit.

    ``ref_cache`` (``id(key) -> (key, b"N G R ")``) may be shared across
    calls of one save to reuse formatted references; each entry pins its
    key, so a recycled ``id`` is detected by the identity check.
    """
    from pypdfbox.pdfwriter.cos_writer import COSWriter as _Writer

    write_string = _Writer.write_string
    kinds_in_pool = frozenset(_kind_of(type(k)) for k in value_pool)
    kinds_in_pool &= _VALUE_KINDS
    keys_get = object_keys.get
    pool_get = value_pool.get
    kind_get = _KIND_CACHE.get
    is_obj_get = _IS_COS_OBJECT.get
    name_type = COSName
    int_type = COSInteger
    dict_type = COSDictionary
    array_type = COSArray
    object_type = COSObject
    space = _SPACE
    if ref_cache is None:
        ref_cache = {}
    ref_get = ref_cache.get
    no_pool = not kinds_in_pool
    string_type = COSString
    float_type = COSFloat

    parts: list[bytes] = []
    append = parts.append
    sink = _ListSink(parts)

    def ref_bytes(key: COSObjectKey) -> bytes:
        hit = ref_get(id(key))
        if hit is not None and hit[0] is key:
            return hit[1]
        data = b"%d %d R " % (key.get_number(), key.get_generation())
        ref_cache[id(key)] = (key, data)
        return data

    def pool_key(base: COSBase, kind: int, item: object) -> COSObjectKey | None:
        """``contains`` + ``get_key`` for a nested (non-top-level) base."""
        key = keys_get(id(base), _END)
        if key is _END:
            if kind in kinds_in_pool:
                return pool_get(base)
            return None
        if key is None:
            # ``contains`` held but the identity entry is None: fall back to
            # the value pool, else fail like ``write_object``.
            if kind in _VALUE_KINDS:
                key = pool_get(base)
            if key is None:
                raise OSError(
                    f"Error: Adding unknown object reference to object stream:{item}"
                )
        return key  # type: ignore[return-value]

    def emit_scalar(base: COSBase, kind: int, item: object) -> None:
        """Write a resolved non-container value (``write_cos_*``)."""
        if kind == _K_NAME:
            if type(base) is name_type:
                token = base._token  # type: ignore[attr-defined]
                if token is None:
                    base.write_pdf(sink)  # type: ignore[attr-defined]
                else:
                    append(token)
            else:
                _write_pdf(base, sink)  # type: ignore[arg-type]
            append(space)
        elif kind == _K_INTEGER:
            if type(base) is int_type:
                append(b"%d " % base.value)  # type: ignore[attr-defined]
            else:
                _write_pdf(base, sink)  # type: ignore[arg-type]
                append(space)
        elif kind == _K_STRING:
            write_string(base, sink)  # type: ignore[arg-type]
            append(space)
        elif kind in (_K_FLOAT, _K_BOOLEAN):
            _write_pdf(base, sink)  # type: ignore[arg-type]
            append(space)
        elif kind == _K_NULL:
            append(b"null ")
        else:
            raise OSError(f"Error: Unknown type in object stream:{item}")

    def emit_key(dkey: object) -> None:
        """Dictionary keys are written as top-level (PDFBOX-5927)."""
        if type(dkey) is name_type:
            token = dkey._token  # type: ignore[attr-defined]
            if token is None:
                dkey.write_pdf(sink)  # type: ignore[attr-defined]
            else:
                append(token)
            append(space)
        else:
            walk(dkey, True)

    def resolve(item: object, top: bool) -> COSBase | None:
        """Shared prologue of ``write_object``: resolve a ``COSObject`` and
        answer nested pool references. Returns the base still to be written,
        or ``None`` when the item was fully emitted here."""
        tp = type(item)
        is_obj = is_obj_get(tp)
        if is_obj is None:
            is_obj = _IS_COS_OBJECT[tp] = issubclass(tp, COSObject)
        base = item
        if is_obj:
            if not top:
                actual_key = item.get_key()  # type: ignore[attr-defined]
                if actual_key is not None:
                    append(ref_bytes(actual_key))
                    return None
            inner = item.get_object()  # type: ignore[attr-defined]
            if inner is None:
                _LOG.debug(
                    "Can't dereference indirect object, writing COSNull instead %s",
                    item,
                )
                append(b"null ")
                return None
            base = inner
        if not top:
            btp = type(base)
            kind = kind_get(btp)
            if kind is None:
                kind = _kind_of(btp)
            key = pool_key(base, kind, item)  # type: ignore[arg-type]
            if key is not None:
                append(ref_bytes(key))
                return None
        return base  # type: ignore[return-value]

    def walk(root: object, top: bool) -> None:
        """Explicit-stack ``write_object`` (no recursion on containers)."""
        stack: list[tuple[bool, object, bytes]] = []
        item: object = root
        while True:
            if item is not None:
                base = resolve(item, top)
                if base is not None:
                    btp = type(base)
                    kind = kind_get(btp)
                    if kind is None:
                        kind = _kind_of(btp)
                    if kind == _K_DICTIONARY:
                        append(b"<<")
                        stack.append((True, iter(base.entry_set()), b">> "))  # type: ignore[attr-defined]
                    elif kind == _K_ARRAY:
                        append(b"[")
                        stack.append((False, iter(base), b"] "))  # type: ignore[call-overload]
                    else:
                        emit_scalar(base, kind, item)
            item = None
            while stack:
                is_dict, it, closer = stack[-1]
                if is_dict:
                    for dkey, dvalue in it:  # type: ignore[attr-defined]
                        if dvalue is None:
                            continue
                        emit_key(dkey)
                        item = dvalue
                        break
                    else:
                        stack.pop()
                        append(closer)
                        continue
                    break
                nxt = next(it, _END)  # type: ignore[call-overload]
                if nxt is _END:
                    stack.pop()
                    append(closer)
                    continue
                if nxt is None:
                    append(b"null ")
                    continue
                item = nxt
                break
            if item is None:
                return
            top = False

    def emit_nested(value: object, depth: int) -> None:
        """Recursive fast path for a nested (non-top-level) value."""
        tv = type(value)
        if tv is object_type:
            actual_key = value.get_key()  # type: ignore[attr-defined]
            if actual_key is not None:
                hit = ref_get(id(actual_key))
                if hit is not None and hit[0] is actual_key:
                    append(hit[1])
                else:
                    append(ref_bytes(actual_key))
                return
            inner = value.get_object()  # type: ignore[attr-defined]
            if inner is None:
                walk(value, False)
                return
            ti = type(inner)
            if ti is not dict_type and ti is not array_type:
                # Uncommon payload: the general path resolves it the same way.
                walk(value, False)
                return
            # Continue with the resolved container (``base = inner``).
            value = inner
            tv = ti
        if tv is name_type:
            if kinds_in_pool:
                key = pool_key(value, _K_NAME, value)  # type: ignore[arg-type]
            else:
                key = keys_get(id(value), _END)
                if key is _END:
                    key = None
                elif key is None:
                    key = pool_key(value, _K_NAME, value)  # type: ignore[arg-type]
            if key is None:
                token = value._token  # type: ignore[attr-defined]
                if token is None:
                    value.write_pdf(sink)  # type: ignore[attr-defined]
                else:
                    append(token)
                append(space)
                return
        elif tv is int_type:
            if kinds_in_pool:
                key = pool_key(value, _K_INTEGER, value)  # type: ignore[arg-type]
            else:
                key = keys_get(id(value), _END)
                if key is _END:
                    key = None
                elif key is None:
                    key = pool_key(value, _K_INTEGER, value)  # type: ignore[arg-type]
            if key is None:
                append(b"%d " % value._value)  # type: ignore[attr-defined]
                return
        elif tv is dict_type or tv is array_type:
            key = keys_get(id(value), _END)
            if key is _END:
                key = None
            elif key is None:
                key = pool_key(value, _K_ARRAY, value)  # type: ignore[arg-type]
            if key is None:
                if depth >= _FAST_PATH_MAX_DEPTH:
                    walk(value, False)
                elif tv is dict_type:
                    emit_dict(value, depth + 1)  # type: ignore[arg-type]
                else:
                    emit_array(value, depth + 1)  # type: ignore[arg-type]
                return
        elif tv is string_type or tv is float_type:
            kind = _K_STRING if tv is string_type else _K_FLOAT
            key = pool_key(value, kind, value)  # type: ignore[arg-type]
            if key is None:
                emit_scalar(value, kind, value)  # type: ignore[arg-type]
                return
        else:
            walk(value, False)
            return
        hit = ref_get(id(key))
        if hit is not None and hit[0] is key:
            append(hit[1])
        else:
            append(ref_bytes(key))

    def emit_dict(cos_dict: COSDictionary, depth: int) -> None:
        append(b"<<")
        for dkey, dvalue in cos_dict.entry_set():
            if dvalue is None:
                continue
            if type(dkey) is name_type and dkey._token is not None:
                append(dkey._token)
                append(space)
            else:
                emit_key(dkey)
            if no_pool:
                # Inline the two commonest direct scalars (no value pool, so
                # only the identity table can turn them into references).
                tv = type(dvalue)
                if tv is name_type:
                    token = dvalue._token  # type: ignore[attr-defined]
                    if token is not None and keys_get(id(dvalue), _END) is _END:
                        append(token)
                        append(space)
                        continue
                elif tv is int_type and keys_get(id(dvalue), _END) is _END:
                    append(b"%d " % dvalue._value)  # type: ignore[attr-defined]
                    continue
            emit_nested(dvalue, depth)
        append(b">> ")

    def emit_array(cos_array: COSArray, depth: int) -> None:
        append(b"[")
        for value in cos_array:
            if value is None:
                append(b"null ")
            else:
                emit_nested(value, depth)
        append(b"] ")

    results: list[bytes] = []
    for root in objects:
        tr = type(root)
        if tr is dict_type:
            emit_dict(root, 1)  # type: ignore[arg-type]
        elif tr is array_type:
            emit_array(root, 1)  # type: ignore[arg-type]
        elif root is not None:
            walk(root, True)
        results.append(b"".join(parts))
        parts.clear()
    return results


__all__ = ["COSWriterObjectStream", "serialize_packed_objects"]
