from __future__ import annotations

from typing import Any

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSString
from pypdfbox.pdmodel.interactive.action.pd_action_hide import PDActionHide
from pypdfbox.pdmodel.interactive.action.pd_action_import_data import (
    PDActionImportData,
)
from pypdfbox.pdmodel.interactive.action.pd_action_sound import PDActionSound
from pypdfbox.pdmodel.interactive.action.pd_action_submit_form import (
    PDActionSubmitForm,
)
from pypdfbox.pdmodel.interactive.action.pd_action_uri import PDActionURI
from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
    PDDestination,
    PDNamedDestination,
    PDPageFitHeightDestination,
    PDPageFitRectangleDestination,
)
from pypdfbox.pdmodel.interactive.documentnavigation.outline import PDOutlineItem

_C = COSName.get_pdf_name("C")
_F = COSName.get_pdf_name("F")
_SOUND = COSName.get_pdf_name("Sound")
_SUBTYPE = COSName.SUBTYPE  # type: ignore[attr-defined]


def test_uri_scheme_rejects_non_rfc_scheme_character() -> None:
    action = PDActionURI()

    action.set_uri("bad_scheme:target")

    assert action.get_scheme() is None
    assert action.is_relative() is True


def test_hide_single_raw_annotation_dictionary_stays_direct_target() -> None:
    action = PDActionHide()
    raw_annotation = COSDictionary()
    raw_annotation.set_name(_SUBTYPE, "Text")

    action.set_annotations([raw_annotation])

    assert action.get_target() is raw_annotation
    assert action.get_annotations()[0].get_cos_object() is raw_annotation  # type: ignore[index]


def test_sound_action_non_stream_sound_entry_is_ignored() -> None:
    action = PDActionSound()
    raw_sound = COSDictionary()

    action.get_cos_object().set_item(_SOUND, raw_sound)

    assert action.get_sound() is None
    assert action.has_sound() is False


@pytest.mark.parametrize(
    "action_cls, getter_name",
    [
        (PDActionImportData, "get_file_path"),
        (PDActionSubmitForm, "get_url"),
    ],
)
def test_file_action_complex_spec_factory_none_has_no_resolved_path(
    monkeypatch: pytest.MonkeyPatch,
    action_cls: type[PDActionImportData] | type[PDActionSubmitForm],
    getter_name: str,
) -> None:
    raw_file_spec = COSDictionary()
    action = action_cls()
    action.get_cos_object().set_item(_F, raw_file_spec)

    def create_none(value: Any) -> None:
        assert value is raw_file_spec
        return None

    monkeypatch.setattr(
        "pypdfbox.pdmodel.common.filespecification.pd_file_specification."
        "PDFileSpecification.create_fs",
        staticmethod(create_none),
    )

    assert getattr(action, getter_name)() is None


def test_destination_abstract_cos_object_and_bytes_named_destination() -> None:
    with pytest.raises(NotImplementedError):
        PDDestination().get_cos_object()

    destination = PDNamedDestination(b"chapter-833")

    assert destination.is_string_form() is True
    assert destination.get_named_destination() == "chapter-833"


def test_destination_and_outline_unset_tail_predicates() -> None:
    fit_height = PDPageFitHeightDestination()
    fit_rectangle = PDPageFitRectangleDestination()
    outline = PDOutlineItem()
    outline.get_cos_object().set_item(
        _C,
        COSArray(
            [
                COSString("bad-red"),
                COSString("bad-green"),
                COSString("bad-blue"),
            ]
        ),
    )

    assert fit_height.is_left_unset() is True
    assert fit_rectangle.is_top_unset() is True
    assert outline.get_text_color() is None
