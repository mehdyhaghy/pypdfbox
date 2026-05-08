from __future__ import annotations

from pypdfbox.cos import COSArray, COSFloat, COSInteger, COSName, COSStream
from pypdfbox.pdmodel.graphics.form import PDFormXObject

_MATRIX = COSName.get_pdf_name("Matrix")


def _new_form() -> PDFormXObject:
    return PDFormXObject(COSStream())


def test_has_matrix_requires_numeric_first_six_entries() -> None:
    form = _new_form()
    matrix = COSArray(
        [
            COSInteger.get(1),
            COSInteger.get(0),
            COSInteger.get(0),
            COSInteger.get(1),
            COSName.get_pdf_name("NotANumber"),
            COSFloat(2.0),
        ]
    )
    form.get_cos_object().set_item(_MATRIX, matrix)

    assert form.get_matrix() == [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]
    assert form.has_matrix() is False


def test_has_matrix_accepts_numeric_array_with_extra_entries() -> None:
    form = _new_form()
    form.set_matrix([1, 0, 0, 1, 10, 20])
    matrix = form.get_cos_object().get_dictionary_object(_MATRIX)
    assert isinstance(matrix, COSArray)
    matrix.add(COSName.get_pdf_name("Ignored"))

    assert form.get_matrix() == [1.0, 0.0, 0.0, 1.0, 10.0, 20.0]
    assert form.has_matrix() is True
