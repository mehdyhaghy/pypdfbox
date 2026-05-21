"""Coverage backfill for :mod:`pypdfbox.io.io_utils`.

Targets the static-facade wrappers on :class:`IOUtils`, the protected
temp-dir/file helpers, the owner-only permissions helper, the unmap stub,
the close_and_log_exception path, and the stream-cache factory helpers.
"""

from __future__ import annotations

import io
import logging
import os
from pathlib import Path

import pytest

from pypdfbox.io.io_utils import (
    DEFAULT_COPY_BUFFER,
    IOUtils,
    _apply_owner_only_permissions,
    _delete_registered_paths,
    _register_for_deletion,
    close_and_log_exception,
    close_quietly,
    copy,
    create_memory_only_stream_cache,
    create_protected_temp_dir,
    create_protected_temp_file,
    create_temp_file_only_stream_cache,
    populate_buffer,
    unmap,
)

# --- IOUtils static facade wraps module-level helpers ----------------------


def test_ioutils_copy_facade_delegates() -> None:
    data = b"hello world"
    out = io.BytesIO()
    n = IOUtils.copy(io.BytesIO(data), out)
    assert n == len(data)
    assert out.getvalue() == data


def test_ioutils_to_byte_array_facade_delegates() -> None:
    data = b"some content"
    assert IOUtils.to_byte_array(io.BytesIO(data)) == data


def test_ioutils_close_quietly_facade_delegates() -> None:
    # Should not raise.
    IOUtils.close_quietly(None)
    IOUtils.close_quietly(io.BytesIO(b""))


def test_ioutils_populate_buffer_facade_delegates() -> None:
    buf = bytearray(5)
    n = IOUtils.populate_buffer(io.BytesIO(b"abcdefg"), buf)
    assert n == 5
    assert bytes(buf) == b"abcde"


def test_ioutils_create_memory_only_stream_cache_facade() -> None:
    factory = IOUtils.create_memory_only_stream_cache()
    cache = factory()
    assert cache is not None


def test_ioutils_create_temp_file_only_stream_cache_facade() -> None:
    factory = IOUtils.create_temp_file_only_stream_cache()
    cache = factory()
    assert cache is not None


def test_ioutils_unmap_facade_handles_none() -> None:
    # Should be silent.
    IOUtils.unmap(None)


def test_ioutils_new_buffer_cleaner_returns_unmap_callable() -> None:
    cleaner = IOUtils.new_buffer_cleaner()
    assert callable(cleaner)


def test_ioutils_unmapper_alias_matches_new_buffer_cleaner() -> None:
    a = IOUtils.unmapper()
    b = IOUtils.new_buffer_cleaner()
    assert callable(a) and callable(b)


# --- copy() guards ---------------------------------------------------------


def test_copy_zero_buffer_size_raises() -> None:
    with pytest.raises(ValueError, match="buffer_size"):
        copy(io.BytesIO(b"x"), io.BytesIO(), buffer_size=0)


def test_copy_negative_buffer_size_raises() -> None:
    with pytest.raises(ValueError, match="buffer_size"):
        copy(io.BytesIO(b"x"), io.BytesIO(), buffer_size=-1)


def test_default_copy_buffer_constant() -> None:
    assert DEFAULT_COPY_BUFFER == 8192


# --- close_and_log_exception happy path + exception swallow ----------------


class _OkClosable:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class _BadClosable:
    def close(self) -> None:
        raise OSError("boom")


def test_close_and_log_exception_close_succeeds_returns_initial() -> None:
    logger = logging.getLogger("test_io_utils_coverage_ok")
    target = _OkClosable()
    out = close_and_log_exception(target, logger, "thing")
    assert target.closed is True
    assert out is None


