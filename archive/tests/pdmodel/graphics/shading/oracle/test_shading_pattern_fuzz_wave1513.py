"""Differential fuzz audit for shading + pattern dictionary construction
leniency vs Apache PDFBox 3.0.7 (wave 1513, agent D).

Complements the well-formed shading/pattern parity suites — none of which
exercise the MALFORMED dictionary subset this audit targets:

* ``PDShading.create`` (types 1 function-based, 2 axial, 3 radial, 4-7 mesh):
  ``/ShadingType`` missing / unknown / out-of-range; ``/ColorSpace`` missing /
  bad; ``/Coords`` wrong arity (axial 4, radial 6); ``/Domain`` / ``/Extend`` /
  ``/Function`` / ``/Background`` / ``/AntiAlias`` malformed; mesh
  ``/BitsPerCoordinate`` ``/BitsPerComponent`` ``/BitsPerFlag`` ``/Decode``
  corners.
* ``PDAbstractPattern.create`` (tiling type 1 / shading type 2):
  ``/PatternType`` missing / unknown; tiling ``/PaintType`` ``/TilingType``
  ``/BBox`` ``/XStep`` ``/YStep`` ``/Resources`` malformed; shading-pattern
  ``/Shading`` + ``/Matrix`` bad.

Both sides are driven on the SAME bytes: the corpus builder writes a one-page
PDF per case (the mutated shading dict installed as resource ``/Shading/Sh1``,
or the mutated pattern dict as ``/Pattern/P1``) plus a ``manifest.txt`` into a
tmp dir. The Java probe (``oracle/probes/ShadingPatternFuzzProbe.java``) loads
each ``<case>.pdf`` and projects a stable framed line through
``PDResources.getShading`` / ``getPattern``; this module reads the exact same
files and projects the identical grammar through pypdfbox, then asserts
line-for-line parity.

Line grammar (one per case, manifest order)::

    CASE <name> shadingType=<n|ERR> class=<simpleName|null|ERR>
        cs=<name|ERR> extra=<key-projection|ERR>

Java is ground truth: a real divergence is a production fix in
``pypdfbox/pdmodel/graphics/shading/`` (or the pattern module); a defensible
divergence is pinned in ``_PINNED`` with a matching CHANGES.md row.
"""

from __future__ import annotations

import math
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

# --------------------------------------------------------------------- helpers

_N = COSName.get_pdf_name


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


def _device_rgb() -> COSName:
    return _N("DeviceRGB")


def _mesh_stream(shading_type: int, **entries: COSBase) -> COSStream:
    s = COSStream()
    s.set_int(_N("ShadingType"), shading_type)
    for k, v in entries.items():
        s.set_item(_N(k), v)
    out = s.create_output_stream()
    out.write(b"\x00" * 16)
    out.close()
    return s


# --------------------------------------------------------------------- corpus


