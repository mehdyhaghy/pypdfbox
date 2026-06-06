"""Wave 1396 branch-coverage tests for ``PDFTextStripper._dispatch``.

Each text-state operator (``Tf``, ``TL``, ``Tj``, ``TJ``, ``'``, ``"``,
``Tc``, ``Tw``) guards its body with an operand-shape check. The False
arms (mistyped or missing operands) hit ``757->exit``, ``778->exit``,
``820->exit``, ``823->exit``, ``830->exit``, ``834->exit``,
``847->exit``, ``850->exit`` in
``pypdfbox/text/pdf_text_stripper.py``. These tests call ``_dispatch``
directly with bad operands and assert the state was *not* mutated.
"""

from __future__ import annotations

from pypdfbox.cos import COSInteger, COSName, COSString
from pypdfbox.text.pdf_text_stripper import PDFTextStripper, _TextState


def _state() -> _TextState:
    return _TextState()


def _stripper() -> PDFTextStripper:
    return PDFTextStripper()


def test_dispatch_tf_with_too_few_operands_keeps_state() -> None:
    """``Tf`` with <2 operands does not mutate font_name/size.

    Closes False arm at line 757 (``len(operands) >= 2``).
    """
    stripper = _stripper()
    state = _state()
    initial_name = state.font_name
    initial_size = state.font_size
    stripper._dispatch("Tf", [COSName.get_pdf_name("F1")], state, [])  # noqa: SLF001
    assert state.font_name == initial_name
    assert state.font_size == initial_size


def test_dispatch_tl_with_empty_operands_keeps_leading() -> None:
    """``TL`` with no operands does not mutate leading.

    Closes False arm at line 778 (``operands and isinstance(...)``).
    """
    stripper = _stripper()
    state = _state()
    initial = state.leading
    stripper._dispatch("TL", [], state, [])  # noqa: SLF001
    assert state.leading == initial


def test_dispatch_tj_with_non_string_operand_does_not_emit() -> None:
    """``Tj`` with a non-string operand is a no-op.

    Closes False arm at line 820 (``isinstance(operands[0], COSString)``).
    """
    stripper = _stripper()
    state = _state()
    state.in_text_object = True
    positions = []
    stripper._dispatch("Tj", [COSInteger.get(42)], state, positions)  # noqa: SLF001
    assert positions == []


def test_dispatch_tj_array_with_non_array_operand_does_not_emit() -> None:
    """``TJ`` with a non-array operand is a no-op.

    Closes False arm at line 823 (``isinstance(operands[0], COSArray)``).
    """
    stripper = _stripper()
    state = _state()
    state.in_text_object = True
    positions = []
    stripper._dispatch("TJ", [COSString("text")], state, positions)  # noqa: SLF001
    assert positions == []


def test_dispatch_quote_with_non_string_operand_advances_line_only() -> None:
    """``'`` with a non-string operand advances the line but emits nothing.

    Closes False arm at line 830 (``isinstance(operands[0], COSString)``).
    """
    stripper = _stripper()
    state = _state()
    # ``'`` decomposes to ``T*`` + ``Tj``; both are no-ops outside a text
    # object (upstream gates them on a non-null text/line matrix), so open one
    # first to exercise the line-advance branch.
    state.in_text_object = True
    state.leading = 12.0
    positions = []
    stripper._dispatch("'", [COSInteger.get(99)], state, positions)  # noqa: SLF001
    # Line advanced by -leading.
    assert state.line_y == -12.0
    assert positions == []


def test_dispatch_double_quote_with_too_few_operands_keeps_state() -> None:
    """``"`` with <3 operands or wrong types is a no-op.

    Closes False arm at line 834 (multi-condition operand check).
    """
    stripper = _stripper()
    state = _state()
    initial_ws = state.word_spacing
    initial_cs = state.char_spacing
    positions = []
    stripper._dispatch('"', [COSInteger.get(1), COSString("x")], state, positions)  # noqa: SLF001
    assert state.word_spacing == initial_ws
    assert state.char_spacing == initial_cs
    assert positions == []


def test_dispatch_tc_with_non_number_operand_keeps_char_spacing() -> None:
    """``Tc`` with a non-number operand is a no-op.

    Closes False arm at line 847 (``isinstance(operands[0], COSNumber)``).
    """
    stripper = _stripper()
    state = _state()
    initial = state.char_spacing
    stripper._dispatch("Tc", [COSName.get_pdf_name("X")], state, [])  # noqa: SLF001
    assert state.char_spacing == initial


def test_dispatch_tw_with_non_number_operand_keeps_word_spacing() -> None:
    """``Tw`` with a non-number operand is a no-op.

    Closes False arm at line 850 (``isinstance(operands[0], COSNumber)``).
    """
    stripper = _stripper()
    state = _state()
    initial = state.word_spacing
    stripper._dispatch("Tw", [COSName.get_pdf_name("X")], state, [])  # noqa: SLF001
    assert state.word_spacing == initial
