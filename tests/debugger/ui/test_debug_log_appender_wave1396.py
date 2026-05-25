"""Wave 1396 — DebugLogAppender upstream class-surface parity.

Wave 1396 closes the parity-tool gap for upstream's
``append(LogEvent)`` / ``createAppender(...)`` / ``setupCustomLogger()``
class members. The pypdfbox port had Python-idiomatic equivalents
(``emit``, the constructor, and a module-level helper), so the additions
are thin parity shims:

- :meth:`DebugLogAppender.append` forwards to :meth:`emit`;
- :meth:`DebugLogAppender.create_appender` is a configured-instance
  classmethod factory;
- :meth:`DebugLogAppender.setup_custom_logger` is a staticmethod that
  delegates to the module-level helper.
"""

from __future__ import annotations

import inspect
import logging

from pypdfbox.debugger.ui.debug_log_appender import (
    DebugLogAppender,
    setup_custom_logger,
)


def _make_record(msg: str = "hello", level: int = logging.INFO) -> logging.LogRecord:
    return logging.LogRecord(
        name="test.wave1396",
        level=level,
        pathname=__file__,
        lineno=1,
        msg=msg,
        args=(),
        exc_info=None,
    )


# ---------------------------------------------------------------------------
# append → emit forwarding
# ---------------------------------------------------------------------------


def test_wave1396_append_forwards_to_emit() -> None:
    """``append(LogEvent)`` upstream maps to stdlib ``emit(LogRecord)``."""
    appender = DebugLogAppender()
    record = _make_record("via-append")
    appender.append(record)
    captured = appender.get_records()
    assert len(captured) == 1
    assert "via-append" in captured[0]


def test_wave1396_append_and_emit_share_buffer() -> None:
    """Mixing append/emit calls produces a single in-order buffer."""
    appender = DebugLogAppender()
    appender.append(_make_record("one"))
    appender.emit(_make_record("two"))
    appender.append(_make_record("three"))
    records = appender.get_records()
    assert len(records) == 3
    assert "one" in records[0]
    assert "two" in records[1]
    assert "three" in records[2]


# ---------------------------------------------------------------------------
# create_appender factory
# ---------------------------------------------------------------------------


def test_wave1396_create_appender_returns_configured_instance() -> None:
    """``create_appender`` is a classmethod that returns a configured
    :class:`DebugLogAppender`."""
    appender = DebugLogAppender.create_appender(
        name="custom", ignore_exceptions=False
    )
    assert isinstance(appender, DebugLogAppender)
    assert appender.name == "custom"
    assert appender._ignore_exceptions is False


def test_wave1396_create_appender_accepts_optional_layout() -> None:
    """When a ``layout`` (a :class:`logging.Formatter`) is supplied it
    replaces the upstream PatternLayout default."""
    custom_fmt = logging.Formatter("PFX:%(message)s")
    appender = DebugLogAppender.create_appender(layout=custom_fmt)
    appender.emit(_make_record("hi"))
    records = appender.get_records()
    assert records == ["PFX:hi"]


def test_wave1396_create_appender_filter_is_applied() -> None:
    """A filter passed via the ``filter`` slot is wired through to the
    handler so records can be dropped before they reach the buffer."""

    class _DropAll(logging.Filter):
        def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003
            return False

    appender = DebugLogAppender.create_appender(filter=_DropAll())
    # The handle pathway honours filters; emit() bypasses them, so we go
    # through the full ``handle`` entry point.
    appender.handle(_make_record("dropped"))
    assert appender.get_records() == []


# ---------------------------------------------------------------------------
# setup_custom_logger staticmethod parity
# ---------------------------------------------------------------------------


def test_wave1396_setup_custom_logger_class_method_present() -> None:
    """Upstream exposes ``setupCustomLogger`` on the class; the port
    mirrors that with a staticmethod."""
    members = {
        name
        for name, _ in inspect.getmembers(DebugLogAppender, predicate=inspect.isfunction)
    }
    assert "setup_custom_logger" in members


def test_wave1396_setup_custom_logger_class_method_attaches_to_root() -> None:
    """Calling the class-level helper attaches a handler to the root
    logger, equivalent to the module-level helper."""
    appender = DebugLogAppender.setup_custom_logger(name="wave1396-class")
    try:
        assert appender.attached_logger is logging.getLogger()
        assert appender in logging.getLogger().handlers
    finally:
        appender.detach()


def test_wave1396_setup_custom_logger_module_function_still_works() -> None:
    """Module-level :func:`setup_custom_logger` still works (back-compat)."""
    appender = setup_custom_logger(name="wave1396-module")
    try:
        assert appender.attached_logger is logging.getLogger()
    finally:
        appender.detach()
