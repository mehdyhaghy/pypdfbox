"""Live PDFBox differential fuzz of the PDRectangle <-> Matrix INTERACTION
(wave 1561).

Prior probes split this surface: ``RectangleFuzzProbe`` (wave 1524) covers
``PDRectangle(COSArray)`` malformed construction + accessors; ``MatrixOpsFuzzProbe``
(wave 1532) and ``MatrixFloat32Probe`` (wave 1485) cover ``Matrix`` algebra in
isolation. This wave's NEW angle is the *crossing* edges neither covers:

* **PDRectangle.transform(Matrix)** — the four corners projected through a
  rotation / scale / shear / translate / singular matrix. Upstream returns a
  ``java.awt.geom.GeneralPath``; pypdfbox returns the same corners as a
  ``list[tuple[float, float]]`` in the identical corner order
  ``(llx,lly), (urx,lly), (urx,ury), (llx,ury)``. The probe reads the path back
  through its ``PathIterator``; we compare corner-for-corner.
* **getScalingFactorX/Y** on a rotated-then-scaled matrix, a sheared matrix, a
  singular matrix, and a pure 90 rotation.
* **contains(x,y)** exactly on each of the four edges and the corners (all
  inclusive) plus just-outside points.
* **Matrix multiply order** applied to a rectangle: scale-then-rotate vs
  rotate-then-scale project a rectangle's corners to different points.
* **transform of an inverted (normalized) MediaBox** through a 90 rotation.
* **float32 rounding** of a chained matrix product's cells.

Every scalar PDFBox emits here is a Java ``float`` (``Matrix`` is a
``float[]``); the comparison renders each value with :func:`float_to_string`
(the raw ``Float.toString`` port the probe's ``println(float)`` uses) so the
match is float32-exact.

**width/height precision (CLOSED wave 1569).** Upstream ``getWidth`` /
``getHeight`` subtract two ``float`` cells and return a ``float`` (float32);
``PDRectangle`` now narrows every stored corner to float32 on construction (it
mirrors upstream's ``COSArray``-of-``COSFloat`` backing) and narrows the
subtraction result, so non-float-representable corners no longer expose a
float-vs-double width cliff. For every case fuzzed here the corners are integer
so the rendered ``Float.toString`` already agreed; the non-representable case is
now pinned by ``test_pd_rectangle_matrix_fuzz_wave1569``. Pinned values below
pass WITHOUT the oracle; the ``@requires_oracle`` differential at the bottom
re-derives every line live against the PDFBox 3.0.7 jar.
"""

from __future__ import annotations

import math

import pytest

from pypdfbox.cos.cos_array import COSArray
from pypdfbox.cos.cos_float import COSFloat, float_to_string
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from pypdfbox.util.matrix import Matrix


def _box(llx: float, lly: float, urx: float, ury: float) -> COSArray:
    a = COSArray()
    for v in (llx, lly, urx, ury):
        a.add(COSFloat(float(v)))
    return a


def _fs(value: float) -> str:
    return float_to_string(value)


def _corners(rect: PDRectangle, m: Matrix) -> list[tuple[str, str]]:
    return [(_fs(x), _fs(y)) for x, y in rect.transform(m)]


# --- inverted-MediaBox normalization -------------------------------------


def test_inverted_media_box_normalizes() -> None:
    inv = PDRectangle.from_cos_array(_box(400, 300, 50, 100))
    assert (_fs(inv.lower_left_x), _fs(inv.lower_left_y)) == ("50.0", "100.0")
    assert (_fs(inv.upper_right_x), _fs(inv.upper_right_y)) == ("400.0", "300.0")
    assert (_fs(inv.width), _fs(inv.height)) == ("350.0", "200.0")


def test_inverted_y_only_normalizes() -> None:
    inv_y = PDRectangle.from_cos_array(_box(50, 300, 400, 100))
    assert (_fs(inv_y.width), _fs(inv_y.height)) == ("350.0", "200.0")
    assert (_fs(inv_y.lower_left_y), _fs(inv_y.upper_right_y)) == ("100.0", "300.0")


def test_negative_box_width_height_positive() -> None:
    neg = PDRectangle.from_cos_array(_box(-100, -200, -50, -60))
    assert (_fs(neg.width), _fs(neg.height)) == ("50.0", "140.0")
    assert (_fs(neg.lower_left_x), _fs(neg.upper_right_x)) == ("-100.0", "-50.0")


def test_zero_area_box() -> None:
    z = PDRectangle.from_cos_array(_box(5, 5, 5, 5))
    assert (_fs(z.width), _fs(z.height)) == ("0.0", "0.0")


