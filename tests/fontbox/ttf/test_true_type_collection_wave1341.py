"""Wave 1341 coverage-boost tests for ``TrueTypeCollection``.

Targets the small set of branches the existing test suites do not
exercise:

* version-2 TTC header (lines 153-155) — the three trailing unsigned
  shorts that PDFBox reads-and-discards from a v2 collection.
* :meth:`TrueTypeCollection._extract_font_bytes` IndexError branch
  (lines 328-329) when a request reaches past the fontTools-side font
  count.
* :meth:`TrueTypeCollection.create_buffered_data_stream` static helper
  with ``close_after_reading=False`` (line 374) and the success path
  with ``close_after_reading=True`` (lines 371-376).
* OTF scaler-tag dispatch in
  :meth:`create_font_parser_at_index_and_seek` (line 351) — fall-back
  parser pick when the per-font scaler is ``OTTO``.
* :meth:`__init__` fallback for an arbitrary ``RandomAccessRead``
  shape (line 122).
"""

from __future__ import annotations

import io
import os
import struct
from pathlib import Path

import pytest

from pypdfbox.fontbox.ttf.otf_parser import OTFParser
from pypdfbox.fontbox.ttf.true_type_collection import TrueTypeCollection
from pypdfbox.fontbox.ttf.ttf_data_stream import RandomAccessReadDataStream

_FIXTURE_TTF = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "fontbox"
    / "ttf"
    / "LiberationSans-Regular.ttf"
)


def _single_font_ttc_bytes() -> bytes:
    """Re-pack the existing TTF fixture into a one-font TTC (v1 header)."""
    pytest.importorskip("fontTools")
    from fontTools.ttLib import TTCollection, TTFont

    font = TTFont(os.fspath(_FIXTURE_TTF))
    coll = TTCollection()
    coll.fonts.append(font)
    sink = io.BytesIO()
    coll.save(sink)
    return sink.getvalue()


def _patch_to_v2(ttc_bytes: bytes) -> bytes:
    """Stamp a v1 TTC header to v2 and append the DSig triple.

    Upstream PDFBox reads three ``unsigned short`` values (``ulDsigTag``,
    ``ulDsigLength``, ``ulDsigOffset``) after the offset table when the
    version is ``>= 2`` (``TrueTypeCollection.java`` lines 92-97). Our
    port mirrors that — we don't preserve the values, just consume them
    so the stream position is correct for downstream reads. Build a
    synthetic v2 collection by rewriting the version field and
    appending three trailing zero shorts after the per-font offset
    array.
    """
    # Header layout:
    #   bytes [0:4]   = "ttcf"
    #   bytes [4:8]   = version (16.16 fixed)
    #   bytes [8:12]  = numFonts
    #   bytes [12:12 + 4*numFonts] = per-font offsets
    assert ttc_bytes[:4] == b"ttcf"
    num_fonts = struct.unpack(">I", ttc_bytes[8:12])[0]
    header_end = 12 + 4 * num_fonts
    head = ttc_bytes[:4]
    version_v2 = b"\x00\x02\x00\x00"  # 2.0 in 16.16 fixed
    # Insert the three trailing unsigned shorts (six zero bytes) between
    # the offset table and the first font's SFNT directory. Adjust each
    # font offset so callers still land on the SFNT scaler tag.
    shift = 6
    offsets = list(struct.unpack(">" + "I" * num_fonts, ttc_bytes[12:header_end]))
    new_offsets = struct.pack(
        ">" + "I" * num_fonts, *[off + shift for off in offsets]
    )
    trailing_dsig = b"\x00" * 6
    rest = ttc_bytes[header_end:]
    return (
        head
        + version_v2
        + struct.pack(">I", num_fonts)
        + new_offsets
        + trailing_dsig
        + rest
    )


class TestVersion2Header:
    def test_version_2_consumes_three_unsigned_shorts(self) -> None:
        v1 = _single_font_ttc_bytes()
        v2 = _patch_to_v2(v1)
        with TrueTypeCollection(v2) as ttc:
            assert ttc.get_number_of_fonts() == 1
            # Floating-point round-trip: the version field reads back as
            # ``read32_fixed`` (16.16 fixed → ``float``), so we assert at
            # least the integer part is 2.
            assert int(ttc._version) >= 2


