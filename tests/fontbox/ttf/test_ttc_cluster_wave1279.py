"""Hand-written tests for the Wave 1279 TTC stream + processor cluster.

Covers the seven freshly-ported classes:

* :class:`TTCDataStream`
* :class:`TrueTypeCollection`
* :class:`RandomAccessReadNonClosingInputStream`
* :class:`RandomAccessReadUnbufferedDataStream`
* :class:`TrueTypeFontHeadersProcessor`
* :class:`TrueTypeFontProcessor`
* :class:`CFFTable`
"""

from __future__ import annotations

import io
import os
import struct
from pathlib import Path

import pytest

from pypdfbox.fontbox.ttf.cff_table import CFFTable
from pypdfbox.fontbox.ttf.random_access_read_non_closing_input_stream import (
    RandomAccessReadNonClosingInputStream,
)
from pypdfbox.fontbox.ttf.random_access_read_unbuffered_data_stream import (
    RandomAccessReadUnbufferedDataStream,
)
from pypdfbox.fontbox.ttf.true_type_collection import TrueTypeCollection
from pypdfbox.fontbox.ttf.true_type_font_headers_processor import (
    TrueTypeFontHeadersProcessor,
)
from pypdfbox.fontbox.ttf.true_type_font_processor import TrueTypeFontProcessor
from pypdfbox.fontbox.ttf.ttc_data_stream import TTCDataStream
from pypdfbox.fontbox.ttf.ttf_data_stream import RandomAccessReadDataStream
from pypdfbox.fontbox.ttf.ttf_parser import FontHeaders
from pypdfbox.io.random_access_read_buffer import RandomAccessReadBuffer

_FIXTURE_TTF = Path(__file__).parent.parent.parent / "fixtures" / "fontbox" / "ttf" / (
    "LiberationSans-Regular.ttf"
)


@pytest.fixture(scope="module")
def single_font_ttc_bytes() -> bytes:
    """Build a single-font TTC by re-packing the existing TTF fixture
    through fontTools (the library-first parser pypdfbox already
    relies on). One font is enough to exercise every code path in the
    new cluster."""
    from fontTools.ttLib import TTCollection, TTFont

    ttf = TTFont(os.fspath(_FIXTURE_TTF))
    coll = TTCollection()
    coll.fonts.append(ttf)
    buf = io.BytesIO()
    coll.save(buf)
    return buf.getvalue()


# -------------------- TrueTypeCollection ----------------------------


