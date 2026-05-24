"""Wave 1389 — port of ``DebugLogAppender`` to a stdlib-logging handler.

Mirrors the behavioural contract of
``org.apache.pdfbox.debugger.ui.DebugLogAppender`` (log4j ``AbstractAppender``
in upstream; :class:`logging.Handler` here per the project-wide
no-log4j deviation documented in ``CHANGES.md``).
"""

from __future__ import annotations

import logging

import pytest

from pypdfbox.debugger.ui.debug_log_appender import (
    DEFAULT_MAX_RECORDS,
    UPSTREAM_PATTERN,
    DebugLogAppender,
    setup_custom_logger,
)

# --- isolation fixture -------------------------------------------------------


@pytest.fixture
def isolated_logger() -> logging.Logger:
    """Return a uniquely-named logger so handlers from different tests do not
    cross-pollute.  Using the root logger here would leak handlers into other
    tests' captures.
    """
    name = f"pypdfbox.debugger.test.{id(object())}"
    logger = logging.getLogger(name)
    logger.handlers.clear()
    logger.setLevel(logging.NOTSET)
    yield logger
    logger.handlers.clear()
    logger.setLevel(logging.NOTSET)


# --- construction ------------------------------------------------------------


def test_default_construction_uses_info_level_and_default_cap() -> None:
    appender = DebugLogAppender()
    try:
        assert appender.level == logging.INFO
        assert appender.max_records == DEFAULT_MAX_RECORDS
        assert appender.name == "DebugLogAppender"
        assert appender.get_records() == []
    finally:
        appender.close()


def test_custom_max_records_is_honoured() -> None:
    appender = DebugLogAppender(max_records=4)
    try:
        assert appender.max_records == 4
    finally:
        appender.close()


def test_non_positive_max_records_rejected() -> None:
    with pytest.raises(ValueError):
        DebugLogAppender(max_records=0)
    with pytest.raises(ValueError):
        DebugLogAppender(max_records=-1)


# --- emit / level filter -----------------------------------------------------


def test_info_records_are_captured(isolated_logger: logging.Logger) -> None:
    appender = DebugLogAppender()
    appender.attach(isolated_logger)
    try:
        isolated_logger.info("hello world")
        records = appender.get_records()
        assert len(records) == 1
        assert "hello world" in records[0]
        assert "INFO" in records[0]
    finally:
        appender.detach()
        appender.close()


def test_warning_and_error_records_captured(isolated_logger: logging.Logger) -> None:
    appender = DebugLogAppender()
    appender.attach(isolated_logger)
    try:
        isolated_logger.warning("warn-msg")
        isolated_logger.error("err-msg")
        records = appender.get_records()
        assert len(records) == 2
        assert "warn-msg" in records[0]
        assert "WARNING" in records[0]
        assert "err-msg" in records[1]
        assert "ERROR" in records[1]
    finally:
        appender.detach()
        appender.close()


def test_debug_records_dropped_at_default_threshold(
    isolated_logger: logging.Logger,
) -> None:
    appender = DebugLogAppender()  # INFO threshold
    appender.attach(isolated_logger)
    try:
        # Logger must allow DEBUG to flow so the handler-level filter is
        # exercised. ``attach`` only lowers to INFO; force it lower so the
        # record reaches the handler.
        isolated_logger.setLevel(logging.DEBUG)
        isolated_logger.debug("hidden")
        isolated_logger.info("visible")
        records = appender.get_records()
        assert len(records) == 1
        assert "visible" in records[0]
        assert "hidden" not in records[0]
    finally:
        appender.detach()
        appender.close()


def test_explicit_debug_threshold_captures_debug(
    isolated_logger: logging.Logger,
) -> None:
    appender = DebugLogAppender(level=logging.DEBUG)
    appender.attach(isolated_logger, level=logging.DEBUG)
    try:
        isolated_logger.debug("now-visible")
        records = appender.get_records()
        assert len(records) == 1
        assert "now-visible" in records[0]
        assert "DEBUG" in records[0]
    finally:
        appender.detach()
        appender.close()


