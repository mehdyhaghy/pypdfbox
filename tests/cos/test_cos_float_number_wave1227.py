from __future__ import annotations

from types import CodeType, FunctionType

from tests.cos import test_cos_float_number_wave699 as wave699


def _find_nested_code(code: CodeType, name: str) -> CodeType:
    pending = [code]
    while pending:
        current = pending.pop()
        for const in current.co_consts:
            if isinstance(const, CodeType):
                if const.co_name == name:
                    return const
                pending.append(const)
    raise AssertionError(f"{name} not found")


def test_wave1227_wave699_number_accept_helper_returns_visitor() -> None:
    accept = FunctionType(
        _find_nested_code(
            wave699.test_wave699_cos_number_abstract_methods_raise.__code__,
            "accept",
        ),
        wave699.__dict__,
    )
    visitor = object()

    assert accept(object(), visitor) is visitor
