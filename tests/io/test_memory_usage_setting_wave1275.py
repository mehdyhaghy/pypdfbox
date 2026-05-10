"""Wave 1275 — explicit ``to_string()`` parity for MemoryUsageSetting."""

from __future__ import annotations

from pypdfbox.io.memory_usage_setting import MemoryUsageSetting


def test_main_memory_only_unrestricted_to_string() -> None:
    s = MemoryUsageSetting.setup_main_memory_only()
    assert s.to_string() == "Main memory only with no size restriction"


def test_main_memory_only_restricted_to_string() -> None:
    s = MemoryUsageSetting.setup_main_memory_only(2048)
    assert s.to_string() == "Main memory only with max. of 2048 bytes"


def test_temp_file_only_unrestricted_to_string() -> None:
    s = MemoryUsageSetting.setup_temp_file_only()
    assert s.to_string() == "Scratch file only with no size restriction"


def test_temp_file_only_restricted_to_string() -> None:
    s = MemoryUsageSetting.setup_temp_file_only(max_storage_bytes=1024)
    assert s.to_string() == "Scratch file only with max. of 1024 bytes"


def test_mixed_unrestricted_to_string() -> None:
    s = MemoryUsageSetting.setup_mixed(1024)
    assert s.to_string() == (
        "Mixed mode with max. of 1024 main memory bytes"
        " and unrestricted scratch file size"
    )


def test_mixed_restricted_to_string() -> None:
    s = MemoryUsageSetting.setup_mixed(1024, max_storage_bytes=4096)
    assert s.to_string() == (
        "Mixed mode with max. of 1024 main memory bytes"
        " and max. of 4096 storage bytes"
    )


def test_str_delegates_to_to_string() -> None:
    s = MemoryUsageSetting.setup_main_memory_only(512)
    assert str(s) == s.to_string()