class TestTrueTypeCollection:
    def test_parses_from_bytes(self, single_font_ttc_bytes: bytes) -> None:
        ttc = TrueTypeCollection(single_font_ttc_bytes)
        try:
            assert ttc.get_number_of_fonts() == 1
            assert len(ttc.get_font_offsets()) == 1
        finally:
            ttc.close()

    def test_parses_from_stream(self, single_font_ttc_bytes: bytes) -> None:
        ttc = TrueTypeCollection(io.BytesIO(single_font_ttc_bytes))
        try:
            assert ttc.get_number_of_fonts() == 1
        finally:
            ttc.close()

    def test_parses_from_path(
        self, single_font_ttc_bytes: bytes, tmp_path: Path
    ) -> None:
        p = tmp_path / "single.ttc"
        p.write_bytes(single_font_ttc_bytes)
        with TrueTypeCollection(p) as ttc:
            assert ttc.get_number_of_fonts() == 1

    def test_missing_header_raises(self) -> None:
        with pytest.raises(OSError, match="Missing TTC header"):
            TrueTypeCollection(b"abcd\x00\x01\x00\x00\x00\x00\x00\x01")

    def test_invalid_font_count_zero(self) -> None:
        # ttcf, version 1.0, numFonts = 0 → invalid (must be >= 1).
        payload = b"ttcf" + struct.pack(">If", 0x00010000, 0.0)[:4] + struct.pack(
            ">I", 0
        )
        # Manually assemble: tag (4) + version (4) + numFonts (4) = 12 bytes
        payload = b"ttcf" + b"\x00\x01\x00\x00" + b"\x00\x00\x00\x00"
        with pytest.raises(OSError, match="Invalid number of fonts"):
            TrueTypeCollection(payload)

    def test_invalid_font_count_huge(self) -> None:
        # Mirrors upstream TrueTypeFontCollectionTest.testNumberOfFonts —
        # numFonts = 0x7FFFFFFF is far above the 1024 cap.
        payload = b"ttcf" + b"\x00\x00\x00\x00" + b"\x7f\xff\xff\xff"
        with pytest.raises(OSError, match="Invalid number of fonts"):
            TrueTypeCollection(payload)

    def test_process_all_fonts_callable(
        self, single_font_ttc_bytes: bytes
    ) -> None:
        collected: list[str] = []
        with TrueTypeCollection(single_font_ttc_bytes) as ttc:
            ttc.process_all_fonts(lambda f: collected.append(f.get_name()))
        assert len(collected) == 1
        assert collected[0]  # PostScript name is non-empty

    def test_process_all_fonts_processor_subclass(
        self, single_font_ttc_bytes: bytes
    ) -> None:
        class _Collector(TrueTypeFontProcessor):
            def __init__(self) -> None:
                self.names: list[str] = []

            def process(self, ttf) -> None:  # type: ignore[no-untyped-def]
                self.names.append(ttf.get_name())

        collector = _Collector()
        with TrueTypeCollection(single_font_ttc_bytes) as ttc:
            ttc.process_all_fonts(collector)
        assert len(collector.names) == 1

    def test_get_font_by_name(self, single_font_ttc_bytes: bytes) -> None:
        with TrueTypeCollection(single_font_ttc_bytes) as ttc:
            name = ttc.get_font_at_index(0).get_name()
            assert ttc.get_font_by_name(name) is not None
            assert ttc.get_font_by_name("DoesNotExist__") is None

    def test_get_font_at_index_out_of_range(
        self, single_font_ttc_bytes: bytes
    ) -> None:
        with TrueTypeCollection(single_font_ttc_bytes) as ttc, pytest.raises(
            IndexError
        ):
            ttc.get_font_at_index(99)

    def test_process_all_font_headers_in_file(
        self, single_font_ttc_bytes: bytes, tmp_path: Path
    ) -> None:
        p = tmp_path / "single2.ttc"
        p.write_bytes(single_font_ttc_bytes)
        collected: list[FontHeaders] = []
        TrueTypeCollection.process_all_font_headers_in_file(
            p, lambda h: collected.append(h)
        )
        assert len(collected) == 1
        assert collected[0].get_name() is not None

    def test_process_all_font_headers_processor_subclass(
        self, single_font_ttc_bytes: bytes
    ) -> None:
        class _Collector(TrueTypeFontHeadersProcessor):
            def __init__(self) -> None:
                self.items: list[FontHeaders] = []

            def process(self, font_headers: FontHeaders) -> None:
                self.items.append(font_headers)

        collector = _Collector()
        with TrueTypeCollection(single_font_ttc_bytes) as ttc:
            ttc.process_all_font_headers(collector)
        assert len(collector.items) == 1


# -------------------- TTCDataStream --------------------------------


class TestTTCDataStream:
    def test_forwards_reads_to_inner_stream(self) -> None:
        inner = RandomAccessReadDataStream(b"\x01\x02\x03\x04\x05\x06\x07\x08")
        wrap = TTCDataStream(inner)
        assert wrap.read() == 1
        assert wrap.get_current_position() == 1
        buf = bytearray(3)
        assert wrap.read_into(buf, 0, 3) == 3
        assert bytes(buf) == b"\x02\x03\x04"

    def test_close_does_not_close_inner(self) -> None:
        inner = RandomAccessReadDataStream(b"\x00" * 16)
        wrap = TTCDataStream(inner)
        wrap.close()
        # Inner is still readable.
        assert inner.read() == 0

    def test_seek_propagates(self) -> None:
        inner = RandomAccessReadDataStream(b"AAAA" + b"BBBB")
        wrap = TTCDataStream(inner)
        wrap.seek(4)
        assert wrap.read_tag() == "BBBB"

    def test_read_long(self) -> None:
        # 0x0102030405060708 big-endian
        inner = RandomAccessReadDataStream(
            b"\x01\x02\x03\x04\x05\x06\x07\x08",
        )
        wrap = TTCDataStream(inner)
        assert wrap.read_long() == 0x0102030405060708

    def test_get_original_data_and_size(self) -> None:
        data = bytes(range(32))
        inner = RandomAccessReadDataStream(data)
        wrap = TTCDataStream(inner)
        assert wrap.get_original_data() == data
        assert wrap.get_original_data_size() == 32

    def test_create_sub_view(self) -> None:
        inner = RandomAccessReadDataStream(b"\x00\x01\x02\x03\x04\x05\x06\x07")
        wrap = TTCDataStream(inner)
        wrap.seek(2)
        view = wrap.create_sub_view(4)
        assert view is not None
        assert view.length() == 4


# -------------------- RandomAccessReadUnbufferedDataStream ----------


