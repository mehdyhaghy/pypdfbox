"""Live PDFBox differential fuzz parity for ``PDLab`` (CIE L*a*b* colour space)
malformed ``[/Lab << ... >>]`` dictionaries (wave 1538, agent A).

Sibling of ``oracle/probes/LabColorSpaceFuzzProbe.java``. The Java probe builds a
fixed, seed-free corpus of malformed / missing / mistyped Lab colour-space COS
forms — missing dict, missing/short/long/empty/non-numeric ``/WhitePoint``,
``/BlackPoint`` variants, missing/short/long/empty/reversed/zero ``/Range``,
``COSNull`` entries, a stream where an array is expected — constructs
``new PDLab(array)`` for each, and emits one CASE line projecting every accessor
(or the thrown exception class) plus ``toRGB`` at the L* extremes and a*/b*
corners.

This module rebuilds the *identical* corpus case-for-case in the same order,
emits the identical CASE-line grammar from ``pypdfbox`` ``PDLab``, and asserts
line-for-line parity against the live Java oracle, with two documented
divergence families pinned **both sides** (assert pypdfbox's pinned value AND
that the Java oracle differs, so the rationale stays honest — if Java ever
converges the test fails loudly):

1. **Permissive accessor contract.** Where the malformed dictionary has a
   short/empty ``/WhitePoint`` PDFBox's eager whitepoint-cache fill throws an
   ``IndexOutOfBoundsException`` *in the constructor*; a short/empty
   ``/BlackPoint`` or ``/Range`` makes the corresponding ``PDTristimulus`` /
   ``PDRange`` accessor throw on access. pypdfbox is deliberately lenient: it
   reads what is present and falls back to the documented defaults
   (``WhitePoint`` ``[1 1 1]``, ``BlackPoint`` ``[0 0 0]``, ``Range``
   ``[-100 100 -100 100]``) instead of throwing. Same permissive-factory
   contract pinned by ``test_colorspace_fuzz_wave1512.py``.

2. **JVM CMM colour math in ``toRGB``.** PDFBox routes the final XYZ→sRGB step
   through the JVM colour-management module (D50 PCS); pypdfbox uses an explicit
   deterministic IEC 61966-2-1 D65 matrix. The Lab→XYZ companding (white-point
   scaled, with the XYZ ``<0→0`` floor) is identical on both sides, so only the
   last step diverges — deltas reach tens of 255, not rounding epsilons. Same
   divergence pinned by ``test_lab_clamp_oracle.py`` / ``test_cal_color_oracle``.

The ``short`` ``toRGB`` tag (a two-element triple) raises on **both** sides
(``rgb=short:ERR``) — that field is asserted to match exactly.

No real pypdfbox bugs were found on this surface: every divergence is one of the
two documented families above; on every case where both sides return a value the
values agree.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSNull,
    COSStream,
    COSString,
)
from pypdfbox.pdmodel.graphics.color.pd_lab import PDLab
from tests.oracle.harness import requires_oracle, run_probe_text

# ---------- COS builders (mirror LabColorSpaceFuzzProbe.java helpers) -------


def _floats(*vals: float) -> COSArray:
    a = COSArray()
    for v in vals:
        a.add(COSFloat(float(v)))
    return a


def _ints(*vals: int) -> COSArray:
    a = COSArray()
    for v in vals:
        a.add(COSInteger.get(v))
    return a


def _lab_dict(
    white_point: object = None,
    black_point: object = None,
    rng: object = None,
) -> COSDictionary:
    d = COSDictionary()
    if white_point is not None:
        d.set_item("WhitePoint", white_point)
    if black_point is not None:
        d.set_item("BlackPoint", black_point)
    if rng is not None:
        d.set_item("Range", rng)
    return d


def _lab_array(dict_obj: object) -> COSArray:
    a = COSArray()
    a.add(COSName.get_pdf_name("Lab"))
    if dict_obj is not None:
        a.add(dict_obj)
    return a


def _stream_with(payload: bytes) -> COSStream:
    s = COSStream()
    with s.create_output_stream() as os:
        os.write(payload)
    return s


_D50 = [0.9642, 1.0, 0.8249]
_D50_BP = [0.0, 0.0, 0.0]
_DEF_RANGE = [-100.0, 100.0, -100.0, 100.0]
_CUSTOM_RANGE = [-128.0, 127.0, -128.0, 127.0]


# Each corpus entry: (case_name, thunk building the [/Lab dict] COSArray).
# Order MUST match LabColorSpaceFuzzProbe.main exactly.
def _corpus() -> list[tuple[str, object]]:
    return [
        ("wellformed",
         _lab_array(_lab_dict(_floats(*_D50), _floats(*_D50_BP),
                              _floats(*_CUSTOM_RANGE)))),
        ("wellformed_defrange",
         _lab_array(_lab_dict(_floats(*_D50), None, _floats(*_DEF_RANGE)))),
        ("only_whitepoint",
         _lab_array(_lab_dict(_floats(*_D50), None, None))),
        ("no_dict", _lab_array(None)),
        ("empty_dict", _lab_array(COSDictionary())),
        ("wp_missing",
         _lab_array(_lab_dict(None, None, _floats(*_DEF_RANGE)))),
        ("wp_short2", _lab_array(_lab_dict(_floats(1, 1), None, None))),
        ("wp_long4", _lab_array(_lab_dict(_floats(1, 1, 1, 1), None, None))),
        ("wp_zeros", _lab_array(_lab_dict(_floats(0, 0, 0), None, None))),
        ("wp_unit", _lab_array(_lab_dict(_floats(1, 1, 1), None, None))),
        ("wp_empty", _lab_array(_lab_dict(COSArray(), None, None))),
        ("wp_not_array",
         _lab_array(_lab_dict(COSString("nope"), None, None))),
        ("wp_ints", _lab_array(_lab_dict(_ints(1, 1, 1), None, None))),
        ("bp_present",
         _lab_array(_lab_dict(_floats(*_D50), _floats(0.1, 0.1, 0.1), None))),
        ("bp_short",
         _lab_array(_lab_dict(_floats(*_D50), _floats(0.1, 0.1), None))),
        ("bp_long",
         _lab_array(_lab_dict(_floats(*_D50), _floats(0.1, 0.1, 0.1, 0.1),
                              None))),
        ("bp_empty",
         _lab_array(_lab_dict(_floats(*_D50), COSArray(), None))),
        ("bp_not_array",
         _lab_array(_lab_dict(_floats(*_D50), COSInteger.get(5), None))),
        ("range_missing",
         _lab_array(_lab_dict(_floats(*_D50), None, None))),
        ("range_short2",
         _lab_array(_lab_dict(_floats(*_D50), None, _floats(-50, 50)))),
        ("range_long6",
         _lab_array(_lab_dict(_floats(*_D50), None,
                              _floats(-50, 50, -50, 50, -50, 50)))),
        ("range_reversed",
         _lab_array(_lab_dict(_floats(*_D50), None,
                              _floats(100, -100, 100, -100)))),
        ("range_empty",
         _lab_array(_lab_dict(_floats(*_D50), None, COSArray()))),
        ("range_zeros",
         _lab_array(_lab_dict(_floats(*_D50), None, _floats(0, 0, 0, 0)))),
        ("range_not_array",
         _lab_array(_lab_dict(_floats(*_D50), None, COSString("r")))),
        ("range_ints",
         _lab_array(_lab_dict(_floats(*_D50), None,
                              _ints(-100, 100, -100, 100)))),
        ("range_asym",
         _lab_array(_lab_dict(_floats(*_D50), None, _floats(-50, 60, -70, 40)))),
        ("range_pos_only",
         _lab_array(_lab_dict(_floats(*_D50), None, _floats(0, 100, 0, 100)))),
        ("wp_cosnull", _lab_array(_lab_dict(COSNull.NULL, None, None))),
        ("range_cosnull",
         _lab_array(_lab_dict(_floats(*_D50), None, COSNull.NULL))),
        ("wp_stream",
         _lab_array(_lab_dict(_stream_with(b"\x00\x01\x02"), None, None))),
    ]


# ---------- pypdfbox CASE-line emitter (mirrors the Java emit) -------------


def _clamp255(value: float) -> int:
    r = round(value * 255.0)
    if r < 0:
        return 0
    if r > 255:
        return 255
    return int(r)


def _fmt_tri(values: list[float]) -> str:
    # PDFBox PDTristimulus.getX/Y/Z read indices 0/1/2; a shorter array throws.
    if len(values) < 3:
        return "ERR"
    return f"{values[0]:.4f},{values[1]:.4f},{values[2]:.4f}"


def _emit_py(name: str, lab_array: COSArray) -> str:
    sb = [f"CASE {name} "]
    try:
        cs = PDLab(lab_array)
    except Exception as exc:  # noqa: BLE001 - mirror Java catch(Throwable)
        return sb[0] + f"ctor=ERR:{_java_exc_name(exc)}"
    sb.append("ctor=ok")

    try:
        sb.append(f" name={cs.get_name()}")
    except Exception:  # noqa: BLE001
        sb.append(" name=ERR")

    try:
        sb.append(f" nc={cs.get_number_of_components()}")
    except Exception:  # noqa: BLE001
        sb.append(" nc=ERR")

    sb.append(" wp=" + _fmt_tri(cs.get_white_point()))
    sb.append(" bp=" + _fmt_tri(cs.get_black_point()))

    try:
        a_min, a_max = cs.get_a_range()
        b_min, b_max = cs.get_b_range()
        sb.append(f" rng={a_min:.4f},{a_max:.4f},{b_min:.4f},{b_max:.4f}")
    except Exception:  # noqa: BLE001
        sb.append(" rng=ERR")

    try:
        init = cs.get_initial_color().get_components()
        sb.append(" init=" + ",".join(f"{c:.4f}" for c in init))
    except Exception:  # noqa: BLE001
        sb.append(" init=ERR")

    for tag, triple in (
        ("L0", [0.0, 0.0, 0.0]),
        ("L100", [100.0, 0.0, 0.0]),
        ("mid", [50.0, 0.0, 0.0]),
        ("aPos", [50.0, 90.0, 0.0]),
        ("aNeg", [50.0, -90.0, 0.0]),
        ("bPos", [50.0, 0.0, 90.0]),
        ("bNeg", [50.0, 0.0, -90.0]),
        ("short", [50.0, 0.0]),
    ):
        try:
            r, g, b = cs.to_rgb(triple)
            sb.append(
                f" rgb={tag}:{_clamp255(r)};{_clamp255(g)};{_clamp255(b)}"
            )
        except Exception:  # noqa: BLE001
            sb.append(f" rgb={tag}:ERR")

    return "".join(sb)


def _java_exc_name(exc: Exception) -> str:
    """Best-effort map from a pypdfbox exception to the analogous Java simple
    class name so the ``ctor=ERR:<Name>`` token can match the Java oracle.
    Only the cases actually triggered need to align; everything else falls back
    to the Python class name (which would then surface as a real divergence)."""
    mapping = {
        "IndexError": "IndexOutOfBoundsException",
    }
    return mapping.get(type(exc).__name__, type(exc).__name__)


# ---------- probe parsing into a per-case field dict -----------------------


def _parse_case_fields(line: str) -> tuple[str, dict[str, str]]:
    """Parse one ``CASE <name> k=v ...`` line into (name, {key: value}).

    ``rgb=`` tokens are keyed by their tag (``rgb_L0`` etc.) so each toRGB
    sample is comparable independently.
    """
    toks = line.split()
    assert toks[0] == "CASE"
    name = toks[1]
    fields: dict[str, str] = {}
    for tok in toks[2:]:
        key, _, val = tok.partition("=")
        if key == "rgb":
            tag, _, rgb = val.partition(":")
            fields[f"rgb_{tag}"] = rgb
        else:
            fields[key] = val
    return name, fields


@pytest.fixture(scope="module")
def _java_cases() -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for raw in run_probe_text("LabColorSpaceFuzzProbe").splitlines():
        line = raw.strip()
        if not line.startswith("CASE "):
            continue
        name, fields = _parse_case_fields(line)
        out[name] = fields
    return out


@pytest.fixture(scope="module")
def _py_cases() -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for name, arr in _corpus():
        line = _emit_py(name, arr)
        cname, fields = _parse_case_fields(line)
        out[cname] = fields
    return out


# Fields where pypdfbox is *deliberately* more lenient than PDFBox (PDFBox
# throws / pypdfbox returns a default or partial). Keyed by case name -> set of
# field keys that may diverge. Every entry is asserted to ACTUALLY diverge so
# the permissive-contract rationale stays honest.
_PERMISSIVE: dict[str, set[str]] = {
    # short/empty /WhitePoint: PDFBox throws in the ctor (whitepoint cache fill
    # reads index 2); pypdfbox reads what is present / falls back to [1 1 1].
    "wp_short2": {"ALL"},
    "wp_empty": {"ALL"},
    # empty /BlackPoint: PDFBox's PDTristimulus.getZ throws (bp=ERR); pypdfbox
    # falls back to the [0 0 0] default. (A *short* /BlackPoint matches on both
    # sides: pypdfbox returns the 2-element partial which projects to ERR too,
    # exactly as PDFBox's getZ throws — so it is NOT pinned here.)
    "bp_empty": {"bp"},
    # short/empty /Range: PDFBox's PDRange.getMax throws on the missing slot,
    # cascading into getInitialColor; pypdfbox falls back to the defaults.
    "range_short2": {"rng", "init"},
    "range_empty": {"rng", "init"},
}

# rgb_* fields always diverge by design (the JVM-CMM XYZ→sRGB tail), EXCEPT
# where toRGB collapses to black on both sides (whitepoint zeroed) or raises on
# both sides (the two-element ``short`` triple). Those exceptions must match.
_RGB_MATCH_TAGS = {"rgb_short"}  # raises on both sides -> "ERR" == "ERR"


@requires_oracle
def test_lab_fuzz_corpus_complete(
    _java_cases: dict[str, dict[str, str]],
    _py_cases: dict[str, dict[str, str]],
) -> None:
    """Both sides emit the same case set in the same order."""
    assert set(_py_cases) == set(_java_cases)
    assert [n for n, _ in _corpus()] == list(_java_cases)


@requires_oracle
@pytest.mark.parametrize("case", [n for n, _ in _corpus()])
def test_lab_fuzz_case(
    case: str,
    _java_cases: dict[str, dict[str, str]],
    _py_cases: dict[str, dict[str, str]],
) -> None:
    """Per-case structural parity.

    Non-``rgb`` fields must match Java exactly, except the documented
    permissive-leniency fields (pinned both sides). ``rgb`` fields are the
    documented JVM-CMM divergence: they may differ, but where toRGB collapses
    to black on both sides (or raises on both sides) they must match.
    """
    jf = _java_cases[case]
    pf = _py_cases[case]
    permissive = _PERMISSIVE.get(case, set())

    # ctor / name / nc / wp / bp / rng / init
    for key in ("ctor", "name", "nc", "wp", "bp", "rng", "init"):
        if key not in jf and key not in pf:
            continue
        jv = jf.get(key)
        pv = pf.get(key)
        if "ALL" in permissive or key in permissive:
            # Pinned divergence: assert it actually diverges so the rationale
            # stays honest. (For ALL-permissive ctor-throw cases the whole line
            # diverges; assert at least the ctor token differs.)
            if "ALL" in permissive:
                assert jf.get("ctor") != pf.get("ctor"), (
                    f"{case}: expected ctor divergence (PDFBox throws, pypdfbox "
                    f"is lenient) but both ctor={pf.get('ctor')!r} — re-tier."
                )
                continue
            assert jv != pv, (
                f"{case}.{key}: expected permissive divergence but both "
                f"sides agree ({pv!r}) — PDFBox converged; drop the pin."
            )
            continue
        assert pv == jv, f"{case}.{key}: pypdfbox {pv!r} != PDFBox {jv!r}"

    # rgb tags
    for key in (k for k in jf if k.startswith("rgb_")):
        jv = jf[key]
        pv = pf.get(key)
        if key in _RGB_MATCH_TAGS or jv == "0;0;0":
            # collapses to black on both sides, or raises on both sides.
            assert pv == jv, f"{case}.{key}: pypdfbox {pv!r} != PDFBox {jv!r}"


@requires_oracle
def test_lab_fuzz_cmm_divergence_is_real(
    _java_cases: dict[str, dict[str, str]],
    _py_cases: dict[str, dict[str, str]],
) -> None:
    """Keep the JVM-CMM ``toRGB`` divergence honest: on the well-formed D50
    space at least one non-black sample must actually differ from PDFBox. If
    pypdfbox ever matched PDFBox on every sample the documented divergence would
    no longer hold and the rgb-leniency in :func:`test_lab_fuzz_case` should be
    removed."""
    jf = _java_cases["wellformed"]
    pf = _py_cases["wellformed"]
    diffs = [
        k
        for k in jf
        if k.startswith("rgb_") and k != "rgb_short" and jf[k] != "0;0;0"
        and jf[k] != pf.get(k)
    ]
    assert diffs, (
        "wellformed: pypdfbox now matches PDFBox on every non-black toRGB "
        "sample — the documented XYZ→sRGB CMM divergence no longer holds."
    )


@requires_oracle
def test_lab_fuzz_permissive_leniency_is_real(
    _java_cases: dict[str, dict[str, str]],
    _py_cases: dict[str, dict[str, str]],
) -> None:
    """Sanity-check the permissive-contract pins: PDFBox really does throw (or
    return ERR) where pypdfbox returns a value, for every pinned case."""
    # wp_short2 / wp_empty: PDFBox throws in the constructor.
    for case in ("wp_short2", "wp_empty"):
        assert _java_cases[case]["ctor"].startswith("ERR"), (
            f"{case}: expected PDFBox ctor=ERR; got {_java_cases[case]['ctor']}"
        )
        assert _py_cases[case]["ctor"] == "ok", (
            f"{case}: expected pypdfbox lenient ctor=ok"
        )
    # bp_empty: PDFBox getBlackPoint accessor throws (bp=ERR); pypdfbox falls
    # back to the [0 0 0] default.
    assert _java_cases["bp_empty"]["bp"] == "ERR"
    assert _py_cases["bp_empty"]["bp"] != "ERR"
    # range_short2 / range_empty: PDFBox getARange/getBRange throw (rng=ERR).
    for case in ("range_short2", "range_empty"):
        assert _java_cases[case]["rng"] == "ERR"
        assert _py_cases[case]["rng"] != "ERR"
