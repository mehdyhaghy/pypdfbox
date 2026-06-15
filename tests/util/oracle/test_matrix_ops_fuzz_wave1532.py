"""Live PDFBox differential fuzz of ``Matrix`` OPERATIONS + ``createMatrix``
coercion (wave 1532).

``MatrixFloat32Probe`` (wave 1485) pins the float32 *representation* of a
handful of rotate/multiply/scaling-factor results. This wave's angle is the
*operations algebra* and the ``createMatrix(COSBase)`` coercion contract:

* **createMatrix coercion** — the live oracle confirms upstream
  ``Matrix.createMatrix`` NEVER returns ``null`` in 3.0.7: a ``null`` base, a
  non-``COSArray`` base (name / string / integer), a too-short array
  (length 0 / 3 / 5), an array whose first six elements are not all
  ``COSNumber`` (a name or a ``null`` slot at index 2) all fall back to the
  **identity** matrix. A length-9 array is accepted and only its first six
  numbers are used (extra trailing entries ignored). pypdfbox's
  :meth:`Matrix.create_matrix` already matches every one of these.
* **multiply / concatenate** — associativity (``a·(b·c) == (a·b)·c``),
  ``a·self``, identity on either side, and in-place ``concatenate`` (which is
  ``other·this``).
* **rotate edge angles** — 0 (note the ``-0.0`` shear from ``-sin(0)``), π, 2π,
  π/2, negative; plus in-place ``rotate``.
* **scale / translate** — scale by zero and by negatives, translate (float and
  ``Vector`` overload), the static ``get*Instance`` factories.
* **getScalingFactor** on a 45° rotation and on the all-zero matrix;
  ``getTranslateX/Y``, ``getScaleX/Y``, ``getShearX/Y``.
* **transformPoint** at the origin, at extreme (``±1e30``) and negative inputs.
* **clone** independence; ``createMatrix → toCOSArray`` round trip.

The cells/scalars are rendered with :func:`float_to_string` — the raw Java
``Float.toString`` port — because that is exactly what the probe emits
(``System.out.println(float)``). Several results land in ``Float`` E-notation
(``1.2246469E-16``, ``-1.0000002E30``) where ``format_float32`` (the
PDF-serialization renderer) would diverge in *notation* while agreeing on the
*value*; the matrix is float32-exact either way. Every pinned assertion below
passes WITHOUT the oracle; the ``@requires_oracle`` differential at the bottom
re-derives them live against the PDFBox 3.0.7 jar.
"""

from __future__ import annotations

import math

import pytest

from pypdfbox.cos.cos_array import COSArray
from pypdfbox.cos.cos_float import COSFloat, float_to_string
from pypdfbox.cos.cos_integer import COSInteger
from pypdfbox.cos.cos_name import COSName
from pypdfbox.cos.cos_string import COSString
from pypdfbox.util.matrix import Matrix
from pypdfbox.util.vector import Vector


def _cells(m: Matrix) -> tuple[str, str, str, str, str, str]:
    """Six geometric cells (toCOSArray order) as Java ``Float.toString``."""
    s = m._single
    return tuple(float_to_string(s[i]) for i in (0, 1, 3, 4, 6, 7))  # type: ignore[return-value]


def _nums(*vals: float) -> COSArray:
    a = COSArray()
    for d in vals:
        a.add(COSFloat(float(d)))
    return a


_IDENTITY = ("1.0", "0.0", "0.0", "1.0", "0.0", "0.0")


# --- createMatrix coercion: identity fallback, never null ----------------


def test_create_matrix_null_base_is_identity() -> None:
    assert _cells(Matrix.create_matrix(None)) == _IDENTITY


def test_create_matrix_non_array_bases_are_identity() -> None:
    assert _cells(Matrix.create_matrix(COSName.get_pdf_name("Foo"))) == _IDENTITY
    assert _cells(Matrix.create_matrix(COSString("abc"))) == _IDENTITY
    assert _cells(Matrix.create_matrix(COSInteger.get(5))) == _IDENTITY


def test_create_matrix_too_short_arrays_are_identity() -> None:
    assert _cells(Matrix.create_matrix(COSArray())) == _IDENTITY
    assert _cells(Matrix.create_matrix(_nums(1, 2, 3))) == _IDENTITY
    assert _cells(Matrix.create_matrix(_nums(1, 2, 3, 4, 5))) == _IDENTITY


