from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName, COSString
from pypdfbox.pdmodel.common.filespecification.pd_complex_file_specification import (
    PDComplexFileSpecification,
)
from pypdfbox.pdmodel.common.filespecification.pd_simple_file_specification import (
    PDSimpleFileSpecification,
)
from pypdfbox.pdmodel.interactive.action.pd_action_launch import PDActionLaunch

_F = COSName.get_pdf_name("F")


def test_wave324_set_file_accepts_simple_string_form() -> None:
    action = PDActionLaunch()

    action.set_file("viewer.exe")

    assert action.get_f() == "viewer.exe"
    resolved = action.get_file()
    assert isinstance(resolved, PDSimpleFileSpecification)
    assert resolved.get_file() == "viewer.exe"


def test_wave324_set_file_accepts_bytes_simple_string_form() -> None:
    action = PDActionLaunch()

    action.set_file(b"viewer.exe")

    assert action.get_f() == "viewer.exe"
    resolved = action.get_file()
    assert isinstance(resolved, PDSimpleFileSpecification)
    assert resolved.get_file() == "viewer.exe"


def test_wave324_set_file_accepts_raw_cos_file_spec() -> None:
    action = PDActionLaunch()
    raw = COSDictionary()
    raw.set_item(_F, COSString("document.pdf"))

    action.set_file(raw)

    assert action.get_cos_object().get_dictionary_object(_F) is raw
    resolved = action.get_file()
    assert isinstance(resolved, PDComplexFileSpecification)
    assert resolved.get_cos_object() is raw
    assert resolved.get_file() == "document.pdf"