# --- contains on edges / corners (inclusive) -----------------------------


def test_contains_corners_and_edges_inclusive() -> None:
    r = PDRectangle(10, 20, 110, 220)
    # all four corners
    assert r.contains(10, 20)
    assert r.contains(110, 220)
    assert r.contains(110, 20)
    assert r.contains(10, 220)
    # midpoints of the four edges
    assert r.contains(10, 120)  # left
    assert r.contains(110, 120)  # right
    assert r.contains(60, 20)  # bottom
    assert r.contains(60, 220)  # top
    # interior
    assert r.contains(60, 120)


def test_contains_just_outside_each_edge() -> None:
    r = PDRectangle(10, 20, 110, 220)
    assert not r.contains(9.999, 120)
    assert not r.contains(110.001, 120)
    assert not r.contains(60, 19.999)
    assert not r.contains(60, 220.001)


# --- createRetranslatedRectangle of an inverted box ----------------------


def test_create_retranslated_of_inverted_box() -> None:
    inv = PDRectangle.from_cos_array(_box(400, 300, 50, 100))
    re = inv.create_retranslated_rectangle()
    assert (_fs(re.lower_left_x), _fs(re.lower_left_y)) == ("0.0", "0.0")
    assert (_fs(re.upper_right_x), _fs(re.upper_right_y)) == ("350.0", "200.0")
    assert re.get_cos_array().size() == 4


# --- transform corners by various matrices -------------------------------

_UNIT = (0.0, 0.0, 100.0, 200.0)


def test_transform_identity_returns_original_corners() -> None:
    corners = _corners(PDRectangle(*_UNIT), Matrix())
    assert corners == [("0.0", "0.0"), ("100.0", "0.0"), ("100.0", "200.0"), ("0.0", "200.0")]


def test_transform_scale() -> None:
    corners = _corners(PDRectangle(*_UNIT), Matrix.get_scale_instance(2, 3))
    assert corners == [("0.0", "0.0"), ("200.0", "0.0"), ("200.0", "600.0"), ("0.0", "600.0")]


def test_transform_translate() -> None:
    corners = _corners(PDRectangle(*_UNIT), Matrix.get_translate_instance(50, -25))
    assert corners == [
        ("50.0", "-25.0"),
        ("150.0", "-25.0"),
        ("150.0", "175.0"),
        ("50.0", "175.0"),
    ]


def test_transform_rotate_90() -> None:
    # cos(pi/2) is a tiny float32 epsilon, not exactly 0 — pinned as upstream.
    corners = _corners(PDRectangle(*_UNIT), Matrix.get_rotate_instance(math.pi / 2, 0, 0))
    assert corners == [
        ("0.0", "0.0"),
        ("6.123234E-15", "100.0"),
        ("-200.0", "100.0"),
        ("-200.0", "1.2246468E-14"),
    ]


def test_transform_rotate_45() -> None:
    corners = _corners(PDRectangle(*_UNIT), Matrix.get_rotate_instance(math.pi / 4, 0, 0))
    assert corners == [
        ("0.0", "0.0"),
        ("70.71068", "70.71068"),
        ("-70.71068", "212.13203"),
        ("-141.42136", "141.42136"),
    ]


def test_transform_rotate_180() -> None:
    corners = _corners(PDRectangle(*_UNIT), Matrix.get_rotate_instance(math.pi, 0, 0))
    assert corners == [
        ("0.0", "0.0"),
        ("-100.0", "1.2246468E-14"),
        ("-100.0", "-200.0"),
        ("-2.4492937E-14", "-200.0"),
    ]


def test_transform_shear() -> None:
    corners = _corners(PDRectangle(*_UNIT), Matrix(1, 0.25, 0.5, 1, 0, 0))
    assert corners == [
        ("0.0", "0.0"),
        ("100.0", "25.0"),
        ("200.0", "225.0"),
        ("100.0", "200.0"),
    ]


def test_transform_singular_collapses_to_line() -> None:
    # rank-1 matrix [1 2 / 2 4]: every corner lands on the line y = 2x.
    corners = _corners(PDRectangle(*_UNIT), Matrix(1, 2, 2, 4, 0, 0))
    assert corners == [
        ("0.0", "0.0"),
        ("100.0", "200.0"),
        ("500.0", "1000.0"),
        ("400.0", "800.0"),
    ]


