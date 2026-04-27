from __future__ import annotations

import pytest

from pypdfbox.cos import COSName
from pypdfbox.pdmodel.page_mode import PageMode


def test_string_value_round_trip() -> None:
    for member in PageMode:
        assert PageMode.from_string(member.string_value()) is member


def test_known_pdf_name_strings() -> None:
    expected = {
        "UseNone",
        "UseOutlines",
        "UseThumbs",
        "FullScreen",
        "UseOC",
        "UseAttachments",
    }
    assert {m.string_value() for m in PageMode} == expected


def test_use_optional_content_value_is_use_oc() -> None:
    # Quirk worth pinning: the constant name and the PDF string differ.
    assert PageMode.USE_OPTIONAL_CONTENT.string_value() == "UseOC"


def test_str_enum_compares_equal_to_string() -> None:
    assert PageMode.USE_OUTLINES == "UseOutlines"
    assert PageMode.FULL_SCREEN == "FullScreen"


def test_to_cos_name_returns_canonical_name() -> None:
    name = PageMode.USE_THUMBS.to_cos_name()
    assert isinstance(name, COSName)
    assert name.get_name() == "UseThumbs"


def test_from_string_unknown_raises() -> None:
    with pytest.raises(ValueError):
        PageMode.from_string("NotARealMode")


def test_from_string_empty_raises() -> None:
    with pytest.raises(ValueError):
        PageMode.from_string("")
