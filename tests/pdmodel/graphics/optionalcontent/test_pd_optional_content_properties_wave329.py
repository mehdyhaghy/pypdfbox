from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel.graphics.optionalcontent import (
    PDOptionalContentGroup,
    PDOptionalContentProperties,
)

_D = COSName.get_pdf_name("D")
_OFF = COSName.get_pdf_name("OFF")
_ORDER = COSName.get_pdf_name("Order")


def test_wave329_remove_group_scrubs_nested_order_hierarchy() -> None:
    props = PDOptionalContentProperties()
    first = PDOptionalContentGroup("First")
    removed = PDOptionalContentGroup("Removed")
    last = PDOptionalContentGroup("Last")
    for group in (first, removed, last):
        props.add_group(group)

    d = props.get_cos_object().get_dictionary_object(_D)
    assert isinstance(d, COSDictionary)
    nested = COSArray()
    nested.add(first.get_cos_object())
    nested.add(removed.get_cos_object())
    order = COSArray()
    order.add(nested)
    order.add(last.get_cos_object())
    d.set_item(_ORDER, order)

    props.set_hidden(removed)

    assert props.remove_group(removed) is True

    assert props.get_group_names() == ["First", "Last"]
    raw_order = d.get_dictionary_object(_ORDER)
    assert isinstance(raw_order, COSArray)
    raw_nested = raw_order.get_object(0)
    assert isinstance(raw_nested, COSArray)
    assert raw_nested.size() == 1
    assert raw_nested.get_object(0) is first.get_cos_object()
    assert raw_order.get_object(1) is last.get_cos_object()

    off = d.get_dictionary_object(_OFF)
    assert isinstance(off, COSArray)
    assert all(
        off.get_object(index) is not removed.get_cos_object()
        for index in range(off.size())
    )
