from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSInteger, COSName, COSObject
from pypdfbox.pdmodel import PDResources
from pypdfbox.pdmodel.graphics.pattern import PDTilingPattern
from pypdfbox.pdmodel.graphics.shading.pd_shading_type2 import PDShadingType2
from pypdfbox.pdmodel.pd_resource_cache import DefaultResourceCache


def _tiling_pattern() -> PDTilingPattern:
    pattern_dict = COSDictionary()
    pattern_dict.set_item(COSName.TYPE, COSName.get_pdf_name("Pattern"))  # type: ignore[attr-defined]
    pattern_dict.set_item(COSName.get_pdf_name("PatternType"), COSInteger(1))
    return PDTilingPattern(pattern_dict)


def _shading_type2() -> PDShadingType2:
    shading_dict = COSDictionary()
    shading_dict.set_item(COSName.get_pdf_name("ShadingType"), COSInteger(2))
    shading_dict.set_item(
        COSName.get_pdf_name("ColorSpace"),
        COSName.get_pdf_name("DeviceRGB"),
    )
    return PDShadingType2(shading_dict)


def test_wave686_lookup_returns_none_for_missing_category_and_resolves_entries() -> None:
    resources = PDResources()
    name = COSName.get_pdf_name("F0")

    assert resources._lookup("Font", name) is None  # noqa: SLF001

    font_dict = COSDictionary()
    resources.put(PDResources.FONT, name, font_dict)

    assert resources._lookup("Font", name) is font_dict  # noqa: SLF001


def test_wave686_get_font_returns_none_for_indirect_non_dictionary() -> None:
    resources = PDResources()
    name = COSName.get_pdf_name("F0")
    resources.put(
        PDResources.FONT,
        name,
        COSObject(10, 0, resolved=COSName.get_pdf_name("NotAFontDictionary")),
    )

    assert resources.get_font(name) is None


def test_wave686_indirect_pattern_and_shading_are_stored_in_cache() -> None:
    cache = DefaultResourceCache()
    resources = PDResources(resource_cache=cache)
    pattern_ref = COSObject(20, 0, resolved=_tiling_pattern().get_cos_object())
    shading_ref = COSObject(21, 0, resolved=_shading_type2().get_cos_object())
    pattern_name = COSName.get_pdf_name("P0")
    shading_name = COSName.get_pdf_name("Sh0")
    resources.put(PDResources.PATTERN, pattern_name, pattern_ref)
    resources.put(PDResources.SHADING, shading_name, shading_ref)

    pattern = resources.get_pattern(pattern_name)
    shading = resources.get_shading(shading_name)

    assert isinstance(pattern, PDTilingPattern)
    assert isinstance(shading, PDShadingType2)
    assert cache.get_pattern(pattern_ref) is pattern
    assert cache.get_shading(shading_ref) is shading


def test_wave686_add_infers_typed_pattern_and_shading_categories() -> None:
    resources = PDResources()

    pattern_name = resources.add(_tiling_pattern())
    shading_name = resources.add(_shading_type2())

    assert pattern_name.get_name() == "p1"
    assert shading_name.get_name() == "sh1"
    assert resources.has_pattern(pattern_name)
    assert resources.has_shading(shading_name)
