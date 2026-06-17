"""Live Apache PDFBox differential parity for PDF functions + shadings.

Compares pypdfbox's ``PDFunctionType0/2/3/4`` evaluation and the axial
(Type 2) / radial (Type 3) shading color-function samples against Apache
PDFBox 3.0.7 via the ``ShadingFuncProbe`` Java oracle.

The probe (``oracle/probes/ShadingFuncProbe.java``) hard-codes a battery of
functions and shadings, evaluates each at fixed sample points, and emits one
canonical line per evaluation:

    FUNC <name> <in0,in1,...> -> <out0> <out1> ...
    SHADING <name> t=<t> -> <c0> <c1> ...

Every float is rendered with ``%.6f`` on the Java side. The Python side
rebuilds the *same* COS objects (same builders, same inputs), evaluates with
pypdfbox, formats identically, and asserts line-by-line equality.

Epsilon: function math is near-exact, but Java PDFBox computes in 32-bit
``float`` while pypdfbox uses 64-bit Python ``float``. After rounding both
to 6 decimal places the two agree exactly for the whole battery, so the
default assertion is on the formatted strings. A numeric fallback compares
with ``abs <= 2e-6`` to document the float-width tolerance for any value
that ever lands on a rounding boundary.
"""

from __future__ import annotations

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSStream,
)
from pypdfbox.pdmodel.common.function import PDFunction
from pypdfbox.pdmodel.graphics.shading import PDShadingType2, PDShadingType3
from tests.oracle.harness import requires_oracle, run_probe_text

# Float-width tolerance: Java float32 vs Python float64, post 6-dp rounding.
_EPSILON = 2e-6


# ---------- canonical formatting (mirror the Java %.6f) ----------


def _fmt(v: float) -> str:
    return f"{v:.6f}"


def _fmt_in(values: list[float]) -> str:
    return ",".join(_fmt(v) for v in values)


def _func_line(name: str, fn: PDFunction, inputs: list[float]) -> str:
    out = fn.eval(inputs)
    body = " ".join(_fmt(v) for v in out)
    return f"FUNC {name} {_fmt_in(inputs)} -> {body}".rstrip()


def _shading_line(name: str, color: list[float], t: float) -> str:
    body = " ".join(_fmt(v) for v in color)
    return f"SHADING {name} t={_fmt(t)} -> {body}".rstrip()


# ---------- COS builders (mirror ShadingFuncProbe.java) ----------


def _floats(*vals: float) -> COSArray:
    a = COSArray()
    for v in vals:
        a.add(COSFloat(float(v)))
    return a


def _ints(*vals: int) -> COSArray:
    a = COSArray()
    for v in vals:
        a.add(COSInteger.get(int(v)))
    return a


def _type2(
    c0: list[float] | None,
    c1: list[float] | None,
    n: float,
    domain: list[float],
    rng: list[float] | None,
) -> COSDictionary:
    d = COSDictionary()
    d.set_int(COSName.get_pdf_name("FunctionType"), 2)
    d.set_item(COSName.get_pdf_name("Domain"), _floats(*domain))
    if c0 is not None:
        d.set_item(COSName.get_pdf_name("C0"), _floats(*c0))
    if c1 is not None:
        d.set_item(COSName.get_pdf_name("C1"), _floats(*c1))
    d.set_item(COSName.get_pdf_name("N"), COSFloat(float(n)))
    if rng is not None:
        d.set_item(COSName.get_pdf_name("Range"), _floats(*rng))
    return d


def _type4(ps: str, domain: list[float], rng: list[float]) -> COSStream:
    s = COSStream()
    s.set_int(COSName.get_pdf_name("FunctionType"), 4)
    s.set_item(COSName.get_pdf_name("Domain"), _floats(*domain))
    s.set_item(COSName.get_pdf_name("Range"), _floats(*rng))
    with s.create_output_stream() as o:
        o.write(ps.encode("ascii"))
    return s