def _shading_cases() -> dict[str, COSDictionary]:
    cases: dict[str, COSDictionary] = {}

    def sh(name: str, d: COSDictionary) -> None:
        cases[f"shading_{name}"] = d

    # --- /ShadingType dispatch corners -------------------------------------
    d = COSDictionary()
    sh("type_missing", d)

    d = COSDictionary()
    d.set_int(_N("ShadingType"), 0)
    sh("type_zero", d)

    d = COSDictionary()
    d.set_int(_N("ShadingType"), 8)
    sh("type_out_of_range_high", d)

    d = COSDictionary()
    d.set_int(_N("ShadingType"), -1)
    sh("type_negative", d)

    d = COSDictionary()
    d.set_name(_N("ShadingType"), "Axial")
    sh("type_name_not_int", d)

    d = COSDictionary()
    d.set_float(_N("ShadingType"), 2.0)
    sh("type_real_2", d)

    # --- Type 1 function-based ---------------------------------------------
    d = COSDictionary()
    d.set_int(_N("ShadingType"), 1)
    d.set_item(_N("ColorSpace"), _device_rgb())
    d.set_item(_N("Domain"), _nums(0, 1, 0, 1))
    d.set_item(_N("Function"), _identity_func())
    sh("type1_well_formed", d)

    d = COSDictionary()
    d.set_int(_N("ShadingType"), 1)
    sh("type1_bare", d)

    d = COSDictionary()
    d.set_int(_N("ShadingType"), 1)
    d.set_item(_N("ColorSpace"), _device_rgb())
    d.set_item(_N("Domain"), _nums(0, 1))  # should be 4 for type 1
    sh("type1_domain_short", d)

    # --- Type 2 axial -------------------------------------------------------
    d = COSDictionary()
    d.set_int(_N("ShadingType"), 2)
    d.set_item(_N("ColorSpace"), _device_rgb())
    d.set_item(_N("Coords"), _nums(0, 0, 100, 0))
    d.set_item(_N("Function"), _identity_func())
    sh("type2_well_formed", d)

    d = COSDictionary()
    d.set_int(_N("ShadingType"), 2)
    d.set_item(_N("ColorSpace"), _device_rgb())
    d.set_item(_N("Coords"), _nums(0, 0))  # axial needs 4
    d.set_item(_N("Function"), _identity_func())
    sh("type2_coords_short", d)

    d = COSDictionary()
    d.set_int(_N("ShadingType"), 2)
    d.set_item(_N("ColorSpace"), _device_rgb())
    sh("type2_no_coords_no_function", d)

    d = COSDictionary()
    d.set_int(_N("ShadingType"), 2)
    d.set_item(_N("Coords"), _nums(0, 0, 1, 1))
    d.set_item(_N("Function"), _identity_func())
    sh("type2_no_colorspace", d)

    d = COSDictionary()
    d.set_int(_N("ShadingType"), 2)
    d.set_name(_N("ColorSpace"), "Bogus")
    d.set_item(_N("Coords"), _nums(0, 0, 1, 1))
    sh("type2_bad_colorspace", d)

    d = COSDictionary()
    d.set_int(_N("ShadingType"), 2)
    d.set_item(_N("ColorSpace"), _device_rgb())
    d.set_item(_N("Coords"), _nums(0, 0, 1, 1))
    d.set_item(_N("Extend"), _arr(COSBoolean.TRUE, COSBoolean.FALSE))
    d.set_item(_N("Domain"), _nums(0.2, 0.8))
    d.set_item(_N("Function"), _identity_func())
    sh("type2_extend_domain", d)

    d = COSDictionary()
    d.set_int(_N("ShadingType"), 2)
    d.set_item(_N("ColorSpace"), _device_rgb())
    d.set_item(_N("Coords"), _nums(0, 0, 1, 1))
    d.set_item(_N("Extend"), _arr(COSBoolean.TRUE))  # should be 2
    d.set_item(_N("Function"), _identity_func())
    sh("type2_extend_short", d)

    d = COSDictionary()
    d.set_int(_N("ShadingType"), 2)
    d.set_item(_N("ColorSpace"), _device_rgb())
    d.set_item(_N("Coords"), _nums(0, 0, 1, 1))
    d.set_item(_N("Function"), _arr(_identity_func(), _identity_func(), _identity_func()))
    d.set_item(_N("Background"), _nums(0.5, 0.5, 0.5))
    d.set_boolean(_N("AntiAlias"), True)
    sh("type2_func_array_bg_aa", d)

    # --- Type 3 radial ------------------------------------------------------
    d = COSDictionary()
    d.set_int(_N("ShadingType"), 3)
    d.set_item(_N("ColorSpace"), _device_rgb())
    d.set_item(_N("Coords"), _nums(0, 0, 0, 0, 0, 50))
    d.set_item(_N("Function"), _identity_func())
    sh("type3_well_formed", d)

    d = COSDictionary()
    d.set_int(_N("ShadingType"), 3)
    d.set_item(_N("ColorSpace"), _device_rgb())
    d.set_item(_N("Coords"), _nums(0, 0, 100, 0))  # radial needs 6
    d.set_item(_N("Function"), _identity_func())
    sh("type3_coords_axial_arity", d)

    d = COSDictionary()
    d.set_int(_N("ShadingType"), 3)
    d.set_item(_N("ColorSpace"), _N("DeviceGray"))
    d.set_item(_N("Coords"), _nums(0, 0, 0, 0, 0, 50))
    d.set_item(_N("AntiAlias"), COSString("yes"))  # AntiAlias not a boolean
    d.set_item(_N("Function"), _identity_func())
    sh("type3_antialias_not_bool", d)

    # --- Type 4-7 mesh ------------------------------------------------------
    sh(
        "type4_well_formed",
        _mesh_stream(
            4,
            ColorSpace=_device_rgb(),
            BitsPerCoordinate=COSInteger(16),
            BitsPerComponent=COSInteger(8),
            BitsPerFlag=COSInteger(8),
            Decode=_nums(0, 1, 0, 1, 0, 1, 0, 1, 0, 1),
        ),
    )

    sh(
        "type5_well_formed",
        _mesh_stream(
            5,
            ColorSpace=_device_rgb(),
            BitsPerCoordinate=COSInteger(16),
            BitsPerComponent=COSInteger(8),
            VerticesPerRow=COSInteger(2),
            Decode=_nums(0, 1, 0, 1, 0, 1, 0, 1, 0, 1),
        ),
    )

    sh(
        "type6_well_formed",
        _mesh_stream(
            6,
            ColorSpace=_device_rgb(),
            BitsPerCoordinate=COSInteger(16),
            BitsPerComponent=COSInteger(8),
            BitsPerFlag=COSInteger(8),
            Decode=_nums(0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1),
        ),
    )

    sh(
        "type7_well_formed",
        _mesh_stream(
            7,
            ColorSpace=_device_rgb(),
            BitsPerCoordinate=COSInteger(32),
            BitsPerComponent=COSInteger(16),
            BitsPerFlag=COSInteger(8),
            Decode=_nums(0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1),
        ),
    )

    # mesh with missing bit-depth entries (factory must still construct)
    sh(
        "type4_missing_bits",
        _mesh_stream(4, ColorSpace=_device_rgb()),
    )

    # mesh declared as a PLAIN dictionary (no stream) — upstream constructs it
    d = COSDictionary()
    d.set_int(_N("ShadingType"), 4)
    d.set_item(_N("ColorSpace"), _device_rgb())
    d.set_int(_N("BitsPerCoordinate"), 16)
    d.set_int(_N("BitsPerComponent"), 8)
    d.set_int(_N("BitsPerFlag"), 8)
    d.set_item(_N("Decode"), _nums(0, 1, 0, 1, 0, 1, 0, 1, 0, 1))
    sh("type4_plain_dict_not_stream", d)

    d = COSDictionary()
    d.set_int(_N("ShadingType"), 6)
    d.set_item(_N("ColorSpace"), _device_rgb())
    sh("type6_plain_dict_not_stream", d)

    # mesh BitsPerCoordinate as a real / odd value
    sh(
        "type4_bpcoord_real",
        _mesh_stream(
            4,
            ColorSpace=_device_rgb(),
            BitsPerCoordinate=COSFloat(16.5),
            BitsPerComponent=COSInteger(8),
            BitsPerFlag=COSInteger(8),
        ),
    )

    # mesh Decode wrong arity
    sh(
        "type4_decode_short",
        _mesh_stream(
            4,
            ColorSpace=_device_rgb(),
            BitsPerCoordinate=COSInteger(16),
            BitsPerComponent=COSInteger(8),
            BitsPerFlag=COSInteger(8),
            Decode=_nums(0, 1),
        ),
    )

    return cases


