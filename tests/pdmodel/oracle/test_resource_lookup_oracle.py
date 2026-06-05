"""Live PDFBox differential parity for the ``PDResources`` lookup surface.

Does pypdfbox's :class:`PDResources` resolve every ``/Resources`` sub-category
(``/Font`` / ``/XObject`` / ``/ColorSpace`` / ``/ExtGState`` / ``/Shading`` /
``/Pattern`` / ``/Properties``) to the same typed object class — and apply the
same well-known color-space-name shortcuts and the same missing-name failure
mode — as Apache PDFBox?

The Java side is ``oracle/probes/ResourceLookupProbe.java``: it builds a
``/Resources`` dictionary from COS primitives (one entry per category, plus a
tiling and a shading pattern, and three array-form color spaces) and dumps, per
key, the resolved object's runtime class simple-name — together with the
``getColorSpaceNames`` / ``getXObjectNames`` / … name listings (sorted) and the
result of looking up the well-known device color-space names
(``DeviceRGB`` / ``DeviceGray`` / ``DeviceCMYK`` / ``Pattern``) that resolve
WITHOUT a resource entry.

Here we build the byte-identical COS dictionary in pypdfbox and reproduce the
same dump, asserting it matches the live oracle.

**Missing color space.** Upstream ``PDResources.getColorSpace`` raises
``MissingResourceException`` for an unresolvable non-device name (verified
against PDFBox 3.0.7), so the probe records ``THROW:Missing color space: <n>``
for that case and the reproducer mirrors it. pypdfbox previously returned
``None`` here; wave 1461 fixed it to match upstream.
"""

from __future__ import annotations

import json

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSStream
from pypdfbox.pdmodel import MissingResourceException, PDDocument, PDResources
from tests.oracle.harness import requires_oracle, run_probe_text


def _name(value: str) -> COSName:
    return COSName.get_pdf_name(value)


def _build_resource_dict() -> COSDictionary:
    """Build the byte-identical /Resources dictionary the Java probe builds."""
    r = COSDictionary()

    # /Font/F0 — minimal Type1 Helvetica.
    font = COSDictionary()
    font.set_item(_name("Type"), _name("Font"))
    font.set_item(_name("Subtype"), _name("Type1"))
    font.set_item(_name("BaseFont"), _name("Helvetica"))
    fonts = COSDictionary()
    fonts.set_item(_name("F0"), font)
    r.set_item(_name("Font"), fonts)

    # /XObject — one image, one form.
    img = COSStream()
    img.set_item(_name("Type"), _name("XObject"))
    img.set_item(_name("Subtype"), _name("Image"))
    img.set_int(_name("Width"), 1)
    img.set_int(_name("Height"), 1)
    img.set_int(_name("BitsPerComponent"), 8)
    img.set_item(_name("ColorSpace"), _name("DeviceGray"))
    bbox = COSArray()
    for v in (0, 0, 10, 10):
        bbox.add(COSInteger.get(v))
    form = COSStream()
    form.set_item(_name("Type"), _name("XObject"))
    form.set_item(_name("Subtype"), _name("Form"))
    form.set_item(_name("BBox"), bbox)
    xobjects = COSDictionary()
    xobjects.set_item(_name("Im0"), img)
    xobjects.set_item(_name("Fm0"), form)
    r.set_item(_name("XObject"), xobjects)

    # /ColorSpace — ICCBased, Separation, CalRGB (all array form).
    color_spaces = COSDictionary()
    icc_stream = COSStream()
    icc_stream.set_int(_name("N"), 3)
    icc = COSArray()
    icc.add(_name("ICCBased"))
    icc.add(icc_stream)
    color_spaces.set_item(_name("csIcc"), icc)
    sep = COSArray()
    sep.add(_name("Separation"))
    sep.add(_name("Spot"))
    sep.add(_name("DeviceRGB"))
    fn = COSDictionary()
    fn.set_int(_name("FunctionType"), 2)
    domain = COSArray()
    domain.add(COSInteger.get(0))
    domain.add(COSInteger.get(1))
    fn.set_item(_name("Domain"), domain)
    fn.set_item(_name("N"), COSInteger.get(1))
    sep.add(fn)
    color_spaces.set_item(_name("csSep"), sep)
    cal = COSArray()
    cal.add(_name("CalRGB"))
    cal.add(COSDictionary())
    color_spaces.set_item(_name("csCal"), cal)
    r.set_item(_name("ColorSpace"), color_spaces)

    # /ExtGState
    gs = COSDictionary()
    gs.set_item(_name("Type"), _name("ExtGState"))
    gs.set_float(_name("ca"), 0.5)
    ext_g_states = COSDictionary()
    ext_g_states.set_item(_name("gs0"), gs)
    r.set_item(_name("ExtGState"), ext_g_states)

    # /Shading — axial (type 2).
    shading = COSDictionary()
    shading.set_int(_name("ShadingType"), 2)
    shading.set_item(_name("ColorSpace"), _name("DeviceRGB"))
    coords = COSArray()
    for v in (0, 0, 1, 0):
        coords.add(COSInteger.get(v))
    shading.set_item(_name("Coords"), coords)
    shadings = COSDictionary()
    shadings.set_item(_name("sh0"), shading)
    r.set_item(_name("Shading"), shadings)

    # /Pattern — tiling (type 1, a stream) and shading (type 2, a dict).
    tiling = COSStream()
    tiling.set_item(_name("Type"), _name("Pattern"))
    tiling.set_int(_name("PatternType"), 1)
    tiling.set_int(_name("PaintType"), 1)
    tiling.set_int(_name("TilingType"), 1)
    tiling.set_item(_name("BBox"), bbox)
    tiling.set_float(_name("XStep"), 10.0)
    tiling.set_float(_name("YStep"), 10.0)
    tiling.set_item(_name("Resources"), COSDictionary())
    sh_pattern = COSDictionary()
    sh_pattern.set_item(_name("Type"), _name("Pattern"))
    sh_pattern.set_int(_name("PatternType"), 2)
    sh_pattern.set_item(_name("Shading"), shading)
    patterns = COSDictionary()
    patterns.set_item(_name("p0"), tiling)
    patterns.set_item(_name("p1"), sh_pattern)
    r.set_item(_name("Pattern"), patterns)

    # /Properties — an optional-content group.
    ocg = COSDictionary()
    ocg.set_item(_name("Type"), _name("OCG"))
    ocg.set_string(_name("Name"), "layer0")
    props = COSDictionary()
    props.set_item(_name("oc0"), ocg)
    r.set_item(_name("Properties"), props)

    return r


