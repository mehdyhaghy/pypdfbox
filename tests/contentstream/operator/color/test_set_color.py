"""Hand-written tests for the ``SetColor`` abstract base — wave 1365.

``SetColor`` is the shared upstream base for ``sc`` / ``scn`` / ``SC`` /
``SCN``. The concrete pypdfbox per-operator subclasses bypass this base
today, so this test exercises the base directly via a minimal subclass to
lock in its branching:

* missing operand count raises ``MissingOperandException`` (non-pattern CS),
* non-number operands trigger the PDFBOX-5851 invalid-color fallback,
* pattern color spaces skip both validations and pass through any operands.
"""

from __future__ import annotations

from typing import Any

import pytest

from pypdfbox.contentstream import Operator
from pypdfbox.contentstream.operator import MissingOperandException
from pypdfbox.contentstream.operator.color.set_color import SetColor
from pypdfbox.cos import COSFloat, COSName


class _ColorSpace:
    """Generic non-pattern color space stub (DeviceRGB / DeviceCMYK shape)."""

    def __init__(self, n: int, name: str = "DeviceRGB") -> None:
        self._n = n
        self._name = name

    def get_number_of_components(self) -> int:
        return self._n

    def get_name(self) -> str:
        return self._name


class PDPattern:
    """Pattern color space stub — class name controls dispatch."""

    def __init__(self, n: int = 0, name: str = "Pattern") -> None:
        self._n = n
        self._name = name

    def get_number_of_components(self) -> int:
        return self._n

    def get_name(self) -> str:
        return self._name


class _Concrete(SetColor):
    """Concrete subclass with deterministic ``get_color_space``."""

    def __init__(self, color_space: Any) -> None:
        super().__init__(None)
        self._cs = color_space
        self.set_color_calls: list[Any] = []
        self._current: Any | None = None

    def get_color_space(self) -> Any:
        return self._cs

    def get_color(self) -> Any:
        return self._current

    def set_color(self, color: Any) -> None:  # type: ignore[override]
        self.set_color_calls.append(color)
        self._current = color


def test_process_no_color_space_is_no_op() -> None:
    op = _Concrete(color_space=None)
    op.process(Operator.get_operator("sc"), [COSFloat(0.5)])
    assert op.set_color_calls == []


def test_process_missing_operand_raises() -> None:
    op = _Concrete(color_space=_ColorSpace(3))
    with pytest.raises(MissingOperandException):
        op.process(
            Operator.get_operator("sc"), [COSFloat(0.5), COSFloat(0.5)]
        )


def test_process_non_number_operand_fallback_invalid_color() -> None:
    op = _Concrete(color_space=_ColorSpace(3))
    op.process(
        Operator.get_operator("sc"),
        [COSFloat(0.5), COSFloat(0.5), COSName.get_pdf_name("Bad")],
    )
    # Per PDFBOX-5851 we still call set_color, but with an empty
    # components array and a None color space.
    assert len(op.set_color_calls) == 1
    pd_color = op.set_color_calls[0]
    assert pd_color.get_color_space() is None
    # Components list should be empty.
    comps = pd_color.get_components()
    assert list(comps) == []


def test_process_happy_path_calls_set_color() -> None:
    cs = _ColorSpace(3)
    op = _Concrete(color_space=cs)
    op.process(
        Operator.get_operator("sc"),
        [COSFloat(0.1), COSFloat(0.2), COSFloat(0.3)],
    )
    assert len(op.set_color_calls) == 1
    pd_color = op.set_color_calls[0]
    assert pd_color.get_color_space() is cs
    components = list(pd_color.get_components())
    assert components == pytest.approx([0.1, 0.2, 0.3])


def test_process_pattern_colorspace_bypasses_validation() -> None:
    # Pattern colorspace: even with zero components we pass operands through.
    cs = PDPattern()
    op = _Concrete(color_space=cs)
    op.process(
        Operator.get_operator("scn"),
        [COSFloat(0.5), COSName.get_pdf_name("P0")],
    )
    assert len(op.set_color_calls) == 1
    pd_color = op.set_color_calls[0]
    assert pd_color.get_color_space() is cs


def test_get_color_and_set_color_are_abstract_in_base() -> None:
    # Cannot instantiate the abstract base directly.
    with pytest.raises(TypeError):
        SetColor()  # type: ignore[abstract]
