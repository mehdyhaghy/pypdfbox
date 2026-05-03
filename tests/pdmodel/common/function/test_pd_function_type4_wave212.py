"""Wave 212 round-out for ``PDFunctionType4``.

Targets small remaining gaps:

* ``get_operator(name)`` / ``is_supported_operator(name)`` lookup helpers
  (parity with upstream ``Operators.getOperator``).
* Operator name groupings — ``ARITHMETIC_OPERATORS``, ``STACK_OPERATORS``,
  ``BOOLEAN_OPERATORS``, ``CONDITIONAL_OPERATORS``, ``ALL_OPERATORS``.
* ``get_instructions()`` typed accessor — exposes the parsed instruction
  sequence (mirrors upstream ``InstructionSequence`` field).
* Output-count validation — when ``/Range`` declares N outputs and the
  program leaves fewer values, raise ``OSError`` (mirrors upstream
  ``IllegalStateException``).
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSStream
from pypdfbox.pdmodel.common.function import PDFunctionType4
from pypdfbox.pdmodel.common.function import pd_function_type4 as ps_module


def _make(
    body: str,
    *,
    domain: list[float] | None = None,
    rng: list[float] | None = None,
) -> PDFunctionType4:
    raw = COSStream()
    raw.set_int("FunctionType", 4)
    if domain is not None:
        d = COSArray()
        d.set_float_array(domain)
        raw.set_item("Domain", d)
    if rng is not None:
        r = COSArray()
        r.set_float_array(rng)
        raw.set_item("Range", r)
    raw.set_data(body.encode("utf-8"))
    return PDFunctionType4(raw)


# --------------------------------------------------------------------------
# get_operator / is_supported_operator
# --------------------------------------------------------------------------


def test_get_operator_returns_callable_for_known_op() -> None:
    """``get_operator`` mirrors ``Operators.getOperator`` — callable for
    every registered name."""
    op = ps_module.get_operator("add")
    assert op is not None
    assert callable(op)


def test_get_operator_returns_none_for_unknown_name() -> None:
    """Upstream ``Operators.getOperator`` returns null for unregistered
    names; we return ``None``."""
    assert ps_module.get_operator("frobnicate") is None
    assert ps_module.get_operator("") is None
    assert ps_module.get_operator("ADD") is None  # case-sensitive


def test_get_operator_executes_on_a_supplied_stack() -> None:
    """The callable returned by ``get_operator`` is the same one the
    executor uses — invoking it manually mutates the supplied stack."""
    op = ps_module.get_operator("add")
    stack: list = [3.0, 4.0]
    op(stack)
    assert stack == [pytest.approx(7.0)]


def test_is_supported_operator_for_each_registered_name() -> None:
    for name in ps_module.ALL_OPERATORS:
        assert ps_module.is_supported_operator(name), name


def test_is_supported_operator_rejects_unknown_names() -> None:
    assert not ps_module.is_supported_operator("frobnicate")
    assert not ps_module.is_supported_operator("def")  # disallowed in Type 4
    assert not ps_module.is_supported_operator("for")
    assert not ps_module.is_supported_operator("forall")
    assert not ps_module.is_supported_operator("")


# --------------------------------------------------------------------------
# Operator-name groupings
# --------------------------------------------------------------------------


def test_arithmetic_operators_grouping_matches_spec() -> None:
    """The arithmetic group must match PDF 32000-1 §7.10.5 Table 41."""
    expected = {
        "add", "sub", "mul", "div", "idiv", "mod", "neg", "abs",
        "ceiling", "floor", "round", "truncate", "sqrt", "sin", "cos",
        "atan", "exp", "ln", "log", "cvi", "cvr",
    }
    assert set(ps_module.ARITHMETIC_OPERATORS) == expected


def test_stack_operators_grouping_matches_spec() -> None:
    """Stack group per PDF 32000-1 §7.10.5 Table 42."""
    expected = {"dup", "exch", "pop", "copy", "index", "roll"}
    assert set(ps_module.STACK_OPERATORS) == expected


def test_boolean_operators_grouping_includes_relational_and_bitwise() -> None:
    """PDFBox splits these into two Java files but registers them in one
    map; we keep the combined view."""
    expected = {
        "eq", "ne", "lt", "le", "gt", "ge",
        "and", "or", "xor", "not", "bitshift",
        "true", "false",
    }
    assert set(ps_module.BOOLEAN_OPERATORS) == expected


def test_conditional_operators_grouping() -> None:
    assert set(ps_module.CONDITIONAL_OPERATORS) == {"if", "ifelse"}


def test_all_operators_is_disjoint_union_of_groups() -> None:
    """The four groups partition ``ALL_OPERATORS`` — every operator
    appears in exactly one group, and the union covers everything."""
    groups = (
        ps_module.ARITHMETIC_OPERATORS,
        ps_module.STACK_OPERATORS,
        ps_module.BOOLEAN_OPERATORS,
        ps_module.CONDITIONAL_OPERATORS,
    )
    union: set[str] = set()
    for group in groups:
        # Disjointness — no name appears in two groups.
        assert union.isdisjoint(group), set(group) & union
        union |= set(group)
    assert union == set(ps_module.ALL_OPERATORS)


def test_groupings_are_immutable_tuples() -> None:
    """Constants must be tuples (not lists) so callers can't mutate them."""
    assert isinstance(ps_module.ARITHMETIC_OPERATORS, tuple)
    assert isinstance(ps_module.STACK_OPERATORS, tuple)
    assert isinstance(ps_module.BOOLEAN_OPERATORS, tuple)
    assert isinstance(ps_module.CONDITIONAL_OPERATORS, tuple)
    assert isinstance(ps_module.ALL_OPERATORS, tuple)


