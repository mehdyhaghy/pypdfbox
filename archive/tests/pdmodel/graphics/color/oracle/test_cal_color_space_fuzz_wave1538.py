"""Live PDFBox differential fuzz parity for the CIE calibrated colour-space
ACCESSOR surface of ``PDCalRGB`` / ``PDCalGray`` (wave 1538, agent B).

Sibling of ``oracle/probes/CalColorSpaceFuzzProbe.java``. Where the wave-1512
``ColorSpaceFuzzProbe`` drives ``PDColorSpace.create(COSBase)`` construction
leniency at a high level and ``CalColorProbe`` pins the well-formed ``toRGB``
CIE math, this probe drills into the dictionary-accessor surface for the array
forms ``[/CalRGB <<...>>]`` / ``[/CalGray <<...>>]`` with malformed
``/WhitePoint``, ``/BlackPoint``, ``/Gamma`` and (CalRGB) ``/Matrix``: missing,
wrong-length, non-numeric, zero/negative, scalar-instead-of-array, empty.

Each case keeps a dictionary present in slot 1 so BOTH sides construct
successfully (upstream's base ctor NPEs when slot 1 is not a dictionary — that
permissive-create divergence is already pinned by the wave-1512 corpus, so it
is out of scope here).

The Java probe prints one structural digest per case::

    CASE <name> nc=<n> gamma=<r,g,b | g | ERR> matrix=<len:v,.. | ERR | NA> \\
        wp=<x,y,z|ERR> bp=<x,y,z|ERR> init=<a,..|ERR> rgb=<r;g;b|ERR|CMM>

``gamma`` for CalRGB projects ``PDGamma.getR/G/B`` (index 0/1/2 of the array,
cast to a number — throws on short/non-numeric); for CalGray it is the single
``getGamma()`` float. ``rgb`` is emitted as a real digest only for the
NON-unit-white-point cases (the documented PDFBOX-2553 pass-through branch
returns the input components verbatim, byte-identical on both sides modulo the
<=1/255 float-vs-double x.5 rounding artifact). Unit-white-point cases route the
final XYZ->sRGB step through the JVM AWT CMM (a D50 PCS) which pypdfbox replaces
with an explicit IEC 61966-2-1 D65 matrix — that divergence is already pinned by
``test_cal_color_oracle.py``, so this probe emits ``rgb=CMM`` (a marker, not
compared).

This module rebuilds the IDENTICAL corpus, case-for-case in order, emits the
identical digest grammar via pypdfbox ``PDCalRGB`` / ``PDCalGray``, and asserts
line-for-line parity against the live Java oracle. Documented divergences are
listed in ``_EXPECTED_DIVERGENCES`` and pinned BOTH sides (assert pypdfbox emits
the pin AND that Java differs, so a future convergence fails loudly).

Pinned divergence families (pre-existing design decisions, no real bug):

* **ctor** — permissive factory contract. Upstream's
  ``PDCIEDictionaryBasedColorSpace`` ctor eagerly reads ``/WhitePoint`` via
  ``fillWhitepointCache(getWhitepoint())`` (which casts each element to a
  number), so a short / non-numeric ``/WhitePoint`` throws *during
  construction*. pypdfbox is permissive: it does not touch the dict at
  construction, so it constructs and surfaces the defect lazily on read. Same
  family as ``test_colorspace_fuzz_wave1512.py``.
* **gamma numeric leniency** — upstream ``PDGamma.getR/G/B`` casts
  ``COSArray.get(i)`` to ``COSNumber`` (throws on a non-numeric element) and an
  empty ``/Gamma`` array yields an empty (length-0) ``PDGamma`` whose ``getR``
  index-0 read throws. pypdfbox's ``get_gamma`` goes through ``to_float_array``
  (coerces non-numerics to ``0.0``) and treats an *empty* array as "absent"
  (falls back to the ``[1, 1, 1]`` default). So a non-numeric ``/Gamma`` reads
  ``0.000,0.000,0.000`` (vs Java ERR) and an empty ``/Gamma`` reads the default
  ``1.000,1.000,1.000`` (vs Java ERR). Same lenient-coercion family as the
  ``/Range`` pin in ``test_icc_based_fuzz_wave1528.py``.
* **tristimulus length leniency** — upstream ``getWhitepoint`` /
  ``getBlackPoint`` wrap the COSArray verbatim, so a short array throws on the
  ``getX/Y/Z`` index read. pypdfbox's CalGray ``_read_tristimulus`` (and CalRGB
  ``_read_float_array`` for ``/BlackPoint``) falls back to the default tuple
  when the array is short. CalRGB's ``/WhitePoint`` / ``/BlackPoint`` happen to
  pass a short array through (so they throw on the index read like Java); only
  CalGray surfaces the default — pinned for ``gray_bp_short``.

NO real production bug was found on this surface — the accessor defaults
(missing /Gamma -> [1,1,1] / 1.0; missing /Matrix -> identity; missing
/BlackPoint -> [0,0,0]; missing /WhitePoint -> [1,1,1]), the short-array
truncation, the matrix verbatim-passthrough, the initial colour, and the
non-unit-white-point pass-through ``toRGB`` are all byte-parity with PDFBox.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSString,
)
from pypdfbox.pdmodel.graphics.color.pd_cal_gray import PDCalGray
from pypdfbox.pdmodel.graphics.color.pd_cal_rgb import PDCalRGB
from tests.oracle.harness import requires_oracle, run_probe_text

# ---------- COS builders (mirror CalColorSpaceFuzzProbe helpers) ----------


def _n(s: str) -> COSName:
    return COSName.get_pdf_name(s)


def _arr(*items: COSBase) -> COSArray:
    a = COSArray()
    for b in items:
        a.add(b)
    return a


def _floats(*vals: float) -> COSArray:
    a = COSArray()
    for v in vals:
        a.add(COSFloat(float(v)))
    return a


def _d(
    wp: COSArray | None,
    bp: COSArray | None,
    gamma: COSBase | None,
    matrix: COSBase | None,
) -> COSDictionary:
    dd = COSDictionary()
    if wp is not None:
        dd.set_item("WhitePoint", wp)
    if bp is not None:
        dd.set_item("BlackPoint", bp)
    if gamma is not None:
        dd.set_item("Gamma", gamma)
    if matrix is not None:
        dd.set_item("Matrix", matrix)
    return dd


def _cal(head: str, d: COSDictionary) -> COSArray:
    return _arr(_n(head), d)


# ---------- digest formatting (mirror the Java probe exactly) ----------

_UNIT = (1.0, 1.0, 1.0)
_D65 = (0.9505, 1.0, 1.089)


def _f3(v: float) -> str:
    return f"{v:.3f}"


def _clamp255(value: float) -> int:
    r = round(value * 255.0)
    if r < 0:
        return 0
    if r > 255:
        return 255
    return int(r)


def _gamma_triple(cs: PDCalRGB) -> str:
    """Mirror PDGamma.getR/G/B: index 0/1/2, number-cast (throws otherwise).

    pypdfbox ``get_gamma`` returns a coerced float list; we index it the way
    upstream indexes the COSArray. A short list raises IndexError (matching
    Java's index OOB); a non-numeric element was coerced to 0.0 upstream-of-here
    (the pinned numeric-leniency divergence).
    """
    g = cs.get_gamma()
    return f"{_f3(g[0])},{_f3(g[1])},{_f3(g[2])}"


def _wpbp(values: list[float]) -> str:
    """Mirror PDTristimulus.getX/Y/Z: index 0/1/2 (throws if short)."""
    return f"{_f3(values[0])},{_f3(values[1])},{_f3(values[2])}"


def _emit_rgb(name: str, d: COSDictionary, unit_wp: bool, sample: list[float]) -> str:
    sb = f"CASE {name} "
    try:
        cs = PDCalRGB(_cal("CalRGB", d))
    except Exception:  # noqa: BLE001 — probe mirrors Java's catch(Throwable)
        return sb + "ctor=ERR"
    sb += f"nc={cs.get_number_of_components()}"
    try:
        sb += " gamma=" + _gamma_triple(cs)
    except Exception:  # noqa: BLE001
        sb += " gamma=ERR"
    try:
        m = cs.get_matrix()
        sb += f" matrix={len(m)}:" + ",".join(_f3(x) for x in m)
    except Exception:  # noqa: BLE001
        sb += " matrix=ERR"
    sb += _wp_bp_init(cs, unit_wp, sample)
    return sb


def _emit_gray(name: str, d: COSDictionary, unit_wp: bool, sample: list[float]) -> str:
    sb = f"CASE {name} "
    try:
        cs = PDCalGray(_cal("CalGray", d))
    except Exception:  # noqa: BLE001
        return sb + "ctor=ERR"
    sb += f"nc={cs.get_number_of_components()}"
    try:
        sb += " gamma=" + _f3(cs.get_gamma())
    except Exception:  # noqa: BLE001
        sb += " gamma=ERR"
    sb += " matrix=NA"
    sb += _wp_bp_init(cs, unit_wp, sample)
    return sb


def _wp_bp_init(cs: object, unit_wp: bool, sample: list[float]) -> str:
    sb = ""
    try:
        sb += " wp=" + _wpbp(cs.get_white_point())  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        sb += " wp=ERR"
    try:
        sb += " bp=" + _wpbp(cs.get_black_point())  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        sb += " bp=ERR"
    try:
        init = cs.get_initial_color().get_components()  # type: ignore[attr-defined]
        sb += " init=" + ",".join(_f3(c) for c in init)
    except Exception:  # noqa: BLE001
        sb += " init=ERR"
    if unit_wp:
        sb += " rgb=CMM"
    else:
        try:
            rgb = cs.to_rgb(sample)  # type: ignore[attr-defined]
            sb += (
                f" rgb={_clamp255(rgb[0])};"
                f"{_clamp255(rgb[1])};{_clamp255(rgb[2])}"
            )
        except Exception:  # noqa: BLE001
            sb += " rgb=ERR"
    return sb


# ---------- the corpus (identical to CalColorSpaceFuzzProbe.main, in order) ----

_S3 = [0.4, 0.6, 0.8]
_S1 = [0.4]

_SRGB_MATRIX = (
    0.4124, 0.2126, 0.0193,
    0.3576, 0.7152, 0.1192,
    0.1805, 0.0722, 0.9505,
)


def _build_cases() -> list[tuple[str, str, COSDictionary, bool, list[float]]]:
    """Return (kind, name, dict, unit_wp, sample) tuples; kind in {rgb, gray}."""
    c: list[tuple[str, str, COSDictionary, bool, list[float]]] = []

    def rgb(name: str, d: COSDictionary, unit: bool) -> None:
        c.append(("rgb", name, d, unit, _S3))

    def gray(name: str, d: COSDictionary, unit: bool) -> None:
        c.append(("gray", name, d, unit, _S1))

    # ===================== CalRGB =====================
    rgb("rgb_empty_dict", _d(None, None, None, None), True)
    rgb(
        "rgb_unit_full",
        _d(_floats(*_UNIT), _floats(0, 0, 0),
           _floats(1.8, 2.2, 2.4), _floats(*_SRGB_MATRIX)),
        True,
    )
    rgb(
        "rgb_d65_full",
        _d(_floats(*_D65), _floats(0, 0, 0),
           _floats(1.8, 2.2, 2.4), _floats(*_SRGB_MATRIX)),
        False,
    )
    rgb("rgb_d65_no_gamma", _d(_floats(*_D65), None, None, None), False)
    rgb("rgb_d65_no_matrix", _d(_floats(*_D65), None, _floats(1, 1, 1), None), False)
    rgb("rgb_d65_gamma_short", _d(_floats(*_D65), None, _floats(2.0, 2.0), None), False)
    rgb(
        "rgb_d65_gamma_long",
        _d(_floats(*_D65), None, _floats(1.5, 1.6, 1.7, 1.8), None),
        False,
    )
    rgb(
        "rgb_d65_gamma_nonnum",
        _d(_floats(*_D65), None, _arr(_n("a"), _n("b"), _n("c")), None),
        False,
    )
    rgb(
        "rgb_d65_gamma_scalar",
        _d(_floats(*_D65), None, COSFloat(2.2), None),
        False,
    )
    rgb(
        "rgb_d65_matrix_short",
        _d(_floats(*_D65), None, _floats(1, 1, 1), _floats(1, 0, 0, 1)),
        False,
    )
    _matrix_scalar = _d(_floats(*_D65), None, _floats(1, 1, 1), None)
    _matrix_scalar.set_item("Matrix", COSFloat(5.0))
    rgb("rgb_d65_matrix_scalar", _matrix_scalar, False)
    rgb("rgb_wp_short", _d(_floats(1, 1), None, None, None), False)
    rgb("rgb_wp_nonnum", _d(_arr(_n("x"), _n("y"), _n("z")), None, None, None), False)
    rgb("rgb_wp_negative", _d(_floats(-1, -1, -1), None, None, None), False)
    rgb("rgb_wp_zeros", _d(_floats(0, 0, 0), None, None, None), False)
    rgb("rgb_bp_short", _d(_floats(*_D65), _floats(0, 0), None, None), False)
    rgb(
        "rgb_bp_long",
        _d(_floats(*_D65), _floats(0.1, 0.2, 0.3, 0.4, 0.5), None, None),
        False,
    )
    rgb("rgb_wp_long_unit", _d(_floats(1, 1, 1, 5), None, None, None), True)
    rgb("rgb_gamma_empty", _d(_floats(*_D65), None, COSArray(), None), False)
    rgb(
        "rgb_matrix_empty",
        _d(_floats(*_D65), None, _floats(1, 1, 1), COSArray()),
        False,
    )

    # ===================== CalGray =====================
    gray("gray_empty_dict", _d(None, None, None, None), True)
    gray(
        "gray_unit_g22",
        _d(_floats(*_UNIT), _floats(0, 0, 0), COSFloat(2.2), None),
        True,
    )
    gray("gray_d65_g22", _d(_floats(*_D65), _floats(0, 0, 0), COSFloat(2.2), None), False)
    gray("gray_d65_no_gamma", _d(_floats(*_D65), None, None, None), False)
    gray(
        "gray_d65_gamma_array",
        _d(_floats(*_D65), None, _floats(2.2, 2.2, 2.2), None),
        False,
    )
    gray("gray_d65_gamma_int", _d(_floats(*_D65), None, COSInteger.get(3), None), False)
    gray("gray_d65_gamma_name", _d(_floats(*_D65), None, _n("foo"), None), False)
    gray(
        "gray_d65_gamma_string",
        _d(_floats(*_D65), None, COSString("2.2"), None),
        False,
    )
    gray("gray_wp_short", _d(_floats(1, 1), None, None, None), False)
    gray("gray_wp_nonnum", _d(_arr(_n("x"), _n("y"), _n("z")), None, None, None), False)
    gray("gray_wp_zeros", _d(_floats(0, 0, 0), None, None, None), False)
    gray("gray_wp_negative", _d(_floats(-1, -1, -1), None, None, None), False)
    gray("gray_bp_short", _d(_floats(*_D65), _floats(0, 0), None, None), False)
    gray("gray_wp_long_unit", _d(_floats(1, 1, 1, 9), None, None, None), True)
    gray("gray_d65_gamma_neg", _d(_floats(*_D65), None, COSFloat(-2.0), None), False)

    return c


def _emit(kind: str, name: str, d: COSDictionary, unit: bool, sample: list[float]) -> str:
    if kind == "rgb":
        return _emit_rgb(name, d, unit, sample)
    return _emit_gray(name, d, unit, sample)


# ---------- documented both-sides-pinned divergences ----------
#
# case name -> (pypdfbox digest line, reason). Each is asserted to (a) match
# pypdfbox's emitted line exactly AND (b) differ from the Java oracle.
_CTOR = (
    "Java PDCIEDictionaryBasedColorSpace ctor eagerly reads /WhitePoint "
    "(fillWhitepointCache(getWhitepoint())) and number-casts each element, so a "
    "short / non-numeric /WhitePoint throws during construction; pypdfbox is "
    "permissive (constructs, surfaces the defect lazily) — same family as "
    "test_colorspace_fuzz_wave1512.py"
)
_GAMMA = (
    "Java PDGamma.getR/G/B casts each /Gamma element to COSNumber (throws on "
    "non-numeric) and an empty /Gamma array yields an empty PDGamma (index-0 "
    "read throws); pypdfbox's get_gamma uses to_float_array (coerces "
    "non-numerics to 0.0) and treats an empty array as absent (falls back to "
    "the [1,1,1] default) — same lenient-coercion family as the /Range pin in "
    "test_icc_based_fuzz_wave1528.py"
)

_TRISTIM = (
    "Java getWhitepoint/getBlackPoint wrap the COSArray verbatim in a "
    "PDTristimulus whose getX/Y/Z number-cast index 0/1/2 (throws on a short / "
    "non-numeric array); pypdfbox's CalGray _read_tristimulus (and CalRGB "
    "_read_float_array for /BlackPoint) falls back to the [0,0,0]/[1,1,1] "
    "default when the array is short, and to_float_array coerces non-numerics to "
    "0.0 — same lenient-read family as the /Range pin in "
    "test_icc_based_fuzz_wave1528.py. (CalRGB /WhitePoint and /BlackPoint pass a "
    "short array through, so they happen to throw like Java; CalGray defaults.)"
)

_IDENT_MATRIX = "matrix=9:1.000,0.000,0.000,0.000,1.000,0.000,0.000,0.000,1.000"

_EXPECTED_DIVERGENCES: dict[str, tuple[str, str]] = {
    # --- permissive ctor: short / non-numeric /WhitePoint (Java throws in
    #     ctor via fillWhitepointCache; pypdfbox constructs, reads lazily) ---
    "rgb_wp_short": (
        f"CASE rgb_wp_short nc=3 gamma=1.000,1.000,1.000 {_IDENT_MATRIX} "
        "wp=ERR bp=0.000,0.000,0.000 init=0.000,0.000,0.000 rgb=102;153;204",
        _CTOR,
    ),
    "rgb_wp_nonnum": (
        f"CASE rgb_wp_nonnum nc=3 gamma=1.000,1.000,1.000 {_IDENT_MATRIX} "
        "wp=0.000,0.000,0.000 bp=0.000,0.000,0.000 init=0.000,0.000,0.000 "
        "rgb=102;153;204",
        _CTOR,
    ),
    "gray_wp_short": (
        "CASE gray_wp_short nc=1 gamma=1.000 matrix=NA wp=1.000,1.000,1.000 "
        "bp=0.000,0.000,0.000 init=0.000 rgb=184;166;162",
        _CTOR,
    ),
    "gray_wp_nonnum": (
        "CASE gray_wp_nonnum nc=1 gamma=1.000 matrix=NA wp=0.000,0.000,0.000 "
        "bp=0.000,0.000,0.000 init=0.000 rgb=102;102;102",
        _CTOR,
    ),
    # --- /Gamma numeric leniency: non-numeric coerced to 0.0 ---
    "rgb_d65_gamma_nonnum": (
        f"CASE rgb_d65_gamma_nonnum nc=3 gamma=0.000,0.000,0.000 {_IDENT_MATRIX} "
        "wp=0.951,1.000,1.089 bp=0.000,0.000,0.000 init=0.000,0.000,0.000 "
        "rgb=102;153;204",
        _GAMMA,
    ),
    # --- /Gamma numeric leniency: empty array -> [1,1,1] default ---
    "rgb_gamma_empty": (
        f"CASE rgb_gamma_empty nc=3 gamma=1.000,1.000,1.000 {_IDENT_MATRIX} "
        "wp=0.951,1.000,1.089 bp=0.000,0.000,0.000 init=0.000,0.000,0.000 "
        "rgb=102;153;204",
        _GAMMA,
    ),
    # --- /BlackPoint length leniency (CalGray): short -> [0,0,0] default ---
    "gray_bp_short": (
        "CASE gray_bp_short nc=1 gamma=1.000 matrix=NA wp=0.951,1.000,1.089 "
        "bp=0.000,0.000,0.000 init=0.000 rgb=102;102;102",
        _TRISTIM,
    ),
}


def _parse_probe(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.rstrip("\r")
        if not line.startswith("CASE "):
            continue
        name = line.split(" ", 2)[1]
        out[name] = line
    return out


@pytest.fixture(scope="module")
def _java_lines() -> dict[str, str]:
    return _parse_probe(run_probe_text("CalColorSpaceFuzzProbe"))


@requires_oracle
def test_corpus_count_matches(_java_lines: dict[str, str]) -> None:
    """The Java probe and the Python sibling drive the identical case set."""
    py_names = [name for _, name, _, _, _ in _build_cases()]
    assert len(py_names) == len(set(py_names)), "duplicate case name in corpus"
    assert set(py_names) == set(_java_lines), (
        "corpus drift: python-only="
        f"{sorted(set(py_names) - set(_java_lines))} "
        f"java-only={sorted(set(_java_lines) - set(py_names))}"
    )


@requires_oracle
@pytest.mark.parametrize(
    "kind,name,d,unit,sample",
    _build_cases(),
    ids=[c[1] for c in _build_cases()],
)
def test_cal_color_space_fuzz_case(
    kind: str,
    name: str,
    d: COSDictionary,
    unit: bool,
    sample: list[float],
    _java_lines: dict[str, str],
) -> None:
    """Each case's pypdfbox digest matches Java byte-for-byte, except the
    documented both-sides-pinned divergences."""
    py_line = _emit(kind, name, d, unit, sample)
    java_line = _java_lines[name]

    if name in _EXPECTED_DIVERGENCES:
        pinned, reason = _EXPECTED_DIVERGENCES[name]
        assert py_line == pinned, (
            f"{name}: pypdfbox digest drifted from its pin.\n"
            f"  emitted: {py_line!r}\n  pinned : {pinned!r}\n  reason : {reason}"
        )
        assert py_line != java_line, (
            f"{name}: pypdfbox now matches the Java oracle — the documented "
            f"divergence ({reason}) no longer holds. Remove this pin and let "
            f"the case fall through to the exact-match assertion.\n"
            f"  java/py: {java_line!r}"
        )
    else:
        assert py_line == java_line, (
            f"{name}: pypdfbox diverged from the live PDFBox oracle.\n"
            f"  pypdfbox: {py_line!r}\n  pdfbox  : {java_line!r}"
        )
