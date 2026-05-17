"""Wave 1337 coverage-boost tests for ``pypdfbox.fontbox.ttf.ttf_parser``.

Targets the residual edge branches:

  * ``parse_table_headers`` —
      - ``get_original_data`` raises  (lines 336-338)
      - ``new_font`` raises             (lines 359-361)
      - ``naming.get_post_script_name`` raises  (lines 368-369)
      - ``naming.get_font_family`` / ``get_font_sub_family`` raise (374-375)
      - ``font.is_post_script()`` raises ``AttributeError``        (394-397)
      - non-OTF font that has the ``CFF `` table                   (399-400)
      - mandatory-table missing → ``set_error`` early-return       (417-418)
  * ``create_font_with_tables`` —
      - ``reader`` is None / unset                                 (line 517)
      - ``read_table_directory`` returns ``None``                  (line 527)
      - directory entry's ``offset+length`` walks past file size   (line 531)
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from pypdfbox.fontbox.ttf import MemoryTTFDataStream, TTFParser
from pypdfbox.fontbox.ttf.ttf_parser import FontHeaders
from pypdfbox.fontbox.ttf.ttf_table import TTFTable

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


# ---------- parse_table_headers error / fallback branches ----------


class _ExplodingStream:
    """TTFDataStream-shaped stand-in whose ``get_original_data`` raises.

    Exercises the outer try-except around ``raw = data.get_original_data()``
    in ``_parse_table_headers_from_stream`` (lines 336-338).
    """

    def get_original_data(self) -> bytes:
        raise OSError("simulated I/O failure")


def test_parse_table_headers_raw_read_error_surfaces_as_field() -> None:
    parser = TTFParser()
    headers = parser._parse_table_headers_from_stream(_ExplodingStream())  # type: ignore[arg-type]
    assert isinstance(headers, FontHeaders)
    assert headers.get_error() is not None
    assert "could not read SFNT bytes" in headers.get_error()


def test_parse_table_headers_short_stream_carries_error() -> None:
    """``len(raw) < 4`` → carries an error, no exception."""
    parser = TTFParser()
    stream = MemoryTTFDataStream(b"\x00\x01")
    headers = parser._parse_table_headers_from_stream(stream)
    assert "too short" in (headers.get_error() or "")


def test_parse_table_headers_unsupported_scaler_carries_error() -> None:
    """Magic that doesn't match any known SFNT scaler ⇒ set_error."""
    parser = TTFParser()
    # Four bytes of garbage that don't match any known scaler.
    stream = MemoryTTFDataStream(b"\xFF\xFF\xFF\xFF" + b"\x00" * 8)
    headers = parser._parse_table_headers_from_stream(stream)
    assert "unsupported SFNT scaler type" in (headers.get_error() or "")


def test_parse_table_headers_otto_without_allow_cff_rejects() -> None:
    """``TTFParser`` (not OTFParser) rejects OTTO magic with allow_cff=False."""
    parser = TTFParser()
    # 'OTTO' = 0x4F54544F + enough trailing bytes
    stream = MemoryTTFDataStream(b"OTTO" + b"\x00" * 12)
    headers = parser._parse_table_headers_from_stream(stream)
    assert "CFF outlines are not supported" in (headers.get_error() or "")


def test_parse_table_headers_new_font_error_caught() -> None:
    """When ``new_font`` raises, the error is captured on the headers
    instead of propagating (lines 359-361)."""

    class _Parser(TTFParser):
        def new_font(self, data: Any) -> Any:  # noqa: ARG002
            raise RuntimeError("simulated parse failure")

    parser = _Parser()
    # Valid TrueType scaler bytes but new_font explodes regardless.
    stream = MemoryTTFDataStream(b"\x00\x01\x00\x00" + b"\x00" * 12)
    headers = parser._parse_table_headers_from_stream(stream)
    assert "could not load font" in (headers.get_error() or "")


def test_parse_table_headers_naming_raises_handled(ttf_bytes: bytes) -> None:
    """Lines 368-369 / 374-375 — when ``naming.get_post_script_name`` or
    ``get_font_family`` raise, the error is swallowed and the field
    stays None."""

    class _FlakyNaming:
        def get_post_script_name(self) -> str:
            raise ValueError("flaky font name")

        def get_font_family(self) -> str:
            raise OSError("flaky family")

        def get_font_sub_family(self) -> str:
            return "subfam"

    class _FlakyFont:
        def get_naming(self) -> _FlakyNaming:
            return _FlakyNaming()

        def get_header(self):
            return None

        def has_table(self, _tag: str) -> bool:
            return True

    class _Parser(TTFParser):
        def new_font(self, data: Any) -> Any:  # noqa: ARG002
            return _FlakyFont()

    parser = _Parser()
    stream = MemoryTTFDataStream(b"\x00\x01\x00\x00" + b"\x00" * 12)
    headers = parser._parse_table_headers_from_stream(stream)
    # No error raised, but the name is None because get_post_script_name
    # raised and the except arm set it back to None.
    assert headers.get_name() is None