def test_create_matrix_valid_six_element_array() -> None:
    assert _cells(Matrix.create_matrix(_nums(2, 0, 0, 2, 10, 20))) == (
        "2.0",
        "0.0",
        "0.0",
        "2.0",
        "10.0",
        "20.0",
    )


def test_create_matrix_length_nine_uses_first_six() -> None:
    # Upstream accepts size() >= 6 and reads indices 0..5; trailing ignored.
    assert _cells(Matrix.create_matrix(_nums(1, 2, 3, 4, 5, 6, 7, 8, 9))) == (
        "1.0",
        "2.0",
        "3.0",
        "4.0",
        "5.0",
        "6.0",
    )


def test_create_matrix_non_number_entry_is_identity() -> None:
    mixed = COSArray()
    mixed.add(COSFloat(1.0))
    mixed.add(COSFloat(0.0))
    mixed.add(COSName.get_pdf_name("X"))
    mixed.add(COSFloat(1.0))
    mixed.add(COSFloat(0.0))
    mixed.add(COSFloat(0.0))
    assert _cells(Matrix.create_matrix(mixed)) == _IDENTITY


def test_create_matrix_null_entry_is_identity() -> None:
    wn = COSArray()
    wn.add(COSFloat(1.0))
    wn.add(COSFloat(0.0))
    wn.add(None)
    wn.add(COSFloat(1.0))
    wn.add(COSFloat(0.0))
    wn.add(COSFloat(0.0))
    assert _cells(Matrix.create_matrix(wn)) == _IDENTITY


def test_create_matrix_integers_are_numbers() -> None:
    ints = COSArray()
    for i in range(6):
        ints.add(COSInteger.get(i + 1))
    assert _cells(Matrix.create_matrix(ints)) == (
        "1.0",
        "2.0",
        "3.0",
        "4.0",
        "5.0",
        "6.0",
    )


# --- multiply / concatenate algebra --------------------------------------


def test_multiply_values() -> None:
    a = Matrix(2, 1, 3, 4, 5, 6)
    b = Matrix(0.5, 0, 0, 2, 1, 1)
    assert _cells(a.multiply(b)) == ("1.0", "2.0", "1.5", "8.0", "3.5", "13.0")


def test_multiply_associative() -> None:
    a = Matrix(2, 1, 3, 4, 5, 6)
    b = Matrix(0.5, 0, 0, 2, 1, 1)
    c = Matrix(1, 1, 0, 1, 0, 0)
    assert _cells(a.multiply(b.multiply(c))) == _cells(a.multiply(b).multiply(c))
    assert _cells(a.multiply(b).multiply(c)) == ("1.0", "3.0", "1.5", "9.5", "3.5", "16.5")


def test_multiply_self() -> None:
    a = Matrix(2, 1, 3, 4, 5, 6)
    assert _cells(a.multiply(a)) == ("7.0", "6.0", "18.0", "19.0", "33.0", "35.0")


def test_multiply_identity_either_side_is_noop() -> None:
    a = Matrix(2, 1, 3, 4, 5, 6)
    assert _cells(a.multiply(Matrix())) == _cells(a)
    assert _cells(Matrix().multiply(a)) == _cells(a)


def test_concatenate_in_place_is_other_times_this() -> None:
    con = Matrix(2, 1, 3, 4, 5, 6)
    con.concatenate(Matrix(0.5, 0, 0, 2, 1, 1))
    assert _cells(con) == ("1.0", "0.5", "6.0", "8.0", "10.0", "11.0")


# --- rotate edge angles --------------------------------------------------


def test_rotate_zero_has_negative_zero_shear() -> None:
    # -sin(0) == -0.0 in IEEE; upstream stores and emits "-0.0".
    assert _cells(Matrix.get_rotate_instance(0.0, 0, 0)) == (
        "1.0",
        "0.0",
        "-0.0",
        "1.0",
        "0.0",
        "0.0",
    )


