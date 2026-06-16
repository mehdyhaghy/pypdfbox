from __future__ import annotations

import io
from typing import Any

import pytest

from pypdfbox.fontbox.cff.type2_char_string import Type2CharString
from pypdfbox.fontbox.cmap import CMap
from pypdfbox.fontbox.encoding import Encoding
from pypdfbox.io import RandomAccessReadBuffer


class _TokenWithoutName:
    def __str__(self) -> str:
        return "endchar"


class _DummyEncoding(Encoding):
    def __init__(self) -> None:
        super().__init__()
        self.add(65, "A")
        self.add(66, "B")

    def get_encoding_name(self) -> str:
        return "Dummy"


def test_type2_constructor_accepts_raw_bytecode() -> None:
    char_string = Type2CharString(
        font=None,
        font_name="RawFont",
        glyph_name=".notdef",
        gid=0,
        sequence=b"\x0e",
        default_width_x=500,
    )

    assert char_string.get_name() == ".notdef"
    assert char_string.get_path() == []


def test_type2_get_width_uses_cached_value_on_second_call() -> None:
    char_string = Type2CharString(
        font=None,
        font_name="WidthFont",
        glyph_name="A",
        gid=1,
        sequence=None,
        default_width_x=500,
    )

    char_string._cached_width = 321.0  # noqa: SLF001

    assert char_string.get_width() == 321.0


def test_type2_get_width_falls_back_to_default_when_extractor_fails() -> None:
    char_string = Type2CharString(
        font=None,
        font_name="BrokenFont",
        glyph_name="A",
        gid=1,
        sequence=None,
        default_width_x=444,
    )
    char_string._t2 = object()  # noqa: SLF001

    assert char_string.get_width() == 444.0
    assert char_string.get_width() == 444.0


def test_type2_list_sequence_stringifies_unknown_program_tokens() -> None:
    token = _TokenWithoutName()

    char_string = Type2CharString(
        font=None,
        font_name="ListFont",
        glyph_name="A",
        gid=1,
        sequence=[token],
    )

    assert char_string.t2.program == ["endchar"]
    assert "endchar" in str(char_string)


def test_cmap_stream_read_code_breaks_when_extension_byte_is_missing(
    caplog: pytest.LogCaptureFixture,
) -> None:
    cmap = CMap("Truncated")
    cmap.add_codespace_range(b"\x00\x00", b"\x00\xff")
    cmap.add_codespace_range(b"\x20", b"\x7e")

    assert cmap.read_code(io.BytesIO(b"\x80")) == 0x80
    assert "Invalid character code sequence" in caplog.text


def test_cmap_random_access_short_initial_read_zero_pads_code() -> None:
    # Wave 1547: a read shorter than minCodeLength is no longer short-circuited
    # to the partial value. Mirroring upstream CMap.readCode, the codespace match
    # runs over the zero-padded buffer — a lone <12> under a <0000> <FFFF>
    # codespace reads as 0x1200 (consuming the 1 available byte).
    cmap = CMap()
    cmap.add_codespace_range(b"\x00\x00", b"\xff\xff")

    assert cmap.read_code(RandomAccessReadBuffer(b"\x12")) == 0x1200


def test_cmap_binary_initial_read_eof_returns_zero() -> None:
    cmap = CMap()
    cmap.add_codespace_range(b"\x00\x00", b"\xff\xff")

    assert cmap.read_code(io.BytesIO(b"")) == 0


def test_cmap_usecmap_expands_min_and_max_code_lengths() -> None:
    base = CMap("Base")
    base.add_codespace_range(b"\x20", b"\x7f")
    base.add_codespace_range(b"\x01\x00\x00", b"\x01\xff\xff")
    base.add_base_font_character(b"\x01\x02\x03", "Wide")

    child = CMap("Child")
    child.add_codespace_range(b"\x80\x00", b"\x80\xff")

    child.use_cmap(base)

    assert child.read_code(b"\x01\x02\x03") == (0x010203, 3)
    assert child.read_code(b"A") == (0x41, 1)
    assert child.get_codes_from_unicode("Wide") == b"\x01\x02\x03"


def test_encoding_snapshot_aliases_are_independent() -> None:
    encoding = _DummyEncoding()

    code_map = encoding.get_code_to_name_map()
    name_map = encoding.get_name_to_code_map()
    code_map[67] = "C"
    name_map["C"] = 67

    assert encoding.get_name(67) == ".notdef"
    assert encoding.get_code("C") is None


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (65, True),
        ("A", True),
        (67, False),
        ("Missing", False),
        (True, False),
        (object(), False),
    ],
)
def test_encoding_contains_method_handles_supported_value_types(
    value: Any,
    expected: bool,
) -> None:
    assert _DummyEncoding().contains(value) is expected
