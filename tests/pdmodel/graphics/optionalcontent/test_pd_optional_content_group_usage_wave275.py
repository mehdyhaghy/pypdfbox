from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_group_usage import (
    PDOptionalContentGroupUsage,
)

_CREATOR_INFO = COSName.get_pdf_name("CreatorInfo")
_LANGUAGE = COSName.get_pdf_name("Language")
_EXPORT = COSName.get_pdf_name("Export")
_ZOOM = COSName.get_pdf_name("Zoom")
_PRINT = COSName.get_pdf_name("Print")
_VIEW = COSName.get_pdf_name("View")
_USER = COSName.get_pdf_name("User")
_PAGE_ELEMENT = COSName.get_pdf_name("PageElement")

_USAGE_SUBDICTS = (
    ("creator_info", _CREATOR_INFO),
    ("language", _LANGUAGE),
    ("export", _EXPORT),
    ("zoom", _ZOOM),
    ("print", _PRINT),
    ("view", _VIEW),
    ("user", _USER),
    ("page_element", _PAGE_ELEMENT),
)


@pytest.mark.parametrize(("suffix", "key"), _USAGE_SUBDICTS)
def test_has_and_clear_typed_usage_subdicts(
    suffix: str, key: COSName
) -> None:
    usage = PDOptionalContentGroupUsage()

    assert getattr(usage, f"get_{suffix}")() is None
    assert not getattr(usage, f"has_{suffix}")()

    getattr(usage, f"clear_{suffix}")()
    assert usage.get_cos_object().get_dictionary_object(key) is None

    created = getattr(usage, f"get_or_create_{suffix}")()
    assert isinstance(created.get_cos_object(), COSDictionary)
    assert getattr(usage, f"has_{suffix}")()
    assert (
        usage.get_cos_object().get_dictionary_object(key)
        is created.get_cos_object()
    )

    getattr(usage, f"clear_{suffix}")()
    assert getattr(usage, f"get_{suffix}")() is None
    assert not getattr(usage, f"has_{suffix}")()
    assert usage.get_cos_object().get_dictionary_object(key) is None


def test_clear_typed_usage_subdict_preserves_siblings() -> None:
    usage = PDOptionalContentGroupUsage()
    view = usage.get_or_create_view().get_cos_object()
    print_dict = usage.get_or_create_print().get_cos_object()

    usage.clear_view()

    assert not usage.has_view()
    assert usage.get_cos_object().get_dictionary_object(_VIEW) is None
    assert usage.has_print()
    assert usage.get_print() is not None
    assert usage.get_cos_object().get_dictionary_object(_PRINT) is print_dict
    assert view is not print_dict


def test_has_ignores_non_dictionary_usage_entry_and_clear_removes_it() -> None:
    raw = COSDictionary()
    raw.set_item(_VIEW, COSName.get_pdf_name("NotADictionary"))
    usage = PDOptionalContentGroupUsage(raw)

    assert usage.get_view() is None
    assert not usage.has_view()

    usage.clear_view()

    assert not raw.contains_key(_VIEW)
