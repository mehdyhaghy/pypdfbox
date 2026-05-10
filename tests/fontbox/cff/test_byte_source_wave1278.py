from __future__ import annotations

import pytest

from pypdfbox.fontbox.cff.byte_source import ByteSource
from pypdfbox.fontbox.cff.cff_byte_source import CFFBytesource


def test_byte_source_is_abstract():
    with pytest.raises(TypeError):
        ByteSource()  # type: ignore[abstract]


def test_cff_bytesource_round_trip():
    data = b"abc\x00\xff\x80"
    src = CFFBytesource(data)
    assert src.get_bytes() == data


def test_cff_bytesource_idempotent():
    data = b"hello"
    src = CFFBytesource(data)
    first = src.get_bytes()
    second = src.get_bytes()
    assert first == second == data
    # Identity is allowed but not required; we explicitly test stability.
    assert first is second


def test_cff_bytesource_accepts_bytearray_and_freezes():
    buf = bytearray(b"mut")
    src = CFFBytesource(buf)
    buf[0] = ord("X")
    # The constructor must defensively copy so external mutation is invisible.
    assert src.get_bytes() == b"mut"


def test_cff_bytesource_accepts_memoryview():
    mv = memoryview(b"mv")
    src = CFFBytesource(mv)
    assert src.get_bytes() == b"mv"


def test_cff_bytesource_empty():
    src = CFFBytesource(b"")
    assert src.get_bytes() == b""


def test_cff_bytesource_is_byte_source():
    assert isinstance(CFFBytesource(b""), ByteSource)


def test_cff_bytesource_class_name_preserves_lowercase_s():
    # Upstream Java keeps the lowercase ``s`` in CFFBytesource —
    # snake_case rule does not apply to class names. Lock the spelling
    # in via this test so no future refactor "fixes" it to CFFByteSource.
    assert CFFBytesource.__name__ == "CFFBytesource"
