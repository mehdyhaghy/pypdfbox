from __future__ import annotations

import pytest

from pypdfbox.cos import COSName, COSStream, COSString
from pypdfbox.pdmodel.fdf import FDFField


def test_rich_text_string_round_trip_wave299() -> None:
    field = FDFField()

    field.set_rich_text("<body><p>Hello</p></body>")

    assert field.has_rich_text()
    assert field.get_rich_text() == "<body><p>Hello</p></body>"
    raw = field.get_cos_object().get_dictionary_object(COSName.get_pdf_name("RV"))
    assert isinstance(raw, COSString)


def test_rich_text_accepts_cos_stream_wave299() -> None:
    field = FDFField()
    stream = COSStream()
    stream.set_data(b"<body><p>Stream</p></body>")

    field.set_rich_text(stream)

    assert field.has_rich_text()
    # Upstream FDFField.getRichText() decodes COSStream via toTextString().
    assert field.get_rich_text() == "<body><p>Stream</p></body>"
    assert field.get_cos_object().get_dictionary_object(COSName.get_pdf_name("RV")) is stream


def test_rich_text_none_clears_entry_wave299() -> None:
    field = FDFField()
    field.set_rich_text(COSString("<body><p>Clear</p></body>"))

    field.clear_rich_text()

    assert field.get_rich_text() is None
    assert not field.has_rich_text()
    assert not field.get_cos_object().contains_key(COSName.get_pdf_name("RV"))


def test_rich_text_rejects_non_rich_text_cos_values_wave299() -> None:
    field = FDFField()

    with pytest.raises(TypeError, match="set_rich_text expected"):
        field.set_rich_text(COSName.get_pdf_name("NotRichText"))  # type: ignore[arg-type]
