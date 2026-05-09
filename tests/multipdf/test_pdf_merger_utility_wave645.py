from __future__ import annotations

import logging

import pytest

from pypdfbox.cos import COSDictionary, COSName, COSString
from pypdfbox.multipdf.pdf_merger_utility import (
    AcroFormMergeMode,
    PDFMergerUtility,
)

_FIELDS = COSName.get_pdf_name("Fields")
_T = COSName.get_pdf_name("T")


class _IdentityCloner:
    def clone_for_new_document(self, value: object) -> object:
        return value


class _NoneCloner:
    def clone_for_new_document(self, value: object) -> None:
        del value
        return None


class _Field:
    def __init__(self, partial_name: str, fully_qualified_name: str | None = None) -> None:
        self._dict = COSDictionary()
        self._dict.set_string(_T, partial_name)
        self._partial_name = partial_name
        self._fully_qualified_name = fully_qualified_name

    def get_cos_object(self) -> COSDictionary:
        return self._dict

    def get_partial_name(self) -> str:
        return self._partial_name

    def get_fully_qualified_name(self) -> str | None:
        return self._fully_qualified_name


class _Form:
    def __init__(self, fields: list[_Field], existing_names: set[str] | None = None) -> None:
        self._dict = COSDictionary()
        self._fields = fields
        self._existing_names = existing_names or set()

    def get_cos_object(self) -> COSDictionary:
        return self._dict

    def get_fields(self) -> list[_Field]:
        return self._fields

    def get_field_tree(self) -> list[_Field]:
        return self._fields

    def get_field(self, name: str) -> object | None:
        return object() if name in self._existing_names else None


class _CatalogWithForm:
    def __init__(self, form: _Form | None = None) -> None:
        self._dict = COSDictionary()
        self._form = form

    def get_cos_object(self) -> COSDictionary:
        return self._dict

    def get_acro_form(self) -> _Form | None:
        return self._form


class _BrokenCatalog:
    def get_acro_form(self) -> object:
        raise RuntimeError("broken form")


class _DynamicXfa:
    def __init__(self, result: bool | Exception) -> None:
        self._result = result

    def xfa_is_dynamic(self) -> bool:
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


def test_wave645_configuration_setters_and_getters_round_trip() -> None:
    util = PDFMergerUtility()
    info = object()
    metadata = object()

    util.set_acro_form_merge_mode(AcroFormMergeMode.JOIN_FORM_FIELDS_MODE)
    util.set_ignore_acro_form_errors(1)
    util.set_destination_file_name("merged.pdf")
    util.set_destination_document_information(info)
    util.set_destination_metadata(metadata)

    assert util.get_acro_form_merge_mode() is AcroFormMergeMode.JOIN_FORM_FIELDS_MODE
    assert util.is_ignore_acro_form_errors() is True
    assert util.get_destination_file_name() == "merged.pdf"
    assert util.get_destination_document_information() is info
    assert util.get_destination_metadata() is metadata


def test_wave645_dynamic_xfa_probe_is_defensive() -> None:
    assert PDFMergerUtility._is_dynamic_xfa(None) is False  # noqa: SLF001
    assert PDFMergerUtility._is_dynamic_xfa(object()) is False  # noqa: SLF001
    assert PDFMergerUtility._is_dynamic_xfa(_DynamicXfa(True)) is True  # noqa: SLF001
    assert PDFMergerUtility._is_dynamic_xfa(_DynamicXfa(RuntimeError("bad"))) is False  # noqa: SLF001


def test_wave645_merge_into_skips_excluded_existing_and_unclonable_values() -> None:
    keep = COSName.get_pdf_name("Keep")
    overwrite = COSName.get_pdf_name("Overwrite")
    excluded = COSName.get_pdf_name("Excluded")
    source = COSDictionary()
    source.set_item(keep, COSString("new"))
    source.set_item(overwrite, COSString("ignored"))
    source.set_item(excluded, COSString("ignored"))
    destination = COSDictionary()
    destination.set_item(overwrite, COSString("old"))

    PDFMergerUtility._merge_into(  # noqa: SLF001
        source,
        destination,
        _IdentityCloner(),  # type: ignore[arg-type]
        {excluded},
    )

    assert destination.get_string(keep) == "new"
    assert destination.get_string(overwrite) == "old"
    assert destination.get_dictionary_object(excluded) is None

    missing_destination = COSDictionary()
    PDFMergerUtility._merge_into(  # noqa: SLF001
        source,
        missing_destination,
        _NoneCloner(),  # type: ignore[arg-type]
        set(),
    )

    assert list(missing_destination.entry_set()) == []


def test_wave645_ignored_acro_form_errors_are_logged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    util = PDFMergerUtility()
    util.set_ignore_acro_form_errors(True)

    with caplog.at_level(logging.WARNING, logger="pypdfbox.multipdf.pdf_merger_utility"):
        util._merge_acro_form(  # noqa: SLF001
            _IdentityCloner(),  # type: ignore[arg-type]
            _BrokenCatalog(),
            _BrokenCatalog(),
        )

    assert "AcroForm merge error ignored" in caplog.text


def test_wave645_acro_form_modes_append_and_rename_colliding_fields() -> None:
    destination_form = _Form([_Field("dummyFieldName3")], {"shared"})
    source_form = _Form([_Field("source", "shared")])
    util = PDFMergerUtility()

    util._merge_acro_form(  # noqa: SLF001
        _IdentityCloner(),  # type: ignore[arg-type]
        _CatalogWithForm(destination_form),
        _CatalogWithForm(source_form),
    )

    fields = destination_form.get_cos_object().get_dictionary_object(_FIELDS)
    assert fields.get_object(0).get_string(_T) == "dummyFieldName4"  # type: ignore[union-attr]

    joined_form = _Form([])
    util.set_acro_form_merge_mode(AcroFormMergeMode.JOIN_FORM_FIELDS_MODE)
    util._merge_acro_form(  # noqa: SLF001
        _IdentityCloner(),  # type: ignore[arg-type]
        _CatalogWithForm(joined_form),
        _CatalogWithForm(_Form([_Field("joined", "joined")])),
    )

    joined_fields = joined_form.get_cos_object().get_dictionary_object(_FIELDS)
    assert joined_fields.get_object(0).get_string(_T) == "joined"  # type: ignore[union-attr]
