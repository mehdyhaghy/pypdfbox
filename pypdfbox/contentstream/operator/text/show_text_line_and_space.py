from __future__ import annotations

from typing import ClassVar

from pypdfbox.cos import COSBase, COSNumber, COSString

from .. import (
    MissingOperandException,
    Operator,
    OperatorName,
    OperatorProcessor,
)


class ShowTextLineAndSpace(OperatorProcessor):
    """``"`` (quotation mark) — Set word & character spacing, move to
    next line, show text. Mirrors
    ``org.apache.pdfbox.contentstream.operator.text.ShowTextLineAndSpace``.

    Operand shape: ``<aw> <ac> <string> "``. Decomposes into ``Tw`` /
    ``Tc`` / ``'`` per ISO 32000-1 §9.4.3, dispatched via the engine so
    the constituent processors fire if registered.

    Class-level constants:

    * :attr:`MIN_OPERANDS` — minimum required operand count (3) per
      ISO 32000-1 §9.4.3. Mirrors upstream's ``arguments.size() < 3``
      guard.
    * :attr:`SUB_OPERATORS` — the ordered triple of sub-operator names
      this composite dispatches to (``Tw``, ``Tc``, ``'``). Useful for
      registry callers that want to confirm the expected sub-handler set
      is registered before processing.
    """

    #: Minimum operand count required by ISO 32000-1 §9.4.3.
    MIN_OPERANDS: ClassVar[int] = 3

    #: Ordered sub-operators this composite dispatches via the engine.
    SUB_OPERATORS: ClassVar[tuple[str, str, str]] = (
        OperatorName.SET_WORD_SPACING,
        OperatorName.SET_CHAR_SPACING,
        OperatorName.SHOW_TEXT_LINE,
    )

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        if len(operands) < self.MIN_OPERANDS:
            raise MissingOperandException(operator, operands)
        ctx = self.get_context()
        ctx.process_operator(OperatorName.SET_WORD_SPACING, [operands[0]])
        ctx.process_operator(OperatorName.SET_CHAR_SPACING, [operands[1]])
        ctx.process_operator(OperatorName.SHOW_TEXT_LINE, [operands[2]])

    def get_name(self) -> str:
        return OperatorName.SHOW_TEXT_LINE_AND_SPACE

    @staticmethod
    def split_operands(
        operands: list[COSBase],
    ) -> tuple[COSNumber, COSNumber, COSString] | None:
        """Return the ``(aw, ac, string)`` triple if ``operands`` matches
        the upstream ``"`` operand shape, else ``None``.

        Pure helper — does NOT raise. Useful for inspection or pre-check
        from registry-level callers without instantiating the engine.
        Mirrors the upstream operand layout per ISO 32000-1 §9.4.3:

        * ``operands[0]`` (``aw``): a :class:`COSNumber` (word spacing).
        * ``operands[1]`` (``ac``): a :class:`COSNumber` (character
          spacing).
        * ``operands[2]`` (``string``): a :class:`COSString` (text to
          show).

        Returns ``None`` when ``operands`` has fewer than three entries
        or when any entry is the wrong type. The engine path
        (:meth:`process`) does not consult this helper — upstream
        forwards each operand to the sub-operator and lets each apply
        its own type guard, which we mirror — so this helper is purely
        an inspection convenience.
        """
        if len(operands) < ShowTextLineAndSpace.MIN_OPERANDS:
            return None
        aw, ac, string = operands[0], operands[1], operands[2]
        if not isinstance(aw, COSNumber):
            return None
        if not isinstance(ac, COSNumber):
            return None
        if not isinstance(string, COSString):
            return None
        return aw, ac, string

    @classmethod
    def accepts(cls, operands: list[COSBase]) -> bool:
        """Return ``True`` if ``operands`` would not raise
        :class:`MissingOperandException` when passed to
        :meth:`process`.

        Equivalent to ``len(operands) >= cls.MIN_OPERANDS``. Type checks
        on the individual operands are NOT performed here — upstream's
        composite dispatch delegates type validation to the sub-
        operators (a wrong-typed operand silently no-ops there), so
        ``accepts`` reports only the operand-count contract.
        """
        return len(operands) >= cls.MIN_OPERANDS
