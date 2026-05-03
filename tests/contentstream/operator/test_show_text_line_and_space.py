from __future__ import annotations

import pytest

from pypdfbox.contentstream import (
    MissingOperandException,
    Operator,
    OperatorName,
    PDFStreamEngine,
)
from pypdfbox.contentstream.operator.text import (
    ShowText,
    ShowTextLine,
    ShowTextLineAndSpace,
)
from pypdfbox.cos import COSBase, COSFloat, COSInteger, COSName, COSString


class _Spy(PDFStreamEngine):
    def __init__(self) -> None:
        super().__init__()
        self.shown: bytes | None = None
        self.unsupported: list[tuple[str, list[COSBase]]] = []

    def show_text_string(self, text: bytes) -> None:
        self.shown = text

    def unsupported_operator(self, operator: Operator, operands: list[COSBase]) -> None:
        self.unsupported.append((operator.get_name(), list(operands)))


def test_get_name() -> None:
    assert ShowTextLineAndSpace().get_name() == '"'


def test_process_decomposes_to_tw_tc_quote() -> None:
    engine = _Spy()
    engine.add_operator(ShowText())
    engine.add_operator(ShowTextLine())
    p = ShowTextLineAndSpace()
    engine.add_operator(p)
    p.process(
        Operator.get_operator('"'),
        [COSInteger.get(1), COSFloat(2.0), COSString(b"hi")],
    )
    names = [n for n, _ in engine.unsupported]
    assert "Tw" in names
    assert "Tc" in names
    # T* is unsupported too because we didn't register a NEXT_LINE handler.
    assert "T*" in names
    assert engine.shown == b"hi"


def test_too_few_operands_raises() -> None:
    p = ShowTextLineAndSpace()
    engine = _Spy()
    engine.add_operator(p)
    with pytest.raises(MissingOperandException):
        p.process(
            Operator.get_operator('"'),
            [COSInteger.get(1), COSInteger.get(2)],
        )


# --- Wave 220 round-out: typed accessors + predicate + constants ----------


def test_get_name_matches_operator_name_constant() -> None:
    """``get_name`` resolves to the centrally-defined string."""
    assert (
        ShowTextLineAndSpace().get_name()
        == OperatorName.SHOW_TEXT_LINE_AND_SPACE
    )


def test_min_operands_constant_is_three() -> None:
    """ISO 32000-1 §9.4.3 — the ``"`` operator takes three operands."""
    assert ShowTextLineAndSpace.MIN_OPERANDS == 3


def test_sub_operators_constant_lists_dispatched_names() -> None:
    """``SUB_OPERATORS`` enumerates the ordered triple of sub-operators
    the composite dispatches to via the engine."""
    assert ShowTextLineAndSpace.SUB_OPERATORS == ("Tw", "Tc", "'")


def test_sub_operators_constant_matches_operator_name_constants() -> None:
    """Each entry in ``SUB_OPERATORS`` must be a centrally-defined
    :class:`OperatorName` constant — guards against drift if either
    side is renamed."""
    assert ShowTextLineAndSpace.SUB_OPERATORS == (
        OperatorName.SET_WORD_SPACING,
        OperatorName.SET_CHAR_SPACING,
        OperatorName.SHOW_TEXT_LINE,
    )


def test_re_export_canonical() -> None:
    """``ShowTextLineAndSpace`` must be importable from the package
    surface as the same class object."""
    from pypdfbox.contentstream.operator.text import (
        ShowTextLineAndSpace as Reexport,
    )

    assert Reexport is ShowTextLineAndSpace


def test_zero_operands_raises_with_carrying_metadata() -> None:
    """``MissingOperandException`` carries the operator and operand list."""
    p = ShowTextLineAndSpace()
    engine = _Spy()
    engine.add_operator(p)
    op = Operator.get_operator('"')
    with pytest.raises(MissingOperandException) as exc_info:
        p.process(op, [])
    assert exc_info.value.operator is op
    assert exc_info.value.operands == []
    assert '"' in str(exc_info.value)
    assert "too few operands" in str(exc_info.value)


def test_one_operand_raises() -> None:
    p = ShowTextLineAndSpace()
    engine = _Spy()
    engine.add_operator(p)
    with pytest.raises(MissingOperandException):
        p.process(Operator.get_operator('"'), [COSInteger.get(1)])


def test_extra_operands_are_ignored() -> None:
    """Upstream only consults the first three operands — anything trailing
    is silently dropped."""
    engine = _Spy()
    engine.add_operator(ShowText())
    engine.add_operator(ShowTextLine())
    p = ShowTextLineAndSpace()
    engine.add_operator(p)
    p.process(
        Operator.get_operator('"'),
        [
            COSInteger.get(1),
            COSFloat(2.0),
            COSString(b"hi"),
            COSFloat(99.0),
            COSString(b"ignored"),
        ],
    )
    assert engine.shown == b"hi"


def test_get_context_unbound_raises() -> None:
    """Calling ``process`` before binding raises ``RuntimeError``."""
    p = ShowTextLineAndSpace()
    with pytest.raises(RuntimeError):
        p.process(
            Operator.get_operator('"'),
            [COSInteger.get(1), COSFloat(2.0), COSString(b"hi")],
        )