def _pattern_cases() -> dict[str, COSDictionary]:
    cases: dict[str, COSDictionary] = {}

    def pat(name: str, d: COSDictionary) -> None:
        cases[f"pattern_{name}"] = d

    # --- /PatternType dispatch corners -------------------------------------
    d = COSDictionary()
    pat("type_missing", d)

    d = COSDictionary()
    d.set_int(_N("PatternType"), 0)
    pat("type_zero", d)

    d = COSDictionary()
    d.set_int(_N("PatternType"), 3)
    pat("type_unknown_high", d)

    d = COSDictionary()
    d.set_name(_N("PatternType"), "Tiling")
    pat("type_name_not_int", d)

    # --- tiling type 1 (must be a stream) ----------------------------------
    def _tiling_stream(**entries: COSBase) -> COSStream:
        s = COSStream()
        s.set_int(_N("PatternType"), 1)
        for k, v in entries.items():
            s.set_item(_N(k), v)
        out = s.create_output_stream()
        out.write(b"")
        out.close()
        return s

    pat(
        "tiling_well_formed",
        _tiling_stream(
            PaintType=COSInteger(1),
            TilingType=COSInteger(1),
            BBox=_nums(0, 0, 10, 10),
            XStep=COSFloat(10),
            YStep=COSFloat(10),
            Resources=COSDictionary(),
        ),
    )

    pat(
        "tiling_bare_stream",
        _tiling_stream(),
    )

    pat(
        "tiling_missing_bbox",
        _tiling_stream(
            PaintType=COSInteger(2),
            TilingType=COSInteger(2),
            XStep=COSFloat(5),
            YStep=COSFloat(5),
        ),
    )

    pat(
        "tiling_bbox_short",
        _tiling_stream(
            PaintType=COSInteger(1),
            TilingType=COSInteger(1),
            BBox=_nums(0, 0),
            XStep=COSFloat(10),
            YStep=COSFloat(10),
        ),
    )

    pat(
        "tiling_zero_steps",
        _tiling_stream(
            PaintType=COSInteger(1),
            TilingType=COSInteger(1),
            BBox=_nums(0, 0, 10, 10),
            XStep=COSFloat(0),
            YStep=COSFloat(0),
        ),
    )

    pat(
        "tiling_steps_not_number",
        _tiling_stream(
            PaintType=COSInteger(1),
            TilingType=COSInteger(1),
            BBox=_nums(0, 0, 10, 10),
            XStep=COSString("ten"),
            YStep=COSString("ten"),
        ),
    )

    pat(
        "tiling_resources_not_dict",
        _tiling_stream(
            PaintType=COSInteger(1),
            TilingType=COSInteger(1),
            BBox=_nums(0, 0, 10, 10),
            XStep=COSFloat(10),
            YStep=COSFloat(10),
            Resources=_nums(1, 2, 3),
        ),
    )

    pat(
        "tiling_paint_type_bad",
        _tiling_stream(
            PaintType=COSInteger(9),
            TilingType=COSInteger(1),
            BBox=_nums(0, 0, 10, 10),
            XStep=COSFloat(10),
            YStep=COSFloat(10),
        ),
    )

    # tiling declared as a plain dictionary (no stream)
    d = COSDictionary()
    d.set_int(_N("PatternType"), 1)
    d.set_int(_N("PaintType"), 1)
    d.set_int(_N("TilingType"), 1)
    d.set_item(_N("BBox"), _nums(0, 0, 10, 10))
    d.set_float(_N("XStep"), 10.0)
    d.set_float(_N("YStep"), 10.0)
    pat("tiling_plain_dict_not_stream", d)

    # --- shading pattern type 2 --------------------------------------------
    sh_dict = COSDictionary()
    sh_dict.set_int(_N("ShadingType"), 2)
    sh_dict.set_item(_N("ColorSpace"), _N("DeviceRGB"))
    sh_dict.set_item(_N("Coords"), _nums(0, 0, 100, 0))
    sh_dict.set_item(_N("Function"), _identity_func())
    d = COSDictionary()
    d.set_int(_N("PatternType"), 2)
    d.set_item(_N("Shading"), sh_dict)
    d.set_item(_N("Matrix"), _nums(1, 0, 0, 1, 0, 0))
    pat("shading_well_formed", d)

    d = COSDictionary()
    d.set_int(_N("PatternType"), 2)
    pat("shading_no_shading_entry", d)

    d = COSDictionary()
    d.set_int(_N("PatternType"), 2)
    d.set_item(_N("Shading"), _nums(1, 2, 3))  # /Shading not a dict
    pat("shading_shading_not_dict", d)

    bad_sh = COSDictionary()
    bad_sh.set_int(_N("ShadingType"), 99)  # nested unknown shading type
    d = COSDictionary()
    d.set_int(_N("PatternType"), 2)
    d.set_item(_N("Shading"), bad_sh)
    pat("shading_nested_unknown_type", d)

    d = COSDictionary()
    d.set_int(_N("PatternType"), 2)
    d.set_item(_N("Shading"), sh_dict)
    d.set_item(_N("Matrix"), _nums(1, 0, 0))  # matrix short
    pat("shading_matrix_short", d)

    d = COSDictionary()
    d.set_int(_N("PatternType"), 2)
    d.set_item(_N("Shading"), sh_dict)
    d.set_item(_N("Matrix"), COSString("not-a-matrix"))
    pat("shading_matrix_not_array", d)

    return cases


