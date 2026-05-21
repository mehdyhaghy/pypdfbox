from __future__ import annotations

import atexit
import contextlib
import logging
import os
import shutil
import stat
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, BinaryIO, Protocol

if TYPE_CHECKING:
    from .random_access_stream_cache import RandomAccessStreamCache
    from .stream_cache_create_function import StreamCacheCreateFunction


DEFAULT_COPY_BUFFER: int = 8192


class IOUtils:
    """Class-shaped facade mirroring ``org.apache.pdfbox.io.IOUtils``.

    Upstream Java declares ``IOUtils`` as a ``public final class`` with
    static methods. Python prefers module-level functions, so the canonical
    implementations live below as module-level callables; this class
    re-exports them as ``@staticmethod`` for parity with the upstream
    class shape (callers porting ``IOUtils.copy(...)`` find the expected
    name).
    """

    @staticmethod
    def copy(
        in_stream: BinaryIO, out_stream: BinaryIO, buffer_size: int = DEFAULT_COPY_BUFFER
    ) -> int:
        return copy(in_stream, out_stream, buffer_size)

    @staticmethod
    def to_byte_array(in_stream: BinaryIO, buffer_size: int = DEFAULT_COPY_BUFFER) -> bytes:
        return to_byte_array(in_stream, buffer_size)

    @staticmethod
    def close_quietly(closeable: _Closeable | None) -> None:
        close_quietly(closeable)

    @staticmethod
    def populate_buffer(in_stream: BinaryIO, buffer: bytearray) -> int:
        return populate_buffer(in_stream, buffer)

    @staticmethod
    def create_memory_only_stream_cache() -> StreamCacheCreateFunction:
        return create_memory_only_stream_cache()

    @staticmethod
    def create_temp_file_only_stream_cache() -> StreamCacheCreateFunction:
        return create_temp_file_only_stream_cache()

    @staticmethod
    def unmap(buf: object) -> None:
        unmap(buf)

    @staticmethod
    def close_and_log_exception(
        closeable: _Closeable | None,
        logger: logging.Logger | str | None = None,
        resource_name: str | None = None,
        initial_exception: BaseException | None = None,
    ) -> BaseException | None:
        """Close *closeable* (if any) and log a warning if it raises.

        Mirrors upstream ``IOUtils.closeAndLogException``. Accepts either a
        :class:`logging.Logger` instance or a logger *name* (string) so call
        sites that pass the upstream ``LogFactory.getLog(name)`` idiom keep
        working; ``None`` falls back to this module's logger.
        """
        if closeable is None:
            return initial_exception
        if isinstance(logger, str) or logger is None:
            resolved = logging.getLogger(logger) if logger else _log
        else:
            resolved = logger
        return close_and_log_exception(
            closeable, resolved, resource_name or "", initial_exception
        )

    @staticmethod
    def create_protected_temp_dir() -> Path:
        """Mirrors upstream ``IOUtils.createProtectedTempDir``."""
        return create_protected_temp_dir()

    @staticmethod
    def create_protected_temp_file(
        prefix: str = "pypdfbox-",
        suffix: str = "",
        directory: Path | str | None = None,
    ) -> Path:
        """Mirrors upstream ``IOUtils.createProtectedTempFile``.

        The ``directory`` argument defaults to ``None`` (system temp), so
        callers using the upstream zero-/two-arg shapes work unchanged.
        """
        return create_protected_temp_file(directory, prefix, suffix)

    @staticmethod
    def apply_owner_only_permissions(path: Path, *, is_directory: bool) -> None:
        """Mirrors upstream private ``IOUtils.applyOwnerOnlyPermissions`` —
        ensures *path* is owner-only readable/writable."""
        _apply_owner_only_permissions(path, is_directory=is_directory)

    @staticmethod
    def register_for_deletion(path: Path) -> None:
        """Mirrors upstream private ``IOUtils.registerForDeletion`` —
        schedules *path* for deletion at interpreter shutdown."""
        _register_for_deletion(path)

    @staticmethod
    def delete_path_recursively(path: Path) -> None:
        """Mirrors upstream ``IOUtils.deletePathRecursively`` — best-effort
        recursive delete that swallows ``OSError`` to mirror Java's
        ``IOException``-tolerant shutdown hook."""
        try:
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
            elif path.exists():
                path.unlink()
        except OSError:
            pass

    @staticmethod
    def new_buffer_cleaner() -> object:
        """Mirrors upstream ``IOUtils.newBufferCleaner`` — returns a
        callable that unmaps memory-mapped buffers. Python's ``mmap``
        objects are released by GC, so this returns :meth:`unmap`."""
        return IOUtils.unmap

    @staticmethod
    def unmapper() -> object:
        """Mirrors upstream ``IOUtils.unmapper`` — alias of
        :meth:`new_buffer_cleaner`."""
        return IOUtils.new_buffer_cleaner()