def test_split_operands_returns_typed_triple() -> None:
    """Pure inspection helper — returns the ``(aw, ac, string)`` typed
    triple when operand shape is valid."""
    aw = COSFloat(0.5)
    ac = COSInteger.get(2)
    s = COSString(b"hi")
    result = ShowTextLineAndSpace.split_operands([aw, ac, s])
    assert result == (aw, ac, s)


def test_split_operands_returns_none_for_short_list() -> None:
    assert ShowTextLineAndSpace.split_operands([]) is None
    assert ShowTextLineAndSpace.split_operands([COSFloat(1.0)]) is None
    assert (
        ShowTextLineAndSpace.split_operands(
            [COSFloat(1.0), COSFloat(2.0)]
        )
        is None
    )


def test_split_operands_rejects_non_number_aw() -> None:
    """``aw`` (first operand) must be a :class:`COSNumber`."""
    bad = [COSString(b"oops"), COSFloat(2.0), COSString(b"hi")]
    assert ShowTextLineAndSpace.split_operands(bad) is None


def test_split_operands_rejects_non_number_ac() -> None:
    """``ac`` (second operand) must be a :class:`COSNumber`."""
    bad = [COSFloat(1.0), COSString(b"oops"), COSString(b"hi")]
    assert ShowTextLineAndSpace.split_operands(bad) is None


def test_split_operands_rejects_non_string_third() -> None:
    """The third operand must be a :class:`COSString`."""
    bad = [COSFloat(1.0), COSFloat(2.0), COSName.get_pdf_name("Oops")]
    assert ShowTextLineAndSpace.split_operands(bad) is None


def test_split_operands_ignores_trailing_operands() -> None:
    """Extra operands beyond the first three don't affect the parse —
    upstream's ``subList(0,1)``/``(1,2)``/``(2,3)`` slices already do
    this."""
    aw = COSFloat(0.5)
    ac = COSInteger.get(2)
    s = COSString(b"hi")
    result = ShowTextLineAndSpace.split_operands(
        [aw, ac, s, COSFloat(99.0), COSString(b"trailer")]
    )
    assert result == (aw, ac, s)


def test_accepts_predicate_matches_min_operands() -> None:
    """``accepts`` returns ``True`` iff operand count meets the minimum."""
    assert ShowTextLineAndSpace.accepts([]) is False
    assert ShowTextLineAndSpace.accepts([COSFloat(1.0)]) is False
    assert (
        ShowTextLineAndSpace.accepts([COSFloat(1.0), COSFloat(2.0)])
        is False
    )
    assert (
        ShowTextLineAndSpace.accepts(
            [COSFloat(1.0), COSFloat(2.0), COSString(b"hi")]
        )
        is True
    )


def test_accepts_predicate_ignores_operand_types() -> None:
    """``accepts`` checks only the operand count — type validation is
    deferred to the sub-operators (matching upstream's composite
    dispatch shape)."""
    assert ShowTextLineAndSpace.accepts(
        [COSString(b"oops"), COSString(b"oops"), COSString(b"hi")]
    )


def test_accepts_predicate_aligns_with_process_for_short_input() -> None:
    """``accepts`` is the negation of the ``MissingOperandException``
    guard in :meth:`process` — wherever ``accepts`` returns ``False``,
    ``process`` must raise."""
    p = ShowTextLineAndSpace()
    engine = _Spy()
    engine.add_operator(p)
    too_short = [COSFloat(1.0), COSFloat(2.0)]
    assert ShowTextLineAndSpace.accepts(too_short) is False
    with pytest.raises(MissingOperandException):
        p.process(Operator.get_operator('"'), too_short)


def test_process_dispatches_in_order() -> None:
    """The composite must dispatch ``Tw`` before ``Tc`` before ``'``,
    matching upstream's ordered ``processOperator`` chain — verified
    by the recorded order in the spy's unsupported list (since none of
    them are registered)."""
    p = ShowTextLineAndSpace()
    engine = _Spy()
    engine.add_operator(p)
    p.process(
        Operator.get_operator('"'),
        [COSFloat(0.5), COSFloat(1.0), COSString(b"x")],
    )
    names = [n for n, _ in engine.unsupported]
    # Tw must precede Tc, Tc must precede the eventual ' (which itself
    # decomposes into T* + Tj).
    assert names.index("Tw") < names.index("Tc")
    assert names.index("Tc") < names.index("'")


def test_process_forwards_each_operand_singly() -> None:
    """Each sub-operator dispatch wraps a single operand, mirroring
    upstream's ``arguments.subList(i, i+1)``."""
    aw = COSFloat(0.5)
    ac = COSFloat(1.0)
    s = COSString(b"x")
    p = ShowTextLineAndSpace()
    engine = _Spy()
    engine.add_operator(p)
    p.process(Operator.get_operator('"'), [aw, ac, s])
    by_name = {n: ops for n, ops in engine.unsupported}
    assert by_name["Tw"] == [aw]
    assert by_name["Tc"] == [ac]
    # ' fires before its inner T*+Tj decomposition
    assert by_name["'"] == [s]
