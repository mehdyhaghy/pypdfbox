"""Coverage round-out for ``EndMarkedContentSequence`` (``EMC``).

Targets the defensive branches not exercised by the existing
``test_end_marked_content.py`` suite — specifically the
``context is None`` early return and the ``hook is None`` early return
(when bound to a stripped-down engine that has had its
``end_marked_content_sequence`` attribute removed).
"""

from __future__ import annotations

from pypdfbox.contentstream import Operator, PDFStreamEngine
from pypdfbox.contentstream.operator.markedcontent.end_marked_content_sequence import (  # noqa: E501
    EndMarkedContentSequence,
)
from pypdfbox.cos import COSInteger, COSName


class _CountingEngine(PDFStreamEngine):
    """Spy engine that counts ``EMC`` notifications."""

    def __init__(self) -> None:
        super().__init__()
        self.end_calls: int = 0

    def end_marked_content_sequence(self) -> None:
        self.end_calls += 1


def test_process_with_no_context_returns_silently() -> None:
    """No context bound → process must early-return without raising.

    Note: the ``EndMarkedContentSequence`` body reads ``self._context``
    directly (not through ``get_context()``), so the ``None`` short-
    circuit returns silently even though ``get_context()`` would raise.
    """
    processor = EndMarkedContentSequence()
    # Direct attribute check — get_context() raises on None per the
    # strict base ``OperatorProcessor`` contract.
    assert processor._context is None  # noqa: SLF001 - intentional probe
    processor.process(Operator.get_operator("EMC"), [])


def test_process_with_engine_lacking_hook_attribute_is_silent() -> None:
    """Engine whose ``end_marked_content_sequence`` attribute is missing
    (set to ``None`` so ``getattr`` returns ``None``) must not raise.
    Mirrors upstream defensive ``hook is not None`` check."""

    class _NoHookEngine(PDFStreamEngine):
        end_marked_content_sequence = None  # type: ignore[assignment]

    engine = _NoHookEngine()
    processor = EndMarkedContentSequence(engine)
    processor.process(Operator.get_operator("EMC"), [])


def test_process_ignores_arbitrary_operand_payloads() -> None:
    """``EMC`` ignores operands per spec — exercise a mixed list."""
    engine = _CountingEngine()
    processor = EndMarkedContentSequence(engine)
    processor.process(
        Operator.get_operator("EMC"),
        [COSName.get_pdf_name("X"), COSInteger.get(7)],
    )
    assert engine.end_calls == 1


def test_get_name_returns_emc_constant() -> None:
    """``get_name`` is the public dispatch key — must equal ``EMC``."""
    assert EndMarkedContentSequence().get_name() == "EMC"
    assert EndMarkedContentSequence.OPERATOR_NAME == "EMC"


def test_set_context_late_binding_engages_hook() -> None:
    """An instance constructed standalone can later be bound via
    ``set_context`` and then call the engine hook."""
    processor = EndMarkedContentSequence()
    engine = _CountingEngine()
    processor.set_context(engine)
    processor.process(Operator.get_operator("EMC"), [])
    assert engine.end_calls == 1