def test_rotate_pi() -> None:
    assert _cells(Matrix.get_rotate_instance(math.pi, 0, 0)) == (
        "-1.0",
        "1.2246469E-16",
        "-1.2246469E-16",
        "-1.0",
        "0.0",
        "0.0",
    )


def test_rotate_two_pi() -> None:
    assert _cells(Matrix.get_rotate_instance(2 * math.pi, 0, 0)) == (
        "1.0",
        "-2.4492937E-16",
        "2.4492937E-16",
        "1.0",
        "0.0",
        "0.0",
    )


def test_rotate_half_pi() -> None:
    assert _cells(Matrix.get_rotate_instance(math.pi / 2, 0, 0)) == (
        "6.123234E-17",
        "1.0",
        "-1.0",
        "6.123234E-17",
        "0.0",
        "0.0",
    )


def test_rotate_negative() -> None:
    assert _cells(Matrix.get_rotate_instance(-1.0, 0, 0)) == (
        "0.5403023",
        "-0.84147096",
        "0.84147096",
        "0.5403023",
        "0.0",
        "0.0",
    )


def test_rotate_in_place() -> None:
    rin = Matrix(2, 0, 0, 2, 0, 0)
    rin.rotate(math.pi / 2)
    assert _cells(rin) == (
        "1.2246469E-16",
        "2.0",
        "-2.0",
        "1.2246469E-16",
        "0.0",
        "0.0",
    )


# --- scale / translate ---------------------------------------------------


def test_scale_by_zero() -> None:
    sc = Matrix(2, 1, 3, 4, 5, 6)
    sc.scale(0, 0)
    assert _cells(sc) == ("0.0", "0.0", "0.0", "0.0", "5.0", "6.0")


def test_scale_by_negative() -> None:
    sc = Matrix(2, 1, 3, 4, 5, 6)
    sc.scale(-1, -2)
    assert _cells(sc) == ("-2.0", "-1.0", "-6.0", "-8.0", "5.0", "6.0")


def test_scale_instance_zero_and_negative() -> None:
    assert _cells(Matrix.get_scale_instance(0, 0)) == ("0.0", "0.0", "0.0", "0.0", "0.0", "0.0")
    assert _cells(Matrix.get_scale_instance(-1.5, -2.5)) == (
        "-1.5",
        "0.0",
        "0.0",
        "-2.5",
        "0.0",
        "0.0",
    )


def test_translate_float_and_vector() -> None:
    tr = Matrix(2, 1, 3, 4, 5, 6)
    tr.translate(10, 20)
    expected = ("2.0", "1.0", "3.0", "4.0", "85.0", "96.0")
    assert _cells(tr) == expected
    trv = Matrix(2, 1, 3, 4, 5, 6)
    trv.translate(Vector(10, 20))
    assert _cells(trv) == expected


def test_translate_instance() -> None:
    assert _cells(Matrix.get_translate_instance(-3.5, 4.25)) == (
        "1.0",
        "0.0",
        "0.0",
        "1.0",
        "-3.5",
        "4.25",
    )


# --- scaling factor / accessors ------------------------------------------


def test_scaling_factor_on_rotation_is_unit() -> None:
    rot45 = Matrix.get_rotate_instance(math.pi / 4, 0, 0)
    assert float_to_string(rot45.get_scaling_factor_x()) == "1.0"
    assert float_to_string(rot45.get_scaling_factor_y()) == "1.0"


def test_scaling_factor_on_zero_matrix() -> None:
    zero = Matrix(0, 0, 0, 0, 0, 0)
    assert float_to_string(zero.get_scaling_factor_x()) == "0.0"
    assert float_to_string(zero.get_scaling_factor_y()) == "0.0"


def test_translate_and_scale_accessors() -> None:
    g = Matrix(2, 1, 3, 4, 5, 6)
    assert float_to_string(g.get_translate_x()) == "5.0"
    assert float_to_string(g.get_translate_y()) == "6.0"
    assert float_to_string(g.get_scale_x()) == "2.0"
    assert float_to_string(g.get_scale_y()) == "4.0"
    assert float_to_string(g.get_shear_x()) == "3.0"
    assert float_to_string(g.get_shear_y()) == "1.0"


# --- transformPoint extremes ---------------------------------------------


