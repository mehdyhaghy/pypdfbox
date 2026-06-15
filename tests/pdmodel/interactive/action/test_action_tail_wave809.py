from __future__ import annotations

from typing import Any

import pytest

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.interactive.action.pd_action_embedded_go_to import (
    PDActionEmbeddedGoTo,
)
from pypdfbox.pdmodel.interactive.action.pd_action_hide import PDActionHide
from pypdfbox.pdmodel.interactive.action.pd_action_import_data import (
    PDActionImportData,
)
from pypdfbox.pdmodel.interactive.action.pd_action_sound import PDActionSound
from pypdfbox.pdmodel.interactive.action.pd_action_submit_form import (
    PDActionSubmitForm,
)
from pypdfbox.pdmodel.interactive.action.pd_action_uri import PDActionURI
from pypdfbox.pdmodel.interactive.action.pd_uri_dictionary import PDURIDictionary
from pypdfbox.pdmodel.pd_document import PDDocument

_BASE = COSName.get_pdf_name("Base")
_F = COSName.get_pdf_name("F")
_SOUND = COSName.get_pdf_name("Sound")
_SUBTYPE = COSName.SUBTYPE  # type: ignore[attr-defined]


def test_uri_dictionary_base_as_cos_name_returns_none() -> None:
    # Wave 1530: upstream ``PDURIDictionary.getBase`` is plain
    # ``COSDictionary.getString(Base)``, which returns null for a COSName
    # (only a COSString decodes). The live PDFBox 3.0.7 oracle confirms a
    # ``/Base`` stored as a name yields ``None``, not the name text.
    raw = COSDictionary()
    raw.set_item(_BASE, COSName.get_pdf_name("NamedBase"))

    uri_dict = PDURIDictionary(raw)

    assert uri_dict.get_base() is None
    assert uri_dict.get_base_as_cos_string() is None


def test_uri_scheme_rejects_invalid_scheme_characters_as_relative() -> None:
    action = PDActionURI()

    action.set_uri("ht*tp://example.test")

    assert action.get_scheme() is None
    assert action.is_relative() is True
    assert action.is_http() is False


def test_submit_form_get_url_returns_none_when_file_spec_factory_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_file_spec = COSDictionary()
    action = PDActionSubmitForm()
    action.get_cos_object().set_item(_F, raw_file_spec)

    def create_none(value: Any) -> None:
        assert value is raw_file_spec
        return None

    monkeypatch.setattr(
        "pypdfbox.pdmodel.common.filespecification.pd_file_specification."
        "PDFileSpecification.create_fs",
        staticmethod(create_none),
    )

    assert action.get_url() is None


def test_sound_action_get_sound_ignores_non_stream_entry() -> None:
    action = PDActionSound()
    raw = COSDictionary()

    action.get_cos_object().set_item(_SOUND, raw)

    assert action.get_sound() is None


def test_import_data_get_file_path_returns_none_when_factory_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_file_spec = COSDictionary()
    action = PDActionImportData()
    action.get_cos_object().set_item(_F, raw_file_spec)

    def create_none(value: Any) -> None:
        assert value is raw_file_spec
        return None

    monkeypatch.setattr(
        "pypdfbox.pdmodel.common.filespecification.pd_file_specification."
        "PDFileSpecification.create_fs",
        staticmethod(create_none),
    )

    assert action.get_file_path() is None


def test_hide_set_annotations_single_raw_dictionary_stores_direct_entry() -> None:
    action = PDActionHide()
    raw_annotation = COSDictionary()
    raw_annotation.set_name(_SUBTYPE, "Widget")

    action.set_annotations([raw_annotation])

    assert action.get_target() is raw_annotation
    annotations = action.get_annotations()
    assert annotations is not None
    assert annotations[0].get_cos_object() is raw_annotation


def test_embedded_go_to_final_destination_ignores_unhandled_destination_object(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = PDDocument()
    action = PDActionEmbeddedGoTo()
    monkeypatch.setattr(action, "get_d", lambda: object())

    try:
        assert action._resolve_final_destination(document) is None
    finally:
        document.close()