# --------------------------------------------------------------------------
# get_instructions()
# --------------------------------------------------------------------------


def test_get_instructions_returns_parsed_sequence() -> None:
    """``get_instructions`` returns the parsed nested list. ``5 6 add``
    parses to ``[5.0, 6.0, "add"]``."""
    fn = _make("{ 5 6 add }", domain=[])
    seq = fn.get_instructions()
    assert seq == [5.0, 6.0, "add"]


def test_get_instructions_empty_body_is_empty_list() -> None:
    fn = _make("{ }", domain=[])
    assert fn.get_instructions() == []


def test_get_instructions_nested_procs_become_sublists() -> None:
    """A ``{ ... }`` block inside the program becomes a Python sub-list."""
    fn = _make("{ true { 1 2 add } if }", domain=[])
    seq = fn.get_instructions()
    # Outer: [True, [1.0, 2.0, "add"], "if"]
    assert seq[0] is True
    assert seq[1] == [1.0, 2.0, "add"]
    assert seq[2] == "if"


def test_get_instructions_caches_same_list_across_calls() -> None:
    """Subsequent calls must return the *same* list object — the cache
    is shared with ``eval``."""
    fn = _make("{ dup mul }", domain=[-10.0, 10.0])
    a = fn.get_instructions()
    b = fn.get_instructions()
    assert a is b


def test_get_instructions_primes_the_eval_cache() -> None:
    """Calling ``get_instructions`` first should populate the cache so
    that subsequent ``eval`` doesn't re-parse."""
    fn = _make("{ dup mul }", domain=[-10.0, 10.0])

    from unittest.mock import patch

    with patch.object(
        ps_module, "_parse", wraps=ps_module._parse
    ) as parse_spy:
        fn.get_instructions()
        fn.eval([3.0])
        fn.eval([4.0])
        assert parse_spy.call_count == 1


def test_clear_instruction_cache_invalidates_get_instructions() -> None:
    fn = _make("{ 1 2 add }", domain=[])
    first = fn.get_instructions()
    fn.clear_instruction_cache()
    second = fn.get_instructions()
    # Same content but a fresh list object after invalidation.
    assert first == second
    assert first is not second


# --------------------------------------------------------------------------
# Output-count validation against /Range
# --------------------------------------------------------------------------


def test_eval_raises_when_program_under_supplies_range() -> None:
    """``/Range`` declares 2 outputs but the program only leaves 1 value
    on the stack — upstream raises ``IllegalStateException``; we surface
    ``OSError``."""
    fn = _make(
        "{ pop 1 }",
        domain=[0.0, 1.0],
        rng=[0.0, 1.0, 0.0, 1.0],
    )
    with pytest.raises(OSError, match="returned 1 values"):
        fn.eval([0.5])


def test_eval_no_range_does_not_validate_output_count() -> None:
    """When ``/Range`` is absent, we skip the validation and return
    whatever's on the stack — preserves the no-range fast path used by
    inline shading helpers."""
    fn = _make("{ pop }", domain=[0.0, 1.0])
    assert fn.eval([0.5]) == []


def test_eval_with_zero_declared_outputs_passes_through() -> None:
    """An empty ``/Range`` array declares zero outputs; under-supply
    cannot occur in that case."""
    fn = _make("{ }", domain=[0.0, 1.0], rng=[])
    assert fn.eval([0.7]) == pytest.approx([0.7])


def test_eval_exact_match_of_output_count_succeeds() -> None:
    """Edge case: program leaves exactly N values when /Range declares
    N outputs."""
    fn = _make(
        "{ dup }",
        domain=[0.0, 1.0],
        rng=[0.0, 1.0, 0.0, 1.0],
    )
    assert fn.eval([0.4]) == pytest.approx([0.4, 0.4])


def test_eval_extra_outputs_are_clipped_pass_through() -> None:
    """When the program leaves more values than /Range declares, the
    extras pass through unclipped — clip_output only iterates the
    declared dimensions. This documents existing behaviour."""
    fn = _make(
        "{ 0.1 0.2 0.3 }",
        domain=[0.0, 1.0],
        rng=[0.0, 1.0],  # one declared output
    )
    # input pop'd would underflow, so use empty input + empty domain
    fn = _make(
        "{ 0.1 0.2 0.3 }",
        domain=[],
        rng=[0.0, 1.0],
    )
    result = fn.eval([])
    # First value clipped to /Range; extras flow through.
    assert result == pytest.approx([0.1, 0.2, 0.3])
