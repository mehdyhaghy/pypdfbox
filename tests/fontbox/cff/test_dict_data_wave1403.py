"""Wave 1403 — branch round-out for :class:`Entry` in
:mod:`pypdfbox.fontbox.cff.dict_data`.

Closes the partial arc ``[95,100]`` — the ``isinstance(operand, int)
and not isinstance(operand, bool)`` False branch in
:meth:`Entry.get_boolean`: when the operand is not an integer (e.g. a
float), the recognise-0/1 block is skipped entirely and the default is
returned after the warning.
"""

from __future__ import annotations

from pypdfbox.fontbox.cff.dict_data import Entry


def _entry(operator: str, *operands: object) -> Entry:
    e = Entry()
    for op in operands:
        e.add_operand(op)
    e.operator_name = operator
    return e


def test_get_boolean_non_int_operand_returns_default() -> None:
    """A float operand is not an ``int`` → the recognise-0/1 ``if`` takes
    its False arc ([95,100]) and the supplied default is returned."""
    e = _entry("isFixedPitch", 2.5)
    assert e.get_boolean(0, default_value=True) is True
    assert e.get_boolean(0, default_value=False) is False


def test_get_boolean_bool_operand_returns_default() -> None:
    """A ``bool`` operand also fails ``not isinstance(operand, bool)`` so
    the block is skipped and the default returned ([95,100])."""
    e = _entry("isFixedPitch", True)
    assert e.get_boolean(0, default_value=False) is False
