from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSString
from pypdfbox.pdmodel.interactive.annotation import PDAnnotationWidget
from pypdfbox.pdmodel.interactive.annotation.pd_movie import PDMovie
from pypdfbox.pdmodel.interactive.form import (
    PDAcroForm,
    PDButton,
    PDChoice,
    PDSignatureField,
)
from pypdfbox.pdmodel.interactive.form.pd_appearance_generator import (
    PDAppearanceGenerator,
)
from pypdfbox.pdmodel.pd_rectangle import PDRectangle


def test_wave745_button_push_button_clears_radio_bit_and_none_clears_values() -> None:
    button = PDButton(PDAcroForm())

    button.set_radio_button(True)
    assert button.is_radio_button() is True

    button.set_push_button(True)
    assert button.is_push_button() is True
    assert button.is_radio_button() is False

    button.set_value("temporary")
    button.set_default_value("temporary")
    button.set_value(None)
    button.set_default_value(None)

    assert button.has_value() is False
    assert button.has_default_value() is False


def test_wave745_button_rejects_unknown_non_numeric_export_value() -> None:
    button = PDButton(PDAcroForm())
    button.set_export_values(["Yes"])

    with pytest.raises(ValueError, match="not a valid option"):
        button.set_value("NotAnIndex")


def test_wave745_button_construct_appearances_skips_non_dictionary_normal_ap() -> None:
    button = PDButton(PDAcroForm())
    widget = PDAnnotationWidget()
    ap = COSDictionary()
    ap.set_item(COSName.get_pdf_name("N"), COSString("bad-normal-appearance"))
    widget.get_cos_object().set_item(COSName.get_pdf_name("AP"), ap)
    button.set_widgets([widget])

    button.construct_appearances()

    assert widget.get_appearance_state() is None


def test_wave745_choice_default_constructor_top_index_and_cos_helpers() -> None:
    choice = PDChoice(PDAcroForm())

    choice.set_top_index(4)
    assert choice.has_top_index() is True
    assert choice.get_top_index() == 4

    choice.set_top_index(None)
    assert choice.has_top_index() is False
    assert choice.get_top_index() == 0

    assert PDChoice._read_string_or_array(COSName.get_pdf_name("Named")) == [  # noqa: SLF001
        "Named"
    ]
    assert PDChoice._read_string_or_array(object()) == []  # noqa: SLF001
    assert PDChoice._write_string_or_array(None) is None  # noqa: SLF001


def test_wave745_signature_string_value_is_unsupported() -> None:
    signature = PDSignatureField(PDAcroForm())

    with pytest.raises(NotImplementedError, match="cannot be set with a string"):
        signature.set_value("signed")


def test_wave745_signature_regenerate_appearance_dispatches_generator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    signature = PDSignatureField(PDAcroForm())
    calls: list[PDSignatureField] = []

    def generate(
        self: PDAppearanceGenerator,
        field: PDSignatureField,
    ) -> None:
        calls.append(field)

    monkeypatch.setattr(PDAppearanceGenerator, "generate", generate)

    signature.regenerate_appearance()

    assert calls == [signature]


def test_wave745_signature_visible_widget_guards_for_empty_and_none_widget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    signature = PDSignatureField(PDAcroForm())

    signature.set_widgets([])
    assert signature.has_visible_widget() is False

    monkeypatch.setattr(signature, "get_widgets", lambda: [None])
    assert signature.has_visible_widget() is False
    assert signature.construct_appearances() is None


def test_wave745_signature_getters_return_none_for_absent_optional_dicts() -> None:
    signature = PDSignatureField(PDAcroForm())

    assert signature.get_seed_value() is None
    assert signature.get_lock() is None


def test_wave745_signature_visible_widget_detects_nonzero_rectangle() -> None:
    signature = PDSignatureField(PDAcroForm())
    widget = PDAnnotationWidget()
    widget.set_rectangle(PDRectangle(0, 0, 12, 8))
    signature.set_widgets([widget])

    assert signature.has_visible_widget() is True

    widget.set_hidden(True)
    assert signature.has_visible_widget() is False


def test_wave745_movie_file_and_poster_clear_and_raw_cos_round_trip() -> None:
    movie = PDMovie()
    raw_file = COSName.get_pdf_name("RawFileSpec")

    movie.set_file(raw_file)
    assert movie.get_cos_object().get_dictionary_object("F") is raw_file

    movie.set_file(None)
    assert movie.get_file() is None

    assert movie.get_poster() is None
    movie.set_poster(COSArray())
    assert isinstance(movie.get_poster(), COSArray)
    movie.set_poster(None)
    assert movie.get_poster() is None
