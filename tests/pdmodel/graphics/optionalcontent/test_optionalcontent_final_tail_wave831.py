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
_SUBTYPE = COSName.get_pdf_name("Subtype")
_USAGE = COSName.get_pdf_name("Usage")


class _NoneBaseStateDictionary(COSDictionary):
    def get_name(
        self, key: COSName | str, default: str | None = None
    ) -> str | None:
        if key == _BASE_STATE:
            return None
        return super().get_name(key, default)


def test_wave831_configuration_base_state_defends_against_none_name() -> None:
    cfg = PDOptionalContentConfiguration(_NoneBaseStateDictionary())

    assert cfg.get_base_state() == "ON"


def test_wave831_group_prune_ignores_malformed_usage_dictionary() -> None:
    group = PDOptionalContentGroup("Layer")
    raw_usage = COSName.get_pdf_name("MalformedUsage")
    group.get_cos_object().set_item(_USAGE, raw_usage)

    group._prune_usage_chain(_PRINT)

    assert group.get_cos_object().get_dictionary_object(_USAGE) is raw_usage


def test_wave831_group_usage_export_state_ignores_non_name_value() -> None:
    group = PDOptionalContentGroup("Layer")
    usage = COSDictionary()
    export = COSDictionary()
    export.set_item(_EXPORT_STATE, COSDictionary())
    usage.set_item(_EXPORT, export)
    group.get_cos_object().set_item(_USAGE, usage)

    assert group.get_usage_export_state() is None
    assert group.get_render_state_enum() is None


def test_wave831_group_rejects_non_render_state_enum() -> None:
    group = PDOptionalContentGroup("Layer")

    with pytest.raises(TypeError, match="state must be RenderState"):
        group.set_render_state_enum("ON")  # type: ignore[arg-type]


def test_wave831_print_usage_subtype_setter_writes_and_removes_name() -> None:
    usage = PDOptionalContentGroupUsage()
    print_usage = usage.get_or_create_print()

    print_usage.subtype = "Watermark"

    assert print_usage.subtype == "Watermark"
    assert (
        print_usage.get_cos_object().get_dictionary_object(_SUBTYPE)
        == COSName.get_pdf_name("Watermark")
    )

    print_usage.subtype = None

    assert print_usage.subtype is None
    assert print_usage.get_cos_object().get_dictionary_object(_SUBTYPE) is None
