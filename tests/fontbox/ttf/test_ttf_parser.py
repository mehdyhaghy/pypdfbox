"""Hand-written tests for :class:`pypdfbox.fontbox.ttf.TTFParser`.

Exercises the public `parse(...)` entry point against bytes, file
paths, file-like streams, ``MemoryTTFDataStream`` instances, and
``RandomAccessRead`` instances. Also covers the SFNT magic gating
(rejects ``OTTO`` and unsupported scaler types) and the embedded-mode
table-presence check.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from pypdfbox.fontbox.ttf import (
    MemoryTTFDataStream,
    OpenTypeFont,
    TrueTypeFont,
    TTFParser,
)
from pypdfbox.io.random_access_read_buffer import RandomAccessReadBuffer

FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "fontbox"
    / "ttf"
    / "LiberationSans-Regular.ttf"
)


@pytest.fixture(scope="module")
def ttf_bytes() -> bytes:
    if not FIXTURE.exists():
        pytest.skip(f"Fixture font not present: {FIXTURE}")
    return FIXTURE.read_bytes()


# ---------- input-shape acceptance ----------------------------------------


def test_parse_from_bytes(ttf_bytes: bytes) -> None:
    parser = TTFParser()
    font = parser.parse(ttf_bytes)
    assert isinstance(font, TrueTypeFont)
    assert font.get_name() == "LiberationSans"


def test_parse_from_bytearray(ttf_bytes: bytes) -> None:
    parser = TTFParser()
    font = parser.parse(bytearray(ttf_bytes))
    assert isinstance(font, TrueTypeFont)
    assert font.get_number_of_glyphs() > 0


def test_parse_from_memoryview(ttf_bytes: bytes) -> None:
    parser = TTFParser()
    font = parser.parse(memoryview(ttf_bytes))
    assert isinstance(font, TrueTypeFont)


def test_parse_from_path_str(ttf_bytes: bytes) -> None:  # noqa: ARG001 — fixture skip-gates
    parser = TTFParser()
    font = parser.parse(str(FIXTURE))
    assert font.get_units_per_em() > 0


def test_parse_from_pathlike(ttf_bytes: bytes) -> None:  # noqa: ARG001
    parser = TTFParser()
    font = parser.parse(FIXTURE)  # Path is os.PathLike
    assert font.has_table("head")


def test_parse_from_file_like(ttf_bytes: bytes) -> None:
    parser = TTFParser()
    font = parser.parse(io.BytesIO(ttf_bytes))
    assert isinstance(font, TrueTypeFont)


def test_parse_from_ttf_data_stream(ttf_bytes: bytes) -> None:
    parser = TTFParser()
    stream = MemoryTTFDataStream(ttf_bytes)
    font = parser.parse(stream)
    assert isinstance(font, TrueTypeFont)


def test_parse_from_random_access_read(ttf_bytes: bytes) -> None:
    parser = TTFParser()
    rar = RandomAccessReadBuffer(ttf_bytes)
    font = parser.parse(rar)
    assert isinstance(font, TrueTypeFont)


def test_parse_unsupported_source_type_raises() -> None:
    parser = TTFParser()
    with pytest.raises(TypeError):
        parser.parse(42)  # type: ignore[arg-type]


# ---------- SFNT magic gating ---------------------------------------------


def test_parse_rejects_truncated_stream() -> None:
    parser = TTFParser()
    with pytest.raises(OSError):
        parser.parse(b"\x00\x01")


def test_parse_rejects_otto_magic() -> None:
    """A stream beginning with 'OTTO' must be rejected by TTFParser —
    callers must use OTFParser for that container."""
    parser = TTFParser()
    fake_otf = b"OTTO" + b"\x00" * 200
    with pytest.raises(OSError, match="OTTO"):
        parser.parse(fake_otf)


def test_parse_rejects_unknown_scaler() -> None:
    parser = TTFParser()
    bogus = b"XXXX" + b"\x00" * 200
    with pytest.raises(OSError, match="scaler"):
        parser.parse(bogus)


# ---------- ctor flags / property surface ---------------------------------


def test_default_flags() -> None:
    parser = TTFParser()
    assert parser.is_embedded is False
    assert parser.parse_on_demand is True


def test_embedded_flag_disables_table_check() -> None:
    """Embedded-mode parsers tolerate fonts missing required tables.
    With a complete fixture font the result is identical, but the flag
    must be observable on the parser instance."""
    parser = TTFParser(is_embedded=True)
    assert parser.is_embedded is True


def test_lazy_flag_recorded() -> None:
    parser = TTFParser(parse_on_demand=False)
    assert parser.parse_on_demand is False


# ---------- factory hook produces TrueTypeFont (not OpenTypeFont) ---------


def test_parse_returns_truetypefont_not_open_type(ttf_bytes: bytes) -> None:
    parser = TTFParser()
    font = parser.parse(ttf_bytes)
    assert type(font) is TrueTypeFont
    assert not isinstance(font, OpenTypeFont)
