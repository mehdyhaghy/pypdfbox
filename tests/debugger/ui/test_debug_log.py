"""Hand-written tests for ``pypdfbox.debugger.ui.DebugLog``."""

import logging
from typing import Any

import pytest

from pypdfbox.debugger.ui import DebugLog
from pypdfbox.debugger.ui import debug_log as module


@pytest.fixture(autouse=True)
def _reset_dialog_sink() -> Any:
    module.set_dialog_sink(None)
    yield
    module.set_dialog_sink(None)


def test_error_always_enabled() -> None:
    log = DebugLog("any")
    assert log.is_error_enabled() is True
    assert log.is_fatal_enabled() is True
    assert log.is_warn_enabled() is True


def test_default_levels_match_upstream() -> None:
    log = DebugLog("any")
    assert log.is_info_enabled() is True
    assert log.is_debug_enabled() is False
    assert log.is_trace_enabled() is False


def test_error_forwards_to_python_logging(caplog: pytest.LogCaptureFixture) -> None:
    log = DebugLog("pypdfbox.test")
    with caplog.at_level(logging.ERROR, logger="pypdfbox.test"):
        log.error("boom")
    assert any("boom" in r.getMessage() for r in caplog.records)


def test_warn_forwards_to_python_logging(caplog: pytest.LogCaptureFixture) -> None:
    log = DebugLog("pypdfbox.test2")
    with caplog.at_level(logging.WARNING, logger="pypdfbox.test2"):
        log.warn("careful")
    assert any("careful" in r.getMessage() for r in caplog.records)


def test_dialog_sink_receives_events() -> None:
    received: list[tuple[str, str, Any, BaseException | None]] = []

    def sink(name: str, level: str, msg: Any, exc: BaseException | None) -> None:
        received.append((name, level, msg, exc))

    module.set_dialog_sink(sink)
    log = DebugLog("pypdfbox.test3")
    log.error("E1")
    log.warn("W1")
    log.info("I1")
    assert ("pypdfbox.test3", "error", "E1", None) in received
    assert ("pypdfbox.test3", "warn", "W1", None) in received
    assert ("pypdfbox.test3", "info", "I1", None) in received


def test_debug_and_trace_suppressed_by_default() -> None:
    received: list[tuple[str, str, Any, BaseException | None]] = []
    module.set_dialog_sink(
        lambda n, lvl, m, e: received.append((n, lvl, m, e))
    )
    log = DebugLog("pypdfbox.test4")
    log.debug("hidden")
    log.trace("hidden")
    assert received == []


def test_throwable_routed_via_exc_info(caplog: pytest.LogCaptureFixture) -> None:
    log = DebugLog("pypdfbox.test5")
    err = RuntimeError("oops")
    with caplog.at_level(logging.ERROR, logger="pypdfbox.test5"):
        log.error("with exc", err)
    record = next(r for r in caplog.records if "with exc" in r.getMessage())
    assert record.exc_info is not None
    assert record.exc_info[1] is err


def test_fatal_forwards_to_python_logging(caplog: pytest.LogCaptureFixture) -> None:
    log = DebugLog("pypdfbox.testfatal")
    with caplog.at_level(logging.CRITICAL, logger="pypdfbox.testfatal"):
        log.fatal("the end")
    assert any("the end" in r.getMessage() for r in caplog.records)


def test_debug_enabled_when_module_flag_set(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(module, "_DEBUG", True)
    log = DebugLog("pypdfbox.testdebug")
    with caplog.at_level(logging.DEBUG, logger="pypdfbox.testdebug"):
        log.debug("dbg-msg")
    assert any("dbg-msg" in r.getMessage() for r in caplog.records)


def test_trace_enabled_when_module_flag_set(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(module, "_TRACE", True)
    log = DebugLog("pypdfbox.testtrace")
    with caplog.at_level(logging.DEBUG, logger="pypdfbox.testtrace"):
        log.trace("trc-msg")
    assert any("trc-msg" in r.getMessage() for r in caplog.records)
