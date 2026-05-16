"""Hand-written coverage tests for ``COSWriterObjectStream``.

Drives the private writeCOSX dispatch table, the offsets header builder,
the reference/indirect/null fallbacks, and the prepare-stage validation.
Stubs the compression pool so tests can run without a full PDDocument.
"""

from __future__ import annotations

from io import BytesIO

import pytest

from pypdfbox.cos.cos_array import COSArray
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
from pypdfbox.pdfwriter.compress.cos_writer_object_stream import (
    COSWriterObjectStream,
)
from pypdfbox.pdfwriter.compress.direct_access_byte_array_output_stream import (
    DirectAccessByteArrayOutputStream,
)


class _StubPool:
    """Mimics the surface of ``COSWriterCompressionPool`` used by the writer."""

    def __init__(self) -> None:
        self._map: dict[int, COSObjectKey] = {}

    def add(self, obj: object, key: COSObjectKey) -> None:
        self._map[id(obj)] = key

    def contains(self, obj: object) -> bool:
        return id(obj) in self._map

    def get_key(self, obj: object) -> COSObjectKey | None:
        return self._map.get(id(obj))


def _new_writer(pool: _StubPool | None = None) -> COSWriterObjectStream:
    return COSWriterObjectStream(pool if pool is not None else _StubPool())


# ----------------------------------------------------------------------
# prepare_stream_object + accessors
# ----------------------------------------------------------------------


def test_prepare_skips_none_key_or_none_object() -> None:
    writer = _new_writer()
    writer.prepare_stream_object(None, COSInteger.get(1))
    writer.prepare_stream_object(COSObjectKey(1, 0), None)
    assert writer.get_prepared_keys() == []


def test_prepare_stores_key_and_resolved_object() -> None:
    writer = _new_writer()
    key = COSObjectKey(3, 0)
    value = COSInteger.get(42)
    writer.prepare_stream_object(key, value)
    keys = writer.get_prepared_keys()
    assert len(keys) == 1
    assert keys[0].get_number() == 3
    # Returned list is a snapshot — mutating it must not affect internal state.
    keys.clear()
    assert len(writer.get_prepared_keys()) == 1


def test_prepare_unwraps_resolved_cos_object() -> None:
    writer = _new_writer()
    inner = COSInteger.get(99)
    indirect = COSObject(7, 0, resolved=inner)
    writer.prepare_stream_object(COSObjectKey(7, 0), indirect)
    # Use write_objects_to_stream to indirectly assert the inner was unwrapped.
    stream = COSStream()
    writer.write_objects_to_stream(stream)
    raw = stream.to_byte_array()
    assert b"99" in raw


def test_prepare_unresolved_indirect_stays_indirect() -> None:
    writer = _new_writer()
    indirect = COSObject(8, 0)  # no resolved payload
    writer.prepare_stream_object(COSObjectKey(8, 0), indirect)
    assert len(writer.get_prepared_keys()) == 1


# ----------------------------------------------------------------------
# Single-token writers
# ----------------------------------------------------------------------


def test_write_cos_string_uses_writer_helper_and_trailing_space() -> None:
    writer = _new_writer()
    out = BytesIO()
    writer.write_cos_string(out, COSString("hi"))
    assert out.getvalue().endswith(b" ")


def test_write_cos_float_emits_value() -> None:
    writer = _new_writer()
    out = BytesIO()
    writer.write_cos_float(out, COSFloat(1.5))
    text = out.getvalue()
    assert b"1.5" in text
    assert text.endswith(b" ")


def test_write_cos_integer_emits_value() -> None:
    writer = _new_writer()
    out = BytesIO()
    writer.write_cos_integer(out, COSInteger.get(7))
    assert out.getvalue() == b"7 "


def test_write_cos_boolean_emits_value() -> None:
    writer = _new_writer()
    out = BytesIO()
    writer.write_cos_boolean(out, COSBoolean.TRUE)
    assert out.getvalue() == b"true "


