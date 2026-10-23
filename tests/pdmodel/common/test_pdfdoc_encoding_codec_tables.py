"""The bulk ``charmap`` codec paths of PDFDocEncoding match the tables."""

import pytest

from pypdfbox.pdmodel.common import pdfdoc_encoding as enc


def _loop_decode(data: bytes) -> str:
    return "".join(enc._CODE_TO_UNI[b] for b in data)


def test_decode_every_byte_matches_table() -> None:
    data = bytes(range(256))
    assert enc.decode_bytes(data) == _loop_decode(data)
    assert enc.decode_bytes(bytearray(data)) == _loop_decode(data)
    assert enc.decode_bytes(memoryview(data)) == _loop_decode(data)
    assert enc.decode_bytes(b"") == ""


def test_decode_undefined_slots() -> None:
    assert enc.decode_bytes(b"\x7f\x9f\xad") == "��\x00"


def test_encode_matches_per_char_lookup() -> None:
    text = "".join(enc._CODE_TO_UNI) + "abc€•"
    expected = bytes(enc._UNI_TO_CODE.get(c, 0) for c in text)
    assert enc.encode_bytes(text) == expected


def test_encode_unmappable_chars_map_to_zero() -> None:
    assert enc.encode_bytes("a中b\U0001f600\x7f") == b"a\x00b\x00\x00"
    assert enc.encode_bytes("") == b""


@pytest.fixture
def restore_7f():
    original = enc._CODE_TO_UNI[0x7F]
    yield
    enc._UNI_TO_CODE.pop("", None)
    enc._UNI_TO_CODE.pop("￾", None)
    enc.set(0x7F, original)


def test_set_rebuilds_codec_tables(restore_7f) -> None:
    enc.set(0x7F, "")
    assert enc.decode_bytes(b"A\x7f") == "A"
    assert enc.encode_bytes("") == b"\x7f"


def test_set_to_fffe_uses_loop_decode(restore_7f) -> None:
    # U+FFFE means "undefined" to charmap_decode; the loop path must win.
    enc.set(0x7F, "￾")
    assert enc.decode_bytes(b"\x7f") == "￾"
