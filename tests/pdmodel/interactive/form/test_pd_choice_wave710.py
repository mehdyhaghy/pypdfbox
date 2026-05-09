from __future__ import annotations

from pypdfbox.cos import COSName
from pypdfbox.pdmodel.interactive.form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_choice import PDChoice

_FT: COSName = COSName.get_pdf_name("FT")
_TI: COSName = COSName.get_pdf_name("TI")


def test_pd_choice_base_constructor_initializes_choice_field_type() -> None:
    field = PDChoice(PDAcroForm())

    assert field.get_cos_object().get_name(_FT) == "Ch"
    assert field.get_field_type() == "Ch"


def test_pd_choice_base_top_index_set_clear_and_remove() -> None:
    field = PDChoice(PDAcroForm())
    cos = field.get_cos_object()

    field.set_top_index(4)
    assert cos.get_int(_TI, -1) == 4
    assert field.has_top_index() is True

    field.set_top_index(None)
    assert cos.get_dictionary_object(_TI) is None
    assert field.has_top_index() is False

    field.set_top_index(0)
    field.clear_top_index()
    assert cos.get_dictionary_object(_TI) is None


def test_pd_choice_read_string_or_array_accepts_names_and_unknowns() -> None:
    assert PDChoice._read_string_or_array(COSName.get_pdf_name("Export")) == [  # noqa: SLF001
        "Export"
    ]
    assert PDChoice._read_string_or_array(object()) == []  # noqa: SLF001


def test_pd_choice_write_string_or_array_none_returns_none() -> None:
    assert PDChoice._write_string_or_array(None) is None  # noqa: SLF001
