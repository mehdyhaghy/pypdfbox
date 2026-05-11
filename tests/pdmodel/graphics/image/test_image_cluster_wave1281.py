"""Tests for the new image classes (Wave 1281)."""

from __future__ import annotations

import io

import pytest

from pypdfbox.pdmodel.graphics.image import (
    Chunk,
    CustomFactory,
    MultipleInputStream,
    PDImage,
    PNGConverter,
    PredictorEncoder,
    SampledImageReader,
)


def test_pd_image_is_abstract():
    with pytest.raises(TypeError):
        PDImage()


def test_custom_factory_invokes_callback():
    captured = {}

    def make(doc, data):
        captured["doc"] = doc
        captured["data"] = data
        return ("xobj", doc, data)

    fac = CustomFactory(make)
    assert fac.create_from_byte_array("doc", b"\x00\x01") == ("xobj", "doc", b"\x00\x01")
    assert captured == {"doc": "doc", "data": b"\x00\x01"}


def test_chunk_get_data_slices_bytes():
    chunk = Chunk(bytes_=b"abcdef", chunk_type=0x49484452, crc=0, start=2, length=3)
    assert chunk.get_data() == b"cde"


def test_png_converter_render_intent_mapping():
    name = PNGConverter.map_png_render_intent(0)
    assert name is not None
    assert PNGConverter.map_png_render_intent(99) is None


def test_png_converter_is_a_static_class():
    with pytest.raises(TypeError):
        PNGConverter()


def test_sampled_image_reader_is_a_static_class():
    with pytest.raises(TypeError):
        SampledImageReader()


def test_multiple_input_stream_reads_in_order():
    stream = MultipleInputStream([io.BytesIO(b"abc"), io.BytesIO(b"def")])
    assert stream.read() == b"abcdef"


def test_multiple_input_stream_partial_read():
    stream = MultipleInputStream([io.BytesIO(b"abc"), io.BytesIO(b"def")])
    assert stream.read(4) == b"abcd"
    assert stream.read(4) == b"ef"
    assert stream.read(4) == b""


def test_predictor_encoder_static_helpers():
    assert PredictorEncoder.png_filter_sub(120, 100) == 20
    assert PredictorEncoder.png_filter_up(120, 100) == 20
    assert PredictorEncoder.png_filter_average(120, 100, 50) == (120 - 75) & 0xFF
    assert PredictorEncoder.png_filter_paeth(100, 80, 90, 70) == (100 - 90) & 0xFF
    assert PredictorEncoder.est_compress_sum(b"\x00\x7f\x80\xff") == 0 + 0x7F + 128 + 1
