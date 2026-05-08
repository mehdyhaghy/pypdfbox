from __future__ import annotations

from pypdfbox.cos import COSArray, COSFloat, COSName
from pypdfbox.pdmodel.graphics.pattern import PDTilingPattern

_MATRIX = COSName.get_pdf_name("Matrix")


def test_set_matrix_accepts_buffer_filling_adapter() -> None:
    class JavaStyleAffineTransform:
        def get_matrix(self, out: list[float]) -> None:
            out[:] = [2.0, 0.0, 0.0, 3.0, 10.0, 20.0]

    pattern = PDTilingPattern()

    pattern.set_matrix(JavaStyleAffineTransform())

    assert pattern.get_matrix() == [2.0, 0.0, 0.0, 3.0, 10.0, 20.0]
    raw = pattern.get_cos_object().get_dictionary_object(_MATRIX)
    assert isinstance(raw, COSArray)
    assert [raw.get_object(i) for i in range(raw.size())] == [
        COSFloat(2.0),
        COSFloat(0.0),
        COSFloat(0.0),
        COSFloat(3.0),
        COSFloat(10.0),
        COSFloat(20.0),
    ]


def test_set_matrix_uses_adapter_return_value_when_buffer_method_returns_sequence() -> None:
    class ReturningAffineTransform:
        def get_matrix(self, out: list[float]) -> tuple[float, ...]:
            out[:] = [99.0] * 6
            return (1.0, 2.0, 3.0, 4.0, 5.0, 6.0)

    pattern = PDTilingPattern()

    pattern.set_matrix(ReturningAffineTransform())

    assert pattern.get_matrix() == [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
