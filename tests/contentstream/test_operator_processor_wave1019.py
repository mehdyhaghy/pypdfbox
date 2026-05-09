from __future__ import annotations

from pypdfbox.contentstream import Operator
from pypdfbox.cos import COSInteger
from tests.contentstream.test_operator_processor import _Recorder


def test_recorder_process_records_operator_and_operand_snapshot() -> None:
    processor = _Recorder()
    operator = Operator.get_operator("RC")
    operands = [COSInteger.get(1)]

    processor.process(operator, operands)
    operands.append(COSInteger.get(2))

    assert processor.calls == [(operator, [COSInteger.get(1)])]


def test_recorder_get_name_returns_class_name() -> None:
    assert _Recorder().get_name() == _Recorder.NAME
