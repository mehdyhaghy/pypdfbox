from __future__ import annotations

from pypdfbox.fontbox.ttf.ttf_data_stream import MemoryTTFDataStream
from pypdfbox.fontbox.ttf.ttf_table import TTFTable


def test_default_field_values() -> None:
    t = TTFTable()
    assert t.get_tag() == ""
    assert t.get_check_sum() == 0
    assert t.get_offset() == 0
    assert t.get_length() == 0
    assert t.get_initialized() is False


def test_setters_round_trip() -> None:
    t = TTFTable()
    t.set_tag("head")
    t.set_check_sum(0xCAFEBABE)
    t.set_offset(1024)
    t.set_length(54)
    assert t.get_tag() == "head"
    assert t.get_check_sum() == 0xCAFEBABE
    assert t.get_offset() == 1024
    assert t.get_length() == 54


def test_pdfbox_camelcase_aliases_round_trip() -> None:
    t = TTFTable()
    t.setTag("name")
    t.setCheckSum(0x1234)
    t.setOffset(2048)
    t.setLength(128)

    assert t.getTag() == "name"
    assert t.getCheckSum() == 0x1234
    assert t.getOffset() == 2048
    assert t.getLength() == 128
    assert t.getInitialized() is False


def test_read_is_noop_and_does_not_initialize() -> None:
    t = TTFTable()
    data = MemoryTTFDataStream(b"\x00" * 32)
    t.read(None, data)  # type: ignore[arg-type]
    # base read() must NOT flip the initialized flag — it stays False so callers
    # can detect that the body was never parsed.
    assert t.get_initialized() is False
    # And the stream cursor must not have moved.
    assert data.get_current_position() == 0


def test_initialized_can_be_flipped_manually() -> None:
    t = TTFTable()
    t.initialized = True
    assert t.get_initialized() is True
