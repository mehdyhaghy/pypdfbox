"""Differential fuzz audit for the :class:`PDResources` lookup / dispatch layer
vs Apache PDFBox 3.0.7 (wave 1514, agent D).

Complements the well-formed ``test_resource_lookup_oracle`` (one valid entry
per category) — none of which exercise the MALFORMED ``/Resources`` subset this
audit targets:

* each resource sub-dictionary (``/Font`` ``/XObject`` ``/ColorSpace``
  ``/ExtGState`` ``/Shading`` ``/Pattern`` ``/Properties``) MISSING vs
  WRONG-TYPE (array / string / number instead of dictionary);
* a requested name ABSENT from a present sub-dictionary;
* the named entry PRESENT but WRONG-TYPE (e.g. ``/Font/F1`` pointing at a
  COSName / array / number rather than a font dictionary);
* ``get_color_space`` with the device-name shortcuts
  (``DeviceGray`` / ``DeviceRGB`` / ``DeviceCMYK`` / ``Pattern``) that resolve
  WITHOUT a ``/ColorSpace`` entry, plus a ``Default*`` override interaction and
  the abbreviated ``/G`` form (which does NOT resolve at the resource layer);
* ``get_color_space`` cache stability across two calls;
* the ``has_color_space`` / ``is_image_x_object`` predicates and the
  ``get_*_names`` listings over a malformed sub-dictionary.

This is the RESOURCES LOOKUP/DISPATCH layer, NOT the color-space (fuzzed wave
1512) or shading/pattern (wave 1513) construction internals — the focus is how
``PDResources`` resolves a NAME to an object and tolerates a malformed
sub-dictionary.

Both sides are driven on the SAME bytes: the corpus builder writes a one-page
PDF per case (the mutated dict installed as the page's ``/Resources``) plus a
``manifest.txt`` into a tmp dir. The Java probe
(``oracle/probes/ResourcesLookupFuzzProbe.java``) loads each ``<case>.pdf`` and
projects a stable framed line; this module reads the exact same files and
projects the identical grammar through pypdfbox, then asserts line-for-line
parity.

Line grammar (one per case, manifest order)::

    CASE <name> font=<cls|null|ERR:X> xobj=<cls|null|ERR:X> cs=<name|null|ERR:X>
        gs=<cls|null|ERR:X> sh=<cls|null|ERR:X> pat=<cls|null|ERR:X>
        prop=<cls|null|ERR:X> has=<cc-flags> names=<sorted|->

Java is ground truth: a real divergence is a production fix in
``pypdfbox/pdmodel/pd_resources.py``; a defensible divergence is pinned in
``_PINNED`` with a matching CHANGES.md row.
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
    COSString,
)
from pypdfbox.pdmodel.missing_resource_exception import MissingResourceException
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from tests.oracle.harness import requires_oracle, run_probe_text

_N = COSName.get_pdf_name
_Q1 = _N("Q1")


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


def _gstate_dict() -> COSDictionary:
    d = COSDictionary()
    d.set_item(_N("Type"), _N("ExtGState"))
    d.set_float(_N("ca"), 0.5)
    return d


def _ocg_dict() -> COSDictionary:
    d = COSDictionary()
    d.set_item(_N("Type"), _N("OCG"))
    d.set_string(_N("Name"), "layer")
    return d


def _axial_shading() -> COSDictionary:
    d = COSDictionary()
    d.set_int(_N("ShadingType"), 2)
    d.set_item(_N("ColorSpace"), _N("DeviceRGB"))
    d.set_item(_N("Coords"), _nums(0, 0, 1, 0))
    return d


def _shading_pattern() -> COSDictionary:
    d = COSDictionary()
    d.set_item(_N("Type"), _N("Pattern"))
    d.set_int(_N("PatternType"), 2)
    d.set_item(_N("Shading"), _axial_shading())
    return d


def _icc_cs() -> COSArray:
    from pypdfbox.cos import COSStream

    icc = COSStream()
    icc.set_int(_N("N"), 3)
    return _arr(_N("ICCBased"), icc)


def _sub(category: str, key: str, value: COSBase) -> COSDictionary:
    """Build a /Resources dict whose ``/<category>`` sub-dict maps ``key`` to
    ``value``."""
    r = COSDictionary()
    s = COSDictionary()
    s.set_item(_N(key), value)
    r.set_item(_N(category), s)
    return r


# --------------------------------------------------------------------- corpus


def _build_corpus() -> dict[str, COSDictionary]:
    """Each case is a full ``/Resources`` dictionary; the probed name is ``Q1``
    (except the device color-space shortcuts, keyed by case-name prefix on the
    Java side)."""
    c: dict[str, COSDictionary] = {}

    # ---- baseline: every category present + well-formed entry under Q1 ----
    base = COSDictionary()
    base.set_item(_N("Font"), _one("Q1", _font_dict()))
    base.set_item(_N("XObject"), _one("Q1", _form_xobject()))
    base.set_item(_N("ColorSpace"), _one("Q1", _icc_cs()))
    base.set_item(_N("ExtGState"), _one("Q1", _gstate_dict()))
    base.set_item(_N("Shading"), _one("Q1", _axial_shading()))
    base.set_item(_N("Pattern"), _one("Q1", _shading_pattern()))
    base.set_item(_N("Properties"), _one("Q1", _ocg_dict()))
    c["all_present"] = base

    # ---- completely empty /Resources ----
    c["empty_resources"] = COSDictionary()

    # ---- each sub-dict MISSING (only the foreign category present) ----
    # A /Resources with just /Font means xobj/cs/gs/sh/pat/prop all miss.
    c["only_font"] = _sub("Font", "Q1", _font_dict())
    c["only_xobject_image"] = _sub("XObject", "Q1", _image_xobject())
    c["only_colorspace"] = _sub("ColorSpace", "Q1", _icc_cs())
    c["only_extgstate"] = _sub("ExtGState", "Q1", _gstate_dict())
    c["only_shading"] = _sub("Shading", "Q1", _axial_shading())
    c["only_pattern_tiling"] = _sub("Pattern", "Q1", _tiling_pattern())
    c["only_properties"] = _sub("Properties", "Q1", _ocg_dict())

    # ---- sub-dict present but WRONG-TYPE (array / string / number / name) ----
    for cat in (
        "Font",
        "XObject",
        "ColorSpace",
        "ExtGState",
        "Shading",
        "Pattern",
        "Properties",
    ):
        lc = cat.lower()
        r = COSDictionary()
        r.set_item(_N(cat), _nums(1, 2, 3))
        c[f"subdict_{lc}_is_array"] = r
        r = COSDictionary()
        r.set_item(_N(cat), COSString("not-a-dict"))
        c[f"subdict_{lc}_is_string"] = r
        r = COSDictionary()
        r.set_item(_N(cat), COSInteger(7))
        c[f"subdict_{lc}_is_number"] = r
        r = COSDictionary()
        r.set_item(_N(cat), _N("AName"))
        c[f"subdict_{lc}_is_name"] = r

    # ---- name ABSENT from a present (well-formed) sub-dict ----
    # Install the entry under a DIFFERENT key so /Q1 misses every category.
    miss = COSDictionary()
    miss.set_item(_N("Font"), _one("Other", _font_dict()))
    miss.set_item(_N("XObject"), _one("Other", _form_xobject()))
    miss.set_item(_N("ColorSpace"), _one("Other", _icc_cs()))
    miss.set_item(_N("ExtGState"), _one("Other", _gstate_dict()))
    miss.set_item(_N("Shading"), _one("Other", _axial_shading()))
    miss.set_item(_N("Pattern"), _one("Other", _shading_pattern()))
    miss.set_item(_N("Properties"), _one("Other", _ocg_dict()))
    c["name_absent_in_present_subdict"] = miss

    # ---- named entry present but WRONG-TYPE (Q1 -> name/array/number/string) ----
    for label, value in (
        ("name", _N("SomeName")),
        ("array", _nums(1, 2, 3)),
        ("number", COSInteger(5)),
        ("string", COSString("hi")),
    ):
        c[f"font_entry_is_{label}"] = _sub("Font", "Q1", value)
        c[f"xobject_entry_is_{label}"] = _sub("XObject", "Q1", value)
        c[f"colorspace_entry_is_{label}"] = _sub("ColorSpace", "Q1", value)
        c[f"extgstate_entry_is_{label}"] = _sub("ExtGState", "Q1", value)
        c[f"shading_entry_is_{label}"] = _sub("Shading", "Q1", value)
        c[f"pattern_entry_is_{label}"] = _sub("Pattern", "Q1", value)
        c[f"properties_entry_is_{label}"] = _sub("Properties", "Q1", value)

    # ---- color-space device-name shortcuts (resolve WITHOUT an entry) ----
    # No /ColorSpace sub-dict at all; the probe asks for the device name.
    c["cs_device_gray_no_entry"] = COSDictionary()
    c["cs_device_rgb_no_entry"] = COSDictionary()
    c["cs_device_cmyk_no_entry"] = COSDictionary()
    c["cs_pattern_shortcut_no_entry"] = COSDictionary()
    # abbreviated /G form — NOT expanded at the resource layer (inline-image
    # short forms are expanded earlier), so this is an unresolvable name.
    c["cs_g_short_no_entry"] = COSDictionary()
    # a non-device unresolvable name with no entry.
    c["cs_absent_nondevice_no_entry"] = COSDictionary()

    # ---- Default* override: DeviceRGB shortcut picks up /DefaultRGB ----
    r = COSDictionary()
    cs_sub = COSDictionary()
    cs_sub.set_item(_N("DefaultRGB"), _icc_cs())
    r.set_item(_N("ColorSpace"), cs_sub)
    c["cs_device_rgb_with_default"] = r

    # ---- /ColorSpace device name with a malformed entry colliding ----
    # /ColorSpace/DeviceRGB present but as an array → entry wins over shortcut.
    r = COSDictionary()
    cs_sub = COSDictionary()
    cs_sub.set_item(_N("Q1"), _N("DeviceRGB"))  # Q1 -> /DeviceRGB name
    r.set_item(_N("ColorSpace"), cs_sub)
    c["cs_entry_is_device_name"] = r

    return c


def _one(key: str, value: COSBase) -> COSDictionary:
    d = COSDictionary()
    d.set_item(_N(key), value)
    return d


def _form_xobject() -> COSBase:
    from pypdfbox.cos import COSStream

    s = COSStream()
    s.set_item(_N("Type"), _N("XObject"))
    s.set_item(_N("Subtype"), _N("Form"))
    s.set_item(_N("BBox"), _nums(0, 0, 10, 10))
    out = s.create_output_stream()
    out.write(b"")
    out.close()
    return s


def _image_xobject() -> COSBase:
    from pypdfbox.cos import COSStream

    s = COSStream()
    s.set_item(_N("Type"), _N("XObject"))
    s.set_item(_N("Subtype"), _N("Image"))
    s.set_int(_N("Width"), 1)
    s.set_int(_N("Height"), 1)
    s.set_int(_N("BitsPerComponent"), 8)
    s.set_item(_N("ColorSpace"), _N("DeviceGray"))
    out = s.create_output_stream()
    out.write(b"\x00")
    out.close()
    return s


def _tiling_pattern() -> COSBase:
    from pypdfbox.cos import COSStream

    s = COSStream()
    s.set_item(_N("Type"), _N("Pattern"))
    s.set_int(_N("PatternType"), 1)
    s.set_int(_N("PaintType"), 1)
    s.set_int(_N("TilingType"), 1)
    s.set_item(_N("BBox"), _nums(0, 0, 10, 10))
    s.set_float(_N("XStep"), 10.0)
    s.set_float(_N("YStep"), 10.0)
    s.set_item(_N("Resources"), COSDictionary())
    out = s.create_output_stream()
    out.write(b"")
    out.close()
    return s


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
    """Map a pypdfbox exception to the Java exception simple-name the probe
    reports for the same failure."""
    if isinstance(exc, MissingResourceException):
        return "MissingResourceException"
    if isinstance(exc, OSError):
        return "IOException"
    return type(exc).__name__


def _cls(obj: object) -> str:
    return type(obj).__name__


def _font_cell(res) -> str:  # type: ignore[no-untyped-def]
    try:
        f = res.get_font(_Q1)
        return "null" if f is None else _cls(f)
    except Exception as e:
        return f"ERR:{_java_exc(e)}"


def _xobj_cell(res) -> str:  # type: ignore[no-untyped-def]
    try:
        x = res.get_x_object(_Q1)
        return "null" if x is None else _cls(x)
    except Exception as e:
        return f"ERR:{_java_exc(e)}"


def _cs_probe_name(name: str) -> COSName:
    if name.startswith("cs_device_gray"):
        return _N("DeviceGray")
    if name.startswith("cs_device_rgb"):
        return _N("DeviceRGB")
    if name.startswith("cs_device_cmyk"):
        return _N("DeviceCMYK")
    if name.startswith("cs_pattern_shortcut"):
        return _N("Pattern")
    if name.startswith("cs_g_short"):
        return _N("G")
    if name.startswith("cs_absent_nondevice"):
        return _N("Nope")
    return _Q1


def _cs_cell(res, cs_name: COSName) -> str:  # type: ignore[no-untyped-def]
    try:
        cs = res.get_color_space(cs_name)
        return "null" if cs is None else cs.get_name()
    except Exception as e:
        return f"ERR:{_java_exc(e)}"


def _gs_cell(res) -> str:  # type: ignore[no-untyped-def]
    try:
        gs = res.get_ext_gstate(_Q1)
        return "null" if gs is None else _cls(gs)
    except Exception as e:
        return f"ERR:{_java_exc(e)}"


def _sh_cell(res) -> str:  # type: ignore[no-untyped-def]
    try:
        sh = res.get_shading(_Q1)
        return "null" if sh is None else _cls(sh)
    except Exception as e:
        return f"ERR:{_java_exc(e)}"


def _pat_cell(res) -> str:  # type: ignore[no-untyped-def]
    try:
        p = res.get_pattern(_Q1)
        return "null" if p is None else _cls(p)
    except Exception as e:
        return f"ERR:{_java_exc(e)}"


def _prop_cell(res) -> str:  # type: ignore[no-untyped-def]
    try:
        p = res.get_properties(_Q1)
        return "null" if p is None else _cls(p)
    except Exception as e:
        return f"ERR:{_java_exc(e)}"


def _bit(fn) -> str:  # type: ignore[no-untyped-def]
    try:
        return "1" if fn() else "0"
    except Exception:
        return "E"


def _has_cell(res, cs_name: COSName) -> str:  # type: ignore[no-untyped-def]
    return _bit(lambda: res.has_color_space(cs_name)) + _bit(
        lambda: res.is_image_x_object(_Q1)
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
        cs_name = _cs_probe_name(name)
        return prefix + (
            f"font={_font_cell(res)} xobj={_xobj_cell(res)} "
            f"cs={_cs_cell(res, cs_name)} gs={_gs_cell(res)} "
            f"sh={_sh_cell(res)} pat={_pat_cell(res)} prop={_prop_cell(res)} "
            f"has={_has_cell(res, cs_name)} names={_names_cell(res)}"
        )
    finally:
        doc.close()


# --------------------------------------------------------------------- pins

# name -> (python_line_override, java_line_override, reason).
#
# Defensible divergence (pinned both-sides): when /ColorSpace/Q1 is an array of
# numbers, a string, or a number (i.e. not a name and not a valid array-form
# color-space spec), upstream PDResources.getColorSpace delegates to
# PDColorSpace.create(badBase) which raises IOException. pypdfbox's shared
# PDColorSpace.create is permissive: it returns None for a spec it cannot
# recognise (the permissive-None design documented since wave 1512), so
# get_color_space yields None and the cell is cs=null. The leniency lives in
# the shared graphics/color module (PDColorSpace.create), which this agent does
# NOT own — pinned both-sides rather than forced, with a hand-off note. Every
# other cell on these lines is byte-identical; only the malformed-color-space
# failure mode (raise vs None) differs. See CHANGES.md wave 1514.
_CS_LENIENCY = (
    "pypdfbox PDColorSpace.create returns None for an unrecognised non-name "
    "color-space spec (array-of-numbers / string / number) where upstream "
    "raises IOException; the rest of the resources-lookup contract is "
    "identical. Shared color-module leniency (wave 1512) — handed off."
)


def _pin_cs_entry(name: str) -> tuple[str, str, str]:
    common = (
        f"CASE {name} font=null xobj=null cs=%s gs=null sh=null pat=null "
        "prop=null has=10 names=Q1"
    )
    return (common % "null", common % "ERR:IOException", _CS_LENIENCY)


_PINNED: dict[str, tuple[str, str, str]] = {
    "colorspace_entry_is_array": _pin_cs_entry("colorspace_entry_is_array"),
    "colorspace_entry_is_string": _pin_cs_entry("colorspace_entry_is_string"),
    "colorspace_entry_is_number": _pin_cs_entry("colorspace_entry_is_number"),
}


# --------------------------------------------------------------------- test


@requires_oracle
def test_resources_lookup_fuzz_matches_pdfbox(tmp_path: Path) -> None:
    """Every malformed ``/Resources`` dict resolves (or fails to resolve)
    identically on pypdfbox and Apache PDFBox 3.0.7: same per-getter cell, same
    presence predicates, same name listings. Divergences are pinned explicitly
    in ``_PINNED`` (with a matching CHANGES.md row)."""
    corpus = _build_corpus()
    for name, resources in corpus.items():
        _write_case_pdf(tmp_path / f"{name}.pdf", resources)
    (tmp_path / "manifest.txt").write_text("\n".join(corpus) + "\n", encoding="utf-8")

    raw = run_probe_text("ResourcesLookupFuzzProbe", str(tmp_path))
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

    assert not mismatches, "PDResources lookup fuzz divergences:\n" + "\n".join(
        mismatches
    )
