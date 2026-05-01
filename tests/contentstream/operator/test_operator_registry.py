from __future__ import annotations

import pytest

from pypdfbox.contentstream.operator import (
    MissingOperandException,
    Operator,
)
from pypdfbox.contentstream.operator.operator_processor import (
    OperatorProcessor,
)
from pypdfbox.contentstream.operator.operator_registry import (
    OperatorRegistry,
)
from pypdfbox.contentstream.operator.path.line_to import LineTo
from pypdfbox.contentstream.operator.path.move_to import MoveTo
from pypdfbox.contentstream.operator.state.restore_graphics_state import (
    RestoreGraphicsState,
)
from pypdfbox.contentstream.operator.state.save_graphics_state import (
    SaveGraphicsState,
)
from pypdfbox.contentstream.operator.text.move_text_position import (
    MoveTextPosition,
)
from pypdfbox.contentstream.operator.text.move_text_set_leading_handler import (
    MoveTextSetLeading,
)
from pypdfbox.contentstream.operator.text.set_font_and_size_handler import (
    SetFontAndSize,
)
from pypdfbox.contentstream.operator.text.set_text_matrix import (
    SetTextMatrix,
)
from pypdfbox.contentstream.operator.text.show_text_array import (
    ShowTextArray,
)
from pypdfbox.contentstream.operator.text.show_text_handler import ShowText
from pypdfbox.contentstream.operator.text.show_text_with_position import (
    ShowTextWithPosition,
)
from pypdfbox.contentstream.operator.text.show_text_with_word_and_char_spacing import (
    ShowTextWithWordAndCharSpacing,
)
from pypdfbox.cos import COSBase, COSString


# ---------- registry contents ----------


def test_registry_has_all_default_operators() -> None:
    """Every operator listed in the lite scaffold must resolve."""
    registry = OperatorRegistry()
    expected = {
        "Tj": ShowText,
        "TJ": ShowTextArray,
        "'": ShowTextWithPosition,
        '"': ShowTextWithWordAndCharSpacing,
        "Tf": SetFontAndSize,
        "Td": MoveTextPosition,
        "TD": MoveTextSetLeading,
        "Tm": SetTextMatrix,
        "q": SaveGraphicsState,
        "Q": RestoreGraphicsState,
        "m": MoveTo,
        "l": LineTo,
    }
    for name, expected_cls in expected.items():
        handler = registry.lookup(name)
        assert isinstance(handler, expected_cls), (
            f"lookup({name!r}) returned {type(handler).__name__}, "
            f"expected {expected_cls.__name__}"
        )


def test_lookup_show_text_returns_show_text_instance() -> None:
    registry = OperatorRegistry()
    handler = registry.lookup("Tj")
    assert isinstance(handler, ShowText)


def test_lookup_unknown_returns_none() -> None:
    registry = OperatorRegistry()
    assert registry.lookup("UNKNOWN") is None
    assert registry.lookup("ZZZ") is None


def test_lookup_returns_fresh_instances() -> None:
    """A fresh handler per lookup keeps invocations independent."""
    registry = OperatorRegistry()
    a = registry.lookup("Tj")
    b = registry.lookup("Tj")
    assert a is not b


# ---------- dispatch ----------


def test_process_known_operator_does_not_raise() -> None:
    registry = OperatorRegistry()
    registry.process(Operator("Tj"), [COSString(b"hello")])


def test_process_unknown_operator_silently_skipped() -> None:
    registry = OperatorRegistry()
    # No handler for ``ZZZ`` — should be a quiet no-op.
    registry.process(Operator("ZZZ"), [])


def test_process_all_default_operators_no_raise() -> None:
    """Every default handler without arity validation must accept its
    operator without raising in the lite scaffold (operands deliberately
    empty — stubs log only).

    ``m`` and ``l`` mirror upstream's ``MissingOperandException``
    behaviour and are exercised separately below.
    """
    registry = OperatorRegistry()
    for name in (
        "Tj",
        "TJ",
        "'",
        '"',
        "Tf",
        "Td",
        "TD",
        "Tm",
        "q",
        "Q",
    ):
        registry.process(Operator(name), [])


