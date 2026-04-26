from __future__ import annotations

from typing import ClassVar

from pypdfbox.cos import COSBase

from . import Operator
from .operator_processor import OperatorProcessor
from .path.line_to import LineTo
from .path.move_to import MoveTo
from .state.restore_graphics_state import RestoreGraphicsState
from .state.save_graphics_state import SaveGraphicsState
from .text.move_text_position import MoveTextPosition
from .text.set_text_matrix import SetTextMatrix
from .text.show_text_array import ShowTextArray
from .text.show_text_handler import ShowText
from .text.show_text_with_position import ShowTextWithPosition
from .text.show_text_with_word_and_char_spacing import (
    ShowTextWithWordAndCharSpacing,
)
from .text.set_font_and_size_handler import SetFontAndSize
from .text.move_text_set_leading_handler import MoveTextSetLeading


class OperatorRegistry:
    """
    Operator-name to :class:`OperatorProcessor` dispatcher.

    Sibling of the engine-coupled registration on
    :class:`PDFStreamEngine`: where the engine binds each processor to
    itself via ``add_operator``, this registry stores plain processor
    classes (instantiated lazily on lookup) so it can be used for
    operator routing without an engine context.

    Mirrors the conceptual shape of upstream PDFBox's per-engine
    operator map but factored out as a standalone object so tooling
    code (parser-only consumers, validators, future content-stream
    rewriters) can route operators to handlers without spinning up a
    full :class:`PDFStreamEngine`.

    Defaults are populated from :attr:`_DEFAULT_HANDLERS` at
    construction; callers override or extend with :meth:`register`.
    """

    _DEFAULT_HANDLERS: ClassVar[dict[str, type[OperatorProcessor]]] = {
        # text operators
        ShowText.OPERATOR_NAME: ShowText,
        ShowTextArray.OPERATOR_NAME: ShowTextArray,
        ShowTextWithPosition.OPERATOR_NAME: ShowTextWithPosition,
        ShowTextWithWordAndCharSpacing.OPERATOR_NAME: (
            ShowTextWithWordAndCharSpacing
        ),
        SetFontAndSize.OPERATOR_NAME: SetFontAndSize,
        MoveTextPosition.OPERATOR_NAME: MoveTextPosition,
        MoveTextSetLeading.OPERATOR_NAME: MoveTextSetLeading,
        SetTextMatrix.OPERATOR_NAME: SetTextMatrix,
        # graphics-state operators
        SaveGraphicsState.OPERATOR_NAME: SaveGraphicsState,
        RestoreGraphicsState.OPERATOR_NAME: RestoreGraphicsState,
        # path-construction operators
        MoveTo.OPERATOR_NAME: MoveTo,
        LineTo.OPERATOR_NAME: LineTo,
    }

    def __init__(self) -> None:
        self._handlers: dict[str, type[OperatorProcessor]] = dict(
            self._DEFAULT_HANDLERS
        )

    # ---------- registration ----------

    def register(
        self, name: str, processor_class: type[OperatorProcessor]
    ) -> None:
        """Register (or override) the handler class for ``name``."""
        self._handlers[name] = processor_class

    # ---------- lookup ----------

    def lookup(self, name: str) -> OperatorProcessor | None:
        """Return a fresh handler instance for ``name``, or ``None`` if
        no handler is registered. A new instance per lookup keeps each
        dispatch independent — handlers may carry per-invocation state
        in subclasses without leaking across operators."""
        cls = self._handlers.get(name)
        if cls is None:
            return None
        return cls()

    # ---------- dispatch ----------

    def process(
        self, operator: Operator, operands: list[COSBase]
    ) -> None:
        """Look up the handler for ``operator`` and call its
        :meth:`OperatorProcessor.process`. Unknown operators are
        silently skipped — matching the lenient default upstream
        ``PDFStreamEngine.unsupportedOperator`` shape."""
        handler = self.lookup(operator.get_name())
        if handler is None:
            return
        handler.process(operator, operands)


__all__ = ["OperatorRegistry"]
