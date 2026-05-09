from __future__ import annotations

from types import CodeType, FunctionType, SimpleNamespace

from tests.contentstream import test_pdf_stream_engine_wave684 as wave684


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


def test_wave1228_wave684_engine_process_stream_helper_sets_processed() -> None:
    process_stream = FunctionType(
        _find_nested_code(
            wave684.test_wave684_show_form_treats_bad_length_as_empty.__code__,
            "process_stream",
        ),
        wave684.__dict__,
    )
    engine = SimpleNamespace(processed=False)

    process_stream(engine, object())

    assert engine.processed is True
