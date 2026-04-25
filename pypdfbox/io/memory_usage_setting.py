from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class StorageMode(Enum):
    MAIN_MEMORY_ONLY = "main_memory_only"
    TEMP_FILE_ONLY = "temp_file_only"
    MIXED = "mixed"


# Sentinel used to indicate "no explicit cap"; consumers treat as unlimited.
UNLIMITED: int = -1


@dataclass(frozen=True)
class MemoryUsageSetting:
    """
    Policy for where parsed PDF objects (decoded streams in particular)
    are stored: in main memory, in a temporary file, or a mix that spills
    to disk after a memory threshold.

    Use the ``setup_*`` factory class methods rather than constructing
    directly — they validate the combinations.
    """

    mode: StorageMode
    max_main_memory_bytes: int
    max_storage_bytes: int  # main memory + temp file combined; UNLIMITED = no cap

    @classmethod
    def setup_main_memory_only(cls, max_main_memory_bytes: int = UNLIMITED) -> MemoryUsageSetting:
        cls._validate_limit(max_main_memory_bytes, "max_main_memory_bytes")
        return cls(
            mode=StorageMode.MAIN_MEMORY_ONLY,
            max_main_memory_bytes=max_main_memory_bytes,
            max_storage_bytes=max_main_memory_bytes,
        )

    @classmethod
    def setup_temp_file_only(cls, max_storage_bytes: int = UNLIMITED) -> MemoryUsageSetting:
        cls._validate_limit(max_storage_bytes, "max_storage_bytes")
        return cls(
            mode=StorageMode.TEMP_FILE_ONLY,
            max_main_memory_bytes=0,
            max_storage_bytes=max_storage_bytes,
        )

    @classmethod
    def setup_mixed(
        cls,
        max_main_memory_bytes: int,
        max_storage_bytes: int = UNLIMITED,
    ) -> MemoryUsageSetting:
        if max_main_memory_bytes < 0:
            raise ValueError("max_main_memory_bytes must be >= 0 in mixed mode")
        cls._validate_limit(max_storage_bytes, "max_storage_bytes")
        if (
            max_storage_bytes != UNLIMITED
            and max_storage_bytes < max_main_memory_bytes
        ):
            raise ValueError("max_storage_bytes must be >= max_main_memory_bytes")
        return cls(
            mode=StorageMode.MIXED,
            max_main_memory_bytes=max_main_memory_bytes,
            max_storage_bytes=max_storage_bytes,
        )

    @staticmethod
    def _validate_limit(value: int, name: str) -> None:
        if value < 0 and value != UNLIMITED:
            raise ValueError(f"{name} must be >= 0 or UNLIMITED")

    def is_main_memory_only(self) -> bool:
        return self.mode is StorageMode.MAIN_MEMORY_ONLY

    def is_temp_file_only(self) -> bool:
        return self.mode is StorageMode.TEMP_FILE_ONLY

    def is_mixed(self) -> bool:
        return self.mode is StorageMode.MIXED

    def is_storage_restricted(self) -> bool:
        return self.max_storage_bytes != UNLIMITED

    def is_main_memory_restricted(self) -> bool:
        return self.max_main_memory_bytes != UNLIMITED
