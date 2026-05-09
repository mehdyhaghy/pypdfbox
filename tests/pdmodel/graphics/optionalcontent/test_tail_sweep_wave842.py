from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.graphics.optionalcontent import (
    PDOptionalContentConfiguration,
    PDOptionalContentGroup,
    PDOptionalContentGroupUsage,
)

_BASE_STATE = COSName.get_pdf_name("BaseState")
_EXPORT = COSName.get_pdf_name("Export")
_EXPORT_STATE = COSName.get_pdf_name("ExportState")
_PRINT = COSName.get_pdf_name("Print")
_PRINT_STATE = COSName.get_pdf_name("PrintState")
_SUBTYPE = COSName.get_pdf_name("Subtype")
_USAGE = COSName.get_pdf_name("Usage")


class _NoneBaseStateDictionary(COSDictionary):
    def get_name(
        self, key: COSName | str, default: str | None = None
    ) -> str | None:
        if key == _BASE_STATE:
            return None
        return super().get_name(key, default)


def test_wave842_configuration_base_state_defaults_when_reader_returns_none() -> None:
    assert PDOptionalContentConfiguration(_NoneBaseStateDictionary()).get_base_state() == "ON"


def test_wave842_group_usage_prune_and_non_name_states_are_tolerant() -> None:
    group = PDOptionalContentGroup("Layer")
    group.get_cos_object().set_item(_USAGE, COSName.get_pdf_name("MalformedUsage"))

    group._prune_usage_chain(_PRINT)

    assert group.get_cos_object().get_dictionary_object(_USAGE) == COSName.get_pdf_name(
        "MalformedUsage"
    )

    usage = COSDictionary()
    export = COSDictionary()
    export.set_item(_EXPORT_STATE, COSDictionary())
    usage.set_item(_EXPORT, export)
    group.get_cos_object().set_item(_USAGE, usage)

    assert group.get_usage_export_state() is None
    assert group.get_render_state_enum() is None


def test_wave842_print_usage_subtype_and_state_write_and_remove_names() -> None:
    usage = PDOptionalContentGroupUsage()
    print_usage = usage.get_or_create_print()

    print_usage.subtype = "Watermark"
    print_usage.print_state = "ON"

    assert print_usage.subtype == "Watermark"
    assert print_usage.print_state == "ON"
    assert (
        print_usage.get_cos_object().get_dictionary_object(_SUBTYPE)
        == COSName.get_pdf_name("Watermark")
    )
    assert (
        print_usage.get_cos_object().get_dictionary_object(_PRINT_STATE)
        == COSName.get_pdf_name("ON")
    )

    print_usage.subtype = None
    print_usage.print_state = None

    assert print_usage.subtype is None
    assert print_usage.print_state is None


def test_wave842_group_rejects_non_render_state_enum() -> None:
    with pytest.raises(TypeError, match="state must be RenderState"):
        PDOptionalContentGroup("Layer").set_render_state_enum("ON")  # type: ignore[arg-type]