def test_close_and_log_exception_close_fails_returns_new_exception(
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = logging.getLogger("test_io_utils_coverage_bad")
    caplog.set_level(logging.WARNING, logger="test_io_utils_coverage_bad")
    out = close_and_log_exception(_BadClosable(), logger, "thing")
    assert isinstance(out, OSError)
    assert any("Error closing thing" in rec.getMessage() for rec in caplog.records)


def test_close_and_log_exception_preserves_initial_exception() -> None:
    logger = logging.getLogger("test_io_utils_coverage_initial")
    initial = ValueError("first")
    out = close_and_log_exception(_BadClosable(), logger, "thing", initial)
    assert out is initial


# --- close_quietly suppresses ---------------------------------------------


def test_close_quietly_suppresses_close_exception() -> None:
    close_quietly(_BadClosable())  # no raise


# --- unmap helper ----------------------------------------------------------


def test_unmap_calls_close_on_object_with_close() -> None:
    cl = _OkClosable()
    unmap(cl)
    assert cl.closed is True


def test_unmap_handles_object_without_close() -> None:
    unmap("not closable")  # no exception
    unmap(None)


def test_unmap_swallows_close_exception() -> None:
    unmap(_BadClosable())  # no raise


# --- create_memory_only_stream_cache factory ------------------------------


def test_create_memory_only_stream_cache_returns_distinct_instances() -> None:
    factory = create_memory_only_stream_cache()
    a = factory()
    b = factory()
    assert a is not b


def test_create_temp_file_only_stream_cache_returns_callable() -> None:
    factory = create_temp_file_only_stream_cache()
    assert callable(factory)
    cache = factory()
    # ScratchFile-backed cache should be a real object.
    assert cache is not None


# --- create_protected_temp_dir / create_protected_temp_file ---------------


def test_create_protected_temp_dir_creates_directory_with_mode() -> None:
    path = create_protected_temp_dir()
    try:
        assert path.is_dir()
        if os.name != "nt":
            mode = path.stat().st_mode & 0o777
            assert mode == 0o700
    finally:
        if path.is_dir():
            import shutil
            shutil.rmtree(path, ignore_errors=True)


def test_create_protected_temp_file_with_explicit_dir_and_suffix(
    tmp_path: Path,
) -> None:
    path = create_protected_temp_file(tmp_path, "pre-", ".bin")
    try:
        assert path.is_file()
        assert path.name.startswith("pre-")
        assert path.suffix == ".bin"
        if os.name != "nt":
            mode = path.stat().st_mode & 0o777
            assert mode == 0o600
    finally:
        if path.exists():
            path.unlink()


def test_create_protected_temp_file_with_none_args(tmp_path: Path) -> None:
    # All None ⇒ defaults to system temp dir, no prefix, no suffix.
    path = create_protected_temp_file(None, None, None)
    try:
        assert path.is_file()
    finally:
        if path.exists():
            path.unlink()


# --- _apply_owner_only_permissions branch on Windows ----------------------


def test_apply_owner_only_permissions_no_op_on_windows(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    target = tmp_path / "marker.bin"
    target.write_bytes(b"x")
    monkeypatch.setattr(os, "name", "nt")
    # Should be a no-op (no chmod call); just ensure no exception.
    _apply_owner_only_permissions(target, is_directory=False)


# --- IOUtils.apply_owner_only_permissions / delete_path_recursively /
# register_for_deletion facades -------------------------------------------


def test_ioutils_apply_owner_only_permissions_facade(tmp_path: Path) -> None:
    f = tmp_path / "file.bin"
    f.write_bytes(b"x")
    IOUtils.apply_owner_only_permissions(f, is_directory=False)
    if os.name != "nt":
        mode = f.stat().st_mode & 0o777
        assert mode == 0o600


def test_ioutils_register_for_deletion_facade(tmp_path: Path) -> None:
    f = tmp_path / "register.bin"
    f.write_bytes(b"x")
    IOUtils.register_for_deletion(f)


def test_ioutils_delete_path_recursively_handles_dir(tmp_path: Path) -> None:
    d = tmp_path / "todelete"
    d.mkdir()
    (d / "x").write_bytes(b"x")
    IOUtils.delete_path_recursively(d)
    assert not d.exists()


def test_ioutils_delete_path_recursively_handles_file(tmp_path: Path) -> None:
    f = tmp_path / "todelete.bin"
    f.write_bytes(b"x")
    IOUtils.delete_path_recursively(f)
    assert not f.exists()


def test_ioutils_delete_path_recursively_silent_on_missing(tmp_path: Path) -> None:
    IOUtils.delete_path_recursively(tmp_path / "missing.bin")


def test_ioutils_create_protected_temp_dir_facade() -> None:
    path = IOUtils.create_protected_temp_dir()
    try:
        assert path.is_dir()
    finally:
        import shutil
        shutil.rmtree(path, ignore_errors=True)


# --- _delete_registered_paths exercises the cleanup hook ------------------


def test_delete_registered_paths_drains_queue(tmp_path: Path) -> None:
    d = tmp_path / "drain_dir"
    d.mkdir()
    f = tmp_path / "drain_file.bin"
    f.write_bytes(b"x")
    _register_for_deletion(d)
    _register_for_deletion(f)
    _delete_registered_paths()
    assert not d.exists()
    assert not f.exists()


# --- populate_buffer EOF break (line 183) --------------------------------


def test_populate_buffer_returns_eof_count_when_stream_drains_early() -> None:
    # Stream has only 3 bytes but buffer wants 10 — the inner ``if not chunk:
    # break`` path triggers when read returns b"".
    buf = bytearray(10)
    n = populate_buffer(io.BytesIO(b"abc"), buf)
    assert n == 3
    assert bytes(buf[:3]) == b"abc"


# --- delete_path_recursively OSError swallow (lines 107-108) -------------


def test_delete_path_recursively_swallows_oserror(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    f = tmp_path / "swallow.bin"
    f.write_bytes(b"x")

    def boom(_self: Path) -> bool:
        raise OSError("simulated")

    monkeypatch.setattr(Path, "is_dir", boom)
    # Must not raise.
    IOUtils.delete_path_recursively(f)


# --- IOUtils.close_and_log_exception facade (line 71) --------------------
# --- IOUtils.create_protected_temp_file facade (line 83) -----------------
# Wave 1367 fixed the signature drift on both facades; they now mirror the
# upstream IOUtils static-method shape.


def test_ioutils_close_and_log_exception_facade_close_succeeds() -> None:
    # Wrapper forwards positionally to the module-level helper.
    target = _OkClosable()
    IOUtils.close_and_log_exception(target, "name", "resource")
    assert target.closed is True


def test_ioutils_create_protected_temp_file_facade_default_args() -> None:
    # After wave 1367 fix, calling with no args succeeds (defaults match
    # upstream zero-arg form).
    path = IOUtils.create_protected_temp_file()
    try:
        assert path.exists()
        assert path.is_file()
    finally:
        path.unlink()
