"""Wave 1397 branch-coverage tests for ``PDFTextStripper``.

Closes False-branch arrows on the operator-state handler and the
arabic-form normaliser:

* Tf operator 760->769 — name operand isn't a COSName
* Tf operator 769->774 — size operand isn't a COSNumber
* ``_decode_text_bytes`` 1058->1066 — active font isn't a PDSimpleFont
* ``handle_pres_forms_for_arabic`` 1904->1907 — second arabic char
  with ``had_change`` already True (loop body's inner-if False arm)
* ``normalize_add`` 2020->exit — item's text position is None
* ``handle_line_separation`` 2081->2083 — is_paragraph_separation False
* ``begin_marked_content_sequence`` 2113->2120 — properties is None
"""

from __future__ import annotations

from typing import Any

from pypdfbox.cos import COSInteger, COSName, COSString
from pypdfbox.text.pdf_text_stripper import PDFTextStripper, _TextState


def test_tf_operator_skips_when_name_operand_is_not_cosname() -> None:
    """Closes 760->769: name operand is a COSString, not COSName —
    state.font_name is left untouched."""
    stripper = PDFTextStripper()
    state = _TextState()
    state.font_name = "preserved"
    # Tf with a non-COSName name → branch at 760 short-circuits.
    stripper._dispatch(  # noqa: SLF001
        "Tf", [COSString("F1"), COSInteger.get(12)], state, [],
    )
    # font_name is unchanged because the COSName branch was skipped.
    assert state.font_name == "preserved"


def test_tf_operator_skips_when_size_operand_is_not_cosnumber() -> None:
    """Closes 769->774: size operand isn't a COSNumber — state.font_size
    is left untouched."""
    stripper = PDFTextStripper()
    state = _TextState()
    state.font_size = 99.0
    # COSName for size — invalid; size branch is skipped.
    stripper._dispatch(  # noqa: SLF001
        "Tf",
        [COSName.get_pdf_name("F1"), COSName.get_pdf_name("NotANumber")],
        state,
        [],
    )
    assert state.font_size == 99.0  # unchanged


def test_decode_text_bytes_with_non_simple_font_falls_back_to_latin1() -> None:
    """Closes 1058->1066: when ``_active_font`` is not a PDSimpleFont
    the helper falls back to latin-1 decoding."""
    stripper = PDFTextStripper()

    class _NotASimpleFont:
        """Has a ``decode`` method but is NOT a PDSimpleFont — branch
        falls through to the latin-1 fallback."""

        def decode(self, b: bytes) -> str:
            return "should-not-be-used"

    stripper._active_font = _NotASimpleFont()  # noqa: SLF001
    assert stripper._decode_show_text(b"abc") == "abc"  # noqa: SLF001


def test_handle_pres_forms_for_arabic_second_char_skips_buffer_reset() -> None:
    """Closes 1904->1907: a string with TWO arabic-presentation-form
    chars hits the True arm on iter 1 (had_change flips to True), then
    the False arm on iter 2 (had_change already True; skip reset)."""
    stripper = PDFTextStripper()
    # Two FB-block presentation forms back to back.
    word = "ﬀﬁ"
    out = stripper.normalize_word(word)
    assert out != word  # normalised


def test_normalize_add_with_item_returning_none_text_position() -> None:
    """Closes 2020->exit: an item whose ``get_text_position()`` is None
    — the append branch is skipped."""
    stripper = PDFTextStripper()

    class _Item:
        def is_word_separator(self) -> bool:
            return False

        def get_text_position(self) -> Any:
            return None

    line_builder: list[str] = []
    word_positions: list[Any] = []
    stripper.normalize_add([], line_builder, word_positions, _Item())  # type: ignore[arg-type]
    # No appends happened.
    assert line_builder == []
    assert word_positions == []


def test_handle_line_separation_skips_paragraph_when_not_separator() -> None:
    """Closes 2081->2083: ``is_paragraph_separation`` returns False —
    the paragraph-start mark is not applied."""
    stripper = PDFTextStripper()

    class _TP:
        pass

    class _Wrapper:
        def __init__(self) -> None:
            self.line_start = False
            self.para_start = False

        def set_line_start(self) -> None:
            self.line_start = True

        def get_text_position(self) -> _TP:
            return _TP()

        def set_paragraph_start(self) -> None:
            self.para_start = True

    current = _Wrapper()
    last_position = _Wrapper()
    # Force the is_paragraph_separation predicate False so the
    # set_paragraph_start branch is skipped.
    stripper.is_paragraph_separation = lambda a, b: False  # type: ignore[assignment]
    out = stripper.handle_line_separation(current, last_position, None, 0.0)  # type: ignore[arg-type]
    assert current.line_start is True
    assert current.para_start is False
    assert out is current


def test_begin_marked_content_sequence_with_none_properties() -> None:
    """Closes 2113->2120: ``properties`` is None — the ActualText
    lookup branch is skipped."""
    stripper = PDFTextStripper()
    stripper.begin_marked_content_sequence(COSName.get_pdf_name("Span"), None)
    # The stack received a (tag, None, None) tuple.
    assert len(stripper._marked_content_stack) == 1  # noqa: SLF001
    assert stripper._marked_content_stack[0][1] is None  # noqa: SLF001