def _type0(
    samples: bytes,
    size: list[int],
    bps: int,
    domain: list[float],
    rng: list[float],
    encode: list[int] | None = None,
    decode: list[float] | None = None,
    order: int = 0,
) -> COSStream:
    s = COSStream()
    s.set_int(COSName.get_pdf_name("FunctionType"), 0)
    s.set_item(COSName.get_pdf_name("Domain"), _floats(*domain))
    s.set_item(COSName.get_pdf_name("Range"), _floats(*rng))
    s.set_item(COSName.get_pdf_name("Size"), _ints(*size))
    s.set_int(COSName.get_pdf_name("BitsPerSample"), bps)
    if encode is not None:
        s.set_item(COSName.get_pdf_name("Encode"), _ints(*encode))
    if decode is not None:
        s.set_item(COSName.get_pdf_name("Decode"), _floats(*decode))
    if order > 0:
        s.set_int(COSName.get_pdf_name("Order"), order)
    with s.create_output_stream() as o:
        o.write(samples)
    return s


def _create(base: COSDictionary | COSStream) -> PDFunction:
    fn = PDFunction.create(base)
    assert fn is not None
    return fn


# ---------- battery (mirror ShadingFuncProbe.java exactly) ----------


def _build_expected_lines() -> list[str]:
    lines: list[str] = []

    # ===== Type 2 =====
    t2lin = _create(_type2([1, 0, 0], [0, 0, 1], 1.0, [0, 1], None))
    for x in (0.0, 0.25, 0.5, 0.75, 1.0):
        lines.append(_func_line("T2lin", t2lin, [x]))
    t2quad = _create(_type2([0], [1], 2.0, [0, 1], None))
    for x in (0.0, 0.25, 0.5, 0.75, 1.0):
        lines.append(_func_line("T2quad", t2quad, [x]))
    t2sqrt = _create(_type2([0, 1], [1, 0], 0.5, [0, 1], None))
    for x in (0.1, 0.5, 0.9):
        lines.append(_func_line("T2sqrt", t2sqrt, [x]))
    t2def = _create(_type2(None, None, 1.0, [0, 1], None))
    for x in (0.0, 0.3, 1.0):
        lines.append(_func_line("T2def", t2def, [x]))
    t2clamp = _create(_type2([-0.5], [1.5], 1.0, [0, 1], [0, 1]))
    for x in (0.0, 0.25, 0.5, 0.75, 1.0):
        lines.append(_func_line("T2clamp", t2clamp, [x]))
    t2dom = _create(_type2([0], [1], 1.0, [0.2, 0.8], None))
    for x in (0.0, 0.2, 0.5, 0.8, 1.0):
        lines.append(_func_line("T2dom", t2dom, [x]))

    # ===== Type 3 (stitching) =====
    funcs = COSArray()
    funcs.add(_type2([0], [1], 1.0, [0, 1], None))
    funcs.add(_type2([1], [0], 1.0, [0, 1], None))
    t3d = COSDictionary()
    t3d.set_int(COSName.get_pdf_name("FunctionType"), 3)
    t3d.set_item(COSName.get_pdf_name("Domain"), _floats(0, 1))
    t3d.set_item(COSName.get_pdf_name("Functions"), funcs)
    t3d.set_item(COSName.get_pdf_name("Bounds"), _floats(0.5))
    t3d.set_item(COSName.get_pdf_name("Encode"), _floats(0, 1, 0, 1))
    t3 = _create(t3d)
    for x in (0.0, 0.25, 0.49, 0.5, 0.51, 0.75, 1.0):
        lines.append(_func_line("T3stitch", t3, [x]))

    funcs3 = COSArray()
    funcs3.add(_type2([0], [1], 1.0, [0, 1], None))
    funcs3.add(_type2([1], [0], 1.0, [0, 1], None))
    funcs3.add(_type2([0], [1], 2.0, [0, 1], None))
    t3b = COSDictionary()
    t3b.set_int(COSName.get_pdf_name("FunctionType"), 3)
    t3b.set_item(COSName.get_pdf_name("Domain"), _floats(0, 1))
    t3b.set_item(COSName.get_pdf_name("Functions"), funcs3)
    t3b.set_item(COSName.get_pdf_name("Bounds"), _floats(0.3, 0.7))
    t3b.set_item(COSName.get_pdf_name("Encode"), _floats(0, 1, 0, 1, 0, 1))
    t3three = _create(t3b)
    for x in (0.0, 0.15, 0.3, 0.5, 0.7, 0.85, 1.0):
        lines.append(_func_line("T3three", t3three, [x]))

    # ===== Type 0 (sampled) =====
    t0lin = _create(_type0(bytes([0, 128, 255]), [3], 8, [0, 1], [0, 1]))
    for x in (0.0, 0.25, 0.5, 0.75, 1.0):
        lines.append(_func_line("T0lin", t0lin, [x]))
    t0rgb = _create(
        _type0(bytes([255, 0, 0, 0, 0, 255]), [2], 8, [0, 1], [0, 1, 0, 1, 0, 1])
    )
    for x in (0.0, 0.25, 0.5, 0.75, 1.0):
        lines.append(_func_line("T0rgb", t0rgb, [x]))
    t0grid = _create(
        _type0(bytes([0, 85, 170, 255]), [2, 2], 8, [0, 1, 0, 1], [0, 1])
    )
    for in_ in ([0, 0], [1, 0], [0, 1], [1, 1], [0.5, 0.5], [0.25, 0.75]):
        lines.append(_func_line("T0grid", t0grid, in_))
    t0n4 = _create(_type0(bytes([0x05, 0xAF]), [4], 4, [0, 1], [0, 1]))
    for x in (0.0, 0.33, 0.66, 1.0):
        lines.append(_func_line("T0n4", t0n4, [x]))
    t0n16 = _create(_type0(bytes([0x00, 0x00, 0xFF, 0xFF]), [2], 16, [0, 1], [0, 1]))
    for x in (0.0, 0.5, 1.0):
        lines.append(_func_line("T0n16", t0n16, [x]))

    # ===== Type 4 (PostScript) =====
    t4sub = _create(_type4("{ 1 exch sub }", [0, 1], [0, 1]))
    for x in (0.0, 0.25, 0.5, 0.75, 1.0):
        lines.append(_func_line("T4sub", t4sub, [x]))
    t4sq = _create(_type4("{ dup mul }", [0, 1], [0, 1]))
    for x in (0.0, 0.25, 0.5, 0.75, 1.0):
        lines.append(_func_line("T4sq", t4sq, [x]))
    t4rgb = _create(_type4("{ dup 1 exch sub 0.5 }", [0, 1], [0, 1, 0, 1, 0, 1]))
    for x in (0.0, 0.5, 1.0):
        lines.append(_func_line("T4rgb", t4rgb, [x]))
    t4cond = _create(_type4("{ 0.5 lt { 0 } { 1 } ifelse }", [0, 1], [0, 1]))
    for x in (0.0, 0.49, 0.5, 0.51, 1.0):
        lines.append(_func_line("T4cond", t4cond, [x]))
    t4math = _create(_type4("{ 360 mul sin abs }", [0, 1], [0, 1]))
    for x in (0.0, 0.125, 0.25, 0.5, 0.75):
        lines.append(_func_line("T4math", t4math, [x]))
    t4avg = _create(_type4("{ add 2 div }", [0, 1, 0, 1], [0, 1]))
    for in_ in ([0, 0], [1, 0], [0.2, 0.8], [1, 1]):
        lines.append(_func_line("T4avg", t4avg, in_))

    # ===== Axial (Type 2) shading color function =====
    ax = PDShadingType2()
    ax.set_coords(_floats(0, 0, 100, 0))
    ax.get_cos_object().set_item(
        COSName.get_pdf_name("Function"),
        _type2([1, 0, 0], [0, 0, 1], 1.0, [0, 1], None),
    )
    for t in (0.0, 0.25, 0.5, 0.75, 1.0):
        lines.append(_shading_line("AxialRGB", ax.eval_function(t), t))

    ax2 = PDShadingType2()
    ax2.set_coords(_floats(0, 0, 100, 0))
    sfuncs = COSArray()
    sfuncs.add(_type2([0], [1], 1.0, [0, 1], None))
    sfuncs.add(_type2([1], [0], 1.0, [0, 1], None))
    sdict = COSDictionary()
    sdict.set_int(COSName.get_pdf_name("FunctionType"), 3)
    sdict.set_item(COSName.get_pdf_name("Domain"), _floats(0, 1))
    sdict.set_item(COSName.get_pdf_name("Functions"), sfuncs)
    sdict.set_item(COSName.get_pdf_name("Bounds"), _floats(0.5))
    sdict.set_item(COSName.get_pdf_name("Encode"), _floats(0, 1, 0, 1))
    ax2.get_cos_object().set_item(COSName.get_pdf_name("Function"), sdict)
    for t in (0.0, 0.25, 0.5, 0.75, 1.0):
        lines.append(_shading_line("AxialStitch", ax2.eval_function(t), t))

    # ===== Radial (Type 3) shading color function =====
    rad = PDShadingType3()
    rad.set_coords(_floats(0, 0, 0, 0, 0, 100))
    rad.get_cos_object().set_item(
        COSName.get_pdf_name("Function"),
        _type2([0, 1, 0], [1, 1, 0], 1.0, [0, 1], None),
    )
    for t in (0.0, 0.25, 0.5, 0.75, 1.0):
        lines.append(_shading_line("RadialRGB", rad.eval_function(t), t))

    rad2 = PDShadingType3()
    rad2.set_coords(_floats(0, 0, 0, 0, 0, 100))
    per_comp = COSArray()
    per_comp.add(_type2([0], [1], 1.0, [0, 1], None))
    per_comp.add(_type2([1], [0.5], 1.0, [0, 1], None))
    per_comp.add(_type2([0.2], [0.8], 2.0, [0, 1], None))
    rad2.get_cos_object().set_item(COSName.get_pdf_name("Function"), per_comp)
    for t in (0.0, 0.25, 0.5, 0.75, 1.0):
        lines.append(_shading_line("RadialPerComp", rad2.eval_function(t), t))

    rad3 = PDShadingType3()
    rad3.set_coords(_floats(0, 0, 0, 0, 0, 100))
    rad3.get_cos_object().set_item(
        COSName.get_pdf_name("Function"),
        _type2([-0.5], [1.5], 1.0, [0, 1], None),
    )
    for t in (0.0, 0.25, 0.5, 0.75, 1.0):
        lines.append(_shading_line("RadialClamp", rad3.eval_function(t), t))

    return lines


