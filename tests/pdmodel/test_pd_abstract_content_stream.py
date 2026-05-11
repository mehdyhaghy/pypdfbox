from __future__ import annotations

import io

from pypdfbox.pdmodel import PDAbstractContentStream


class _Concrete(PDAbstractContentStream):
    """Minimal concrete subclass for testing the protected state."""


def test_cannot_instantiate_directly() -> None:
    # PDAbstractContentStream is abstract — but ABC only enforces this if
    # there are abstract methods. Here we just verify the subclass works.
    output = io.BytesIO()
    sub = _Concrete(None, output, None)
    assert sub.output_stream is output


def test_state_initialization() -> None:
    output = io.BytesIO()
    sub = _Concrete(None, output, None)
    assert sub.document is None
    assert sub.resources is None
    assert sub.in_text_mode is False
    assert sub.get_maximum_fraction_digits() == PDAbstractContentStream.DEFAULT_MAX_FRACTION_DIGITS


def test_set_max_fraction_digits() -> None:
    sub = _Concrete(None, io.BytesIO(), None)
    sub.set_maximum_fraction_digits(2)
    assert sub.get_maximum_fraction_digits() == 2


def test_set_max_fraction_digits_clamped_to_zero() -> None:
    sub = _Concrete(None, io.BytesIO(), None)
    sub.set_maximum_fraction_digits(-1)
    assert sub.get_maximum_fraction_digits() == 0


def test_context_manager_closes_output() -> None:
    output = io.BytesIO()
    with _Concrete(None, output, None) as sub:
        assert sub.output_stream is output
    assert output.closed


def test_close_handles_already_closed() -> None:
    output = io.BytesIO()
    output.close()
    sub = _Concrete(None, output, None)
    # Should not raise.
    sub.close()


def test_stacks_initialized_empty() -> None:
    sub = _Concrete(None, io.BytesIO(), None)
    assert not sub._font_stack
    assert not sub._stroking_color_space_stack
    assert not sub._non_stroking_color_space_stack
