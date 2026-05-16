"""Class-surface visibility tests for ``OSXAdapter`` upstream-shape statics.

Wave 1310 ported the reflection-dispatch helpers (``is_min_jdk9``,
``is_correct_method``, ``invoke``, ``call_target``,
``set_application_event_handled``) as module-level functions. Upstream Java
exposes them as ``public static`` members of ``OSXAdapter``. Wave 1312
re-exposes them as ``@staticmethod``s on the class so the parity tool
counts them and so callers can use the ``OSXAdapter.<name>`` spelling.
"""

from __future__ import annotations

from pypdfbox.debugger.ui import osx_adapter
from pypdfbox.debugger.ui.osx_adapter import OSXAdapter


def test_is_min_jdk9_on_class_surface() -> None:
    assert getattr(OSXAdapter, "is_min_jdk9", None) is not None
    # Delegation: class-surface call returns the same value as the
    # module-level function (both are deterministic on the same host).
    assert OSXAdapter.is_min_jdk9() == osx_adapter.is_min_jdk9()


def test_is_correct_method_on_class_surface() -> None:
    assert getattr(OSXAdapter, "is_correct_method", None) is not None

    def sample(a, b):  # noqa: ANN001, ANN202 - parameter types not the focus here
        return a + b

    # Name match, no type constraints, parameter count check.
    assert OSXAdapter.is_correct_method(sample, "sample") is True
    # Name mismatch.
    assert OSXAdapter.is_correct_method(sample, "other") is False
    # None argument short-circuits.
    assert OSXAdapter.is_correct_method(None, "sample") is False


def test_invoke_on_class_surface() -> None:
    assert getattr(OSXAdapter, "invoke", None) is not None

    class Target:
        def __init__(self) -> None:
            self.received: list[int] = []

        def handle(self, value: int) -> int:
            self.received.append(value)
            return value * 2

    target = Target()
    assert OSXAdapter.invoke(target, "handle", 21) == 42
    assert target.received == [21]
    # Missing attribute returns ``None`` (no AttributeError).
    assert OSXAdapter.invoke(target, "does_not_exist") is None


def test_call_target_on_class_surface() -> None:
    assert getattr(OSXAdapter, "call_target", None) is not None

    class Target:
        def __init__(self) -> None:
            self.events: list[object] = []

        def handle_event(self, event: object) -> str:
            self.events.append(event)
            return "ok"

        def handle_quit(self) -> str:
            return "quit"

    target = Target()
    # With event -> forwarded to one-arg handler.
    assert OSXAdapter.call_target(target, "handle_event", event="apple") == "ok"
    assert target.events == ["apple"]
    # Without event -> zero-arg call.
    assert OSXAdapter.call_target(target, "handle_quit") == "quit"


def test_set_application_event_handled_on_class_surface() -> None:
    assert getattr(OSXAdapter, "set_application_event_handled", None) is not None
    # No-op on Tk: must return ``None`` regardless of inputs and must not
    # raise for arbitrary positional values.
    assert OSXAdapter.set_application_event_handled(object(), True) is None
    assert OSXAdapter.set_application_event_handled(None, False) is None


def test_class_statics_delegate_to_module_level_functions() -> None:
    """Each class staticmethod calls the matching module-level helper."""
    captured: dict[str, tuple[object, ...]] = {}

    def _stub(name: str):
        def _inner(*args: object, **kwargs: object) -> str:
            captured[name] = args
            return f"stub:{name}"

        return _inner

    original = {
        "invoke": osx_adapter.invoke,
        "call_target": osx_adapter.call_target,
    }
    osx_adapter.invoke = _stub("invoke")  # type: ignore[assignment]
    osx_adapter.call_target = _stub("call_target")  # type: ignore[assignment]
    try:
        # The class staticmethod must call into the module-level binding,
        # i.e. our stub must be invoked.
        assert OSXAdapter.invoke("target", "method", 1, 2) == "stub:invoke"
        assert captured["invoke"] == ("target", "method", 1, 2)
        assert (
            OSXAdapter.call_target("target", "method", event="e") == "stub:call_target"
        )
        assert captured["call_target"] == ("target", "method", "e")
    finally:
        osx_adapter.invoke = original["invoke"]  # type: ignore[assignment]
        osx_adapter.call_target = original["call_target"]  # type: ignore[assignment]
