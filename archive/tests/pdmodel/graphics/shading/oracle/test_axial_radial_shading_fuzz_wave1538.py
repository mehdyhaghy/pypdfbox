"""Differential fuzz audit for the type-specific geometry / function
accessors of ``PDShadingType1`` (function-based), ``PDShadingType2`` (axial),
and ``PDShadingType3`` (radial) vs Apache PDFBox 3.0.7 (wave 1538, agent C).

Distinct angle from ``test_shading_pattern_fuzz_wave1513`` (which projects the
generic ``getShadingType`` / ``getColorSpace`` / raw COS key arity): this audit
drives the *typed* accessors each concrete subclass exposes and that callers
consume — ``PDShadingType1.get_domain`` / ``get_matrix`` / ``get_function``;
``PDShadingType2/3.get_coords`` / ``get_domain`` / ``get_extend`` /
``get_function``.

Upstream contract (confirmed by decompiling PDFBox 3.0.7):
``getDomain`` / ``getCoords`` / ``getExtend`` all delegate to
``COSDictionary.getCOSArray(name)`` — which returns the stored ``COSArray`` when
the entry IS a ``COSArray``, and ``null`` otherwise (absent, wrong type). There
is **no** spec-default materialization (``[0 1 0 1]`` / ``[0 1]`` /
``[false false]``) and **no** boolean coercion. ``getFunction`` routes any
non-null ``/Function`` through ``PDFunction.create``.

Both sides are driven on the SAME bytes: a one-page PDF per case (mutated
shading dict installed as resource ``/Shading/Sh1``) plus a ``manifest.txt``
are written to a tmp dir. The Java probe
(``oracle/probes/AxialRadialShadingFuzzProbe.java``) projects a stable framed
line per case through the typed accessors; this module reads the same files and
projects the identical grammar through pypdfbox, then asserts line-for-line.

Line grammar (one per case, manifest order)::

    CASE <name> type=<n|ERR> class=<simpleName|null> coords=<arr_n|null|n/a>
        domain=<arr_n|null> extend=<arr_n|null|n/a> matrix=<ok|null|n/a>
        function=<simpleName|null|ERR>

Java is ground truth. A real divergence is a production fix in
``pypdfbox/pdmodel/graphics/shading/``; a defensible divergence is pinned in
``_PINNED`` with a matching CHANGES.md row.
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSBoolean,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSString,
)
from pypdfbox.pdmodel.pd_document import PDDocument
from tests.oracle.harness import requires_oracle, run_probe_text

_N = COSName.get_pdf_name


# --------------------------------------------------------------------- helpers


def _arr(*items: COSBase) -> COSArray:
    a = COSArray()
    for it in items:
        a.add(it)
    return a


def _nums(*vals: float) -> COSArray:
    return _arr(*[COSFloat(float(v)) for v in vals])


def _identity_func() -> COSDictionary:
    """A minimal valid Type 2 (exponential) function dict."""
    f = COSDictionary()
    f.set_int(_N("FunctionType"), 2)
    f.set_item(_N("Domain"), _nums(0, 1))
    f.set_item(_N("C0"), _nums(0))
    f.set_item(_N("C1"), _nums(1))
    f.set_float(_N("N"), 1.0)
    return f


def _rgb() -> COSName:
    return _N("DeviceRGB")


# --------------------------------------------------------------------- corpus


def _cases() -> dict[str, COSDictionary]:
    cases: dict[str, COSDictionary] = {}

    def add(name: str, d: COSDictionary) -> None:
        cases[name] = d

    # ----- Type 1 function-based ------------------------------------------
    d = COSDictionary()
    d.set_int(_N("ShadingType"), 1)
    d.set_item(_N("ColorSpace"), _rgb())
    d.set_item(_N("Domain"), _nums(0, 1, 0, 1))
    d.set_item(_N("Matrix"), _nums(1, 0, 0, 1, 0, 0))
    d.set_item(_N("Function"), _identity_func())
    add("t1_well_formed", d)

    d = COSDictionary()
    d.set_int(_N("ShadingType"), 1)
    d.set_item(_N("ColorSpace"), _rgb())
    add("t1_domain_missing", d)

    d = COSDictionary()
    d.set_int(_N("ShadingType"), 1)
    d.set_item(_N("ColorSpace"), _rgb())
    d.set_item(_N("Domain"), _nums(0, 1))  # wrong length (should be 4)
    add("t1_domain_short", d)

    d = COSDictionary()
    d.set_int(_N("ShadingType"), 1)
    d.set_item(_N("ColorSpace"), _rgb())
    d.set_item(_N("Domain"), COSString("0 1 0 1"))  # not an array
    add("t1_domain_not_array", d)

    d = COSDictionary()
    d.set_int(_N("ShadingType"), 1)
    d.set_item(_N("ColorSpace"), _rgb())
    d.set_item(_N("Domain"), _arr(COSString("a"), COSString("b")))  # non-numeric
    add("t1_domain_non_numeric", d)

    d = COSDictionary()
    d.set_int(_N("ShadingType"), 1)
    d.set_item(_N("ColorSpace"), _rgb())
    d.set_item(_N("Domain"), _nums(0, 1, 0, 1))
    # /Matrix absent → getMatrix() returns identity (non-null) upstream.
    add("t1_matrix_missing", d)

    d = COSDictionary()
    d.set_int(_N("ShadingType"), 1)
    d.set_item(_N("ColorSpace"), _rgb())
    d.set_item(_N("Matrix"), _nums(1, 0, 0))  # short → identity fallback
    add("t1_matrix_short", d)

    d = COSDictionary()
    d.set_int(_N("ShadingType"), 1)
    d.set_item(_N("ColorSpace"), _rgb())
    add("t1_function_missing", d)

    d = COSDictionary()
    d.set_int(_N("ShadingType"), 1)
    d.set_item(_N("ColorSpace"), _rgb())
    d.set_item(_N("Function"), _arr(_identity_func(), _identity_func()))
    add("t1_function_array", d)

    # ----- Type 2 axial ---------------------------------------------------
    d = COSDictionary()
    d.set_int(_N("ShadingType"), 2)
    d.set_item(_N("ColorSpace"), _rgb())
    d.set_item(_N("Coords"), _nums(0, 0, 100, 0))
    d.set_item(_N("Domain"), _nums(0, 1))
    d.set_item(_N("Extend"), _arr(COSBoolean.TRUE, COSBoolean.FALSE))
    d.set_item(_N("Function"), _identity_func())
    add("t2_well_formed", d)

    d = COSDictionary()
    d.set_int(_N("ShadingType"), 2)
    d.set_item(_N("ColorSpace"), _rgb())
    d.set_item(_N("Function"), _identity_func())
    add("t2_coords_missing", d)

    d = COSDictionary()
    d.set_int(_N("ShadingType"), 2)
    d.set_item(_N("ColorSpace"), _rgb())
    d.set_item(_N("Coords"), _nums(0, 0))  # axial needs 4
    add("t2_coords_short", d)

    d = COSDictionary()
    d.set_int(_N("ShadingType"), 2)
    d.set_item(_N("ColorSpace"), _rgb())
    d.set_item(_N("Coords"), COSString("0 0 1 1"))  # not an array
    add("t2_coords_not_array", d)

    d = COSDictionary()
    d.set_int(_N("ShadingType"), 2)
    d.set_item(_N("ColorSpace"), _rgb())
    d.set_item(_N("Coords"), _arr(COSName.get_pdf_name("x"), COSFloat(0)))
    add("t2_coords_non_numeric", d)

    d = COSDictionary()
    d.set_int(_N("ShadingType"), 2)
    d.set_item(_N("ColorSpace"), _rgb())
    d.set_item(_N("Coords"), _nums(0, 0, 1, 1))
    add("t2_domain_missing", d)

    d = COSDictionary()
    d.set_int(_N("ShadingType"), 2)
    d.set_item(_N("ColorSpace"), _rgb())
    d.set_item(_N("Coords"), _nums(0, 0, 1, 1))
    d.set_item(_N("Domain"), _nums(0.2, 0.4, 0.6))  # wrong length
    add("t2_domain_wrong_length", d)

    d = COSDictionary()
    d.set_int(_N("ShadingType"), 2)
    d.set_item(_N("ColorSpace"), _rgb())
    d.set_item(_N("Coords"), _nums(0, 0, 1, 1))
    d.set_item(_N("Domain"), COSInteger(0))  # not an array
    add("t2_domain_not_array", d)

    d = COSDictionary()
    d.set_int(_N("ShadingType"), 2)
    d.set_item(_N("ColorSpace"), _rgb())
    d.set_item(_N("Coords"), _nums(0, 0, 1, 1))
    add("t2_extend_missing", d)

    d = COSDictionary()
    d.set_int(_N("ShadingType"), 2)
    d.set_item(_N("ColorSpace"), _rgb())
    d.set_item(_N("Coords"), _nums(0, 0, 1, 1))
    d.set_item(_N("Extend"), _arr(COSBoolean.TRUE))  # short
    add("t2_extend_short", d)

    d = COSDictionary()
    d.set_int(_N("ShadingType"), 2)
    d.set_item(_N("ColorSpace"), _rgb())
    d.set_item(_N("Coords"), _nums(0, 0, 1, 1))
    d.set_item(_N("Extend"), _arr(COSInteger(1), COSInteger(0)))  # non-boolean
    add("t2_extend_non_boolean", d)

    d = COSDictionary()
    d.set_int(_N("ShadingType"), 2)
    d.set_item(_N("ColorSpace"), _rgb())
    d.set_item(_N("Coords"), _nums(0, 0, 1, 1))
    d.set_item(_N("Extend"), COSBoolean.TRUE)  # not an array
    add("t2_extend_not_array", d)

    d = COSDictionary()
    d.set_int(_N("ShadingType"), 2)
    d.set_item(_N("ColorSpace"), _rgb())
    d.set_item(_N("Coords"), _nums(0, 0, 1, 1))
    add("t2_function_missing", d)

    # ----- Type 3 radial --------------------------------------------------
    d = COSDictionary()
    d.set_int(_N("ShadingType"), 3)
    d.set_item(_N("ColorSpace"), _rgb())
    d.set_item(_N("Coords"), _nums(0, 0, 0, 0, 0, 50))
    d.set_item(_N("Domain"), _nums(0, 1))
    d.set_item(_N("Extend"), _arr(COSBoolean.TRUE, COSBoolean.TRUE))
    d.set_item(_N("Function"), _identity_func())
    add("t3_well_formed", d)

    d = COSDictionary()
    d.set_int(_N("ShadingType"), 3)
    d.set_item(_N("ColorSpace"), _rgb())
    d.set_item(_N("Function"), _identity_func())
    add("t3_coords_missing", d)

    d = COSDictionary()
    d.set_int(_N("ShadingType"), 3)
    d.set_item(_N("ColorSpace"), _rgb())
    d.set_item(_N("Coords"), _nums(0, 0, 100, 0))  # radial needs 6
    add("t3_coords_axial_arity", d)

    d = COSDictionary()
    d.set_int(_N("ShadingType"), 3)
    d.set_item(_N("ColorSpace"), _rgb())
    d.set_item(_N("Coords"), _nums(0, 0, -5, 0, 0, -50))  # negative radii
    d.set_item(_N("Function"), _identity_func())
    add("t3_negative_radii", d)

    d = COSDictionary()
    d.set_int(_N("ShadingType"), 3)
    d.set_item(_N("ColorSpace"), _rgb())
    d.set_item(_N("Coords"), COSInteger(6))  # not an array
    add("t3_coords_not_array", d)

    d = COSDictionary()
    d.set_int(_N("ShadingType"), 3)
    d.set_item(_N("ColorSpace"), _rgb())
    d.set_item(_N("Coords"), _nums(0, 0, 0, 0, 0, 50))
    d.set_item(_N("Domain"), _nums(0, 1, 0))  # wrong length
    add("t3_domain_wrong_length", d)

    d = COSDictionary()
    d.set_int(_N("ShadingType"), 3)
    d.set_item(_N("ColorSpace"), _rgb())
    d.set_item(_N("Coords"), _nums(0, 0, 0, 0, 0, 50))
    add("t3_domain_extend_missing", d)

    d = COSDictionary()
    d.set_int(_N("ShadingType"), 3)
    d.set_item(_N("ColorSpace"), _rgb())
    d.set_item(_N("Coords"), _nums(0, 0, 0, 0, 0, 50))
    d.set_item(_N("Extend"), _arr(COSBoolean.TRUE, COSBoolean.FALSE, COSBoolean.TRUE))
    add("t3_extend_long", d)

    return cases


def _write_case_pdf(path: Path, entry: COSDictionary) -> None:
    from pypdfbox.pdmodel.pd_page import PDPage

    doc = PDDocument()
    try:
        page = PDPage()
        doc.add_page(page)
        resources = COSDictionary()
        sub = COSDictionary()
        sub.set_item(_N("Sh1"), entry)
        resources.set_item(_N("Shading"), sub)
        page.set_resources(resources)
        doc.save(str(path))
    finally:
        doc.close()


# ----------------------------------------------------- Python-side projection


def _arr_arity(a) -> str:  # type: ignore[no-untyped-def]
    return "null" if a is None else f"arr{a.size()}"


def _func_projection(shading) -> str:  # type: ignore[no-untyped-def]
    """Project /Function as the concrete class simple-name, or null/ERR. For a
    /Function array on a Type-1 shading the two sides differ (pypdfbox returns
    the raw COSArray, upstream raises) — that case is pinned in _PINNED."""
    try:
        f = shading.get_function()
    except Exception as e:  # noqa: BLE001
        return f"ERR:{_java_exc(e)}"
    if f is None:
        return "null"
    return type(f).__name__


def _java_exc(exc: Exception) -> str:
    if isinstance(exc, OSError):
        return "IOException"
    return type(exc).__name__


def _python_line(case_dir: Path, name: str) -> str:
    from pypdfbox.pdmodel.graphics.shading.pd_shading_type1 import PDShadingType1
    from pypdfbox.pdmodel.graphics.shading.pd_shading_type2 import PDShadingType2
    from pypdfbox.pdmodel.graphics.shading.pd_shading_type3 import PDShadingType3

    pdf = case_dir / f"{name}.pdf"
    prefix = f"CASE {name} "
    try:
        doc = PDDocument.load(str(pdf))
    except Exception as e:  # noqa: BLE001
        return prefix + (
            f"type=ERR class=ERR:{_java_exc(e)} coords=ERR domain=ERR "
            f"extend=ERR matrix=ERR function=ERR"
        )
    try:
        page = doc.get_page(0)
        resources = page.get_resources()
        try:
            shading = resources.get_shading(_N("Sh1"))
        except Exception as e:  # noqa: BLE001
            return prefix + (
                f"type=ERR class=ERR:{_java_exc(e)} coords=ERR domain=ERR "
                f"extend=ERR matrix=ERR function=ERR"
            )
        if shading is None:
            return prefix + (
                "type=null class=null coords=null domain=null extend=null "
                "matrix=null function=null"
            )
        try:
            t = str(shading.get_shading_type())
        except Exception:  # noqa: BLE001
            t = "ERR"

        if isinstance(shading, (PDShadingType3, PDShadingType2)):
            coords = _arr_arity(shading.get_coords())
            domain = _arr_arity(shading.get_domain())
            extend = _arr_arity(shading.get_extend())
            matrix = "n/a"
        elif isinstance(shading, PDShadingType1):
            coords = "n/a"
            domain = _arr_arity(shading.get_domain())
            extend = "n/a"
            # get_matrix() returns the raw COSArray or None; pin the
            # absent case (upstream getMatrix never returns null).
            matrix = "null" if shading.get_matrix() is None else "ok"
        else:
            coords = domain = extend = matrix = "n/a"

        return prefix + (
            f"type={t} class={type(shading).__name__} coords={coords} "
            f"domain={domain} extend={extend} matrix={matrix} "
            f"function={_func_projection(shading)}"
        )
    finally:
        doc.close()


# --------------------------------------------------------------------- pins

# Defensible divergence 1 — /Matrix absent. Upstream PDShadingType1.getMatrix()
# delegates to Matrix.createMatrix(base) which returns a fresh identity Matrix
# for an absent / short / non-numeric /Matrix (never null). pypdfbox's
# get_matrix() returns the raw COSArray or None (no typed Matrix port for the
# shading surface yet — the renderer's _shading_matrix applies the identity
# fallback at the call site). So for an absent /Matrix the Java probe reports
# matrix=ok while pypdfbox reports matrix=null. The Matrix-vs-COSArray return
# type is a util-module concern outside this agent's zone — pinned both-sides.
# See CHANGES.md wave 1538.
_MATRIX_LENIENCY = (
    "pypdfbox PDShadingType1.get_matrix returns the raw COSArray or None where "
    "upstream getMatrix() returns a typed Matrix (identity fallback, never "
    "null); util-module Matrix port out of scope — pinned."
)

# Defensible divergence 2 — /Function array. Upstream PDShading.getFunction()
# routes any non-null /Function (including a COSArray) through
# PDFunction.create, which for a COSArray yields a PDFunctionArrayBased wrapper
# class. pypdfbox's get_function() returns the raw COSArray for the array form
# (callers use get_functions_array() for per-component access). Different
# concrete class name; pinned both-sides. See CHANGES.md wave 1538.
_FUNCTION_ARRAY_LENIENCY = (
    "pypdfbox get_function returns the raw COSArray for a /Function array where "
    "upstream wraps it via PDFunction.create; per-component access is via "
    "get_functions_array() — pinned."
)


def _matrix_pin(name: str, *, cls: str, domain: str, function: str) -> tuple[str, str, str]:
    base = (
        f"CASE {name} type=1 class={cls} coords=n/a domain={domain} "
        f"extend=n/a matrix={{m}} function={function}"
    )
    return (base.format(m="null"), base.format(m="ok"), _MATRIX_LENIENCY)


# name -> (python_line, java_line, reason)
_PINNED: dict[str, tuple[str, str, str]] = {
    # /Matrix absent → py null vs java ok.
    "t1_domain_missing": _matrix_pin(
        "t1_domain_missing", cls="PDShadingType1", domain="null", function="null"
    ),
    "t1_domain_short": _matrix_pin(
        "t1_domain_short", cls="PDShadingType1", domain="arr2", function="null"
    ),
    "t1_domain_not_array": _matrix_pin(
        "t1_domain_not_array", cls="PDShadingType1", domain="null", function="null"
    ),
    "t1_domain_non_numeric": _matrix_pin(
        "t1_domain_non_numeric",
        cls="PDShadingType1",
        domain="arr2",
        function="null",
    ),
    "t1_function_missing": _matrix_pin(
        "t1_function_missing", cls="PDShadingType1", domain="null", function="null"
    ),
    "t1_matrix_missing": _matrix_pin(
        "t1_matrix_missing", cls="PDShadingType1", domain="arr4", function="null"
    ),
    # /Function array on a Type-1 shading → upstream getFunction() routes the
    # COSArray through PDFunction.create, which rejects an array as a single
    # function and raises IOException (function=ERR:IOException). pypdfbox's
    # get_function() instead returns the raw COSArray (callers use
    # get_functions_array() for per-component access). /Matrix also absent here
    # (py null vs java ok identity fallback). Both legs pinned both-sides.
    "t1_function_array": (
        "CASE t1_function_array type=1 class=PDShadingType1 coords=n/a "
        "domain=null extend=n/a matrix=null function=COSArray",
        "CASE t1_function_array type=1 class=PDShadingType1 coords=n/a "
        "domain=null extend=n/a matrix=ok function=ERR:IOException",
        _FUNCTION_ARRAY_LENIENCY,
    ),
}


# --------------------------------------------------------------------- test


@requires_oracle
def test_axial_radial_shading_fuzz_matches_pdfbox(tmp_path: Path) -> None:
    """Every mutated Type-1/2/3 shading dict projects identically through the
    typed geometry / function accessors on pypdfbox and Apache PDFBox 3.0.7:
    same resolved type, same concrete class, same coords / domain / extend
    arity, same matrix presence, same function class. Divergences are pinned
    explicitly in ``_PINNED`` (with a matching CHANGES.md row)."""
    corpus = _cases()
    for name, entry in corpus.items():
        _write_case_pdf(tmp_path / f"{name}.pdf", entry)
    (tmp_path / "manifest.txt").write_text(
        "\n".join(corpus) + "\n", encoding="utf-8"
    )

    raw = run_probe_text("AxialRadialShadingFuzzProbe", str(tmp_path))
    java_lines = [ln for ln in raw.splitlines() if ln.startswith("CASE ")]
    assert len(java_lines) == len(corpus), (
        f"probe emitted {len(java_lines)} lines for {len(corpus)} cases:\n{raw}"
    )
    java_by_name = {ln.split(" ", 2)[1]: ln for ln in java_lines}

    mismatches: list[str] = []
    for name in corpus:
        java = java_by_name.get(name, "<MISSING>")
        py = _python_line(tmp_path, name)
        if name in _PINNED:
            py_exp, java_exp, _reason = _PINNED[name]
            if py == py_exp and java == java_exp:
                continue
        if py != java:
            mismatches.append(f"  {name}\n    java: {java}\n    py  : {py}")

    assert not mismatches, "axial/radial shading fuzz divergences:\n" + "\n".join(
        mismatches
    )
