from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel.graphics.optionalcontent import (
    PDOptionalContentGroup,
    PDOptionalContentProperties,
)


def _default_dict(props: PDOptionalContentProperties) -> COSDictionary:
    raw = props.get_cos_object().get_dictionary_object(COSName.D)
    assert isinstance(raw, COSDictionary)
    return raw


def _ocgs_array(props: PDOptionalContentProperties) -> COSArray:
    raw = props.get_cos_object().get_dictionary_object(COSName.get_pdf_name("OCGs"))
    assert isinstance(raw, COSArray)
    return raw


def test_wave660_name_based_accessors_skip_malformed_ocg_entries() -> None:
    props = PDOptionalContentProperties()
    layer = PDOptionalContentGroup("Layer")
    ocgs = _ocgs_array(props)
    ocgs.add(COSName.get_pdf_name("bad"))
    ocgs.add(layer.get_cos_object())

    assert props.get_group("Layer").get_cos_object() is layer.get_cos_object()
    assert props.remove_group("Missing") is False
    assert props.is_group_enabled("Missing") is False
    assert props.set_group_enabled("Missing", True) is False


def test_wave660_radio_button_enforcement_skips_junk_and_moves_sibling_off() -> None:
    props = PDOptionalContentProperties()
    red = PDOptionalContentGroup("Red")
    blue = PDOptionalContentGroup("Blue")
    props.add_group(red)
    props.add_group(blue)
    props.set_group_enabled(red, True)
    props.set_group_enabled(blue, True)

    rbgroup = COSArray(
        [COSName.get_pdf_name("junk"), red.get_cos_object(), blue.get_cos_object()]
    )
    rbgroups = COSArray([COSName.get_pdf_name("not-an-array"), rbgroup])
    _default_dict(props).set_item(COSName.get_pdf_name("RBGroups"), rbgroups)

    assert props.set_group_enabled(blue, True) is True

    assert props.is_group_enabled(blue) is True
    assert props.is_group_enabled(red) is False


def test_wave660_base_state_falls_back_when_default_dict_returns_none() -> None:
    class DefaultDict:
        def get_name(self, key: COSName, default: str) -> None:
            assert key == COSName.get_pdf_name("BaseState")
            assert default == "ON"
            return None

    class Props(PDOptionalContentProperties):
        def _get_d(self) -> DefaultDict:  # type: ignore[override]
            return DefaultDict()

    assert Props().get_base_state() == "ON"


def test_wave660_compute_visible_ocgs_without_auto_state_returns_base_visibility() -> None:
    props = PDOptionalContentProperties()
    layer = PDOptionalContentGroup("Layer")
    props.add_group(layer)

    assert props.compute_visible_ocgs("Print") == {id(layer.get_cos_object())}


def test_wave660_auto_state_skips_bad_ocg_entries_and_invalid_group_dicts() -> None:
    props = PDOptionalContentProperties()
    visible_layer = PDOptionalContentGroup("Visible")
    props.add_group(visible_layer)

    usage = COSDictionary()
    view = COSDictionary()
    view.set_item(COSName.get_pdf_name("ViewState"), COSName.get_pdf_name("OFF"))
    usage.set_item(COSName.get_pdf_name("View"), view)
    visible_layer.get_cos_object().set_item(COSName.get_pdf_name("Usage"), usage)

    invalid_group = COSDictionary()
    invalid_group.set_item(COSName.TYPE, COSName.get_pdf_name("NotOCG"))

    auto_state = COSDictionary()
    auto_state.set_item(COSName.get_pdf_name("Event"), COSName.get_pdf_name("View"))
    auto_state.set_item(COSName.get_pdf_name("Category"), COSName.get_pdf_name("View"))
    auto_state.set_item(
        COSName.get_pdf_name("OCGs"),
        COSArray(
            [
                COSName.get_pdf_name("bad"),
                invalid_group,
                visible_layer.get_cos_object(),
            ]
        ),
    )
    _default_dict(props).set_item(COSName.get_pdf_name("AS"), COSArray([auto_state]))

    assert props.compute_visible_ocgs("View") == set()
