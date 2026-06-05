"""Per-kernel parity for the JBIG2 resampling filters (wave 1492).

Wave 1490 ported the AWT ``Resizer`` / ``Filter`` pipeline and proved the
*Gaussian* kernel byte-exact against the 3.0.7 jar (that is the kernel the JBIG2
``readRaster`` path hardwires). The other fourteen ``FilterType`` members
(Bessel, Blackman, Box, Catrom, Cubic, Hamming, Hanning, Hermite, Lanczos,
Mitchell, Point, Quadratic, Sinc, Triangle) were unreachable through
``readRaster`` and therefore untested at the byte level.

This module reaches them two ways:

* **Live differential oracle** — ``oracle/probes/Jbig2ReaderProbe.java`` grew an
  optional ``filterName`` argument; when present it bypasses ``readRaster``,
  decodes the page bitmap via the package-private ``JBIG2Document`` ->
  ``JBIG2Page.getBitmap()`` pipeline, and dumps
  ``Bitmaps.asRaster(bitmap, param, FilterType.valueOf(name))``. We drive every
  kernel over a real fixture and assert the resampled grayscale raster is
  identical to pypdfbox's ``Bitmaps.as_raster(..., FilterType.X)``.

* **Hand-written kernel-math pins** — characteristic ``f(x)`` values (including
  the support-edge discontinuities and the symmetry/evenness each kernel
  guarantees) lifted directly from the upstream kernel definitions, so the
  polynomial coefficients stay pinned even without the jar.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from pypdfbox.jbig2.image.bitmaps import Bitmaps
from pypdfbox.jbig2.image.filter import (
    Bessel,
    Blackman,
    Box,
    Catrom,
    Cubic,
    Filter,
    FilterType,
    Hamming,
    Hanning,
    Hermite,
    Lanczos,
    Mitchell,
    Point,
    Quadratic,
    Sinc,
    Triangle,
    _to_float32,
)
from pypdfbox.jbig2.io.image_input_stream import ImageInputStream
from pypdfbox.jbig2.jbig2_document import JBIG2Document
from pypdfbox.jbig2.jbig2_read_param import JBIG2ReadParam
from tests.oracle.harness import requires_oracle, run_probe_text

_FIXTURES = Path(__file__).resolve().parent / "fixtures"

_ALL_KERNELS = [
    "Bessel", "Blackman", "Box", "Catrom", "Cubic", "Gaussian", "Hamming",
    "Hanning", "Hermite", "Lanczos", "Mitchell", "Point", "Quadratic", "Sinc",
    "Triangle",
]


# --------------------------------------------------------------------------
# Live differential oracle — every kernel, byte-for-byte vs the 3.0.7 jar.
# --------------------------------------------------------------------------

# (name, fixture, region(x,y,w,h | 0,0,0,0=none), render(w,h))
_KERNEL_SCALE_CASES = [
    ("down_003", "003.jb2", (0, 0, 0, 0), (255, 330)),
    ("down_nonint_003", "003.jb2", (0, 0, 0, 0), (100, 130)),
    ("region_005", "005.jb2", (50, 50, 300, 300), (150, 150)),
    ("region_up_006", "006.jb2", (0, 0, 250, 250), (500, 500)),
]


def _py_kernel_raster(filename: str, region, render, kernel: str) -> str:
    data = (_FIXTURES / filename).read_bytes()
    rx, ry, rw, rh = region
    bitmap = JBIG2Document(ImageInputStream(data)).get_page(1).get_bitmap()
    region_tuple = (rx, ry, rw, rh) if rw > 0 and rh > 0 else None
    param = JBIG2ReadParam(1, 1, 0, 0, region_tuple, render)
    raster = Bitmaps.as_raster(param=param, bitmap=bitmap,
                               filter_type=getattr(FilterType, kernel.upper()))
    return bytes(raster).hex()


@requires_oracle
@pytest.mark.parametrize("kernel", _ALL_KERNELS)
@pytest.mark.parametrize(
    ("name", "filename", "region", "render"),
    _KERNEL_SCALE_CASES,
    ids=[c[0] for c in _KERNEL_SCALE_CASES],
)
def test_kernel_raster_matches_pdfbox(name, filename, region, render, kernel):
    data = (_FIXTURES / filename).read_bytes()
    rx, ry, rw, rh = region
    rrw, rrh = render
    java = run_probe_text(
        "Jbig2ReaderProbe",
        data.hex(),
        "0",
        str(rx), str(ry), str(rw), str(rh),
        "1", "1", "0", "0",
        str(rrw), str(rrh),
        kernel,
    ).strip()
    # The probe still prints "<numImages> <width> <height> <hexbytes>"; only the
    # raster bytes are kernel-dependent, so compare the last field.
    java_hex = java.split()[3] if len(java.split()) > 3 else ""
    assert _py_kernel_raster(filename, region, render, kernel) == java_hex


# --------------------------------------------------------------------------
# Hand-written kernel-math pins (jar-independent).
#
# Each kernel's f(x) is a verbatim port; pin its value at characteristic points
# — the centre, the support edge(s) where the piecewise definition flips, and a
# symmetry check (every kernel here is even: f(x) == f(-x)).
# --------------------------------------------------------------------------


def test_bessel_centre_and_support():
    b = Bessel()
    assert b.support == 3.2383
    assert b.cardinal is False
    # f(0) == pi/4 by the explicit x == 0 branch.
    assert b.f(0.0) == math.pi / 4.0
    # even function
    assert b.f(1.7) == pytest.approx(b.f(-1.7))
    # the J1-based body is continuous; a first positive zero of J1(pi*x)/(2x)
    # lies past x ~ 1.2197 (first zero of J1 at ~3.8317 => x ~ 1.2197).
    assert b.f(1.2197) == pytest.approx(0.0, abs=1e-4)


def test_bessel_large_argument_asymptotic_branch():
    # For |pi*x| >= 8 (x >= ~2.546) the Bessel J1 evaluation switches to its
    # asymptotic _p1/_q1 expansion. x == 3.0 (within the 3.2383 support) drives
    # that branch; the value stays small and the function remains even.
    b = Bessel()
    assert b.f(3.0) == pytest.approx(b.f(-3.0))
    # sanity bound: |J1(3pi)/(6)| is small and finite, not NaN/inf.
    assert abs(b.f(3.0)) < 0.1


def test_blackman_window():
    b = Blackman()
    # 0.42 + 0.5*cos(0) + 0.08*cos(0) == 1.0
    assert b.f(0.0) == pytest.approx(1.0)
    # at x == 1: 0.42 + 0.5*cos(pi) + 0.08*cos(2pi) == 0.42 - 0.5 + 0.08 == 0.0
    assert b.f(1.0) == pytest.approx(0.0)
    assert b.f(0.6) == pytest.approx(b.f(-0.6))


def test_box_and_point_edges():
    box = Box()
    assert box.support == 0.5
    assert box.f(-0.5) == 1.0      # left edge inclusive
    assert box.f(0.0) == 1.0
    assert box.f(0.4999) == 1.0
    assert box.f(0.5) == 0.0       # right edge exclusive
    point = Point()
    assert point.support == 0
    # Point skips windowing, so f_windowed delegates straight to Box.f.
    assert point.f_windowed(0.0) == 1.0
    assert point.f_windowed(0.5) == 0.0


def test_catrom_piecewise():
    c = Catrom()
    assert c.support == 2.0
    assert c.f(0.0) == pytest.approx(1.0)   # 0.5*(2) == 1
    assert c.f(1.0) == pytest.approx(0.0)   # 0.5*(2 + (-5+3)) == 0
    assert c.f(2.0) == 0.0                  # out of support
    assert c.f(0.5) == pytest.approx(c.f(-0.5))
    # interior value of the [0,1) cubic: 0.5*(2 + 0.25*(-5 + 1.5))
    assert c.f(0.5) == pytest.approx(0.5 * (2.0 + 0.25 * (-5.0 + 0.5 * 3.0)))


def test_cubic_bspline():
    c = Cubic()
    assert c.support == 2.0
    assert c.f(0.0) == pytest.approx(2.0 / 3.0)
    # at x==1 both branches meet at 1/6.
    assert c.f(1.0) == pytest.approx(1.0 / 6.0)
    assert c.f(2.0) == 0.0
    assert c.f(1.5) == pytest.approx(c.f(-1.5))


def test_hamming_window():
    h = Hamming()
    assert h.f(0.0) == pytest.approx(1.0)        # 0.54 + 0.46
    assert h.f(1.0) == pytest.approx(0.08)       # 0.54 + 0.46*cos(pi)
    assert h.f(0.3) == pytest.approx(h.f(-0.3))


def test_hanning_window():
    h = Hanning()
    assert h.f(0.0) == pytest.approx(1.0)
    assert h.f(1.0) == pytest.approx(0.0)
    assert h.f(0.3) == pytest.approx(h.f(-0.3))


def test_hermite_piecewise():
    h = Hermite()
    assert h.f(0.0) == pytest.approx(1.0)
    assert h.f(1.0) == 0.0                  # (2-3)*1 + 1 == 0
    assert h.f(2.0) == 0.0
    assert h.f(0.5) == pytest.approx(h.f(-0.5))
    assert h.f(0.5) == pytest.approx((2.0 * 0.5 - 3.0) * 0.25 + 1.0)


def test_lanczos_sinc_product():
    lz = Lanczos()
    assert lz.support == 3.0
    assert lz.f(0.0) == pytest.approx(1.0)   # sinc(0)*sinc(0) == 1
    assert lz.f(1.0) == pytest.approx(0.0, abs=1e-6)  # sinc(1)==0
    assert lz.f(3.0) == 0.0                  # out of support
    assert lz.f(2.0) == pytest.approx(lz.f(-2.0))
    # upstream truncates the product to float32; pin that.
    sinc = lambda v: 1.0 if v == 0 else math.sin(v * math.pi) / (v * math.pi)  # noqa: E731
    assert lz.f(1.5) == _to_float32(sinc(1.5) * sinc(1.5 / 3.0))


def test_mitchell_piecewise():
    m = Mitchell()
    assert m.support == 2.0
    # b == c == 1/3. At x==0: (6 - 2b)/6 == (6 - 2/3)/6
    assert m.f(0.0) == pytest.approx((6.0 - 2.0 / 3.0) / 6.0)
    assert m.f(2.0) == 0.0
    assert m.f(1.3) == pytest.approx(m.f(-1.3))


def test_quadratic_piecewise():
    q = Quadratic()
    assert q.support == 1.5
    assert q.f(0.0) == pytest.approx(0.75)
    assert q.f(0.5) == pytest.approx(0.5)      # 0.75 - 0.25 == 0.5
    assert q.f(1.5) == 0.0
    assert q.f(0.75) == pytest.approx(q.f(-0.75))
    # interior of the second branch: at x==1, (1-1.5)^2*0.5 == 0.125
    assert q.f(1.0) == pytest.approx(0.5 * (1.0 - 1.5) ** 2)


def test_sinc_kernel():
    s = Sinc()
    assert s.support == 4.0
    assert s.f(0.0) == 1.0
    assert s.f(1.0) == pytest.approx(0.0, abs=1e-12)  # sin(pi)/pi
    assert s.f(0.5) == pytest.approx(math.sin(0.5 * math.pi) / (0.5 * math.pi))
    assert s.f(2.3) == pytest.approx(s.f(-2.3))


def test_triangle_kernel():
    t = Triangle()
    assert t.f(0.0) == 1.0
    assert t.f(0.5) == 0.5
    assert t.f(1.0) == 0.0
    assert t.f(0.25) == pytest.approx(t.f(-0.25))


def test_f_windowed_clips_outside_support():
    # f_windowed returns 0 strictly outside [-support, support] for a kernel
    # whose f(x) would otherwise be non-zero there. Sinc's support is 4.
    s = Sinc()
    assert s.f_windowed(4.5) == 0.0
    assert s.f_windowed(-4.5) == 0.0
    # inside support it equals f(x).
    assert s.f_windowed(0.5) == s.f(0.5)


def test_by_type_round_trips_every_member():
    expected = {
        FilterType.BESSEL: Bessel, FilterType.BLACKMAN: Blackman,
        FilterType.BOX: Box, FilterType.CATROM: Catrom, FilterType.CUBIC: Cubic,
        FilterType.HAMMING: Hamming, FilterType.HANNING: Hanning,
        FilterType.HERMITE: Hermite, FilterType.LANCZOS: Lanczos,
        FilterType.MITCHELL: Mitchell, FilterType.POINT: Point,
        FilterType.QUADRATIC: Quadratic, FilterType.SINC: Sinc,
        FilterType.TRIANGLE: Triangle,
    }
    for ft, cls in expected.items():
        assert isinstance(Filter.by_type(ft), cls)


def test_get_name_is_simple_class_name():
    assert Lanczos().get_name() == "Lanczos"
    assert Mitchell().get_name() == "Mitchell"
