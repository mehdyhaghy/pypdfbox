"""Second-generation differential fuzz audit for the :class:`PDResources`
lookup / dispatch layer vs Apache PDFBox 3.0.7 (wave 1555, agent A).

Complements ``test_resources_lookup_fuzz_wave1514`` (which fuzzed missing /
wrong-type sub-dicts, absent names, wrong-type entries, the device-name
color-space shortcuts and the ``Default*`` override). This module targets the
angles wave 1514 did NOT cover:

* an ``/XObject`` stream whose ``/Subtype`` is a **COSString** ``"Form"`` /
  ``"Image"`` rather than a name — upstream ``PDXObject.createXObject`` reads it
  through ``COSStream.getNameAsString``, so a string subtype STILL dispatches to
  the right wrapper; an absent / unknown subtype raises;
* resource names with ``#``-escapes / non-ASCII characters that must round-trip
  through the writer + lexer and still resolve;
* ``get_properties`` class projection across an OCG, an OCMD and a plain
  marked-content dictionary;
* ``get_color_space`` where the named ``/ColorSpace/Q1`` entry is itself a
  device-name COSName, plus the inline-array forms (CalRGB / Indexed) resolved
  by name.

The ``/Subtype``-as-COSString cases pin a **real production bug fixed in this
wave**: ``PDResources.get_x_object`` previously read ``/Subtype`` with
``get_name`` (name-only), so a stream whose subtype was stored as a string was
mis-classified and raised ``Invalid XObject Subtype``. It now uses
``get_name_as_string``, matching upstream.

Both sides are driven on the SAME bytes: a one-page PDF per case (the mutated
dict installed as the page's ``/Resources``) plus a ``manifest.txt``. The Java
probe (``oracle/probes/ResourcesLookupFuzz2Probe.java``) loads each
``<case>.pdf`` and projects a stable framed line; this module reads the exact
same files and projects the identical grammar through pypdfbox, then asserts
line-for-line parity.

Line grammar (one per case, manifest order)::

    CASE <name> font=<cls|null|ERR:X> xobj=<cls|null|ERR:X> cs=<name|null|ERR:X>
        gs=<cls|null|ERR:X> sh=<cls|null|ERR:X> pat=<cls|null|ERR:X>
        prop=<cls|null|ERR:X> has=<cc-flags> names=<sorted|->

Java is ground truth: a real divergence is a production fix; a defensible
divergence is pinned in ``_PINNED`` with a matching CHANGES.md row.
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSStream,
    COSString,
)
from pypdfbox.pdmodel.missing_resource_exception import MissingResourceException
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from tests.oracle.harness import requires_oracle, run_probe_text

_N = COSName.get_pdf_name
_Q1 = _N("Q1")
_HASH = _N("A B#C")
_SPECIAL = _N("Aあ")


# --------------------------------------------------------------------- helpers


def _arr(*items: COSBase) -> COSArray:
    a = COSArray()
    for it in items:
        a.add(it)
    return a


def _nums(*vals: float) -> COSArray:
    return _arr(*[COSFloat(float(v)) for v in vals])


def _font_dict() -> COSDictionary:
    d = COSDictionary()
    d.set_item(_N("Type"), _N("Font"))
    d.set_item(_N("Subtype"), _N("Type1"))
    d.set_item(_N("BaseFont"), _N("Helvetica"))
    return d


def _ocg_dict() -> COSDictionary:
    d = COSDictionary()
    d.set_item(_N("Type"), _N("OCG"))
    d.set_string(_N("Name"), "layer")
    return d


def _ocmd_dict() -> COSDictionary:
    d = COSDictionary()
    d.set_item(_N("Type"), _N("OCMD"))
    return d


def _plain_mc_dict() -> COSDictionary:
    # A marked-content property list with no /Type → bare PDPropertyList.
    d = COSDictionary()
    d.set_item(_N("MCID"), COSInteger(3))
    return d


# Sentinel so an explicit ``subtype_value=None`` (absent /Subtype) is
# distinguishable from "use the default name" (B008-safe default).
_DEFAULT_SUBTYPE = object()


def _form_xobject(subtype_value: COSBase | None | object = _DEFAULT_SUBTYPE) -> COSStream:
    if subtype_value is _DEFAULT_SUBTYPE:
        subtype_value = _N("Form")
    s = COSStream()
    s.set_item(_N("Type"), _N("XObject"))
    if isinstance(subtype_value, COSBase):
        s.set_item(_N("Subtype"), subtype_value)
    s.set_item(_N("BBox"), _nums(0, 0, 10, 10))
    out = s.create_output_stream()
    out.write(b"")
    out.close()
    return s


def _image_xobject(subtype_value: COSBase | None | object = _DEFAULT_SUBTYPE) -> COSStream:
    if subtype_value is _DEFAULT_SUBTYPE:
        subtype_value = _N("Image")
    s = COSStream()
    s.set_item(_N("Type"), _N("XObject"))
    if isinstance(subtype_value, COSBase):
        s.set_item(_N("Subtype"), subtype_value)
    s.set_int(_N("Width"), 1)
    s.set_int(_N("Height"), 1)
    s.set_int(_N("BitsPerComponent"), 8)
    s.set_item(_N("ColorSpace"), _N("DeviceGray"))
    out = s.create_output_stream()
    out.write(b"\x00")
    out.close()
    return s


def _calrgb_cs() -> COSArray:
    params = COSDictionary()
    params.set_item(_N("WhitePoint"), _nums(0.9505, 1.0, 1.089))
    return _arr(_N("CalRGB"), params)


def _indexed_cs() -> COSArray:
    lut = COSString(b"\x00\x00\x00\xff\xff\xff")
    return _arr(_N("Indexed"), _N("DeviceRGB"), COSInteger(1), lut)


def _one(key: COSName, value: COSBase) -> COSDictionary:
    d = COSDictionary()
    d.set_item(key, value)
    return d


# --------------------------------------------------------------------- corpus


def _build_corpus() -> dict[str, COSDictionary]:
    c: dict[str, COSDictionary] = {}

    # ---- /Subtype stored as a COSString (the bug-fix cases) ----
    # Upstream getNameAsString decodes a string subtype, so "Form"/"Image"
    # still dispatch to PDFormXObject / PDImageXObject.
    c["xobj_subtype_string_form"] = _wrap(
        "XObject", _Q1, _form_xobject(COSString("Form"))
    )
    c["xobj_subtype_string_image"] = _wrap(
        "XObject", _Q1, _image_xobject(COSString("Image"))
    )
    # /Subtype absent entirely → getNameAsString returns null → raise.
    c["xobj_subtype_absent"] = _wrap(
        "XObject", _Q1, _form_xobject(subtype_value=None)
    )
    # /Subtype is an unknown name → raise.
    c["xobj_subtype_unknown"] = _wrap(
        "XObject", _Q1, _form_xobject(_N("Bogus"))
    )
    # /Subtype is a string but an unknown value → raise (decoded, not matched).
    c["xobj_subtype_string_unknown"] = _wrap(
        "XObject", _Q1, _form_xobject(COSString("Nope"))
    )

    # ---- resource names with #-escapes / non-ASCII ----
    # Key "A B#C" must survive write + lex and still resolve.
    c["name_hash_escape_font"] = _wrap("Font", _HASH, _font_dict())
    c["name_hash_escape_image"] = _wrap("XObject", _HASH, _image_xobject())
    c["name_special_font"] = _wrap("Font", _SPECIAL, _font_dict())

    # ---- getProperties class projection ----
    c["prop_ocg"] = _wrap("Properties", _Q1, _ocg_dict())
    c["prop_ocmd"] = _wrap("Properties", _Q1, _ocmd_dict())
    c["prop_plain_mc"] = _wrap("Properties", _Q1, _plain_mc_dict())

    # ---- getColorSpace: named entry is a device-name COSName ----
    # /ColorSpace/Q1 -> /DeviceRGB : the named lookup resolves the device CS.
    c["cs_named_device_rgb"] = _wrap("ColorSpace", _Q1, _N("DeviceRGB"))
    c["cs_named_device_gray"] = _wrap("ColorSpace", _Q1, _N("DeviceGray"))
    c["cs_named_device_cmyk"] = _wrap("ColorSpace", _Q1, _N("DeviceCMYK"))
    c["cs_named_pattern"] = _wrap("ColorSpace", _Q1, _N("Pattern"))
    # ---- getColorSpace: named inline-array forms ----
    c["cs_array_calrgb"] = _wrap("ColorSpace", _Q1, _calrgb_cs())
    c["cs_array_indexed"] = _wrap("ColorSpace", _Q1, _indexed_cs())

    return c


def _wrap(category: str, key: COSName, value: COSBase) -> COSDictionary:
    r = COSDictionary()
    r.set_item(_N(category), _one(key, value))
    return r


# --------------------------------------------------------------------- corpus io


def _write_case_pdf(path: Path, resources: COSDictionary) -> None:
    doc = PDDocument()
    try:
        page = PDPage()
        doc.add_page(page)
        page.set_resources(resources)
        doc.save(str(path))
    finally:
        doc.close()


# ----------------------------------------------------- Python-side projection


def _java_exc(exc: Exception) -> str:
    if isinstance(exc, MissingResourceException):
        return "MissingResourceException"
    if isinstance(exc, OSError):
        return "IOException"
    return type(exc).__name__


def _cls(obj: object) -> str:
    return type(obj).__name__


def _probe_name(name: str) -> COSName:
    if name.startswith("name_hash_escape"):
        return _HASH
    if name.startswith("name_special"):
        return _SPECIAL
    return _Q1


def _font_cell(res, name) -> str:  # type: ignore[no-untyped-def]
    try:
        f = res.get_font(name)
        return "null" if f is None else _cls(f)
    except Exception as e:
        return f"ERR:{_java_exc(e)}"


def _xobj_cell(res, name) -> str:  # type: ignore[no-untyped-def]
    try:
        x = res.get_x_object(name)
        return "null" if x is None else _cls(x)
    except Exception as e:
        return f"ERR:{_java_exc(e)}"


def _cs_cell(res, cs_name) -> str:  # type: ignore[no-untyped-def]
    try:
        cs = res.get_color_space(cs_name)
        return "null" if cs is None else cs.get_name()
    except Exception as e:
        return f"ERR:{_java_exc(e)}"


def _gs_cell(res, name) -> str:  # type: ignore[no-untyped-def]
    try:
        gs = res.get_ext_gstate(name)
        return "null" if gs is None else _cls(gs)
    except Exception as e:
        return f"ERR:{_java_exc(e)}"


def _sh_cell(res, name) -> str:  # type: ignore[no-untyped-def]
    try:
        sh = res.get_shading(name)
        return "null" if sh is None else _cls(sh)
    except Exception as e:
        return f"ERR:{_java_exc(e)}"


def _pat_cell(res, name) -> str:  # type: ignore[no-untyped-def]
    try:
        p = res.get_pattern(name)
        return "null" if p is None else _cls(p)
    except Exception as e:
        return f"ERR:{_java_exc(e)}"


def _prop_cell(res, name) -> str:  # type: ignore[no-untyped-def]
    try:
        p = res.get_properties(name)
        return "null" if p is None else _cls(p)
    except Exception as e:
        return f"ERR:{_java_exc(e)}"


def _bit(fn) -> str:  # type: ignore[no-untyped-def]
    try:
        return "1" if fn() else "0"
    except Exception:
        return "E"


def _has_cell(res, cs_name, probe) -> str:  # type: ignore[no-untyped-def]
    return _bit(lambda: res.has_color_space(cs_name)) + _bit(
        lambda: res.is_image_x_object(probe)
    )


def _names_cell(res) -> str:  # type: ignore[no-untyped-def]
    names: set[str] = set()
    for getter in (
        res.get_font_names,
        res.get_xobject_names,
        res.get_color_space_names,
        res.get_extgstate_names,
        res.get_shading_names,
        res.get_pattern_names,
        res.get_property_list_names,
    ):
        try:
            for n in getter():
                names.add(n.get_name())
        except Exception:
            pass
    return "|".join(sorted(names)) if names else "-"


def _python_line(case_dir: Path, name: str) -> str:
    pdf = case_dir / f"{name}.pdf"
    prefix = f"CASE {name} "
    try:
        doc = PDDocument.load(str(pdf))
    except Exception as e:
        cls = e.__class__.__name__
        return prefix + (
            f"font=LOAD:{cls} xobj=LOAD cs=LOAD gs=LOAD sh=LOAD pat=LOAD "
            "prop=LOAD has=LOAD names=LOAD"
        )
    try:
        page = doc.get_page(0)
        res = page.get_resources()
        if res is None:
            return prefix + (
                "font=NORES xobj=NORES cs=NORES gs=NORES sh=NORES pat=NORES "
                "prop=NORES has=NORES names=NORES"
            )
        p = _probe_name(name)
        csp = _Q1 if name.startswith("cs_") else p
        return prefix + (
            f"font={_font_cell(res, p)} xobj={_xobj_cell(res, p)} "
            f"cs={_cs_cell(res, csp)} gs={_gs_cell(res, p)} "
            f"sh={_sh_cell(res, p)} pat={_pat_cell(res, p)} "
            f"prop={_prop_cell(res, p)} "
            f"has={_has_cell(res, csp, p)} names={_names_cell(res)}"
        )
    finally:
        doc.close()


# --------------------------------------------------------------------- pins

# name -> (python_line_override, java_line_override, reason).
_PINNED: dict[str, tuple[str, str, str]] = {}


# --------------------------------------------------------------------- test


@requires_oracle
def test_resources_lookup_fuzz2_matches_pdfbox(tmp_path: Path) -> None:
    """Every edge-case ``/Resources`` dict resolves (or fails) identically on
    pypdfbox and Apache PDFBox 3.0.7: same per-getter cell, same presence
    predicates, same name listings. Divergences are pinned in ``_PINNED``."""
    corpus = _build_corpus()
    for name, resources in corpus.items():
        _write_case_pdf(tmp_path / f"{name}.pdf", resources)
    (tmp_path / "manifest.txt").write_text("\n".join(corpus) + "\n", encoding="utf-8")

    raw = run_probe_text("ResourcesLookupFuzz2Probe", str(tmp_path))
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

    assert not mismatches, "PDResources lookup fuzz (gen2) divergences:\n" + "\n".join(
        mismatches
    )
