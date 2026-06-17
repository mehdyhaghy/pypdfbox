"""Live PDFBox differential parity for ``PDLineDashPattern`` over a malformed
dash array + phase (wave 1531, agent B).

``oracle/probes/LineDashPatternFuzzProbe.java`` materialises the same dash
arrays + phases in authoritative Apache PDFBox 3.0.7 and projects, per case:

* ``getDashArray()`` — the resolved ``float[]`` (non-``COSNumber`` entries map
  to ``0.0`` and are kept, never dropped — upstream ``COSArray.toFloatArray``).
* ``getPhase()`` — the dash phase. Upstream stores it as ``int`` (the field is
  ``private final int phase``); the negative-phase normalisation truncates the
  float result back to ``int``.
* ``getCOSObject()`` round-trip — the inner dash ``float[]`` and the phase
  entry's COS class + value. Upstream always serialises the phase as a
  ``COSInteger`` (``COSInteger.get((long) phase)``), never a ``COSFloat``.

pypdfbox builds the SAME COS shapes and must reproduce identical projections.

Real bug fixed this wave (was a pre-fix divergence): pypdfbox stored the
negative-phase-normalised phase as a ``float`` and serialised it as a
``COSFloat``; upstream stores ``int`` and serialises ``COSInteger``. The
constructor now truncates the phase to ``int`` before and after normalisation,
matching the upstream ``int phase`` field. See CHANGES.md, wave 1531.
"""

from __future__ import annotations

import math

import pytest

from pypdfbox.cos import (
    COSArray,
    COSBoolean,
    COSFloat,
    COSInteger,
    COSName,
    COSNull,
    COSString,
)
from pypdfbox.pdmodel.graphics.pd_line_dash_pattern import PDLineDashPattern
from tests.oracle.harness import requires_oracle, run_probe_text

# name | dash-element spec | phase  (see the probe's javadoc for the spelling)
_CASES: list[tuple[str, str, int]] = [
    ("empty", "-", 0),
    ("single_int", "i3", 0),
    ("multi_int", "i3,i2,i5", 0),
    ("all_zero", "i0,i0,i0", 0),
    ("single_zero", "i0", 0),
    ("negphase_small", "i3,i3", -2),
    ("negphase_large", "i3,i3", -100),
    ("negphase_zero_sum", "i0,i0", -5),
    ("negphase_empty", "-", -5),
    ("floats", "f1.5,f2.5", 0),
    ("neg_entries", "i-3,i5", 0),
    ("name_entry", "i3,name,i5", 0),
    ("str_entry", "i3,str", 0),
    ("bool_entry", "bool,i2", 0),
    ("null_entry", "null,i4", 0),
    ("nested_arr", "arr,i2", 0),
    ("huge_val", "f1e30,i2", 0),
    ("huge_phase", "i3,i3", 2000000000),
    ("phase_in_array_sum", "f0.5,f0.5", -3),
    ("mixed_nonnum", "name,str,null", 0),
    ("single_name", "name", 0),
    ("frac_phase_normalize", "f2.5,f2.5", -3),
]


def _build_elem(elem: str):
    if elem.startswith("i"):
        return COSInteger.get(int(elem[1:]))
    if elem.startswith("f"):
        return COSFloat(float(elem[1:]))
    return {
        "name": COSName.get_pdf_name("X"),
        "str": COSString("s"),
        "bool": COSBoolean.TRUE,
        "null": COSNull.NULL,
        "arr": COSArray(),
    }[elem]


def _build_dash(spec: str) -> COSArray:
    arr = COSArray()
    if spec == "-":
        return arr
    for elem in spec.split(","):
        arr.add(_build_elem(elem.strip()))
    return arr


def _norm_floats(line: str) -> str:
    """Normalise float renderings inside a projection line so Java's
    ``Float.toString`` (float32) and Python's ``repr`` (float64) of the same
    underlying value compare equal. We round every numeric token to a float32
    canonical form.
    """
    import re
    import struct

    def canon(token: str) -> str:
        try:
            val = float(token)
        except ValueError:
            return token
        # Round-trip through float32 so both ports collapse to one spelling.
        f32 = struct.unpack("f", struct.pack("f", val))[0]
        if math.isinf(f32):
            return "inf" if f32 > 0 else "-inf"
        if f32 == int(f32) and abs(f32) < 1e15:
            return str(int(f32))
        return repr(round(f32, 3))

    # Tokenise numbers (incl. scientific / signed) that sit between brackets,
    # commas, colons; leave structural chars alone.
    return re.sub(
        r"-?\d+\.?\d*(?:[eE][-+]?\d+)?",
        lambda m: canon(m.group(0)),
        line,
    )


def _py_line(name: str, spec: str, phase: int) -> str:
    dash = _build_dash(spec)
    pattern = PDLineDashPattern(dash, phase)
    arr = pattern.get_dash_array()
    ab = "[" + ",".join(_fmt(v) for v in arr) + "]"
    cos = pattern.get_cos_object()
    inner = cos.get_object(0).to_float_array()
    ib = "[" + ",".join(_fmt(v) for v in inner) + "]"
    phase_entry = cos.get_object(1)
    if isinstance(phase_entry, COSInteger):
        cp = "int:" + str(phase_entry.value)
    elif isinstance(phase_entry, COSFloat):
        cp = "float:" + _fmt(phase_entry.value)
    else:
        cp = type(phase_entry).__name__
    return f"CASE {name} arr={ab} phase={pattern.get_phase()} cos=[{ib},{cp}]"


def _fmt(v: float) -> str:
    if isinstance(v, float):
        if math.isnan(v):
            return "nan"
        if math.isinf(v):
            return "inf" if v > 0 else "-inf"
        if v == int(v) and abs(v) < 1e15:
            return str(int(v))
    return str(v)


@requires_oracle
def test_line_dash_pattern_fuzz_matches_pdfbox(tmp_path) -> None:
    manifest = tmp_path / "manifest.txt"
    manifest.write_text(
        "\n".join(f"{n}|{s}|{p}" for n, s, p in _CASES),
        encoding="utf-8",
    )
    java_out = run_probe_text("LineDashPatternFuzzProbe", str(manifest))
    java_lines = [ln for ln in java_out.splitlines() if ln.strip()]
    assert len(java_lines) == len(_CASES)

    py_lines = [_py_line(n, s, p) for n, s, p in _CASES]

    for java_line, py_line in zip(java_lines, py_lines, strict=True):
        assert _norm_floats(py_line) == _norm_floats(java_line)


@pytest.mark.parametrize(
    ("name", "spec", "phase"),
    _CASES,
    ids=[c[0] for c in _CASES],
)
def test_phase_is_always_int(name: str, spec: str, phase: int) -> None:
    """Pinned: upstream's ``phase`` field is ``int``; ``get_phase()`` and the
    ``getCOSObject`` phase entry are always integral, even after negative-phase
    normalisation produces a value via float arithmetic."""
    pattern = PDLineDashPattern(_build_dash(spec), phase)
    assert isinstance(pattern.get_phase(), int)
    assert not isinstance(pattern.get_phase(), bool)
    phase_entry = pattern.get_cos_object().get_object(1)
    assert isinstance(phase_entry, COSInteger)