_log = logging.getLogger(__name__)

# Tracks temporary directories created by ``create_protected_temp_dir`` so
# they can be cleaned up at interpreter shutdown — mirrors upstream's
# shutdown-hook list (``TEMP_DIRS_TO_DELETE``).
_TEMP_DIRS_TO_DELETE: list[Path] = []
_SHUTDOWN_HOOK_REGISTERED = False


class _Closeable(Protocol):
    def close(self) -> None: ...


def copy(in_stream: BinaryIO, out_stream: BinaryIO, buffer_size: int = DEFAULT_COPY_BUFFER) -> int:
    """
    Copy all bytes from ``in_stream`` to ``out_stream``. Returns the total
    number of bytes copied.
    """
    if buffer_size <= 0:
        raise ValueError("buffer_size must be > 0")
    total = 0
    while True:
        chunk = in_stream.read(buffer_size)
        if not chunk:
            break
        out_stream.write(chunk)
        total += len(chunk)
    return total


def to_byte_array(in_stream: BinaryIO, buffer_size: int = DEFAULT_COPY_BUFFER) -> bytes:
    """Read ``in_stream`` to EOF and return its contents as bytes."""
    chunks: list[bytes] = []
    while True:
        chunk = in_stream.read(buffer_size)
        if not chunk:
            break
        chunks.append(chunk)
    return b"".join(chunks)


def close_quietly(closeable: _Closeable | None) -> None:
    """Close ``closeable`` if non-None; suppress any exception."""
    if closeable is None:
        return
    with contextlib.suppress(Exception):
        closeable.close()


def populate_buffer(in_stream: BinaryIO, buffer: bytearray) -> int:
    """
    Fill ``buffer`` from ``in_stream``. Returns the number of bytes actually
    read; less than ``len(buffer)`` indicates EOF was reached.
    """
    total = 0
    target = len(buffer)
    mv = memoryview(buffer)
    while total < target:
        chunk = in_stream.read(target - total)
        if not chunk:
            break
        n = len(chunk)
        mv[total : total + n] = chunk
        total += n
    return total


def close_and_log_exception(
    closeable: _Closeable,
    logger: logging.Logger,
    resource_name: str,
    initial_exception: BaseException | None = None,
) -> BaseException | None:
    """Close an I/O resource, logging (but not raising) any failure.

    Mirrors upstream ``IOUtils.closeAndLogException`` in semantics:

    * Always attempts ``closeable.close()``.
    * On failure, logs a warning with ``resource_name``.
    * Returns the new exception only when ``initial_exception`` is ``None``
      — so callers can carry forward an in-flight error without losing it.
    * Returns ``initial_exception`` unchanged when it was supplied (whether
      or not close succeeded).
    """
    try:
        closeable.close()
    except Exception as exc:
        logger.warning("Error closing %s: %s", resource_name, exc)
        if initial_exception is None:
            return exc
    return initial_exception


def create_memory_only_stream_cache() -> StreamCacheCreateFunction:
    """Return a factory that produces fresh in-memory stream caches.

    Mirrors upstream ``IOUtils.createMemoryOnlyStreamCache`` (Java line
    362). Memory-only caches use unrestricted main memory.
    """
    # Local import — random_access_stream_cache_impl imports back to
    # io_utils indirectly through the package __init__.
    from .random_access_stream_cache_impl import (  # noqa: PLC0415
        RandomAccessStreamCacheImpl,
    )

    def _create() -> RandomAccessStreamCache:
        return RandomAccessStreamCacheImpl()

    return _create


