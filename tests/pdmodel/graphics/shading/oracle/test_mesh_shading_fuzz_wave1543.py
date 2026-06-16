"""Differential fuzz audit for the dictionary-accessor surface of the mesh
shading types — ``PDShadingType4`` (free-form Gouraud triangle),
``PDShadingType5`` (lattice-form Gouraud triangle), ``PDShadingType6`` (Coons
patch), ``PDShadingType7`` (tensor-product patch) — vs Apache PDFBox 3.0.7
(wave 1543, agent D).

Distinct angle from ``test_axial_radial_shading_fuzz_wave1538`` (Types 1/2/3
coords / domain / extend / matrix) and from the geometry-dump probes
(``MeshGouraudFlagProbe`` / ``PatchMeshDecodeProbe`` decode triangles /
patches): this audit drives the *mesh metadata accessors* that every decode
path reads first and that callers consume to validate a stream before
rasterizing — ``get_shading_type`` / ``get_bits_per_coordinate`` /
``get_bits_per_component`` / ``get_bits_per_flag`` / ``get_vertices_per_row``
(Type 5) / ``get_decode_for_parameter`` / ``get_number_of_color_components`` /
``get_background`` / ``get_b_box`` / ``get_anti_alias`` / ``get_function``.

Upstream contracts (confirmed by decompiling PDFBox 3.0.7):

* ``getBitsPer*`` delegate to ``COSDictionary.getInt(name)`` which defaults to
  ``-1`` (absent / non-int) with NO legal-value validation — an invalid
  ``/BitsPerCoordinate`` such as 7 or 64 is returned verbatim.
* ``getDecodeForParameter(p)`` returns a non-null ``PDRange`` when
  ``decode.size() >= 2*p + 1`` (NOT ``2*p + 2``). The range is lazy:
  ``getMin()`` reads index ``2*p``, ``getMax()`` reads ``2*p + 1``. So at the
  exact boundary ``size == 2*p + 1`` the range is non-null and ``getMin()``
  works but ``getMax()`` throws ``IndexOutOfBoundsException``. pypdfbox's
  ``get_decode_for_parameter`` eagerly returns a ``(min, max)`` tuple and
  requires ``size >= 2*p + 2`` (returns ``None`` otherwise), so it reports
  ``null`` where upstream reports the "min-ok / max-throws" boundary. Pinned.
* ``getBBox()`` builds a ``PDRectangle`` from ANY non-null ``/BBox`` COSArray
  (no size-4 guard); a non-array ``/BBox`` yields ``null``.
* ``getBackground()`` / the decode array use ``getCOSArray(name)``: the stored
  COSArray or ``null`` (absent / wrong type) — no default materialization.

Both sides are driven on the SAME bytes: a one-page PDF per case (mutated
shading dict / stream installed as resource ``/Shading/Sh1``) plus a
``manifest.txt`` are written to a tmp dir. The Java probe
(``oracle/probes/MeshShadingFuzzProbe.java``) projects a stable framed line per
case; this module reads the same files and projects the identical grammar
through pypdfbox, then asserts line-for-line.

Line grammar (one per case, manifest order)::

    CASE <name> type=<n|ERR> class=<simpleName|null> bpc=<n> bcomp=<n>
        bflag=<n> vpr=<n|n/a> ncc=<n|ERR> dec=<arr_n|null>
        d0=<okMM|min|null|ERR> dc=<okMM|min|null|ERR> bg=<arr_n|null>
        bbox=<rect|null> aa=<true|false> function=<simpleName|null|ERR>

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
    COSStream,
    COSString,
)
from pypdfbox.pdmodel.pd_document import PDDocument
from tests.oracle.harness import requires_oracle, run_probe_text

_N = COSName.get_pdf_name

_DECODE = _N("Decode")
_BITS_PER_FLAG = _N("BitsPerFlag")


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


def _gray() -> COSName:
    return _N("DeviceGray")


def _stream(entries: COSDictionary, body: bytes = b"\x00\x00\x00\x00") -> COSStream:
    """A COSStream carrying the same /entries plus a small body. Used so the
    shading is backed by a real stream object (mesh shadings are stream-based
    upstream) while we only exercise the dictionary-accessor surface."""
    s = COSStream()
    for key in entries.key_set():
        s.set_item(key, entries.get_item(key))
    with s.create_output_stream() as out:
        out.write(body)
    return s


# --------------------------------------------------------------------- corpus


def _base4(**over: object) -> COSDictionary:
    d = COSDictionary()
    d.set_int(_N("ShadingType"), 4)
    d.set_item(_N("ColorSpace"), _rgb())
    d.set_int(_N("BitsPerCoordinate"), 8)
    d.set_int(_N("BitsPerComponent"), 8)
    d.set_int(_N("BitsPerFlag"), 8)
    d.set_item(_N("Decode"), _nums(0, 1, 0, 1, 0, 1, 0, 1, 0, 1))
    return d


def _cases() -> dict[str, COSStream]:
    cases: dict[str, COSStream] = {}

    def add(name: str, d: COSDictionary, body: bytes = b"\x00\x00\x00\x00") -> None:
        cases[name] = _stream(d, body)

    # ===== Type 4 free-form Gouraud =======================================
    d = _base4()
    add("t4_well_formed", d)

    # /BitsPerCoordinate not a legal value (legal: 1,2,4,8,12,16,24,32).
    d = _base4()
    d.set_int(_N("BitsPerCoordinate"), 7)
    add("t4_bpc_illegal_7", d)

    d = _base4()
    d.set_int(_N("BitsPerCoordinate"), 64)
    add("t4_bpc_illegal_64", d)

    d = _base4()
    d.remove_item(_N("BitsPerCoordinate"))
    add("t4_bpc_missing", d)

    # /BitsPerComponent not legal (legal: 1,2,4,8,12,16).
    d = _base4()
    d.set_int(_N("BitsPerComponent"), 3)
    add("t4_bcomp_illegal_3", d)

    d = _base4()
    d.remove_item(_N("BitsPerComponent"))
    add("t4_bcomp_missing", d)

    # /BitsPerFlag not legal (legal: 2,4,8).
    d = _base4()
    d.set_int(_N("BitsPerFlag"), 3)
    add("t4_bflag_illegal_3", d)

    d = _base4()
    d.remove_item(_N("BitsPerFlag"))
    add("t4_bflag_missing", d)

    # /BitsPerCoordinate not an int (string).
    d = _base4()
    d.set_item(_N("BitsPerCoordinate"), COSString("8"))
    add("t4_bpc_not_int", d)

    # /Decode missing entirely.
    d = _base4()
    d.remove_item(_N("Decode"))
    add("t4_decode_missing", d)

    # /Decode not an array.
    d = _base4()
    d.set_item(_N("Decode"), COSString("0 1 0 1"))
    add("t4_decode_not_array", d)

    # /Decode too short for any colour range (only xy: 4 entries → d0 ok,
    # dc=param2 needs size>=6).
    d = _base4()
    d.set_item(_N("Decode"), _nums(0, 1, 0, 1))
    add("t4_decode_xy_only", d)

    # /Decode boundary: size == 2*0 + 1 == 1 → upstream d0 non-null,
    # getMin ok, getMax throws (boundary); pypdfbox returns None. Pinned.
    d = _base4()
    d.set_item(_N("Decode"), _nums(0))
    add("t4_decode_len1_boundary", d)

    # /Decode boundary for param2: size == 2*2 + 1 == 5 → upstream dc non-null,
    # getMax throws; pypdfbox None. d0 fully ok (size>=4). Pinned.
    d = _base4()
    d.set_item(_N("Decode"), _nums(0, 1, 0, 1, 0))
    add("t4_decode_len5_boundary", d)

    # /Decode reversed (max < min) — both sides return the pair verbatim.
    d = _base4()
    d.set_item(_N("Decode"), _nums(1, 0, 1, 0, 1, 0, 1, 0, 1, 0))
    add("t4_decode_reversed", d)

    # /Decode entry non-numeric at the hi slot (index 1) → upstream getMin ok,
    # getMax casts to COSNumber and throws ClassCastException; pypdfbox returns
    # None (isinstance hi COSNumber fails). Pinned.
    d = _base4()
    d.set_item(_N("Decode"), _arr(COSFloat(0.0), COSName.get_pdf_name("x"),
                                  COSFloat(0.0), COSFloat(1.0),
                                  COSFloat(0.0), COSFloat(1.0)))
    add("t4_decode_hi_non_numeric", d)

    # No /Function: ncc derives from colour space (RGB → 3).
    d = _base4()
    add("t4_no_function_rgb", d)

    # No /Function, Gray colour space → ncc 1.
    d = _base4()
    d.set_item(_N("ColorSpace"), _gray())
    add("t4_no_function_gray", d)

    # /Function present → ncc fixed at 1 regardless of colour space.
    d = _base4()
    d.set_item(_N("Function"), _identity_func())
    add("t4_with_function", d)

    # /Background present (numeric 3-array).
    d = _base4()
    d.set_item(_N("Background"), _nums(0.5, 0.5, 0.5))
    add("t4_background", d)

    # /Background not an array.
    d = _base4()
    d.set_item(_N("Background"), COSInteger(3))
    add("t4_background_not_array", d)

    # /BBox valid 4-array.
    d = _base4()
    d.set_item(_N("BBox"), _nums(0, 0, 100, 100))
    add("t4_bbox_valid", d)

    # /BBox short (2-array) → upstream getBBox builds a PDRectangle anyway
    # (no size-4 guard) so bbox=rect; the raw COSArray is non-null so this is
    # NOT a divergence at the getBBox()/get_b_box level. (get_b_box_rect would
    # diverge but is not on this surface.)
    d = _base4()
    d.set_item(_N("BBox"), _nums(0, 0))
    add("t4_bbox_short", d)

    # /BBox not an array → getCOSArray null → getBBox null.
    d = _base4()
    d.set_item(_N("BBox"), COSString("0 0 1 1"))
    add("t4_bbox_not_array", d)

    # /AntiAlias true.
    d = _base4()
    d.set_item(_N("AntiAlias"), COSBoolean.TRUE)
    add("t4_antialias_true", d)

    # /AntiAlias non-boolean (int) → getBoolean default false on both.
    d = _base4()
    d.set_item(_N("AntiAlias"), COSInteger(1))
    add("t4_antialias_not_bool", d)

    # ===== Type 5 lattice-form Gouraud ====================================
    def _base5(**_: object) -> COSDictionary:
        d = COSDictionary()
        d.set_int(_N("ShadingType"), 5)
        d.set_item(_N("ColorSpace"), _rgb())
        d.set_int(_N("BitsPerCoordinate"), 8)
        d.set_int(_N("BitsPerComponent"), 8)
        d.set_int(_N("VerticesPerRow"), 2)
        d.set_item(_N("Decode"), _nums(0, 1, 0, 1, 0, 1, 0, 1, 0, 1))
        return d

    add("t5_well_formed", _base5())

    d = _base5()
    d.remove_item(_N("VerticesPerRow"))
    add("t5_vpr_missing", d)

    d = _base5()
    d.set_int(_N("VerticesPerRow"), 0)
    add("t5_vpr_zero", d)

    d = _base5()
    d.set_int(_N("VerticesPerRow"), -3)
    add("t5_vpr_negative", d)

    d = _base5()
    d.set_item(_N("VerticesPerRow"), COSString("2"))  # not an int
    add("t5_vpr_not_int", d)

    # Type 5 has no /BitsPerFlag — bflag should be -1 on both sides.
    d = _base5()
    add("t5_no_bflag", d)

    # ShadingType mismatch: stream says 5 but the typed accessor still works;
    # this projects the resolved class via PDShading.create dispatch.
    d = _base5()
    d.set_int(_N("VerticesPerRow"), 4)
    add("t5_vpr_four", d)

    # ===== Type 6 Coons patch =============================================
    def _base6(**_: object) -> COSDictionary:
        d = COSDictionary()
        d.set_int(_N("ShadingType"), 6)
        d.set_item(_N("ColorSpace"), _rgb())
        d.set_int(_N("BitsPerCoordinate"), 16)
        d.set_int(_N("BitsPerComponent"), 8)
        d.set_int(_N("BitsPerFlag"), 8)
        d.set_item(_N("Decode"), _nums(0, 1, 0, 1, 0, 1, 0, 1, 0, 1))
        return d

    add("t6_well_formed", _base6())

    d = _base6()
    d.set_int(_N("BitsPerFlag"), 5)  # illegal flag value (legal 2,4,8)
    add("t6_bflag_illegal", d)

    d = _base6()
    d.remove_item(_N("BitsPerFlag"))
    add("t6_bflag_missing", d)

    d = _base6()
    d.set_item(_N("Function"), _identity_func())
    add("t6_with_function", d)

    d = _base6()
    d.set_item(_N("Decode"), _nums(0, 1))  # too short for any colour comp
    add("t6_decode_short", d)

    # ===== Type 7 tensor-product patch ====================================
    def _base7(**_: object) -> COSDictionary:
        d = COSDictionary()
        d.set_int(_N("ShadingType"), 7)
        d.set_item(_N("ColorSpace"), _rgb())
        d.set_int(_N("BitsPerCoordinate"), 16)
        d.set_int(_N("BitsPerComponent"), 8)
        d.set_int(_N("BitsPerFlag"), 8)
        d.set_item(_N("Decode"), _nums(0, 1, 0, 1, 0, 1, 0, 1, 0, 1))
        return d

    add("t7_well_formed", _base7())

    d = _base7()
    d.set_int(_N("BitsPerCoordinate"), 0)  # illegal
    add("t7_bpc_zero", d)

    d = _base7()
    d.set_item(_N("Function"), _identity_func())
    add("t7_with_function", d)

    d = _base7()
    d.set_item(_N("Background"), _nums(0.1, 0.2, 0.3))
    d.set_item(_N("BBox"), _nums(0, 0, 50, 50))
    d.set_item(_N("AntiAlias"), COSBoolean.TRUE)
    add("t7_full_optionals", d)

    return cases


def _write_case_pdf(path: Path, entry: COSStream) -> None:
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


def _decode_param(shading, param: int) -> str:  # type: ignore[no-untyped-def]
    """Project pypdfbox get_decode_for_parameter into the same grammar as the
    Java probe. pypdfbox eagerly returns a (min, max) tuple or None, so it can
    only emit ``okMM`` or ``null`` — the ``min`` (getMin-ok / getMax-throws)
    boundary state is upstream-only and pinned."""
    try:
        rng = shading.get_decode_for_parameter(param)
    except Exception as e:  # noqa: BLE001
        return f"ERR:{_java_exc(e)}"
    return "null" if rng is None else "okMM"


def _ncc(shading) -> str:  # type: ignore[no-untyped-def]
    try:
        return str(shading.get_number_of_color_components())
    except Exception as e:  # noqa: BLE001
        return f"ERR:{_java_exc(e)}"


def _func_projection(shading) -> str:  # type: ignore[no-untyped-def]
    try:
        f = shading.get_function()
    except Exception as e:  # noqa: BLE001
        return f"ERR:{_java_exc(e)}"
    if f is None:
        return "null"
    return type(f).__name__


def _bbox_projection(shading) -> str:  # type: ignore[no-untyped-def]
    """Mirror upstream getBBox(): a PDRectangle from any non-null /BBox
    COSArray, else null. pypdfbox get_b_box returns the raw COSArray (or None
    for absent / non-array), which is rect-presence-equivalent."""
    try:
        v = shading.get_b_box()
    except Exception as e:  # noqa: BLE001
        return f"ERR:{_java_exc(e)}"
    return "null" if v is None else "rect"


def _bits_per_flag(shading) -> int:  # type: ignore[no-untyped-def]
    # Project the raw COS int uniformly (Type 5 has no typed accessor / no flag
    # field; the Java probe reads getCOSObject().getInt the same way).
    return shading.get_cos_object().get_int(_BITS_PER_FLAG)


def _java_exc(exc: Exception) -> str:
    if isinstance(exc, OSError):
        return "IOException"
    return type(exc).__name__


def _python_line(case_dir: Path, name: str) -> str:
    from pypdfbox.pdmodel.graphics.shading.pd_shading_type5 import PDShadingType5

    pdf = case_dir / f"{name}.pdf"
    prefix = f"CASE {name} "
    err = (
        "type=ERR class=ERR:{exc} bpc=ERR bcomp=ERR bflag=ERR vpr=ERR ncc=ERR "
        "dec=ERR d0=ERR dc=ERR bg=ERR bbox=ERR aa=ERR function=ERR"
    )
    try:
        doc = PDDocument.load(str(pdf))
    except Exception as e:  # noqa: BLE001
        return prefix + err.format(exc=_java_exc(e))
    try:
        page = doc.get_page(0)
        resources = page.get_resources()
        try:
            shading = resources.get_shading(_N("Sh1"))
        except Exception as e:  # noqa: BLE001
            return prefix + err.format(exc=_java_exc(e))
        if shading is None:
            return prefix + (
                "type=null class=null bpc=n/a bcomp=n/a bflag=n/a vpr=n/a "
                "ncc=n/a dec=null d0=null dc=null bg=null bbox=null aa=false "
                "function=null"
            )
        try:
            t = str(shading.get_shading_type())
        except Exception:  # noqa: BLE001
            t = "ERR"

        vpr = (
            str(shading.get_vertices_per_row())
            if isinstance(shading, PDShadingType5)
            else "n/a"
        )

        cos = shading.get_cos_object()
        dec_raw = cos.get_dictionary_object(_DECODE)
        dec = _arr_arity(dec_raw if isinstance(dec_raw, COSArray) else None)

        return prefix + (
            f"type={t} class={type(shading).__name__} "
            f"bpc={shading.get_bits_per_coordinate()} "
            f"bcomp={shading.get_bits_per_component()} "
            f"bflag={_bits_per_flag(shading)} "
            f"vpr={vpr} "
            f"ncc={_ncc(shading)} "
            f"dec={dec} "
            f"d0={_decode_param(shading, 0)} "
            f"dc={_decode_param(shading, 2)} "
            f"bg={_arr_arity(shading.get_background())} "
            f"bbox={_bbox_projection(shading)} "
            f"aa={'true' if shading.get_anti_alias() else 'false'} "
            f"function={_func_projection(shading)}"
        )
    finally:
        doc.close()


# --------------------------------------------------------------------- pins

# Defensible divergence — getDecodeForParameter off-by-one + lazy PDRange.
# Upstream returns a non-null lazy PDRange when decode.size() >= 2*p + 1;
# getMin() reads index 2*p, getMax() reads 2*p + 1. So at the exact boundary
# size == 2*p + 1 (or when the hi slot is non-numeric) the range is non-null
# and getMin succeeds while getMax throws — the Java probe records "min".
# pypdfbox's get_decode_for_parameter eagerly returns a (min, max) tuple and
# requires size >= 2*p + 2 with both slots COSNumber, returning None otherwise,
# so it records "null". The eager-vs-lazy contract is the rendering cluster's
# concern (the decode is consumed to build a concrete float range); pinned
# both-sides. See CHANGES.md wave 1543.
_DECODE_BOUNDARY = (
    "pypdfbox get_decode_for_parameter eagerly returns a (min, max) tuple "
    "requiring size>=2*p+2 (None otherwise), where upstream returns a lazy "
    "PDRange when size>=2*p+1 whose getMax() throws at the boundary — eager "
    "vs lazy decode range; pinned."
)


def _pin(name: str, py_line: str, java_line: str) -> tuple[str, str, str]:
    return (
        f"CASE {name} {py_line}",
        f"CASE {name} {java_line}",
        _DECODE_BOUNDARY,
    )


# name -> (python_line, java_line, reason)
_PINNED: dict[str, tuple[str, str, str]] = {
    # /Decode length 1 → d0 boundary. py null / java min.
    "t4_decode_len1_boundary": _pin(
        "t4_decode_len1_boundary",
        "type=4 class=PDShadingType4 bpc=8 bcomp=8 bflag=8 vpr=n/a ncc=3 "
        "dec=arr1 d0=null dc=null bg=null bbox=null aa=false function=null",
        "type=4 class=PDShadingType4 bpc=8 bcomp=8 bflag=8 vpr=n/a ncc=3 "
        "dec=arr1 d0=min dc=null bg=null bbox=null aa=false function=null",
    ),
    # /Decode length 5 → dc (param 2) boundary; d0 fully ok. py dc null /
    # java dc min.
    "t4_decode_len5_boundary": _pin(
        "t4_decode_len5_boundary",
        "type=4 class=PDShadingType4 bpc=8 bcomp=8 bflag=8 vpr=n/a ncc=3 "
        "dec=arr5 d0=okMM dc=null bg=null bbox=null aa=false function=null",
        "type=4 class=PDShadingType4 bpc=8 bcomp=8 bflag=8 vpr=n/a ncc=3 "
        "dec=arr5 d0=okMM dc=min bg=null bbox=null aa=false function=null",
    ),
    # /Decode hi slot (index 1) non-numeric → d0 getMin ok, getMax cast throws.
    # py null / java min. dc (param2) is fully numeric so okMM on both.
    "t4_decode_hi_non_numeric": _pin(
        "t4_decode_hi_non_numeric",
        "type=4 class=PDShadingType4 bpc=8 bcomp=8 bflag=8 vpr=n/a ncc=3 "
        "dec=arr6 d0=null dc=okMM bg=null bbox=null aa=false function=null",
        "type=4 class=PDShadingType4 bpc=8 bcomp=8 bflag=8 vpr=n/a ncc=3 "
        "dec=arr6 d0=min dc=okMM bg=null bbox=null aa=false function=null",
    ),
}


# --------------------------------------------------------------------- test


@requires_oracle
def test_mesh_shading_fuzz_matches_pdfbox(tmp_path: Path) -> None:
    """Every mutated Type-4/5/6/7 mesh-shading dict projects identically
    through the metadata accessors on pypdfbox and Apache PDFBox 3.0.7: same
    resolved type, same concrete class, same bits-per-* (no legal-value
    validation either side), same vertices-per-row, same colour-component
    count, same decode arity / per-parameter resolution, same background /
    bbox presence, same anti-alias, same function class. Divergences are
    pinned explicitly in ``_PINNED`` (with a matching CHANGES.md row)."""
    corpus = _cases()
    for name, entry in corpus.items():
        _write_case_pdf(tmp_path / f"{name}.pdf", entry)
    (tmp_path / "manifest.txt").write_text(
        "\n".join(corpus) + "\n", encoding="utf-8"
    )

    raw = run_probe_text("MeshShadingFuzzProbe", str(tmp_path))
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

    assert not mismatches, "mesh shading fuzz divergences:\n" + "\n".join(
        mismatches
    )
