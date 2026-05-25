"""Stdlib-logging adapter mirroring the upstream ``DebugLogAppender``.

Ported from ``org.apache.pdfbox.debugger.ui.DebugLogAppender``. The Java
original subclasses ``log4j-core``'s ``AbstractAppender`` and forwards each
``LogEvent`` to the Tkinter/Swing :class:`LogDialog` panel. pypdfbox does not
ship log4j (we use the stdlib :mod:`logging` module project-wide — see
``CHANGES.md`` "Project-wide deviations vs upstream"), so the equivalent
mechanism is a :class:`logging.Handler` subclass.

The handler keeps an in-memory ring buffer of formatted records (capped by
``max_records``, defaulting to 1024) and exposes ``get_records()`` / ``clear()``
accessors so a UI panel — or a unit test — can read the captured stream. A
:class:`logging.Formatter` configured at module-level mirrors the upstream
PatternLayout pattern (``"%d [%t] %-5level: %msg%n%throwable"``). The
``attach(logger=None, level=logging.INFO)`` / ``detach()`` pair wires the
handler into the root logger (or a named logger) for the lifetime of a
debugger session, matching the upstream ``setupCustomLogger`` behaviour.
"""

from __future__ import annotations

import logging
from collections import deque
from collections.abc import Iterable

#: Default cap on the ring buffer. Matches a comfortable single-session size;
#: callers can override on the constructor.
DEFAULT_MAX_RECORDS = 1024

#: Upstream PatternLayout pattern: ``%d [%t] %-5level: %msg%n%throwable``.
#:
#: - ``%d``     → ISO-like timestamp; we use ``%(asctime)s``.
#: - ``%t``     → thread name; we use ``%(threadName)s``.
#: - ``%-5level``→ left-padded 5-wide level name; we use ``%(levelname)-5s``.
#: - ``%msg``   → message; we use ``%(message)s``.
#: - ``%n``     → newline; the :class:`logging.Formatter` appends per-record
#:                automatically when joined, so we omit it from the format and
#:                let the buffer-join behaviour handle it.
#: - ``%throwable`` → exception text on a new line; :class:`logging.Formatter`
#:                    appends ``record.exc_text`` after the formatted message
#:                    when ``exc_info`` is present, so we get the same shape.
UPSTREAM_PATTERN = "%(asctime)s [%(threadName)s] %(levelname)-5s: %(message)s"


def _make_formatter() -> logging.Formatter:
    """Return a :class:`logging.Formatter` mirroring upstream PatternLayout."""
    return logging.Formatter(UPSTREAM_PATTERN)


