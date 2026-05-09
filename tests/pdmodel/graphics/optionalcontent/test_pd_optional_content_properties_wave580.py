from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.cos.cos_object import COSObject
from pypdfbox.pdmodel.graphics.optionalcontent import (
    PDOptionalContentGroup,
    PDOptionalContentProperties,
)


def _default_dict(props: PDOptionalContentProperties) -> COSDictionary:
    raw = props.get_cos_object().get_dictionary_object(COSName.D)
    assert isinstance(raw, COSDictionary)
    return raw


def _state_array(props: PDOptionalContentProperties, name: str) -> COSArray:
    raw = _default_dict(props).get_dictionary_object(COSName.get_pdf_name(name))
    assert isinstance(raw, COSArray)
    return raw


def test_wave580_get_groups_repairs_malformed_ocgs_entry() -> None:
    raw = COSDictionary()
    raw.set_item(COSName.get_pdf_name("OCGs"), COSName.get_pdf_name("bad"))
    props = PDOptionalContentProperties(raw)

    assert props.get_groups() == []

    repaired = props.get_cos_object().get_dictionary_object(COSName.get_pdf_name("OCGs"))
    assert isinstance(repaired, COSArray)
    assert repaired.size() == 0


def test_wave580_set_group_enabled_replaces_malformed_state_arrays() -> None:
    props = PDOptionalContentProperties()
    layer = PDOptionalContentGroup("Layer")
    props.add_group(layer)
    d = _default_dict(props)
    d.set_item(COSName.get_pdf_name("ON"), COSName.get_pdf_name("not-array"))
    d.set_item(COSName.get_pdf_name("OFF"), COSName.get_pdf_name("not-array"))

    assert props.set_group_enabled(layer, False) is False

    assert _state_array(props, "ON").size() == 0
    off = _state_array(props, "OFF")
    assert off.size() == 1
    assert off.get_object(0) is layer.get_cos_object()


def test_wave580_remove_group_scrubs_indirect_on_and_off_entries() -> None:
    props = PDOptionalContentProperties()
    layer = PDOptionalContentGroup("Layer")
    props.add_group(layer)
    wrapped_on = COSObject(20, resolved=layer.get_cos_object())
    wrapped_off = COSObject(21, resolved=layer.get_cos_object())
    d = _default_dict(props)
    d.set_item(COSName.get_pdf_name("ON"), COSArray([wrapped_on]))
    d.set_item(COSName.get_pdf_name("OFF"), COSArray([wrapped_off]))

    assert props.remove_group(layer) is True

    assert props.get_groups() == []
    assert _state_array(props, "ON").size() == 0
    assert _state_array(props, "OFF").size() == 0