def test_transform_point_origin() -> None:
    x, y = Matrix(2, 1, 3, 4, 5, 6).transform_point(0, 0)
    assert (float_to_string(x), float_to_string(y)) == ("5.0", "6.0")


def test_transform_point_extreme() -> None:
    x, y = Matrix(2, 1, 3, 4, 5, 6).transform_point(1e30, -1e30)
    assert (float_to_string(x), float_to_string(y)) == ("-1.0000002E30", "-3.0000002E30")


def test_transform_point_negative() -> None:
    x, y = Matrix(2, 1, 3, 4, 5, 6).transform_point(-12345.678, 9876.543)
    assert (float_to_string(x), float_to_string(y)) == ("4943.2734", "27166.494")


# --- clone independence + round trip -------------------------------------


def test_clone_is_independent() -> None:
    orig = Matrix(2, 1, 3, 4, 5, 6)
    cl = orig.clone()
    cl.translate(100, 100)
    assert _cells(orig) == ("2.0", "1.0", "3.0", "4.0", "5.0", "6.0")
    assert _cells(cl) == ("2.0", "1.0", "3.0", "4.0", "505.0", "506.0")


def test_create_matrix_to_cos_array_round_trip() -> None:
    rt = Matrix.create_matrix(_nums(1.5, 2.5, 3.5, 4.5, 5.5, 6.5))
    arr = rt.to_cos_array()
    rendered = [float_to_string(arr.get_object(i).float_value()) for i in range(6)]
    assert rendered == ["1.5", "2.5", "3.5", "4.5", "5.5", "6.5"]


# --- live differential ----------------------------------------------------

try:
    from tests.oracle.harness import requires_oracle, run_probe_text
except Exception:  # pragma: no cover - harness optional
    requires_oracle = pytest.mark.skip(reason="oracle harness unavailable")

    def run_probe_text(*_a: str, **_k: object) -> str:  # type: ignore[misc]
        return ""