def test_process_move_to_and_line_to_raise_on_empty_operands() -> None:
    """``m`` and ``l`` mirror upstream's arity check and raise
    ``MissingOperandException`` with no operands."""
    registry = OperatorRegistry()
    for name in ("m", "l"):
        with pytest.raises(MissingOperandException):
            registry.process(Operator(name), [])


# ---------- registration overrides ----------


class _Recorder(OperatorProcessor):
    OPERATOR_NAME = "Tj"
    last_operands: list[COSBase] | None = None

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        type(self).last_operands = operands


def test_register_overrides_default() -> None:
    registry = OperatorRegistry()
    registry.register("Tj", _Recorder)
    handler = registry.lookup("Tj")
    assert isinstance(handler, _Recorder)
    assert not isinstance(handler, ShowText)


def test_register_dispatches_to_overridden_handler() -> None:
    registry = OperatorRegistry()
    registry.register("Tj", _Recorder)
    _Recorder.last_operands = None
    operands: list[COSBase] = [COSString(b"world")]
    registry.process(Operator("Tj"), operands)
    assert _Recorder.last_operands == operands


def test_register_new_operator() -> None:
    """Registering a brand-new operator name should make it routable."""

    class _CustomHandler(OperatorProcessor):
        OPERATOR_NAME = "XYZ"

        def process(
            self, operator: Operator, operands: list[COSBase]
        ) -> None:
            pass

    registry = OperatorRegistry()
    assert registry.lookup("XYZ") is None
    registry.register("XYZ", _CustomHandler)
    assert isinstance(registry.lookup("XYZ"), _CustomHandler)


def test_default_handlers_unaffected_by_instance_register() -> None:
    """``register`` on one registry must not bleed into another."""
    a = OperatorRegistry()
    b = OperatorRegistry()
    a.register("Tj", _Recorder)
    assert isinstance(a.lookup("Tj"), _Recorder)
    assert isinstance(b.lookup("Tj"), ShowText)


# ---------- handler get_name ----------


def test_handler_get_name_matches_operator_name() -> None:
    """OperatorProcessor.get_name() defaults to OPERATOR_NAME class attr."""
    pairs = [
        (ShowText, "Tj"),
        (ShowTextArray, "TJ"),
        (ShowTextWithPosition, "'"),
        (ShowTextWithWordAndCharSpacing, '"'),
        (SetFontAndSize, "Tf"),
        (MoveTextPosition, "Td"),
        (MoveTextSetLeading, "TD"),
        (SetTextMatrix, "Tm"),
        (SaveGraphicsState, "q"),
        (RestoreGraphicsState, "Q"),
        (MoveTo, "m"),
        (LineTo, "l"),
    ]
    for cls, expected in pairs:
        assert cls().get_name() == expected, (
            f"{cls.__name__}.get_name() != {expected!r}"
        )


# ---------- lite OperatorProcessor.get_context ----------


def test_lite_processor_get_context_returns_none_when_unbound() -> None:
    """Mirrors upstream ``OperatorProcessor.getContext`` accessor; lite
    scaffold returns ``None`` (rather than raising) so standalone
    registry use needs no engine."""
    p = MoveTo()
    assert p.get_context() is None


def test_lite_processor_get_context_returns_engine_when_bound() -> None:
    """``set_context`` round-trip through ``get_context`` — the accessor
    must report the engine that ``set_context`` recorded."""
    from pypdfbox.contentstream import PDFStreamEngine

    engine = PDFStreamEngine()
    p = MoveTo()
    p.set_context(engine)
    assert p.get_context() is engine


def test_lite_processor_get_context_returns_constructor_engine() -> None:
    """The lite ``OperatorProcessor`` constructor accepts an engine
    context; ``get_context`` reports the same instance."""
    from pypdfbox.contentstream import PDFStreamEngine

    engine = PDFStreamEngine()
    p = LineTo(engine)
    assert p.get_context() is engine
