from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSFloat, COSName, COSString
from pypdfbox.pdmodel.common.filespecification import PDEmbeddedFile

_PARAMS = COSName.get_pdf_name("Params")
_SIZE = COSName.get_pdf_name("Size")


def test_wave337_get_size_defaults_to_minus_one_when_missing() -> None:
    embedded = PDEmbeddedFile()

    assert embedded.get_size() == -1
    assert embedded.has_size() is False


def test_wave337_get_size_defaults_to_minus_one_for_malformed_params() -> None:
    embedded = PDEmbeddedFile()
    embedded.get_cos_object().set_item(_PARAMS, COSString("bad"))

    assert embedded.get_size() == -1
    assert embedded.has_size() is False


def test_wave337_get_size_uses_cos_number_int_value() -> None:
    embedded = PDEmbeddedFile()
    params = COSDictionary()
    params.set_item(_SIZE, COSFloat(42.75))
    embedded.get_cos_object().set_item(_PARAMS, params)

    assert embedded.get_size() == 42
    assert embedded.has_size() is True