class TestRandomAccessReadUnbufferedDataStream:
    def test_read_byte(self) -> None:
        buf = RandomAccessReadBuffer(b"\xab\xcd")
        s = RandomAccessReadUnbufferedDataStream(buf)
        assert s.read() == 0xAB
        assert s.read() == 0xCD
        assert s.read() == -1

    def test_read_long_signed(self) -> None:
        # 0xFFFFFFFFFFFFFFFE → -2 in signed 64-bit
        buf = RandomAccessReadBuffer(b"\xff" * 7 + b"\xfe")
        s = RandomAccessReadUnbufferedDataStream(buf)
        assert s.read_long() == -2

    def test_read_long_positive(self) -> None:
        buf = RandomAccessReadBuffer(
            b"\x00\x00\x00\x00\x00\x00\x00\x01"
        )
        s = RandomAccessReadUnbufferedDataStream(buf)
        assert s.read_long() == 1

    def test_seek_and_position(self) -> None:
        buf = RandomAccessReadBuffer(b"abcdef")
        s = RandomAccessReadUnbufferedDataStream(buf)
        s.seek(3)
        assert s.get_current_position() == 3
        assert s.read() == ord("d")

    def test_read_into(self) -> None:
        buf = RandomAccessReadBuffer(b"hello world")
        s = RandomAccessReadUnbufferedDataStream(buf)
        out = bytearray(5)
        n = s.read_into(out, 0, 5)
        assert n == 5
        assert bytes(out) == b"hello"

    def test_original_data_size(self) -> None:
        buf = RandomAccessReadBuffer(b"\x00" * 42)
        s = RandomAccessReadUnbufferedDataStream(buf)
        assert s.get_original_data_size() == 42

    def test_get_original_data_returns_bytes(self) -> None:
        payload = b"this is the payload"
        buf = RandomAccessReadBuffer(payload)
        s = RandomAccessReadUnbufferedDataStream(buf)
        assert s.get_original_data() == payload

    def test_close_closes_inner(self) -> None:
        buf = RandomAccessReadBuffer(b"\x00" * 8)
        s = RandomAccessReadUnbufferedDataStream(buf)
        s.close()
        assert buf.is_closed()

    def test_create_sub_view(self) -> None:
        buf = RandomAccessReadBuffer(b"abcdefghij")
        s = RandomAccessReadUnbufferedDataStream(buf)
        s.seek(2)
        view = s.create_sub_view(4)
        assert view is not None
        assert view.length() == 4


# -------------------- RandomAccessReadNonClosingInputStream --------


class TestRandomAccessReadNonClosingInputStream:
    def test_read_all(self) -> None:
        rar = RandomAccessReadBuffer(b"hello")
        s = RandomAccessReadNonClosingInputStream(rar)
        assert s.read() == b"hello"

    def test_read_n(self) -> None:
        rar = RandomAccessReadBuffer(b"abcdef")
        s = RandomAccessReadNonClosingInputStream(rar)
        assert s.read(3) == b"abc"
        assert s.read(3) == b"def"
        assert s.read(1) == b""

    def test_readinto(self) -> None:
        rar = RandomAccessReadBuffer(b"hello world")
        s = RandomAccessReadNonClosingInputStream(rar)
        out = bytearray(5)
        n = s.readinto(out)
        assert n == 5
        assert bytes(out) == b"hello"

    def test_seek_and_tell(self) -> None:
        rar = RandomAccessReadBuffer(b"abcdef")
        s = RandomAccessReadNonClosingInputStream(rar)
        s.seek(3)
        assert s.tell() == 3
        assert s.read(2) == b"de"

    def test_seek_cur(self) -> None:
        rar = RandomAccessReadBuffer(b"abcdef")
        s = RandomAccessReadNonClosingInputStream(rar)
        s.read(2)
        s.seek(2, io.SEEK_CUR)
        assert s.tell() == 4

    def test_close_does_not_close_inner(self) -> None:
        rar = RandomAccessReadBuffer(b"some bytes")
        s = RandomAccessReadNonClosingInputStream(rar)
        s.close()
        # Inner is still usable.
        assert rar.read() == ord("s")

    def test_readable_and_seekable(self) -> None:
        rar = RandomAccessReadBuffer(b"a")
        s = RandomAccessReadNonClosingInputStream(rar)
        assert s.readable()
        assert s.seekable()


# -------------------- Processor ABCs --------------------------------


class TestProcessorInterfaces:
    def test_true_type_font_processor_is_abstract(self) -> None:
        with pytest.raises(TypeError):
            TrueTypeFontProcessor()  # type: ignore[abstract]

    def test_true_type_font_headers_processor_is_abstract(self) -> None:
        with pytest.raises(TypeError):
            TrueTypeFontHeadersProcessor()  # type: ignore[abstract]

    def test_can_subclass_font_processor(self) -> None:
        class _P(TrueTypeFontProcessor):
            def process(self, ttf) -> None:  # type: ignore[no-untyped-def]
                pass

        _P()  # should not raise

    def test_can_subclass_headers_processor(self) -> None:
        class _P(TrueTypeFontHeadersProcessor):
            def process(self, font_headers: FontHeaders) -> None:
                pass

        _P()  # should not raise


