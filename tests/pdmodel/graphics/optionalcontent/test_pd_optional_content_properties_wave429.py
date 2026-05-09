from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.cos.cos_object import COSObject
from pypdfbox.pdmodel.graphics.optionalcontent import (
    PDOptionalContentConfiguration,
    PDOptionalContentGroup,
    PDOptionalContentProperties,
)


def _dict_group(name: str) -> COSDictionary:
    group = PDOptionalContentGroup(name)
    return group.get_cos_object()


def test_groups_and_counts_resolve_indirect_entries_and_skip_junk() -> None:
    props = PDOptionalContentProperties()
    ocgs = props.get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("OCGs")
    )
    assert isinstance(ocgs, COSArray)
    layer = _dict_group("Indirect")
    ocgs.add(COSObject(7, resolved=layer))
    ocgs.add(COSName.get_pdf_name("not-a-dictionary"))

    groups = props.get_groups()

    assert [group.get_name() for group in groups] == ["Indirect"]
    assert props.get_optional_content_groups()[0].get_name() == "Indirect"
    assert props.get_group_count() == 1
    assert len(props) == 1
    assert props.has_groups() is True


def test_missing_ocgs_and_default_configuration_are_recreated() -> None:
    raw = COSDictionary()
    props = PDOptionalContentProperties(raw)

    assert props.get_groups() == []
    default = props.get_default_configuration()

    assert isinstance(raw.get_dictionary_object(COSName.get_pdf_name("OCGs")), COSArray)
    assert default.get_name() == "Top"
    assert props.get_base_state() == "ON"
    assert props.has_groups() is False


def test_auto_state_uses_first_non_unchanged_category_for_destination() -> None:
    props = PDOptionalContentProperties()
    layer = PDOptionalContentGroup("Layer")
    props.add_group(layer)
    props.set_hidden(layer)

    usage = COSDictionary()
    view = COSDictionary()
    view.set_item(COSName.get_pdf_name("ViewState"), COSName.get_pdf_name("ON"))
    export = COSDictionary()
    export.set_item(
        COSName.get_pdf_name("ExportState"), COSName.get_pdf_name("OFF")
    )
    usage.set_item(COSName.get_pdf_name("View"), view)
    usage.set_item(COSName.get_pdf_name("Export"), export)
    layer.get_cos_object().set_item(COSName.get_pdf_name("Usage"), usage)

    default = props.get_cos_object().get_dictionary_object(COSName.D)
    assert isinstance(default, COSDictionary)
    auto_state = COSDictionary()
    auto_state.set_item(COSName.get_pdf_name("Event"), COSName.get_pdf_name("View"))
    auto_state.set_item(
        COSName.get_pdf_name("Category"),
        COSArray(
            [
                COSName.get_pdf_name("Export"),
                COSName.get_pdf_name("View"),
            ]
        ),
    )
    auto_state.set_item(
        COSName.get_pdf_name("OCGs"),
        COSArray([COSObject(9, resolved=layer.get_cos_object())]),
    )
    default.set_item(COSName.get_pdf_name("AS"), COSArray([auto_state]))

    assert props.compute_visible_ocgs("View") == {id(layer.get_cos_object())}
    assert props.compute_visible_ocgs("Print") == set()


def test_add_configuration_accepts_raw_dictionary_and_resolves_indirect() -> None:
    props = PDOptionalContentProperties()
    config_dict = COSDictionary()
    config_dict.set_string(COSName.get_pdf_name("Name"), "Alt")

    returned = props.add_configuration(config_dict)

    assert isinstance(returned, PDOptionalContentConfiguration)
    assert returned.get_name() == "Alt"
    assert props.has_configuration("Alt") is True
    assert props.get_configuration("Alt").get_cos_object() is config_dict

    configs = props.get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("Configs")
    )
    assert isinstance(configs, COSArray)
    configs.add(COSObject(11, resolved=config_dict))
    configs.add(COSName.get_pdf_name("junk"))

    assert props.get_configuration_names() == ["Alt", "Alt"]
    assert len(props.get_configurations()) == 2
    assert props.has_configuration("Missing") is False


def test_add_configuration_rejects_unsupported_object() -> None:
    props = PDOptionalContentProperties()
    with pytest.raises(TypeError, match="config must be"):
        props.add_configuration(object())  # type: ignore[arg-type]