# --- ring-buffer cap ---------------------------------------------------------


def test_max_records_cap_evicts_oldest(isolated_logger: logging.Logger) -> None:
    appender = DebugLogAppender(max_records=3)
    appender.attach(isolated_logger)
    try:
        for i in range(5):
            isolated_logger.info("msg-%d", i)
        records = appender.get_records()
        assert len(records) == 3
        # Oldest two (msg-0, msg-1) evicted; newest three retained in order.
        assert "msg-2" in records[0]
        assert "msg-3" in records[1]
        assert "msg-4" in records[2]
    finally:
        appender.detach()
        appender.close()


# --- formatter ---------------------------------------------------------------


def test_formatter_matches_upstream_pattern_shape(
    isolated_logger: logging.Logger,
) -> None:
    appender = DebugLogAppender()
    appender.attach(isolated_logger)
    try:
        isolated_logger.info("payload")
        line = appender.get_records()[0]
        # Upstream pattern is "%d [%t] %-5level: %msg%n%throwable".
        # We can't pin the timestamp but we can pin the rest.
        assert "[" in line and "]" in line  # thread tag
        assert "INFO" in line
        assert ": payload" in line
    finally:
        appender.detach()
        appender.close()


def test_formatter_renders_exception_text(isolated_logger: logging.Logger) -> None:
    appender = DebugLogAppender()
    appender.attach(isolated_logger)
    try:
        try:
            raise ValueError("boom")
        except ValueError:
            isolated_logger.exception("trapped")
        line = appender.get_records()[0]
        assert "trapped" in line
        # Stdlib appends the traceback after the formatted message; verify
        # the exception class name reached the buffer.
        assert "ValueError" in line
        assert "boom" in line
    finally:
        appender.detach()
        appender.close()


def test_upstream_pattern_constant_round_trip() -> None:
    # The constant is part of the public surface (callers may want to build
    # their own formatter from it).  Pin its shape so accidental edits
    # surface in CI.
    assert "%(asctime)s" in UPSTREAM_PATTERN
    assert "%(threadName)s" in UPSTREAM_PATTERN
    assert "%(levelname)-5s" in UPSTREAM_PATTERN
    assert "%(message)s" in UPSTREAM_PATTERN


# --- clear -------------------------------------------------------------------


def test_clear_empties_buffer(isolated_logger: logging.Logger) -> None:
    appender = DebugLogAppender()
    appender.attach(isolated_logger)
    try:
        isolated_logger.info("a")
        isolated_logger.info("b")
        assert len(appender.get_records()) == 2
        appender.clear()
        assert appender.get_records() == []
        # Buffer remains usable after clear.
        isolated_logger.info("c")
        records = appender.get_records()
        assert len(records) == 1
        assert "c" in records[0]
    finally:
        appender.detach()
        appender.close()


# --- attach / detach lifecycle ----------------------------------------------


def test_attach_returns_target_logger(isolated_logger: logging.Logger) -> None:
    appender = DebugLogAppender()
    target = appender.attach(isolated_logger)
    try:
        assert target is isolated_logger
        assert appender in isolated_logger.handlers
        assert appender.attached_logger is isolated_logger
    finally:
        appender.detach()
        appender.close()


def test_detach_removes_handler(isolated_logger: logging.Logger) -> None:
    appender = DebugLogAppender()
    appender.attach(isolated_logger)
    appender.detach()
    assert appender not in isolated_logger.handlers
    assert appender.attached_logger is None
    # Detach on an already-detached handler is a no-op.
    appender.detach()
    appender.close()


def test_reattach_first_detaches_previous(
    isolated_logger: logging.Logger,
) -> None:
    other = logging.getLogger(f"pypdfbox.debugger.test.other.{id(object())}")
    other.handlers.clear()
    try:
        appender = DebugLogAppender()
        appender.attach(isolated_logger)
        assert appender in isolated_logger.handlers
        appender.attach(other)
        # Re-attaching to ``other`` should pull the handler off
        # ``isolated_logger`` so the same record doesn't fire twice.
        assert appender not in isolated_logger.handlers
        assert appender in other.handlers
        appender.detach()
        appender.close()
    finally:
        other.handlers.clear()