def test_parse_table_headers_otf_is_post_script_attribute_error() -> None:
    """Lines 394-397 — an OpenTypeFont subclass that lacks
    ``is_post_script`` is handled by setting the flag to False."""
    from pypdfbox.fontbox.ttf.open_type_font import OpenTypeFont

    class _BadOTF(OpenTypeFont):
        def __init__(self) -> None:  # noqa: D401 — minimal
            pass

        def get_naming(self):
            return None

        def get_header(self):
            return None

        def has_table(self, _tag: str) -> bool:
            return True

        def is_post_script(self) -> bool:  # noqa: D401
            raise AttributeError("no _cff_table")

    class _Parser(TTFParser):
        def new_font(self, data: Any) -> Any:  # noqa: ARG002
            return _BadOTF()

    parser = _Parser()
    stream = MemoryTTFDataStream(b"\x00\x01\x00\x00" + b"\x00" * 12)
    headers = parser._parse_table_headers_from_stream(stream)
    assert headers.is_open_type_post_script() is False


def test_parse_table_headers_non_otf_with_cff_table_errors() -> None:
    """Lines 399-400 — a non-OTF font that exposes the ``CFF `` table is
    rejected (legacy TTF with CFF outlines, mismatch upstream calls out)."""

    class _FontWithCff:
        def get_naming(self):
            return None

        def get_header(self):
            return None

        def has_table(self, tag: str) -> bool:
            return tag == "CFF "

    class _Parser(TTFParser):
        def new_font(self, data: Any) -> Any:  # noqa: ARG002
            return _FontWithCff()

    parser = _Parser()
    stream = MemoryTTFDataStream(b"\x00\x01\x00\x00" + b"\x00" * 12)
    headers = parser._parse_table_headers_from_stream(stream)
    assert "CFF outlines are not supported" in (headers.get_error() or "")


def test_parse_table_headers_missing_mandatory_table_errors() -> None:
    """Lines 417-418 — when one of the mandatory tables is missing,
    set_error fires and the helper short-circuits."""

    class _FontMissingHead:
        def get_naming(self):
            return None

        def get_header(self):
            return None

        def has_table(self, tag: str) -> bool:
            # missing "head" forces the mandatory-table loop to fire.
            # Don't claim to have CFF — that would short-circuit earlier.
            if tag == "CFF ":
                return False
            return tag != "head"

    class _Parser(TTFParser):
        def new_font(self, data: Any) -> Any:  # noqa: ARG002
            return _FontMissingHead()

    parser = _Parser()
    stream = MemoryTTFDataStream(b"\x00\x01\x00\x00" + b"\x00" * 12)
    headers = parser._parse_table_headers_from_stream(stream)
    assert "'head' table is mandatory" in (headers.get_error() or "")


# ---------- create_font_with_tables fall-back branches ----------


def test_create_font_with_tables_no_reader_short_circuits(ttf_bytes: bytes) -> None:
    """Line 517 — when ``font._tt.reader`` is missing, the helper
    short-circuits and returns the font without walking entries."""

    class _ParserNoReader(TTFParser):
        def new_font(self, data: Any) -> Any:
            font = super().new_font(data)
            # Wipe the reader handle to force the early-return.
            font._tt = None
            return font

    parser = _ParserNoReader()
    font = parser.create_font_with_tables(MemoryTTFDataStream(ttf_bytes))
    # Still returns a valid font, just without registering directory entries.
    assert font is not None


def test_create_font_with_tables_skips_unknown_entries(ttf_bytes: bytes) -> None:
    """Line 527 — when ``read_table_directory`` returns ``None`` for an
    entry, the loop ``continue``s and that entry is skipped."""

    class _ParserSkipAll(TTFParser):
        def _build_directory_entry(
            self,
            _tag: str,
            _checksum: int,
            _offset: int,
            _length: int,
        ) -> TTFTable | None:
            return None

    parser = _ParserSkipAll()
    font = parser.create_font_with_tables(MemoryTTFDataStream(ttf_bytes))
    # None-returns from _build_directory_entry mean no tables get added
    # by the loop — but the font object itself is still produced.
    assert font is not None


def test_create_font_with_tables_skips_oversize_entries(ttf_bytes: bytes) -> None:
    """Line 531 — when an entry's ``offset+length`` walks past the file
    size, it is skipped (PDFBOX-5285 guard)."""

    class _OversizeEntry(TTFTable):
        def __init__(self, total_size: int) -> None:
            super().__init__()
            self.set_offset(total_size + 1024)
            self.set_length(64)

    class _ParserOversize(TTFParser):
        def _build_directory_entry(
            self,
            _tag: str,
            _checksum: int,
            _offset: int,
            _length: int,
        ) -> TTFTable | None:
            return _OversizeEntry(len(ttf_bytes))

    parser = _ParserOversize()
    font = parser.create_font_with_tables(MemoryTTFDataStream(ttf_bytes))
    assert font is not None
