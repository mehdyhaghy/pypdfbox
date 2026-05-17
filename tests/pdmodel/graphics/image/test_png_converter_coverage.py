"""Coverage-boost tests for
``pypdfbox.pdmodel.graphics.image.png_converter`` (wave 1316).

The module wraps PIL + zlib to expose the upstream
``PNGConverter`` surface (chunk parsing, CRC tables, convert-PNG entry
point, ``MultipleInputStream`` aggregator). Pre-wave the module sat at
37% line coverage — most static helpers and the inner-class stream
adapter were untested. These tests build a tiny RGB PNG with Pillow,
feed it through ``parse_png_chunks`` / ``convert_png_image``, then
exercise every static helper independently with synthetic byte buffers.
"""
from __future__ import annotations

import io
import zlib

import pytest
from PIL import Image

from pypdfbox.cos import COSName
from pypdfbox.pdmodel import PDDocument
from pypdfbox.pdmodel.graphics.image.png_converter import (
    _CHUNK_IHDR,
    Chunk,
    MultipleInputStream,
    PNGConverter,
    _PNGConverterState,
)


# --------------------------------------------------------------------------
# fixtures
# --------------------------------------------------------------------------
@pytest.fixture
def rgb_png_bytes() -> bytes:
    """A 3x2 red RGB PNG generated in-memory by Pillow."""
    img = Image.new("RGB", (3, 2), "red")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def gray_png_bytes() -> bytes:
    """A 4x4 grayscale PNG."""
    img = Image.new("L", (4, 4), 128)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def indexed_png_bytes() -> bytes:
    """A small palettised (PLTE chunk) PNG — colour type 3 forces the
    ``build_index_image`` dispatch branch."""
    img = Image.new("P", (4, 4), 0)
    img.putpalette([0, 0, 0, 255, 255, 255])
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# --------------------------------------------------------------------------
# convert_png_image — high-level entry point
# --------------------------------------------------------------------------
def test_convert_png_image_returns_pd_image_x_object(rgb_png_bytes: bytes) -> None:
    doc = PDDocument()
    try:
        result = PNGConverter.convert_png_image(doc, rgb_png_bytes)
        assert result is not None
        assert type(result).__name__ == "PDImageXObject"
    finally:
        doc.close()


def test_convert_png_image_returns_none_on_invalid_bytes() -> None:
    doc = PDDocument()
    try:
        # Non-PNG payload — Pillow raises UnidentifiedImageError (OSError
        # subclass), caught by the converter.
        result = PNGConverter.convert_png_image(doc, b"not-a-png-blob")
        assert result is None
    finally:
        doc.close()


def test_convert_png_image_handles_truncated_payload() -> None:
    doc = PDDocument()
    try:
        # First 8 bytes are a valid PNG magic but no chunks follow.
        result = PNGConverter.convert_png_image(doc, b"\x89PNG\r\n\x1a\n")
        assert result is None
    finally:
        doc.close()


# --------------------------------------------------------------------------
# parse_png_chunks — chunk walker
# --------------------------------------------------------------------------
def test_parse_png_chunks_populates_state_for_rgb_png(rgb_png_bytes: bytes) -> None:
    state = PNGConverter.parse_png_chunks(rgb_png_bytes)
    assert state is not None
    assert state.width == 3
    assert state.height == 2
    assert state.bits_per_component == 8
    assert state.ihdr is not None
    assert len(state.idats) >= 1
    assert state.plte is None


def test_parse_png_chunks_picks_up_palette_for_indexed_png(
    indexed_png_bytes: bytes,
) -> None:
    state = PNGConverter.parse_png_chunks(indexed_png_bytes)
    assert state is not None
    assert state.plte is not None
    # Indexed PNGs have colour type 3 in IHDR byte 9.
    assert state.ihdr is not None
    assert state.ihdr.get_data()[9] == 3


def test_parse_png_chunks_rejects_non_png_signature() -> None:
    assert PNGConverter.parse_png_chunks(b"NOT-A-PNG-12345678") is None


def test_parse_png_chunks_rejects_short_buffer() -> None:
    assert PNGConverter.parse_png_chunks(b"\x00\x01") is None


def test_parse_png_chunks_stops_on_truncated_tail() -> None:
    """When the declared chunk length runs past the buffer end, the loop
    must bail rather than wrap into garbage."""
    magic = b"\x89PNG\r\n\x1a\n"
    # Declare length 99 for a chunk type 'IHDR' but provide only 4 bytes.
    payload = (
        magic
        + (99).to_bytes(4, "big")
        + b"IHDR"
        + b"\x00" * 4  # truncated
    )
    state = PNGConverter.parse_png_chunks(payload)
    # Loop bailed mid-walk; ihdr never populated.
    assert state is not None
    assert state.ihdr is None


# --------------------------------------------------------------------------
# Chunk + check_chunk_sane
# --------------------------------------------------------------------------
def test_chunk_get_data_slices_buffer() -> None:
    chunk = Chunk(bytes_=b"prefix_DATA_trail", chunk_type=0, crc=0, start=7, length=4)
    assert chunk.get_data() == b"DATA"


