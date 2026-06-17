"""Wave 1582 — PDResources typed-accessor / cache / named-colorspace fuzz.

Hammers ``PDResources`` resolution against PDFBox 3.0.7
``org.apache.pdfbox.pdmodel.PDResources`` behaviour:

- the typed accessors (``get_font`` / ``get_x_object`` / ``get_color_space`` /
  ``get_ext_gstate`` / ``get_pattern`` / ``get_shading`` / ``get_properties``)
  hit a typed wrapper or return ``None`` for a miss;
- the resource cache returns the *same* instance for repeated indirect-ref
  lookups (identity caching, upstream's SoftReference map);
- the built-in colour-space names (DeviceGray/RGB/CMYK/Pattern) resolve even
  when NOT present in ``/ColorSpace`` (the ``COSName`` branch of
  ``PDColorSpace.create``);
- ``add_*`` mints a fresh 1-based ``<prefix><n>`` key and re-uses the existing
  key for an already-registered COS object (upstream ``createKey`` parity);
- the ``get_*_names`` accessors list the COSName keys and return ``[]`` for an
  absent sub-dictionary;
- a tiling (PatternType 1) vs shading (PatternType 2) pattern dispatch.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSInteger,
    COSName,
    COSObject,
    COSStream,
)
from pypdfbox.pdmodel import PDDocument, PDResources
from pypdfbox.pdmodel.font import PDFont, PDType1Font
from pypdfbox.pdmodel.graphics.color import PDColorSpace
from pypdfbox.pdmodel.graphics.color.pd_device_cmyk import PDDeviceCMYK
from pypdfbox.pdmodel.graphics.color.pd_device_gray import PDDeviceGray
from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB
from pypdfbox.pdmodel.graphics.pattern import PDAbstractPattern
from pypdfbox.pdmodel.graphics.pattern.pd_shading_pattern import PDShadingPattern
from pypdfbox.pdmodel.graphics.pattern.pd_tiling_pattern import PDTilingPattern
from pypdfbox.pdmodel.graphics.pd_property_list import PDPropertyList
from pypdfbox.pdmodel.graphics.shading import PDShading
from pypdfbox.pdmodel.graphics.state import PDExtendedGraphicsState
from pypdfbox.pdmodel.missing_resource_exception import MissingResourceException

_FONT = COSName.get_pdf_name("Font")
_XOBJECT = COSName.get_pdf_name("XObject")
_COLOR_SPACE = COSName.get_pdf_name("ColorSpace")
_EXT_GSTATE = COSName.get_pdf_name("ExtGState")
_PATTERN = COSName.get_pdf_name("Pattern")
_SHADING = COSName.get_pdf_name("Shading")
_PROPERTIES = COSName.get_pdf_name("Properties")


def _name(s: str) -> COSName:
    return COSName.get_pdf_name(s)


# ---------- COS dictionary builders ----------


def _type1_font_dict(base_font: str = "Helvetica") -> COSDictionary:
    d = COSDictionary()
    d.set_name(COSName.TYPE, "Font")  # type: ignore[attr-defined]
    d.set_name(COSName.SUBTYPE, "Type1")  # type: ignore[attr-defined]
    d.set_name(COSName.BASE_FONT, base_font)  # type: ignore[attr-defined]
    return d


def _form_xobject_stream() -> COSStream:
    s = COSStream()
    s.set_name(COSName.TYPE, "XObject")  # type: ignore[attr-defined]
    s.set_name(COSName.SUBTYPE, "Form")  # type: ignore[attr-defined]
    return s


def _image_xobject_stream() -> COSStream:
    s = COSStream()
    s.set_name(COSName.TYPE, "XObject")  # type: ignore[attr-defined]
    s.set_name(COSName.SUBTYPE, "Image")  # type: ignore[attr-defined]
    s.set_int(COSName.get_pdf_name("Width"), 1)
    s.set_int(COSName.get_pdf_name("Height"), 1)
    return s


def _ext_gstate_dict() -> COSDictionary:
    d = COSDictionary()
    d.set_name(COSName.TYPE, "ExtGState")  # type: ignore[attr-defined]
    return d


def _tiling_pattern_dict() -> COSStream:
    # PatternType 1 == tiling. Tiling patterns are content streams.
    s = COSStream()
    s.set_name(COSName.TYPE, "Pattern")  # type: ignore[attr-defined]
    s.set_int(COSName.get_pdf_name("PatternType"), 1)
    s.set_int(COSName.get_pdf_name("PaintType"), 1)
    s.set_int(COSName.get_pdf_name("TilingType"), 1)
    return s


def _shading_pattern_dict() -> COSDictionary:
    d = COSDictionary()
    d.set_name(COSName.TYPE, "Pattern")  # type: ignore[attr-defined]
    d.set_int(COSName.get_pdf_name("PatternType"), 2)
    shading = COSDictionary()
    shading.set_int(COSName.get_pdf_name("ShadingType"), 2)
    d.set_item(_SHADING, shading)
    return d


def _shading_dict(shading_type: int = 2) -> COSDictionary:
    d = COSDictionary()
    d.set_int(COSName.get_pdf_name("ShadingType"), shading_type)
    return d


def _property_list_dict() -> COSDictionary:
    d = COSDictionary()
    d.set_name(COSName.TYPE, "OCG")  # type: ignore[attr-defined]
    d.set_name(COSName.get_pdf_name("Name"), "layer")
    return d


# ============================================================================
# Empty / absent sub-dictionaries — every miss is None / empty, never raising.
# ============================================================================


def test_all_typed_getters_none_on_empty_resources() -> None:
    res = PDResources()
    n = _name("X")
    assert res.get_font(n) is None
    assert res.get_x_object(n) is None
    assert res.get_ext_gstate(n) is None
    assert res.get_pattern(n) is None
    assert res.get_shading(n) is None
    assert res.get_properties(n) is None


def test_all_name_iterators_empty_on_absent_subdict() -> None:
    res = PDResources()
    assert res.get_font_names() == []
    assert res.get_xobject_names() == []
    assert res.get_color_space_names() == []
    assert res.get_extgstate_names() == []
    assert res.get_pattern_names() == []
    assert res.get_shading_names() == []
    assert res.get_property_list_names() == []


def test_color_space_miss_for_unknown_bare_name_raises_missing_resource() -> None:
    # Upstream: PDColorSpace.create's COSName branch throws
    # MissingException("Unknown color space..." ) for a non-builtin name with
    # no /ColorSpace entry.
    res = PDResources()
    with pytest.raises(MissingResourceException):
        res.get_color_space(_name("NotAColorSpace"))


# ============================================================================
# Built-in colour-space names resolve even without a /ColorSpace entry.
# ============================================================================


@pytest.mark.parametrize(
    ("device_name", "singleton"),
    [
        ("DeviceGray", PDDeviceGray.INSTANCE),
        ("DeviceRGB", PDDeviceRGB.INSTANCE),
        ("DeviceCMYK", PDDeviceCMYK.INSTANCE),
    ],
)
def test_builtin_device_colorspace_resolved_when_absent(
    device_name: str, singleton: PDColorSpace
) -> None:
    res = PDResources()
    assert res.get_color_space_names() == []
    cs = res.get_color_space(_name(device_name))
    assert cs is singleton


def test_builtin_pattern_colorspace_resolved_when_absent() -> None:
    res = PDResources()
    cs = res.get_color_space(_name("Pattern"))
    assert cs is not None
    assert cs.get_name() == "Pattern"


def test_named_colorspace_in_dict_as_cosname_resolves_to_device() -> None:
    # A /ColorSpace entry whose value is itself a COSName /DeviceRGB.
    res = PDResources()
    res.put(_COLOR_SPACE, _name("CS0"), _name("DeviceRGB"))
    cs = res.get_color_space(_name("CS0"))
    assert cs is PDDeviceRGB.INSTANCE
    assert _name("CS0") in res.get_color_space_names()


def test_default_override_redirects_device_to_default_entry() -> None:
    # PDF 32000-1 8.6.5.6: a DeviceRGB reference picks up /DefaultRGB when the
    # resource dict defines it (an ICCBased array here). Upstream getColorSpace.
    res = PDResources()
    icc_array = COSArray()
    icc_array.add(_name("ICCBased"))
    icc_stream = COSStream()
    icc_stream.set_int(_name("N"), 3)
    icc_array.add(icc_stream)
    res.put(_COLOR_SPACE, _name("DefaultRGB"), icc_array)
    cs = res.get_color_space(_name("DeviceRGB"))
    # Resolves to the Default override (not the bare device singleton).
    assert cs is not None
    assert cs is not PDDeviceRGB.INSTANCE


# ============================================================================
# Font typed accessor — hit / miss / non-dict.
# ============================================================================


def test_get_font_direct_hit_typed() -> None:
    res = PDResources()
    res.put(_FONT, _name("F1"), _type1_font_dict())
    font = res.get_font(_name("F1"))
    assert isinstance(font, PDType1Font)


def test_get_font_non_dictionary_is_none() -> None:
    res = PDResources()
    res.put(_FONT, _name("Bad"), COSInteger.get(7))
    assert res.get_font(_name("Bad")) is None


def test_get_font_indirect_identity_via_cache() -> None:
    doc = PDDocument()
    try:
        res = PDResources(document=doc)
        ref = COSObject(101, 0, resolved=_type1_font_dict())
        res.put(_FONT, _name("F1"), ref)
        a = res.get_font(_name("F1"))
        b = res.get_font(_name("F1"))
        assert isinstance(a, PDFont)
        assert a is b
    finally:
        doc.close()


# ============================================================================
# XObject typed accessor — form / image / miss / non-stream.
# ============================================================================


def test_get_x_object_form_typed() -> None:
    from pypdfbox.pdmodel.graphics.form.pd_form_x_object import PDFormXObject

    res = PDResources()
    res.put(_XOBJECT, _name("Fm0"), _form_xobject_stream())
    xobj = res.get_x_object(_name("Fm0"))
    assert isinstance(xobj, PDFormXObject)


def test_get_x_object_image_typed() -> None:
    from pypdfbox.pdmodel.graphics.image.pd_image_x_object import PDImageXObject

    res = PDResources()
    res.put(_XOBJECT, _name("Im0"), _image_xobject_stream())
    xobj = res.get_x_object(_name("Im0"))
    assert isinstance(xobj, PDImageXObject)


def test_get_x_object_miss_none() -> None:
    res = PDResources()
    assert res.get_x_object(_name("nope")) is None


def test_get_x_object_non_stream_raises_oserror() -> None:
    # Upstream PDXObject.createXObject throws IOException for a non-stream
    # /XObject entry; pypdfbox mirrors with OSError.
    res = PDResources()
    res.put(_XOBJECT, _name("Bad"), COSDictionary())
    with pytest.raises(OSError):
        res.get_x_object(_name("Bad"))


def test_get_x_object_string_name_accepted() -> None:
    from pypdfbox.pdmodel.graphics.form.pd_form_x_object import PDFormXObject

    res = PDResources()
    res.put(_XOBJECT, _name("Fm0"), _form_xobject_stream())
    assert isinstance(res.get_x_object("Fm0"), PDFormXObject)


def test_get_x_object_indirect_cache_identity() -> None:
    doc = PDDocument()
    try:
        res = PDResources(document=doc)
        ref = COSObject(55, 0, resolved=_form_xobject_stream())
        res.put(_XOBJECT, _name("Fm0"), ref)
        a = res.get_x_object(_name("Fm0"))
        b = res.get_x_object(_name("Fm0"))
        assert a is b
    finally:
        doc.close()


# ============================================================================
# ExtGState / Properties typed accessors.
# ============================================================================


def test_get_ext_gstate_hit_and_miss() -> None:
    res = PDResources()
    res.put(_EXT_GSTATE, _name("GS0"), _ext_gstate_dict())
    assert isinstance(res.get_ext_gstate(_name("GS0")), PDExtendedGraphicsState)
    assert res.get_ext_gstate(_name("absent")) is None


def test_get_ext_gstate_non_dict_is_none() -> None:
    res = PDResources()
    res.put(_EXT_GSTATE, _name("Bad"), COSInteger.get(1))
    assert res.get_ext_gstate(_name("Bad")) is None


def test_get_ext_gstate_indirect_cache_identity() -> None:
    doc = PDDocument()
    try:
        res = PDResources(document=doc)
        ref = COSObject(60, 0, resolved=_ext_gstate_dict())
        res.put(_EXT_GSTATE, _name("GS0"), ref)
        assert res.get_ext_gstate(_name("GS0")) is res.get_ext_gstate(_name("GS0"))
    finally:
        doc.close()


def test_get_properties_hit_and_miss() -> None:
    res = PDResources()
    res.put(_PROPERTIES, _name("MC0"), _property_list_dict())
    assert isinstance(res.get_properties(_name("MC0")), PDPropertyList)
    assert res.get_properties(_name("absent")) is None


def test_get_properties_non_dict_is_none() -> None:
    res = PDResources()
    res.put(_PROPERTIES, _name("Bad"), COSInteger.get(2))
    assert res.get_properties(_name("Bad")) is None


# ============================================================================
# Pattern typed accessor — tiling vs shading, miss, cache.
# ============================================================================


def test_get_pattern_tiling_type1() -> None:
    res = PDResources()
    res.put(_PATTERN, _name("P0"), _tiling_pattern_dict())
    pat = res.get_pattern(_name("P0"))
    assert isinstance(pat, PDTilingPattern)
    assert pat.get_pattern_type() == PDAbstractPattern.TYPE_TILING_PATTERN


def test_get_pattern_shading_type2() -> None:
    res = PDResources()
    res.put(_PATTERN, _name("P1"), _shading_pattern_dict())
    pat = res.get_pattern(_name("P1"))
    assert isinstance(pat, PDShadingPattern)
    assert pat.get_pattern_type() == PDAbstractPattern.TYPE_SHADING_PATTERN


def test_get_pattern_miss_none() -> None:
    res = PDResources()
    assert res.get_pattern(_name("nope")) is None


def test_get_pattern_non_dict_none() -> None:
    res = PDResources()
    res.put(_PATTERN, _name("Bad"), COSInteger.get(9))
    assert res.get_pattern(_name("Bad")) is None


def test_get_pattern_indirect_cache_identity() -> None:
    doc = PDDocument()
    try:
        res = PDResources(document=doc)
        ref = COSObject(70, 0, resolved=_tiling_pattern_dict())
        res.put(_PATTERN, _name("P0"), ref)
        assert res.get_pattern(_name("P0")) is res.get_pattern(_name("P0"))
    finally:
        doc.close()


# ============================================================================
# Shading typed accessor.
# ============================================================================


def test_get_shading_hit_typed() -> None:
    res = PDResources()
    res.put(_SHADING, _name("Sh0"), _shading_dict(2))
    sh = res.get_shading(_name("Sh0"))
    assert isinstance(sh, PDShading)
    assert sh.get_shading_type() == 2


def test_get_shading_miss_none() -> None:
    res = PDResources()
    assert res.get_shading(_name("nope")) is None


def test_get_shading_non_dict_none() -> None:
    res = PDResources()
    res.put(_SHADING, _name("Bad"), COSInteger.get(4))
    assert res.get_shading(_name("Bad")) is None


def test_get_shading_indirect_cache_identity() -> None:
    doc = PDDocument()
    try:
        res = PDResources(document=doc)
        ref = COSObject(80, 0, resolved=_shading_dict(2))
        res.put(_SHADING, _name("Sh0"), ref)
        assert res.get_shading(_name("Sh0")) is res.get_shading(_name("Sh0"))
    finally:
        doc.close()


# ============================================================================
# Colour-space cache identity (and the "Pattern" never-cached exclusion).
# ============================================================================


def test_get_color_space_indirect_cache_identity() -> None:
    doc = PDDocument()
    try:
        res = PDResources(document=doc)
        icc_array = COSArray()
        icc_array.add(_name("ICCBased"))
        icc_stream = COSStream()
        icc_stream.set_int(_name("N"), 3)
        icc_array.add(icc_stream)
        ref = COSObject(90, 0, resolved=icc_array)
        res.put(_COLOR_SPACE, _name("CS0"), ref)
        a = res.get_color_space(_name("CS0"))
        b = res.get_color_space(_name("CS0"))
        assert a is not None
        assert a is b
    finally:
        doc.close()


# ============================================================================
# add_*/add — fresh 1-based key, re-use of existing COS object key.
# ============================================================================


def test_add_x_object_form_mints_form_key() -> None:
    from pypdfbox.pdmodel.graphics.form.pd_form_x_object import PDFormXObject

    res = PDResources()
    form = PDFormXObject(_form_xobject_stream())
    key = res.add_x_object(form)
    assert str(key.get_name()).startswith("Form")
    assert key.get_name() == "Form1"


def test_add_x_object_image_mints_im_key() -> None:
    from pypdfbox.pdmodel.graphics.image.pd_image_x_object import PDImageXObject

    res = PDResources()
    img = PDImageXObject(_image_xobject_stream(), res)
    key = res.add_x_object(img)
    assert key.get_name() == "Im1"


def test_add_x_object_reuses_existing_key_for_same_cos() -> None:
    from pypdfbox.pdmodel.graphics.form.pd_form_x_object import PDFormXObject

    res = PDResources()
    form = PDFormXObject(_form_xobject_stream())
    first = res.add_x_object(form)
    second = res.add_x_object(form)
    assert first == second
    assert res.get_xobject_names() == [first]


def test_add_font_typed_overload_mints_f_key() -> None:
    res = PDResources()
    font = PDType1Font(_type1_font_dict())
    key = res.add(font)
    assert key.get_name().startswith("F")
    assert isinstance(res.get_font(key), PDFont)


def test_create_key_is_one_based_not_smallest_free() -> None:
    # Upstream createKey seeds n at keySet().size() and pre-increments, so a
    # sub-dict holding only {gs5} (size 1) yields gs2, NOT gs1.
    res = PDResources()
    res.put(_EXT_GSTATE, _name("gs5"), _ext_gstate_dict())
    key = res.create_key(_EXT_GSTATE, "gs")
    assert key.get_name() == "gs2"


def test_create_key_fresh_subdict_is_one() -> None:
    res = PDResources()
    key = res.create_key(_EXT_GSTATE, "gs")
    assert key.get_name() == "gs1"


# ============================================================================
# get_*_names returns only the COSName keys present.
# ============================================================================


def test_name_iterators_list_keys() -> None:
    res = PDResources()
    res.put(_FONT, _name("F1"), _type1_font_dict())
    res.put(_FONT, _name("F2"), _type1_font_dict())
    res.put(_XOBJECT, _name("Im0"), _image_xobject_stream())
    res.put(_COLOR_SPACE, _name("CS0"), _name("DeviceRGB"))
    res.put(_PATTERN, _name("P0"), _tiling_pattern_dict())
    res.put(_SHADING, _name("Sh0"), _shading_dict())
    res.put(_PROPERTIES, _name("MC0"), _property_list_dict())
    res.put(_EXT_GSTATE, _name("GS0"), _ext_gstate_dict())

    assert set(res.get_font_names()) == {_name("F1"), _name("F2")}
    assert res.get_xobject_names() == [_name("Im0")]
    assert res.get_color_space_names() == [_name("CS0")]
    assert res.get_pattern_names() == [_name("P0")]
    assert res.get_shading_names() == [_name("Sh0")]
    assert res.get_property_list_names() == [_name("MC0")]
    assert res.get_extgstate_names() == [_name("GS0")]
    # every listed key is a COSName
    assert all(isinstance(k, COSName) for k in res.get_font_names())


def test_get_names_generic_dispatch() -> None:
    res = PDResources()
    res.put(_FONT, _name("F1"), _type1_font_dict())
    assert res.get_names(_FONT) == [_name("F1")]
    assert res.get_names(_name("XObject")) == []


# ============================================================================
# Cache is genuinely consulted: pre-seeding it short-circuits the lookup.
# ============================================================================


def test_cache_seeded_instance_returned_without_rewrap() -> None:
    from pypdfbox.pdmodel.pd_resource_cache import DefaultResourceCache

    cache = DefaultResourceCache()
    res = PDResources(resource_cache=cache)
    ref = COSObject(200, 0, resolved=_ext_gstate_dict())
    res.put(_EXT_GSTATE, _name("GS0"), ref)
    sentinel = PDExtendedGraphicsState(COSDictionary())
    cache.put_ext_g_state(ref, sentinel)
    # The seeded sentinel comes straight back; no re-wrap of the real dict.
    assert res.get_ext_gstate(_name("GS0")) is sentinel


def test_get_resource_cache_accessor() -> None:
    from pypdfbox.pdmodel.pd_resource_cache import DefaultResourceCache

    cache = DefaultResourceCache()
    res = PDResources(resource_cache=cache)
    assert res.get_resource_cache() is cache
    assert PDResources().get_resource_cache() is None
