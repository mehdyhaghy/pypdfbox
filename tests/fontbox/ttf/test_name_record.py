from __future__ import annotations

from pypdfbox.fontbox.ttf.name_record import NameRecord
from pypdfbox.fontbox.ttf.ttf_data_stream import MemoryTTFDataStream


def _header(
    platform: int,
    encoding: int,
    language: int,
    name_id: int,
    length: int,
    offset: int,
) -> bytes:
    return b"".join(
        v.to_bytes(2, "big") for v in (platform, encoding, language, name_id, length, offset)
    )


def test_default_constructor_zero_initialises() -> None:
    nr = NameRecord()
    assert nr.get_platform_id() == 0
    assert nr.get_platform_encoding_id() == 0
    assert nr.get_language_id() == 0
    assert nr.get_name_id() == 0
    assert nr.get_string_length() == 0
    assert nr.get_string_offset() == 0
    assert nr.get_string() is None


def test_init_data_reads_six_unsigned_shorts_in_order() -> None:
    data = MemoryTTFDataStream(
        _header(
            NameRecord.PLATFORM_WINDOWS,
            NameRecord.ENCODING_WINDOWS_UNICODE_BMP,
            NameRecord.LANGUAGE_WINDOWS_EN_US,
            NameRecord.NAME_FONT_FAMILY_NAME,
            22,
            128,
        )
    )
    nr = NameRecord()
    nr.init_data(None, data)  # type: ignore[arg-type]  # ttf unused
    assert nr.get_platform_id() == NameRecord.PLATFORM_WINDOWS
    assert nr.get_platform_encoding_id() == NameRecord.ENCODING_WINDOWS_UNICODE_BMP
    assert nr.get_language_id() == NameRecord.LANGUAGE_WINDOWS_EN_US
    assert nr.get_name_id() == NameRecord.NAME_FONT_FAMILY_NAME
    assert nr.get_string_length() == 22
    assert nr.get_string_offset() == 128
    # exactly 12 bytes consumed
    assert data.get_current_position() == 12


def test_init_data_max_unsigned_short_values() -> None:
    data = MemoryTTFDataStream(_header(0xFFFF, 0xFFFF, 0xFFFF, 0xFFFF, 0xFFFF, 0xFFFF))
    nr = NameRecord()
    nr.init_data(None, data)  # type: ignore[arg-type]
    assert nr.get_platform_id() == 0xFFFF
    assert nr.get_platform_encoding_id() == 0xFFFF
    assert nr.get_language_id() == 0xFFFF
    assert nr.get_name_id() == 0xFFFF
    assert nr.get_string_length() == 0xFFFF
    assert nr.get_string_offset() == 0xFFFF


def test_setters_round_trip() -> None:
    nr = NameRecord()
    nr.set_platform_id(3)
    nr.set_platform_encoding_id(1)
    nr.set_language_id(0x0409)
    nr.set_name_id(6)
    nr.set_string_length(10)
    nr.set_string_offset(0x100)
    nr.set_string("PostScriptName")
    assert nr.get_platform_id() == 3
    assert nr.get_platform_encoding_id() == 1
    assert nr.get_language_id() == 0x0409
    assert nr.get_name_id() == 6
    assert nr.get_string_length() == 10
    assert nr.get_string_offset() == 0x100
    assert nr.get_string() == "PostScriptName"


def test_set_string_accepts_none() -> None:
    nr = NameRecord()
    nr.set_string("foo")
    nr.set_string(None)
    assert nr.get_string() is None


def test_repr_includes_key_fields() -> None:
    nr = NameRecord()
    nr.set_platform_id(3)
    nr.set_platform_encoding_id(1)
    nr.set_language_id(0x0409)
    nr.set_name_id(4)
    nr.set_string("Helvetica")
    text = repr(nr)
    assert "platform=3" in text
    assert "pEncoding=1" in text
    assert f"language={0x0409}" in text
    assert "name=4" in text
    assert "Helvetica" in text


def test_platform_constants() -> None:
    assert NameRecord.PLATFORM_UNICODE == 0
    assert NameRecord.PLATFORM_MACINTOSH == 1
    assert NameRecord.PLATFORM_ISO == 2
    assert NameRecord.PLATFORM_WINDOWS == 3


def test_unicode_encoding_constants() -> None:
    assert NameRecord.ENCODING_UNICODE_1_0 == 0
    assert NameRecord.ENCODING_UNICODE_1_1 == 1
    assert NameRecord.ENCODING_UNICODE_2_0_BMP == 3
    assert NameRecord.ENCODING_UNICODE_2_0_FULL == 4


def test_windows_encoding_constants() -> None:
    assert NameRecord.ENCODING_WINDOWS_SYMBOL == 0
    assert NameRecord.ENCODING_WINDOWS_UNICODE_BMP == 1
    assert NameRecord.ENCODING_WINDOWS_UNICODE_UCS4 == 10


def test_macintosh_encoding_constant() -> None:
    assert NameRecord.ENCODING_MACINTOSH_ROMAN == 0


def test_language_constants() -> None:
    assert NameRecord.LANGUAGE_UNICODE == 0
    assert NameRecord.LANGUAGE_WINDOWS_EN_US == 0x0409
    assert NameRecord.LANGUAGE_MACINTOSH_ENGLISH == 0


def test_name_id_constants() -> None:
    assert NameRecord.NAME_COPYRIGHT == 0
    assert NameRecord.NAME_FONT_FAMILY_NAME == 1
    assert NameRecord.NAME_FONT_SUB_FAMILY_NAME == 2
    assert NameRecord.NAME_UNIQUE_FONT_ID == 3
    assert NameRecord.NAME_FULL_FONT_NAME == 4
    assert NameRecord.NAME_VERSION == 5
    assert NameRecord.NAME_POSTSCRIPT_NAME == 6
    assert NameRecord.NAME_TRADEMARK == 7