def test_transform_multiply_order_matters() -> None:
    scale = Matrix.get_scale_instance(2, 3)
    rot = Matrix.get_rotate_instance(math.pi / 4, 0, 0)
    scale_rot = _corners(PDRectangle(*_UNIT), scale.multiply(rot))
    rot_scale = _corners(PDRectangle(*_UNIT), rot.multiply(scale))
    assert scale_rot == [
        ("0.0", "0.0"),
        ("141.42136", "141.42136"),
        ("-282.84268", "565.6854"),
        ("-424.26404", "424.26404"),
    ]
    assert rot_scale == [
        ("0.0", "0.0"),
        ("141.42136", "212.13202"),
        ("-141.42136", "636.39606"),
        ("-282.8427", "424.26404"),
    ]
    assert scale_rot != rot_scale


def test_transform_inverted_box_rotate_90() -> None:
    inv = PDRectangle.from_cos_array(_box(400, 300, 50, 100))
    corners = _corners(inv, Matrix.get_rotate_instance(math.pi / 2, 0, 0))
    assert corners == [
        ("-100.0", "50.0"),
        ("-100.0", "400.0"),
        ("-300.0", "400.0"),
        ("-300.0", "50.0"),
    ]


# --- getScalingFactor on rotated+scaled / sheared / singular -------------


def test_scaling_factor_rotated_then_scaled() -> None:
    rs = Matrix.get_scale_instance(2, 3)
    rs.rotate(math.pi / 4)
    # sqrt((2*cos45)^2 + (2*sin45)^2)  along each axis after concatenation
    assert _fs(rs.get_scaling_factor_x()) == "2.5495098"
    assert _fs(rs.get_scaling_factor_y()) == "2.5495098"


def test_scaling_factor_sheared() -> None:
    sheared = Matrix(1, 0.25, 0.5, 1, 0, 0)
    assert _fs(sheared.get_scaling_factor_x()) == "1.0307764"
    assert _fs(sheared.get_scaling_factor_y()) == "1.118034"


def test_scaling_factor_singular() -> None:
    singular = Matrix(1, 2, 2, 4, 0, 0)
    assert _fs(singular.get_scaling_factor_x()) == "2.236068"
    assert _fs(singular.get_scaling_factor_y()) == "4.472136"


def test_scaling_factor_pure_rotate_90_is_unit() -> None:
    rot90 = Matrix.get_rotate_instance(math.pi / 2, 0, 0)
    assert _fs(rot90.get_scaling_factor_x()) == "1.0"
    assert _fs(rot90.get_scaling_factor_y()) == "1.0"


def test_transform_point_rotated_scaled() -> None:
    rs = Matrix.get_scale_instance(2, 3)
    rs.rotate(math.pi / 4)
    x, y = rs.transform_point(10, 20)
    assert (_fs(x), _fs(y)) == ("-14.142136", "63.63961")


def test_chained_product_float32_rounding() -> None:
    chain = Matrix(1.1, 2.2, 3.3, 4.4, 5.5, 6.6)
    chain2 = Matrix(0.7, 0.3, 0.9, 0.1, 0.2, 0.8)
    s = chain.multiply(chain2)._single
    rendered = tuple(_fs(s[i]) for i in (0, 1, 3, 4, 6, 7))
    assert rendered == ("2.75", "0.55", "6.27", "1.4300001", "9.989999", "3.1100001")


# --- live differential ----------------------------------------------------

try:
    from tests.oracle.harness import requires_oracle, run_probe_text
except Exception:  # pragma: no cover - harness optional

    requires_oracle = pytest.mark.skip(reason="oracle harness unavailable")

    def run_probe_text(*_a: str, **_k: object) -> str:  # type: ignore[misc]
        return ""