def create_temp_file_only_stream_cache() -> StreamCacheCreateFunction:
    """Return a factory that produces fresh temp-file stream caches.

    Mirrors upstream ``IOUtils.createTempFileOnlyStreamCache`` (Java line
    373). The upstream form routes through
    ``MemoryUsageSetting.setupTempFileOnly().streamCache``. We surface a
    ``ScratchFile``-backed cache directly because pypdfbox's
    ``MemoryUsageSetting`` does not yet expose a ``stream_cache`` field.
    """
    from .memory_usage_setting import MemoryUsageSetting  # noqa: PLC0415
    from .scratch_file import ScratchFile  # noqa: PLC0415

    setting = MemoryUsageSetting.setup_temp_file_only()

    def _create() -> RandomAccessStreamCache:
        return ScratchFile(setting)

    return _create


def create_protected_temp_dir() -> Path:
    """Create a temp directory with owner-only permissions.

    Mirrors upstream ``IOUtils.createProtectedTempDir`` (Java line 389).
    Returns a freshly created directory rooted under the system temp
    location. Schedules deletion at interpreter shutdown.
    """
    path = Path(tempfile.mkdtemp(prefix="pypdfbox-"))
    _apply_owner_only_permissions(path, is_directory=True)
    _register_for_deletion(path)
    return path


def create_protected_temp_file(
    directory: Path | str | None,
    prefix: str | None,
    suffix: str | None,
) -> Path:
    """Create a temp file with owner-only permissions.

    Mirrors upstream ``IOUtils.createProtectedTempFile`` (Java line 463).
    Unlike :func:`create_protected_temp_dir` no shutdown-hook deletion
    is registered — the caller owns lifecycle.
    """
    dir_str = os.fspath(directory) if directory is not None else None
    fd, name = tempfile.mkstemp(prefix=prefix or "", suffix=suffix or "", dir=dir_str)
    os.close(fd)
    path = Path(name)
    _apply_owner_only_permissions(path, is_directory=False)
    return path


def _apply_owner_only_permissions(path: Path, *, is_directory: bool) -> None:
    if os.name == "nt":
        # On Windows there is no chmod analogue to POSIX file modes; rely
        # on default ACL inheritance. Upstream falls back to ACL hacks;
        # we accept the platform default for parity simplicity.
        return
    mode = stat.S_IRWXU if is_directory else stat.S_IRUSR | stat.S_IWUSR
    os.chmod(path, mode)


def _register_for_deletion(path: Path) -> None:
    global _SHUTDOWN_HOOK_REGISTERED
    _TEMP_DIRS_TO_DELETE.append(path)
    if not _SHUTDOWN_HOOK_REGISTERED:
        atexit.register(_delete_registered_paths)
        _SHUTDOWN_HOOK_REGISTERED = True


def _delete_registered_paths() -> None:
    while _TEMP_DIRS_TO_DELETE:
        p = _TEMP_DIRS_TO_DELETE.pop()
        with contextlib.suppress(Exception):
            if p.is_dir():
                shutil.rmtree(p, ignore_errors=True)
            elif p.exists():
                p.unlink()


def unmap(buf: object) -> None:
    """No-op stub for parity with upstream ``IOUtils.unmap``.

    Upstream releases JVM memory-mapped ``ByteBuffer`` instances eagerly
    via ``sun.misc.Unsafe`` because the JVM otherwise pins the underlying
    file. CPython's ``mmap`` releases its file lock when the object is
    garbage-collected (or its ``close()`` is called), so the explicit
    unmap step is unnecessary here. We accept any object so call sites
    can be ported mechanically; if the object exposes ``close()`` we call
    it as a best-effort hook (matches the pragmatic intent of the
    upstream method).
    """
    if buf is None:
        return
    close = getattr(buf, "close", None)
    if callable(close):
        with contextlib.suppress(Exception):
            close()
