"""Wave 1367 — :mod:`pypdfbox.io.io_utils` facade fixes + corner cases.

After wave 1367's fix to :class:`IOUtils.close_and_log_exception` and
:class:`IOUtils.create_protected_temp_file` (both had signature drift
from the module-level functions), the facades now mirror the upstream
:class:`org.apache.pdfbox.io.IOUtils` static-method shapes. These tests
exercise the new accepting-arguments paths plus a few edges of the
underlying copy / populate_buffer / unmap helpers.
"""

from __future__ import annotations

import io
import logging

import pytest

from pypdfbox.io.io_utils import (
    IOUtils,
    copy,
    populate_buffer,
    unmap,
)


def test_copy_rejects_zero_buffer_size() -> None:
    with pytest.raises(ValueError):
        copy(io.BytesIO(b"abc"), io.BytesIO(), buffer_size=0)


def test_copy_rejects_negative_buffer_size() -> None:
    with pytest.raises(ValueError):
        copy(io.BytesIO(b"abc"), io.BytesIO(), buffer_size=-1)


def test_copy_empty_source_returns_zero() -> None:
    out = io.BytesIO()
    assert copy(io.BytesIO(b""), out) == 0
    assert out.getvalue() == b""


def test_copy_loops_over_chunks() -> None:
    payload = b"x" * 25_000
    out = io.BytesIO()
    n = copy(io.BytesIO(payload), out, buffer_size=4096)
    assert n == len(payload)
    assert out.getvalue() == payload


def test_populate_buffer_full() -> None:
    buf = bytearray(10)
    n = populate_buffer(io.BytesIO(b"abcdefghij"), buf)
    assert n == 10
    assert bytes(buf) == b"abcdefghij"


def test_populate_buffer_short_read_loops_until_eof() -> None:
    """``populate_buffer`` must loop over partial reads, not give up
    on the first short return."""

    class Drip(io.RawIOBase):
        def __init__(self, payload: bytes) -> None:
            super().__init__()
            self._buf = payload
            self._pos = 0

        def readable(self) -> bool:
            return True

        def read(self, size: int = -1) -> bytes:  # type: ignore[override]
            if self._pos >= len(self._buf):
                return b""
            # Always return at most 3 bytes regardless of asked size.
            n = min(3, len(self._buf) - self._pos, size if size > 0 else 3)
            chunk = self._buf[self._pos : self._pos + n]
            self._pos += n
            return chunk

    buf = bytearray(8)
    n = populate_buffer(Drip(b"abcdefgh"), buf)
    assert n == 8
    assert bytes(buf) == b"abcdefgh"


def test_populate_buffer_short_eof_returns_partial() -> None:
    buf = bytearray(10)
    n = populate_buffer(io.BytesIO(b"abc"), buf)
    assert n == 3
    assert bytes(buf[:3]) == b"abc"


def test_unmap_none_is_noop() -> None:
    unmap(None)  # must not raise


def test_unmap_object_without_close_is_noop() -> None:
    unmap(object())


def test_unmap_object_with_close_calls_it() -> None:
    called: list[bool] = []

    class C:
        def close(self) -> None:
            called.append(True)

    unmap(C())
    assert called == [True]


def test_unmap_swallows_close_errors() -> None:
    class C:
        def close(self) -> None:
            raise OSError("boom")

    # Must not propagate.
    unmap(C())


# ---- IOUtils.close_and_log_exception facade (wave 1367 fix) -------------


class _RaisingClose:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True
        raise OSError("simulated")


def test_facade_close_and_log_exception_str_logger_name(
    caplog: pytest.LogCaptureFixture,
) -> None:
    target = _RaisingClose()
    with caplog.at_level(logging.WARNING, logger="pypdfbox.test_w1367"):
        rv = IOUtils.close_and_log_exception(target, "pypdfbox.test_w1367", "tmp")
    assert target.closed is True
    assert isinstance(rv, OSError)
    assert any("tmp" in r.getMessage() for r in caplog.records)


def test_facade_close_and_log_exception_logger_instance(
    caplog: pytest.LogCaptureFixture,
) -> None:
    target = _RaisingClose()
    logger = logging.getLogger("pypdfbox.test_w1367.instance")
    with caplog.at_level(logging.WARNING, logger=logger.name):
        rv = IOUtils.close_and_log_exception(target, logger, "tmp")
    assert isinstance(rv, OSError)


def test_facade_close_and_log_exception_initial_exception_preserved() -> None:
    target = _RaisingClose()
    initial = ValueError("upstream failure")
    rv = IOUtils.close_and_log_exception(target, None, "tmp", initial)
    # Returned value is the initial exception, not the new one.
    assert rv is initial


def test_facade_close_and_log_exception_none_target() -> None:
    # No-op when closeable is None.
    rv = IOUtils.close_and_log_exception(None, None, "tmp")
    assert rv is None


def test_facade_close_and_log_exception_default_logger_name(
    caplog: pytest.LogCaptureFixture,
) -> None:
    target = _RaisingClose()
    with caplog.at_level(logging.WARNING, logger="pypdfbox.io.io_utils"):
        IOUtils.close_and_log_exception(target)
    assert target.closed is True


# ---- IOUtils.create_protected_temp_file facade (wave 1367 fix) -----------


def test_facade_create_protected_temp_file_default_args() -> None:
    path = IOUtils.create_protected_temp_file()
    try:
        assert path.exists()
        assert path.is_file()
        assert path.name.startswith("pypdfbox-")
    finally:
        path.unlink()


def test_facade_create_protected_temp_file_explicit_prefix_suffix() -> None:
    path = IOUtils.create_protected_temp_file(prefix="custom-", suffix=".bin")
    try:
        assert path.name.startswith("custom-")
        assert path.suffix == ".bin"
    finally:
        path.unlink()


def test_facade_create_protected_temp_file_directory_arg(tmp_path) -> None:  # type: ignore[no-untyped-def]
    path = IOUtils.create_protected_temp_file(directory=tmp_path)
    try:
        assert path.parent == tmp_path
    finally:
        path.unlink()


# ---- IOUtils.unmapper / new_buffer_cleaner ------------------------------


def test_unmapper_returns_callable_that_invokes_unmap() -> None:
    cleaner = IOUtils.unmapper()
    # Should be callable.
    assert callable(cleaner)
    # And calling it with None is a no-op (mirrors unmap()).
    cleaner(None)  # type: ignore[misc]


def test_new_buffer_cleaner_returns_unmap_func() -> None:
    assert IOUtils.new_buffer_cleaner() is IOUtils.unmap
