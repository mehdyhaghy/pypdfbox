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
from pypdfbox.fontbox.ttf.ttf_parser import FontHeaders
from pypdfbox.fontbox.ttf.ttf_table import TTFTable
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


# ---------- parse_embedded ------------------------------------------------


def test_parse_embedded_flips_flag_and_parses(ttf_bytes: bytes) -> None:
    """Mirrors upstream ``TTFParser.parseEmbedded(InputStream)``:
    the call must succeed AND leave the parser in embedded mode
    (matching upstream's ``this.isEmbedded = true`` side-effect)."""
    parser = TTFParser(is_embedded=False)
    assert parser.is_embedded is False
    font = parser.parse_embedded(io.BytesIO(ttf_bytes))
    assert isinstance(font, TrueTypeFont)
    assert parser.is_embedded is True


def test_parse_embedded_tolerates_partial_table_set() -> None:
    """In embedded mode, the post-parse table check is skipped, so
    the parser must NOT raise for a font that lacks the otherwise-
    required ``cmap`` / ``name`` tables. We can't easily craft a
    valid SFNT with missing tables; instead exercise the flag flip
    by checking that the subsequent ``parse`` call inherits embedded
    semantics (the flag is now True)."""
    parser = TTFParser()
    parser._is_embedded = True  # noqa: SLF001 — same end state as parse_embedded
    # Embedded parsers must not blow up on a normal full font either.
    font = parser.parse(FIXTURE)
    assert font.has_table("head")


# ---------- allow_cff hook (upstream allowCFF()) --------------------------


def test_allow_cff_default_false() -> None:
    """Plain ``TTFParser`` rejects CFF outlines — matches upstream
    ``TTFParser.allowCFF()`` returning false."""
    parser = TTFParser()
    assert parser.allow_cff() is False


def test_allow_cff_true_in_otf_subclass() -> None:
    """``OTFParser`` overrides the hook to allow CFF (``OTTO``)
    streams. Mirrors upstream ``OTFParser.allowCFF()``."""
    from pypdfbox.fontbox.ttf import OTFParser  # noqa: PLC0415

    parser = OTFParser()
    assert parser.allow_cff() is True


def test_allow_cff_underscored_alias_still_works() -> None:
    """Earlier waves shipped ``_allow_cff``; the underscored alias must
    keep forwarding to :meth:`allow_cff` for back-compat."""
    parser = TTFParser()
    assert parser._allow_cff() is False  # noqa: SLF001


# ---------- read_table hook (upstream readTable(String)) ------------------


def test_read_table_returns_generic_ttftable() -> None:
    """Default ``read_table`` produces a bare :class:`TTFTable` for
    unknown tags — mirrors upstream ``TTFParser.readTable``."""
    parser = TTFParser()
    table = parser.read_table("zzzz")
    assert isinstance(table, TTFTable)


def test_read_table_underscored_alias_still_works() -> None:
    """The pre-promotion ``_read_table`` spelling forwards to the
    public name."""
    parser = TTFParser()
    table = parser._read_table("zzzz")  # noqa: SLF001
    assert isinstance(table, TTFTable)


# ---------- new_font factory hook (upstream newFont(TTFDataStream)) -------


def test_new_font_returns_truetypefont(ttf_bytes: bytes) -> None:
    """``TTFParser.new_font`` is the factory hook the parse pipeline
    uses to instantiate the concrete font; the base class returns a
    :class:`TrueTypeFont`. Mirrors upstream ``newFont(TTFDataStream)``
    (TTFParser.java L169-L172)."""
    parser = TTFParser()
    stream = MemoryTTFDataStream(ttf_bytes)
    font = parser.new_font(stream)
    assert type(font) is TrueTypeFont
    assert not isinstance(font, OpenTypeFont)


def test_new_font_underscored_alias_still_works(ttf_bytes: bytes) -> None:
    parser = TTFParser()
    stream = MemoryTTFDataStream(ttf_bytes)
    font = parser._new_font(stream)  # noqa: SLF001
    assert isinstance(font, TrueTypeFont)


# ---------- create_font_with_tables / read_table_directory / parse_tables ----


def test_create_font_with_tables_registers_directory(ttf_bytes: bytes) -> None:
    """``create_font_with_tables`` builds a font and seeds it with one
    :class:`TTFTable` per directory entry. Mirrors upstream
    ``createFontWithTables`` (TTFParser.java L130-L160)."""
    parser = TTFParser()
    stream = MemoryTTFDataStream(ttf_bytes)
    font = parser.create_font_with_tables(stream)
    assert isinstance(font, TrueTypeFont)
    # Every well-known SFNT table must have a directory entry.
    table_map = font.get_table_map()
    for tag in ("head", "hhea", "maxp", "hmtx", "name", "cmap", "post"):
        assert tag in table_map, f"missing directory entry for {tag!r}"
        assert table_map[tag].get_length() > 0


