from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.interactive.action import PDAction, PDActionURI


def test_wave312_get_type_accepts_string_encoded_type_entry() -> None:
    raw = COSDictionary()
    raw.set_string(COSName.get_pdf_name("Type"), "Action")
    raw.set_name(COSName.get_pdf_name("S"), "URI")

    action = PDActionURI(raw)

    assert action.get_type() == "Action"


def test_wave312_get_sub_type_accepts_string_encoded_s_entry() -> None:
    raw = COSDictionary()
    raw.set_string(COSName.get_pdf_name("S"), "URI")

    action = PDActionURI(raw)

    assert action.get_sub_type() == "URI"


def test_wave312_factory_dispatches_string_encoded_s_entry() -> None:
    raw = COSDictionary()
    raw.set_string(COSName.get_pdf_name("S"), "URI")

    action = PDAction.create(raw)

    assert isinstance(action, PDActionURI)
    assert action.get_cos_object() is raw
