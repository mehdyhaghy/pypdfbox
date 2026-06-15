from __future__ import annotations

from typing import Any

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSString
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
from pypdfbox.pdmodel.interactive.annotation.pd_annotation import PDAnnotation
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_screen import (
    PDAnnotationScreen,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_sound import (
    PDAnnotationSound,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_square_circle import (
    PDAnnotationCircle,
)
from pypdfbox.pdmodel.interactive.annotation.pd_ink_list import PDInkList
from pypdfbox.pdmodel.interactive.form import PDAcroForm, PDField, PDFieldTree

_A = COSName.get_pdf_name("A")
_AP = COSName.get_pdf_name("AP")
_BASE = COSName.get_pdf_name("Base")
_F = COSName.get_pdf_name("F")
_SOUND = COSName.get_pdf_name("Sound")
_SUBTYPE = COSName.SUBTYPE  # type: ignore[attr-defined]


class _NonTerminalProtocolOnlyField(PDField):
    def is_terminal(self) -> bool:
        return False


class _DictionaryBackedWrapper:
    def get_cos_object(self) -> COSDictionary:
        return COSDictionary()


def test_wave843_action_raw_and_malformed_entries_cover_tail_branches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Wave 1530: a COSName /Base yields None (upstream getString returns null
    # for a name; only a COSString decodes).
    raw_base = COSDictionary()
    raw_base.set_item(_BASE, COSName.get_pdf_name("NamedBase"))
    assert PDURIDictionary(raw_base).get_base() is None

    uri = PDActionURI()
    uri.set_uri("ht*tp://example.test")
    assert uri.get_scheme() is None
    assert uri.is_relative() is True

    sound = PDActionSound()
    sound.get_cos_object().set_item(_SOUND, COSDictionary())
    assert sound.get_sound() is None

    def create_none(value: Any) -> None:
        assert isinstance(value, COSDictionary)
        return None

    monkeypatch.setattr(
        "pypdfbox.pdmodel.common.filespecification.pd_file_specification."
        "PDFileSpecification.create_fs",
        staticmethod(create_none),
    )
    raw_file_spec = COSDictionary()

    import_data = PDActionImportData()
    import_data.get_cos_object().set_item(_F, raw_file_spec)
    assert import_data.get_file_path() is None

    submit = PDActionSubmitForm()
    submit.get_cos_object().set_item(_F, raw_file_spec)
    assert submit.get_url() is None

    hide = PDActionHide()
    raw_annotation = COSDictionary()
    raw_annotation.set_name(_SUBTYPE, "Widget")
    hide.set_annotations([raw_annotation])
    assert hide.get_cos_object().get_dictionary_object("T") is raw_annotation


def test_wave843_annotation_raw_and_malformed_entries_cover_tail_branches() -> None:
    annotation = PDAnnotation()
    annotation.get_cos_object().set_item(_AP, COSDictionary())
    assert annotation.get_normal_appearance_stream() is None

    screen = PDAnnotationScreen()
    raw_action = COSDictionary()
    screen.set_action(raw_action)
    assert screen.get_cos_object().get_dictionary_object(_A) is raw_action

    sound_annotation = PDAnnotationSound()
    with pytest.raises(TypeError, match="COSStream-backed"):
        sound_annotation.set_sound(_DictionaryBackedWrapper())  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="PDAnnotationCircle requires"):
        PDAnnotationCircle(COSString("not-a-dictionary"))  # type: ignore[arg-type]

    ink_list = PDInkList(COSArray([COSString("not-a-path")]))
    with pytest.raises(TypeError, match="expected COSArray"):
        ink_list.get_path(0)


def test_wave843_field_tree_ignores_nonterminal_protocol_only_field(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    form = PDAcroForm()
    field = _NonTerminalProtocolOnlyField(form)
    field.set_partial_name("opaque")
    field.get_cos_object().set_item("Kids", COSArray([COSInteger.get(1)]))

    monkeypatch.setattr(form, "get_fields", lambda: [field])

    assert [item.get_fully_qualified_name() for item in PDFieldTree(form)] == [
        "opaque"
    ]
