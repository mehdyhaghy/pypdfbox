from __future__ import annotations

import pytest

from pypdfbox.io import UNLIMITED, MemoryUsageSetting, StorageMode


def test_setup_main_memory_only_unlimited() -> None:
    s = MemoryUsageSetting.setup_main_memory_only()
    assert s.mode is StorageMode.MAIN_MEMORY_ONLY
    assert s.is_main_memory_only()
    assert not s.is_temp_file_only()
    assert not s.is_mixed()
    assert not s.is_storage_restricted()
    assert not s.is_main_memory_restricted()


def test_setup_main_memory_only_with_cap() -> None:
    s = MemoryUsageSetting.setup_main_memory_only(max_main_memory_bytes=1024)
    assert s.is_main_memory_restricted()
    assert s.is_storage_restricted()
    assert s.max_storage_bytes == 1024


def test_setup_temp_file_only() -> None:
    s = MemoryUsageSetting.setup_temp_file_only()
    assert s.mode is StorageMode.TEMP_FILE_ONLY
    assert s.is_temp_file_only()
    assert s.max_main_memory_bytes == 0


def test_setup_temp_file_only_with_cap() -> None:
    s = MemoryUsageSetting.setup_temp_file_only(max_storage_bytes=10_000)
    assert s.is_storage_restricted()
    assert s.max_storage_bytes == 10_000


def test_setup_mixed() -> None:
    s = MemoryUsageSetting.setup_mixed(max_main_memory_bytes=512, max_storage_bytes=4096)
    assert s.is_mixed()
    assert s.max_main_memory_bytes == 512
    assert s.max_storage_bytes == 4096


def test_setup_mixed_unlimited_storage() -> None:
    s = MemoryUsageSetting.setup_mixed(max_main_memory_bytes=512)
    assert s.max_storage_bytes == UNLIMITED
    assert not s.is_storage_restricted()


def test_mixed_rejects_storage_below_memory() -> None:
    with pytest.raises(ValueError):
        MemoryUsageSetting.setup_mixed(max_main_memory_bytes=1000, max_storage_bytes=500)


def test_mixed_rejects_negative_memory() -> None:
    with pytest.raises(ValueError):
        MemoryUsageSetting.setup_mixed(max_main_memory_bytes=-1)


def test_invalid_limits_raise() -> None:
    with pytest.raises(ValueError):
        MemoryUsageSetting.setup_main_memory_only(max_main_memory_bytes=-2)
    with pytest.raises(ValueError):
        MemoryUsageSetting.setup_temp_file_only(max_storage_bytes=-5)


def test_setting_is_frozen() -> None:
    from dataclasses import FrozenInstanceError

    s = MemoryUsageSetting.setup_main_memory_only()
    with pytest.raises(FrozenInstanceError):
        s.max_main_memory_bytes = 999  # type: ignore[misc]
