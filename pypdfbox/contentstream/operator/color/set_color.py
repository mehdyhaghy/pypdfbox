"""``sc / scn / SC / SCN`` — base class for stroking/non-stroking color ops.

Mirrors ``org.apache.pdfbox.contentstream.operator.color.SetColor`` (PDFBox 3.x;
Java path
``pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/color/SetColor.java``).
This is the upstream-shared abstract base for the four color-set operators —
:class:`SetStrokingColor`, :class:`SetNonStrokingColor`,
:class:`SetStrokingColorN`, :class:`SetNonStrokingColorN`. The existing port
collapses those four operator handlers into per-operator classes; this base
preserves the upstream class identity for parity tooling and future ports.
"""

from __future__ import annotations

from abc import abstractmethod
from typing import Any

from pypdfbox.cos import COSArray, COSBase, COSNumber

from .. import MissingOperandException, Operator
from ..operator_processor import OperatorProcessor


class SetColor(OperatorProcessor):
    """Abstract base for ``sc`` / ``scn`` / ``SC`` / ``SCN``.

    Subclasses implement :meth:`get_color` / :meth:`set_color` /
    :meth:`get_color_space` to plug into either the stroking or
    non-stroking arm of the graphics state.
    """

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        color_space = self.get_color_space()
        if color_space is None:
            return
        # PDPattern colorspace branches differently upstream (it lets the
        # last operand be a pattern name); mirror by short-circuiting.
        if not _is_pattern_colorspace(color_space):
            component_count = color_space.get_number_of_components()
            if len(operands) < component_count:
                raise MissingOperandException(operator, operands)
            if not self.check_array_types_class(operands, COSNumber):
                # PDFBOX-5851: invalid color when pattern colorspace is missing.
                self.set_color(_make_pd_color([], None))
                return
        array = COSArray()
        array.add_all(operands)
        self.set_color(_make_pd_color(array, color_space))

    @abstractmethod
    def get_color(self) -> Any:
        """Return the current stroking / non-stroking color."""

    @abstractmethod
    def set_color(self, color: Any) -> None:
        """Set the current stroking / non-stroking color."""

    @abstractmethod
    def get_color_space(self) -> Any:
        """Return the current stroking / non-stroking color space."""


def _is_pattern_colorspace(color_space: Any) -> bool:
    return type(color_space).__name__ == "PDPattern"


def _make_pd_color(components: Any, color_space: Any) -> Any:
    from pypdfbox.pdmodel.graphics.color import PDColor

    return PDColor(components, color_space)


__all__ = ["SetColor"]
