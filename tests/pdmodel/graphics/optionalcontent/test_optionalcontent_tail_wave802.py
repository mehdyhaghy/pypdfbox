from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.graphics.optionalcontent import (
    PDOptionalContentConfiguration,
    PDOptionalContentGroup,
)
from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_group_usage import (
    PDOptionalContentGroupUsage,
)
from pypdfbox.pdmodel.graphics.pattern.pd_shading_pattern import PDShadingPattern

_BASE_STATE = COSName.get_pdf_name("BaseState")
_PRINT = COSName.get_pdf_name("Print")
_SUBTYPE = COSName.get_pdf_name("Subtype")
_USAGE = COSName.get_pdf_name("Usage")
_VIEW = COSName.get_pdf_name("View")
_VIEW_STATE = COSName.get_pdf_name("ViewState")


class _NoneNameDictionary(COSDictionary):
    def get_name(
        self, key: COSName | str, default: str | None = None
    ) -> str | None:
        if key == _BASE_STATE:
            return None
        return super().get_name(key, default)


def test_wave802_print_subtype_setter_round_trips_and_removes() -> None:
    usage = PDOptionalContentGroupUsage()
    print_usage = usage.get_or_create_print()

    print_usage.subtype = "Watermark"
    assert print_usage.subtype == "Watermark"
    assert print_usage.get_cos_object().get_dictionary_object(_SUBTYPE) == COSName.get_pdf_name(
        "Watermark"
    )

    print_usage.subtype = None
    assert print_usage.subtype is None
    assert print_usage.get_cos_object().get_dictionary_object(_SUBTYPE) is None


def test_wave802_group_prune_usage_ignores_malformed_usage_entry() -> None:
    group = PDOptionalContentGroup("Layer")
    group.get_cos_object().set_item(_USAGE, COSName.get_pdf_name("BadUsage"))

    group._prune_usage_chain(_PRINT)

    assert group.get_cos_object().get_dictionary_object(_USAGE) == COSName.get_pdf_name(
        "BadUsage"
    )


def test_wave802_group_usage_state_reader_ignores_non_name_state() -> None:
    group = PDOptionalContentGroup("Layer")
    usage = COSDictionary()
    view = COSDictionary()
    view.set_item(_VIEW_STATE, COSDictionary())
    usage.set_item(_VIEW, view)
    group.get_cos_object().set_item(_USAGE, usage)

    assert group.get_usage_view_state() is None


def test_wave802_configuration_base_state_defensive_none_defaults_on() -> None:
    cfg = PDOptionalContentConfiguration(_NoneNameDictionary())

    assert cfg.get_base_state() == "ON"


def test_wave802_shading_pattern_clear_extended_graphics_state_removes_entry() -> None:
    pattern = PDShadingPattern()
    ext_g_state = COSDictionary()

    pattern.set_extended_graphics_state(ext_g_state)
    pattern.clear_extended_graphics_state()

    assert pattern.get_extended_graphics_state() is None


def test_wave802_shading_pattern_set_shading_rejects_non_cos_value() -> None:
    pattern = PDShadingPattern()

    with pytest.raises(TypeError, match="set_shading expects"):
        pattern.set_shading(123)  # type: ignore[arg-type]
