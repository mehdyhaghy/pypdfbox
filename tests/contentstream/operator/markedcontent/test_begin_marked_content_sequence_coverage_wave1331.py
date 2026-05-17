"""Coverage round-out for ``BeginMarkedContentSequence`` (``BMC``).

Targets the missed defensive branches:

* ``context is None`` → silent return.
* ``hook is None`` (engine attribute absent) → silent return.
* last-COSName-wins behaviour when multiple names appear.
"""

from __future__ import annotations

from pypdfbox.contentstream import Operator, PDFStreamEngine
from pypdfbox.contentstream.operator.markedcontent.begin_marked_content_sequence import (  # noqa: E501
    BeginMarkedContentSequence,
)
from pypdfbox.cos import COSDictionary, COSInteger, COSName, COSString


class _BmcSpyEngine(PDFStreamEngine):
    """Engine recording every ``BMC`` invocation."""

    def __init__(self) -> None:
        super().__init__()
        self.calls: list[tuple[COSName | None, COSDictionary | None]] = []

    def begin_marked_content_sequence(
        self,
        tag: COSName | None,
        properties: COSDictionary | None,
    ) -> None:
        self.calls.append((tag, properties))


def test_process_without_context_returns_silently() -> None:
    """No engine bound → no-op.

    The ``process`` body checks ``self._context`` directly; calling
    ``get_context()`` here would raise per the strict base contract, so
    we probe the underlying attribute instead.
    """
    processor = BeginMarkedContentSequence()
    assert processor._context is None  # noqa: SLF001 - intentional probe
    processor.process(
        Operator.get_operator("BMC"), [COSName.get_pdf_name("P")]
    )


def test_process_when_engine_lacks_hook_attribute_is_silent() -> None:
    """Engine whose ``begin_marked_content_sequence`` attribute is
    explicitly ``None`` → operator must skip the call without raising."""

    class _NoHook(PDFStreamEngine):
        begin_marked_content_sequence = None  # type: ignore[assignment]

    engine = _NoHook()
    processor = BeginMarkedContentSequence(engine)
    processor.process(
        Operator.get_operator("BMC"), [COSName.get_pdf_name("P")]
    )


def test_process_last_cos_name_wins_when_multiple_names() -> None:
    """If multiple COSName operands appear (defensive scan, not a real
    parser case), the last one is forwarded."""
    engine = _BmcSpyEngine()
    processor = BeginMarkedContentSequence(engine)
    first = COSName.get_pdf_name("Span")
    second = COSName.get_pdf_name("P")
    processor.process(Operator.get_operator("BMC"), [first, second])
    assert engine.calls == [(second, None)]


def test_process_skips_non_name_operands() -> None:
    """COSString / COSInteger / COSDictionary entries are filtered out
    by the ``isinstance`` guard; only a trailing COSName updates ``tag``."""
    engine = _BmcSpyEngine()
    processor = BeginMarkedContentSequence(engine)
    only_name = COSName.get_pdf_name("Figure")
    processor.process(
        Operator.get_operator("BMC"),
        [COSString("noise"), COSInteger.get(3), only_name],
    )
    assert engine.calls == [(only_name, None)]


def test_process_with_only_non_name_operands_sends_none_tag() -> None:
    """No COSName anywhere → engine still notified with tag=None."""
    engine = _BmcSpyEngine()
    processor = BeginMarkedContentSequence(engine)
    processor.process(
        Operator.get_operator("BMC"),
        [COSString("nope"), COSInteger.get(0)],
    )
    assert engine.calls == [(None, None)]


def test_process_with_empty_operands_sends_none_tag() -> None:
    """Empty operand list → hook fires with ``tag=None``."""
    engine = _BmcSpyEngine()
    processor = BeginMarkedContentSequence(engine)
    processor.process(Operator.get_operator("BMC"), [])
    assert engine.calls == [(None, None)]


def test_get_name_returns_bmc_constant() -> None:
    """``get_name`` returns the ``BMC`` operator token."""
    assert BeginMarkedContentSequence().get_name() == "BMC"
    assert BeginMarkedContentSequence.OPERATOR_NAME == "BMC"


def test_set_context_late_binding_engages_hook() -> None:
    """An instance bound via ``set_context`` after construction still
    routes ``BMC`` through the engine hook."""
    processor = BeginMarkedContentSequence()
    engine = _BmcSpyEngine()
    processor.set_context(engine)
    tag = COSName.get_pdf_name("Sect")
    processor.process(Operator.get_operator("BMC"), [tag])
    assert engine.calls == [(tag, None)]
