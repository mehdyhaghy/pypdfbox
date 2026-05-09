from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSStream
from pypdfbox.pdmodel.common.function import PDFunctionType4
from pypdfbox.pdmodel.common.function import pd_function_type4 as ps_module


def _make(
    body: bytes | str,
    *,
    domain: list[float] | None = None,
    rng: list[float] | None = None,
) -> PDFunctionType4:
    raw = COSStream()
    raw.set_int("FunctionType", 4)
    if domain is not None:
        domain_arr = COSArray()
        domain_arr.set_float_array(domain)
        raw.set_item("Domain", domain_arr)
    if rng is not None:
        range_arr = COSArray()
        range_arr.set_float_array(rng)
        raw.set_item("Range", range_arr)
    raw.set_data(body.encode("utf-8") if isinstance(body, str) else body)
    return PDFunctionType4(raw)


def test_streamless_type4_has_empty_instruction_sequence() -> None:
    fn = PDFunctionType4()

    assert fn.get_instructions() == []
    assert fn.eval([1.0, 2.0]) == pytest.approx([1.0, 2.0])


def test_latin1_body_fallback_still_reports_unsupported_token() -> None:
    fn = _make(b"{ \xff }", domain=[])

    with pytest.raises(OSError, match="unsupported PostScript operator"):
        fn.eval([])


def test_procedure_literal_left_on_stack_is_not_valid_output() -> None:
    fn = _make("{ true { 1 } }", domain=[])

    with pytest.raises(OSError, match="expected numeric output"):
        fn.eval([])


def test_if_requires_procedure_on_stack() -> None:
    fn = _make("{ true 1 if }", domain=[])

    with pytest.raises(OSError, match="if expects a procedure"):
        fn.eval([])


def test_ifelse_requires_two_procedures() -> None:
    fn = _make("{ true { 1 } 2 ifelse }", domain=[])

    with pytest.raises(OSError, match="ifelse expects two procedures"):
        fn.eval([])


def test_ifelse_requires_boolean_condition() -> None:
    fn = _make("{ 1 { 2 } { 3 } ifelse }", domain=[])

    with pytest.raises(OSError, match="ifelse expects a boolean condition"):
        fn.eval([])


def test_bitwise_operators_reject_mixed_bool_and_number_operands() -> None:
    for op in ("and", "or", "xor"):
        fn = _make(f"{{ true 1 {op} }}", domain=[])

        with pytest.raises(OSError, match=rf"{op} operands must both"):
            fn.eval([])


def test_not_rejects_procedure_operand() -> None:
    fn = _make("{ { 1 } not }", domain=[])

    with pytest.raises(OSError, match="not operand must be bool or int"):
        fn.eval([])


def test_direct_executor_rejects_non_string_operator_token() -> None:
    stack: list[object] = []

    with pytest.raises(OSError, match="unsupported PostScript token"):
        ps_module._execute([object()], stack)


def test_direct_output_float_rejects_non_numeric_value() -> None:
    with pytest.raises(OSError, match="expected numeric output"):
        ps_module._to_output_float("not-a-number")