@requires_oracle
def test_rect_matrix_fuzz_matches_live_oracle() -> None:
    """Re-derive every ``RectMatrixFuzzProbe`` line from the live PDFBox jar and
    confirm pypdfbox reproduces each value (rendered as ``Float.toString``)."""
    lines = run_probe_text("RectMatrixFuzzProbe").splitlines()
    oracle = dict(line.split("=", 1) for line in lines if "=" in line)

    def dims(label: str, rect: PDRectangle) -> None:
        assert _fs(rect.lower_left_x) == oracle[f"{label}.llx"], f"{label}.llx"
        assert _fs(rect.lower_left_y) == oracle[f"{label}.lly"], f"{label}.lly"
        assert _fs(rect.upper_right_x) == oracle[f"{label}.urx"], f"{label}.urx"
        assert _fs(rect.upper_right_y) == oracle[f"{label}.ury"], f"{label}.ury"
        assert _fs(rect.width) == oracle[f"{label}.w"], f"{label}.w"
        assert _fs(rect.height) == oracle[f"{label}.h"], f"{label}.h"

    def path(label: str, rect: PDRectangle, m: Matrix) -> None:
        corners = rect.transform(m)
        assert oracle[f"{label}.n"] == str(len(corners)), f"{label}.n"
        for i, (x, y) in enumerate(corners):
            assert _fs(x) == oracle[f"{label}.p{i}.x"], f"{label}.p{i}.x"
            assert _fs(y) == oracle[f"{label}.p{i}.y"], f"{label}.p{i}.y"

    def boolean(key: str, value: bool) -> None:
        assert ("true" if value else "false") == oracle[key], key

    def scalar(key: str, value: float) -> None:
        assert _fs(value) == oracle[key], key

    inv = PDRectangle.from_cos_array(_box(400, 300, 50, 100))
    inv_y = PDRectangle.from_cos_array(_box(50, 300, 400, 100))
    neg = PDRectangle.from_cos_array(_box(-100, -200, -50, -60))
    zero = PDRectangle.from_cos_array(_box(5, 5, 5, 5))
    dims("inv", inv)
    dims("invY", inv_y)
    dims("neg", neg)
    dims("zeroarea", zero)

    r = PDRectangle(10, 20, 110, 220)
    boolean("c.ll", r.contains(10, 20))
    boolean("c.ur", r.contains(110, 220))
    boolean("c.lr", r.contains(110, 20))
    boolean("c.ul", r.contains(10, 220))
    boolean("c.left", r.contains(10, 120))
    boolean("c.right", r.contains(110, 120))
    boolean("c.bottom", r.contains(60, 20))
    boolean("c.top", r.contains(60, 220))
    boolean("c.in", r.contains(60, 120))
    boolean("c.outL", r.contains(9.999, 120))
    boolean("c.outR", r.contains(110.001, 120))
    boolean("c.outB", r.contains(60, 19.999))
    boolean("c.outT", r.contains(60, 220.001))

    re = inv.create_retranslated_rectangle()
    dims("re", re)
    assert oracle["re.ca"] == str(re.get_cos_array().size())

    unit = PDRectangle(*_UNIT)
    path("t_id", unit, Matrix())
    path("t_scale", unit, Matrix.get_scale_instance(2, 3))
    path("t_translate", unit, Matrix.get_translate_instance(50, -25))
    path("t_rot90", unit, Matrix.get_rotate_instance(math.pi / 2, 0, 0))
    path("t_rot45", unit, Matrix.get_rotate_instance(math.pi / 4, 0, 0))
    path("t_rot180", unit, Matrix.get_rotate_instance(math.pi, 0, 0))
    path("t_shear", unit, Matrix(1, 0.25, 0.5, 1, 0, 0))
    path("t_singular", unit, Matrix(1, 2, 2, 4, 0, 0))
    scale = Matrix.get_scale_instance(2, 3)
    rot = Matrix.get_rotate_instance(math.pi / 4, 0, 0)
    path("t_scale_rot", unit, scale.multiply(rot))
    path("t_rot_scale", unit, rot.multiply(scale))
    path("t_inv_rot90", inv, Matrix.get_rotate_instance(math.pi / 2, 0, 0))

    rs = Matrix.get_scale_instance(2, 3)
    rs.rotate(math.pi / 4)
    scalar("rs.sfx", rs.get_scaling_factor_x())
    scalar("rs.sfy", rs.get_scaling_factor_y())
    sheared = Matrix(1, 0.25, 0.5, 1, 0, 0)
    scalar("sheared.sfx", sheared.get_scaling_factor_x())
    scalar("sheared.sfy", sheared.get_scaling_factor_y())
    singular = Matrix(1, 2, 2, 4, 0, 0)
    scalar("singular.sfx", singular.get_scaling_factor_x())
    scalar("singular.sfy", singular.get_scaling_factor_y())
    rot90 = Matrix.get_rotate_instance(math.pi / 2, 0, 0)
    scalar("rot90.sfx", rot90.get_scaling_factor_x())
    scalar("rot90.sfy", rot90.get_scaling_factor_y())

    x, y = rs.transform_point(10, 20)
    scalar("rs.tp.x", x)
    scalar("rs.tp.y", y)

    chain = Matrix(1.1, 2.2, 3.3, 4.4, 5.5, 6.6)
    chain2 = Matrix(0.7, 0.3, 0.9, 0.1, 0.2, 0.8)
    prod = chain.multiply(chain2)._single
    scalar("prod.sx", prod[0])
    scalar("prod.hy", prod[1])
    scalar("prod.hx", prod[3])
    scalar("prod.sy", prod[4])
    scalar("prod.tx", prod[6])
    scalar("prod.ty", prod[7])