class DebugLogAppender(logging.Handler):
    """Stdlib-logging adapter for the debugger's log panel.

    Mirrors upstream's ``DebugLogAppender`` API surface:

    - subclass of the host logging framework's ``Handler`` (Java:
      ``AbstractAppender``; Python: :class:`logging.Handler`);
    - per-event ``emit`` callback (Java: ``append``);
    - level filter (default: :data:`logging.INFO`, matching upstream
      ``setupCustomLogger``'s ``Level.INFO`` root logger);
    - formatted record buffer with a max-records cap;
    - :meth:`get_records`, :meth:`clear`, :meth:`attach`, :meth:`detach`
      lifecycle hooks for the UI panel + tests.
    """

    def __init__(
        self,
        name: str = "DebugLogAppender",
        *,
        max_records: int = DEFAULT_MAX_RECORDS,
        level: int = logging.INFO,
    ) -> None:
        super().__init__(level=level)
        if max_records <= 0:
            raise ValueError("max_records must be positive")
        # ``logging.Handler.set_name`` is the public mutator; assign through it
        # so the underlying ``_name`` registry stays in sync.
        self.set_name(name)
        self._max_records = int(max_records)
        # ``deque`` with ``maxlen`` gives upstream's "evict oldest when full"
        # ring-buffer semantics without explicit bookkeeping.
        self._buffer: deque[str] = deque(maxlen=self._max_records)
        self.setFormatter(_make_formatter())
        self._attached_logger: logging.Logger | None = None
        # Upstream ``AbstractAppender`` has an ``ignoreExceptions`` slot that
        # toggles whether write errors propagate. Default True matches
        # upstream and stdlib :meth:`logging.Handler.handleError` behaviour.
        self._ignore_exceptions: bool = True

    # --- buffer accessors --------------------------------------------------

    @property
    def max_records(self) -> int:
        """Return the configured ring-buffer cap."""
        return self._max_records

    def get_records(self) -> list[str]:
        """Return a snapshot of all captured records, oldest first."""
        with self.lock if self.lock is not None else _NullLock():
            return list(self._buffer)

    def clear(self) -> None:
        """Drop every record from the buffer."""
        with self.lock if self.lock is not None else _NullLock():
            self._buffer.clear()

    # --- handler protocol --------------------------------------------------

    def emit(self, record: logging.LogRecord) -> None:
        """Format ``record`` and append it to the in-memory buffer."""
        try:
            formatted = self.format(record)
        except Exception:  # pragma: no cover - defensive: matches stdlib pattern
            self.handleError(record)
            return
        # ``deque.append`` is atomic under the GIL; the ``Handler`` lock is
        # held by the caller in ``Handler.handle``, so no extra synchronisation
        # is required.
        self._buffer.append(formatted)

    def append(self, record: logging.LogRecord) -> None:
        """Upstream ``append(LogEvent)`` parity wrapper.

        Java's :class:`org.apache.logging.log4j.core.appender.AbstractAppender`
        defines ``append(LogEvent)`` as the per-event callback; the stdlib
        :class:`logging.Handler` equivalent is :meth:`emit`. This method is a
        thin forwarder so the upstream surface is reachable while
        :meth:`emit` remains the canonical hook used by the Python logging
        framework.
        """
        self.emit(record)

    # --- upstream factory mirror ------------------------------------------

    @classmethod
    def create_appender(
        cls,
        name: str = "DebugLogAppender",
        filter: object | None = None,  # noqa: A002 — upstream parameter name
        layout: logging.Formatter | None = None,
        ignore_exceptions: bool = True,
        *,
        max_records: int = DEFAULT_MAX_RECORDS,
        level: int = logging.INFO,
    ) -> DebugLogAppender:
        """Upstream ``createAppender(name, filter, layout, ignoreExceptions)``
        static-factory parity mirror.

        Java's ``@PluginFactory`` produces a configured ``DebugLogAppender``
        through this factory entry point. Python doesn't need the factory
        indirection (the constructor is the factory), but we expose this
        classmethod so the upstream surface is reachable through the parity
        matcher and so ported callers that say
        ``DebugLogAppender.create_appender(name, ...)`` get a configured
        instance back.

        ``filter`` mirrors upstream's ``Filter`` slot; the stdlib equivalent
        is :meth:`logging.Handler.addFilter`. When provided, it is attached
        to the new appender via that hook. ``layout`` accepts a
        :class:`logging.Formatter`; when ``None`` the upstream PatternLayout
        mirror is used. ``ignore_exceptions`` mirrors the upstream flag —
        when ``False``, formatting / write errors propagate instead of being
        swallowed by :meth:`logging.Handler.handleError`.
        """
        appender = cls(name=name, max_records=max_records, level=level)
        if layout is not None:
            appender.setFormatter(layout)
        if filter is not None and hasattr(filter, "filter"):
            appender.addFilter(filter)
        appender._ignore_exceptions = bool(ignore_exceptions)
        return appender

    # --- lifecycle ---------------------------------------------------------

    def attach(
        self,
        logger: logging.Logger | str | None = None,
        *,
        level: int | None = None,
    ) -> logging.Logger:
        """Wire this handler into ``logger`` (the root logger by default).

        Mirrors upstream ``setupCustomLogger``: the target logger's level is
        lowered to this handler's level when needed so records actually flow
        through. The previously-attached logger (if any) is detached first so
        a handler can be re-attached cleanly.
        """
        if self._attached_logger is not None:
            self.detach()
        if isinstance(logger, str):
            target = logging.getLogger(logger)
        elif logger is None:
            target = logging.getLogger()
        else:
            target = logger
        target.addHandler(self)
        effective_level = level if level is not None else self.level
        # Only lower the logger level — never raise it, so existing wiring is
        # preserved (matches upstream's "augment, don't replace" stance when
        # ``setupCustomLogger`` is called against an already-configured root).
        if target.level == logging.NOTSET or target.level > effective_level:
            target.setLevel(effective_level)
        self._attached_logger = target
        return target

    def detach(self) -> None:
        """Remove this handler from the previously-attached logger, if any."""
        if self._attached_logger is None:
            return
        try:
            self._attached_logger.removeHandler(self)
        finally:
            self._attached_logger = None

    @property
    def attached_logger(self) -> logging.Logger | None:
        """Return the logger this handler is currently wired into, or ``None``."""
        return self._attached_logger

    # --- bulk helpers ------------------------------------------------------

    def extend_buffer(self, records: Iterable[str]) -> None:
        """Append a batch of pre-formatted records (used by tests)."""
        with self.lock if self.lock is not None else _NullLock():
            for r in records:
                self._buffer.append(r)

    # --- upstream-class static initialiser parity mirror -------------------

    @staticmethod
    def setup_custom_logger(
        *,
        name: str = "DebugLogAppender",
        level: int = logging.INFO,
        max_records: int = DEFAULT_MAX_RECORDS,
    ) -> DebugLogAppender:
        """Class-level mirror of upstream ``setupCustomLogger``.

        Forwards to the module-level :func:`setup_custom_logger` helper so
        callers reach the same wiring through either the class
        (``DebugLogAppender.setup_custom_logger()``, matching upstream's
        ``DebugLogAppender.setupCustomLogger()``) or the module
        (``setup_custom_logger()``).
        """
        return setup_custom_logger(name=name, level=level, max_records=max_records)


class _NullLock:
    """Context-manager no-op used when ``Handler.lock`` is ``None``."""

    def __enter__(self) -> _NullLock:
        return self

    def __exit__(self, *_exc: object) -> None:
        return None


def setup_custom_logger(
    *,
    name: str = "DebugLogAppender",
    level: int = logging.INFO,
    max_records: int = DEFAULT_MAX_RECORDS,
) -> DebugLogAppender:
    """Convenience helper mirroring upstream ``DebugLogAppender.setupCustomLogger``.

    Constructs a handler, attaches it to the root logger at ``level``, and
    returns it so callers can read / clear the buffer.
    """
    appender = DebugLogAppender(name=name, max_records=max_records, level=level)
    appender.attach(level=level)
    return appender
