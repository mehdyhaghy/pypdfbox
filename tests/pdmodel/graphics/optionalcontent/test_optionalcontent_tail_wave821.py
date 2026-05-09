from __future__ import annotations

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


class _NoneNameDictionary(COSDictionary):
    def get_name(
        self, key: COSName | str, default: str | None = None
    ) -> str | None:
        if key == _BASE_STATE:
            return None
        return super().get_name(key, default)


def test_wave821_configuration_base_state_defaults_on_when_get_name_returns_none() -> None:
    cfg = PDOptionalContentConfiguration(_NoneNameDictionary())

    assert cfg.get_base_state() == "ON"


def test_wave821_group_prune_usage_keeps_malformed_usage_entry() -> None:
    group = PDOptionalContentGroup("Layer")
    malformed_usage = COSName.get_pdf_name("NotAUsageDictionary")
    group.get_cos_object().set_item(_USAGE, malformed_usage)

    group._prune_usage_chain(_PRINT)

    assert group.get_cos_object().get_dictionary_object(_USAGE) is malformed_usage


def test_wave821_group_usage_state_reader_ignores_non_name_export_state() -> None:
    group = PDOptionalContentGroup("Layer")
    usage = COSDictionary()
    export = COSDictionary()
    export.set_item(_EXPORT_STATE, COSDictionary())
    usage.set_item(_EXPORT, export)
    group.get_cos_object().set_item(_USAGE, usage)

    assert group.get_usage_export_state() is None


def test_wave821_print_subtype_setter_writes_and_removes_name() -> None:
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