# -------------------- CFFTable --------------------------------------


class TestCFFTable:
    def test_tag_constant(self) -> None:
        assert CFFTable.TAG == "CFF "

    def test_default_state(self) -> None:
        table = CFFTable()
        assert table.get_font() is None
        assert not table.initialized
        assert table.get_tag() == ""  # set later by directory walk

    def test_read_populates_font(self) -> None:
        # Build a minimal OTF (CFF-flavoured) via fontTools' FontBuilder
        # — the same in-memory synthesis path the OTFParser upstream
        # tests use (tests/fontbox/ttf/upstream/test_otf_parser.py).
        # Extract the inner ``CFF `` table bytes from the OTF wrapper
        # (mirrors CFFParser._extract_cff_table) and feed them to
        # CFFTable.read via a MemoryTTFDataStream, exercising the
        # exact upstream contract: read_bytes(get_length()) → CFFParser
        # → cff_font is populated and initialized flips to True.
        try:
            from fontTools.fontBuilder import FontBuilder  # noqa: PLC0415
            from fontTools.misc.psCharStrings import T2CharString  # noqa: PLC0415
        except ImportError:
            pytest.skip("fontTools FontBuilder / T2CharString unavailable")

        cs = T2CharString()
        cs.program = ["endchar"]

        fb = FontBuilder(unitsPerEm=1000, isTTF=False)
        glyph_order = [".notdef", "A"]
        fb.setupGlyphOrder(glyph_order)
        fb.setupCharacterMap({0x41: "A"})
        fb.setupCFF(
            psName="ParityCFFTable",
            fontInfo={"FullName": "Parity CFFTable"},
            charStringsDict=dict.fromkeys(glyph_order, cs),
            privateDict={},
        )
        fb.setupHorizontalMetrics(dict.fromkeys(glyph_order, (500, 0)))
        fb.setupHorizontalHeader(ascent=800, descent=-200)
        fb.setupNameTable({"familyName": "Parity", "styleName": "Regular"})
        fb.setupOS2(sTypoAscender=800, usWinAscent=800, usWinDescent=200)
        fb.setupPost()

        otf_buf = io.BytesIO()
        fb.font.save(otf_buf)
        otf_bytes = otf_buf.getvalue()

        # Extract the 'CFF ' table bytes from the OTF directory.
        # Mirrors pypdfbox.fontbox.cff.cff_parser._extract_cff_table:
        # 16-byte records of tag(4) checksum(4) offset(4) length(4)
        # starting at offset 12.
        num_tables = struct.unpack(">H", otf_bytes[4:6])[0]
        cff_bytes: bytes | None = None
        for i in range(num_tables):
            record = 12 + i * 16
            tag = otf_bytes[record : record + 4]
            if tag == b"CFF ":
                offset = struct.unpack(">I", otf_bytes[record + 8 : record + 12])[0]
                length = struct.unpack(
                    ">I", otf_bytes[record + 12 : record + 16]
                )[0]
                cff_bytes = otf_bytes[offset : offset + length]
                break
        assert cff_bytes is not None, "synthesised OTF must contain a 'CFF ' table"

        # Feed the raw CFF payload through CFFTable.read with a memory
        # data stream and the declared length — this is the surface
        # CFFTable.java L50-L59 exercises.
        from pypdfbox.fontbox.ttf.ttf_data_stream import (  # noqa: PLC0415
            MemoryTTFDataStream,
        )

        table = CFFTable()
        table.set_length(len(cff_bytes))
        # Host TTF is only consulted by the _CFFByteSource for re-reading;
        # read() itself never touches it. None-typed minimal stand-in is
        # acceptable for this surface check — upstream's read() takes the
        # ttf only to wire the byte-source callback.
        table.read(None, MemoryTTFDataStream(cff_bytes))  # type: ignore[arg-type]
        assert table.initialized is True
        assert table.get_font() is not None


# -------------------- End-to-end: TTC iteration ---------------------


class TestEndToEndIteration:
    def test_font_can_be_used_after_iteration(
        self, single_font_ttc_bytes: bytes
    ) -> None:
        with TrueTypeCollection(single_font_ttc_bytes) as ttc:
            font = ttc.get_font_at_index(0)
            # Sanity: PostScript name is present and the font has at
            # least one cmap subtable.
            assert font.get_name()
            assert font.get_number_of_glyphs() > 0
