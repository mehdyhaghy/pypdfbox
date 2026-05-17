"""Coverage-boost tests for ``MarkedContentPoint`` (wave 1323).

Targets the residual missing branches in
``pypdfbox.contentstream.operator.markedcontent.marked_content_point``:
the no-operands ``MissingOperandException`` guard, the silent return
when the first operand is not a ``COSName``, the no-context early
return, the no-hook silent return, and the ``get_name()`` accessor.
"""

from __future__ import annotations

import pytest

from pypdfbox.contentstream import Operator, PDFStreamEngine
from pypdfbox.contentstream.operator import MissingOperandException
from pypdfbox.contentstream.operator.markedcontent.marked_content_point import (
    MarkedContentPoint,
)
from pypdfbox.cos import COSDictionary, COSInteger, COSName, COSString


class _SpyEngine(PDFStreamEngine):
    """Records every ``marked_content_point`` callback for assertion."""

    def __init__(self) -> None:
        super().__init__()
        self.calls: list[tuple[COSName | None, COSDictionary | None]] = []

    def marked_content_point(
        self,
        tag: COSName | None,
        properties: COSDictionary | None,
    ) -> None:
        self.calls.append((tag, properties))


def test_process_no_operands_raises_missing_operand_exception() -> None:
    """Empty operand list must raise ``MissingOperandException`` so the
    interpreter surfaces the malformed content stream rather than
    silently dropping the operator."""
    processor = MarkedContentPoint()
    with pytest.raises(MissingOperandException):
        processor.process(Operator.get_operator("MP"), [])


def test_process_non_cos_name_first_operand_is_silent_no_op() -> None:
    """Upstream returns silently when the first operand isn't a name —
    the MP operator only carries a single ``/Tag`` token."""
    engine = _SpyEngine()
    processor = MarkedContentPoint()
    engine.add_operator(processor)
    processor.process(Operator.get_operator("MP"), [COSString("not-a-name")])
    assert engine.calls == []


def test_process_non_cos_name_integer_first_operand_is_silent_no_op() -> None:
    """A numeric operand also takes the ``not isinstance(.., COSName)``
    branch — distinct token type from the string case above."""
    engine = _SpyEngine()
    processor = MarkedContentPoint()
    engine.add_operator(processor)
    processor.process(Operator.get_operator("MP"), [COSInteger.get(7)])
    assert engine.calls == []


def test_process_without_context_silently_returns() -> None:
    """A processor with no attached engine has ``_context is None`` —
    the body must return without raising or recording anything."""
    processor = MarkedContentPoint()
    processor.process(Operator.get_operator("MP"), [COSName.get_pdf_name("Foo")])


def test_process_with_engine_lacking_hook_is_silent() -> None:
    """A vanilla ``PDFStreamEngine`` does not implement
    ``marked_content_point``; the operator must respect ``getattr(.., None)``
    and return without raising."""
    engine = PDFStreamEngine()
    processor = MarkedContentPoint()
    engine.add_operator(processor)
    processor.process(Operator.get_operator("MP"), [COSName.get_pdf_name("Foo")])


def test_process_dispatches_to_engine_hook_with_none_properties() -> None:
    """Happy path: a COSName tag with a hook-bearing engine must invoke
    the hook with ``(tag, None)`` — MP carries no property dictionary."""
    engine = _SpyEngine()
    processor = MarkedContentPoint()
    engine.add_operator(processor)
    tag = COSName.get_pdf_name("Span")
    processor.process(Operator.get_operator("MP"), [tag])
    assert engine.calls == [(tag, None)]


def test_process_ignores_trailing_operands_after_name() -> None:
    """MP takes a single tag; trailing operands are silently dropped
    when the first is a name. Only ``operands[0]`` is forwarded."""
    engine = _SpyEngine()
    processor = MarkedContentPoint()
    engine.add_operator(processor)
    tag = COSName.get_pdf_name("Tag")
    extra = COSString("extra")
    processor.process(Operator.get_operator("MP"), [tag, extra])
    assert engine.calls == [(tag, None)]


def test_get_name_returns_mp_operator_name() -> None:
    """``get_name()`` must return the ``OperatorName.MARKED_CONTENT_POINT``
    constant — i.e. the literal ``"MP"``."""
    assert MarkedContentPoint().get_name() == "MP"


def test_operator_name_class_attribute_matches_constant() -> None:
    """``OPERATOR_NAME`` mirrors the upstream ``static final String NAME``
    so dispatch tables can key off the class attribute directly."""
    assert MarkedContentPoint.OPERATOR_NAME == "MP"