def _font_present(res: PDResources, name: str) -> bool:
    return res.get_font(_name(name)) is not None


def _font_class(res: PDResources, name: str) -> str:
    # get_font returns a typed PDFont for both direct and indirect entries
    # (matching upstream); compare the resolved class simple-name.
    f = res.get_font(_name(name))
    return "NULL" if f is None else type(f).__name__


def _font_subtype(res: PDResources, name: str) -> str:
    f = res.get_font(_name(name))
    if f is None:
        return "NULL"
    subtype = f.get_cos_object().get_name_as_string(_name("Subtype"))
    return "NULL" if subtype is None else subtype


def _xobject_class(res: PDResources, name: str) -> str:
    # pypdfbox's get_xobject() returns the raw COS object; the typed wrapper
    # (matching Java's PDResources.getXObject) is get_x_object().
    x = res.get_x_object(_name(name))
    return "NULL" if x is None else type(x).__name__


def _cs_class(res: PDResources, name: str) -> str:
    cs = res.get_color_space(_name(name))
    return "NULL" if cs is None else type(cs).__name__


def _cs_result(res: PDResources, name: str) -> str:
    try:
        cs = res.get_color_space(_name(name))
        return "NULL" if cs is None else type(cs).__name__
    except MissingResourceException as exc:
        return f"THROW:{exc}"


def _ext_g_state_class(res: PDResources, name: str) -> str:
    gs = res.get_ext_gstate(_name(name))
    return "NULL" if gs is None else type(gs).__name__


def _shading_class(res: PDResources, name: str) -> str:
    sh = res.get_shading(_name(name))
    return "NULL" if sh is None else type(sh).__name__


def _pattern_class(res: PDResources, name: str) -> str:
    p = res.get_pattern(_name(name))
    return "NULL" if p is None else type(p).__name__


def _property_list_class(res: PDResources, name: str) -> str:
    p = res.get_properties(_name(name))
    return "NULL" if p is None else type(p).__name__


def _names(values: list[COSName]) -> list[str]:
    return sorted({n.get_name() for n in values})


def _py_dump() -> dict[str, object]:
    """Reproduce the same key->value map ResourceLookupProbe.java emits."""
    doc = PDDocument()
    try:
        res = PDResources(_build_resource_dict(), document=doc)
        return {
            "font_F0_present": _font_present(res, "F0"),
            "font_F0_class": _font_class(res, "F0"),
            "font_F0_subtype": _font_subtype(res, "F0"),
            "font_missing_present": _font_present(res, "Fx"),
            "xobject_Im0": _xobject_class(res, "Im0"),
            "xobject_Fm0": _xobject_class(res, "Fm0"),
            "xobject_missing": _xobject_class(res, "Imx"),
            "is_image_Im0": res.is_image_x_object(_name("Im0")),
            "is_image_Fm0": res.is_image_x_object(_name("Fm0")),
            "cs_csIcc": _cs_class(res, "csIcc"),
            "cs_csSep": _cs_class(res, "csSep"),
            "cs_csCal": _cs_class(res, "csCal"),
            "cs_DeviceRGB": _cs_class(res, "DeviceRGB"),
            "cs_DeviceGray": _cs_class(res, "DeviceGray"),
            "cs_DeviceCMYK": _cs_class(res, "DeviceCMYK"),
            "cs_Pattern": _cs_class(res, "Pattern"),
            "cs_missing": _cs_result(res, "csNope"),
            "gs_gs0": _ext_g_state_class(res, "gs0"),
            "gs_missing": _ext_g_state_class(res, "gsx"),
            "sh_sh0": _shading_class(res, "sh0"),
            "sh_missing": _shading_class(res, "shx"),
            "pat_p0": _pattern_class(res, "p0"),
            "pat_p1": _pattern_class(res, "p1"),
            "pat_missing": _pattern_class(res, "px"),
            "prop_oc0": _property_list_class(res, "oc0"),
            "prop_missing": _property_list_class(res, "Propx"),
            "color_space_names": _names(res.get_color_space_names()),
            "xobject_names": _names(res.get_xobject_names()),
            "font_names": _names(res.get_font_names()),
            "ext_gstate_names": _names(res.get_extgstate_names()),
            "shading_names": _names(res.get_shading_names()),
            "pattern_names": _names(res.get_pattern_names()),
            "property_names": _names(res.get_property_list_names()),
        }
    finally:
        doc.close()


@requires_oracle
def test_resource_lookup_matches_pdfbox() -> None:
    java = json.loads(run_probe_text("ResourceLookupProbe"))
    py = _py_dump()
    assert py == java, (
        "PDResources lookup surface diverges from PDFBox.\n"
        f"--- pypdfbox ---\n{json.dumps(py, indent=2, sort_keys=True)}\n"
        f"--- java ---\n{json.dumps(java, indent=2, sort_keys=True)}"
    )
