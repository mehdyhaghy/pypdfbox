from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSName, COSObject, COSStream
from pypdfbox.pdmodel import PDPage, PDResources
from pypdfbox.pdmodel.graphics.color import PDDeviceRGB
from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_group import (
    PDOptionalContentGroup,
)


class RecordingResourceCache:
    def __init__(self) -> None:
        self.calls: list[tuple[str, COSObject]] = []

    def remove_color_space(self, obj: COSObject) -> None:
        self.calls.append(("ColorSpace", obj))

    def remove_ext_state(self, obj: COSObject) -> None:
        self.calls.append(("ExtGState", obj))

    def remove_pattern(self, obj: COSObject) -> None:
        self.calls.append(("Pattern", obj))

    def remove_properties(self, obj: COSObject) -> None:
        self.calls.append(("Properties", obj))

    def remove_shading(self, obj: COSObject) -> None:
        self.calls.append(("Shading", obj))

    def remove_font(self, obj: COSObject) -> None:
        self.calls.append(("Font", obj))

    def remove_x_object(self, obj: COSObject) -> None:
        self.calls.append(("XObject", obj))


def test_page_remove_resource_cache_clears_only_own_indirect_resources() -> None:
    page = PDPage()
    cache = RecordingResourceCache()
    page.set_resource_cache(cache)

    resources = COSDictionary()
    indirect_by_kind: dict[str, COSObject] = {}
    for index, kind in enumerate(
        ["ColorSpace", "ExtGState", "Pattern", "Properties", "Shading", "Font", "XObject"],
        start=1,
    ):
        subdict = COSDictionary()
        indirect = COSObject(index, 0, resolved=COSDictionary())
        indirect_by_kind[kind] = indirect
        subdict.set_item(COSName.get_pdf_name(f"{kind}Indirect"), indirect)
        subdict.set_item(COSName.get_pdf_name(f"{kind}Direct"), COSDictionary())
        resources.set_item(COSName.get_pdf_name(kind), subdict)
    page.set_resources(resources)

    page.remove_page_resource_from_cache()

    assert cache.calls == [(kind, indirect_by_kind[kind]) for kind in indirect_by_kind]


def test_page_remove_resource_cache_noops_without_own_resource_dictionary() -> None:
    page = PDPage()
    parent = COSDictionary()
    parent.set_item(COSName.RESOURCES, COSDictionary())  # type: ignore[attr-defined]
    page.get_cos_object().set_item(COSName.PARENT, parent)  # type: ignore[attr-defined]
    cache = RecordingResourceCache()
    page.set_resource_cache(cache)

    page.remove_page_resource_from_cache()

    assert cache.calls == []


def test_page_viewports_accept_raw_dictionary_and_wrappers_then_clear() -> None:
    class ViewportWrapper:
        def __init__(self, cos: COSDictionary) -> None:
            self._cos = cos

        def get_cos_object(self) -> COSDictionary:
            return self._cos

    first = COSDictionary()
    first.set_name("Name", "raw")
    second = COSDictionary()
    second.set_name("Name", "wrapped")
    page = PDPage()

    page.set_viewports([first, ViewportWrapper(second)])

    resolved = page.get_viewports()
    assert resolved is not None
    assert [vp.get_cos_object().get_name("Name") for vp in resolved] == [
        "raw",
        "wrapped",
    ]
    assert page.has_viewports()

    page.set_viewports(None)
    assert page.get_viewports() is None
    assert not page.has_viewports()


def test_page_viewports_reject_non_dictionary_wrappers() -> None:
    class BadViewportWrapper:
        def get_cos_object(self) -> COSName:
            return COSName.get_pdf_name("NotADictionary")

    with pytest.raises(TypeError, match="set_viewports entries"):
        PDPage().set_viewports([BadViewportWrapper()])


def test_page_transition_effect_alias_and_clear_with_duration() -> None:
    class Transition:
        def __init__(self) -> None:
            self.cos = COSDictionary()
            self.cos.set_name("S", "Fade")

        def get_cos_object(self) -> COSDictionary:
            return self.cos

    page = PDPage()
    page.set_transition_effect(Transition())

    assert page.has_transition()
    assert page.get_transition_effect().get_style() == "Fade"

    page.set_transition(None, duration=2.5)

    assert not page.has_transition()
    assert page.get_duration() == 2.5


def test_resources_default_device_color_space_uses_configured_default() -> None:
    res = PDResources()
    res.put(PDResources.COLOR_SPACE, COSName.get_pdf_name("DefaultRGB"), PDDeviceRGB.INSTANCE)

    color_space = res.get_color_space(COSName.get_pdf_name("DeviceRGB"))

    assert color_space is PDDeviceRGB.INSTANCE


def test_resources_color_space_reentry_guard_returns_none() -> None:
    res = PDResources()
    name = COSName.get_pdf_name("CS0")
    res.put(PDResources.COLOR_SPACE, name, COSName.get_pdf_name("DeviceRGB"))

    res._resolving_color_spaces.add(name)
    assert res.get_color_space(name) is None


def test_resources_add_optional_content_group_uses_oc_prefix() -> None:
    res = PDResources()
    group = PDOptionalContentGroup("Layer 1")

    name = res.add(group)

    assert name.get_name() == "oc1"
    assert res.get_property_list(name).get_cos_object() is group.get_cos_object()


def test_resources_cos_value_rejects_wrapper_returning_non_cos() -> None:
    class BadResource:
        def get_cos_object(self) -> object:
            return object()

    with pytest.raises(TypeError, match="not COS-backed"):
        PDResources().add(PDResources.XOBJECT, BadResource())


def test_resources_create_key_seeds_from_size() -> None:
    # createKey seeds the counter to keySet().size() (here 2) and
    # pre-increments to 3, so a dict already holding {Im0, Im1} yields Im3.
    subdict = COSDictionary()
    subdict.set_item(COSName.get_pdf_name("Im0"), COSStream())
    subdict.set_item(COSName.get_pdf_name("Im1"), COSStream())

    assert PDResources._create_key(subdict, "Im").get_name() == "Im3"