def test_check_chunk_sane_validates_correct_crc() -> None:
    type_bytes = (0x49484452).to_bytes(4, "big")  # 'IHDR'
    data = b"abcd"
    crc = zlib.crc32(type_bytes + data) & 0xFFFFFFFF
    payload = b"prefix__" + data
    chunk = Chunk(
        bytes_=payload,
        chunk_type=0x49484452,
        crc=crc,
        start=len(payload) - 4,
        length=4,
    )
    assert PNGConverter.check_chunk_sane(chunk) is True


def test_check_chunk_sane_rejects_bad_crc() -> None:
    chunk = Chunk(
        bytes_=b"hello_data", chunk_type=0x49484452, crc=0xDEADBEEF, start=6, length=4,
    )
    assert PNGConverter.check_chunk_sane(chunk) is False


def test_check_chunk_sane_rejects_negative_length() -> None:
    chunk = Chunk(bytes_=b"", chunk_type=0, crc=0, start=0, length=-1)
    assert PNGConverter.check_chunk_sane(chunk) is False


# --------------------------------------------------------------------------
# state validation
# --------------------------------------------------------------------------
def test_check_converter_state_rejects_empty_state() -> None:
    assert PNGConverter.check_converter_state(_PNGConverterState()) is False


def test_check_converter_state_accepts_populated_state(rgb_png_bytes: bytes) -> None:
    state = PNGConverter.parse_png_chunks(rgb_png_bytes)
    assert state is not None
    assert PNGConverter.check_converter_state(state) is True


# --------------------------------------------------------------------------
# map_png_render_intent
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("intent", "expected_name"),
    [
        (0, "Perceptual"),
        (1, "RelativeColorimetric"),
        (2, "Saturation"),
        (3, "AbsoluteColorimetric"),
    ],
)
def test_map_png_render_intent_known_values(intent: int, expected_name: str) -> None:
    name = PNGConverter.map_png_render_intent(intent)
    assert name == COSName.get_pdf_name(expected_name)


def test_map_png_render_intent_unknown_returns_none() -> None:
    assert PNGConverter.map_png_render_intent(99) is None


# --------------------------------------------------------------------------
# read helpers
# --------------------------------------------------------------------------
def test_read_int_decodes_big_endian_signed() -> None:
    assert PNGConverter.read_int(b"\x00\x00\x00\x05", 0) == 5


def test_read_int_handles_negative_values() -> None:
    # 0xFFFFFFFF reads as -1 with signed=True.
    assert PNGConverter.read_int(b"\xff\xff\xff\xff", 0) == -1


def test_read_png_float_scales_by_100000() -> None:
    # 0x000186A0 == 100000 -> 1.0 after divide.
    assert PNGConverter.read_png_float(b"\x00\x01\x86\xa0", 0) == pytest.approx(1.0)


# --------------------------------------------------------------------------
# CRC table + crc helpers
# --------------------------------------------------------------------------
def test_make_crc_table_returns_256_entries_and_is_cached() -> None:
    table = PNGConverter.make_crc_table()
    assert len(table) == 256
    assert table[0] == 0
    # Second invocation reuses the cache (no re-computation).
    table2 = PNGConverter.make_crc_table()
    assert table is table2


def test_crc_matches_zlib_for_known_payload() -> None:
    buf = b"hello world"
    expected = zlib.crc32(buf) & 0xFFFFFFFF
    assert PNGConverter.crc(buf, 0, len(buf)) == expected


def test_update_crc_with_custom_initial_chains_with_stdlib() -> None:
    """``update_crc`` keeps the running CRC in canonical (one's-complement)
    form; passing 0xFFFFFFFF as the seed and XORing the final value with
    0xFFFFFFFF should match the standalone ``crc`` helper / ``zlib.crc32``."""
    buf = b"chunk"
    seeded = PNGConverter.update_crc(buf, 0, len(buf), 0xFFFFFFFF)
    assert (seeded ^ 0xFFFFFFFF) == PNGConverter.crc(buf, 0, len(buf))


# --------------------------------------------------------------------------
# build_decode_params
# --------------------------------------------------------------------------
def test_build_decode_params_for_rgb_png_returns_predictor_dict(
    rgb_png_bytes: bytes,
) -> None:
    state = PNGConverter.parse_png_chunks(rgb_png_bytes)
    assert state is not None
    params = PNGConverter.build_decode_params(state, None)
    assert params is not None
    # PNG predictor = 15 (any-row PNG); Colours = 3 for RGB.
    assert params.get_int(COSName.get_pdf_name("Predictor")) == 15
    assert params.get_int(COSName.get_pdf_name("Colors")) == 3
    assert params.get_int(COSName.get_pdf_name("BitsPerComponent")) == 8
    assert params.get_int(COSName.get_pdf_name("Columns")) == 3


def test_build_decode_params_returns_none_without_ihdr() -> None:
    state = _PNGConverterState()
    assert PNGConverter.build_decode_params(state, None) is None


