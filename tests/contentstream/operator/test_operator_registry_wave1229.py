from __future__ import annotations

import pytest

from pypdfbox.contentstream.operator import Operator
from pypdfbox.contentstream.operator.operator_registry import (
    OperatorHandler,
)
from tests.contentstream.operator import test_operator_registry as target


def test_register_new_operator_custom_handler_process_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, type[OperatorHandler]] = {}
    original_register = target.OperatorRegistry.register

    def capture_register(
        self: target.OperatorRegistry,
        name: str,
        processor_class: type[OperatorHandler],
    ) -> None:
        if name == "XYZ":
            captured["handler"] = processor_class
        original_register(self, name, processor_class)

    monkeypatch.setattr(target.OperatorRegistry, "register", capture_register)

    target.test_register_new_operator()

    handler = captured["handler"]()
    handler.process(Operator.get_operator("XYZ"), [])
