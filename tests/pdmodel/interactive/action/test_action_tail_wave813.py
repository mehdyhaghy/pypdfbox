from __future__ import annotations

from typing import Any

import pytest

from pypdfbox.cos import COSDictionary, COSName
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

_BASE = COSName.get_pdf_name("Base")
_F = COSName.get_pdf_name("F")
_SOUND = COSName.get_pdf_name("Sound")
_SUBTYPE = COSName.SUBTYPE  # type: ignore[attr-defined]


def test_hide_single_raw_annotation_dictionary_is_stored_without_wrapping() -> None:
    action = PDActionHide()
    raw_annotation = COSDictionary()
    raw_annotation.set_name(_SUBTYPE, "Text")

    action.set_annotations([raw_annotation])

    assert action.get_target() is raw_annotation
    assert action.get_annotations()[0].get_cos_object() is raw_annotation  # type: ignore[index]


def test_import_data_complex_file_spec_without_factory_wrapper_has_no_path(
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


def test_sound_action_raw_non_stream_sound_entry_is_not_typed_sound() -> None:
    action = PDActionSound()
    raw_sound = COSDictionary()

    action.set_sound(raw_sound)

    assert action.get_cos_object().get_dictionary_object(_SOUND) is raw_sound
    assert action.get_sound() is None
    assert action.has_sound() is False


def test_submit_form_complex_file_spec_without_factory_wrapper_has_no_url(
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


def test_uri_scheme_with_disallowed_character_is_treated_as_relative() -> None:
    action = PDActionURI()

    action.set_uri("bad_scheme:target")

    assert action.get_scheme() is None
    assert action.is_relative() is True


def test_uri_dictionary_base_accepts_name_form() -> None:
    raw = COSDictionary()
    raw.set_item(_BASE, COSName.get_pdf_name("NamedBase"))

    uri_dictionary = PDURIDictionary(raw)

    assert uri_dictionary.get_base() == "NamedBase"
    assert uri_dictionary.get_base_as_cos_string() is None