@requires_oracle
def test_matrix_ops_fuzz_matches_live_oracle() -> None:
    """Re-derive every probe line from the live PDFBox ``MatrixOpsFuzzProbe``
    and confirm pypdfbox reproduces each value (rendered as ``Float.toString``)
    byte-for-byte."""
    lines = run_probe_text("MatrixOpsFuzzProbe").splitlines()
    oracle = dict(line.split("=", 1) for line in lines if "=" in line)

    def m_cells(label: str, mtx: Matrix) -> None:
        s = mtx._single
        for nm, idx in (("sx", 0), ("hy", 1), ("hx", 3), ("sy", 4), ("tx", 6), ("ty", 7)):
            assert float_to_string(s[idx]) == oracle[f"{label}.{nm}"], f"{label}.{nm}"

    def scalar(key: str, value: float) -> None:
        assert float_to_string(value) == oracle[key], key

    # createMatrix coercion
    m_cells("cm_null", Matrix.create_matrix(None))
    m_cells("cm_name", Matrix.create_matrix(COSName.get_pdf_name("Foo")))
    m_cells("cm_string", Matrix.create_matrix(COSString("abc")))
    m_cells("cm_int", Matrix.create_matrix(COSInteger.get(5)))
    m_cells("cm_len0", Matrix.create_matrix(COSArray()))
    m_cells("cm_len3", Matrix.create_matrix(_nums(1, 2, 3)))
    m_cells("cm_len5", Matrix.create_matrix(_nums(1, 2, 3, 4, 5)))
    m_cells("cm_len6", Matrix.create_matrix(_nums(2, 0, 0, 2, 10, 20)))
    m_cells("cm_len9", Matrix.create_matrix(_nums(1, 2, 3, 4, 5, 6, 7, 8, 9)))
    mixed = COSArray()
    mixed.add(COSFloat(1.0))
    mixed.add(COSFloat(0.0))
    mixed.add(COSName.get_pdf_name("X"))
    mixed.add(COSFloat(1.0))
    mixed.add(COSFloat(0.0))
    mixed.add(COSFloat(0.0))
    m_cells("cm_mixed", Matrix.create_matrix(mixed))
    ints = COSArray()
    for i in range(6):
        ints.add(COSInteger.get(i + 1))
    m_cells("cm_ints", Matrix.create_matrix(ints))
    wn = COSArray()
    wn.add(COSFloat(1.0))
    wn.add(COSFloat(0.0))
    wn.add(None)
    wn.add(COSFloat(1.0))
    wn.add(COSFloat(0.0))
    wn.add(COSFloat(0.0))
    m_cells("cm_nullentry", Matrix.create_matrix(wn))

    a = Matrix(2, 1, 3, 4, 5, 6)
    b = Matrix(0.5, 0, 0, 2, 1, 1)
    c = Matrix(1, 1, 0, 1, 0, 0)
    m_cells("ab", a.multiply(b))
    m_cells("a_bc", a.multiply(b.multiply(c)))
    m_cells("ab_c", a.multiply(b).multiply(c))
    m_cells("aa", a.multiply(a))
    m_cells("a_id", a.multiply(Matrix()))
    m_cells("id_a", Matrix().multiply(a))
    con = Matrix(2, 1, 3, 4, 5, 6)
    con.concatenate(b)
    m_cells("concat", con)

    m_cells("rot_0", Matrix.get_rotate_instance(0.0, 0, 0))
    m_cells("rot_pi", Matrix.get_rotate_instance(math.pi, 0, 0))
    m_cells("rot_2pi", Matrix.get_rotate_instance(2 * math.pi, 0, 0))
    m_cells("rot_halfpi", Matrix.get_rotate_instance(math.pi / 2, 0, 0))
    m_cells("rot_neg", Matrix.get_rotate_instance(-1.0, 0, 0))
    rin = Matrix(2, 0, 0, 2, 0, 0)
    rin.rotate(math.pi / 2)
    m_cells("rotate_inplace", rin)

    sc = Matrix(2, 1, 3, 4, 5, 6)
    sc.scale(0, 0)
    m_cells("scale_zero", sc)
    sc2 = Matrix(2, 1, 3, 4, 5, 6)
    sc2.scale(-1, -2)
    m_cells("scale_neg", sc2)
    m_cells("scale_inst_zero", Matrix.get_scale_instance(0, 0))
    m_cells("scale_inst_neg", Matrix.get_scale_instance(-1.5, -2.5))

    tr = Matrix(2, 1, 3, 4, 5, 6)
    tr.translate(10, 20)
    m_cells("translate", tr)
    trv = Matrix(2, 1, 3, 4, 5, 6)
    trv.translate(Vector(10, 20))
    m_cells("translate_vec", trv)
    m_cells("translate_inst", Matrix.get_translate_instance(-3.5, 4.25))

    orig = Matrix(2, 1, 3, 4, 5, 6)
    cl = orig.clone()
    cl.translate(100, 100)
    m_cells("clone_orig", orig)
    m_cells("clone_mod", cl)

    rot45 = Matrix.get_rotate_instance(math.pi / 4, 0, 0)
    scalar("rot45.sfx", rot45.get_scaling_factor_x())
    scalar("rot45.sfy", rot45.get_scaling_factor_y())
    zero = Matrix(0, 0, 0, 0, 0, 0)
    scalar("zero.sfx", zero.get_scaling_factor_x())
    scalar("zero.sfy", zero.get_scaling_factor_y())

    g = Matrix(2, 1, 3, 4, 5, 6)
    scalar("g.tx", g.get_translate_x())
    scalar("g.ty", g.get_translate_y())
    scalar("g.scx", g.get_scale_x())
    scalar("g.scy", g.get_scale_y())
    scalar("g.shx", g.get_shear_x())
    scalar("g.shy", g.get_shear_y())

    tm = Matrix(2, 1, 3, 4, 5, 6)
    x, y = tm.transform_point(0, 0)
    scalar("tp0.x", x)
    scalar("tp0.y", y)
    x, y = tm.transform_point(1e30, -1e30)
    scalar("tpbig.x", x)
    scalar("tpbig.y", y)
    x, y = tm.transform_point(-12345.678, 9876.543)
    scalar("tpneg.x", x)
    scalar("tpneg.y", y)

    rt = Matrix.create_matrix(_nums(1.5, 2.5, 3.5, 4.5, 5.5, 6.5))
    arr = rt.to_cos_array()
    for i in range(6):
        scalar(f"rt[{i}]", arr.get_object(i).float_value())
