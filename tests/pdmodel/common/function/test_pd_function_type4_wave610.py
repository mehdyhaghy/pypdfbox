from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSStream
from pypdfbox.pdmodel.common.function import PDFunctionType4
from pypdfbox.pdmodel.common.function import pd_function_type4 as type4


def _make(
    body: str,
    *,
    domain: list[float] | None = None,
    rng: list[float] | None = None,
) -> PDFunctionType4:
    stream = COSStream()
    stream.set_int("FunctionType", 4)
    if domain is not None:
        domain_array = COSArray()
        domain_array.set_float_array(domain)
        stream.set_item("Domain", domain_array)
    if rng is not None:
        range_array = COSArray()
        range_array.set_float_array(rng)
        stream.set_item("Range", range_array)
    stream.set_data(body.encode("ascii"))
    return PDFunctionType4(stream)


def test_tokenizer_splits_adjacent_braces_and_ignores_comments() -> None:
    fn = _make("{1 2 add% comment hides the rest\n{3 mul}if}", domain=[])

    assert fn.get_instructions() == [1.0, 2.0, "add", [3.0, "mul"], "if"]


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ("}", "unexpected closing brace"),
        ("{ 1 } 2", "unexpected trailing tokens"),
        ("{ 1", "missing closing brace"),
    ],
)
def test_parse_reports_malformed_braces(body: str, message: str) -> None:
    fn = _make(body, domain=[])

    with pytest.raises(OSError, match=message):
        fn.get_instructions()


def test_eval_raises_when_range_declares_more_outputs_than_stack_has() -> None:
    fn = _make("{ 0.25 }", domain=[], rng=[0.0, 1.0, 0.0, 1.0])

    with pytest.raises(OSError, match="/Range declares 2"):
        fn.eval([])


def test_boolean_output_is_coerced_before_range_clipping() -> None:
    fn = _make("{ true false }", domain=[], rng=[0.0, 0.5, 0.0, 1.0])

    assert fn.eval([]) == pytest.approx([0.5, 0.0])


def test_numeric_operators_reject_boolean_operands() -> None:
    fn = _make("{ true abs }", domain=[])

    with pytest.raises(OSError, match="expected number, got boolean"):
        fn.eval([])


def test_bitwise_operators_reject_procedure_operands() -> None:
    fn = _make("{ { 1 } 3 and }", domain=[])

    with pytest.raises(OSError, match="and operands must both"):
        fn.eval([])


def test_private_bool_pop_rejects_non_boolean_value() -> None:
    with pytest.raises(OSError, match="expected boolean"):
        type4._pop_bool([1.0])


def test_operator_introspection_exposes_registered_groups() -> None:
    stack: list[object] = [2.0, 3.0]
    add = type4.get_operator("add")

    assert add is not None
    add(stack)
    assert stack == [5.0]
    assert type4.get_operator("def") is None
    assert type4.is_supported_operator("ifelse")
    assert not type4.is_supported_operator("def")
    assert set(type4.ALL_OPERATORS) == (
        set(type4.ARITHMETIC_OPERATORS)
        | set(type4.STACK_OPERATORS)
        | set(type4.BOOLEAN_OPERATORS)
        | set(type4.CONDITIONAL_OPERATORS)
    )