def test_build_decode_params_returns_none_for_truncated_ihdr() -> None:
    state = _PNGConverterState()
    # Synthesise an IHDR chunk shorter than the required 13 bytes.
    state.ihdr = Chunk(bytes_=b"short", chunk_type=_CHUNK_IHDR, crc=0, start=0, length=5)
    assert PNGConverter.build_decode_params(state, None) is None


# --------------------------------------------------------------------------
# dispatcher stubs that intentionally return None
# --------------------------------------------------------------------------
def test_convert_png_returns_none_without_ihdr() -> None:
    assert PNGConverter.convert_png(None, _PNGConverterState()) is None


def test_convert_png_returns_none_for_truncated_ihdr() -> None:
    state = _PNGConverterState()
    state.ihdr = Chunk(bytes_=b"short", chunk_type=_CHUNK_IHDR, crc=0, start=0, length=5)
    assert PNGConverter.convert_png(None, state) is None


def test_convert_png_indexed_routes_to_build_index_image(
    indexed_png_bytes: bytes,
) -> None:
    state = PNGConverter.parse_png_chunks(indexed_png_bytes)
    assert state is not None
    # Both builders are intentional ``None`` returns in the port; we only
    # care that the dispatch reaches them without raising.
    assert PNGConverter.convert_png(None, state) is None


def test_convert_png_non_indexed_routes_to_build_image_object(
    rgb_png_bytes: bytes,
) -> None:
    state = PNGConverter.parse_png_chunks(rgb_png_bytes)
    assert state is not None
    assert PNGConverter.convert_png(None, state) is None


def test_build_index_image_returns_none() -> None:
    assert PNGConverter.build_index_image(None, _PNGConverterState()) is None


def test_build_image_object_returns_none() -> None:
    assert PNGConverter.build_image_object(None, _PNGConverterState()) is None


def test_build_transparency_mask_returns_none_without_trns() -> None:
    state = _PNGConverterState()
    assert PNGConverter.build_transparency_mask_from_indexed_data(None, state) is None


def test_build_transparency_mask_returns_none_when_trns_present() -> None:
    state = _PNGConverterState()
    state.trns = Chunk(bytes_=b"", chunk_type=0, crc=0, start=0, length=0)
    assert PNGConverter.build_transparency_mask_from_indexed_data(None, state) is None


def test_setup_indexed_color_space_is_noop() -> None:
    """The ``LosslessFactory`` path handles indexed colour-space setup; the
    upstream-named stub returns ``None`` without side effects."""
    assert PNGConverter.setup_indexed_color_space(None, None, None, 8) is None


def test_create_cos_streamwith_icc_profile_is_noop() -> None:
    assert (
        PNGConverter.create_cos_streamwith_icc_profile(
            None, _PNGConverterState(), b"profile",
        )
        is None
    )


# --------------------------------------------------------------------------
# get_idat_input_stream
# --------------------------------------------------------------------------
def test_get_idat_input_stream_aggregates_idats(rgb_png_bytes: bytes) -> None:
    state = PNGConverter.parse_png_chunks(rgb_png_bytes)
    assert state is not None
    stream = PNGConverter.get_idat_input_stream(state)
    assert isinstance(stream, MultipleInputStream)
    assert len(stream.input_streams) == len(state.idats)


# --------------------------------------------------------------------------
# MultipleInputStream
# --------------------------------------------------------------------------
def test_multiple_input_stream_empty_available_is_zero() -> None:
    mis = MultipleInputStream()
    assert mis.available() == 0
    # ``read`` on an empty aggregator returns -1 (no-arg) or empty bytes.
    assert mis.read() == -1
    assert mis.read(8) == b""


def test_multiple_input_stream_concatenates_buffers() -> None:
    mis = MultipleInputStream()
    mis.input_streams = [b"hello", b"world"]
    assert mis.read(3) == b"hel"
    assert mis.read(5) == b"lowor"
    assert mis.read(100) == b"ld"


def test_multiple_input_stream_read_no_arg_yields_byte_by_byte() -> None:
    mis = MultipleInputStream()
    mis.input_streams = [b"ab", b"cd"]
    out: list[int] = []
    while True:
        byte = mis.read()
        if byte == -1:
            break
        assert isinstance(byte, int)
        out.append(byte)
    assert out == [97, 98, 99, 100]


def test_multiple_input_stream_skips_empty_chunks() -> None:
    """An empty buffer in the middle of the list must not stall the
    read loop — ``ensure_stream`` advances past it."""
    mis = MultipleInputStream()
    mis.input_streams = [b"", b"tail"]
    assert mis.read(4) == b"tail"


def test_multiple_input_stream_available_reflects_remaining(rgb_png_bytes: bytes) -> None:
    state = PNGConverter.parse_png_chunks(rgb_png_bytes)
    assert state is not None
    stream = PNGConverter.get_idat_input_stream(state)
    # Non-empty stream — ``available`` returns 1 (mirrors upstream's "at
    # least one byte" signal).
    assert stream.available() == 1


# --------------------------------------------------------------------------
# constructor guard
# --------------------------------------------------------------------------
def test_png_converter_constructor_raises_typeerror() -> None:
    """Mirrors upstream's private constructor — instantiation is a bug."""
    with pytest.raises(TypeError, match="static utility"):
        PNGConverter()
