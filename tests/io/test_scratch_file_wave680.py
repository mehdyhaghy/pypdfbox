from __future__ import annotations

import types

import pytest

from pypdfbox.io import UNLIMITED, MemoryUsageSetting, ScratchFile, StorageMode


def test_wave680_max_main_memory_bytes_mixed_default_and_non_mixed_cap() -> None:
    mixed_without_cap = MemoryUsageSetting(
        mode=StorageMode.MIXED,
        max_main_memory_bytes=UNLIMITED,
        max_storage_bytes=UNLIMITED,
    )

    with ScratchFile(mixed_without_cap) as scratch:
        assert scratch.get_max_main_memory_bytes() == 16 * 1024 * 1024

    with ScratchFile(MemoryUsageSetting.setup_main_memory_only(128)) as scratch:
        assert scratch.get_max_main_memory_bytes() == 128


def test_wave680_validate_page_io_rejects_offset_past_buffer() -> None:
    with ScratchFile(page_size=4) as scratch:
        page = scratch.get_new_page()

        with pytest.raises(ValueError, match="offset/length out of range"):
            scratch.write_page(page, b"abc", offset=2, length=2)


def test_wave680_reused_temp_file_page_is_zeroed() -> None:
    with ScratchFile(MemoryUsageSetting.setup_temp_file_only(), page_size=4) as scratch:
        page = scratch.get_new_page()
        scratch.write_page(page, b"ABCD")
        scratch.mark_pages_as_free([page])

        reused = scratch.get_new_page()

        buf = bytearray(4)
        scratch.read_page(reused, buf)
        assert reused == page
        assert bytes(buf) == b"\x00\x00\x00\x00"


def test_wave680_should_use_main_memory_honors_unlimited_cap() -> None:
    with ScratchFile(MemoryUsageSetting.setup_mixed(0), page_size=4) as scratch:
        scratch.get_max_main_memory_bytes = types.MethodType(  # type: ignore[method-assign]
            lambda self: UNLIMITED,
            scratch,
        )

        assert scratch._should_use_main_memory() is True  # noqa: SLF001


def test_wave680_file_backed_page_without_mapping_reads_as_zeroes() -> None:
    with ScratchFile(MemoryUsageSetting.setup_temp_file_only(), page_size=4) as scratch:
        scratch._page_count = 1  # noqa: SLF001
        scratch._mem_pages.append(None)  # noqa: SLF001

        buf = bytearray(b"xxxx")

        assert scratch.read_page(0, buf) == 4
        assert bytes(buf) == b"\x00\x00\x00\x00"


def test_wave680_file_backed_store_allocates_missing_mapping_lazily() -> None:
    with ScratchFile(MemoryUsageSetting.setup_temp_file_only(), page_size=4) as scratch:
        scratch._page_count = 1  # noqa: SLF001
        scratch._mem_pages.append(None)  # noqa: SLF001

        scratch.write_page(0, b"AB", length=2)

        buf = bytearray(4)
        scratch.read_page(0, buf)
        assert bytes(buf) == b"AB\x00\x00"
