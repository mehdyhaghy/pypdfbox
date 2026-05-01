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


# ----- upstream parity round-out -----


def test_use_main_memory_and_use_temp_file() -> None:
    mm = MemoryUsageSetting.setup_main_memory_only()
    assert mm.use_main_memory() is True
    assert mm.use_temp_file() is False

    tf = MemoryUsageSetting.setup_temp_file_only()
    assert tf.use_main_memory() is False
    assert tf.use_temp_file() is True

    mx = MemoryUsageSetting.setup_mixed(max_main_memory_bytes=1024)
    assert mx.use_main_memory() is True
    assert mx.use_temp_file() is True


def test_get_max_accessors_match_attributes() -> None:
    s = MemoryUsageSetting.setup_mixed(
        max_main_memory_bytes=512, max_storage_bytes=4096
    )
    assert s.get_max_main_memory_bytes() == s.max_main_memory_bytes == 512
    assert s.get_max_storage_bytes() == s.max_storage_bytes == 4096


def test_set_temp_dir_chains_and_get_temp_dir(tmp_path) -> None:
    s = MemoryUsageSetting.setup_temp_file_only()
    assert s.get_temp_dir() is None
    returned = s.set_temp_dir(tmp_path)
    assert returned is s  # fluent setter
    assert s.get_temp_dir() == tmp_path
    # Allow clearing back to None.
    s.set_temp_dir(None)
    assert s.get_temp_dir() is None


def test_str_main_memory_only_unrestricted() -> None:
    s = MemoryUsageSetting.setup_main_memory_only()
    assert str(s) == "Main memory only with no size restriction"


def test_str_main_memory_only_restricted() -> None:
    s = MemoryUsageSetting.setup_main_memory_only(max_main_memory_bytes=2048)
    assert str(s) == "Main memory only with max. of 2048 bytes"


def test_str_temp_file_only_variants() -> None:
    assert str(MemoryUsageSetting.setup_temp_file_only()) == (
        "Scratch file only with no size restriction"
    )
    assert str(MemoryUsageSetting.setup_temp_file_only(max_storage_bytes=1024)) == (
        "Scratch file only with max. of 1024 bytes"
    )


def test_str_mixed_variants() -> None:
    s = MemoryUsageSetting.setup_mixed(max_main_memory_bytes=512)
    assert str(s) == (
        "Mixed mode with max. of 512 main memory bytes and unrestricted scratch file size"
    )
    s = MemoryUsageSetting.setup_mixed(
        max_main_memory_bytes=512, max_storage_bytes=4096
    )
    assert str(s) == (
        "Mixed mode with max. of 512 main memory bytes and max. of 4096 storage bytes"
    )
