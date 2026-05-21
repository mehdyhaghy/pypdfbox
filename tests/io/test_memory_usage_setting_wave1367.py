"""Wave 1367 — :class:`MemoryUsageSetting` factory + accessor coverage.

Targets validation branches in :mod:`pypdfbox.io.memory_usage_setting`:
* ``setup_mixed`` rejects ``max_main_memory_bytes < 0``.
* ``setup_mixed`` rejects ``max_storage_bytes < max_main_memory_bytes``.
* ``set_temp_dir`` round-trip via the fluent setter.
* ``to_string`` covers all four narrative templates.
* ``use_main_memory`` / ``use_temp_file`` matrix per mode.
"""

from __future__ import annotations

import os

import pytest

from pypdfbox.io.memory_usage_setting import (
    UNLIMITED,
    MemoryUsageSetting,
    StorageMode,
)


def test_main_memory_only_default_unlimited() -> None:
    s = MemoryUsageSetting.setup_main_memory_only()
    assert s.mode is StorageMode.MAIN_MEMORY_ONLY
    assert s.max_main_memory_bytes == UNLIMITED
    assert s.max_storage_bytes == UNLIMITED
    assert s.is_main_memory_only() is True
    assert s.is_main_memory_restricted() is False
    assert s.is_storage_restricted() is False
    assert s.use_main_memory() is True
    assert s.use_temp_file() is False


def test_main_memory_only_with_cap() -> None:
    s = MemoryUsageSetting.setup_main_memory_only(max_main_memory_bytes=4096)
    assert s.get_max_main_memory_bytes() == 4096
    assert s.is_main_memory_restricted() is True


def test_main_memory_only_invalid_cap_rejected() -> None:
    with pytest.raises(ValueError):
        MemoryUsageSetting.setup_main_memory_only(max_main_memory_bytes=-2)


def test_temp_file_only_default_unlimited() -> None:
    s = MemoryUsageSetting.setup_temp_file_only()
    assert s.mode is StorageMode.TEMP_FILE_ONLY
    assert s.max_main_memory_bytes == 0
    assert s.max_storage_bytes == UNLIMITED
    assert s.is_temp_file_only() is True
    assert s.use_main_memory() is False
    assert s.use_temp_file() is True


def test_temp_file_only_invalid_storage_rejected() -> None:
    with pytest.raises(ValueError):
        MemoryUsageSetting.setup_temp_file_only(max_storage_bytes=-3)


def test_mixed_basic() -> None:
    s = MemoryUsageSetting.setup_mixed(max_main_memory_bytes=1024)
    assert s.mode is StorageMode.MIXED
    assert s.use_main_memory() is True
    assert s.use_temp_file() is True


def test_mixed_rejects_negative_main_memory() -> None:
    with pytest.raises(ValueError):
        MemoryUsageSetting.setup_mixed(max_main_memory_bytes=-1)


def test_mixed_rejects_storage_smaller_than_main_memory() -> None:
    with pytest.raises(ValueError):
        MemoryUsageSetting.setup_mixed(
            max_main_memory_bytes=4096, max_storage_bytes=1024
        )


def test_mixed_with_unlimited_storage_ok() -> None:
    s = MemoryUsageSetting.setup_mixed(max_main_memory_bytes=4096)
    assert s.max_storage_bytes == UNLIMITED


def test_set_temp_dir_returns_self_and_mutates() -> None:
    s = MemoryUsageSetting.setup_main_memory_only()
    assert s.get_temp_dir() is None
    rv = s.set_temp_dir("/tmp/foo")
    # Fluent setter: chained return is the same instance.
    assert rv is s
    assert s.get_temp_dir() == "/tmp/foo"


def test_set_temp_dir_accepts_pathlike() -> None:
    s = MemoryUsageSetting.setup_main_memory_only()
    p = os.fspath("/tmp/bar")
    s.set_temp_dir(p)
    assert s.get_temp_dir() == p


def test_to_string_mixed_with_storage_cap() -> None:
    s = MemoryUsageSetting.setup_mixed(
        max_main_memory_bytes=4096, max_storage_bytes=8192
    )
    msg = s.to_string()
    assert "Mixed mode" in msg
    assert "4096" in msg
    assert "8192 storage bytes" in msg


def test_to_string_mixed_unrestricted_storage() -> None:
    s = MemoryUsageSetting.setup_mixed(max_main_memory_bytes=4096)
    msg = s.to_string()
    assert "Mixed mode" in msg
    assert "unrestricted scratch file size" in msg


def test_to_string_main_memory_only_capped() -> None:
    s = MemoryUsageSetting.setup_main_memory_only(max_main_memory_bytes=1024)
    msg = s.to_string()
    assert msg == "Main memory only with max. of 1024 bytes"


def test_to_string_main_memory_only_unrestricted() -> None:
    s = MemoryUsageSetting.setup_main_memory_only()
    msg = s.to_string()
    assert msg == "Main memory only with no size restriction"


def test_to_string_temp_file_only_capped() -> None:
    s = MemoryUsageSetting.setup_temp_file_only(max_storage_bytes=4096)
    msg = s.to_string()
    assert msg == "Scratch file only with max. of 4096 bytes"


def test_to_string_temp_file_only_unrestricted() -> None:
    s = MemoryUsageSetting.setup_temp_file_only()
    msg = s.to_string()
    assert msg == "Scratch file only with no size restriction"


def test_str_delegates_to_to_string() -> None:
    s = MemoryUsageSetting.setup_main_memory_only()
    assert str(s) == s.to_string()


def test_is_mixed_predicate() -> None:
    assert MemoryUsageSetting.setup_mixed(max_main_memory_bytes=0).is_mixed() is True
    assert MemoryUsageSetting.setup_main_memory_only().is_mixed() is False
    assert MemoryUsageSetting.setup_temp_file_only().is_mixed() is False