def _build_corpus() -> dict[str, COSDictionary]:
    corpus: dict[str, COSDictionary] = {}
    corpus.update(_shading_cases())
    corpus.update(_pattern_cases())
    return corpus


def _write_case_pdf(path: Path, name: str, entry: COSDictionary) -> None:
    """Build a one-page PDF whose first page carries the mutated dict as a
    resource (``/Shading/Sh1`` or ``/Pattern/P1``) and save it to ``path``."""
    from pypdfbox.pdmodel.pd_document import PDDocument
    from pypdfbox.pdmodel.pd_page import PDPage

    doc = PDDocument()
    try:
        page = PDPage()
        doc.add_page(page)
        resources = COSDictionary()
        sub = COSDictionary()
        if name.startswith("pattern_"):
            sub.set_item(_N("P1"), entry)
            resources.set_item(_N("Pattern"), sub)
        else:
            sub.set_item(_N("Sh1"), entry)
            resources.set_item(_N("Shading"), sub)
        page.set_resources(resources)
        doc.save(str(path))
    finally:
        doc.close()


# ----------------------------------------------------- Python-side projection


def _arity(base: COSBase | None) -> str:
    if base is None:
        return "absent"
    if isinstance(base, COSArray):
        return f"arr{base.size()}"
    return type(base).__name__


