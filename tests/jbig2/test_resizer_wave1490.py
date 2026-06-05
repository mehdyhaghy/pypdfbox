"""Tests for the JBIG2 scaled-render pipeline (wave 1490).

Covers the ported AWT ``Resizer`` / ``Filter`` resampling pipeline
(:mod:`pypdfbox.jbig2.image.resizer`, :mod:`pypdfbox.jbig2.image.filter`) and
its wiring into :meth:`Bitmaps.as_raster` / :meth:`Bitmaps.as_buffered_image`
via :class:`JBIG2ReadParam`'s ``source_render_size``. Wave 1489 left the scaled
path raising ``NotImplementedError``; this wave removes that.

The kernels and resampler are a faithful port of ``apache/pdfbox-jbig2``'s
filtered-zoom resizer (Graphics Gems III), matched byte-for-byte against the
bundled PDFBox 3.0.7 jar — the live differential below drives the real Java
``JBIG2ImageReader.readRaster`` with a render size and asserts identical bytes.

Java -> Python mappings:

* scaled output raster is single-band 8-bit grayscale (``DataBufferByte``) ->
  the row-major ``bytes`` of ``read_raster`` and a PIL mode ``"L"`` image.
* the unscaled bilevel raster (mode ``"1"``) is unchanged from wave 1489.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.jbig2.image.filter import (
    Box,
    Filter,
    FilterType,
    Gaussian,
    Lanczos,
    Point,
    Triangle,
)
from pypdfbox.jbig2.io.image_input_stream import ImageInputStream
from pypdfbox.jbig2.jbig2_image_reader import JBIG2ImageReader
from pypdfbox.jbig2.jbig2_read_param import JBIG2ReadParam
from tests.oracle.harness import requires_oracle, run_probe_text

_FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _reader(filename: str) -> JBIG2ImageReader:
    data = (_FIXTURES / filename).read_bytes()
    reader = JBIG2ImageReader()
    reader.set_input(ImageInputStream(data))
    return reader


# --------------------------------------------------------------------------
# FilterType / Filter
# --------------------------------------------------------------------------


def test_filter_type_default_is_triangle():
    assert FilterType.get_default_filter_type() is FilterType.TRIANGLE


def test_filter_type_set_default_round_trips():
    try:
        FilterType.set_default_filter_type(FilterType.LANCZOS)
        assert FilterType.get_default_filter_type() is FilterType.LANCZOS
    finally:
        FilterType.set_default_filter_type(FilterType.TRIANGLE)


def test_filter_member_order_matches_upstream():
    assert [m.value for m in FilterType] == [
        "Bessel", "Blackman", "Box", "Catrom", "Cubic", "Gaussian", "Hamming",
        "Hanning", "Hermite", "Lanczos", "Mitchell", "Point", "Quadratic",
        "Sinc", "Triangle",
    ]


def test_filter_name_and_type_round_trip():
    assert Filter.name_by_type(FilterType.GAUSSIAN) == "Gaussian"
    assert Filter.type_by_name("Lanczos") is FilterType.LANCZOS


def test_filter_type_by_name_unknown_raises():
    with pytest.raises(ValueError):
        Filter.type_by_name("NoSuchFilter")


def test_filter_by_type_instances():
    assert isinstance(Filter.by_type(FilterType.GAUSSIAN), Gaussian)
    assert isinstance(Filter.by_type(FilterType.TRIANGLE), Triangle)
    assert isinstance(Filter.by_type(FilterType.LANCZOS), Lanczos)


def test_filter_supports_and_cardinality():
    # values lifted verbatim from upstream constructors
    assert Gaussian().support == 1.25
    assert Gaussian().cardinal is False
    assert Triangle().support == 1.0  # default ctor
    assert Triangle().cardinal is True
    assert Lanczos().support == 3.0
    assert Lanczos().cardinal is True


def test_box_and_point_kernels():
    box = Box()
    assert box.f(0.0) == 1.0
    assert box.f(0.5) == 0.0
    assert box.f(-0.5) == 1.0
    point = Point()
    assert point.support == 0
    # Point overrides f_windowed to skip windowing.
    assert point.f_windowed(0.0) == 1.0


def test_triangle_kernel_values():
    t = Triangle()
    assert t.f(0.0) == 1.0
    assert t.f(0.5) == 0.5
    assert t.f(1.0) == 0.0
    assert t.f(-0.25) == 0.75


def test_gaussian_kernel_symmetric():
    g = Gaussian()
    assert g.f(0.3) == pytest.approx(g.f(-0.3))
    assert g.f(0.0) == pytest.approx((2.0 / 3.141592653589793) ** 0.5)


# --------------------------------------------------------------------------
# Reader scaled-render shapes (no NotImplementedError)
# --------------------------------------------------------------------------


def test_scaled_read_raster_shape_downscale():
    reader = _reader("003.jb2")  # 2550 x 3305
    param = JBIG2ReadParam(1, 1, 0, 0, None, (255, 330))
    raster = reader.read_raster(0, param)
    # scaled raster is 8-bit grayscale, 1 byte per pixel, row-major.
    assert len(raster) == 255 * 330


def test_scaled_read_returns_grayscale_image():
    reader = _reader("003.jb2")
    param = JBIG2ReadParam(1, 1, 0, 0, None, (255, 330))
    image = reader.read(0, param)
    assert image.mode == "L"
    assert image.size == (255, 330)


def test_scaled_read_dimensions_use_round():
    # round(2550 * (100/2550)) == 100 ; round(3305 * (100/3305)) == 100
    reader = _reader("003.jb2")
    param = JBIG2ReadParam(1, 1, 0, 0, None, (100, 100))
    image = reader.read(0, param)
    assert image.size == (100, 100)
    assert len(reader.read_raster(0, param)) == 100 * 100


def test_region_then_scale_shape():
    reader = _reader("003.jb2")  # full page 2550 x 3305
    # Upstream computes the scale factor against the *full* bitmap
    # (renderW / fullW), then extracts the region and scales the extracted
    # bitmap by that factor. So render (300, 225) over a 200x150 region of a
    # 2550x3305 page yields round(200*300/2550) x round(150*225/3305) = 24 x 10
    # (verified byte-exact against the 3.0.7 jar). The render size is *not* the
    # output size when a source region is present.
    param = JBIG2ReadParam(1, 1, 0, 0, (100, 100, 200, 150), (300, 225))
    image = reader.read(0, param)
    assert image.mode == "L"
    assert image.size == (24, 10)
    assert len(reader.read_raster(0, param)) == 24 * 10


def test_unscaled_path_unchanged_when_render_size_equals_source():
    reader = _reader("003.jb2")
    # render size == source dims -> scale 1 -> still the bilevel mode "1" path.
    param = JBIG2ReadParam(1, 1, 0, 0, None, (2550, 3305))
    image = reader.read(0, param)
    assert image.mode == "1"
    assert image.size == (2550, 3305)


# --------------------------------------------------------------------------
# Live differential oracle — drive the real Java JBIG2ImageReader.readRaster
# with a sourceRenderSize and assert byte-exact grayscale rasters.
# --------------------------------------------------------------------------

# (name, fixture, region(x,y,w,h | 0,0,0,0=none), render(w,h))
_SCALE_CASES = [
    ("down_int_003", "003.jb2", (0, 0, 0, 0), (255, 330)),
    ("down_nonint_003", "003.jb2", (0, 0, 0, 0), (100, 100)),
    ("down_frac_003", "003.jb2", (0, 0, 0, 0), (382, 495)),
    ("region_up_003", "003.jb2", (100, 100, 200, 150), (300, 225)),
    ("region_down_003", "003.jb2", (0, 0, 400, 300), (100, 75)),
    ("region_half_005", "005.jb2", (50, 50, 300, 300), (150, 150)),
    ("region_up2x_006", "006.jb2", (0, 0, 250, 250), (500, 500)),
    ("down_multipage", "20123110001.jb2", (0, 0, 0, 0), (128, 167)),
]


@requires_oracle
@pytest.mark.parametrize(
    ("name", "filename", "region", "render"),
    _SCALE_CASES,
    ids=[c[0] for c in _SCALE_CASES],
)
def test_scaled_read_raster_matches_pdfbox(name, filename, region, render):
    data = (_FIXTURES / filename).read_bytes()
    rx, ry, rw, rh = region
    rrw, rrh = render
    java = run_probe_text(
        "Jbig2ReaderProbe",
        data.hex(),
        "0",
        str(rx),
        str(ry),
        str(rw),
        str(rh),
        "1",
        "1",
        "0",
        "0",
        str(rrw),
        str(rrh),
    ).strip()

    reader = JBIG2ImageReader()
    reader.set_input(ImageInputStream(data))
    region_tuple = (rx, ry, rw, rh) if rw > 0 and rh > 0 else None
    param = JBIG2ReadParam(1, 1, 0, 0, region_tuple, (rrw, rrh))
    raster = reader.read_raster(0, param)
    py = (
        f"{reader.get_num_images(True)} "
        f"{reader.get_width(0)} "
        f"{reader.get_height(0)} "
        f"{bytes(raster).hex()}"
    )
    assert py == java