def test_attach_accepts_logger_name_string() -> None:
    name = f"pypdfbox.debugger.test.bystring.{id(object())}"
    appender = DebugLogAppender()
    try:
        target = appender.attach(name)
        assert target is logging.getLogger(name)
        assert appender in target.handlers
    finally:
        appender.detach()
        appender.close()


def test_attach_defaults_to_root_logger() -> None:
    appender = DebugLogAppender()
    root = logging.getLogger()
    pre_handlers = list(root.handlers)
    try:
        target = appender.attach()
        assert target is root
        assert appender in root.handlers
    finally:
        appender.detach()
        appender.close()
        # Ensure we didn't leak our handler into the root.
        assert appender not in root.handlers
        assert list(root.handlers) == pre_handlers


def test_attach_lowers_logger_level_but_never_raises_it(
    isolated_logger: logging.Logger,
) -> None:
    isolated_logger.setLevel(logging.DEBUG)  # already permissive
    appender = DebugLogAppender(level=logging.WARNING)
    try:
        appender.attach(isolated_logger)
        # Should not raise the logger from DEBUG to WARNING.
        assert isolated_logger.level == logging.DEBUG
    finally:
        appender.detach()
        appender.close()


def test_attach_lowers_unset_logger(isolated_logger: logging.Logger) -> None:
    # NOTSET (level 0) should be raised to the handler level so records flow.
    appender = DebugLogAppender(level=logging.INFO)
    try:
        appender.attach(isolated_logger)
        assert isolated_logger.level == logging.INFO
    finally:
        appender.detach()
        appender.close()


# --- setup_custom_logger helper ---------------------------------------------


def test_setup_custom_logger_returns_attached_handler() -> None:
    root = logging.getLogger()
    pre_handlers = list(root.handlers)
    appender = setup_custom_logger()
    try:
        assert appender.attached_logger is root
        assert appender in root.handlers
        assert appender.level == logging.INFO
    finally:
        appender.detach()
        appender.close()
        assert list(root.handlers) == pre_handlers


# --- bulk helpers ------------------------------------------------------------


def test_extend_buffer_appends_pre_formatted_records() -> None:
    appender = DebugLogAppender(max_records=3)
    try:
        appender.extend_buffer(["a", "b"])
        appender.extend_buffer(["c", "d"])  # 'a' evicted
        records = appender.get_records()
        assert records == ["b", "c", "d"]
    finally:
        appender.close()


# --- parametrised level matrix ----------------------------------------------


@pytest.mark.parametrize(
    ("threshold", "record_level", "expect_captured"),
    [
        (logging.INFO, logging.DEBUG, False),
        (logging.INFO, logging.INFO, True),
        (logging.INFO, logging.WARNING, True),
        (logging.INFO, logging.ERROR, True),
        (logging.WARNING, logging.INFO, False),
        (logging.WARNING, logging.WARNING, True),
        (logging.ERROR, logging.WARNING, False),
        (logging.ERROR, logging.ERROR, True),
    ],
    ids=[
        "info_drops_debug",
        "info_keeps_info",
        "info_keeps_warning",
        "info_keeps_error",
        "warning_drops_info",
        "warning_keeps_warning",
        "error_drops_warning",
        "error_keeps_error",
    ],
)
def test_level_filter_matrix(
    isolated_logger: logging.Logger,
    threshold: int,
    record_level: int,
    expect_captured: bool,
) -> None:
    appender = DebugLogAppender(level=threshold)
    appender.attach(isolated_logger, level=logging.DEBUG)
    isolated_logger.setLevel(logging.DEBUG)  # let everything reach the handler
    try:
        isolated_logger.log(record_level, "probe")
        records = appender.get_records()
        if expect_captured:
            assert len(records) == 1
            assert "probe" in records[0]
        else:
            assert records == []
    finally:
        appender.detach()
        appender.close()