def _cs_name(shading) -> str:  # type: ignore[no-untyped-def]
    try:
        cs = shading.get_color_space_object()
        return "none" if cs is None else cs.get_name()
    except Exception:
        return "ERR"


def _shading_extra(shading) -> str:  # type: ignore[no-untyped-def]
    d = shading.get_cos_object()
    try:
        t = shading.get_shading_type()
    except Exception:
        t = -1
    parts: list[str] = []
    if t == 1:
        parts.append(f"domain={_arity(d.get_dictionary_object(_N('Domain')))}")
        parts.append(
            f"function={'0' if d.get_dictionary_object(_N('Function')) is None else '1'}"
        )
    elif t in (2, 3):
        parts.append(f"coords={_arity(d.get_dictionary_object(_N('Coords')))}")
        parts.append(f"domain={_arity(d.get_dictionary_object(_N('Domain')))}")
        parts.append(f"extend={_arity(d.get_dictionary_object(_N('Extend')))}")
        parts.append(
            f"function={'0' if d.get_dictionary_object(_N('Function')) is None else '1'}"
        )
    elif 4 <= t <= 7:
        parts.append(f"bpcoord={d.get_int(_N('BitsPerCoordinate'), -1)}")
        parts.append(f"bpcomp={d.get_int(_N('BitsPerComponent'), -1)}")
        parts.append(f"bpflag={d.get_int(_N('BitsPerFlag'), -1)}")
        parts.append(f"decode={_arity(d.get_dictionary_object(_N('Decode')))}")
    else:
        parts.append(f"type={t}")
    parts.append(f"aa={'1' if shading.get_anti_alias() else '0'}")
    parts.append(f"bg={_arity(d.get_dictionary_object(_N('Background')))}")
    return ",".join(parts)