def _numeric_close(line_a: str, line_b: str) -> bool:
    """Fallback: compare the float fields with ``abs <= _EPSILON``.

    Used only when the formatted strings differ — documents the
    Java-float32 vs Python-float64 tolerance for boundary roundings. The
    prefix (everything up to ``->``) must still match exactly.
    """
    head_a, _, tail_a = line_a.partition("->")
    head_b, _, tail_b = line_b.partition("->")
    if head_a != head_b:
        return False
    fa = [float(x) for x in tail_a.split()]
    fb = [float(x) for x in tail_b.split()]
    if len(fa) != len(fb):
        return False
    return all(abs(x - y) <= _EPSILON for x, y in zip(fa, fb, strict=True))


@requires_oracle
def test_shading_func_eval_matches_pdfbox():
    java_lines = run_probe_text("ShadingFuncProbe").splitlines()
    py_lines = _build_expected_lines()

    assert len(py_lines) == len(java_lines), (
        f"line count mismatch: py={len(py_lines)} java={len(java_lines)}\n"
        f"py head: {py_lines[:3]}\njava head: {java_lines[:3]}"
    )

    mismatches: list[str] = []
    for i, (py, java) in enumerate(zip(py_lines, java_lines, strict=True)):
        if py == java:
            continue
        if _numeric_close(py, java):
            continue
        mismatches.append(f"  line {i}:\n    py  : {py}\n    java: {java}")

    assert not mismatches, "function/shading parity divergence:\n" + "\n".join(
        mismatches
    )
