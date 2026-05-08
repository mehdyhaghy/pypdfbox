from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSStream
from pypdfbox.pdmodel import PDPage


def _name(value: str) -> COSName:
    return COSName.get_pdf_name(value)


def test_malformed_optional_entries_are_detectable_without_breaking_accessors() -> None:
    page = PDPage()
    page_dict = page.get_cos_object()

    malformed = COSName.get_pdf_name("Malformed")
    page_dict.set_item(_name("Contents"), malformed)
    page_dict.set_item(_name("Metadata"), malformed)
    page_dict.set_item(_name("Thumb"), malformed)
    page_dict.set_item(_name("Trans"), malformed)
    page_dict.set_item(_name("AA"), malformed)
    page_dict.set_item(_name("Annots"), malformed)
    page_dict.set_item(_name("B"), malformed)
    page_dict.set_item(_name("VP"), malformed)
    page_dict.set_item(_name("Group"), malformed)
    page_dict.set_item(_name("Tabs"), COSInteger.get(1))
    page_dict.set_item(_name("Dur"), malformed)

    assert page.has_contents() is False
    assert page.has_metadata() is True
    assert page.has_thumb() is True
    assert page.has_transition() is True
    assert page.has_actions() is True
    assert page.has_annotations() is True
    assert page.has_thread_beads() is True
    assert page.has_viewports() is True
    assert page.has_group() is True
    assert page.has_tab_order() is True
    assert page.has_duration() is True

    assert page.get_contents() == b""
    assert page.get_content_streams() == []
    assert page.get_metadata() is None
    assert page.get_thumb() is None
    assert page.get_transition() is None
    assert page.get_annotations() == []
    assert page.get_thread_beads() == []
    assert page.get_viewports() is None
    assert page.get_group() is None
    assert page.get_tab_order() is None
    assert page.get_duration() is None

    # The read-only has_* probe must not normalize or replace malformed /AA.
    assert page_dict.get_dictionary_object(_name("AA")) is malformed


def test_clear_helpers_remove_direct_optional_entries() -> None:
    page = PDPage()
    page_dict = page.get_cos_object()

    page_dict.set_item(_name("Contents"), COSArray([COSStream()]))
    page_dict.set_item(_name("Metadata"), COSStream())
    page_dict.set_item(_name("Thumb"), COSStream())
    page_dict.set_item(_name("Trans"), COSDictionary())
    page_dict.set_item(_name("AA"), COSDictionary())
    page_dict.set_item(_name("Annots"), COSArray())
    page_dict.set_item(_name("B"), COSArray())
    page_dict.set_item(_name("VP"), COSArray())
    page_dict.set_item(_name("Group"), COSDictionary())
    page_dict.set_item(_name("Tabs"), COSName.get_pdf_name(PDPage.TAB_ORDER_ROW))
    page_dict.set_item(_name("Dur"), COSInteger.get(3))

    page.clear_contents()
    page.clear_metadata()
    page.clear_thumb()
    page.clear_transition()
    page.clear_actions()
    page.clear_annotations()
    page.clear_thread_beads()
    page.clear_viewports()
    page.clear_group()
    page.clear_tab_order()
    page.clear_duration()

    for key in (
        "Contents",
        "Metadata",
        "Thumb",
        "Trans",
        "AA",
        "Annots",
        "B",
        "VP",
        "Group",
        "Tabs",
        "Dur",
    ):
        assert not page_dict.contains_key(_name(key))

    assert page.has_contents() is False
    assert page.has_metadata() is False
    assert page.has_thumb() is False
    assert page.has_transition() is False
    assert page.has_actions() is False
    assert page.has_annotations() is False
    assert page.has_thread_beads() is False
    assert page.has_viewports() is False
    assert page.has_group() is False
    assert page.has_tab_order() is False
    assert page.has_duration() is False


def test_clear_actions_removes_auto_materialized_empty_actions_dict() -> None:
    page = PDPage()

    page.get_actions()
    assert page.has_actions() is True

    page.clear_actions()

    assert page.has_actions() is False
    assert page.get_cos_object().get_dictionary_object(_name("AA")) is None