class TestExtractFontBytesOutOfRange:
    def test_extract_beyond_fonttools_count_raises(self) -> None:
        v1 = _single_font_ttc_bytes()
        with (
            TrueTypeCollection(v1) as ttc,
            pytest.raises(IndexError, match="font index out of range"),
        ):
            ttc._extract_font_bytes(99)


class TestCreateBufferedDataStream:
    def test_close_after_reading_true_closes_inner(self) -> None:
        from pypdfbox.io.random_access_read_buffer import RandomAccessReadBuffer

        buf = RandomAccessReadBuffer(io.BytesIO(b"A" * 32))
        TrueTypeCollection.create_buffered_data_stream(buf, close_after_reading=True)
        # The helper hands ownership to the data stream and then closes
        # the random access read. A second close() must be a no-op
        # (idempotent) — the value-prop here is that the original was
        # released.
        assert buf.is_closed()

    def test_close_after_reading_false_keeps_inner(self) -> None:
        from pypdfbox.io.random_access_read_buffer import RandomAccessReadBuffer

        buf = RandomAccessReadBuffer(io.BytesIO(b"B" * 32))
        TrueTypeCollection.create_buffered_data_stream(buf, close_after_reading=False)
        # When ``close_after_reading`` is false, the underlying random
        # access read is *not* closed automatically. Callers are
        # responsible for closing.
        assert not buf.is_closed()
        buf.close()


class TestMemoryTTFDataStreamBranch:
    def test_extract_font_bytes_from_memory_stream(self) -> None:
        """Exercise :meth:`_extract_font_bytes` with a
        :class:`MemoryTTFDataStream` backing stream — confirms the
        materialise-then-slice path works regardless of which stream
        subclass holds the TTC bytes."""
        from pypdfbox.fontbox.ttf.ttf_data_stream import MemoryTTFDataStream

        ttc_bytes = _single_font_ttc_bytes()
        mem_stream = MemoryTTFDataStream(ttc_bytes)
        with TrueTypeCollection(mem_stream) as ttc:
            payload = ttc._extract_font_bytes(0)
            assert payload.startswith(b"\x00\x01\x00\x00") or payload[:4] == b"OTTO"


class TestRandomAccessReadFallback:
    def test_random_access_read_shaped_object(self) -> None:
        """Pass a bare ``RandomAccessRead``-shaped object — exercises the
        ``hasattr(source, 'length') and hasattr(source, 'read_into')``
        branch (line 120-122)."""
        from pypdfbox.io.random_access_read_buffer import RandomAccessReadBuffer

        rar = RandomAccessReadBuffer(io.BytesIO(_single_font_ttc_bytes()))
        with TrueTypeCollection(rar) as ttc:
            assert ttc.get_number_of_fonts() == 1


class TestCreateFontParserOTF:
    def test_otto_scaler_returns_otf_parser(self) -> None:
        """When the per-font scaler tag is ``OTTO``, the parser dispatch
        must hand back an :class:`OTFParser` (line 351). We build a TTC
        whose font slot starts with ``OTTO`` so the dispatch decides
        against the default TTF parser; we don't need a fully-valid OTF
        body for the parser-selection check.
        """
        # Minimal TTC header pointing at byte offset 16 where we plant
        # ``OTTO`` (this only exercises ``create_font_parser_at_index_and_seek``
        # which seeks, peeks the four-byte tag, and re-seeks).
        ttc_header = (
            b"ttcf"
            + b"\x00\x01\x00\x00"  # version 1.0
            + b"\x00\x00\x00\x01"  # numFonts = 1
            + b"\x00\x00\x00\x10"  # offset table[0] = 16
        )
        # Pad so the byte at offset 16 lands inside the buffer; the
        # OTFParser ``parse`` is not invoked, only the tag peek.
        sfnt_otto = b"OTTO" + b"\x00" * 16
        payload = ttc_header + sfnt_otto

        # Bypass the full TTC parse (which validates the SFNT body)
        # by constructing the collection from a pre-built data stream.
        stream = RandomAccessReadDataStream(payload)
        ttc = TrueTypeCollection.__new__(TrueTypeCollection)
        ttc._stream = stream
        ttc._num_fonts = 1
        ttc._font_offsets = [16]
        ttc._version = 1.0

        parser = ttc.create_font_parser_at_index_and_seek(0)
        assert isinstance(parser, OTFParser)
        ttc.close()