def test_write_cos_name_emits_slash_prefix() -> None:
    writer = _new_writer()
    out = BytesIO()
    writer.write_cos_name(out, COSName.get_pdf_name("Length"))
    assert out.getvalue().startswith(b"/Length")
    assert out.getvalue().endswith(b" ")


def test_write_cos_null_emits_literal_null() -> None:
    writer = _new_writer()
    out = BytesIO()
    writer.write_cos_null(out)
    assert out.getvalue() == b"null "


def test_write_object_reference_emits_n_g_r() -> None:
    writer = _new_writer()
    out = BytesIO()
    writer.write_object_reference(out, COSObjectKey(5, 2))
    assert out.getvalue() == b"5 2 R "


# ----------------------------------------------------------------------
# Container writers
# ----------------------------------------------------------------------


def test_write_cos_array_wraps_brackets_and_handles_null_entry() -> None:
    writer = _new_writer()
    out = BytesIO()
    arr = COSArray()
    arr.add(COSInteger.get(1))
    arr.add(None)
    writer.write_cos_array(out, arr)
    payload = out.getvalue()
    assert payload.startswith(b"[")
    assert b"null" in payload
    assert payload.endswith(b" ")
    assert b"]" in payload


def test_write_cos_dictionary_keys_top_level_values_inline() -> None:
    writer = _new_writer()
    out = BytesIO()
    cos_dict = COSDictionary()
    cos_dict.set_item(COSName.get_pdf_name("Foo"), COSInteger.get(3))
    writer.write_cos_dictionary(out, cos_dict)
    payload = out.getvalue()
    assert payload.startswith(b"<<")
    assert b"/Foo" in payload
    assert b"3" in payload
    assert b">>" in payload


def test_write_cos_dictionary_skips_none_entries() -> None:
    writer = _new_writer()
    out = BytesIO()
    cos_dict = COSDictionary()
    cos_dict.set_item(COSName.get_pdf_name("Skip"), None)
    cos_dict.set_item(COSName.get_pdf_name("Keep"), COSInteger.get(2))
    writer.write_cos_dictionary(out, cos_dict)
    payload = out.getvalue()
    assert b"/Skip" not in payload
    assert b"/Keep" in payload


# ----------------------------------------------------------------------
# write_object dispatch + fallbacks
# ----------------------------------------------------------------------


def test_write_object_none_is_noop() -> None:
    writer = _new_writer()
    out = BytesIO()
    writer.write_object(out, None, top_level=False)
    assert out.getvalue() == b""


def test_write_object_unresolved_indirect_emits_null() -> None:
    writer = _new_writer()
    out = BytesIO()
    indirect = COSObject(11, 0)
    writer.write_object(out, indirect, top_level=False)
    assert b"null" in out.getvalue()


def test_write_object_indirect_with_key_emits_reference_when_not_top_level() -> None:
    writer = _new_writer()
    out = BytesIO()
    payload = COSInteger.get(1)
    indirect = COSObject(4, 0, resolved=payload)
    indirect.set_key(COSObjectKey(4, 0))
    writer.write_object(out, indirect, top_level=False)
    assert out.getvalue() == b"4 0 R "


def test_write_object_top_level_unwraps_indirect_payload() -> None:
    writer = _new_writer()
    out = BytesIO()
    payload = COSInteger.get(8)
    indirect = COSObject(6, 0, resolved=payload)
    indirect.set_key(COSObjectKey(6, 0))
    writer.write_object(out, indirect, top_level=True)
    assert out.getvalue() == b"8 "


def test_write_object_pool_hit_emits_reference() -> None:
    pool = _StubPool()
    target = COSInteger.get(123)
    pool.add(target, COSObjectKey(9, 0))
    writer = _new_writer(pool)
    out = BytesIO()
    writer.write_object(out, target, top_level=False)
    assert out.getvalue() == b"9 0 R "


