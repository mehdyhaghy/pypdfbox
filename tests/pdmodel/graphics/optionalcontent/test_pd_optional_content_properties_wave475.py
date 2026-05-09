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
    arr = _default_dict(props).get_dictionary_object(COSName.get_pdf_name(name))
    assert isinstance(arr, COSArray)
    return arr


def test_set_group_enabled_preserves_indirect_state_entry_when_moved() -> None:
    props = PDOptionalContentProperties()
    layer = PDOptionalContentGroup("Indirect State")
    props.add_group(layer)
    wrapped = COSObject(42, resolved=layer.get_cos_object())
    _default_dict(props).set_item(COSName.get_pdf_name("ON"), COSArray([wrapped]))

    assert props.is_group_enabled(layer) is True
    assert props.set_group_enabled(layer, False) is True

    assert _state_array(props, "ON").size() == 0
    off = _state_array(props, "OFF")
    assert off.size() == 1
    assert off.get(0) is wrapped
    assert props.is_group_enabled(layer) is False


def test_remove_group_prunes_nested_order_arrays_and_empty_containers() -> None:
    props = PDOptionalContentProperties()
    keep = PDOptionalContentGroup("Keep")
    doomed = PDOptionalContentGroup("Doomed")
    props.add_group(keep)
    props.add_group(doomed)
    d = _default_dict(props)
    d.set_item(
        COSName.get_pdf_name("Order"),
        COSArray(
            [
                keep.get_cos_object(),
                COSArray([COSObject(7, resolved=doomed.get_cos_object())]),
            ]
        ),
    )

    assert props.remove_group(doomed) is True

    order = d.get_dictionary_object(COSName.get_pdf_name("Order"))
    assert isinstance(order, COSArray)
    assert order.size() == 1
    assert order.get_object(0) is keep.get_cos_object()


def test_auto_state_accepts_single_category_name_and_ignores_bad_ocgs() -> None:
    props = PDOptionalContentProperties()
    layer = PDOptionalContentGroup("Layer")
    props.add_group(layer)
    props.set_base_state("OFF")
    usage = COSDictionary()
    view = COSDictionary()
    view.set_item(COSName.get_pdf_name("ViewState"), COSName.get_pdf_name("ON"))
    usage.set_item(COSName.get_pdf_name("View"), view)
    layer.get_cos_object().set_item(COSName.get_pdf_name("Usage"), usage)

    bad_ocg = COSDictionary()
    auto_state = COSDictionary()
    auto_state.set_item(COSName.get_pdf_name("Event"), COSName.get_pdf_name("View"))
    auto_state.set_item(COSName.get_pdf_name("Category"), COSName.get_pdf_name("View"))
    auto_state.set_item(
        COSName.get_pdf_name("OCGs"),
        COSArray([bad_ocg, COSObject(99, resolved=layer.get_cos_object())]),
    )
    _default_dict(props).set_item(COSName.get_pdf_name("AS"), COSArray([auto_state]))

    assert props.compute_visible_ocgs("View") == {id(layer.get_cos_object())}


def test_unmatched_name_toggle_returns_false_without_creating_state_arrays() -> None:
    props = PDOptionalContentProperties()
    props.add_group(PDOptionalContentGroup("Known"))

    assert props.set_group_enabled("Missing", True) is False

    d = _default_dict(props)
    assert d.get_dictionary_object(COSName.get_pdf_name("ON")) is None
    assert d.get_dictionary_object(COSName.get_pdf_name("OFF")) is None
