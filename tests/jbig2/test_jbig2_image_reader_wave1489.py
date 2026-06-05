"""Tests for the JBIG2 ImageIO-surface port (wave 1489).

Covers :class:`JBIG2ImageReader`, :class:`JBIG2ImageReaderSpi` and
:class:`JBIG2ReadParam` — the ``javax.imageio`` entry points of the upstream
``apache/pdfbox-jbig2`` library. The underlying decode is already bit-exact
versus Java (see ``tests/jbig2/oracle/test_jbig2_page_oracle.py``); these tests
focus on the reader's API contract (index bounds, missing input, default read
param, globals handling) and on byte-for-byte parity of ``read_raster`` /
``read`` output shapes against the proven page-decode path. A live-oracle
differential drives the real Java ``JBIG2ImageReader.readRaster`` through
``oracle/probes/Jbig2ReaderProbe.java`` and asserts identical packed-raster
bytes, num-images and dimensions for a matrix of source-region / subsampling
read params.

Java -> Python mappings exercised here:

* ``IndexOutOfBoundsException`` (page index out of range) -> ``IndexError``.
* ``IOException`` (input not set) -> ``OSError``.
* ``ArrayIndexOutOfBoundsException`` from the upstream X-only/Y-only
  subsampling dimension bug -> ``IndexError`` (verified against the 3.0.7 jar).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.filter.jbig2_decode import _inverted_bitmap_bytes
from pypdfbox.jbig2.io.image_input_stream import ImageInputStream
from pypdfbox.jbig2.jbig2_document import JBIG2Document
from pypdfbox.jbig2.jbig2_image_reader import JBIG2ImageReader
from pypdfbox.jbig2.jbig2_image_reader_spi import JBIG2ImageReaderSpi
from pypdfbox.jbig2.jbig2_read_param import JBIG2ReadParam
from tests.oracle.harness import requires_oracle, run_probe_text

_FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _reader(filename: str) -> JBIG2ImageReader:
    data = (_FIXTURES / filename).read_bytes()
    reader = JBIG2ImageReader(JBIG2ImageReaderSpi())
    reader.set_input(ImageInputStream(data))
    return reader


# --------------------------------------------------------------------------
# JBIG2ReadParam
# --------------------------------------------------------------------------


def test_read_param_defaults():
    param = JBIG2ReadParam()
    assert param.get_source_x_subsampling() == 1
    assert param.get_source_y_subsampling() == 1
    assert param.get_subsampling_x_offset() == 0
    assert param.get_subsampling_y_offset() == 0
    assert param.get_source_region() is None
    assert param.get_source_render_size() is None
    assert param.can_set_source_render_size_() is True


def test_read_param_full_constructor():
    param = JBIG2ReadParam(2, 3, 1, 2, (10, 20, 30, 40), (100, 200))
    assert param.get_source_x_subsampling() == 2
    assert param.get_source_y_subsampling() == 3
    assert param.get_subsampling_x_offset() == 1
    assert param.get_subsampling_y_offset() == 2
    assert param.get_source_region() == (10, 20, 30, 40)
    assert param.get_source_render_size() == (100, 200)


def test_read_param_rejects_zero_subsampling():
    with pytest.raises(ValueError):
        JBIG2ReadParam(0, 1, 0, 0, None, None)
    with pytest.raises(ValueError):
        JBIG2ReadParam(1, 0, 0, 0, None, None)


def test_read_param_setters_validate():
    param = JBIG2ReadParam()
    with pytest.raises(ValueError):
        param.set_source_subsampling(2, 2, 2, 0)  # offset >= factor
    with pytest.raises(ValueError):
        param.set_source_region((0, 0, 0, 10))  # non-positive width


# --------------------------------------------------------------------------
# JBIG2ImageReaderSpi
# --------------------------------------------------------------------------


def test_spi_can_decode_standalone():
    spi = JBIG2ImageReaderSpi()
    data = (_FIXTURES / "003.jb2").read_bytes()
    assert spi.can_decode_input(ImageInputStream(data)) is True


def test_spi_cannot_decode_embedded_without_header():
    spi = JBIG2ImageReaderSpi()
    data = (_FIXTURES / "21.jb2").read_bytes()  # bare segments, no file header
    assert spi.can_decode_input(ImageInputStream(data)) is False


def test_spi_non_stream_source_returns_false():
    assert JBIG2ImageReaderSpi().can_decode_input(object()) is False


def test_spi_none_source_raises():
    with pytest.raises(ValueError):
        JBIG2ImageReaderSpi().can_decode_input(None)


def test_spi_description_and_reader_instance():
    spi = JBIG2ImageReaderSpi()
    assert spi.get_description() == "JBIG2 Image Reader"
    assert spi.get_description(locale="en_US") == "JBIG2 Image Reader"
    assert isinstance(spi.create_reader_instance(), JBIG2ImageReader)


def test_spi_metadata_constants():
    spi = JBIG2ImageReaderSpi()
    assert spi.VENDOR == "Apache Software Foundation"
    assert spi.NAMES == ("jbig2", "JBIG2")
    assert spi.SUFFIXES == ("jb2", "jbig2", "JB2", "JBIG2")
    assert spi.MIME_TYPES == ("image/x-jbig2", "image/x-jb2")
    assert spi.SUPPORTS_STANDARD_STREAM_METADATE_FORMAT is False
    assert spi.SUPPORTS_STANDARD_IMAGE_METADATA_FORMAT is False


# --------------------------------------------------------------------------
# JBIG2ImageReader — API contract
# --------------------------------------------------------------------------


def test_num_images_allow_search():
    assert _reader("003.jb2").get_num_images(True) == 1


def test_num_images_no_search_returns_minus_one():
    assert _reader("003.jb2").get_num_images(False) == -1


def test_multipage_num_images():
    # 20123110001.jb2 is a 3-page document.
    assert _reader("20123110001.jb2").get_num_images(True) == 3


def test_width_height():
    reader = _reader("003.jb2")
    assert reader.get_width(0) == 2550
    assert reader.get_height(0) == 3305


def test_get_stream_metadata_is_none():
    assert _reader("003.jb2").get_stream_metadata() is None


def test_get_image_metadata_returns_page():
    reader = _reader("003.jb2")
    page = reader.get_image_metadata(0)
    assert page.get_width() == 2550
    assert page.get_height() == 3305


def test_get_image_types():
    assert _reader("003.jb2").get_image_types(0) == ["1"]


def test_can_read_raster():
    assert _reader("003.jb2").can_read_raster() is True


def test_get_default_read_param():
    param = _reader("003.jb2").get_default_read_param()
    assert isinstance(param, JBIG2ReadParam)
    assert param.get_source_region() is None


def test_index_out_of_bounds_raises_index_error():
    reader = _reader("003.jb2")
    with pytest.raises(IndexError):
        reader.get_width(99)
    with pytest.raises(IndexError):
        reader.read(99)


def test_missing_input_raises_os_error():
    reader = JBIG2ImageReader()
    with pytest.raises(OSError):
        reader.get_num_images(True)
    with pytest.raises(OSError):
        reader.read(0)


def test_set_input_invalidates_document():
    reader = _reader("003.jb2")
    assert reader.get_width(0) == 2550
    # Re-point at a different fixture; the cached document must be dropped.
    reader.set_input(ImageInputStream((_FIXTURES / "005.jb2").read_bytes()))
    assert reader.get_width(0) == 2544


def test_set_globals_invalidates_document():
    reader = JBIG2ImageReader()
    reader.set_input(ImageInputStream((_FIXTURES / "21.jb2").read_bytes()))
    globals_doc = JBIG2Document(ImageInputStream((_FIXTURES / "21.glob").read_bytes()))
    reader.set_globals(globals_doc.get_global_segments())
    # With globals wired, the embedded page decodes.
    assert reader.get_width(0) > 0


def test_process_globals():
    reader = JBIG2ImageReader()
    globals_ = reader.process_globals(
        ImageInputStream((_FIXTURES / "21.glob").read_bytes())
    )
    assert globals_ is not None


def test_get_globals_after_decode():
    reader = _reader("003.jb2")
    reader.read(0)
    assert reader.get_globals() is not None


# --------------------------------------------------------------------------
# read / read_raster output parity with the proven page-decode path
# --------------------------------------------------------------------------


@pytest.mark.parametrize("filename", ["003.jb2", "005.jb2", "20123110001.jb2"])
def test_read_raster_matches_inverted_bitmap_bytes(filename):
    """Default (unscaled, no-region, no-subsample) raster == the filter path.

    ``_inverted_bitmap_bytes`` is the bit-exact-vs-Java byte buffer the
    ``/JBIG2Decode`` filter writes; the reader's default raster must equal it.
    """
    data = (_FIXTURES / filename).read_bytes()
    reader = JBIG2ImageReader()
    reader.set_input(ImageInputStream(data))
    raster = reader.read_raster(0, JBIG2ReadParam(1, 1, 0, 0, None, None))

    bitmap = JBIG2Document(ImageInputStream(data)).get_page(1).get_bitmap()
    assert bytes(raster) == _inverted_bitmap_bytes(bitmap)


def test_read_returns_one_bit_pil_image():
    reader = _reader("003.jb2")
    image = reader.read(0)
    assert image.mode == "1"
    assert image.size == (2550, 3305)


def test_read_source_region_shape():
    reader = _reader("003.jb2")
    param = JBIG2ReadParam(1, 1, 0, 0, (0, 0, 100, 50), None)
    image = reader.read(0, param)
    assert image.size == (100, 50)
    raster = reader.read_raster(0, param)
    assert len(raster) == 50 * ((100 + 7) // 8)


def test_read_subsampling_shape():
    reader = _reader("003.jb2")
    # 2x2 subsampling of 2550x3305 -> integer division (3.0.7 jar) 1275x1652.
    param = JBIG2ReadParam(2, 2, 0, 0, None, None)
    image = reader.read(0, param)
    assert image.size == (1275, 1652)


def test_x_only_subsampling_raises_like_upstream_bug():
    """3.0.7 subsampleX derives the wrong height; out-of-range -> IndexError."""
    reader = _reader("003.jb2")
    param = JBIG2ReadParam(1, 2, 0, 1, None, None)  # y-only triggers the bug
    with pytest.raises(IndexError):
        reader.read_raster(0, param)


# --------------------------------------------------------------------------
# Live differential oracle — drive the real Java JBIG2ImageReader.readRaster
# --------------------------------------------------------------------------

# (name, fixture, page_index, region(x,y,w,h | 0,0,0,0=none), xsub, ysub, xoff, yoff)
_ORACLE_CASES = [
    ("default", "003.jb2", 0, (0, 0, 0, 0), 1, 1, 0, 0),
    ("region", "003.jb2", 0, (100, 200, 300, 150), 1, 1, 0, 0),
    ("subsample_2x2", "003.jb2", 0, (0, 0, 0, 0), 2, 2, 0, 0),
    ("subsample_4x3_off", "003.jb2", 0, (0, 0, 0, 0), 4, 3, 2, 1),
    ("region_plus_subsample", "003.jb2", 0, (50, 50, 500, 400), 2, 2, 1, 1),
    ("default_005", "005.jb2", 0, (0, 0, 0, 0), 1, 1, 0, 0),
    ("subsample_005", "005.jb2", 0, (0, 0, 0, 0), 2, 2, 0, 0),
    ("multipage_p0", "20123110001.jb2", 0, (0, 0, 0, 0), 1, 1, 0, 0),
    ("multipage_subsample", "20123110001.jb2", 0, (0, 0, 0, 0), 2, 2, 0, 0),
]


@requires_oracle
@pytest.mark.parametrize(
    ("name", "filename", "page_index", "region", "xsub", "ysub", "xoff", "yoff"),
    _ORACLE_CASES,
    ids=[c[0] for c in _ORACLE_CASES],
)
def test_read_raster_matches_pdfbox(
    name, filename, page_index, region, xsub, ysub, xoff, yoff
):
    data = (_FIXTURES / filename).read_bytes()
    rx, ry, rw, rh = region
    java = run_probe_text(
        "Jbig2ReaderProbe",
        data.hex(),
        str(page_index),
        str(rx),
        str(ry),
        str(rw),
        str(rh),
        str(xsub),
        str(ysub),
        str(xoff),
        str(yoff),
    ).strip()

    reader = JBIG2ImageReader()
    reader.set_input(ImageInputStream(data))
    region_tuple = (rx, ry, rw, rh) if rw > 0 and rh > 0 else None
    param = JBIG2ReadParam(xsub, ysub, xoff, yoff, region_tuple, None)
    raster = reader.read_raster(page_index, param)
    py = (
        f"{reader.get_num_images(True)} "
        f"{reader.get_width(page_index)} "
        f"{reader.get_height(page_index)} "
        f"{bytes(raster).hex()}"
    )
    assert py == java