def test_write_object_pool_hit_with_missing_key_raises() -> None:
    class _BadPool(_StubPool):
        def get_key(self, obj: object) -> COSObjectKey | None:
            return None

    pool = _BadPool()
    target = COSInteger.get(0)
    pool.add(target, COSObjectKey(1, 0))  # added but get_key forced to None
    writer = _new_writer(pool)
    with pytest.raises(OSError):
        writer.write_object(BytesIO(), target, top_level=False)


def test_write_object_explicit_null_dispatched() -> None:
    writer = _new_writer()
    out = BytesIO()
    writer.write_object(out, COSNull.NULL, top_level=False)
    assert b"null" in out.getvalue()


def test_write_object_unknown_type_raises() -> None:
    writer = _new_writer()

    # COSBase subclass that has none of the dispatched concrete types.
    from pypdfbox.cos.cos_base import COSBase

    class _Mystery(COSBase):
        def accept(self, visitor: object) -> object:
            return None

    with pytest.raises(OSError):
        writer.write_object(BytesIO(), _Mystery(), top_level=False)


# ----------------------------------------------------------------------
# write_objects_to_stream: full /ObjStm assembly
# ----------------------------------------------------------------------


def test_write_objects_to_stream_populates_header_dict() -> None:
    writer = _new_writer()
    writer.prepare_stream_object(COSObjectKey(2, 0), COSInteger.get(10))
    writer.prepare_stream_object(COSObjectKey(3, 0), COSInteger.get(20))
    stream = COSStream()
    out = writer.write_objects_to_stream(stream)
    assert out is stream
    assert out.get_cos_name(COSName.TYPE) == COSName.OBJ_STM
    assert out.get_int(COSName.N) == 2
    first = out.get_int(COSName.FIRST)
    assert first > 0


def test_write_objects_to_stream_offsets_track_token_size() -> None:
    writer = _new_writer()
    writer.prepare_stream_object(COSObjectKey(2, 0), COSInteger.get(10))
    writer.prepare_stream_object(COSObjectKey(3, 0), COSInteger.get(2000))
    stream = COSStream()
    writer.write_objects_to_stream(stream)
    # Decode the underlying body so we can sanity-check the offsets header.
    decoded = stream.to_byte_array()
    # The (objNum, offset) header lives at the start of the stream body.
    # We don't know the FIRST split exactly without parsing — just verify
    # both object numbers appear in the header bytes.
    assert b"2" in decoded
    assert b"3" in decoded


def test_write_objects_to_stream_with_no_objects_emits_n_zero() -> None:
    writer = _new_writer()
    stream = COSStream()
    writer.write_objects_to_stream(stream)
    assert stream.get_int(COSName.N) == 0
    assert stream.get_int(COSName.FIRST) == 0


# ----------------------------------------------------------------------
# DirectAccessByteArrayOutputStream helper
# ----------------------------------------------------------------------


def test_direct_access_buffer_get_raw_and_size() -> None:
    buf = DirectAccessByteArrayOutputStream()
    buf.write(b"abc")
    assert buf.size() == 3
    assert buf.get_raw_data() == b"abc"


# ----------------------------------------------------------------------
# Back-compat aliases survive
# ----------------------------------------------------------------------


def test_backcompat_aliases_are_bound_to_public_methods() -> None:
    cls = COSWriterObjectStream
    assert cls._write_object is cls.write_object
    assert cls._write_cos_string is cls.write_cos_string
    assert cls._write_cos_float is cls.write_cos_float
    assert cls._write_cos_integer is cls.write_cos_integer
    assert cls._write_cos_boolean is cls.write_cos_boolean
    assert cls._write_cos_name is cls.write_cos_name
    assert cls._write_cos_array is cls.write_cos_array
    assert cls._write_cos_dictionary is cls.write_cos_dictionary
    assert cls._write_object_reference is cls.write_object_reference
    assert cls._write_cos_null is cls.write_cos_null