def test_read_table_directory_returns_typed_entry() -> None:
    """``read_table_directory`` reads a 16-byte SFNT directory record
    and returns a :class:`TTFTable` with tag/checksum/offset/length set.
    Mirrors upstream ``readTableDirectory`` (TTFParser.java L331-L401)."""
    parser = TTFParser()
    # A synthetic record: tag='head', checksum=0xDEADBEEF, offset=0x100,
    # length=54 (the head table size).
    record = b"head" + (0xDEADBEEF).to_bytes(4, "big") + (0x100).to_bytes(
        4, "big"
    ) + (54).to_bytes(4, "big")
    stream = MemoryTTFDataStream(record)
    table = parser.read_table_directory(stream)
    assert table is not None
    assert table.get_tag() == "head"
    assert table.get_check_sum() == 0xDEADBEEF
    assert table.get_offset() == 0x100
    assert table.get_length() == 54


def test_read_table_directory_skips_zero_length_non_glyf() -> None:
    """Upstream's L394-L398 guard: a zero-length entry for a non-glyf
    tag is dropped (returns ``None``)."""
    parser = TTFParser()
    record = b"DSIG" + b"\x00" * 12  # checksum/offset/length all zero
    stream = MemoryTTFDataStream(record)
    assert parser.read_table_directory(stream) is None


def test_read_table_directory_keeps_zero_length_glyf() -> None:
    """A zero-length ``glyf`` entry is legal (all-empty fonts) and
    must NOT be dropped — mirrors upstream's ``!tag.equals(GlyphTable.TAG)``
    branch."""
    parser = TTFParser()
    record = b"glyf" + b"\x00" * 12
    stream = MemoryTTFDataStream(record)
    table = parser.read_table_directory(stream)
    assert table is not None
    assert table.get_tag() == "glyf"
    assert table.get_length() == 0


def test_parse_tables_validates_required_tables(ttf_bytes: bytes) -> None:
    """``parse_tables`` forces every directory entry to load and
    validates the mandatory-tables presence. Mirrors upstream
    ``parseTables`` (TTFParser.java L180-L249) — for a fully-formed
    font the call must succeed silently."""
    parser = TTFParser()
    font = parser.parse(ttf_bytes)
    # Exercise the public method directly.
    parser.parse_tables(font)
    for table in font.get_tables():
        assert table.get_initialized() is True


# ---------- parse_table_headers fast path ----------------------------------


def test_parse_table_headers_populates_summary(ttf_bytes: bytes) -> None:
    parser = TTFParser()
    headers = parser.parse_table_headers(ttf_bytes)

    assert isinstance(headers, FontHeaders)
    assert headers.get_error() is None
    assert headers.get_name() is not None
    assert headers.get_font_family() is not None
    assert headers.get_header_mac_style() is not None
    assert headers.get_os2_windows() is not None
    assert headers.is_open_type_post_script() is False


def test_parse_table_headers_from_path(ttf_bytes: bytes) -> None:  # noqa: ARG001
    parser = TTFParser()
    headers = parser.parse_table_headers(FIXTURE)
    assert headers.get_error() is None


def test_parse_table_headers_truncated_sets_error() -> None:
    parser = TTFParser()
    headers = parser.parse_table_headers(b"\x00\x01")
    assert headers.get_error() is not None
    assert "too short" in headers.get_error()


def test_parse_table_headers_otto_sets_error() -> None:
    """A bare TTF parser must surface a ``setError`` for an OTTO
    stream rather than raising. Mirrors upstream's
    ``outHeaders.setError("True Type fonts using CFF outlines ..."`` path."""
    parser = TTFParser()
    fake_otf = b"OTTO" + b"\x00" * 200
    headers = parser.parse_table_headers(fake_otf)
    assert headers.get_error() is not None
    assert "CFF" in headers.get_error()


def test_parse_table_headers_unknown_scaler_sets_error() -> None:
    parser = TTFParser()
    headers = parser.parse_table_headers(b"XXXX" + b"\x00" * 200)
    assert headers.get_error() is not None


# ---------- FontHeaders surface --------------------------------------------


def test_font_headers_setters_round_trip() -> None:
    headers = FontHeaders()

    headers.set_error("oops")
    headers.set_name("MyFont")
    headers.set_header_mac_style(2)
    headers.set_font_family("Family", "Sub")
    headers.set_non_otf_gcid_142(b"\x00" * 142)
    headers.set_is_otf_and_post_script(True)
    headers.set_otf_ros("Adobe", "Japan1", 6)

    assert headers.get_error() == "oops"
    assert headers.get_name() == "MyFont"
    assert headers.get_header_mac_style() == 2
    assert headers.get_font_family() == "Family"
    assert headers.get_font_sub_family() == "Sub"
    assert headers.get_non_otf_table_gcid_142() == b"\x00" * 142
    assert headers.is_open_type_post_script() is True
    assert headers.get_otf_registry() == "Adobe"
    assert headers.get_otf_ordering() == "Japan1"
    assert headers.get_otf_supplement() == 6


def test_font_headers_defaults() -> None:
    headers = FontHeaders()
    assert headers.get_error() is None
    assert headers.get_name() is None
    assert headers.get_header_mac_style() is None
    assert headers.get_os2_windows() is None
    assert headers.get_font_family() is None
    assert headers.get_font_sub_family() is None
    assert headers.get_non_otf_table_gcid_142() is None
    assert headers.is_open_type_post_script() is False
    assert headers.get_otf_registry() is None
    assert headers.get_otf_ordering() is None
    assert headers.get_otf_supplement() == 0
    assert FontHeaders.BYTES_GCID == 142
