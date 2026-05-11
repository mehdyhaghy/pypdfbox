"""Wave 1281: IOUtils factory helpers."""

from __future__ import annotations

import os
import stat
from pathlib import Path

from pypdfbox.io import (
    RandomAccessStreamCache,
    create_memory_only_stream_cache,
    create_protected_temp_dir,
    create_protected_temp_file,
    create_temp_file_only_stream_cache,
)


def test_create_memory_only_stream_cache_yields_factory() -> None:
    factory = create_memory_only_stream_cache()
    cache = factory()
    assert isinstance(cache, RandomAccessStreamCache)
    buf = cache.create_buffer()
    assert buf is not None
    buf.close()
    cache.close()


def test_create_temp_file_only_stream_cache_yields_factory() -> None:
    factory = create_temp_file_only_stream_cache()
    cache = factory()
    # ``ScratchFile`` does not subclass ``RandomAccessStreamCache``
    # in pypdfbox but quacks like one.
    assert hasattr(cache, "create_buffer")
    cache.close()


def test_protected_temp_dir_has_owner_only_mode_when_posix() -> None:
    path = create_protected_temp_dir()
    assert path.is_dir()
    if os.name != "nt":
        mode = path.stat().st_mode & 0o777
        assert mode == stat.S_IRWXU
    # Caller does not have to clean up; the shutdown hook will.


def test_protected_temp_file_has_owner_only_mode_when_posix() -> None:
    path = create_protected_temp_file(None, "test", ".tmp")
    try:
        assert path.is_file()
        if os.name != "nt":
            mode = path.stat().st_mode & 0o777
            assert mode == stat.S_IRUSR | stat.S_IWUSR
    finally:
        Path(path).unlink(missing_ok=True)