def _fmt(f: float) -> str:
    if math.isnan(f):
        return "nan"
    if f == math.floor(f) and not math.isinf(f):
        return str(int(f))
    return repr(f)


def _pattern_extra(pat) -> str:  # type: ignore[no-untyped-def]
    d = pat.get_cos_object()
    try:
        t = pat.get_pattern_type()
    except Exception:
        t = -1
    parts: list[str] = []
    if t == 1:
        parts.append(f"paint={d.get_int(_N('PaintType'), -1)}")
        parts.append(f"tiling={d.get_int(_N('TilingType'), -1)}")
        parts.append(f"bbox={_arity(d.get_dictionary_object(_N('BBox')))}")
        parts.append(f"xstep={_fmt(d.get_float(_N('XStep'), float('nan')))}")
        parts.append(f"ystep={_fmt(d.get_float(_N('YStep'), float('nan')))}")
    elif t == 2:
        sh_obj = d.get_dictionary_object(_N("Shading"))
        try:
            sh = pat.get_shading()
            nested = "null" if sh is None else str(sh.get_shading_type())
        except Exception as e:
            nested = f"ERR:{_java_exc(e)}"
        parts.append(f"shading={'absent' if sh_obj is None else 'present'}")
        parts.append(f"nestedType={nested}")
        parts.append(f"matrix={_arity(d.get_dictionary_object(_N('Matrix')))}")
    else:
        parts.append(f"type={t}")
    return ",".join(parts)


def _java_exc(exc: Exception) -> str:
    """Map a pypdfbox exception to the Java exception simple-name the probe
    would report for the same failure (the create/getShading factories raise
    IOException upstream → OSError here)."""
    if isinstance(exc, OSError):
        return "IOException"
    return type(exc).__name__


def _python_line(case_dir: Path, name: str) -> str:
    pdf = case_dir / f"{name}.pdf"
    prefix = f"CASE {name} "
    try:
        doc = PDDocument.load(str(pdf))
    except Exception as e:
        return prefix + (
            f"shadingType=ERR class=ERR:{_java_exc(e)} cs=ERR extra=ERR"
        )
    try:
        page = doc.get_page(0)
        resources = page.get_resources()
        if name.startswith("pattern_"):
            try:
                pat = resources.get_pattern(_N("P1"))
            except Exception as e:
                return prefix + (
                    f"shadingType=ERR class=ERR:{_java_exc(e)} cs=ERR extra=ERR"
                )
            if pat is None:
                return prefix + "shadingType=null class=null cs=n/a extra=null"
            try:
                pt = str(pat.get_pattern_type())
            except Exception:
                pt = "ERR"
            return prefix + (
                f"shadingType={pt} class={type(pat).__name__} cs=n/a "
                f"extra={_pattern_extra(pat)}"
            )
        try:
            shading = resources.get_shading(_N("Sh1"))
        except Exception as e:
            return prefix + (
                f"shadingType=ERR class=ERR:{_java_exc(e)} cs=ERR extra=ERR"
            )
        if shading is None:
            return prefix + "shadingType=null class=null cs=null extra=null"
        try:
            st = str(shading.get_shading_type())
        except Exception:
            st = "ERR"
        return prefix + (
            f"shadingType={st} class={type(shading).__name__} "
            f"cs={_cs_name(shading)} extra={_shading_extra(shading)}"
        )
    finally:
        doc.close()


# --------------------------------------------------------------------- pins

# name -> (python_line_override, java_line_override, reason).
#
# Defensible divergence (pinned both-sides): when /ColorSpace (or /CS) is
# absent, an unknown name, or otherwise not a valid color-space object,
# upstream PDShading.getColorSpace() delegates to PDColorSpace.create(null /
# bad) which throws IOException / MissingResourceException — the probe reports
# cs=ERR. pypdfbox's PDColorSpace.create is more lenient: it returns None for a
# null or unrecognised color-space spec rather than raising, so
# PDShading.get_color_space_object() yields None and we report cs=none. The
# shading object itself constructs identically on both sides (same type, same
# class, same key projection); only the color-space resolution leniency
# differs. The leniency lives in the shared graphics/color module
# (PDColorSpace.create), which this agent does not own — flagged for hand-off.
# Pinned rather than forced so the rest of the construction contract stays a
# hard parity assertion. See CHANGES.md wave 1513.
_CS_LENIENCY = (
    "pypdfbox PDColorSpace.create returns None for null/unknown color-space "
    "spec where upstream throws IOException/MissingResourceException; shading "
    "still constructs identically. Color-module leniency — handed off."
)


def _pin_cs(name: str, extra: str) -> tuple[str, str, str]:
    py = (
        f"CASE {name} shadingType={_PIN_TYPE[name]} "
        f"class={_PIN_CLASS[name]} cs=none extra={extra}"
    )
    java = (
        f"CASE {name} shadingType={_PIN_TYPE[name]} "
        f"class={_PIN_CLASS[name]} cs=ERR extra={extra}"
    )
    return (py, java, _CS_LENIENCY)


_PIN_TYPE = {
    "shading_type_real_2": "2",
    "shading_type1_bare": "1",
    "shading_type2_no_colorspace": "2",
    "shading_type2_bad_colorspace": "2",
}
_PIN_CLASS = {
    "shading_type_real_2": "PDShadingType2",
    "shading_type1_bare": "PDShadingType1",
    "shading_type2_no_colorspace": "PDShadingType2",
    "shading_type2_bad_colorspace": "PDShadingType2",
}

_PINNED: dict[str, tuple[str, str, str]] = {
    "shading_type_real_2": _pin_cs(
        "shading_type_real_2",
        "coords=absent,domain=absent,extend=absent,function=0,aa=0,bg=absent",
    ),
    "shading_type1_bare": _pin_cs(
        "shading_type1_bare", "domain=absent,function=0,aa=0,bg=absent"
    ),
    "shading_type2_no_colorspace": _pin_cs(
        "shading_type2_no_colorspace",
        "coords=arr4,domain=absent,extend=absent,function=1,aa=0,bg=absent",
    ),
    "shading_type2_bad_colorspace": _pin_cs(
        "shading_type2_bad_colorspace",
        "coords=arr4,domain=absent,extend=absent,function=0,aa=0,bg=absent",
    ),
}


# --------------------------------------------------------------------- test


@requires_oracle
def test_shading_pattern_fuzz_matches_pdfbox(tmp_path: Path) -> None:
    """Every mutated shading/pattern dict constructs (or fails to construct)
    identically on pypdfbox and Apache PDFBox 3.0.7: same resolved type, same
    concrete class, same color-space name, same key projection. Divergences
    are pinned explicitly in ``_PINNED`` (with a matching CHANGES.md row)."""
    corpus = _build_corpus()
    for name, entry in corpus.items():
        _write_case_pdf(tmp_path / f"{name}.pdf", name, entry)
    (tmp_path / "manifest.txt").write_text(
        "\n".join(corpus) + "\n", encoding="utf-8"
    )

    raw = run_probe_text("ShadingPatternFuzzProbe", str(tmp_path))
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

    assert not mismatches, "shading/pattern fuzz divergences:\n" + "\n".join(
        mismatches
    )
